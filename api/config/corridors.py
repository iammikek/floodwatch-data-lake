"""Corridor registry for v0 historic-analogue predictions (A361 Muchelney slice)."""

from __future__ import annotations

from typing import Any, Dict, List

# measure_id values are EA notations = folders under data/raw/ea/readings/
CORRIDORS: Dict[str, Dict[str, Any]] = {
    "a361-muchelney": {
        "id": "a361-muchelney",
        "label": "A361 Muchelney corridor",
        "region": "SOM",
        # Longest local history on Parrett approach — used for percentile / slope.
        "primary": {
            "measure_id": "52119-level-stage-i-15_min-mASD",
            "label": "Gaw Bridge · River Parrett",
            "role": "parrett_upstream",
        },
        "gauges": [
            {
                "measure_id": "52119-level-stage-i-15_min-mASD",
                "label": "Gaw Bridge · River Parrett",
                "ref": "gauge-gaw-bridge",
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
            {
                "measure_id": "52245-level-stage-i-15_min-m",
                "label": "Westonzoyland PS",
                "ref": "gauge-westonzoyland",
            },
            {
                "measure_id": "52230-level-stage-i-15_min-m",
                "label": "Langport Great Bow",
                "ref": "gauge-langport",
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
    }
}


def list_corridor_ids() -> List[str]:
    return sorted(CORRIDORS.keys())


def get_corridor(corridor_id: str) -> Dict[str, Any]:
    return CORRIDORS[corridor_id]
