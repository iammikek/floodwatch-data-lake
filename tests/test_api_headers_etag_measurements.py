import unittest
from fastapi.testclient import TestClient
from api.main import app


class ApiHeadersETagMeasurementsTests(unittest.TestCase):
    def test_measurements_etag_present(self):
        client = TestClient(app)
        r = client.get(
            "/v1/measurements",
            params={
                "measure_id": "TESTMEASURE",
                "from": "2026-03-10T00:00:00Z",
                "to": "2026-03-10T02:00:00Z",
                "aggregate": "raw",
                "limit": 100,
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("ETag", r.headers)
        self.assertIn("Cache-Control", r.headers)
        self.assertTrue(r.headers["ETag"])
        self.assertTrue(r.headers["Cache-Control"])
