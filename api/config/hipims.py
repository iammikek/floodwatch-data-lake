"""HiPIMS / depth-over-road preparation config (solver not wired yet).

This documents the Muchelney corridor pilot domain that finer DEM ingest
feeds. Full HiPIMS-CUDA job orchestration remains Phase 2
(`docs/architecture-plan.md`, `docs/hipims-prep.md`).
"""

from __future__ import annotations

from typing import Any, Dict, List

HIPIMS_PILOTS: Dict[str, Dict[str, Any]] = {
    "a361-muchelney": {
        "id": "a361-muchelney",
        "label": "A361 Muchelney corridor HiPIMS pilot",
        "status": "dem_prep",
        "placeId": "a361-muchelney",
        "dem": {
            "preferredResolution": "1m",
            "fallbackResolution": "2m",
            "extent": "hotspot",
            "product": "LIDAR Composite DTM",
            "crs": "EPSG:27700",
            "ingestHint": (
                "python -m ingestion.cli ingest-lidar-dtm "
                "--place a361-muchelney --resolution 1m --extent hotspot --resume"
            ),
        },
        "domain": {
            "bboxKey": "bng_hotspot",
            "targetGridResM": 5.0,
            "notes": (
                "Start hydrodynamic runs at ~5 m on the A361 hotspot; "
                "evaluate 1–2 m for road depth hotspots once the DEM is in."
            ),
        },
        "road": {
            "centrelineConfig": "api/config/road_lines.py",
            "depthThresholdsM": [0.3, 0.5, 1.0],
        },
        "forcing": {
            "stagePrimary": "52230-level-stage-i-15_min-m",
            "stagePrimaryLabel": "Langport Great Bow",
            "rainfall": "deferred",
        },
        "solver": {
            "engine": "hipims-cuda",
            "wired": False,
            "license": "GPLv3 (isolate as optional service)",
        },
    }
}


def list_hipims_pilot_ids() -> List[str]:
    return sorted(HIPIMS_PILOTS.keys())


def get_hipims_pilot(place_id: str) -> Dict[str, Any]:
    return HIPIMS_PILOTS[place_id]
