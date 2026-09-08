"""Bathtub volume + road depth: storm outline × LiDAR DTM, gauge-linked rise."""

from __future__ import annotations

import glob
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from pyproj import Transformer
from rasterio.features import geometry_mask
from rasterio.transform import Affine
from rasterio.windows import from_bounds

from api.config.corridors import get_corridor
from api.config.road_lines import get_road_line
from api.config.storms import get_storm

try:
    import rasterio
except ImportError:  # pragma: no cover
    rasterio = None  # type: ignore

DEFAULT_DTM_ROOT = "data/curated/lidar"
DEFAULT_FILL_PERCENTILE = 70.0
DEFAULT_DEM_FLOOR_PERCENTILE = 15.0
DEFAULT_ROAD_STEP_M = 20.0
SEVERITY_FILL_PERCENTILE = {
    "high": 75.0,
    "medium": 65.0,
    "low": 55.0,
}
ROAD_DEPTH_THRESHOLDS_M = (0.3, 0.5, 1.0)


def _ring_from_storm(storm: Dict[str, Any]) -> Optional[List[List[float]]]:
    mode = str(storm.get("bounds_mode") or "").lower()
    if mode == "none":
        return None
    geom = storm.get("impact_geometry") or {}
    features = geom.get("features") or []
    if not features:
        return None
    g = features[0].get("geometry") or {}
    if g.get("type") != "Polygon":
        return None
    coords = g.get("coordinates") or []
    if not coords or not coords[0]:
        return None
    return coords[0]


def _to_bng_ring(ring_wgs84: Sequence[Sequence[float]]) -> List[List[float]]:
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
    out: List[List[float]] = []
    for lon, lat in ring_wgs84:
        e, n = transformer.transform(float(lon), float(lat))
        out.append([float(e), float(n)])
    if out and out[0] != out[-1]:
        out.append(out[0])
    return out


def _bbox_of_ring(ring: Sequence[Sequence[float]]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def _parse_tile_bbox(path: str) -> Optional[Tuple[float, float, float, float]]:
    """Parse E{w}-{e}_N{s}-{n} from filename."""
    base = os.path.basename(path)
    try:
        e_part = base.split("_E", 1)[1]
        e_box, n_box = e_part.split("_N", 1)
        n_box = n_box.replace(".tif", "")
        w, e = e_box.split("-")
        s, n = n_box.split("-")
        return float(w), float(s), float(e), float(n)
    except (IndexError, ValueError):
        return None


def _bboxes_overlap(
    a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]
) -> bool:
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def list_dtm_tiles(
    place_id: str,
    *,
    resolution: str = "2m",
    dtm_root: str = DEFAULT_DTM_ROOT,
) -> List[str]:
    pattern = os.path.join(dtm_root, place_id, f"dtm-{resolution}", "*.tif")
    return sorted(
        p
        for p in glob.glob(pattern)
        if p.endswith(".tif") and not p.endswith("provenance.json")
    )


def _fill_percentile(severity: Optional[str]) -> float:
    key = str(severity or "").lower()
    return float(SEVERITY_FILL_PERCENTILE.get(key, DEFAULT_FILL_PERCENTILE))


def _parse_iso_date(raw: str, *, end_of_day: bool = False) -> datetime:
    text = raw.strip()
    if "T" in text:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    else:
        dt = datetime.fromisoformat(text)
        if end_of_day:
            dt = dt.replace(hour=23, minute=59, second=59)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def stage_stats_for_window(
    measure_id: str,
    window_from: str,
    window_to: str,
    *,
    series_loader=None,
) -> Optional[Dict[str, float]]:
    """Peak / median stage over an inclusive calendar window (hour aggregate)."""
    from api.services.predictions import _load_measure_series

    loader = series_loader or _load_measure_series
    start = _parse_iso_date(window_from)
    end = _parse_iso_date(window_to, end_of_day=True)
    series = loader(measure_id, start, end, "hour")
    vals = [float(p.value) for p in series if p.value is not None]
    if not vals:
        return None
    return {
        "peak": float(max(vals)),
        "median": float(np.median(vals)),
        "min": float(min(vals)),
        "sampleCount": float(len(vals)),
    }


