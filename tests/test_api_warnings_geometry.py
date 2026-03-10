import unittest
import os
import json
from fastapi.testclient import TestClient
from api.main import app
from api.deps import get_ea_client
from api.utils.cache import clear_rate_limit, clear_cache
from api.services.warnings import clear_flood_areas_cache


class FakeEAClient:
    def get_floods(self, min_severity=None, county=None, lat=None, lon=None, dist_km=None):
        return [
            {
                "@id": "flood-geom-1",
                "severityLevel": 3,
                "severity": "Flood Alert",
                "description": "Possible flooding expected",
                "timeRaised": "2024-01-01T00:00:00Z",
                "timeSeverityChanged": "2024-01-01T01:00:00Z",
                "floodAreaID": "area-1",
                "eaAreaName": "Test Area",
            }
        ]


class ApiWarningsGeometryTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_ea_client] = lambda: FakeEAClient()
        clear_rate_limit()
        clear_cache()
        clear_flood_areas_cache()
        os.makedirs(os.path.join("data", "raw", "ea", "flood_areas"), exist_ok=True)
        path = os.path.join("data", "raw", "ea", "flood_areas", "SOM.geojson")
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"id": "area-1", "eaAreaName": "Test Area"},
                    "geometry": {"type": "Polygon", "coordinates": [[[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]]]},
                }
            ],
        }
        with open(path, "w") as f:
            json.dump(fc, f)

    def tearDown(self):
        app.dependency_overrides.clear()
        try:
            os.remove(os.path.join("data", "raw", "ea", "flood_areas", "SOM.geojson"))
        except Exception:
            pass

    def test_warnings_geometry_present(self):
        client = TestClient(app)
        r = client.get("/v1/warnings", params={"region": "SOM"})
        self.assertEqual(r.status_code, 200, msg=f"status={r.status_code} body={r.text}")
        body = r.json()
        items = body.get("items") or []
        self.assertGreaterEqual(len(items), 1)
        geom = items[0].get("geometry")
        self.assertIsNotNone(geom)
