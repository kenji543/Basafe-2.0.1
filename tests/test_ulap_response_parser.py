from __future__ import annotations

import json
import unittest
from pathlib import Path

from geosafe.ulap.errors import UlapInvalidResponseError
from geosafe.ulap.models import Status
from geosafe.ulap.response_parser import (
    decode_attributes,
    extract_coded_domains,
    parse_arcgis_error,
    response_features,
)


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ulap"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class ArcGISResponseParserTests(unittest.TestCase):
    def test_authentication_errors_498_and_499_are_explicit(self) -> None:
        for name, code in (
            ("arcgis_error_498.json", 498),
            ("arcgis_error_499.json", 499),
        ):
            with self.subTest(code=code):
                error = parse_arcgis_error(fixture(name), http_status=200)
                self.assertIsNotNone(error)
                assert error is not None
                self.assertEqual(error.code, code)
                self.assertEqual(error.status, Status.AUTHENTICATION_REQUIRED)

    def test_coded_domain_decoding_preserves_raw_code(self) -> None:
        metadata = fixture("flood_layer_metadata.json")
        domains = extract_coded_domains(metadata)
        decoded = decode_attributes(
            {"objectid": 10, "fscode": "03", "gthcode": "raw-theme"}, domains
        )
        self.assertEqual(decoded.raw["fscode"], "03")
        self.assertEqual(decoded.decoded["fscode"], "High Susceptibility")
        self.assertEqual(decoded.decoded["gthcode"], "raw-theme")

    def test_renderer_can_supply_domain_when_field_domain_is_absent(self) -> None:
        metadata = fixture("liquefaction_layer_metadata.json")
        for field in metadata["fields"]:
            if field["name"] == "lccode":
                field["domain"] = None
        domain = extract_coded_domains(metadata)["lccode"]
        self.assertEqual(domain["06"], "Moderately Susceptible")

    def test_missing_features_array_is_invalid_not_no_intersection(self) -> None:
        with self.assertRaises(UlapInvalidResponseError):
            response_features("https://example.invalid/query", {"results": []})


if __name__ == "__main__":
    unittest.main()
