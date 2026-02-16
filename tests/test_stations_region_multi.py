import os
import gzip
import json
import tempfile
import unittest
from types import SimpleNamespace
from ingestion import cli as ingestion_cli


class StationsRegionMultiTests(unittest.TestCase):
    def test_multi_center_dedup(self):
        calls = []

        class _FakeEA:
            def get_stations_near(self, lat, lon, dist, parameter=None):
                calls.append((lat, lon, dist))
                if len(calls) == 1:
                    return [{"notation": "S1"}, {"notation": "S2"}]
                return [{"notation": "S2"}, {"notation": "S3"}]

        original_client = ingestion_cli.EAClient
        try:
            ingestion_cli.EAClient = lambda: _FakeEA()  # type: ignore
            with tempfile.TemporaryDirectory() as td:
                out_path = os.path.join(td, "dorset.ndjson.gz")
                args = SimpleNamespace(region="DOR", parameter=None, out=out_path)
                ingestion_cli.cmd_fetch_ea_stations_region(args)
                with gzip.open(out_path, "rt") as f:
                    items = [json.loads(l) for l in f]
                ids = sorted(i.get("notation") for i in items)
                self.assertEqual(ids, ["S1", "S2", "S3"])
                self.assertGreaterEqual(len(calls), 2)
        finally:
            ingestion_cli.EAClient = original_client  # type: ignore


if __name__ == "__main__":
    unittest.main()

