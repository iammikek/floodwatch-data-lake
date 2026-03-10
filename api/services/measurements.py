import os
import gzip
import json
from typing import Any, Dict, List, Tuple
from datetime import datetime, timezone, timedelta
from api.models import SeriesPoint


def month_iter(start: datetime, end: datetime) -> List[Tuple[int, int]]:
    s = datetime(start.year, start.month, 1, tzinfo=timezone.utc)
    e = datetime(end.year, end.month, 1, tzinfo=timezone.utc)
    months: List[Tuple[int, int]] = []
    cur = s
    while cur <= e:
        months.append((cur.year, cur.month))
        if cur.month == 12:
            cur = datetime(cur.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            cur = datetime(cur.year, cur.month + 1, 1, tzinfo=timezone.utc)
    return months

def read_ndjson_gz(path: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not os.path.exists(path):
        return items
    with gzip.open(path, "rt") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                continue
    return items

def series_points(items: List[Dict[str, Any]], from_: datetime, to: datetime) -> List[SeriesPoint]:
    pts: List[SeriesPoint] = []
    for it in items:
        dt = it.get("dateTime") or it.get("date") or it.get("time")
        val = it.get("value")
        if not dt or val is None:
            continue
        try:
            t = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            continue
        if t < from_ or t > to:
            continue
        pts.append(SeriesPoint(t=t, value=float(val), agg="raw", quality=it.get("qualifier")))
    pts.sort(key=lambda p: p.t)
    return pts

def aggregate_points(pts: List[SeriesPoint], mode: str) -> List[SeriesPoint]:
    if mode == "raw":
        return pts
    buckets: Dict[str, List[float]] = {}
    for p in pts:
        if mode == "hour":
            k = p.t.replace(minute=0, second=0, microsecond=0).isoformat()
        elif mode == "day":
            k = p.t.date().isoformat()
        else:
            return pts
        buckets.setdefault(k, []).append(p.value)
    out: List[SeriesPoint] = []
    for k, vs in buckets.items():
        if mode == "hour":
            t = datetime.fromisoformat(k)
        else:
            t = datetime.fromisoformat(k + "T00:00:00+00:00")
        out.append(SeriesPoint(t=t, value=sum(vs) / len(vs), agg=mode))
    out.sort(key=lambda p: p.t)
    return out
