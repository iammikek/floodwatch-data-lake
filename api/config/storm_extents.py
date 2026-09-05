"""Curated approximate inundation footprints for Muchelney place-history storms.

These are hand-drawn corridor/floodplain polygons for History map outlines —
not surveyed inundation, LiDAR water masks, or HiPIMS output. They replace
axis-aligned impact_bbox rectangles as the spatial story for each event.

Coordinates are WGS84 [lng, lat]. Rings are closed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Muchelney / Parrett corridor reference (~A361).
# Floodplain axis runs roughly SW–NE through the Levels around Muchelney.

_EXTENT_RINGS: Dict[str, List[List[float]]] = {
    # Peak 2014 Levels isolation — wide basin around Muchelney / Westonzoyland.
    "eval-2014-01": [
        [-2.97, 51.06],
        [-2.90, 51.03],
        [-2.78, 51.04],
        [-2.70, 51.09],
        [-2.69, 51.16],
        [-2.74, 51.21],
        [-2.84, 51.22],
        [-2.94, 51.19],
        [-2.98, 51.13],
        [-2.97, 51.06],
    ],
    # Early Jan 2014 onset — tighter lobe along Parrett approaches.
    "place-2014-01-onset": [
        [-2.89, 51.10],
        [-2.85, 51.08],
        [-2.78, 51.09],
        [-2.75, 51.12],
        [-2.76, 51.15],
        [-2.81, 51.16],
        [-2.87, 51.15],
        [-2.90, 51.12],
        [-2.89, 51.10],
    ],
    # Nov 2019 wet spell — modest local pooling.
    "place-2019-11": [
        [-2.875, 51.105],
        [-2.84, 51.095],
        [-2.79, 51.10],
        [-2.77, 51.125],
        [-2.79, 51.145],
        [-2.84, 51.148],
        [-2.875, 51.135],
        [-2.88, 51.12],
        [-2.875, 51.105],
    ],
    # Storm Ciara — corridor under pressure, mid-size footprint.
    "place-2020-02-ciara": [
        [-2.93, 51.07],
        [-2.86, 51.05],
        [-2.76, 51.07],
        [-2.72, 51.12],
        [-2.74, 51.17],
        [-2.82, 51.18],
        [-2.90, 51.16],
        [-2.94, 51.12],
        [-2.93, 51.07],
    ],
    # Storm Dennis golden eval — large but distinct from 2014 peak.
    "eval-2020-02": [
        [-2.95, 51.05],
        [-2.88, 51.035],
        [-2.76, 51.05],
        [-2.705, 51.10],
        [-2.71, 51.17],
        [-2.78, 51.195],
        [-2.88, 51.19],
        [-2.95, 51.15],
        [-2.96, 51.10],
        [-2.95, 51.05],
    ],
    # Jan 2023 wet period — small monitoring window near village.
    "place-2023-01": [
        [-2.86, 51.11],
        [-2.835, 51.105],
        [-2.80, 51.11],
        [-2.785, 51.125],
        [-2.80, 51.138],
        [-2.835, 51.14],
        [-2.86, 51.132],
        [-2.865, 51.12],
        [-2.86, 51.11],
    ],
}


def _bbox_of_ring(ring: List[List[float]]) -> List[float]:
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return [min(xs), min(ys), max(xs), max(ys)]


def impact_feature(storm_id: str, *, storm_label: str = "") -> Optional[Dict[str, Any]]:
    ring = _EXTENT_RINGS.get(storm_id)
    if not ring:
        return None
    return {
        "type": "Feature",
        "properties": {
            "storm_id": storm_id,
            "label": storm_label or storm_id,
            "kind": "curated_impact_v0",
            "method": "hand_curated_floodplain_polygon",
            "notes": (
                "Approximate place-history footprint for map outline / FZ clip. "
                "Not surveyed inundation or modelled depth."
            ),
        },
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }


def impact_collection(storm_id: str, *, storm_label: str = "") -> Optional[Dict[str, Any]]:
    feature = impact_feature(storm_id, storm_label=storm_label)
    if not feature:
        return None
    return {"type": "FeatureCollection", "features": [feature]}


def impact_bbox_for(storm_id: str) -> Optional[List[float]]:
    ring = _EXTENT_RINGS.get(storm_id)
    if not ring:
        return None
    return _bbox_of_ring(ring)


def known_extent_ids() -> Tuple[str, ...]:
    return tuple(_EXTENT_RINGS.keys())
