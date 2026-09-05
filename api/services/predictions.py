"""Historic multi-gauge analogue matching → floodwatch.prediction.v1."""

from __future__ import annotations

from bisect import bisect_right, insort
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import sqrt
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


def _percentile_rank(values: Sequence[float], value: float) -> float:
    if not values:
        return 0.0
    below = sum(1 for v in values if v <= value)
    return round(100.0 * below / len(values), 2)


def _percentile_rank_sorted(sorted_vals: Sequence[float], value: float) -> float:
    if not sorted_vals:
        return 0.0
    below = bisect_right(sorted_vals, value)
    return round(100.0 * below / len(sorted_vals), 2)


@dataclass(frozen=True)
class _SeriesIndex:
    pts: Sequence[SeriesPoint]
    times: List[datetime]
    values: List[float]
    index_by_time: Dict[datetime, int]
    sorted_values: List[float]
    min_v: float
    max_v: float


def _index_series(pts: Sequence[SeriesPoint]) -> _SeriesIndex:
    times = [p.t for p in pts]
    values = [float(p.value) for p in pts]
    return _SeriesIndex(
        pts=pts,
        times=times,
        values=values,
        index_by_time={t: i for i, t in enumerate(times)},
        sorted_values=sorted(values),
        min_v=min(values) if values else 0.0,
        max_v=max(values) if values else 0.0,
    )


def _window_end_candidates(
    series_by_measure: Dict[str, Sequence[SeriesPoint]],
    measure_ids: Sequence[str],
    cutoff: datetime,
    horizon_hours: int,
) -> List[datetime]:
    shared: Optional[set[datetime]] = None
    for measure_id in measure_ids:
        pts = series_by_measure.get(measure_id, [])
        times = {
            p.t
            for p in pts
            if p.t <= cutoff - timedelta(hours=horizon_hours)
        }
        shared = times if shared is None else shared & times
    if not shared:
        return []
    return sorted(t for t in shared if t >= cutoff - timedelta(days=3650))  # stable order


def _window_points(pts: Sequence[SeriesPoint], end: datetime, window_hours: int) -> List[SeriesPoint]:
    start = end - timedelta(hours=window_hours - 1)
    window = [p for p in pts if start <= p.t <= end]
    return window if len(window) == window_hours else []


def _window_points_indexed(
    index: _SeriesIndex, end: datetime, window_hours: int
) -> List[SeriesPoint]:
    idx = index.index_by_time.get(end)
    if idx is None or idx + 1 < window_hours:
        return []
    start_idx = idx - window_hours + 1
    expected_start = end - timedelta(hours=window_hours - 1)
    if index.times[start_idx] == expected_start:
        return list(index.pts[start_idx : idx + 1])
    return _window_points(index.pts, end, window_hours)


def _values_by_measure(
    series_by_measure: Dict[str, Sequence[SeriesPoint]],
    measure_ids: Sequence[str],
) -> Dict[str, List[float]]:
    return {measure_id: [p.value for p in series_by_measure.get(measure_id, [])] for measure_id in measure_ids}


def _fingerprint_for_window(
    series_by_measure: Dict[str, Sequence[SeriesPoint]],
    values_by_measure: Dict[str, Sequence[float]],
    measure_ids: Sequence[str],
    end: datetime,
    window_hours: int,
) -> Optional[List[float]]:
    vector: List[float] = []
    for measure_id in measure_ids:
        pts = _window_points(series_by_measure.get(measure_id, []), end, window_hours)
        if len(pts) != window_hours:
            return None
        vals = values_by_measure.get(measure_id, [])
        vector.extend(_percentile_rank(vals, p.value) / 100.0 for p in pts[-12:])
        base = pts[0].value
        hist_span = max(vals) - min(vals) if vals else 0.0
        scale = hist_span if hist_span > 0.05 else 0.05
        vector.extend(round((p.value - base) / scale, 4) for p in pts[-12:])
        slope = _slope_per_hour(pts[-6:])
        vector.append(0.0 if slope is None else round(slope, 4))
    return vector


