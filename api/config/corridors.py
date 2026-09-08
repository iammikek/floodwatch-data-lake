"""Corridor registry for v0 historic-analogue predictions (A361 Muchelney slice)."""

from __future__ import annotations

from typing import Any, Dict, List

# measure_id values are EA notations = folders under data/raw/ea/readings/
CORRIDORS: Dict[str, Dict[str, Any]] = {
    "a361-muchelney": {
        "id": "a361-muchelney",
        "label": "A361 Muchelney corridor",
        "region": "SOM",
        # Prefer Great Bow for hindcast primary / outcome scoring.
        # 2026 Gaw Bridge live FM sits on a different scale (~1–3 m) than the
        # Thorney Mill hydrology proxy archive (~9–10 mASD) in the same folder.
        "primary": {
            "measure_id": "52230-level-stage-i-15_min-m",
            "label": "Langport Great Bow",
            "role": "levels_free_surface_proxy",
        },
        "gauges": [
            {
                "measure_id": "52230-level-stage-i-15_min-m",
                "label": "Langport Great Bow",
                "ref": "gauge-langport",
            },
            {
                "measure_id": "52245-level-stage-i-15_min-m",
                "label": "Westonzoyland PS",
                "ref": "gauge-westonzoyland",
            },
            {
                "measure_id": "52119-level-stage-i-15_min-mASD",
                "label": "Gaw Bridge · River Parrett",
                "ref": "gauge-gaw-bridge",
                "optional": True,
                "exclude_from_analogue": True,
                "note": (
                    "Kept for observables / map context only. Exclude from "
                    "analogue fingerprints until 2026 FM vs Thorney Mill proxy "
                    "scale is reconciled."
                ),
            },
            {
                "measure_id": "52153-level-stage-i-15_min-mASD",
                "label": "Midelney · River Isle (near Muchelney)",
                "ref": "gauge-midelney",
                "optional": True,
                "note": (
                    "No EA gauge named Muchelney; Midelney is closest. "
                    "Optional until a long-retention hydrology series exists "
                    "(Midelney Lock archive only from Aug 2022)."
                ),
            },
        ],
        "affected_areas": [
            {
                "id": "area-muchelney-lanes",
                "label": "Muchelney low lanes",
                "kind": "road_segment",
            },
            {
                "id": "area-a361-east-lyng",
                "label": "A361 East Lyng approach",
                "kind": "road_segment",
            },
        ],
        # Preferred stage for History bathtub free-surface / rise.
        # Great Bow (m) tracks flood rise; Gaw mASD barely moves flood vs summer.
        "volume_stage": {
            "measure_id": "52230-level-stage-i-15_min-m",
            "label": "Langport Great Bow",
            "unit": "m",
            "role": "levels_free_surface_proxy",
            "baseline_window": {"from": "2018-08-01", "to": "2018-08-31"},
            "dem_floor_percentile": 15.0,
            "notes": (
                "Peak stage minus late-summer baseline ≈ free-surface rise; "
                "applied above DEM floor inside the curated outline."
            ),
        },
    }
}


def list_corridor_ids() -> List[str]:
    return sorted(CORRIDORS.keys())


def get_corridor(corridor_id: str) -> Dict[str, Any]:
    return CORRIDORS[corridor_id]
