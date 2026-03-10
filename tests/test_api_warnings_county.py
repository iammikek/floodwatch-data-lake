import unittest
from fastapi.testclient import TestClient
from api.main import app
from api.deps import get_ea_client
from api.utils.cache import clear_rate_limit, clear_cache


class RecorderEAClient:
    def __init__(self):
        self.calls = []

    def get_floods(self, min_severity=None, county=None, lat=None, lon=None, dist_km=None):
        self.calls.append({"min_severity": min_severity, "county": county, "lat": lat, "lon": lon, "dist_km": dist_km})
        return [
            {
                "@id": "flood-1",
                "severityLevel": min_severity or 3,
                "severity": "Flood Alert" if (min_severity or 3) >= 3 else "Flood Warning",
                "description": "Test flood",
                "timeRaised": "2024-01-01T00:00:00Z",
                "timeSeverityChanged": "2024-01-01T01:00:00Z",
            }
        ]


class ApiWarningsCountyTests(unittest.TestCase):
    def setUp(self):
        self.recorder = RecorderEAClient()
        app.dependency_overrides[get_ea_client] = lambda: self.recorder
        clear_rate_limit()
        clear_cache()

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_warnings_passes_county(self):
        client = TestClient(app)
        r = client.get("/v1/warnings", params={"county": "Somerset", "min_severity": 2})
        self.assertEqual(r.status_code, 200, msg=f"status={r.status_code} body={r.text}")
        body = r.json()
        items = body.get("items") or []
        self.assertGreaterEqual(len(items), 1)
        # assert recorder captured county and min_severity
        self.assertGreaterEqual(len(self.recorder.calls), 1)
        call = self.recorder.calls[-1]
        self.assertEqual(call["county"], "Somerset")
        self.assertEqual(call["min_severity"], 2)
