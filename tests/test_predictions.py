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
            analogues = {
                "52119-level-stage-i-15_min-mASD": [1.05, 1.1, 1.2, 1.3, 1.42, 1.55],
                "52153-level-stage-i-15_min-mASD": [0.92, 0.96, 1.02, 1.08, 1.16, 1.24],
                "52245-level-stage-i-15_min-m": [0.84, 0.88, 0.95, 1.02, 1.1, 1.18],
                "52230-level-stage-i-15_min-m": [0.75, 0.79, 0.84, 0.9, 0.97, 1.05],
            }
            outcome_tail = [1.8, 1.92, 2.05, 2.2, 2.3, 2.42]
            tail = analogues[measure_id]
            history = [1.0] * 48 + tail + outcome_tail + [0.95] * 24 + tail
            return _pts(history, start)

        doc = predict_corridor(
            "a361-muchelney",
            history_days=30,
            now=now,
            series_loader=loader,
        )
        self.assertEqual(doc["schema"], "floodwatch.prediction.v1")
        self.assertEqual(doc["corridor"]["id"], "a361-muchelney")
        self.assertIn(doc["prediction"]["verdict"], ("watch", "at_risk", "clear"))
        self.assertTrue(doc["drivers"])
        self.assertIn("gaugeSeries", doc["observables"])
        self.assertIn("gauge-gaw-bridge", doc["observables"]["gaugeSeries"])
        self.assertEqual(doc["method"]["name"], "historic_analogue_v1")
        self.assertTrue(any(d["type"] == "analogue_consensus" for d in doc["drivers"]))

    def test_predict_corridor_clear_when_no_good_matches(self):
        start = datetime(2026, 6, 1, tzinfo=timezone.utc)
        now = start + timedelta(hours=100)

        def loader(measure_id, from_, to, aggregate="hour"):
            history = [1.0] * 96 + [1.6, 1.72, 1.84, 1.95, 2.08, 2.2, 2.28, 2.34]
            return _pts(history, start)

        doc = predict_corridor("a361-muchelney", history_days=30, now=now, series_loader=loader)
        self.assertEqual(doc["prediction"]["verdict"], "clear")
        self.assertEqual(doc["prediction"]["timeToImpactHours"], None)
        self.assertEqual(doc["dispatch"]["safeToPass"], True)

    def test_predict_corridor_returns_analogue_drivers_when_matches_exist(self):
        start = datetime(2026, 6, 1, tzinfo=timezone.utc)
        now = start + timedelta(hours=100)

        def loader(measure_id, from_, to, aggregate="hour"):
            current_patterns = {
                "52119-level-stage-i-15_min-mASD": [1.0] * 18 + [1.02, 1.05, 1.1, 1.16, 1.22, 1.28],
                "52153-level-stage-i-15_min-mASD": [0.92] * 18 + [0.95, 0.98, 1.01, 1.05, 1.08, 1.11],
                "52245-level-stage-i-15_min-m": [0.85] * 18 + [0.87, 0.9, 0.94, 0.98, 1.01, 1.04],
                "52230-level-stage-i-15_min-m": [0.75] * 18 + [0.77, 0.8, 0.83, 0.86, 0.89, 0.92],
            }
            if measure_id == "52119-level-stage-i-15_min-mASD":
                history = (
                    [1.0] * 36
                    + current_patterns[measure_id]
                    + [1.36, 1.4, 1.44, 1.47, 1.49, 1.5]
                    + [0.98] * 18
                    + current_patterns[measure_id]
                    + [1.62, 1.74, 1.88, 1.96, 2.04, 2.12]
                    + [0.96] * 18
                    + current_patterns[measure_id]
                )
            else:
                history = (
                    [0.9] * 36
                    + current_patterns[measure_id]
                    + [1.0] * 18
                    + current_patterns[measure_id]
                    + [1.12] * 18
                    + current_patterns[measure_id]
                )
            return _pts(history, start)

        doc = predict_corridor("a361-muchelney", history_days=30, now=now, series_loader=loader)
        self.assertIn(doc["prediction"]["verdict"], ("watch", "at_risk"))
        self.assertFalse(doc["dispatch"]["safeToPass"])
        self.assertTrue(any(d["type"] == "historic_analogue" for d in doc["drivers"]))

    def test_predict_skips_optional_gauge_without_series(self):
        start = datetime(2026, 6, 1, tzinfo=timezone.utc)
        now = start + timedelta(hours=100)

        def loader(measure_id, from_, to, aggregate="hour"):
            if measure_id == "52153-level-stage-i-15_min-mASD":
                return []
            current_patterns = {
                "52119-level-stage-i-15_min-mASD": [1.0] * 18 + [1.02, 1.05, 1.1, 1.16, 1.22, 1.28],
                "52245-level-stage-i-15_min-m": [0.85] * 18 + [0.87, 0.9, 0.94, 0.98, 1.01, 1.04],
                "52230-level-stage-i-15_min-m": [0.75] * 18 + [0.77, 0.8, 0.83, 0.86, 0.89, 0.92],
            }
            pattern = current_patterns[measure_id]
            if measure_id == "52119-level-stage-i-15_min-mASD":
                history = (
                    [1.0] * 36
                    + pattern
                    + [1.36, 1.4, 1.44, 1.47, 1.49, 1.5]
                    + [0.98] * 18
                    + pattern
                    + [1.62, 1.74, 1.88, 1.96, 2.04, 2.12]
                    + [0.96] * 18
                    + pattern
                )
            else:
                history = (
                    [0.9] * 36
                    + pattern
                    + [1.0] * 18
                    + pattern
                    + [1.12] * 18
                    + pattern
                )
            return _pts(history, start)

        doc = predict_corridor("a361-muchelney", history_days=30, now=now, series_loader=loader)
        self.assertEqual(doc["method"]["parameters"]["activeGauges"], 3)
        self.assertTrue(any(d["type"] == "historic_analogue" for d in doc["drivers"]))
        midelney = next(d for d in doc["drivers"] if d.get("ref") == "52153-level-stage-i-15_min-mASD")
        self.assertEqual(midelney["signal"], "no_data")

    def test_unknown_corridor(self):
        with self.assertRaises(KeyError):
            predict_corridor("nope", series_loader=lambda *a, **k: [])


if __name__ == "__main__":
    unittest.main()
