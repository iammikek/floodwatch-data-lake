import os
import unittest

from fastapi.testclient import TestClient

from api.main import app
from api.utils.cache import clear_rate_limit


class ApiAuthTests(unittest.TestCase):
    def setUp(self):
        clear_rate_limit()
        self._prev = os.environ.get("LAKE_API_TOKEN")

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("LAKE_API_TOKEN", None)
        else:
            os.environ["LAKE_API_TOKEN"] = self._prev

    def test_healthz_open_when_token_configured(self):
        os.environ["LAKE_API_TOKEN"] = "secret-token"
        client = TestClient(app)
        r = client.get("/healthz")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get("status"), "ok")

    def test_v1_rejects_missing_bearer_when_token_configured(self):
        os.environ["LAKE_API_TOKEN"] = "secret-token"
        client = TestClient(app)
        r = client.get("/v1/warnings", params={"region": "SOM"})
        self.assertEqual(r.status_code, 401)
        self.assertIn("WWW-Authenticate", r.headers)

    def test_v1_rejects_invalid_bearer_when_token_configured(self):
        os.environ["LAKE_API_TOKEN"] = "secret-token"
        client = TestClient(app)
        r = client.get(
            "/v1/warnings",
            params={"region": "SOM"},
            headers={"Authorization": "Bearer wrong-token"},
        )
        self.assertEqual(r.status_code, 401)

    def test_v1_accepts_valid_bearer_when_token_configured(self):
        os.environ["LAKE_API_TOKEN"] = "secret-token"
        client = TestClient(app)
        r = client.get(
            "/v1/rainfall",
            params={"region": "SOM"},
            headers={"Authorization": "Bearer secret-token"},
        )
        self.assertEqual(r.status_code, 200)

    def test_v1_open_when_token_unset(self):
        os.environ.pop("LAKE_API_TOKEN", None)
        client = TestClient(app)
        r = client.get("/v1/rainfall", params={"region": "SOM"})
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
