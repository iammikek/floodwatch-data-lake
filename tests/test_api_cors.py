import unittest

from fastapi.testclient import TestClient

from api.main import app


class ApiCorsTests(unittest.TestCase):
    def test_preflight_allows_default_vite_origin(self):
        client = TestClient(app)
        r = client.options(
            "/v1/predictions",
            headers={
                "Origin": "http://localhost:5177",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("access-control-allow-origin"), "http://localhost:5177")


if __name__ == "__main__":
    unittest.main()
