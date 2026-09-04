import unittest

from ingestion.clients.hydrology import HydrologyClient


class HydrologyClientTests(unittest.TestCase):
    def test_to_flood_monitoring_shape_skips_missing_values(self):
        items = [
            {"dateTime": "2020-02-01T00:00:00", "value": 1.2, "@id": "a"},
            {"dateTime": "2020-02-01T00:15:00", "value": None, "@id": "b"},
            {"date": "2020-02-01", "value": 1.3, "@id": "c", "quality": "Unchecked"},
        ]
        out = HydrologyClient.to_flood_monitoring_shape(
            items, "52245-level-stage-i-15_min-m"
        )
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["measure"], "52245-level-stage-i-15_min-m")
        self.assertEqual(out[0]["provenance"], "ea_hydrology_archive")
        self.assertEqual(out[1]["quality"], "Unchecked")


if __name__ == "__main__":
    unittest.main()
