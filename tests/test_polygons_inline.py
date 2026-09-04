"""Unit tests for inline flood-zone polygon preparation."""

from __future__ import annotations

import unittest

from api.services.polygons import clip_geometry_to_bbox, prepare_inline_features


class InlinePolygonPrepTests(unittest.TestCase):
    def test_clip_keeps_viewport_vertices(self):
        geom = {
            "type": "Polygon",
            "coordinates": [
                [
                    [-3.5, 50.5],
                    [-2.85, 51.10],
                    [-2.80, 51.10],
                    [-2.80, 51.12],
                    [-2.85, 51.12],
                    [-2.85, 51.10],
                    [-3.5, 50.5],
                ]
            ],
        }
        clipped = clip_geometry_to_bbox(geom, [-2.9, 51.08, -2.75, 51.15], max_points=32)
        self.assertIsNotNone(clipped)
        assert clipped is not None
        ring = clipped["coordinates"][0]
        self.assertGreaterEqual(len(ring), 4)
        self.assertLess(len(ring), 10)

    def test_prepare_prefers_fz3_and_caps(self):
        feats = []
        for i, zone in enumerate(["FZ2", "FZ3", "FZ3", "FZ2"] * 400):
            feats.append(
                {
                    "type": "Feature",
                    "properties": {"id": f"z-{i}", "flood_zone": zone},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-2.86, 51.10],
                                [-2.84, 51.10],
                                [-2.84, 51.11],
                                [-2.86, 51.11],
                                [-2.86, 51.10],
                            ]
                        ],
                    },
                }
            )
        out = prepare_inline_features(feats, [-2.9, 51.08, -2.75, 51.15], max_features=50)
        self.assertEqual(len(out), 50)
        self.assertTrue(all(f["properties"]["flood_zone"] == "FZ3" for f in out[:40]))


if __name__ == "__main__":
    unittest.main()
