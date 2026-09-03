import unittest

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


class HealthEndpointTests(unittest.TestCase):
    def make_client(self, checks=None):
        settings = Settings(environment="test", _env_file=None)
        return TestClient(create_app(settings, include_legacy=False, readiness_checks=checks))

    def test_liveness_has_versioned_contract_and_request_id(self):
        with self.make_client() as client:
            response = client.get("/api/v1/health/live", headers={"X-Request-ID": "test-request"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.headers["X-Request-ID"], "test-request")

    def test_readiness_reports_successful_dependencies(self):
        with self.make_client({"database": lambda: True}) as client:
            response = client.get("/api/v1/health/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["checks"], {"database": "ok"})

    def test_readiness_returns_503_for_failed_dependency(self):
        with self.make_client({"database": lambda: False}) as client:
            response = client.get("/api/v1/health/ready")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["checks"], {"database": "unavailable"})

    def test_http_errors_use_standard_contract(self):
        with self.make_client() as client:
            response = client.get("/api/v1/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "http_error")
        self.assertTrue(response.json()["request_id"])
