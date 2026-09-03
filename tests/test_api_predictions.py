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
        ids = [c["id"] for c in r.json()["corridors"]]
        self.assertIn("a361-muchelney", ids)

    def test_unknown_corridor_404(self):
        r = self.client.get("/v1/predictions", params={"corridor": "no-such"})
        self.assertEqual(r.status_code, 404)

    def test_prediction_ok_with_stubbed_service(self):
        def fake_predict(corridor, history_days=120):
            return {
                "schema": "floodwatch.prediction.v1",
                "corridor": {"id": corridor, "label": "test"},
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
                "method": {"name": "historic_analogue_v1", "inputs": [], "notes": ""},
                "observables": {"gaugeSeries": {}},
            }

        original = predictions_route.predict_corridor
        predictions_route.predict_corridor = fake_predict
        try:
            r = self.client.get(
                "/v1/predictions",
                params={"corridor": "a361-muchelney"},
            )
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["schema"], "floodwatch.prediction.v1")
            self.assertEqual(r.json()["prediction"]["verdict"], "clear")
            self.assertEqual(r.json()["method"]["name"], "historic_analogue_v1")
        finally:
            predictions_route.predict_corridor = original


if __name__ == "__main__":
    unittest.main()
