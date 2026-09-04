import unittest

from api.config.hydrology_measures import HYDROLOGY_MEASURE_MAP, mapped_corridor_measures
from ingestion.corridor_backfill import corridor_measure_ids


class HydrologyMeasureMapTests(unittest.TestCase):
    def test_westonzoyland_is_exact(self):
        m = HYDROLOGY_MEASURE_MAP["52245-level-stage-i-15_min-m"]
        self.assertFalse(m.get("proxy"))
        self.assertIn("0a6e9d80-6de0-4f88-a1ae-8da70cebf95f", m["hydrology_measure_id"])

    def test_gaw_and_great_bow_use_proxies(self):
        gaw = HYDROLOGY_MEASURE_MAP["52119-level-stage-i-15_min-mASD"]
        bow = HYDROLOGY_MEASURE_MAP["52230-level-stage-i-15_min-m"]
        self.assertTrue(gaw["proxy"])
        self.assertTrue(bow["proxy"])
        self.assertEqual(gaw["proxy_for"], "Gaw Bridge")
        self.assertEqual(bow["proxy_for"], "Langport Great Bow")

    def test_midelney_not_mapped_yet(self):
        self.assertNotIn("52153-level-stage-i-15_min-mASD", HYDROLOGY_MEASURE_MAP)

    def test_corridor_mapping_covers_three_of_four(self):
        mapped = mapped_corridor_measures(corridor_measure_ids("a361-muchelney"))
        self.assertEqual(len(mapped), 3)


if __name__ == "__main__":
    unittest.main()
