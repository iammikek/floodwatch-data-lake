import os
import gzip
import json
import tempfile
import unittest
from types import SimpleNamespace
from ingestion import cli as ingestion_cli


class CliReadingsMonthTests(unittest.TestCase):
    def test_writes_expected_gz_lines(self):
        class _FakeEA:
            def get_readings(self, measure_id, since=None, until=None, sorted_flag=True):
                assert since == "2026-01-01" and until == "2026-01-31"
                return [
                    {"@id": "1", "dateTime": "2026-01-01T00:00:00Z", "value": 1.0, "measure": measure_id},
                    {"@id": "2", "dateTime": "2026-01-01T00:15:00Z", "value": 2.0, "measure": measure_id},
                ]

        original = ingestion_cli.EAClient
        try:
            ingestion_cli.EAClient = lambda: _FakeEA()  # type: ignore
            with tempfile.TemporaryDirectory() as td:
                out_path = os.path.join(td, "slice.ndjson.gz")
                args = SimpleNamespace(measure="MEASURE-XYZ", year=2026, month=1, out=out_path)
                ingestion_cli.cmd_fetch_ea_readings_month(args)
                self.assertTrue(os.path.exists(out_path))
                with gzip.open(out_path, "rt") as f:
                    rows = [json.loads(l) for l in f]
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0]["measure"], "MEASURE-XYZ")
        finally:
            ingestion_cli.EAClient = original  # type: ignore


if __name__ == "__main__":
    unittest.main()
