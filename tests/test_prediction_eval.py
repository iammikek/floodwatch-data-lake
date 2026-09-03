"""Golden evaluation scenarios for prediction v1 (P6).

Each scenario injects synthetic series via ``series_loader`` that mimic the
shape of a known historical EA period.  The test asserts the verdict falls
within the expected band — not an exact match, because the engine is
analogue-based and sensitive to window alignment.

Scenario IDs correspond to the eval table in
``flood-watch/docs/build/11-prediction-v1-analogues.md``.
"""

import unittest
from datetime import datetime, timedelta, timezone
from typing import List

from api.models import SeriesPoint
from api.services.predictions import predict_corridor


def _pts(values: List[float], start: datetime) -> List[SeriesPoint]:
    return [
        SeriesPoint(t=start + timedelta(hours=i), value=v, agg="hour")
        for i, v in enumerate(values)
    ]


# ---------------------------------------------------------------------------
# Helper: build a multi-gauge synthetic series loader
# ---------------------------------------------------------------------------

def _make_loader(
    *,
    primary_history: List[float],
    secondary_history: List[float],
    start: datetime,
):
    """Return a series_loader compatible with predict_corridor.

    primary_history   → used for Gaw Bridge (52119)
    secondary_history → used for the other three gauges (scaled slightly)
    """
    scales = {
        "52119-level-stage-i-15_min-mASD": 1.0,
        "52153-level-stage-i-15_min-mASD": 0.88,
        "52245-level-stage-i-15_min-m": 0.82,
        "52230-level-stage-i-15_min-m": 0.76,
    }

    def loader(measure_id, from_, to, aggregate="hour"):
        scale = scales.get(measure_id, 1.0)
        base = primary_history if measure_id == "52119-level-stage-i-15_min-mASD" else secondary_history
        return _pts([round(v * scale, 4) for v in base], start)

    return loader


class EvalJan2014ParrettRise(unittest.TestCase):
    """eval-2014-01: Jan 2014 Parrett rise → expected at_risk or watch.

    Shape: quiet baseline for ~48h, then a strong multi-day rise with all
    gauges climbing together — mirrors the documented Somerset Levels 2014
    event.  A historic window with similar shape should exist earlier in the
    synthetic series and should itself have led to impact, giving the engine
    material for an at_risk/watch verdict.
    """

    def test_verdict_in_band(self):
        start = datetime(2013, 12, 1, tzinfo=timezone.utc)
        now = start + timedelta(hours=200)

        # First event block (analogue that led to impact)
        analogue_rise = [1.0] * 18 + [1.05, 1.12, 1.22, 1.35, 1.50, 1.65]
        analogue_outcome = [1.82, 1.95, 2.10, 2.22, 2.32, 2.40]  # clearly impact

        # Gap period
        gap = [1.0] * 24

        # Second event block (the "now" window — same shape, engine should match)
        current_rise = [1.0] * 18 + [1.05, 1.12, 1.22, 1.35, 1.50, 1.65]
        # Future outcome the engine doesn't see but the analogue tells it
        future = [1.80, 1.90, 2.02, 2.15, 2.25, 2.35]

        primary = analogue_rise + analogue_outcome + gap + current_rise + future
        secondary = [0.9] * len(analogue_rise) + [1.0] * len(analogue_outcome) + \
                     [0.88] * len(gap) + [0.9] * len(current_rise) + [1.0] * len(future)

        loader = _make_loader(
            primary_history=primary,
            secondary_history=secondary,
            start=start,
        )

        doc = predict_corridor(
            "a361-muchelney",
            history_days=30,
            now=now,
            series_loader=loader,
        )

        self.assertIn(
            doc["prediction"]["verdict"],
            ("at_risk", "watch"),
            f"Expected at_risk or watch for Jan 2014 shape, got {doc['prediction']['verdict']}",
        )
        self.assertFalse(doc["dispatch"]["safeToPass"])


