import os
import json
import math
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
import httpx


def curated_polygons_path(dataset: str, region: str, scenario: Optional[str], format_: str) -> str:
    base_dir = os.path.join("data", "curated", "ea")
    if dataset not in ("flood_zones", "rse"):
        raise HTTPException(status_code=400, detail="dataset must be flood_zones or rse")
    if format_ not in ("simplified", "normalized"):
        raise HTTPException(status_code=400, detail="format must be simplified or normalized")
    if dataset == "flood_zones":
        name = f"{region}_fz2_3"
    else:
        if not scenario:
            raise HTTPException(status_code=400, detail="scenario is required for rse dataset")
        name = f"{region}_{scenario}"
    suffix = "_simplified" if format_ == "simplified" else "_normalized"
    return os.path.join(base_dir, f"{name}{suffix}.geojson")

def _remote_base() -> Optional[str]:
    base = os.getenv("REMOTE_BASE_URL")
    if base and base.strip():
        return base.rstrip("/")
    return None

def read_geojson_any(path: str) -> Dict[str, Any]:
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    base = _remote_base()
    if not base:
        return {"type": "FeatureCollection", "features": []}
    # Map local path 'data/curated/ea/<file>' to remote '<base>/ea/<file>'
    parts = path.split("data/curated/")
    key = parts[1] if len(parts) > 1 else os.path.basename(path)
    url = f"{base}/{key.lstrip('/')}"
    try:
        client = httpx.Client(timeout=30, headers={"Accept": "application/geo+json, application/json;q=0.9"})
        r = client.get(url)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {"type": "FeatureCollection", "features": []}

def parse_bbox(bbox: str) -> List[float]:
    parts = [float(x) for x in bbox.split(",")]
    if len(parts) != 4:
        raise HTTPException(status_code=400, detail="bbox must be west,south,east,north")
    return parts

def bbox_small(w: float, s: float, e: float, n: float) -> bool:
    width = abs(e - w)
    height = abs(n - s)
    return width <= 0.5 and height <= 0.5

def geom_bbox(geom: Dict[str, Any]) -> Optional[List[float]]:
    t = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return None
    xs: List[float] = []
    ys: List[float] = []
    def add_points(points):
        for p in points:
            xs.append(p[0])
            ys.append(p[1])
    if t == "Polygon":
        for ring in coords:
            add_points(ring)
    elif t == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                add_points(ring)
    else:
        return None
    if not xs or not ys:
        return None
    return [min(xs), min(ys), max(xs), max(ys)]

def bbox_intersects(a: List[float], b: List[float]) -> bool:
    aw, as_, ae, an = a
    bw, bs, be, bn = b
    return not (ae < bw or be < aw or an < bs or bn < as_)

def tile_bbox(z: int, x: int, y: int) -> List[float]:
    n = 2.0 ** z
    w = x / n * 360.0 - 180.0
    e = (x + 1) / n * 360.0 - 180.0
    def lat(yi: int) -> float:
        r = math.atan(math.sinh(math.pi - 2.0 * math.pi * yi / n))
        return math.degrees(r)
    s = lat(y + 1)
    nlat = lat(y)
    return [w, s, e, nlat]
