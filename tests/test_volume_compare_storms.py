"""Tests for lake-owned History volume-compare storm membership."""

from __future__ import annotations

import unittest

from api.config.storms import get_storm, list_volume_compare_storms
from fastapi.testclient import TestClient

from api.main import app


class VolumeCompareStormsTests(unittest.TestCase):
    def test_golden_four_flagged_and_ordered(self):
        rows = list_volume_compare_storms("a361-muchelney")
        ids = [s["id"] for s in rows]
        self.assertEqual(
            ids,
            [
                "place-2026-01-chandra-levels",
                "eval-2020-02",
                "eval-2014-01",
                "place-2020-02-ciara",
            ],
        )
        for storm in rows:
            self.assertTrue(storm["volume_compare"])
            self.assertIsInstance(storm["volume_compare_rank"], int)

    def test_control_and_wet_spells_excluded(self):
        self.assertFalse(get_storm("eval-stable-summer")["volume_compare"])
        self.assertFalse(get_storm("place-2019-11")["volume_compare"])
        self.assertNotIn(
            "place-2014-01-onset",
            [s["id"] for s in list_volume_compare_storms("a361-muchelney")],
        )

    def test_storms_endpoint_volume_compare_filter(self):
        client = TestClient(app)
        res = client.get(
            "/v1/storms",
            params={"corridor": "a361-muchelney", "volume_compare": "true"},
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        ids = [s["id"] for s in body["storms"]]
        self.assertEqual(ids[0], "place-2026-01-chandra-levels")
        self.assertEqual(len(ids), 4)
        self.assertTrue(all(s.get("volume_compare") for s in body["storms"]))


if __name__ == "__main__":
    unittest.main()