def resolve_gauge_rise_surface(
    storm: Dict[str, Any],
    elevations: np.ndarray,
    *,
    series_loader=None,
) -> Optional[Dict[str, Any]]:
    """Water surface = DEM floor + (peak stage − summer baseline)."""
    corridor_id = str(storm.get("corridor") or "")
    if not corridor_id:
        return None
    try:
        corridor = get_corridor(corridor_id)
    except KeyError:
        return None
    vs = corridor.get("volume_stage") or {}
    measure_id = vs.get("measure_id")
    win = storm.get("window") or {}
    base_win = vs.get("baseline_window") or {}
    if not measure_id or not win.get("from") or not win.get("to"):
        return None
    if not base_win.get("from") or not base_win.get("to"):
        return None

    event = stage_stats_for_window(
        measure_id, win["from"], win["to"], series_loader=series_loader
    )
    baseline = stage_stats_for_window(
        measure_id,
        base_win["from"],
        base_win["to"],
        series_loader=series_loader,
    )
    if not event or not baseline:
        return None

    vals = np.asarray(elevations, dtype=np.float64)
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return None

    floor_pct = float(vs.get("dem_floor_percentile") or DEFAULT_DEM_FLOOR_PERCENTILE)
    dem_floor = float(np.percentile(vals, floor_pct))
    rise = max(0.0, float(event["peak"]) - float(baseline["median"]))
    water = dem_floor + rise
    return {
        "waterSurfaceM": water,
        "demFloorM": dem_floor,
        "demFloorPercentile": floor_pct,
        "riseM": rise,
        "stagePeakM": float(event["peak"]),
        "stageBaselineM": float(baseline["median"]),
        "measureId": measure_id,
        "measureLabel": vs.get("label") or measure_id,
        "unit": vs.get("unit") or "m",
        "baselineWindow": dict(base_win),
        "eventWindow": {"from": win["from"], "to": win["to"]},
        "mode": "gauge_rise",
    }


def bathtub_from_elevations(
    elevations: np.ndarray,
    *,
    cell_area_m2: float,
    fill_percentile: Optional[float] = None,
    water_surface_m: Optional[float] = None,
) -> Dict[str, Any]:
    """Pure bathtub stats on DEM samples inside the polygon."""
    vals = np.asarray(elevations, dtype=np.float64)
    vals = vals[np.isfinite(vals)]
    if vals.size == 0 or cell_area_m2 <= 0:
        return {
            "sampleCount": 0,
            "wetSampleCount": 0,
            "areaM2": 0.0,
            "areaKm2": 0.0,
            "meanDepthM": None,
            "maxDepthM": None,
            "volumeM3": 0.0,
            "volumeMm3": 0.0,
            "waterSurfaceM": None,
            "demMinM": None,
            "demMaxM": None,
            "fillPercentile": fill_percentile,
        }

    if water_surface_m is not None:
        water = float(water_surface_m)
        fill_used = None
    else:
        pct = float(
            fill_percentile
            if fill_percentile is not None
            else DEFAULT_FILL_PERCENTILE
        )
        water = float(np.percentile(vals, pct))
        fill_used = pct

    depth = np.maximum(0.0, water - vals)
    wet = depth > 0
    wet_count = int(np.count_nonzero(wet))
    area = wet_count * cell_area_m2
    volume = float(np.sum(depth[wet]) * cell_area_m2) if wet_count else 0.0
    mean_depth = float(np.mean(depth[wet])) if wet_count else 0.0
    max_depth = float(np.max(depth[wet])) if wet_count else 0.0
    return {
        "sampleCount": int(vals.size),
        "wetSampleCount": wet_count,
        "areaM2": round(area, 1),
        "areaKm2": round(area / 1_000_000.0, 4),
        "meanDepthM": round(mean_depth, 3),
        "maxDepthM": round(max_depth, 3),
        "volumeM3": round(volume, 1),
        "volumeMm3": round(volume / 1_000_000.0, 4),
        "waterSurfaceM": round(water, 3),
        "demMinM": round(float(np.min(vals)), 3),
        "demMaxM": round(float(np.max(vals)), 3),
        "fillPercentile": fill_used,
    }


