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

_GEOJSON_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}


def read_geojson_any(path: str) -> Dict[str, Any]:
    if os.path.exists(path):
        mtime = os.path.getmtime(path)
        cached = _GEOJSON_CACHE.get(path)
        if cached and cached[0] == mtime:
            return cached[1]
        with open(path, "r") as f:
            doc = json.load(f)
        _GEOJSON_CACHE[path] = (mtime, doc)
        return doc
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


def _decimate_ring(points: List[List[float]], max_points: int) -> List[List[float]]:
    n = len(points)
    if n <= max_points:
        return points
    step = max(1, n // max_points)
    out = [points[i] for i in range(0, n, step)]
    if out[-1] != points[-1]:
        out.append(points[-1])
    return out


def clip_ring_to_bbox(
    ring: List[List[float]],
    bbox: List[float],
    *,
    pad: float = 0.02,
    max_points: int = 64,
) -> Optional[List[List[float]]]:
    """Keep ring vertices near the viewport and hard-decimate for map payloads."""
    if not ring or len(ring) < 2:
        return None
    w, s, e, n = bbox
    ww, ss, ee, nn = w - pad, s - pad, e + pad, n + pad
    kept = [[float(x), float(y)] for x, y in ring if ww <= float(x) <= ee and ss <= float(y) <= nn]
    if len(kept) < 4:
        return None
    closed = kept[0] == kept[-1]
    core = kept[:-1] if closed else kept
    core = _decimate_ring(core, max_points)
    if len(core) < 3:
        return None
    if core[0] != core[-1]:
        core = core + [core[0]]
    return core


def clip_geometry_to_bbox(
    geom: Dict[str, Any],
    bbox: List[float],
    *,
    max_points: int = 64,
) -> Optional[Dict[str, Any]]:
    t = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return None
    if t == "Polygon":
        rings: List[List[List[float]]] = []
        for ring in coords:
            clipped = clip_ring_to_bbox(ring, bbox, max_points=max_points)
            if clipped:
                rings.append(clipped)
        return {"type": "Polygon", "coordinates": rings} if rings else None
    if t == "MultiPolygon":
        polys: List[List[List[List[float]]]] = []
        for poly in coords:
            rings = []
            for ring in poly:
                clipped = clip_ring_to_bbox(ring, bbox, max_points=max_points)
                if clipped:
                    rings.append(clipped)
            if rings:
                polys.append(rings)
        return {"type": "MultiPolygon", "coordinates": polys} if polys else None
    return None


def prepare_inline_features(
    feats: List[Dict[str, Any]],
    bbox: List[float],
    *,
    max_features: int = 1200,
    max_ring_points: int = 64,
) -> List[Dict[str, Any]]:
    """Filter, clip, and cap features for browser-friendly flood-bound overlays."""
    scored: List[tuple[int, float, Dict[str, Any]]] = []
    for feat in feats:
        geom = feat.get("geometry") or {}
        gb = geom_bbox(geom)
        if not gb or not bbox_intersects(gb, bbox):
            continue
        clipped = clip_geometry_to_bbox(geom, bbox, max_points=max_ring_points)
        if not clipped:
            continue
        props = feat.get("properties") or {}
        zone = str(props.get("flood_zone") or "")
        zone_rank = 0 if zone == "FZ3" else (1 if zone == "FZ2" else 2)
        area = max(0.0, (gb[2] - gb[0]) * (gb[3] - gb[1]))
        scored.append(
            (
                zone_rank,
                -area,
                {
                    "type": "Feature",
                    "properties": {
                        "id": props.get("id"),
                        "flood_zone": props.get("flood_zone"),
                        "flood_source": props.get("flood_source"),
                        "origin": props.get("origin"),
                    },
                    "geometry": clipped,
                },
            )
        )
    scored.sort(key=lambda row: (row[0], row[1]))
    return [row[2] for row in scored[:max_features]]


def resolve_curated_polygons_path(
    dataset: str,
    region: str,
    scenario: Optional[str],
    format_: str,
) -> tuple[str, str]:
    """Prefer requested format; fall back to normalized when simplified is empty/missing.

    Uses file presence/size only — does not parse multi‑hundred‑MB GeoJSON.
    """
    primary = curated_polygons_path(dataset, region, scenario, format_)
    if os.path.exists(primary) and os.path.getsize(primary) > 64:
        return primary, format_
    if format_ == "simplified":
        fallback = curated_polygons_path(dataset, region, scenario, "normalized")
        if os.path.exists(fallback) and os.path.getsize(fallback) > 64:
            return fallback, "normalized"
        return fallback, "normalized"
    return primary, format_


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
