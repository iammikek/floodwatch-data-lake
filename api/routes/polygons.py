from fastapi import APIRouter, Query, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import os
import json
from api.models import PolygonsResponse
from api.services.polygons import curated_polygons_path, parse_bbox, bbox_small, geom_bbox, bbox_intersects, tile_bbox, read_geojson_any
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
    path = curated_polygons_path(dataset, region, scenario, format_)
    try:
        data = read_geojson_any(path)
        feats = data.get("features") or []
        cnt = len(feats) if isinstance(feats, list) else 0
    except Exception:
        raise HTTPException(status_code=404, detail="curated polygons not found")
    result: Dict[str, Any] = {
        "region_id": region,
        "dataset": dataset,
        "scenario": scenario,
        "format": format_,
        "path": path,
        "count": cnt,
    }
    if inline:
        if not bbox:
            raise HTTPException(status_code=400, detail="bbox is required when inline=true")
        w, s, e, n = parse_bbox(bbox)
        if not bbox_small(w, s, e, n):
            raise HTTPException(status_code=400, detail="bbox too large for inline response")
        key = f"poly:inline:{dataset}:{region}:{scenario}:{format_}:{bbox}"
        cached = cache_get(key)
        if cached is not None:
            result["data"] = cached["data"]
            result["count"] = cached["count"]
            etag = f"W/{hash((path, bbox, result['count']))}"
            ttl = polygons_ttl()
            headers = {"ETag": etag, "Cache-Control": f"public, max-age={ttl}", "X-RateLimit-Limit": str(rl["limit"]), "X-RateLimit-Remaining": str(rl["remaining"]), "X-RateLimit-Reset": str(rl["reset"])}
            return JSONResponse(content=result, headers=headers)
        try:
            doc = read_geojson_any(path)
            feats = doc.get("features") or []
            target = [w, s, e, n]
            filtered: List[Dict[str, Any]] = []
            for feat in feats:
                gb = geom_bbox(feat.get("geometry") or {})
                if gb and bbox_intersects(gb, target):
                    filtered.append(feat)
            payload = {"type": "FeatureCollection", "features": filtered}
            result["data"] = payload
            result["count"] = len(filtered)
            ttl = polygons_ttl()
            cache_set(key, {"data": payload, "count": len(filtered)}, ttl=ttl)
            etag = f"W/{hash((path, bbox, len(filtered)))}"
            headers = {"ETag": etag, "Cache-Control": f"public, max-age={ttl}", "X-RateLimit-Limit": str(rl["limit"]), "X-RateLimit-Remaining": str(rl["remaining"]), "X-RateLimit-Reset": str(rl["reset"])}
            return JSONResponse(content=result, headers=headers)
        except Exception:
            raise HTTPException(status_code=500, detail="failed to build inline response")
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
