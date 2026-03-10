from fastapi import APIRouter, Query, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import os
import json
from api.models import PolygonsResponse
from api.services.polygons import curated_polygons_path, parse_bbox, bbox_small, geom_bbox, bbox_intersects, tile_bbox
from api.utils.cache import cache_get, cache_set
from api.deps import rate_limiter

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
):
    Depends(rate_limiter)
    path = curated_polygons_path(dataset, region, scenario, format_)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="curated polygons not found")
    try:
        with open(path, "r") as f:
            data = json.load(f)
        feats = data.get("features") or []
        cnt = len(feats) if isinstance(feats, list) else 0
    except Exception:
        cnt = None
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
            return JSONResponse(content=result, headers={"ETag": etag, "Cache-Control": "public, max-age=30"})
        try:
            with open(path, "r") as f:
                doc = json.load(f)
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
            cache_set(key, {"data": payload, "count": len(filtered)}, ttl=30)
            etag = f"W/{hash((path, bbox, len(filtered)))}"
            return JSONResponse(content=result, headers={"ETag": etag, "Cache-Control": "public, max-age=30"})
        except Exception:
            raise HTTPException(status_code=500, detail="failed to build inline response")
    # metadata-only response
    etag = f"W/{hash((path, result['count']))}"
    return JSONResponse(content=result, headers={"ETag": etag, "Cache-Control": "public, max-age=30"})

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
):
    Depends(rate_limiter)
    path = curated_polygons_path(dataset, region, scenario, format_)
    bbox = tile_bbox(z, x, y)
    key = f"poly:tile:{dataset}:{region}:{scenario}:{format_}:{z}:{x}:{y}"
    cached = cache_get(key)
    if cached is not None:
        return cached
    try:
        feats = []
        if os.path.exists(path):
            with open(path, "r") as f:
                doc = json.load(f)
            feats = doc.get("features") or []
        filtered = []
        for feat in feats:
            gb = geom_bbox(feat.get("geometry") or {})
            if gb and bbox_intersects(gb, bbox):
                filtered.append(feat)
        payload = {"type": "FeatureCollection", "features": filtered}
        cache_set(key, payload, ttl=30)
        etag = f"W/{hash((path, z, x, y, len(filtered)))}"
        return JSONResponse(content=payload, headers={"ETag": etag, "Cache-Control": "public, max-age=30"})
    except Exception:
        raise HTTPException(status_code=500, detail="failed to build tile")
