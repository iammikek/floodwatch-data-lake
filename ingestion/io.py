from typing import Iterable, Dict, Any
import os
import gzip
import json


def write_ndjson_gz(path: str, rows: Iterable[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False))
            f.write("\n")

