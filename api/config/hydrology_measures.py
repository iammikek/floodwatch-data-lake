"""Map flood-monitoring corridor measures to EA Hydrology archive measure IDs.

Hydrology station GUIDs differ from flood-monitoring notations. Exact matches
are preferred; where the FM gauge is absent from the hydrology catalogue we
may map a nearby proxy station (proxy=True) so storm hindcasts have archive
depth. Proxy series are written into the FM measure folder with provenance
ea_hydrology_archive — treat as approximate for that corridor role.
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
        "proxy": False,
        "notes": "Exact hydrology archive series (15-min level).",
    },
    # Gaw Bridge (52119 / wiski 520320_FW) is not in the hydrology catalogue.
    "52119-level-stage-i-15_min-mASD": {
        "hydrology_measure_id": (
            "9a1824e6-cf47-49b0-a3d6-3b534609adfc-level-i-900-m-qualified"
        ),
        "hydrology_station_id": "9a1824e6-cf47-49b0-a3d6-3b534609adfc",
        "label": "Thorney Mill (proxy for Gaw Bridge)",
        "station_reference": None,
        "proxy": True,
        "proxy_for": "Gaw Bridge",
        "approx_distance_km": 3.1,
        "notes": (
            "No hydrology GUID for Gaw Bridge. Thorney Mill is the nearest "
            "archive series with 2014/2020 coverage (~3.1 km). Approximate "
            "primary-gauge trajectory only."
        ),
    },
    # Langport Great Bow (52230) is not in the hydrology catalogue.
    "52230-level-stage-i-15_min-m": {
        "hydrology_measure_id": (
            "ae8900e2-4a59-4e6b-99d1-bff15912f8bc-level-i-900-m-qualified"
        ),
        "hydrology_station_id": "ae8900e2-4a59-4e6b-99d1-bff15912f8bc",
        "label": "Monks Leaze (proxy for Langport Great Bow)",
        "station_reference": "52233",
        "proxy": True,
        "proxy_for": "Langport Great Bow",
        "approx_distance_km": 1.0,
        "notes": (
            "No hydrology GUID for Langport Great Bow. Monks Leaze is ~1 km "
            "upstream/downstream on the Levels with archive from 2007."
        ),
    },
    # Midelney (52153): Langport Midelney Lock is ~90 m away but archive only
    # starts Aug 2022 — omitted until a longer series is found.
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
