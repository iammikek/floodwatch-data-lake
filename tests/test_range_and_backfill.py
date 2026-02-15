import os
import gzip
import json
import tempfile
import unittest
from types import SimpleNamespace
from ingestion import cli as ingestion_cli
from ingestion.jobs import slice_runner
from fastapi.testclient import TestClient
from api.main import app


class RangeAndBackfillTests(unittest.TestCase):
    def test_readings_range_writes_two_months(self):
        class _FakeEA:
            def get_readings(self, measure_id, since=None, until=None, sorted_flag=True):
                return [{"@id": "1", "value": 1.0, "measure": measure_id}]

        original = ingestion_cli.EAClient
        try:
            ingestion_cli.EAClient = lambda: _FakeEA()  # type: ignore
            cwd = os.getcwd()
            with tempfile.TemporaryDirectory() as td:
                os.chdir(td)
                args = SimpleNamespace(measure="MEASURE-XYZ", from_month="2026-01", to_month="2026-02")
                ingestion_cli.cmd_fetch_ea_readings_range(args)
                p1 = "data/raw/ea/readings/MEASURE-XYZ/2026-01.ndjson.gz"
                p2 = "data/raw/ea/readings/MEASURE-XYZ/2026-02.ndjson.gz"
                self.assertTrue(os.path.exists(p1))
                self.assertTrue(os.path.exists(p2))
                with gzip.open(p1, "rt") as f:
                    rows = [json.loads(l) for l in f]
                self.assertEqual(len(rows), 1)
        finally:
            ingestion_cli.EAClient = original  # type: ignore
            os.chdir(cwd)

    def test_backfill_region_respects_limits(self):
        calls = []

        class _FakeEA:
            def get_stations(self, bbox=None, parameter=None):
                return [{"notation": "S1"}, {"notation": "S2"}]

            def get_measures(self, station=None, parameter=None):
                return [{"notation": "M1", "parameter": "level"}, {"notation": "M2", "parameter": "flow"}]

        def _stub_range(args):
            calls.append((args.measure, args.from_month, args.to_month))

        original_client = ingestion_cli.EAClient
        original_range = ingestion_cli.cmd_fetch_ea_readings_range
        try:
            ingestion_cli.EAClient = lambda: _FakeEA()  # type: ignore
            ingestion_cli.cmd_fetch_ea_readings_range = _stub_range  # type: ignore
            args = SimpleNamespace(region="SOM", parameters="level,flow", from_month="2026-01", to_month="2026-01", max_stations=1, max_measures=1)
            ingestion_cli.cmd_backfill_ea_region(args)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][1], "2026-01")
        finally:
            ingestion_cli.EAClient = original_client  # type: ignore
            ingestion_cli.cmd_fetch_ea_readings_range = original_range  # type: ignore

    def test_api_healthz(self):
        client = TestClient(app)
        r = client.get("/healthz")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get("status"), "ok")

    def test_slice_runner_date_params(self):
        class _FakeEA:
            def get_readings(self, measure_id, since=None, until=None, sorted_flag=True):
                self.since = since
                self.until = until
                return [{"@id": "1", "value": 1.0, "measure": measure_id}]

        original = slice_runner.EAClient
        try:
            slice_runner.EAClient = lambda: _FakeEA()  # type: ignore
            cwd = os.getcwd()
            with tempfile.TemporaryDirectory() as td:
                os.chdir(td)
                res = slice_runner.run_hydrology_month_slice("MEASURE-XYZ", 2026, 1)
                self.assertTrue(os.path.exists(res["path"]))
        finally:
            slice_runner.EAClient = original  # type: ignore
            os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()

