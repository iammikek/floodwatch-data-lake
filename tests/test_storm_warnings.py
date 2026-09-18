import unittest

from fastapi.testclient import TestClient

from api.config.storm_warnings import known_warning_storm_ids, warning_evidence_for
from api.config.storms import get_storm
from api.main import app
from api.utils.cache import clear_rate_limit


class StormWarningEvidenceTests(unittest.TestCase):
    def setUp(self):
        clear_rate_limit()
        self.client = TestClient(app)

    def test_chandra_has_afa435_items(self):
        doc = warning_evidence_for("place-2026-01-chandra-levels")
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertGreaterEqual(doc["counts"]["total"], 5)
        self.assertGreaterEqual(doc["counts"]["floodWarning"], 1)
        self.assertGreaterEqual(doc["counts"]["floodAlert"], 1)
        ids = {it["floodAreaID"] for it in doc["items"]}
        self.assertIn("112FWFMTM10A", ids)
        self.assertIn("112WAFYPM", ids)

    def test_dennis_has_corridor_alerts(self):
        doc = warning_evidence_for("eval-2020-02")
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc["counts"]["total"], 4)
        self.assertEqual(doc["counts"]["floodAlert"], 2)
        self.assertEqual(doc["counts"]["floodWarning"], 2)
        ids = {it["floodAreaID"] for it in doc["items"]}
        self.assertIn("112WAFYPM", ids)
        self.assertIn("112FWFCUR10A", ids)

    def test_2014_includes_severe_a361(self):
        doc = warning_evidence_for("eval-2014-01")
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc["counts"]["severeFloodWarning"], 1)
        severe = next(it for it in doc["items"] if it["severityLevel"] == 1)
        self.assertEqual(severe["floodAreaID"], "112FWFEAS10A")
        self.assertEqual(severe["issued_at"][:10], "2014-02-05")

    def test_ciara_curated_but_empty_window(self):
        doc = warning_evidence_for("place-2020-02-ciara")
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc["counts"]["total"], 0)
        self.assertIn("Dennis", doc["notes"])

    def test_storm_enrichment_includes_warning_evidence(self):
        storm = get_storm("place-2026-01-chandra-levels")
        self.assertIsNotNone(storm)
        assert storm is not None
        ev = storm.get("warning_evidence")
        self.assertIsInstance(ev, dict)
        self.assertEqual(ev["schema"], "floodwatch.storm_warning_evidence.v0")
        dennis = get_storm("eval-2020-02")
        assert dennis is not None
        self.assertEqual(len(dennis["warning_evidence"]["items"]), 4)
        summer = get_storm("eval-stable-summer")
        self.assertIsNone(summer.get("warning_evidence"))

    def test_api_storm_warnings(self):
        r = self.client.get("/v1/storms/place-2026-01-chandra-levels/warnings")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["available"])
        self.assertGreaterEqual(len(body["items"]), 5)

    def test_api_ciara_unavailable_with_notes(self):
        r = self.client.get("/v1/storms/place-2020-02-ciara/warnings")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body["available"])
        self.assertEqual(body["reason"], "no_corridor_issues_in_window")
        self.assertEqual(body["items"], [])
        self.assertIn("Dennis", body.get("notes") or "")

    def test_api_storm_without_evidence(self):
        r = self.client.get("/v1/storms/eval-stable-summer/warnings")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body["available"])
        self.assertEqual(body["reason"], "no_warning_evidence")
        self.assertEqual(body["items"], [])

    def test_known_ids(self):
        ids = known_warning_storm_ids()
        self.assertIn("place-2026-01-chandra-levels", ids)
        self.assertIn("eval-2020-02", ids)
        self.assertIn("eval-2014-01", ids)
        self.assertIn("place-2020-02-ciara", ids)


if __name__ == "__main__":
    unittest.main()