def densify_bng_line(
    coords_bng: Sequence[Sequence[float]], *, step_m: float = DEFAULT_ROAD_STEP_M
) -> List[Tuple[float, float, float]]:
    """Return (easting, northing, chainage_m) along a BNG polyline."""
    if len(coords_bng) < 2 or step_m <= 0:
        return []
    out: List[Tuple[float, float, float]] = []
    chain = 0.0
    out.append((float(coords_bng[0][0]), float(coords_bng[0][1]), 0.0))
    for i in range(1, len(coords_bng)):
        x0, y0 = float(coords_bng[i - 1][0]), float(coords_bng[i - 1][1])
        x1, y1 = float(coords_bng[i][0]), float(coords_bng[i][1])
        seg = math.hypot(x1 - x0, y1 - y0)
        if seg <= 0:
            continue
        n = max(1, int(math.ceil(seg / step_m)))
        for k in range(1, n + 1):
            t = k / n
            e = x0 + (x1 - x0) * t
            n_ = y0 + (y1 - y0) * t
            chain += seg / n
            out.append((e, n_, chain))
    return out


def _sample_points_on_tiles(
    points_bng: Sequence[Tuple[float, float, float]],
    tiles: Sequence[str],
) -> List[Dict[str, Any]]:
    assert rasterio is not None
    datasets = [rasterio.open(p) for p in tiles]
    try:
        samples: List[Dict[str, Any]] = []
        for e, n, chain in points_bng:
            z = None
            for ds in datasets:
                if (
                    ds.bounds.left <= e <= ds.bounds.right
                    and ds.bounds.bottom <= n <= ds.bounds.top
                ):
                    raw = list(ds.sample([(e, n)]))[0][0]
                    val = float(raw)
                    if math.isfinite(val) and -100 < val < 2000:
                        if ds.nodata is None or val != ds.nodata:
                            z = val
                    break
            if z is None:
                continue
            samples.append(
                {
                    "chainageM": round(chain, 1),
                    "easting": round(e, 1),
                    "northing": round(n, 1),
                    "terrainM": round(z, 3),
                }
            )
        return samples
    finally:
        for ds in datasets:
            ds.close()


def road_depth_summary(
    place_id: str,
    *,
    water_surface_m: float,
    tiles: Sequence[str],
    step_m: float = DEFAULT_ROAD_STEP_M,
) -> Optional[Dict[str, Any]]:
    """Sample curated road centreline vs free surface → depth strip summary."""
    if rasterio is None or not tiles:
        return None
    road = get_road_line(place_id)
    if not road:
        return None
    ring_wgs = road.get("coordinates") or []
    if len(ring_wgs) < 2:
        return None
    line_bng = _to_bng_ring(ring_wgs)
    # _to_bng_ring closes polygons; for lines drop accidental close if duplicated
    if len(line_bng) >= 2 and line_bng[0] == line_bng[-1]:
        line_bng = line_bng[:-1]
    points = densify_bng_line(line_bng, step_m=step_m)
    samples = _sample_points_on_tiles(points, tiles)
    if not samples:
        return {
            "available": False,
            "reason": "no_road_samples",
            "roadId": road.get("id"),
            "label": road.get("label"),
        }

    to_wgs = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
    depths = [max(0.0, water_surface_m - s["terrainM"]) for s in samples]
    wet = [d for d in depths if d > 0]
    length_total = float(samples[-1]["chainageM"]) if samples else 0.0
    wet_count = sum(1 for d in depths if d > 0)
    length_wet = wet_count * step_m

    thresholds: Dict[str, float] = {}
    for thr in ROAD_DEPTH_THRESHOLDS_M:
        thresholds[f"{thr:g}"] = round(
            sum(1 for d in depths if d >= thr) * step_m, 1
        )

    strip = []
    for s, d in zip(samples, depths):
        lon, lat = to_wgs.transform(float(s["easting"]), float(s["northing"]))
        strip.append(
            {
                "chainageM": s["chainageM"],
                "lng": round(float(lon), 6),
                "lat": round(float(lat), 6),
                "easting": s["easting"],
                "northing": s["northing"],
                "terrainM": s["terrainM"],
                "depthM": round(d, 3),
            }
        )

    return {
        "available": True,
        "roadId": road.get("id"),
        "label": road.get("label"),
        "kind": road.get("kind"),
        "waterSurfaceM": round(water_surface_m, 3),
        "sampleCount": len(samples),
        "stepM": step_m,
        "lengthTotalM": round(length_total, 1),
        "lengthWetM": round(length_wet, 1),
        "meanDepthM": round(float(np.mean(wet)), 3) if wet else 0.0,
        "maxDepthM": round(float(max(wet)), 3) if wet else 0.0,
        "thresholdsM": thresholds,
        "notes": road.get("notes"),
        "samples": strip,
    }


