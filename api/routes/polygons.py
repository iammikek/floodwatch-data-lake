from fastapi import APIRouter, Query, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import os
import json
from api.models import PolygonsResponse
from api.services.polygons import (
    parse_bbox,
    bbox_small,
    geom_bbox,
    bbox_intersects,
    tile_bbox,
    read_geojson_any,
    prepare_inline_features,
    resolve_curated_polygons_path,
    curated_polygons_path,
    _GEOJSON_CACHE,
    _remote_base,
)
from api.utils.cache import cache_get, cache_set
from api.deps import rate_limiter, polygons_ttl

router = APIRouter()

@router.get("/v1/polygons", response_model=PolygonsResponse)
def get_polygons(
    request: Request,
    dataset: str = Query(..., pattern="^(flood_zones|rse)$"),
    region: str = Query(..., pattern="^(BRI|SOM|DOR|DEV|CON)$"),
    scenario: Optional[str] = Query(None, pattern="^(defended_1in100_1in200|undefended_1in100_1in200|defended_1in1000|undefended_1in1000)$"),
    format_: str = Query("simplified", alias="format", pattern="^(simplified|normalized)$"),
    inline: bool = False,
    bbox: Optional[str] = None,
    rl: Dict[str, int] = Depends(rate_limiter),
):
    path, resolved_format = resolve_curated_polygons_path(dataset, region, scenario, format_)
    # Reject oversized inline bboxes before loading GeoJSON (can be 100MB+).
    if inline:
        if not bbox:
            raise HTTPException(status_code=400, detail="bbox is required when inline=true")
        w, s, e, n = parse_bbox(bbox)
        if not bbox_small(w, s, e, n):
            raise HTTPException(status_code=400, detail="bbox too large for inline response")
        key = f"poly:inline:v2:{dataset}:{region}:{scenario}:{resolved_format}:{bbox}"
        cached = cache_get(key)
        if cached is not None:
            result = {
                "region_id": region,
                "dataset": dataset,
                "scenario": scenario,
                "format": resolved_format,
                "path": path,
                "count": cached["count"],
                "data": cached["data"],
            }
            etag = f"W/{hash((path, bbox, result['count']))}"
            ttl = polygons_ttl()
            headers = {"ETag": etag, "Cache-Control": f"public, max-age={ttl}", "X-RateLimit-Limit": str(rl["limit"]), "X-RateLimit-Remaining": str(rl["remaining"]), "X-RateLimit-Reset": str(rl["reset"])}
            return JSONResponse(content=result, headers=headers)
        try:
            doc = read_geojson_any(path)
            feats = doc.get("features") or []
            filtered = prepare_inline_features(feats if isinstance(feats, list) else [], [w, s, e, n])
            payload = {"type": "FeatureCollection", "features": filtered}
            result = {
                "region_id": region,
                "dataset": dataset,
                "scenario": scenario,
                "format": resolved_format,
                "path": path,
                "count": len(filtered),
                "data": payload,
            }
            ttl = polygons_ttl()
            cache_set(key, {"data": payload, "count": len(filtered)}, ttl=ttl)
            etag = f"W/{hash((path, bbox, len(filtered)))}"
            headers = {"ETag": etag, "Cache-Control": f"public, max-age={ttl}", "X-RateLimit-Limit": str(rl["limit"]), "X-RateLimit-Remaining": str(rl["remaining"]), "X-RateLimit-Reset": str(rl["reset"])}
            return JSONResponse(content=result, headers=headers)
        except Exception:
            raise HTTPException(status_code=500, detail="failed to build inline response")

    try:
        if not os.path.exists(path) and not _remote_base():
            raise FileNotFoundError(path)
        # Avoid parsing 100MB+ GeoJSON just for metadata; count is approximate (-1 = unknown).
        cached = _GEOJSON_CACHE.get(path)
        if cached is not None:
            feats = cached[1].get("features") or []
            cnt = len(feats) if isinstance(feats, list) else 0
        elif os.path.exists(path):
            cnt = -1
        else:
            data = read_geojson_any(path)
            feats = data.get("features") or []
            cnt = len(feats) if isinstance(feats, list) else 0
    except Exception:
        raise HTTPException(status_code=404, detail="curated polygons not found")
    result: Dict[str, Any] = {
        "region_id": region,
        "dataset": dataset,
        "scenario": scenario,
        "format": resolved_format,
        "path": path,
        "count": cnt,
    }
    # metadata-only response
    etag = f"W/{hash((path, result['count']))}"
    ttl = polygons_ttl()
    headers = {"ETag": etag, "Cache-Control": f"public, max-age={ttl}", "X-RateLimit-Limit": str(rl["limit"]), "X-RateLimit-Remaining": str(rl["remaining"]), "X-RateLimit-Reset": str(rl["reset"])}
    return JSONResponse(content=result, headers=headers)

@router.get("/v1/polygons/tiles/{dataset}/{z}/{x}/{y}")
def get_polygon_tile(
    request: Request,
    dataset: str,
    z: int,
    x: int,
    y: int,
    region: str = Query(..., pattern="^(BRI|SOM|DOR|DEV|CON)$"),
    scenario: Optional[str] = Query(None, pattern="^(defended_1in100_1in200|undefended_1in100_1in200|defended_1in1000|undefended_1in1000)$"),
    format_: str = Query("simplified", alias="format", pattern="^(simplified|normalized)$"),
    rl: Dict[str, int] = Depends(rate_limiter),
):
    path = curated_polygons_path(dataset, region, scenario, format_)
    bbox = tile_bbox(z, x, y)
    key = f"poly:tile:{dataset}:{region}:{scenario}:{format_}:{z}:{x}:{y}"
    cached = cache_get(key)
    if cached is not None:
        ttl = polygons_ttl()
        etag = f"W/{hash((path, z, x, y, len((cached.get('features') or []))) )}"
        headers = {"ETag": etag, "Cache-Control": f"public, max-age={ttl}", "X-RateLimit-Limit": str(rl["limit"]), "X-RateLimit-Remaining": str(rl["remaining"]), "X-RateLimit-Reset": str(rl["reset"])}
        return JSONResponse(content=cached, headers=headers)
    try:
        doc = read_geojson_any(path)
        feats = doc.get("features") or []
        filtered = []
        for feat in feats:
            gb = geom_bbox(feat.get("geometry") or {})
            if gb and bbox_intersects(gb, bbox):
                filtered.append(feat)
        payload = {"type": "FeatureCollection", "features": filtered}
        ttl = polygons_ttl()
        cache_set(key, payload, ttl=ttl)
        etag = f"W/{hash((path, z, x, y, len(filtered)))}"
        headers = {"ETag": etag, "Cache-Control": f"public, max-age={ttl}", "X-RateLimit-Limit": str(rl["limit"]), "X-RateLimit-Remaining": str(rl["remaining"]), "X-RateLimit-Reset": str(rl["reset"])}
        return JSONResponse(content=payload, headers=headers)
    except Exception:
        raise HTTPException(status_code=500, detail="failed to build tile")
