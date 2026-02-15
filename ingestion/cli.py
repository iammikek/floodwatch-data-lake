import argparse
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from ingestion.clients.ea import EAClient
from ingestion.io import write_ndjson_gz


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
    since = iso_utc(start)
    until = iso_utc(end - timedelta(seconds=1))
    items: List[Dict[str, Any]] = client.get_readings(args.measure, since=since, until=until, sorted_flag=True)
    out = args.out or f"data/raw/ea/readings/{args.measure}/{args.year:04d}-{args.month:02d}.ndjson.gz"
    write_ndjson_gz(out, items)
    print(out)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ingestion")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("fetch-ea-stations")
    ps.add_argument("--bbox", help="west,south,east,north")
    ps.add_argument("--parameter", help="e.g. level, flow")
    ps.add_argument("--out")
    ps.set_defaults(func=cmd_fetch_ea_stations)

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

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

