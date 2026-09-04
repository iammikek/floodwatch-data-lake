"""Real-data storm replay validation.

Runs predict_corridor as-of curated storm timestamps against on-disk EA readings.
Skips when archive coverage is insufficient (common until hydrology backfill lands).
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from api.config.storms import list_storms
from ingestion.corridor_backfill import coverage_report


def _storm_month(as_of: str) -> str:
    return as_of[:7]


class RealStormReplayTests(unittest.TestCase):
    """Optional real-archive acceptance for curated storms."""

    def test_catalogue_storms_have_as_of(self):
        storms = list_storms("a361-muchelney")
        self.assertGreaterEqual(len(storms), 3)
        for storm in storms:
            self.assertTrue(storm.get("as_of"))
            self.assertTrue(storm.get("id"))

    def test_replay_storm_dennis_when_archive_present(self):
        from api.services.predictions import predict_corridor

        storm = next(s for s in list_storms("a361-muchelney") if s["id"] == "eval-2020-02")
        report = coverage_report("a361-muchelney", "2019-12", "2020-02")
        if report["total_present_files"] < 1:
            self.skipTest(
                "No archive readings for Storm Dennis window; "
                "run backfill-ea-hydrology-corridor / flood-monitoring backfill first"
            )
        now = datetime.fromisoformat(storm["as_of"].replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
        doc = predict_corridor("a361-muchelney", history_days=120, now=now)
        self.assertEqual(doc["schema"], "floodwatch.prediction.v1")
        self.assertIn(doc["prediction"]["verdict"], {
            "clear",
            "watch",
            "at_risk",
            "likely_impassable",
            "no_data",
        })
        # Soft assertion: once Gaw Bridge archive exists, expect non-no_data.
        primary_months = next(
            (
                m["present_months"]
                for m in report["measures"]
                if m["measure_id"] == "52119-level-stage-i-15_min-mASD"
            ),
            0,
        )
        if primary_months > 0:
            self.assertNotEqual(
                doc["prediction"]["verdict"],
                "no_data",
                f"Expected a real verdict for {storm['id']} when primary gauge has data",
            )


if __name__ == "__main__":
    unittest.main()
