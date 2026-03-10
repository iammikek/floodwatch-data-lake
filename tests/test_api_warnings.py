import unittest
from fastapi.testclient import TestClient
from api.main import app
from api.deps import get_ea_client
from api.utils.cache import clear_rate_limit


class FakeEAClient:
    def get_floods(self, min_severity=None, county=None, lat=None, lon=None, dist_km=None):
        return [
            {
                "@id": "flood-123",
                "severityLevel": 2,
                "severity": "Flood Warning",
                "description": "Flooding expected in low lying areas near river",
                "message": "Act now to protect yourself and property",
                "timeRaised": "2024-01-01T00:00:00Z",
                "timeSeverityChanged": "2024-01-01T01:00:00Z",
            }
        ]


class ApiWarningsTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_ea_client] = lambda: FakeEAClient()
        clear_rate_limit()

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_warnings_basic_shape(self):
        client = TestClient(app)
        r = client.get("/v1/warnings", params={"region": "SOM"})
        self.assertEqual(r.status_code, 200, msg=f"status={r.status_code} body={r.text}")
        body = r.json()
        items = body.get("items") or []
        self.assertGreaterEqual(len(items), 1)
        w = items[0]
        for k in ["id", "severity", "title", "issued_at", "updated_at"]:
            self.assertIn(k, w)
