import gzip
import json
import os
import tempfile
import unittest
from types import SimpleNamespace

from ingestion import cli as ingestion_cli
from ingestion.corridor_backfill import (
    corridor_measure_ids,
    coverage_for_measure,
    coverage_report,
    assert_coverage,
)


class CorridorBackfillTests(unittest.TestCase):
    def test_corridor_measure_ids_a361(self):
        ids = corridor_measure_ids("a361-muchelney")
        self.assertIn("52119-level-stage-i-15_min-mASD", ids)
        self.assertIn("52153-level-stage-i-15_min-mASD", ids)
        self.assertEqual(len(ids), 4)

    def test_coverage_detects_present_and_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = os.path.join(td, "readings")
            measure = "52119-level-stage-i-15_min-mASD"
            os.makedirs(os.path.join(root, measure), exist_ok=True)
            path = os.path.join(root, measure, "2026-01.ndjson.gz")
            with gzip.open(path, "wt") as f:
                f.write(json.dumps({"value": 1.0}) + "\n")

            cov = coverage_for_measure(measure, "2026-01", "2026-02", data_root=root)
            self.assertEqual(cov.present_months, 1)
            self.assertEqual(cov.missing, ["2026-02"])
            self.assertFalse(cov.complete)

    def test_coverage_report_complete(self):
        with tempfile.TemporaryDirectory() as td:
            root = os.path.join(td, "readings")
            for measure in corridor_measure_ids("a361-muchelney"):
                os.makedirs(os.path.join(root, measure), exist_ok=True)
                path = os.path.join(root, measure, "2026-01.ndjson.gz")
                with gzip.open(path, "wt") as f:
                    f.write(json.dumps({"value": 1.0}) + "\n")

            report = coverage_report("a361-muchelney", "2026-01", "2026-01", data_root=root)
            self.assertTrue(report["complete"])
            self.assertEqual(report["total_present_files"], 4)

    def test_assert_coverage_min_months(self):
        with tempfile.TemporaryDirectory() as td:
            root = os.path.join(td, "readings")
            for measure in corridor_measure_ids("a361-muchelney"):
                os.makedirs(os.path.join(root, measure), exist_ok=True)
                for month in ("2026-01", "2026-02"):
                    path = os.path.join(root, measure, f"{month}.ndjson.gz")
                    with gzip.open(path, "wt") as f:
                        f.write(json.dumps({"value": 1.0}) + "\n")

            assert_coverage("a361-muchelney", "2026-01", "2026-02", min_months=2, data_root=root)

            os.remove(os.path.join(root, corridor_measure_ids("a361-muchelney")[0], "2026-02.ndjson.gz"))
            with self.assertRaises(RuntimeError):
                assert_coverage("a361-muchelney", "2026-01", "2026-02", min_months=2, data_root=root)

    def test_backfill_ea_corridor_calls_measures(self):
        calls = []

        class _FakeEA:
            def get_readings(self, measure_id, since=None, until=None, sorted_flag=True):
                calls.append((measure_id, since, until))
                return [{"@id": "1", "value": 1.0, "measure": measure_id}]

        original = ingestion_cli.EAClient
        try:
            ingestion_cli.EAClient = lambda: _FakeEA()  # type: ignore
            cwd = os.getcwd()
            with tempfile.TemporaryDirectory() as td:
                os.chdir(td)
                args = SimpleNamespace(
                    corridor="a361-muchelney",
                    from_month="2026-01",
                    to_month="2026-01",
                    resume=False,
                )
                ingestion_cli.cmd_backfill_ea_corridor(args)
                self.assertEqual(len(calls), 4)
                measure_ids = set(c[0] for c in calls)
                self.assertEqual(measure_ids, set(corridor_measure_ids("a361-muchelney")))
        finally:
            ingestion_cli.EAClient = original  # type: ignore
            os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
