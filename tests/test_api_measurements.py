import unittest
from fastapi.testclient import TestClient
from api.main import app
import os
import gzip
import json
from datetime import datetime, timezone, timedelta


class ApiMeasurementsTests(unittest.TestCase):
    def setUp(self):
        self.measure_id = "TESTMEASURE"
        now = datetime.now(timezone.utc)
        self.year = now.year
        self.month = now.month
        self.mm = f"{self.year:04d}-{self.month:02d}"
        self.dirpath = os.path.join("data", "raw", "ea", "readings", self.measure_id)
        os.makedirs(self.dirpath, exist_ok=True)
        self.fpath = os.path.join(self.dirpath, f"{self.mm}.ndjson.gz")
        # write three readings within the window
        t0 = (now - timedelta(hours=3)).replace(microsecond=0)
        t1 = (now - timedelta(hours=2)).replace(microsecond=0)
        t2 = (now - timedelta(hours=1)).replace(microsecond=0)
        items = [
            {"dateTime": t0.isoformat().replace("+00:00", "Z"), "value": 1.0, "qualifier": "Sample"},
            {"dateTime": t1.isoformat().replace("+00:00", "Z"), "value": 2.0, "qualifier": "Sample"},
            {"dateTime": t2.isoformat().replace("+00:00", "Z"), "value": 3.0, "qualifier": "Sample"},
        ]
        with gzip.open(self.fpath, "wt") as f:
            for it in items:
                f.write(json.dumps(it) + "\n")

    def tearDown(self):
        try:
            os.remove(self.fpath)
        except Exception:
            pass

    def test_measurements_raw_returns_series(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        frm = (now - timedelta(hours=4)).isoformat().replace("+00:00", "Z")
        to = now.isoformat().replace("+00:00", "Z")
        client = TestClient(app)
        r = client.get("/v1/measurements", params={"measure_id": self.measure_id, "from": frm, "to": to, "aggregate": "raw", "limit": 100})
        self.assertEqual(r.status_code, 200, msg=f"status={r.status_code} body={r.text}")
        body = r.json()
        series = body.get("series") or []
        self.assertGreaterEqual(len(series), 3)
        # check ordering and values
        values = [pt["value"] for pt in series]
        self.assertEqual(values, sorted(values))

    def test_measurements_hourly_aggregates(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        frm = (now - timedelta(hours=4)).isoformat().replace("+00:00", "Z")
        to = now.isoformat().replace("+00:00", "Z")
        client = TestClient(app)
        r = client.get("/v1/measurements", params={"measure_id": self.measure_id, "from": frm, "to": to, "aggregate": "hour", "limit": 100})
        self.assertEqual(r.status_code, 200, msg=f"status={r.status_code} body={r.text}")
        body = r.json()
        series = body.get("series") or []
        self.assertGreaterEqual(len(series), 1)
        # values should be averages per hour bucket
        self.assertTrue(all("agg" in pt and pt["agg"] == "hour" for pt in series))


if __name__ == "__main__":
    unittest.main()
