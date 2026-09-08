"""Curated EA Historic Flood Warnings (AfA435) evidence for place-history storms.

Source: Environment Agency Historic Flood Warnings (AfA435), Open Government Licence.
Rows are *issue* dates from the national ODS export — not full in-force intervals.

Hand-filtered for the A361 Muchelney / Parrett–Tone Levels corridor.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Severity mapping aligned with live EA flood-monitoring codes.
_SEVERITY_LEVEL = {
    "severe flood warning": 1,
    "flood warning": 2,
    "update flood warning": 2,
    "flood alert": 3,
    "update flood alert": 3,
    "flood watch": 3,
}


def _level(type_label: str) -> int:
    return int(_SEVERITY_LEVEL.get(str(type_label or "").strip().lower(), 4))


def _item(
    *,
    flood_area_id: str,
    title: str,
    type_label: str,
    issued_on: str,
    area: str,
) -> Dict[str, Any]:
    return {
        "floodAreaID": flood_area_id,
        "title": title,
        "severity": type_label.title() if type_label else "Unknown",
        "severityLevel": _level(type_label),
        "issued_at": f"{issued_on}T12:00:00Z",
        "area": area,
        "source": "ea:afa435-historic-flood-warnings",
    }


# Extracted from AfA435 ODS (202607 export) for corridor codes / Muchelney names.
_STORM_WARNINGS: Dict[str, Dict[str, Any]] = {
    "place-2026-01-chandra-levels": {
        "schema": "floodwatch.storm_warning_evidence.v0",
        "stormId": "place-2026-01-chandra-levels",
        "source": "ea:afa435-historic-flood-warnings",
        "dataset": "Historic Flood Warnings (AfA435)",
        "datasetExport": "202607",
        "attribution": (
            "© Environment Agency copyright and/or database right 2026. "
            "Historic Flood Warnings."
        ),
        "method": "hand_filtered_afa435_issue_rows",
        "notes": (
            "AfA435 records warning issue dates, not the full period a warning stayed "
            "in force. Corridor filter: Muchelney / Parrett–Tone Levels flood areas. "
            "A361 East Lyng to Burrowbridge (112FWFEAS10A) has no 2026 issue row in "
            "AfA435 (last issue 2024-01-05) even though EA briefing 27 Feb 2026 reported "
            "removing that Flood Warning — treated as an archive gap, not absence of impact."
        ),
        "items": [
            _item(
                flood_area_id="112WAFYPM",
                title="River Yeo and River Parrett Moors around Muchelney and Thorney",
                type_label="Flood alert",
                issued_on="2026-01-17",
                area="Wessex",
            ),
            _item(
                flood_area_id="112WAFYPL",
                title="River Yeo and Parrett, The Levels",
                type_label="Flood alert",
                issued_on="2026-01-20",
                area="Wessex",
            ),
            _item(
                flood_area_id="112WAFTPM",
                title="Lower Tone and Parrett Moors",
                type_label="Flood alert",
                issued_on="2026-01-20",
                area="Wessex",
            ),
            _item(
                flood_area_id="112WAFYPB",
                title="River Yeo and Parrett, Bridgwater to the Coast",
                type_label="Flood alert",
                issued_on="2026-01-20",
                area="Wessex",
            ),
            _item(
                flood_area_id="112WAFYPY",
                title="River Yeo and Parrett, Yeovilton to Huish Episcopi",
                type_label="Flood alert",
                issued_on="2026-01-20",
                area="Wessex",
            ),
            _item(
                flood_area_id="112FWFMTM10A",
                title=(
                    "River Yeo and River Parrett Moors, low lying properties around Muchelney"
                ),
                type_label="Flood warning",
                issued_on="2026-01-27",
                area="Wessex",
            ),
            _item(
                flood_area_id="112FWFPAR20A",
                title="River Parrett (upper) at Thorney and Kingsbury Episcopi",
                type_label="Flood warning",
                issued_on="2026-01-27",
                area="Wessex",
            ),
        ],
    }
}


def warning_evidence_for(storm_id: str) -> Optional[Dict[str, Any]]:
    raw = _STORM_WARNINGS.get(storm_id)
    if not raw:
        return None
    doc = dict(raw)
    doc["items"] = list(raw.get("items") or [])
    doc["counts"] = {
        "total": len(doc["items"]),
        "floodWarning": sum(
            1 for it in doc["items"] if int(it.get("severityLevel") or 9) == 2
        ),
        "floodAlert": sum(
            1 for it in doc["items"] if int(it.get("severityLevel") or 9) == 3
        ),
        "severeFloodWarning": sum(
            1 for it in doc["items"] if int(it.get("severityLevel") or 9) == 1
        ),
    }
    return doc


def known_warning_storm_ids() -> List[str]:
    return sorted(_STORM_WARNINGS.keys())
