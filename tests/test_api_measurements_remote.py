import unittest
import os
import gzip
import io
import json
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from api.main import app
from api.services import measurements as meas_mod


class _FakeResp:
    def __init__(self, content: bytes):
        self.status_code = 200
        self.content = content
    def raise_for_status(self):
        return None


class _FakeHTTPXClient:
    def __init__(self, timeout=None, headers=None):
        self.timeout = timeout
        self.headers = headers
        self.urls = []
    def get(self, url, params=None):
        self.urls.append(url)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        items = [
            {"dateTime": (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z"), "value": 1.0},
            {"dateTime": (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"), "value": 2.0},
        ]
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as gf:
            for it in items:
                line = (json.dumps(it) + "\n").encode("utf-8")
                gf.write(line)
        return _FakeResp(buf.getvalue())


class ApiMeasurementsRemoteTests(unittest.TestCase):
    def setUp(self):
        self._orig_client = meas_mod.httpx.Client
        meas_mod.httpx.Client = _FakeHTTPXClient
        os.environ["REMOTE_BASE_URL"] = "https://cdn.example.com"
        self.measure_id = "REMOTE_TEST"
        self.dirpath = os.path.join("data", "raw", "ea", "readings", self.measure_id)
        try:
            if os.path.exists(self.dirpath):
                for f in os.listdir(self.dirpath):
                    try:
                        os.remove(os.path.join(self.dirpath, f))
                    except Exception:
                        pass
        except Exception:
            pass

    def tearDown(self):
        meas_mod.httpx.Client = self._orig_client
        os.environ.pop("REMOTE_BASE_URL", None)

    def test_measurements_reads_remote_ndjson_when_local_missing(self):
        client = TestClient(app)
        r = client.get("/v1/measurements", params={"measure_id": self.measure_id})
        self.assertEqual(r.status_code, 200, msg=f"status={r.status_code} body={r.text}")
        body = r.json()
        series = body.get("series") or []
        self.assertGreaterEqual(len(series), 2)
        self.assertIn("ETag", r.headers)
        self.assertIn("Cache-Control", r.headers)
        self.assertIn("X-RateLimit-Limit", r.headers)
        self.assertIn("X-RateLimit-Remaining", r.headers)
        self.assertIn("X-RateLimit-Reset", r.headers)

