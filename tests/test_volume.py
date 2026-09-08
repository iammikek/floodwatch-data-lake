import os
import tempfile
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient

from api.main import app
from api.services.volume import (
    bathtub_from_elevations,
    densify_bng_line,
    estimate_storm_volume,
    resolve_gauge_rise_surface,
)
from api.utils.cache import clear_rate_limit

try:
    import rasterio
    from rasterio.transform import from_origin
except ImportError:  # pragma: no cover
    rasterio = None


class BathtubUnitTests(unittest.TestCase):
    def test_bathtub_stats_on_flat_basin(self):
        elev = np.arange(1.0, 11.0, 1.0)
        stats = bathtub_from_elevations(elev, cell_area_m2=4.0, fill_percentile=70.0)
        self.assertGreater(stats["volumeM3"], 0)
        self.assertEqual(stats["fillPercentile"], 70.0)

    def test_bathtub_with_explicit_surface(self):
        elev = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        stats = bathtub_from_elevations(
            elev, cell_area_m2=4.0, water_surface_m=3.5
        )
        self.assertIsNone(stats["fillPercentile"])
        self.assertEqual(stats["waterSurfaceM"], 3.5)
        self.assertGreater(stats["volumeM3"], 0)

    def test_densify_line_chainage(self):
        pts = densify_bng_line([(0.0, 0.0), (100.0, 0.0)], step_m=25.0)
        self.assertGreaterEqual(len(pts), 5)
        self.assertAlmostEqual(pts[-1][2], 100.0, places=5)

    def test_gauge_rise_surface(self):
        elev = np.array([3.0, 3.5, 4.0, 5.0, 6.0])

        def fake_loader(measure_id, from_, to, aggregate="hour"):
            # Event window peaks higher than baseline
            if from_.year == 2020:
                vals = [7.0, 8.0, 8.2]
            else:
                vals = [6.5, 6.7, 6.8]
            return [SimpleNamespace(value=v, t=from_) for v in vals]

        storm = {
            "corridor": "a361-muchelney",
            "window": {"from": "2020-02-13", "to": "2020-02-20"},
        }
        meta = resolve_gauge_rise_surface(storm, elev, series_loader=fake_loader)
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertEqual(meta["mode"], "gauge_rise")
        self.assertGreater(meta["riseM"], 0)
        self.assertAlmostEqual(
            meta["waterSurfaceM"], meta["demFloorM"] + meta["riseM"], places=5
        )


