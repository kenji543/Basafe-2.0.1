from __future__ import annotations

import json
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from geosafe.server import GeoSafeServer
from tests.helpers import DemoApplication


WEB_ROOT = Path(__file__).resolve().parent.parent / "web"


class HttpServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = DemoApplication()
        cls.server = GeoSafeServer(
            ("127.0.0.1", 0), cls.application.api, WEB_ROOT
        )
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True
        )
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.application.close()

    def test_public_landing_and_map_pages_load(self) -> None:
        with urlopen(f"{self.base_url}/", timeout=5) as response:
            content = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("Understand the hazards affecting a location.", content)
            self.assertEqual(response.headers["X-Frame-Options"], "DENY")
            self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
            self.assertIn("https://server.arcgisonline.com", response.headers["Content-Security-Policy"])
            self.assertIn("https://ulap-hazards.georisk.gov.ph", response.headers["Content-Security-Policy"])
        with urlopen(f"{self.base_url}/map", timeout=5) as response:
            content = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("Interactive Basey hazard map", content)

    def test_public_routes_and_pwa_assets_load(self) -> None:
        for route in (
            "/methodology",
            "/data-sources",
            "/limitations",
            "/about",
            "/privacy",
            "/offline",
            "/manifest.webmanifest",
            "/service-worker.js",
        ):
            with self.subTest(route=route):
                with urlopen(f"{self.base_url}{route}", timeout=5) as response:
                    self.assertEqual(response.status, 200)

    def test_health_and_compatibility_endpoints(self) -> None:
        for route in ("/api/health", "/api/layers", "/api/model/current"):
            with self.subTest(route=route):
                with urlopen(f"{self.base_url}{route}", timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    self.assertTrue(json.load(response))
        try:
            response = urlopen(f"{self.base_url}/api/source-status", timeout=5)
        except HTTPError as error:
            self.assertEqual(error.code, 503)
            self.assertTrue(json.load(error))
        else:
            with response:
                self.assertEqual(response.status, 200)
                self.assertTrue(json.load(response))

    def test_api_workflow_over_http(self) -> None:
        request = Request(
            f"{self.base_url}/api/v1/assessments",
            data=json.dumps({"latitude": 11.5, "longitude": 125.25}).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=5) as response:
            assessment = json.load(response)
            self.assertEqual(response.status, 201)
            self.assertEqual(assessment["status"], "complete")
            report_url = assessment["links"]["report"]
        with urlopen(f"{self.base_url}{report_url}", timeout=5) as report:
            self.assertEqual(report.headers["Content-Type"], "application/pdf")
            self.assertTrue(report.read(8).startswith(b"%PDF-1.4"))

    def test_out_of_scope_http_endpoint_is_absent(self) -> None:
        with self.assertRaises(HTTPError) as caught:
            urlopen(f"{self.base_url}/api/v1/admin", timeout=5)
        self.assertEqual(caught.exception.code, 404)

    def test_assessment_rate_limit_is_bounded_per_client(self) -> None:
        client = "203.0.113.77"
        for _ in range(self.server.assessment_rate_limit):
            allowed, _, _, _ = self.server.check_rate_limit(client, "assessment")
            self.assertTrue(allowed)
        allowed, limit, remaining, retry_after = self.server.check_rate_limit(
            client, "assessment"
        )
        self.assertFalse(allowed)
        self.assertEqual(limit, self.server.assessment_rate_limit)
        self.assertEqual(remaining, 0)
        self.assertGreaterEqual(retry_after, 1)


if __name__ == "__main__":
    unittest.main()
