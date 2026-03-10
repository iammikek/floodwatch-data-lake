import unittest
from fastapi.testclient import TestClient
from api.main import app
from api.utils.cache import set_rate_limit_config, clear_rate_limit


class ApiRateLimitHeadersTests(unittest.TestCase):
    def setUp(self):
        set_rate_limit_config(3, 60)
        clear_rate_limit()

    def test_warnings_rate_limit_headers(self):
        client = TestClient(app)
        r = client.get("/v1/warnings", params={"region": "SOM"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("X-RateLimit-Limit", r.headers)
        self.assertIn("X-RateLimit-Remaining", r.headers)
        self.assertIn("X-RateLimit-Reset", r.headers)
        self.assertEqual(r.headers["X-RateLimit-Limit"], "3")
        self.assertEqual(r.headers["X-RateLimit-Remaining"], "2")
        self.assertTrue(r.headers["X-RateLimit-Reset"].isdigit())

    def test_measurements_rate_limit_headers(self):
        client = TestClient(app)
        r = client.get(
            "/v1/measurements",
            params={"measure_id": "TESTMEASURE", "from": "2026-03-10T00:00:00Z", "to": "2026-03-10T02:00:00Z", "aggregate": "raw", "limit": 10},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("X-RateLimit-Limit", r.headers)
        self.assertIn("X-RateLimit-Remaining", r.headers)
        self.assertIn("X-RateLimit-Reset", r.headers)
        self.assertEqual(r.headers["X-RateLimit-Limit"], "3")
        self.assertTrue(r.headers["X-RateLimit-Remaining"].isdigit())
        self.assertTrue(r.headers["X-RateLimit-Reset"].isdigit())

    def test_polygons_tile_rate_limit_headers(self):
        client = TestClient(app)
        r = client.get("/v1/polygons/tiles/flood_zones/10/511/340", params={"region": "SOM"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("X-RateLimit-Limit", r.headers)
        self.assertIn("X-RateLimit-Remaining", r.headers)
        self.assertIn("X-RateLimit-Reset", r.headers)
        self.assertEqual(r.headers["X-RateLimit-Limit"], "3")
        self.assertTrue(r.headers["X-RateLimit-Remaining"].isdigit())
        self.assertTrue(r.headers["X-RateLimit-Reset"].isdigit())