def _sample_tile(
    path: str,
    ring_bng: Sequence[Sequence[float]],
    poly_bbox: Tuple[float, float, float, float],
) -> Tuple[np.ndarray, float]:
    assert rasterio is not None
    with rasterio.open(path) as ds:
        res_x = abs(ds.res[0])
        res_y = abs(ds.res[1])
        cell_area = float(res_x * res_y)
        tile_bbox = (ds.bounds.left, ds.bounds.bottom, ds.bounds.right, ds.bounds.top)
        if not _bboxes_overlap(poly_bbox, tile_bbox):
            return np.array([], dtype=np.float64), cell_area

        window = from_bounds(
            max(poly_bbox[0], tile_bbox[0]),
            max(poly_bbox[1], tile_bbox[1]),
            min(poly_bbox[2], tile_bbox[2]),
            min(poly_bbox[3], tile_bbox[3]),
            transform=ds.transform,
        )
        window = window.round_offsets().round_lengths()
        if window.width <= 0 or window.height <= 0:
            return np.array([], dtype=np.float64), cell_area

        data = ds.read(1, window=window, boundless=False, masked=False)
        transform: Affine = ds.window_transform(window)
        geom = {"type": "Polygon", "coordinates": [list(ring_bng)]}
        inside = geometry_mask(
            [geom],
            out_shape=data.shape,
            transform=transform,
            invert=True,
            all_touched=False,
        )
        nodata = ds.nodata
        finite = np.isfinite(data)
        if nodata is not None:
            finite &= data != nodata
        finite &= (data > -100) & (data < 2000)
        selected = data[inside & finite]
        return np.asarray(selected, dtype=np.float64), cell_area


