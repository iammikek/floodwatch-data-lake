import unittest
import os
import gzip
import json
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from api.main import app


class ApiMeasurementsBboxTests(unittest.TestCase):
    def setUp(self):
        # create stations and measures discovery files
        os.makedirs(os.path.join("data", "raw", "ea", "stations"), exist_ok=True)
        os.makedirs(os.path.join("data", "raw", "ea", "measures"), exist_ok=True)
        self.stations_path = os.path.join("data", "raw", "ea", "stations", "stations_test.ndjson.gz")
        self.measures_path = os.path.join("data", "raw", "ea", "measures", "measures_test.ndjson.gz")
        with gzip.open(self.stations_path, "wt") as f:
            f.write(json.dumps({"notation": "S1", "lat": 51.00, "long": -2.90}) + "\n")
        with gzip.open(self.measures_path, "wt") as f:
            f.write(json.dumps({"notation": "M1", "station": "S1"}) + "\n")
        # create readings for measure M1
        self.measure_id = "M1"
        now = datetime.now(timezone.utc).replace(microsecond=0)
        self.year = now.year
        self.month = now.month
        self.mm = f"{self.year:04d}-{self.month:02d}"
        dirpath = os.path.join("data", "raw", "ea", "readings", self.measure_id)
        os.makedirs(dirpath, exist_ok=True)
        self.readings_path = os.path.join(dirpath, f"{self.mm}.ndjson.gz")
        items = [
            {"dateTime": (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z"), "value": 1.0, "qualifier": "Sample"},
            {"dateTime": (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"), "value": 2.0, "qualifier": "Sample"},
        ]
        with gzip.open(self.readings_path, "wt") as f:
            for it in items:
                f.write(json.dumps(it) + "\n")

    def tearDown(self):
        for p in [self.stations_path, self.measures_path, self.readings_path]:
            try:
                os.remove(p)
            except Exception:
                pass

    def test_measurements_bbox_inside_returns_series(self):
        client = TestClient(app)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        frm = (now - timedelta(hours=4)).isoformat().replace("+00:00", "Z")
        to = now.isoformat().replace("+00:00", "Z")
        bbox = "-3.00,50.90,-2.80,51.10"
        r = client.get("/v1/measurements", params={"measure_id": self.measure_id, "from": frm, "to": to, "aggregate": "raw", "limit": 100, "bbox": bbox})
        self.assertEqual(r.status_code, 200, msg=f"status={r.status_code} body={r.text}")
        body = r.json()
        series = body.get("series") or []
        self.assertGreaterEqual(len(series), 2)
        st = body.get("station") or {}
        self.assertEqual(st.get("id"), "unknown")  # station_id not provided in request
        self.assertIsNotNone(st.get("lat"))
        self.assertIsNotNone(st.get("lng"))

    def test_measurements_bbox_outside_returns_empty(self):
        client = TestClient(app)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        frm = (now - timedelta(hours=4)).isoformat().replace("+00:00", "Z")
        to = now.isoformat().replace("+00:00", "Z")
        bbox = "-4.00,51.50,-3.80,51.60"  # outside
        r = client.get("/v1/measurements", params={"measure_id": self.measure_id, "from": frm, "to": to, "aggregate": "raw", "limit": 100, "bbox": bbox})
        self.assertEqual(r.status_code, 200, msg=f"status={r.status_code} body={r.text}")
        body = r.json()
        series = body.get("series") or []
        self.assertEqual(len(series), 0)
        st = body.get("station") or {}
        self.assertIsNotNone(st.get("lat"))
        self.assertIsNotNone(st.get("lng"))
