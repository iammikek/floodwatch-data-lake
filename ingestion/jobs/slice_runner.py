import argparse
import os
from datetime import datetime, timezone, timedelta
import json
from ingestion.clients.ea import EAClient
from ingestion.io import write_ndjson_gz


def iso_utc(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def next_month(year: int, month: int) -> datetime:
    if month == 12:
        return datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    return datetime(year, month + 1, 1, tzinfo=timezone.utc)


def run_hydrology_month_slice(measure: str, year: int, month: int) -> dict:
    client = EAClient()
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = next_month(year, month)
    since = start.strftime("%Y-%m-%d")
    until = (end - timedelta(days=1)).strftime("%Y-%m-%d")
    items = client.get_readings(measure, since=since, until=until, sorted_flag=True)
    out = f"data/raw/ea/readings/{measure}/{year:04d}-{month:02d}.ndjson.gz"
    write_ndjson_gz(out, items)
    size = os.path.getsize(out) if os.path.exists(out) else 0
    return {
        "dataset": "hydrology_readings",
        "measure": measure,
        "year": year,
        "month": month,
        "path": out,
        "rows": len(items),
        "bytes": size,
    }


def main():
    p = argparse.ArgumentParser(prog="slice-runner")
    p.add_argument("--dataset", required=True, choices=["hydrology_readings"])
    p.add_argument("--measure", required=True)
    p.add_argument("--year", required=True, type=int)
    p.add_argument("--month", required=True, type=int)
    args = p.parse_args()
    if args.dataset == "hydrology_readings":
        res = run_hydrology_month_slice(args.measure, args.year, args.month)
        print(json.dumps(res, separators=(",", ":"), ensure_ascii=False))


if __name__ == "__main__":
    main()