def estimate_storm_volume(
    storm_id: str,
    *,
    place_id: Optional[str] = None,
    resolution: str = "2m",
    dtm_root: str = DEFAULT_DTM_ROOT,
    fill_percentile: Optional[float] = None,
    water_surface_m: Optional[float] = None,
    series_loader=None,
    include_road: bool = True,
) -> Dict[str, Any]:
    storm = get_storm(storm_id)
    if not storm:
        raise KeyError(storm_id)

    corridor = str(storm.get("corridor") or place_id or "")
    place = place_id or corridor
    if not place:
        raise ValueError("place_id required")

    ring_wgs = _ring_from_storm(storm)
    if not ring_wgs:
        return {
            "schema": "floodwatch.storm_volume.v1",
            "stormId": storm_id,
            "placeId": place,
            "available": False,
            "reason": "no_impact_geometry",
            "prediction": None,
            "road": None,
            "method": {
                "name": "bathtub_gauge_rise_v1",
                "notes": "Storm has bounds_mode none or missing impact_geometry.",
            },
        }

    if rasterio is None:
        return {
            "schema": "floodwatch.storm_volume.v1",
            "stormId": storm_id,
            "placeId": place,
            "available": False,
            "reason": "rasterio_not_installed",
            "prediction": None,
            "road": None,
            "method": {"name": "bathtub_gauge_rise_v1"},
        }

    tiles = list_dtm_tiles(place, resolution=resolution, dtm_root=dtm_root)
    if not tiles:
        return {
            "schema": "floodwatch.storm_volume.v1",
            "stormId": storm_id,
            "placeId": place,
            "available": False,
            "reason": "no_dtm_tiles",
            "prediction": None,
            "road": None,
            "method": {
                "name": "bathtub_gauge_rise_v1",
                "notes": f"No GeoTIFFs under {dtm_root}/{place}/dtm-{resolution}/",
            },
        }

    ring_bng = _to_bng_ring(ring_wgs)
    poly_bbox = _bbox_of_ring(ring_bng)
    fill_pct = (
        float(fill_percentile)
        if fill_percentile is not None
        else _fill_percentile(storm.get("severity"))
    )

    chunks: List[np.ndarray] = []
    cell_area = None
    used_tiles: List[str] = []
    used_paths: List[str] = []
    for path in tiles:
        tile_box = _parse_tile_bbox(path)
        if tile_box and not _bboxes_overlap(poly_bbox, tile_box):
            continue
        samples, area = _sample_tile(path, ring_bng, poly_bbox)
        cell_area = area if cell_area is None else cell_area
        if samples.size:
            chunks.append(samples)
            used_tiles.append(os.path.basename(path))
            used_paths.append(path)

    if not chunks or not cell_area:
        return {
            "schema": "floodwatch.storm_volume.v1",
            "stormId": storm_id,
            "placeId": place,
            "available": False,
            "reason": "no_samples_in_polygon",
            "prediction": None,
            "road": None,
            "method": {
                "name": "bathtub_gauge_rise_v1",
                "fillPercentile": fill_pct,
                "tilesConsidered": len(tiles),
            },
        }

    elev = np.concatenate(chunks)

    gauge_meta = None
    surface = water_surface_m
    mode = "explicit_surface" if surface is not None else None
    if surface is None and fill_percentile is None:
        gauge_meta = resolve_gauge_rise_surface(
            storm, elev, series_loader=series_loader
        )
        if gauge_meta:
            surface = float(gauge_meta["waterSurfaceM"])
            mode = "gauge_rise"

    if surface is None:
        mode = "dem_percentile_fallback"
        stats = bathtub_from_elevations(
            elev, cell_area_m2=cell_area, fill_percentile=fill_pct
        )
    else:
        stats = bathtub_from_elevations(
            elev, cell_area_m2=cell_area, water_surface_m=surface
        )

    road = None
    if include_road and stats["waterSurfaceM"] is not None:
        road = road_depth_summary(
            place, water_surface_m=float(stats["waterSurfaceM"]), tiles=tiles
        )

    confidence = 0.45 if mode == "gauge_rise" else 0.35
    confidence_label = "Low"
    method_name = (
        "bathtub_gauge_rise_v1"
        if mode == "gauge_rise"
        else "bathtub_fill_percentile_v0"
    )
    notes = (
        "Approximate bathtub: free surface = DEM floor (inside curated outline) "
        "+ gauge peak rise above late-summer baseline. Depth = max(0, surface − "
        "terrain). Not hydrodynamic; outline is not surveyed inundation. "
        "Road strip uses a hand-curated A361 centreline within the LiDAR core."
        if mode == "gauge_rise"
        else (
            "Approximate bathtub: water surface = DEM percentile inside curated "
            "impact polygon (gauge rise unavailable). Not a hydrodynamic model."
        )
    )

    method: Dict[str, Any] = {
        "name": method_name,
        "mode": mode,
        "inputs": [
            "impact_geometry",
            f"lidar_composite_dtm_{resolution}",
        ],
        "notes": notes,
        "attribution": (
            "© Environment Agency copyright and/or database right 2022. "
            "LIDAR Composite DTM."
        ),
    }
    if mode == "dem_percentile_fallback" or mode == "explicit_surface":
        if stats.get("fillPercentile") is not None:
            method["fillPercentile"] = stats["fillPercentile"]
    if gauge_meta:
        method["inputs"].append(str(gauge_meta["measureId"]))
        method["gauge"] = {
            "measureId": gauge_meta["measureId"],
            "label": gauge_meta["measureLabel"],
            "stagePeakM": round(gauge_meta["stagePeakM"], 3),
            "stageBaselineM": round(gauge_meta["stageBaselineM"], 3),
            "riseM": round(gauge_meta["riseM"], 3),
            "demFloorM": round(gauge_meta["demFloorM"], 3),
            "demFloorPercentile": gauge_meta["demFloorPercentile"],
            "baselineWindow": gauge_meta["baselineWindow"],
            "eventWindow": gauge_meta["eventWindow"],
        }

    return {
        "schema": "floodwatch.storm_volume.v1",
        "stormId": storm_id,
        "stormLabel": storm.get("label"),
        "placeId": place,
        "available": True,
        "reason": None,
        "prediction": {
            "areaM2": stats["areaM2"],
            "areaKm2": stats["areaKm2"],
            "meanDepthM": stats["meanDepthM"],
            "maxDepthM": stats["maxDepthM"],
            "volumeM3": stats["volumeM3"],
            "volumeMm3": stats["volumeMm3"],
            "waterSurfaceM": stats["waterSurfaceM"],
            "confidence": confidence,
            "confidenceLabel": confidence_label,
        },
        "road": road,
        "observables": {
            "demMinM": stats["demMinM"],
            "demMaxM": stats["demMaxM"],
            "sampleCount": stats["sampleCount"],
            "wetSampleCount": stats.get("wetSampleCount"),
            "cellAreaM2": cell_area,
            "tilesUsed": used_tiles,
            "resolution": resolution,
            "surfaceMode": mode,
            "gauge": method.get("gauge"),
        },
        "method": method,
    }
