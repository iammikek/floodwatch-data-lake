import unittest
import os
from fastapi.testclient import TestClient
from api.main import app
from api.services import polygons as poly_mod


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200
    def raise_for_status(self):
        return None
    def json(self):
        return self._payload


class _FakeHTTPXClient:
    def __init__(self, timeout=None, headers=None):
        self.timeout = timeout
        self.headers = headers
    def get(self, url, params=None):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"id": "f1"},
                    "geometry": {"type": "Polygon", "coordinates": [[[-3.80, 50.95], [-3.80, 51.05], [-3.70, 51.05], [-3.70, 50.95], [-3.80, 50.95]]]},
                }
            ],
        }
        return _FakeResp(fc)


class ApiPolygonsRemoteTests(unittest.TestCase):
    def setUp(self):
        self._orig_client = poly_mod.httpx.Client
        poly_mod.httpx.Client = _FakeHTTPXClient
        os.environ["REMOTE_BASE_URL"] = "https://cdn.example.com"
        if os.path.exists(os.path.join("data", "curated", "ea", "SOM_fz2_3_simplified.geojson")):
            try:
                os.remove(os.path.join("data", "curated", "ea", "SOM_fz2_3_simplified.geojson"))
            except Exception:
                pass

    def tearDown(self):
        poly_mod.httpx.Client = self._orig_client
        os.environ.pop("REMOTE_BASE_URL", None)

    def test_polygons_inline_remote_fallback_returns_features(self):
        client = TestClient(app)
        params = {
            "dataset": "flood_zones",
            "region": "SOM",
            "format": "simplified",
            "inline": True,
            "bbox": "-3.90,50.90,-3.60,51.10",
        }
        r = client.get("/v1/polygons", params=params)
        self.assertEqual(r.status_code, 200, msg=f"status={r.status_code} body={r.text}")
        body = r.json()
        data = body.get("data") or {}
        feats = data.get("features") or []
        self.assertGreaterEqual(len(feats), 1)
        self.assertIn("ETag", r.headers)
        self.assertIn("Cache-Control", r.headers)
        self.assertIn("X-RateLimit-Limit", r.headers)
        self.assertIn("X-RateLimit-Remaining", r.headers)
        self.assertIn("X-RateLimit-Reset", r.headers)

