import unittest
from datetime import datetime, timedelta, timezone
from typing import List

from api.models import SeriesPoint
from api.services.predictions import analyse_series, predict_corridor


def _pts(values, start: datetime) -> List[SeriesPoint]:
    out = []
    for i, v in enumerate(values):
        out.append(
            SeriesPoint(
                t=start + timedelta(hours=i),
                value=float(v),
                agg="hour",
            )
        )
    return out


class AnalyseSeriesTests(unittest.TestCase):
    def test_rising_toward_high(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # long quiet history then sharp rise
        hist = [1.0] * 80 + [1.1, 1.2, 1.35, 1.5, 1.65, 1.8]
        a = analyse_series(_pts(hist, start))
        self.assertIn(a["signal"], ("rising_toward_high", "elevated_and_rising", "rising"))
        self.assertGreater(a["slope_per_hour"], 0)
        self.assertGreater(a["pct_rank"], 70)

    def test_falling_clear_signal(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        hist = [2.0, 1.9, 1.8, 1.7, 1.6, 1.5, 1.4, 1.3]
        a = analyse_series(_pts(hist, start))
        self.assertEqual(a["signal"], "steady_or_falling")

    def test_empty(self):
        a = analyse_series([])
        self.assertEqual(a["signal"], "no_data")


class PredictCorridorTests(unittest.TestCase):
    def test_predict_uses_loader_and_schema(self):
        start = datetime(2026, 6, 1, tzinfo=timezone.utc)
        now = start + timedelta(hours=100)

        def loader(measure_id, from_, to, aggregate="hour"):
            # Rising series for all measures
            base = [1.0 + i * 0.02 for i in range(90)]
            return _pts(base, start)

        doc = predict_corridor(
            "a361-muchelney",
            history_days=30,
            now=now,
            series_loader=loader,
        )
        self.assertEqual(doc["schema"], "floodwatch.prediction.v0")
        self.assertEqual(doc["corridor"]["id"], "a361-muchelney")
        self.assertIn(doc["prediction"]["verdict"], ("watch", "at_risk", "clear"))
        self.assertTrue(doc["drivers"])
        self.assertIn("gaugeSeries", doc["observables"])
        self.assertIn("gauge-gaw-bridge", doc["observables"]["gaugeSeries"])

    def test_unknown_corridor(self):
        with self.assertRaises(KeyError):
            predict_corridor("nope", series_loader=lambda *a, **k: [])


if __name__ == "__main__":
    unittest.main()