def _fingerprint_for_window_indexed(
    indexes: Dict[str, _SeriesIndex],
    measure_ids: Sequence[str],
    end: datetime,
    window_hours: int,
) -> Optional[List[float]]:
    vector: List[float] = []
    for measure_id in measure_ids:
        index = indexes[measure_id]
        pts = _window_points_indexed(index, end, window_hours)
        if len(pts) != window_hours:
            return None
        vector.extend(_percentile_rank_sorted(index.sorted_values, p.value) / 100.0 for p in pts[-12:])
        base = pts[0].value
        hist_span = index.max_v - index.min_v
        scale = hist_span if hist_span > 0.05 else 0.05
        vector.extend(round((p.value - base) / scale, 4) for p in pts[-12:])
        slope = _slope_per_hour(pts[-6:])
        vector.append(0.0 if slope is None else round(slope, 4))
    return vector


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sqrt(sum(x * x for x in a))
    norm_b = sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _outcome_for_analogue(
    primary_series: Sequence[SeriesPoint],
    end: datetime,
    *,
    horizon_hours: int,
    impact_delta: float,
    watch_delta: float,
) -> Tuple[str, Optional[float]]:
    analogue_window = _window_points(primary_series, end, 24)
    if not analogue_window:
        return ("clear", None)
    baseline = analogue_window[-1].value
    history_values = sorted(p.value for p in primary_series if p.t <= end)
    p90 = _percentile(history_values, 90) if history_values else baseline
    p95 = _percentile(history_values, 95) if history_values else baseline
    future = [
        p for p in primary_series
        if end < p.t <= end + timedelta(hours=horizon_hours)
    ]
    first_watch = None
    for p in future:
        rise = p.value - baseline
        hours = (p.t - end).total_seconds() / 3600.0
        if p.value >= p95 or rise >= impact_delta:
            return ("impact", round(hours, 1))
        if first_watch is None and (p.value >= p90 or rise >= watch_delta):
            first_watch = round(hours, 1)
    if first_watch is not None:
        return ("watch", first_watch)
    return ("clear", None)


def _outcome_for_analogue_indexed(
    primary: _SeriesIndex,
    end: datetime,
    history_sorted: Sequence[float],
    *,
    horizon_hours: int,
    impact_delta: float,
    watch_delta: float,
) -> Tuple[str, Optional[float]]:
    analogue_window = _window_points_indexed(primary, end, 24)
    if not analogue_window:
        return ("clear", None)
    baseline = analogue_window[-1].value
    p90 = _percentile(history_sorted, 90) if history_sorted else baseline
    p95 = _percentile(history_sorted, 95) if history_sorted else baseline
    end_idx = primary.index_by_time.get(end)
    if end_idx is None:
        return ("clear", None)
    horizon_end = end + timedelta(hours=horizon_hours)
    first_watch = None
    for p in primary.pts[end_idx + 1 :]:
        if p.t > horizon_end:
            break
        rise = p.value - baseline
        hours = (p.t - end).total_seconds() / 3600.0
        if p.value >= p95 or rise >= impact_delta:
            return ("impact", round(hours, 1))
        if first_watch is None and (p.value >= p90 or rise >= watch_delta):
            first_watch = round(hours, 1)
    if first_watch is not None:
        return ("watch", first_watch)
    return ("clear", None)


def _weighted_median_time(rows: Sequence[Dict[str, Any]]) -> Optional[float]:
    values = sorted(
        [(float(r["timeToImpactHours"]), float(r["similarity"])) for r in rows if r.get("timeToImpactHours") is not None],
        key=lambda x: x[0],
    )
    if not values:
        return None
    total = sum(weight for _, weight in values)
    seen = 0.0
    for value, weight in values:
        seen += weight
        if seen >= total / 2.0:
            return round(value, 1)
    return round(values[-1][0], 1)


def _impact_window(now: datetime, hours: Optional[float]) -> Optional[Dict[str, str]]:
    if hours is None:
        return None
    impact_from = now + timedelta(hours=max(0.0, hours * 0.7))
    impact_to = now + timedelta(hours=hours + 3)
    return {
        "from": impact_from.isoformat().replace("+00:00", "Z"),
        "to": impact_to.isoformat().replace("+00:00", "Z"),
    }


def _confidence_label(confidence: float) -> str:
    if confidence >= 0.7:
        return "High"
    if confidence >= 0.45:
        return "Medium"
    return "Low"


