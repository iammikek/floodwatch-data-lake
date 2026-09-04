"""Curated storm / flood-event catalogue for place-mode replay.

Timestamps are UTC evaluation instants for predict_corridor(now=...).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

STORMS: List[Dict[str, Any]] = [
    {
        "id": "eval-2014-01",
        "label": "Jan–Feb 2014 Parrett / Levels flood",
        "corridor": "a361-muchelney",
        "place_label": "Muchelney / A361 corridor",
        "as_of": "2014-02-13T12:00:00Z",
        "window": {"from": "2014-01-01", "to": "2014-02-28"},
        "expected_verdict": "at_risk_or_watch",
        "notes": (
            "Somerset Levels winter flooding; Muchelney isolation peaked mid-February. "
            "as_of is the mid-event evaluation instant (not early January onset)."
        ),
    },
    {
        "id": "eval-2020-02",
        "label": "Storm Dennis (Feb 2020)",
        "corridor": "a361-muchelney",
        "place_label": "Muchelney / A361 corridor",
        "as_of": "2020-02-16T12:00:00Z",
        "window": {"from": "2020-02-13", "to": "2020-02-20"},
        "expected_verdict": "at_risk",
        "notes": "Named storm window used for golden analogue eval.",
    },
    {
        "id": "eval-stable-summer",
        "label": "Aug 2018 stable summer",
        "corridor": "a361-muchelney",
        "place_label": "Muchelney / A361 corridor",
        "as_of": "2018-08-15T12:00:00Z",
        "window": {"from": "2018-08-01", "to": "2018-08-31"},
        "expected_verdict": "clear",
        "notes": "Low-flow control window; expected clear / no impact analogues.",
    },
]


def list_storms(corridor: Optional[str] = None) -> List[Dict[str, Any]]:
    if not corridor:
        return list(STORMS)
    return [s for s in STORMS if s.get("corridor") == corridor]


def get_storm(storm_id: str) -> Optional[Dict[str, Any]]:
    for storm in STORMS:
        if storm["id"] == storm_id:
            return storm
    return None