class EvalFeb2020StormDennis(unittest.TestCase):
    """eval-2020-02: Storm Dennis window → expected at_risk.

    Shape: already elevated baseline, then a sharp secondary rise across
    all gauges.  Two prior analogue windows with similar multi-gauge shape
    both led to impact.
    """

    def test_verdict_in_band(self):
        start = datetime(2020, 1, 15, tzinfo=timezone.utc)
        now = start + timedelta(hours=250)

        # Two prior analogue blocks that led to impact
        elevated_rise = [1.2] * 18 + [1.28, 1.38, 1.52, 1.68, 1.82, 1.95]
        impact_tail = [2.10, 2.22, 2.30, 2.35, 2.38, 2.40]
        calm = [1.1] * 24

        # Current window — same elevated-rise shape
        current_rise = [1.2] * 18 + [1.28, 1.38, 1.52, 1.68, 1.82, 1.95]

        primary = (
            elevated_rise + impact_tail + calm
            + elevated_rise + impact_tail + calm
            + current_rise
        )
        secondary = (
            [1.0] * len(elevated_rise) + [1.15] * len(impact_tail) + [0.95] * len(calm)
        ) * 2 + [1.0] * len(current_rise)

        loader = _make_loader(
            primary_history=primary,
            secondary_history=secondary,
            start=start,
        )

        doc = predict_corridor(
            "a361-muchelney",
            history_days=30,
            now=now,
            series_loader=loader,
        )

        self.assertIn(
            doc["prediction"]["verdict"],
            ("at_risk",),
            f"Expected at_risk for Storm Dennis shape, got {doc['prediction']['verdict']}",
        )
        self.assertIsNotNone(doc["prediction"]["timeToImpactHours"])
        self.assertTrue(
            any(d["type"] == "historic_analogue" for d in doc["drivers"]),
            "Expected at least one historic_analogue driver",
        )


class EvalAug2018StableSummer(unittest.TestCase):
    """eval-stable-summer: Aug 2018 low flow → expected clear.

    Shape: gently falling or flat series across all gauges, well below
    disruption thresholds.  No historic window should match a rising
    fingerprint because there isn't one.
    """

    def test_verdict_in_band(self):
        start = datetime(2018, 7, 15, tzinfo=timezone.utc)
        now = start + timedelta(hours=200)

        # Quiet falling history — no rising patterns anywhere
        primary = [0.65 - 0.001 * i for i in range(200)]
        secondary = [0.55 - 0.0008 * i for i in range(200)]

        loader = _make_loader(
            primary_history=primary,
            secondary_history=secondary,
            start=start,
        )

        doc = predict_corridor(
            "a361-muchelney",
            history_days=30,
            now=now,
            series_loader=loader,
        )

        self.assertEqual(
            doc["prediction"]["verdict"],
            "clear",
            f"Expected clear for stable summer, got {doc['prediction']['verdict']}",
        )
        self.assertTrue(doc["dispatch"]["safeToPass"])
        self.assertIsNone(doc["prediction"]["timeToImpactHours"])


class EvalConfidenceMonotonic(unittest.TestCase):
    """Release checklist: confidence should increase as impact rate increases.

    We construct three scenarios with 0%, 50%, and 100% impact rate among
    analogues and verify confidence is monotonically non-decreasing.
    """

    def _build_scenario(self, impact_fraction: float):
        """Build a series where ~impact_fraction of analogue windows led to impact."""
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        now = start + timedelta(hours=300)

        rise = [1.0] * 18 + [1.05, 1.12, 1.22, 1.35, 1.50, 1.65]
        impact_out = [1.82, 1.95, 2.10, 2.22, 2.32, 2.40]
        clear_out = [1.10, 1.05, 1.02, 1.00, 0.98, 0.97]
        gap = [0.95] * 18

        blocks = []
        n_blocks = 4
        n_impact = round(n_blocks * impact_fraction)
        for i in range(n_blocks):
            blocks.extend(rise)
            blocks.extend(impact_out if i < n_impact else clear_out)
            blocks.extend(gap)

        # Current window
        blocks.extend(rise)

        secondary = [0.9] * len(blocks)

        loader = _make_loader(primary_history=blocks, secondary_history=secondary, start=start)
        return predict_corridor("a361-muchelney", history_days=60, now=now, series_loader=loader)

    def test_confidence_increases_with_impact_rate(self):
        doc_clear = self._build_scenario(0.0)
        doc_mixed = self._build_scenario(0.5)
        doc_impact = self._build_scenario(1.0)

        c_clear = doc_clear["prediction"]["confidence"]
        c_mixed = doc_mixed["prediction"]["confidence"]
        c_impact = doc_impact["prediction"]["confidence"]

        # Monotonic: impact >= mixed >= clear (allow equal)
        self.assertGreaterEqual(
            c_impact, c_mixed,
            f"Impact confidence {c_impact} should be >= mixed {c_mixed}",
        )
        self.assertGreaterEqual(
            c_mixed, c_clear,
            f"Mixed confidence {c_mixed} should be >= clear {c_clear}",
        )


if __name__ == "__main__":
    unittest.main()
