import unittest
from fastapi.testclient import TestClient
from api.main import app
from api.deps import get_ea_client
from api.utils.cache import clear_rate_limit, clear_cache

class DummyEAClient:
    def get_floods(self, min_severity=None, county=None, lat=None, lon=None, dist_km=None):
        return [
            {
                "@id": "flood-1",
                "severityLevel": min_severity or 3,
                "severity": "Flood Alert",
                "description": "Test flood",
                "timeRaised": "2024-01-01T00:00:00Z",
                "timeSeverityChanged": "2024-01-01T01:00:00Z",
            }
        ]


class ApiHeadersETagTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_ea_client] = lambda: DummyEAClient()
        clear_rate_limit()
        clear_cache()

    def tearDown(self):
        app.dependency_overrides.clear()
    def test_warnings_etag_present(self):
        client = TestClient(app)
        r = client.get("/v1/warnings", params={"region": "SOM", "min_severity": 3})
        self.assertEqual(r.status_code, 200)
        self.assertIn("ETag", r.headers)
        self.assertIn("Cache-Control", r.headers)
        self.assertTrue(r.headers["ETag"])
        self.assertTrue(r.headers["Cache-Control"])
        self.assertIn("X-RateLimit-Limit", r.headers)
        self.assertIn("X-RateLimit-Remaining", r.headers)
        self.assertIn("X-RateLimit-Reset", r.headers)

    def test_polygons_inline_etag_present(self):
        client = TestClient(app)
        r = client.get(
            "/v1/polygons",
            params={
                "dataset": "flood_zones",
                "region": "SOM",
                "format": "simplified",
                "inline": True,
                "bbox": "-3.90,50.90,-3.80,51.00",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("ETag", r.headers)
        self.assertIn("Cache-Control", r.headers)
        self.assertTrue(r.headers["ETag"])
        self.assertTrue(r.headers["Cache-Control"])
        self.assertIn("X-RateLimit-Limit", r.headers)
        self.assertIn("X-RateLimit-Remaining", r.headers)
        self.assertIn("X-RateLimit-Reset", r.headers)

    def test_polygons_tile_etag_present(self):
        client = TestClient(app)
        r = client.get(
            "/v1/polygons/tiles/flood_zones/10/511/340",
            params={"region": "SOM", "format": "simplified"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("ETag", r.headers)
        self.assertIn("Cache-Control", r.headers)
        self.assertTrue(r.headers["ETag"])
        self.assertTrue(r.headers["Cache-Control"])
        self.assertIn("X-RateLimit-Limit", r.headers)
        self.assertIn("X-RateLimit-Remaining", r.headers)
        self.assertIn("X-RateLimit-Reset", r.headers)
