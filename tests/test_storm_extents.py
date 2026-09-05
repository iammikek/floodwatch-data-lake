import unittest

from api.config.storm_extents import impact_bbox_for, impact_collection, known_extent_ids
from api.config.storms import get_storm, list_storms


class StormExtentsTests(unittest.TestCase):
    def test_impact_storms_have_polygon_geometry(self):
        for storm in list_storms("a361-muchelney"):
            mode = str(storm.get("bounds_mode") or "").lower()
            if mode == "none":
                self.assertIsNone(storm.get("impact_geometry"))
                self.assertIsNone(storm.get("impact_bbox"))
                continue
            geom = storm.get("impact_geometry")
            self.assertIsInstance(geom, dict)
            self.assertEqual(geom.get("type"), "FeatureCollection")
            features = geom.get("features") or []
            self.assertEqual(len(features), 1)
            self.assertEqual(features[0]["geometry"]["type"], "Polygon")
            ring = features[0]["geometry"]["coordinates"][0]
            self.assertGreaterEqual(len(ring), 4)
            self.assertEqual(ring[0], ring[-1])
            bbox = storm.get("impact_bbox")
            self.assertIsInstance(bbox, list)
            self.assertEqual(len(bbox), 4)
            self.assertLess(bbox[0], bbox[2])
            self.assertLess(bbox[1], bbox[3])

    def test_extent_ids_match_catalogue_impact_storms(self):
        impact_ids = {
            s["id"]
            for s in list_storms("a361-muchelney")
            if str(s.get("bounds_mode") or "").lower() == "impact"
        }
        self.assertEqual(impact_ids, set(known_extent_ids()))

    def test_dennis_and_2014_footprints_differ(self):
        a = impact_collection("eval-2014-01")
        b = impact_collection("eval-2020-02")
        self.assertNotEqual(
            a["features"][0]["geometry"]["coordinates"],
            b["features"][0]["geometry"]["coordinates"],
        )
        self.assertNotEqual(impact_bbox_for("eval-2014-01"), impact_bbox_for("eval-2020-02"))

    def test_get_storm_includes_geometry(self):
        storm = get_storm("eval-2020-02")
        self.assertIsNotNone(storm)
        assert storm is not None
        self.assertEqual(storm["impact_geometry"]["features"][0]["properties"]["kind"], "curated_impact_v0")


if __name__ == "__main__":
    unittest.main()