@unittest.skipUnless(rasterio is not None, "rasterio required")
class VolumeIntegrationTests(unittest.TestCase):
    def setUp(self):
        clear_rate_limit()
        self.client = TestClient(app)

    def _write_flat_tile(self, directory: str, elevation: float = 5.0) -> str:
        path = os.path.join(directory, "dtm2m_E337400-337600_N137400-137600.tif")
        transform = from_origin(337400.0, 137600.0, 2.0, 2.0)
        h, w = 100, 100
        data = np.full((h, w), elevation, dtype=np.float32)
        data[20:80, 20:80] = elevation - 2.0
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=h,
            width=w,
            count=1,
            dtype="float32",
            crs="EPSG:27700",
            transform=transform,
            nodata=-9999.0,
        ) as dst:
            dst.write(data, 1)
        return path

    def test_estimate_with_synthetic_dtm(self):
        with tempfile.TemporaryDirectory() as tmp:
            place_dir = os.path.join(tmp, "a361-muchelney", "dtm-2m")
            os.makedirs(place_dir)
            self._write_flat_tile(place_dir)
            doc = estimate_storm_volume(
                "eval-2020-02",
                place_id="a361-muchelney",
                resolution="2m",
                dtm_root=tmp,
                fill_percentile=70.0,
                include_road=False,
            )
            self.assertEqual(doc["schema"], "floodwatch.storm_volume.v1")
            self.assertEqual(doc["stormId"], "eval-2020-02")
            self.assertIn("method", doc)

    def test_summer_control_unavailable(self):
        doc = estimate_storm_volume("eval-stable-summer")
        self.assertFalse(doc["available"])
        self.assertEqual(doc["reason"], "no_impact_geometry")

    def test_api_unknown_storm_404(self):
        r = self.client.get("/v1/storms/no-such-storm/volume")
        self.assertEqual(r.status_code, 404)

    def test_api_summer_returns_unavailable(self):
        r = self.client.get("/v1/storms/eval-stable-summer/volume")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body["available"])
        self.assertEqual(body["reason"], "no_impact_geometry")

    def test_estimate_overlap_produces_volume(self):
        from pyproj import Transformer

        to_wgs = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
        corners_bng = [
            (337420, 137420),
            (337580, 137420),
            (337580, 137580),
            (337420, 137580),
            (337420, 137420),
        ]
        ring_wgs = [list(to_wgs.transform(e, n)) for e, n in corners_bng]
        fake_storm = {
            "id": "eval-2020-02",
            "label": "Storm Dennis",
            "corridor": "a361-muchelney",
            "severity": "high",
            "bounds_mode": "impact",
            "window": {"from": "2020-02-13", "to": "2020-02-20"},
            "impact_geometry": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {"type": "Polygon", "coordinates": [ring_wgs]},
                    }
                ],
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            place_dir = os.path.join(tmp, "a361-muchelney", "dtm-2m")
            os.makedirs(place_dir)
            self._write_flat_tile(place_dir, elevation=10.0)
            with patch("api.services.volume.get_storm", return_value=fake_storm):
                doc = estimate_storm_volume(
                    "eval-2020-02",
                    place_id="a361-muchelney",
                    dtm_root=tmp,
                    fill_percentile=70.0,
                    include_road=False,
                )
            self.assertTrue(doc["available"], doc)
            pred = doc["prediction"]
            self.assertGreater(pred["volumeM3"], 0)
            self.assertEqual(doc["method"]["mode"], "dem_percentile_fallback")

    def test_gauge_rise_mode_on_synthetic(self):
        from pyproj import Transformer

        to_wgs = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
        corners_bng = [
            (337420, 137420),
            (337580, 137420),
            (337580, 137580),
            (337420, 137580),
            (337420, 137420),
        ]
        ring_wgs = [list(to_wgs.transform(e, n)) for e, n in corners_bng]
        fake_storm = {
            "id": "eval-2020-02",
            "label": "Storm Dennis",
            "corridor": "a361-muchelney",
            "severity": "high",
            "bounds_mode": "impact",
            "window": {"from": "2020-02-13", "to": "2020-02-20"},
            "impact_geometry": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {"type": "Polygon", "coordinates": [ring_wgs]},
                    }
                ],
            },
        }

        def fake_loader(measure_id, from_, to, aggregate="hour"):
            if from_.year == 2020:
                vals = [7.5, 8.0, 8.2]
            else:
                vals = [6.6, 6.7, 6.8]
            return [SimpleNamespace(value=v, t=from_) for v in vals]

        with tempfile.TemporaryDirectory() as tmp:
            place_dir = os.path.join(tmp, "a361-muchelney", "dtm-2m")
            os.makedirs(place_dir)
            self._write_flat_tile(place_dir, elevation=10.0)
            with patch("api.services.volume.get_storm", return_value=fake_storm):
                doc = estimate_storm_volume(
                    "eval-2020-02",
                    place_id="a361-muchelney",
                    dtm_root=tmp,
                    series_loader=fake_loader,
                    include_road=False,
                )
            self.assertTrue(doc["available"], doc)
            self.assertEqual(doc["method"]["mode"], "gauge_rise")
            self.assertEqual(doc["method"]["name"], "bathtub_gauge_rise_v1")
            self.assertIn("gauge", doc["method"])
            self.assertGreater(doc["method"]["gauge"]["riseM"], 0)

    def test_road_samples_include_wgs84(self):
        from api.services.volume import road_depth_summary

        with tempfile.TemporaryDirectory() as tmp:
            # Tile covering A361 Othery approach samples (~E336–340k / N131k)
            place_dir = os.path.join(tmp, "a361-muchelney", "dtm-2m")
            os.makedirs(place_dir)
            path = os.path.join(place_dir, "dtm2m_E335000-341000_N130000-133000.tif")
            transform = from_origin(335000.0, 133000.0, 20.0, 20.0)
            h, w = 150, 300
            data = np.full((h, w), 4.0, dtype=np.float32)
            with rasterio.open(
                path,
                "w",
                driver="GTiff",
                height=h,
                width=w,
                count=1,
                dtype="float32",
                crs="EPSG:27700",
                transform=transform,
                nodata=-9999.0,
            ) as dst:
                dst.write(data, 1)
            road = road_depth_summary(
                "a361-muchelney",
                water_surface_m=5.5,
                tiles=[path],
                step_m=100.0,
            )
            self.assertIsNotNone(road)
            assert road is not None
            self.assertTrue(road["available"], road)
            sample = road["samples"][0]
            self.assertIn("lng", sample)
            self.assertIn("lat", sample)
            self.assertIn("depthM", sample)
            self.assertTrue(-3.0 < sample["lng"] < -2.5)
            self.assertTrue(51.0 < sample["lat"] < 51.2)


if __name__ == "__main__":
    unittest.main()
