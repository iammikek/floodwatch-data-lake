import argparse
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from ingestion.clients.ea import EAClient
from ingestion.io import write_ndjson_gz
from ingestion.regions import REGION_BBOX


def iso_utc(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def next_month(year: int, month: int) -> datetime:
    if month == 12:
        return datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    return datetime(year, month + 1, 1, tzinfo=timezone.utc)


def cmd_fetch_ea_stations(args: argparse.Namespace) -> None:
    client = EAClient()
    items = client.get_stations(bbox=args.bbox, parameter=args.parameter)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or f"data/raw/ea/stations/stations_{ts}.ndjson.gz"
    write_ndjson_gz(out, items)
    print(out)


def cmd_fetch_ea_measures(args: argparse.Namespace) -> None:
    client = EAClient()
    items = client.get_measures(station=args.station, parameter=args.parameter)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sid = args.station or "all"
    out = args.out or f"data/raw/ea/measures/measures_{sid}_{ts}.ndjson.gz"
    write_ndjson_gz(out, items)
    print(out)


def cmd_fetch_ea_readings_month(args: argparse.Namespace) -> None:
    client = EAClient()
    start = datetime(args.year, args.month, 1, tzinfo=timezone.utc)
    end = next_month(args.year, args.month)
    since = start.strftime("%Y-%m-%d")
    until = (end - timedelta(days=1)).strftime("%Y-%m-%d")
    items: List[Dict[str, Any]] = client.get_readings(args.measure, since=since, until=until, sorted_flag=True)
    out = args.out or f"data/raw/ea/readings/{args.measure}/{args.year:04d}-{args.month:02d}.ndjson.gz"
    write_ndjson_gz(out, items)
    print(out)

def cmd_fetch_ea_stations_region(args: argparse.Namespace) -> None:
    bbox = REGION_BBOX[args.region]
    ns = argparse.Namespace(bbox=bbox, parameter=args.parameter, out=args.out)
    cmd_fetch_ea_stations(ns)

def cmd_fetch_ea_readings_range(args: argparse.Namespace) -> None:
    client = EAClient()
    start_year, start_month = map(int, args.from_month.split("-"))
    end_year, end_month = map(int, args.to_month.split("-"))
    y, m = start_year, start_month
    while True:
        s = datetime(y, m, 1, tzinfo=timezone.utc)
        e = next_month(y, m)
        since = s.strftime("%Y-%m-%d")
        until = (e - timedelta(days=1)).strftime("%Y-%m-%d")
        items: List[Dict[str, Any]] = client.get_readings(args.measure, since=since, until=until, sorted_flag=True)
        out = f"data/raw/ea/readings/{args.measure}/{y:04d}-{m:02d}.ndjson.gz"
        write_ndjson_gz(out, items)
        if y == end_year and m == end_month:
            break
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1

def _measure_notation(m: Dict[str, Any]) -> str:
    nid = m.get("notation")
    if nid:
        return nid
    mid = m.get("@id", "")
    if "/id/measures/" in mid:
        return mid.split("/id/measures/")[-1]
    return mid

def _station_id(s: Dict[str, Any]) -> str:
    return s.get("notation") or s.get("stationReference") or s.get("@id", "")

def cmd_backfill_ea_region(args: argparse.Namespace) -> None:
    client = EAClient()
    bbox = REGION_BBOX[args.region]
    stations = client.get_stations(bbox=bbox)
    params = [p.strip() for p in (args.parameters.split(",") if args.parameters else ["level","flow"])]
    # Default range: last 10 years through current month if not provided
    now = datetime.now(timezone.utc)
    if args.from_month and args.to_month:
        from_month = args.from_month
        to_month = args.to_month
    else:
        fy = now.year - 10
        fm = now.month
        from_month = f"{fy:04d}-{fm:02d}"
        to_month = f"{now.year:04d}-{now.month:02d}"
    station_count = 0
    measure_total = 0
    for s in stations:
        station_count += 1
        if args.max_stations and station_count > args.max_stations:
            break
        sid = _station_id(s)
        measures = client.get_measures(station=sid)
        selected = [m for m in measures if m.get("parameter") in params]
        for m in selected:
            if args.max_measures and measure_total >= args.max_measures:
                break
            measure_id = _measure_notation(m)
            rng_args = argparse.Namespace(measure=measure_id, from_month=from_month, to_month=to_month)
            cmd_fetch_ea_readings_range(rng_args)
            measure_total += 1
        if args.max_measures and measure_total >= args.max_measures:
            break
    print(f"region={args.region} stations_processed={min(station_count, args.max_stations or station_count)} measures_processed={measure_total}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ingestion")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("fetch-ea-stations")
    ps.add_argument("--bbox", help="west,south,east,north")
    ps.add_argument("--parameter", help="e.g. level, flow")
    ps.add_argument("--out")
    ps.set_defaults(func=cmd_fetch_ea_stations)
    psr = sub.add_parser("fetch-ea-stations-region")
    psr.add_argument("--region", required=True, choices=list(REGION_BBOX.keys()))
    psr.add_argument("--parameter")
    psr.add_argument("--out")
    psr.set_defaults(func=cmd_fetch_ea_stations_region)


    pm = sub.add_parser("fetch-ea-measures")
    pm.add_argument("--station", help="station notation or ref")
    pm.add_argument("--parameter", help="e.g. level, flow")
    pm.add_argument("--out")
    pm.set_defaults(func=cmd_fetch_ea_measures)

    pr = sub.add_parser("fetch-ea-readings-month")
    pr.add_argument("--measure", required=True, help="measure id")
    pr.add_argument("--year", type=int, required=True)
    pr.add_argument("--month", type=int, required=True)
    pr.add_argument("--out")
    pr.set_defaults(func=cmd_fetch_ea_readings_month)
    prng = sub.add_parser("fetch-ea-readings-range")
    prng.add_argument("--measure", required=True)
    prng.add_argument("--from", dest="from_month", required=True, help="YYYY-MM")
    prng.add_argument("--to", dest="to_month", required=True, help="YYYY-MM")
    prng.set_defaults(func=cmd_fetch_ea_readings_range)

    pbr = sub.add_parser("backfill-ea-region")
    pbr.add_argument("--region", required=True, choices=list(REGION_BBOX.keys()))
    pbr.add_argument("--parameters", default="level,flow", help="comma-separated, e.g. level,flow")
    pbr.add_argument("--from", dest="from_month", help="YYYY-MM; default last 10y from current month")
    pbr.add_argument("--to", dest="to_month", help="YYYY-MM; default current month")
    pbr.add_argument("--max-stations", type=int, help="limit stations for trial runs")
    pbr.add_argument("--max-measures", type=int, help="limit measures for trial runs")
    pbr.set_defaults(func=cmd_backfill_ea_region)

    return p

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
