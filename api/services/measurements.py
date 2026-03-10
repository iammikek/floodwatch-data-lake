import os
import gzip
import json
from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime, timezone, timedelta
from api.models import SeriesPoint
import glob
import gzip
import os
import json


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

def _latest_file(dirpath: str, pattern: str = "*.ndjson.gz") -> Optional[str]:
    paths = glob.glob(os.path.join(dirpath, pattern))
    if not paths:
        return None
    paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return paths[0]

def load_latest_stations() -> Dict[str, Dict[str, float]]:
    dirpath = os.path.join("data", "raw", "ea", "stations")
    latest = _latest_file(dirpath)
    out: Dict[str, Dict[str, float]] = {}
    if not latest:
        return out
    items = read_ndjson_gz(latest)
    for it in items:
        sid = it.get("notation") or it.get("stationReference") or it.get("@id")
        lat = it.get("lat") or it.get("latitude")
        lng = it.get("long") or it.get("longitude") or it.get("lng")
        if sid and lat is not None and lng is not None:
            try:
                out[str(sid)] = {"lat": float(lat), "lng": float(lng)}
            except Exception:
                continue
    return out

def load_latest_measures_map() -> Dict[str, str]:
    dirpath = os.path.join("data", "raw", "ea", "measures")
    latest = _latest_file(dirpath)
    out: Dict[str, str] = {}
    if not latest:
        return out
    items = read_ndjson_gz(latest)
    for it in items:
        mid = it.get("notation") or it.get("@id")
        # station may be nested or a direct field; accept common keys
        station = it.get("station") or it.get("stationReference") or it.get("station_id")
        if isinstance(station, dict):
            station = station.get("notation") or station.get("@id")
        if mid and station:
            out[str(mid)] = str(station)
    return out
