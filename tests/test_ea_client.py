import unittest
from typing import Any, Dict
from ingestion.clients.ea import EAClient


class _FakeResponse:
    def __init__(self, status_code: int = 200, payload: Dict[str, Any] | None = None):
        self.status_code = status_code
        self._payload = payload or {"items": []}
        self.request = None
        self._raise = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _FakeHTTPClient:
    def __init__(self):
        self.last_url = None
        self.last_params = None
        self.response = _FakeResponse()

    def get(self, url, params=None):
        self.last_url = url
        self.last_params = params or {}
        return self.response


class EAClientTests(unittest.TestCase):
    def setUp(self):
        self.client = EAClient()
        self.fake = _FakeHTTPClient()
        self.client._client = self.fake  # type: ignore[attr-defined]

    def test_get_stations_bbox_param(self):
        self.fake.response = _FakeResponse(200, {"items": [{"id": 1}]})
        items = self.client.get_stations(bbox="-2,51,-1,52", parameter="level")
        self.assertEqual(len(items), 1)
        self.assertIn("/id/stations", self.fake.last_url)
        self.assertEqual(self.fake.last_params.get("bbox"), "-2,51,-1,52")
        self.assertEqual(self.fake.last_params.get("parameter"), "level")

    def test_get_readings_date_params(self):
        self.fake.response = _FakeResponse(200, {"items": [{"v": 1}, {"v": 2}]})
        items = self.client.get_readings(
            "MEASURE-123", since="2026-01-01", until="2026-01-31", sorted_flag=True
        )
        self.assertEqual(len(items), 2)
        self.assertIn("/id/measures/MEASURE-123/readings", self.fake.last_url)
        self.assertEqual(self.fake.last_params.get("startdate"), "2026-01-01")
        self.assertEqual(self.fake.last_params.get("enddate"), "2026-01-31")
        self.assertIn("_sorted", self.fake.last_params)


if __name__ == "__main__":
    unittest.main()
