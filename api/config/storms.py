"""Curated storm / flood-event catalogue for place-mode replay + history.

Timestamps are UTC evaluation instants for predict_corridor(now=...).
Entries with as_of are replayable; place history surfaces the full set.

bounds_mode:
  - "impact" — curated floodplain polygon (impact_geometry) + bbox envelope
  - "none" — no flood-bound overlay (e.g. summer control)

impact_geometry is a GeoJSON FeatureCollection (hand-curated v0).
impact_bbox remains the envelope for clients that only clip by bbox.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from api.config.storm_extents import impact_bbox_for, impact_collection

_STORMS_RAW: List[Dict[str, Any]] = [
    {
        "id": "eval-2014-01",
        "label": "Jan–Feb 2014 Parrett / Levels flood",
        "corridor": "a361-muchelney",
        "place_label": "Muchelney / A361 corridor",
        "as_of": "2014-02-13T12:00:00Z",
        "window": {"from": "2014-01-01", "to": "2014-02-28"},
        "expected_verdict": "at_risk_or_watch",
        "kind": "major_flood",
        "severity": "high",
        "impact_summary": "Muchelney cut off for weeks; A361 approaches flooded.",
        "bounds_mode": "impact",
        "notes": (
            "Somerset Levels winter flooding; Muchelney isolation peaked mid-February. "
            "as_of is the mid-event evaluation instant (not early January onset)."
        ),
    },
    {
        "id": "place-2014-01-onset",
        "label": "Early Jan 2014 Levels rise",
        "corridor": "a361-muchelney",
        "place_label": "Muchelney / A361 corridor",
        "as_of": "2014-01-07T12:00:00Z",
        "window": {"from": "2013-12-20", "to": "2014-01-15"},
        "expected_verdict": "watch_or_at_risk",
        "kind": "major_flood",
        "severity": "high",
        "impact_summary": "Parrett catchment climbing; lanes starting to flood.",
        "bounds_mode": "impact",
        "notes": "Onset of the 2013–14 Levels emergency, before peak isolation.",
    },
    {
        "id": "place-2019-11",
        "label": "Nov 2019 wet spell",
        "corridor": "a361-muchelney",
        "place_label": "Muchelney / A361 corridor",
        "as_of": "2019-11-14T12:00:00Z",
        "window": {"from": "2019-11-01", "to": "2019-11-30"},
        "expected_verdict": "watch_or_clear",
        "kind": "wet_spell",
        "severity": "medium",
        "impact_summary": "Saturated Levels; local road flooding risk elevated.",
        "bounds_mode": "impact",
        "notes": "Pre-winter wet period used as a secondary place-history marker.",
    },
    {
        "id": "place-2020-02-ciara",
        "label": "Storm Ciara (Feb 2020)",
        "corridor": "a361-muchelney",
        "place_label": "Muchelney / A361 corridor",
        "as_of": "2020-02-09T12:00:00Z",
        "window": {"from": "2020-02-07", "to": "2020-02-11"},
        "expected_verdict": "watch_or_at_risk",
        "kind": "named_storm",
        "severity": "high",
        "impact_summary": "Named storm; Parrett corridor under pressure before Dennis.",
        "bounds_mode": "impact",
        "notes": "Storm Ciara weekend; Dennis followed a week later.",
    },
    {
        "id": "eval-2020-02",
        "label": "Storm Dennis (Feb 2020)",
        "corridor": "a361-muchelney",
        "place_label": "Muchelney / A361 corridor",
        "as_of": "2020-02-16T12:00:00Z",
        "window": {"from": "2020-02-13", "to": "2020-02-20"},
        "expected_verdict": "at_risk",
        "kind": "named_storm",
        "severity": "high",
        "impact_summary": "Named-storm peak; corridor hindcast golden eval.",
        "bounds_mode": "impact",
        "notes": "Named storm window used for golden analogue eval.",
    },
    {
        "id": "place-2023-01",
        "label": "Jan 2023 wet period",
        "corridor": "a361-muchelney",
        "place_label": "Muchelney / A361 corridor",
        "as_of": "2023-01-16T12:00:00Z",
        "window": {"from": "2023-01-01", "to": "2023-01-31"},
        "expected_verdict": "watch_or_clear",
        "kind": "wet_spell",
        "severity": "medium",
        "impact_summary": "Winter wet spell on the Levels; monitoring window.",
        "bounds_mode": "impact",
        "notes": "More recent archive check for place history coverage.",
    },
    {
        "id": "eval-stable-summer",
        "label": "Aug 2018 stable summer",
        "corridor": "a361-muchelney",
        "place_label": "Muchelney / A361 corridor",
        "as_of": "2018-08-15T12:00:00Z",
        "window": {"from": "2018-08-01", "to": "2018-08-31"},
        "expected_verdict": "clear",
        "kind": "control",
        "severity": "low",
        "impact_summary": "Low-flow control — no predicted place impact.",
        "bounds_mode": "none",
        "notes": "Low-flow control window; expected clear / no impact analogues.",
    },
]


def _enrich_storm(raw: Dict[str, Any]) -> Dict[str, Any]:
    storm = dict(raw)
    mode = str(storm.get("bounds_mode") or "").lower()
    if mode == "none":
        storm["impact_bbox"] = None
        storm["impact_geometry"] = None
        return storm

    storm_id = str(storm["id"])
    geom = impact_collection(storm_id, storm_label=str(storm.get("label") or ""))
    bbox = impact_bbox_for(storm_id)
    storm["impact_geometry"] = geom
    storm["impact_bbox"] = bbox
    return storm


STORMS: List[Dict[str, Any]] = [_enrich_storm(row) for row in _STORMS_RAW]


def list_storms(corridor: Optional[str] = None) -> List[Dict[str, Any]]:
    rows = list(STORMS) if not corridor else [s for s in STORMS if s.get("corridor") == corridor]
    return sorted(rows, key=lambda s: s.get("as_of") or "", reverse=True)


def get_storm(storm_id: str) -> Optional[Dict[str, Any]]:
    for storm in STORMS:
        if storm["id"] == storm_id:
            return storm
    return None