def _consensus_verdict(
    analogue_rows: Sequence[Dict[str, Any]],
    corridor_label: str,
) -> Tuple[str, str, Optional[float], float, str, str]:
    if not analogue_rows:
        return (
            "clear",
            "No predicted impact in window",
            None,
            0.35,
            "Current multi-gauge shape does not closely match disruptive historic EA windows.",
            "No trend-based hold — continue live-warning checks.",
        )

    total = len(analogue_rows)
    impacts = [r for r in analogue_rows if r["outcome"] == "impact"]
    watches = [r for r in analogue_rows if r["outcome"] == "watch"]
    impact_rate = len(impacts) / total
    watch_or_impact_rate = (len(impacts) + len(watches)) / total
    clear_rate = sum(1 for r in analogue_rows if r["outcome"] == "clear") / total

    if impact_rate >= 0.6:
        tti = _weighted_median_time(impacts)
        confidence = min(0.92, 0.5 + 0.4 * impact_rate)
        summary = (
            f"{len(impacts)} of {total} close historic matches reached disruptive levels "
            f"within the next day on {corridor_label.lower()}."
        )
        implication = (
            f"Hold non-urgent runs on {corridor_label} "
            f"within ~{int(tti) if tti is not None else 6}h if levels keep rising."
        )
        return ("at_risk", "At risk within window", tti, round(confidence, 2), summary, implication)

    if impact_rate >= 0.4 or watch_or_impact_rate >= 0.5:
        mixed = impacts + watches
        tti = _weighted_median_time(mixed)
        confidence = min(0.92, 0.35 + 0.3 * watch_or_impact_rate)
        summary = (
            f"Historic EA matches are mixed: {len(impacts)} impact analogue(s), "
            f"{len(watches)} watch analogue(s), {total - len(impacts) - len(watches)} clear."
        )
        implication = f"Increase monitoring on {corridor_label}; no hard hold yet."
        return ("watch", "Watch — mixed historic analogues", tti, round(confidence, 2), summary, implication)

    confidence = min(0.92, 0.5 + 0.2 * clear_rate)
    summary = (
        f"{int(clear_rate * total)} of {total} close historic matches stayed below disruptive thresholds "
        f"through the next day."
    )
    implication = "No trend-based hold — continue live-warning checks."
    return ("clear", "No predicted impact in window", None, round(confidence, 2), summary, implication)


def _analogue_measure_ids(
    corridor: Dict[str, Any],
    series_by_measure: Dict[str, Sequence[SeriesPoint]],
) -> List[str]:
    """Gauges used for multi-gauge fingerprints.

    Required gauges (optional=False) must have series. Optional gauges (e.g.
    Midelney without a long hydrology archive) are included only when present.
    """
    primary_id = corridor["primary"]["measure_id"]
    active: List[str] = []
    for gauge in corridor["gauges"]:
        measure_id = gauge["measure_id"]
        has_series = bool(series_by_measure.get(measure_id))
        if has_series:
            active.append(measure_id)
        elif not gauge.get("optional"):
            return []
    if primary_id not in active or len(active) < 2:
        return []
    # Keep corridor order; primary first for outcome scoring.
    if active[0] != primary_id:
        active = [primary_id] + [m for m in active if m != primary_id]
    return active


