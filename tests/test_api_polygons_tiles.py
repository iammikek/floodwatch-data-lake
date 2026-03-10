import unittest
from fastapi.testclient import TestClient
from api.main import app


class ApiPolygonsTilesTests(unittest.TestCase):
    def test_tile_endpoint_returns_feature_collection(self):
        client = TestClient(app)
        r = client.get("/v1/polygons/tiles/flood_zones/10/511/340", params={"region": "SOM"})
        self.assertEqual(r.status_code, 200, msg=f"status={r.status_code} body={r.text}")
        body = r.json()
        self.assertEqual(body.get("type"), "FeatureCollection")
        self.assertIn("features", body)
        self.assertIsInstance(body["features"], list)


if __name__ == "__main__":
    unittest.main()
