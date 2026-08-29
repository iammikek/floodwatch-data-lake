"""Historic stage trajectory → floodwatch.prediction.v0 (no rainfall / depth yet)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from api.config.corridors import get_corridor, list_corridor_ids
from api.models import SeriesPoint
from api.services.measurements import (
    aggregate_points,
    month_iter,
    read_ndjson_gz,
    series_points,
)


def _load_measure_series(
    measure_id: str,
    from_: datetime,
    to: datetime,
    aggregate: str = "hour",
) -> List[SeriesPoint]:
    series: List[SeriesPoint] = []
    for y, m in month_iter(from_, to):
        path = f"data/raw/ea/readings/{measure_id}/{y:04d}-{m:02d}.ndjson.gz"
        items = read_ndjson_gz(path)
        series.extend(series_points(items, from_, to))
    if aggregate in ("hour", "day"):
        series = aggregate_points(series, aggregate)
    return series


def _percentile(sorted_vals: Sequence[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return float(sorted_vals[f])
    return float(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f))


def _slope_per_hour(pts: Sequence[SeriesPoint], lookback_hours: int = 6) -> Optional[float]:
    if len(pts) < 2:
        return None
    end = pts[-1].t
    start_cut = end - timedelta(hours=lookback_hours)
    window = [p for p in pts if p.t >= start_cut]
    if len(window) < 2:
        window = list(pts[-min(8, len(pts)) :])
    if len(window) < 2:
        return None
    dt_h = (window[-1].t - window[0].t).total_seconds() / 3600.0
    if dt_h <= 0:
        return None
    return (window[-1].value - window[0].value) / dt_h


def analyse_series(pts: Sequence[SeriesPoint], now: Optional[datetime] = None) -> Dict[str, Any]:
    """Pure analysis on an hour (or raw) series — used by tests without disk I/O."""
    now = now or datetime.now(timezone.utc)
    if not pts:
        return {
            "level": None,
            "slope_per_hour": None,
            "pct_rank": None,
            "p70": None,
            "p90": None,
            "p95": None,
            "signal": "no_data",
            "hours_to_p95": None,
        }

    values = sorted(p.value for p in pts)
    latest = pts[-1]
    level = float(latest.value)
    slope = _slope_per_hour(pts)
    below = sum(1 for v in values if v <= level)
    pct_rank = 100.0 * below / len(values)
    p70 = _percentile(values, 70)
    p90 = _percentile(values, 90)
    p95 = _percentile(values, 95)

    if slope is None:
        signal = "unknown_slope"
    elif slope > 0.01 and level >= p90:
        signal = "elevated_and_rising"
    elif slope > 0.01 and level >= p70:
        signal = "rising_toward_high"
    elif slope > 0.005:
        signal = "rising"
    elif slope < -0.005:
        signal = "steady_or_falling"
    else:
        signal = "steady"

    hours_to_p95 = None
    if slope and slope > 0.005 and level < p95:
        hours_to_p95 = round((p95 - level) / slope, 1)
        if hours_to_p95 < 0:
            hours_to_p95 = None
        elif hours_to_p95 > 72:
            hours_to_p95 = 72.0

    return {
        "level": level,
        "slope_per_hour": None if slope is None else round(slope, 4),
        "pct_rank": round(pct_rank, 1),
        "p70": round(p70, 3),
        "p90": round(p90, 3),
        "p95": round(p95, 3),
        "signal": signal,
        "hours_to_p95": hours_to_p95,
        "as_of_point": latest.t.isoformat().replace("+00:00", "Z"),
    }


def _verdict_from_primary(analysis: Dict[str, Any]) -> Tuple[str, str, Optional[float], float, str]:
    signal = analysis.get("signal")
    hours = analysis.get("hours_to_p95")
    pct = analysis.get("pct_rank") or 0.0

    if signal == "no_data":
        return (
            "watch",
            "Insufficient local series for this corridor",
            None,
            0.25,
            "No readings found for primary measure in the history window.",
        )

    if signal == "elevated_and_rising":
        tti = hours if hours is not None else 3.0
        return (
            "at_risk",
            "At risk within window",
            tti,
            min(0.85, 0.45 + pct / 200.0),
            "Primary gauge is elevated versus its own mined history and still rising.",
        )

    if signal == "rising_toward_high":
        tti = hours if hours is not None else 8.0
        return (
            "at_risk" if (hours is not None and hours <= 12) else "watch",
            "At risk within window" if (hours is not None and hours <= 12) else "Watch — rising toward historic high",
            tti,
            min(0.75, 0.4 + pct / 250.0),
            "Stage trajectory resembles approaches to prior high-water periods in local EA history.",
        )

    if signal == "rising":
        return (
            "watch",
            "Watch — rising",
            hours,
            0.45,
            "Levels are rising but still below typically disruptive percentiles for this gauge.",
        )

    return (
        "clear",
        "No predicted impact in window",
        None,
        0.55,
        "Current trajectory does not match elevated historic analogues for this measure.",
    )


def _compact_hour_values(pts: Sequence[SeriesPoint], n: int = 12) -> List[float]:
    tail = list(pts[-n:]) if pts else []
    return [round(p.value, 3) for p in tail]


def predict_corridor(
    corridor_id: str,
    *,
    history_days: int = 120,
    now: Optional[datetime] = None,
    series_loader=_load_measure_series,
) -> Dict[str, Any]:
    if corridor_id not in list_corridor_ids():
        raise KeyError(corridor_id)

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    corridor = get_corridor(corridor_id)
    primary = corridor["primary"]
    hist_from = now - timedelta(days=history_days)

    primary_series = series_loader(primary["measure_id"], hist_from, now, "hour")
    primary_analysis = analyse_series(primary_series, now=now)
    verdict, verdict_label, tti, confidence, summary = _verdict_from_primary(primary_analysis)

    drivers: List[Dict[str, Any]] = [
        {
            "type": "gauge_trajectory",
            "ref": primary["measure_id"],
            "label": primary["label"],
            "signal": primary_analysis["signal"],
            "level": primary_analysis["level"],
            "pct_rank": primary_analysis["pct_rank"],
            "slope_per_hour": primary_analysis["slope_per_hour"],
        }
    ]

    gauge_series_out: Dict[str, List[float]] = {}
    key_gauge_id = corridor["gauges"][0]["ref"]

    for g in corridor["gauges"]:
        mid = g["measure_id"]
        # Short window for sparkline observables; primary already loaded long.
        if mid == primary["measure_id"]:
            pts = primary_series
            analysis = primary_analysis
        else:
            pts = series_loader(mid, now - timedelta(days=14), now, "hour")
            analysis = analyse_series(pts, now=now)
            drivers.append(
                {
                    "type": "gauge_trajectory",
                    "ref": mid,
                    "label": g["label"],
                    "signal": analysis["signal"],
                    "level": analysis["level"],
                    "pct_rank": analysis["pct_rank"],
                    "slope_per_hour": analysis["slope_per_hour"],
                }
            )
        gauge_series_out[g["ref"]] = _compact_hour_values(pts, 12)

    drivers.append(
        {
            "type": "historic_percentile",
            "ref": primary["measure_id"],
            "label": f"{primary['label']} vs mined history",
            "similarity": round((primary_analysis.get("pct_rank") or 0) / 100.0, 2),
            "p90": primary_analysis.get("p90"),
            "p95": primary_analysis.get("p95"),
        }
    )

    impact_window = None
    if tti is not None:
        impact_from = now + timedelta(hours=max(0.0, tti * 0.7))
        impact_to = now + timedelta(hours=tti + 3)
        impact_window = {
            "from": impact_from.isoformat().replace("+00:00", "Z"),
            "to": impact_to.isoformat().replace("+00:00", "Z"),
        }

    risk_for_areas = "high" if verdict == "at_risk" else ("medium" if verdict == "watch" else "low")
    affected = []
    if verdict in ("at_risk", "watch"):
        for area in corridor["affected_areas"]:
            affected.append({**area, "risk": risk_for_areas if verdict == "at_risk" else "medium"})

    safe = verdict == "clear"
    if verdict == "at_risk":
        implication = (
            f"Hold non-urgent runs on {corridor['label']} "
            f"within ~{int(tti) if tti is not None else 6}h if levels keep rising."
        )
    elif verdict == "watch":
        implication = f"Increase monitoring on {corridor['label']}; no hard hold yet."
    else:
        implication = "No trend-based hold — continue live-warning checks."

    series_start = None
    if primary_series:
        tail = primary_series[-12:]
        series_start = tail[0].t.isoformat().replace("+00:00", "Z")

    return {
        "schema": "floodwatch.prediction.v0",
        "as_of": now.isoformat().replace("+00:00", "Z"),
        "region": corridor["region"],
        "corridor": {"id": corridor["id"], "label": corridor["label"]},
        "prediction": {
            "verdict": verdict,
            "verdictLabel": verdict_label,
            "timeToImpactHours": tti,
            "impactWindow": impact_window,
            "confidence": round(confidence, 2),
            "confidenceLabel": (
                "High" if confidence >= 0.7 else "Medium" if confidence >= 0.45 else "Low"
            ),
            "summary": summary,
        },
        "drivers": drivers,
        "affectedAreas": affected,
        "dispatch": {"implication": implication, "safeToPass": safe},
        "method": {
            "name": "historic_stage_trajectory_v0",
            "inputs": ["ea_stage_history", "live_stage_hour"],
            "notes": (
                "v0 uses station-relative percentiles and recent slope from mined EA readings. "
                "Not a rainfall lag or depth model."
            ),
        },
        "observables": {
            "seriesStart": series_start,
            "keyGaugeId": key_gauge_id,
            "rainfallUpstreamMm": [],
            "gaugeSeries": gauge_series_out,
            "primaryMeasureId": primary["measure_id"],
            "primaryAnalysis": primary_analysis,
        },
    }
