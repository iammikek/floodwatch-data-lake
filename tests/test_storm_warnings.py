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

    def test_storm_enrichment_includes_warning_evidence(self):
        storm = get_storm("place-2026-01-chandra-levels")
        self.assertIsNotNone(storm)
        assert storm is not None
        ev = storm.get("warning_evidence")
        self.assertIsInstance(ev, dict)
        self.assertEqual(ev["schema"], "floodwatch.storm_warning_evidence.v0")
        summer = get_storm("eval-stable-summer")
        self.assertIsNone(summer.get("warning_evidence"))

    def test_api_storm_warnings(self):
        r = self.client.get("/v1/storms/place-2026-01-chandra-levels/warnings")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["available"])
        self.assertGreaterEqual(len(body["items"]), 5)

    def test_api_storm_without_evidence(self):
        r = self.client.get("/v1/storms/eval-stable-summer/warnings")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body["available"])
        self.assertEqual(body["items"], [])

    def test_known_ids(self):
        self.assertIn("place-2026-01-chandra-levels", known_warning_storm_ids())


if __name__ == "__main__":
    unittest.main()
