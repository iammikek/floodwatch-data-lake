import unittest
from fastapi.testclient import TestClient
from api.main import app
from api.utils.cache import set_rate_limit_config, clear_rate_limit


class ApiRateLimitTests(unittest.TestCase):
    def setUp(self):
        set_rate_limit_config(2, 60)
        clear_rate_limit()

    def test_warnings_rate_limit_third_call_429(self):
        client = TestClient(app)
        r1 = client.get("/v1/warnings", params={"region": "SOM"})
        r2 = client.get("/v1/warnings", params={"region": "SOM"})
        r3 = client.get("/v1/warnings", params={"region": "SOM"})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r3.status_code, 429)


if __name__ == "__main__":
    unittest.main()