def _build_analogue_rows(
    corridor: Dict[str, Any],
    series_by_measure: Dict[str, Sequence[SeriesPoint]],
    now: datetime,
    *,
    window_hours: int,
    min_gap_hours: int,
    horizon_hours: int,
    min_similarity: float,
    top_k: int,
) -> List[Dict[str, Any]]:
    measure_ids = _analogue_measure_ids(corridor, series_by_measure)
    if not measure_ids:
        return []
    indexes = {
        measure_id: _index_series(series_by_measure[measure_id]) for measure_id in measure_ids
    }
    latest_times = [indexes[measure_id].times[-1] for measure_id in measure_ids]
    current_end = min(latest_times)
    current_fp = _fingerprint_for_window_indexed(indexes, measure_ids, current_end, window_hours)
    if not current_fp:
        return []

    primary = indexes[measure_ids[0]]
    candidate_cutoff = current_end - timedelta(hours=min_gap_hours)
    candidates = _window_end_candidates(series_by_measure, measure_ids, candidate_cutoff, horizon_hours)
    rows: List[Dict[str, Any]] = []
    history_sorted: List[float] = []
    hist_i = 0
    for end in candidates:
        while hist_i < len(primary.pts) and primary.pts[hist_i].t <= end:
            insort(history_sorted, primary.values[hist_i])
            hist_i += 1
        fp = _fingerprint_for_window_indexed(indexes, measure_ids, end, window_hours)
        if not fp:
            continue
        similarity = round(_cosine_similarity(current_fp, fp), 4)
        if similarity < min_similarity:
            continue
        outcome, tti = _outcome_for_analogue_indexed(
            primary,
            end,
            history_sorted,
            horizon_hours=horizon_hours,
            impact_delta=0.35,
            watch_delta=0.2,
        )
        rows.append(
            {
                "type": "historic_analogue",
                "ref": end.isoformat().replace("+00:00", "Z"),
                "label": end.strftime("%b %Y analogue"),
                "similarity": similarity,
                "outcome": outcome,
                "timeToImpactHours": tti,
            }
        )
    rows.sort(key=lambda r: r["similarity"], reverse=True)
    return rows[:top_k]


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
    gauge_meta = corridor["gauges"]
    measure_ids = [g["measure_id"] for g in gauge_meta]

    series_by_measure: Dict[str, Sequence[SeriesPoint]] = {
        measure_id: series_loader(measure_id, hist_from, now, "hour")
        for measure_id in measure_ids
    }
    primary_series = series_by_measure[primary["measure_id"]]
    primary_analysis = analyse_series(primary_series, now=now)
    active_measures = _analogue_measure_ids(corridor, series_by_measure)

    analogue_rows = _build_analogue_rows(
        corridor,
        series_by_measure,
        now,
        window_hours=24,
        min_gap_hours=24,
        horizon_hours=24,
        min_similarity=0.85,
        top_k=20,
    )
    verdict, verdict_label, tti, confidence, summary, implication = _consensus_verdict(
        analogue_rows,
        corridor["label"],
    )

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
        pts = series_by_measure[mid]
        analysis = primary_analysis if mid == primary["measure_id"] else analyse_series(pts, now=now)
        if mid != primary["measure_id"]:
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

    drivers.extend(analogue_rows)
    drivers.append(
        {
            "type": "analogue_consensus",
            "ref": f"k{len(analogue_rows)}",
            "label": f"{len(analogue_rows)} matched windows",
            "impactRate": round(sum(1 for r in analogue_rows if r["outcome"] == "impact") / len(analogue_rows), 2)
            if analogue_rows
            else 0.0,
            "watchRate": round(sum(1 for r in analogue_rows if r["outcome"] == "watch") / len(analogue_rows), 2)
            if analogue_rows
            else 0.0,
        }
    )

    impact_window = _impact_window(now, tti)

    risk_for_areas = "high" if verdict == "at_risk" else ("medium" if verdict == "watch" else "low")
    affected = []
    if verdict in ("at_risk", "watch"):
        for area in corridor["affected_areas"]:
            affected.append({**area, "risk": risk_for_areas if verdict == "at_risk" else "medium"})

    safe = verdict == "clear"

    series_start = None
    if primary_series:
        tail = primary_series[-12:]
        series_start = tail[0].t.isoformat().replace("+00:00", "Z")

    return {
        "schema": "floodwatch.prediction.v1",
        "as_of": now.isoformat().replace("+00:00", "Z"),
        "region": corridor["region"],
        "corridor": {"id": corridor["id"], "label": corridor["label"]},
        "prediction": {
            "verdict": verdict,
            "verdictLabel": verdict_label,
            "timeToImpactHours": tti,
            "impactWindow": impact_window,
            "confidence": round(confidence, 2),
            "confidenceLabel": _confidence_label(confidence),
            "summary": summary,
        },
        "drivers": drivers,
        "affectedAreas": affected,
        "dispatch": {"implication": implication, "safeToPass": safe},
        "method": {
            "name": "historic_analogue_v1",
            "inputs": ["ea_stage_history_hour", "corridor_gauge_set"],
            "parameters": {
                "windowHours": 24,
                "historyDays": history_days,
                "topK": 20,
                "minSimilarity": 0.85,
                "activeGauges": len(active_measures),
            },
            "notes": (
                "Matches current multi-gauge shape to past EA windows. "
                "Optional corridor gauges without archive are omitted from fingerprints. "
                "Not a rainfall-lag or depth model; confidence reflects analogue agreement."
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
