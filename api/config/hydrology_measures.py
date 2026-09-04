"""Map flood-monitoring corridor measures to EA Hydrology archive measure IDs.

Hydrology station GUIDs differ from flood-monitoring notations. Only stations
with a confirmed hydrology 15-minute level series are listed here. Gauges
without a mapping cannot be archive-backfilled via hydrology until resolved.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Keys = flood-monitoring measure_id (folder under data/raw/ea/readings/).
HYDROLOGY_MEASURE_MAP: Dict[str, Dict[str, Any]] = {
    "52245-level-stage-i-15_min-m": {
        "hydrology_measure_id": (
            "0a6e9d80-6de0-4f88-a1ae-8da70cebf95f-level-i-900-m-qualified"
        ),
        "hydrology_station_id": "0a6e9d80-6de0-4f88-a1ae-8da70cebf95f",
        "label": "Westonzoyland",
        "station_reference": "52245",
        "notes": "Confirmed hydrology archive series (15-min level).",
    },
}


def hydrology_mapping(measure_id: str) -> Optional[Dict[str, Any]]:
    return HYDROLOGY_MEASURE_MAP.get(measure_id)


def mapped_corridor_measures(measure_ids: List[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for mid in measure_ids:
        mapping = hydrology_mapping(mid)
        if mapping:
            out.append({"flood_monitoring_measure_id": mid, **mapping})
    return out
