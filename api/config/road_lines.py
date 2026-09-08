"""Curated approximate road centrelines for History LiDAR depth strips.

Not OS MasterMap / ITN — hand-drawn corridors that stay inside the LiDAR
core window so DTM sampling succeeds. Used only for approximate road-depth
summaries under History.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# A361 approach through low Levels ground near Othery / East Lyng
# (within a361-muchelney bng_core DTM tiles). WGS84 [lng, lat].
_ROAD_LINES: Dict[str, Dict[str, Any]] = {
    "a361-muchelney": {
        "id": "a361-othery-approach",
        "label": "A361 East Lyng / Othery approach (approx)",
        "kind": "road_centreline_v0",
        "placeId": "a361-muchelney",
        "coordinates": [
            [-2.930, 51.070],
            [-2.920, 51.073],
            [-2.910, 51.076],
            [-2.910, 51.080],
            [-2.895, 51.082],
            [-2.880, 51.080],
            [-2.870, 51.078],
            [-2.860, 51.080],
            [-2.850, 51.082],
        ],
        "notes": (
            "Hand-curated approximate centreline for depth sampling inside the "
            "LiDAR core ingest. Not surveyed carriageway geometry."
        ),
    }
}


def get_road_line(place_id: str) -> Optional[Dict[str, Any]]:
    return _ROAD_LINES.get(place_id)


def list_road_place_ids() -> List[str]:
    return sorted(_ROAD_LINES.keys())
