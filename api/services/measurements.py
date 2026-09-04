import os
import gzip
import json
import io
import httpx
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
    if os.path.exists(path):
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
    base = os.getenv("REMOTE_BASE_URL")
    if base:
        base = base.rstrip("/")
        parts = path.split("data/raw/")
        key = parts[1] if len(parts) > 1 else os.path.basename(path)
        url = f"{base}/{key.lstrip('/')}"
        try:
            client = httpx.Client(timeout=30, headers={"Accept": "application/x-ndjson, application/json;q=0.9"})
            r = client.get(url)
            r.raise_for_status()
            buf = io.BytesIO(r.content)
            with gzip.GzipFile(fileobj=buf, mode="rb") as gf:
                for raw in gf.read().splitlines():
                    try:
                        line = raw.decode("utf-8").strip()
                    except Exception:
                        continue
                    if not line:
                        continue
                    try:
                        items.append(json.loads(line))
                    except Exception:
                        continue
        except Exception:
            return []
    return items

def _as_utc(dt: datetime) -> datetime:
    """Treat naive timestamps as UTC (EA hydrology archive often omits Z)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def series_points(items: List[Dict[str, Any]], from_: datetime, to: datetime) -> List[SeriesPoint]:
    pts: List[SeriesPoint] = []
    from_utc = _as_utc(from_)
    to_utc = _as_utc(to)
    for it in items:
        dt = it.get("dateTime") or it.get("date") or it.get("time")
        val = it.get("value")
        if not dt or val is None:
            continue
        try:
            raw = str(dt).strip()
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            t = _as_utc(datetime.fromisoformat(raw))
        except Exception:
            continue
        if t < from_utc or t > to_utc:
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
            t = _as_utc(datetime.fromisoformat(k))
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
        name = it.get("label") or it.get("name")
        if sid and lat is not None and lng is not None:
            try:
                row: Dict[str, float] = {"lat": float(lat), "lng": float(lng)}
                if name:
                    # store name alongside coords; keep typing simple
                    row["name"] = name  # type: ignore[assignment]
                out[str(sid)] = row
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
