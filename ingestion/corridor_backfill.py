"""Backfill and coverage helpers for prediction corridor EA measures."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple

from api.config.corridors import get_corridor, list_corridor_ids


def corridor_measure_ids(corridor_id: str) -> List[str]:
    """Unique measure_id values for a corridor (primary + gauges)."""
    corridor = get_corridor(corridor_id)
    seen: set[str] = set()
    ordered: List[str] = []

    def add(mid: str) -> None:
        if mid and mid not in seen:
            seen.add(mid)
            ordered.append(mid)

    primary = corridor.get("primary") or {}
    add(str(primary.get("measure_id", "")))
    for gauge in corridor.get("gauges") or []:
        add(str(gauge.get("measure_id", "")))
    return ordered


def iter_months(from_month: str, to_month: str) -> Iterable[Tuple[int, int]]:
    sy, sm = map(int, from_month.split("-"))
    ey, em = map(int, to_month.split("-"))
    y, m = sy, sm
    while True:
        yield y, m
        if y == ey and m == em:
            break
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1


def month_count(from_month: str, to_month: str) -> int:
    return sum(1 for _ in iter_months(from_month, to_month))


def readings_path(measure_id: str, year: int, month: int, data_root: str = "data/raw/ea/readings") -> str:
    return os.path.join(data_root, measure_id, f"{year:04d}-{month:02d}.ndjson.gz")


@dataclass
class MeasureCoverage:
    measure_id: str
    expected_months: int
    present_months: int
    missing: List[str]

    @property
    def complete(self) -> bool:
        return self.present_months == self.expected_months and self.expected_months > 0


def coverage_for_measure(
    measure_id: str,
    from_month: str,
    to_month: str,
    data_root: str = "data/raw/ea/readings",
) -> MeasureCoverage:
    missing: List[str] = []
    present = 0
    for y, m in iter_months(from_month, to_month):
        label = f"{y:04d}-{m:02d}"
        path = readings_path(measure_id, y, m, data_root=data_root)
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            present += 1
        else:
            missing.append(label)
    expected = month_count(from_month, to_month)
    return MeasureCoverage(
        measure_id=measure_id,
        expected_months=expected,
        present_months=present,
        missing=missing,
    )


def coverage_report(
    corridor_id: str,
    from_month: str,
    to_month: str,
    data_root: str = "data/raw/ea/readings",
) -> Dict[str, Any]:
    measures = [coverage_for_measure(mid, from_month, to_month, data_root=data_root) for mid in corridor_measure_ids(corridor_id)]
    total_expected = sum(m.expected_months for m in measures)
    total_present = sum(m.present_months for m in measures)
    return {
        "corridor": corridor_id,
        "from_month": from_month,
        "to_month": to_month,
        "measure_count": len(measures),
        "total_expected_files": total_expected,
        "total_present_files": total_present,
        "complete": all(m.complete for m in measures),
        "measures": [
            {
                "measure_id": m.measure_id,
                "expected_months": m.expected_months,
                "present_months": m.present_months,
                "missing": m.missing,
                "complete": m.complete,
            }
            for m in measures
        ],
    }


def default_to_month() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


def assert_coverage(
    corridor_id: str,
    from_month: str,
    to_month: str,
    min_months: int,
    data_root: str = "data/raw/ea/readings",
) -> None:
    if corridor_id not in list_corridor_ids():
        raise ValueError(f"Unknown corridor '{corridor_id}'")
    report = coverage_report(corridor_id, from_month, to_month, data_root=data_root)
    failures: List[str] = []
    for row in report["measures"]:
        if row["present_months"] < min_months:
            failures.append(
                f"{row['measure_id']}: {row['present_months']}/{row['expected_months']} months "
                f"(need at least {min_months})"
            )
    if failures:
        raise RuntimeError("Corridor backfill incomplete:\n" + "\n".join(failures))
