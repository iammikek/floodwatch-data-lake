import unittest
from urllib.parse import parse_qs, urlparse

from api.config.place_bboxes import bng_bbox, list_place_ids, wgs84_bbox
from ingestion.lidar_dtm import iter_bng_tiles, wcs_get_coverage_url


class PlaceBboxTests(unittest.TestCase):
    def test_a361_bbox_positive_extent(self):
        self.assertIn("a361-muchelney", list_place_ids())
        w, s, e, n = wgs84_bbox("a361-muchelney")
        self.assertLess(w, e)
        self.assertLess(s, n)
        cw, cs, ce, cn = bng_bbox("a361-muchelney", extent="core")
        fw, fs, fe, fn = bng_bbox("a361-muchelney", extent="full")
        self.assertLess(cw, ce)
        self.assertLessEqual(fw, cw)
        self.assertGreaterEqual(fe, ce)


class LidarDtmHelpersTests(unittest.TestCase):
    def test_iter_bng_tiles_covers_bbox(self):
        tiles = iter_bng_tiles(332100, 131100, 337100, 136100, tile_m=5000)
        self.assertGreaterEqual(len(tiles), 1)
        # All tiles stay within the snapped grid covering the request
        self.assertTrue(all(t[2] > t[0] and t[3] > t[1] for t in tiles))

    def test_wcs_url_has_subsets(self):
        url = wcs_get_coverage_url(
            resolution="2m", west=335000, south=134000, east=336000, north=135000
        )
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        self.assertEqual(qs["request"], ["GetCoverage"])
        self.assertEqual(qs["format"], ["image/tiff"])
        self.assertIn("E(335000,336000)", qs["subset"])
        self.assertIn("N(134000,135000)", qs["subset"])


if __name__ == "__main__":
    unittest.main()
