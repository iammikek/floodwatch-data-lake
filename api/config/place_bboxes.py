"""Place bounding boxes for LiDAR / volume analytics (History accuracy ladder).

WGS84 boxes are the product truth for maps; BNG (EPSG:27700) boxes are for
DEFRA LiDAR Composite WCS subsets. BNG values are curated for the Muchelney
corridor (verified against WCS coverage around E 337000 / N 136000).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

# Union of curated storm impact envelopes + ~1 km pad (WGS84).
_A361_WGS84 = {
    "west": -2.99,
    "south": 51.02,
    "east": -2.67,
    "north": 51.23,
}

# Core analytics window (~10 km) centred on Muchelney / A361.
_A361_CORE_BNG = {
    "west": 332000.0,
    "south": 131000.0,
    "east": 342000.0,
    "north": 141000.0,
}

# Full place window covering golden-storm footprints (~22 × 24 km).
_A361_FULL_BNG = {
    "west": 325000.0,
    "south": 126000.0,
    "east": 347000.0,
    "north": 150000.0,
}

PLACE_BBOXES: Dict[str, Dict[str, Any]] = {
    "a361-muchelney": {
        "id": "a361-muchelney",
        "label": "A361 Muchelney / Parrett Levels place",
        "crs_wgs84": "EPSG:4326",
        "crs_bng": "EPSG:27700",
        "wgs84": dict(_A361_WGS84),
        "bng_core": dict(_A361_CORE_BNG),
        "bng_full": dict(_A361_FULL_BNG),
        "notes": (
            "bng_core is the default LiDAR ingest window for volume v0; "
            "bng_full covers curated storm impact envelopes."
        ),
    }
}


def list_place_ids() -> List[str]:
    return sorted(PLACE_BBOXES.keys())


def get_place_bbox(place_id: str) -> Dict[str, Any]:
    return PLACE_BBOXES[place_id]


def bng_bbox(
    place_id: str, *, extent: str = "core"
) -> Tuple[float, float, float, float]:
    place = get_place_bbox(place_id)
    key = "bng_full" if extent == "full" else "bng_core"
    box = place[key]
    return (
        float(box["west"]),
        float(box["south"]),
        float(box["east"]),
        float(box["north"]),
    )


def wgs84_bbox(place_id: str) -> Tuple[float, float, float, float]:
    box = get_place_bbox(place_id)["wgs84"]
    return (
        float(box["west"]),
        float(box["south"]),
        float(box["east"]),
        float(box["north"]),
    )
