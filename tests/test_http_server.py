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

    def test_unified_web_gis_page_loads(self) -> None:
        with urlopen(f"{self.base_url}/", timeout=5) as response:
            content = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("Interactive Basey hazard map", content)
            self.assertEqual(response.headers["X-Frame-Options"], "DENY")
            self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])

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


if __name__ == "__main__":
    unittest.main()
