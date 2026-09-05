import unittest

from fastapi.testclient import TestClient

from api.main import app
from api.utils.cache import clear_rate_limit
import api.routes.predictions as predictions_route


class PredictionsApiTests(unittest.TestCase):
    def setUp(self):
        clear_rate_limit()
        self.client = TestClient(app)

    def test_list_corridors(self):
        r = self.client.get("/v1/predictions/corridors")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("corridors", body)
        self.assertIsInstance(body["corridors"], list)
        ids = [c["id"] for c in body["corridors"]]
        self.assertIn("a361-muchelney", ids)
        self.assertEqual(body["corridors"][0]["region"], "SOM")

    def test_unknown_corridor_404(self):
        r = self.client.get("/v1/predictions", params={"corridor": "no-such"})
        self.assertEqual(r.status_code, 404)

    def test_prediction_ok_with_stubbed_service(self):
        def fake_predict(corridor, history_days=120, now=None):
            return {
                "schema": "floodwatch.prediction.v1",
                "corridor": {"id": corridor, "label": "test"},
                "as_of": (now.isoformat().replace("+00:00", "Z") if now else "2026-01-01T00:00:00Z"),
                "prediction": {
                    "verdict": "clear",
                    "verdictLabel": "No predicted impact in window",
                    "timeToImpactHours": None,
                    "impactWindow": None,
                    "confidence": 0.5,
                    "confidenceLabel": "Medium",
                    "summary": "stub",
                },
                "drivers": [
                    {
                        "type": "historic_analogue",
                        "ref": "2020-02-16T00:00:00Z",
                        "label": "Storm Dennis analogue",
                        "similarity": 0.88,
                        "outcome": "impact",
                        "timeToImpactHours": 6,
                    }
                ],
                "affectedAreas": [],
                "dispatch": {"implication": "ok", "safeToPass": True},
                "method": {
                    "name": "historic_analogue_v1",
                    "inputs": [],
                    "parameters": {"windowHours": 24, "historyDays": 120, "topK": 20, "minSimilarity": 0.85},
                    "notes": "",
                },
                "observables": {"gaugeSeries": {}},
            }

        original = predictions_route.predict_corridor
        predictions_route.predict_corridor = fake_predict
        try:
            r = self.client.get(
                "/v1/predictions",
                params={"corridor": "a361-muchelney"},
            )
            body = r.json()
            self.assertEqual(r.status_code, 200)
            self.assertEqual(body["schema"], "floodwatch.prediction.v1")
            self.assertEqual(body["prediction"]["verdict"], "clear")
            self.assertEqual(body["method"]["name"], "historic_analogue_v1")
            self.assertIn("drivers", body)
            self.assertIn("dispatch", body)
            self.assertIn("observables", body)
            self.assertIn("parameters", body["method"])
            self.assertEqual(body["drivers"][0]["type"], "historic_analogue")

            r2 = self.client.get(
                "/v1/predictions",
                params={
                    "corridor": "a361-muchelney",
                    "as_of": "2020-02-16T12:00:00Z",
                },
            )
            self.assertEqual(r2.status_code, 200)
            self.assertTrue(str(r2.json().get("as_of", "")).startswith("2020-02-16"))
        finally:
            predictions_route.predict_corridor = original

    def test_storms_catalogue(self):
        r = self.client.get("/v1/storms", params={"corridor": "a361-muchelney"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("storms", body)
        ids = [s["id"] for s in body["storms"]]
        self.assertIn("eval-2020-02", ids)
        self.assertIn("place-2020-02-ciara", ids)
        self.assertGreaterEqual(len(ids), 6)
        detail = self.client.get("/v1/storms/eval-2020-02")
        self.assertEqual(detail.status_code, 200)
        body = detail.json()
        self.assertEqual(body["label"], "Storm Dennis (Feb 2020)")
        self.assertEqual(body.get("kind"), "named_storm")
        self.assertTrue(body.get("impact_summary"))
        self.assertEqual(body.get("bounds_mode"), "impact")
        geom = body.get("impact_geometry") or {}
        self.assertEqual(geom.get("type"), "FeatureCollection")
        self.assertEqual(len(geom.get("features") or []), 1)
        self.assertEqual(geom["features"][0]["geometry"]["type"], "Polygon")
        self.assertIsInstance(body.get("impact_bbox"), list)
        missing = self.client.get("/v1/storms/nope")
        self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()
