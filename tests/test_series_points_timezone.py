import unittest
from datetime import datetime, timezone

from api.services.measurements import series_points


class SeriesPointsTimezoneTests(unittest.TestCase):
    def test_naive_hydrology_timestamps_compare_against_aware_window(self):
        items = [
            {"dateTime": "2020-02-16T11:00:00", "value": 1.2},
            {"dateTime": "2020-02-16T13:00:00Z", "value": 1.3},
            {"dateTime": "2020-02-16T15:00:00", "value": 1.4},
        ]
        from_ = datetime(2020, 2, 16, 12, 0, tzinfo=timezone.utc)
        to = datetime(2020, 2, 16, 14, 0, tzinfo=timezone.utc)
        pts = series_points(items, from_, to)
        self.assertEqual(len(pts), 1)
        self.assertEqual(pts[0].value, 1.3)
        self.assertIsNotNone(pts[0].t.tzinfo)


if __name__ == "__main__":
    unittest.main()
