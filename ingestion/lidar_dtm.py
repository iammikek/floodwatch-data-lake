"""DEFRA LiDAR Composite DTM ingest via WCS GetCoverage (EPSG:27700)."""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx

from api.config.place_bboxes import bng_bbox, get_place_bbox, list_place_ids

WCS_ENDPOINTS = {
    "1m": {
        "url": (
            "https://environment.data.gov.uk/spatialdata/"
            "lidar-composite-digital-terrain-model-dtm-1m/wcs"
        ),
        "coverage_id": (
            "13787b9a-26a4-4775-8523-806d13af58fc__Lidar_Composite_Elevation_DTM_1m"
        ),
        "resolution_m": 1,
        "dataset_id": "13787b9a-26a4-4775-8523-806d13af58fc",
        "product": "LIDAR Composite DTM 1m (2022)",
    },
    "2m": {
        "url": (
            "https://environment.data.gov.uk/spatialdata/"
            "lidar-composite-digital-terrain-model-dtm-2m/wcs"
        ),
        "coverage_id": (
            "09ea3b37-df3a-4e8b-ac69-fb0842227b04__Lidar_Composite_Elevation_DTM_2m"
        ),
        "resolution_m": 2,
        "dataset_id": "09ea3b37-df3a-4e8b-ac69-fb0842227b04",
        "product": "LIDAR Composite DTM 2m (2022)",
    },
}

DEFAULT_OUT_ROOT = "data/curated/lidar"


def iter_bng_tiles(
    west: float,
    south: float,
    east: float,
    north: float,
    *,
    tile_m: float = 5000.0,
) -> List[Tuple[float, float, float, float]]:
    """Axis-aligned BNG tiles covering [west,south,east,north]."""
    if east <= west or north <= south:
        raise ValueError("bbox must have positive width and height")
    if tile_m <= 0:
        raise ValueError("tile_m must be positive")

    x0 = math.floor(west / tile_m) * tile_m
    y0 = math.floor(south / tile_m) * tile_m
    tiles: List[Tuple[float, float, float, float]] = []
    y = y0
    while y < north:
        x = x0
        while x < east:
            tw, ts = x, y
            te, tn = min(x + tile_m, east), min(y + tile_m, north)
            # Skip empty slivers
            if te > tw and tn > ts:
                tiles.append((tw, ts, te, tn))
            x += tile_m
        y += tile_m
    return tiles


def wcs_get_coverage_url(
    *,
    resolution: str,
    west: float,
    south: float,
    east: float,
    north: float,
) -> str:
    meta = WCS_ENDPOINTS[resolution]
    params = {
        "service": "WCS",
        "version": "2.0.1",
        "request": "GetCoverage",
        "CoverageId": meta["coverage_id"],
        "format": "image/tiff",
        "subset": [f"E({west},{east})", f"N({south},{north})"],
    }
    # urlencode with doseq for repeated subset keys
    query = urlencode(params, doseq=True)
    return f"{meta['url']}?{query}"


def _tile_name(west: float, south: float, east: float, north: float, resolution: str) -> str:
    return (
        f"dtm{resolution}_"
        f"E{int(west)}-{int(east)}_N{int(south)}-{int(north)}.tif"
    )


def ingest_place_dtm(
    place_id: str,
    *,
    resolution: str = "2m",
    extent: str = "core",
    tile_m: float = 5000.0,
    out_root: str = DEFAULT_OUT_ROOT,
    resume: bool = True,
    timeout_s: float = 120.0,
    client: Optional[httpx.Client] = None,
) -> Dict[str, Any]:
    """Download LiDAR Composite DTM tiles for a place bbox; write provenance."""
    if place_id not in list_place_ids():
        raise KeyError(place_id)
    if resolution not in WCS_ENDPOINTS:
        raise KeyError(resolution)

    place = get_place_bbox(place_id)
    west, south, east, north = bng_bbox(place_id, extent=extent)
    tiles = iter_bng_tiles(west, south, east, north, tile_m=tile_m)
    meta = WCS_ENDPOINTS[resolution]

    place_dir = os.path.join(out_root, place_id, f"dtm-{resolution}")
    os.makedirs(place_dir, exist_ok=True)

    owns_client = client is None
    http = client or httpx.Client(timeout=timeout_s, follow_redirects=True)
    written: List[Dict[str, Any]] = []
    skipped: List[str] = []
    errors: List[Dict[str, str]] = []

    try:
        for tw, ts, te, tn in tiles:
            name = _tile_name(tw, ts, te, tn, resolution)
            path = os.path.join(place_dir, name)
            if resume and os.path.exists(path) and os.path.getsize(path) > 1000:
                skipped.append(name)
                written.append(
                    {
                        "path": path,
                        "bbox_bng": [tw, ts, te, tn],
                        "bytes": os.path.getsize(path),
                        "status": "skipped_existing",
                    }
                )
                continue

            url = wcs_get_coverage_url(
                resolution=resolution, west=tw, south=ts, east=te, north=tn
            )
            try:
                resp = http.get(url)
                is_tiff = resp.content[:4] in (b"II*\x00", b"MM\x00*")
                if resp.status_code != 200 or not is_tiff:
                    raise RuntimeError(
                        f"unexpected response status={resp.status_code} "
                        f"ctype={resp.headers.get('content-type')} "
                        f"bytes={len(resp.content)}"
                    )
                with open(path, "wb") as f:
                    f.write(resp.content)
                written.append(
                    {
                        "path": path,
                        "bbox_bng": [tw, ts, te, tn],
                        "bytes": len(resp.content),
                        "status": "downloaded",
                        "url": url,
                    }
                )
            except Exception as exc:  # pragma: no cover - network path
                errors.append({"tile": name, "error": str(exc), "url": url})
    finally:
        if owns_client:
            http.close()

    provenance = {
        "schema": "floodwatch.lidar_dtm_ingest.v0",
        "as_of": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "place_id": place_id,
        "place_label": place["label"],
        "extent": extent,
        "bbox_bng": [west, south, east, north],
        "bbox_wgs84": [
            place["wgs84"]["west"],
            place["wgs84"]["south"],
            place["wgs84"]["east"],
            place["wgs84"]["north"],
        ],
        "product": meta["product"],
        "dataset_id": meta["dataset_id"],
        "coverage_id": meta["coverage_id"],
        "resolution_m": meta["resolution_m"],
        "crs": "EPSG:27700",
        "tile_m": tile_m,
        "wcs_url": meta["url"],
        "attribution": (
            "© Environment Agency copyright and/or database right 2022. "
            "LIDAR Composite DTM."
        ),
        "tiles": written,
        "skipped": skipped,
        "errors": errors,
        "notes": (
            "Tiles fetched via WCS GetCoverage for History volume v0. "
            "Not a mosaicked single GeoTIFF yet; consumers should read tiles "
            "or mosaic offline with GDAL/rasterio."
        ),
    }
    prov_path = os.path.join(place_dir, "provenance.json")
    with open(prov_path, "w", encoding="utf-8") as f:
        json.dump(provenance, f, indent=2)
        f.write("\n")
    provenance["provenance_path"] = prov_path
    return provenance
