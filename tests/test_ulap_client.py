from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

from geosafe.ulap.arcgis_client import ArcGISClient, TransportResponse
from geosafe.ulap.errors import (
    ArcGISServiceError,
    UlapTimeoutError,
    UrlNotAllowedError,
)
from geosafe.ulap.models import Status


HOST = "ulap-hazards.georisk.gov.ph"
LAYER = (
    "https://ulap-hazards.georisk.gov.ph/arcgis/rest/services/"
    "MGBPublic/Flood/MapServer/0"
)


def transport_response(payload: dict, status: int = 200) -> TransportResponse:
    return TransportResponse(
        status=status,
        body=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )


class ScriptedTransport:
    def __init__(self, responses: list[TransportResponse | Exception]) -> None:
        self.responses = list(responses)
        self.urls: list[str] = []

    def __call__(self, url: str, timeout: float) -> TransportResponse:
        self.urls.append(url)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def client(transport, **options) -> ArcGISClient:
    return ArcGISClient(
        allowed_hosts=(HOST,),
        transport=transport,
        sleeper=lambda _: None,
        now=lambda: datetime(2026, 7, 23, tzinfo=timezone.utc),
        **options,
    )


class ArcGISClientTests(unittest.TestCase):
    def test_point_query_uses_encoded_parameter_dictionary(self) -> None:
        transport = ScriptedTransport([transport_response({"features": []})])
        result = client(transport).point_query(LAYER, 125.05, 11.28)
        self.assertEqual(result.status, Status.NO_INTERSECTION)
        requested = transport.urls[0]
        self.assertIn("geometry=125.05000000%2C11.28000000", requested)
        parameters = parse_qs(urlsplit(requested).query)
        self.assertEqual(parameters["geometryType"], ["esriGeometryPoint"])
        self.assertEqual(parameters["inSR"], ["4326"])
        self.assertEqual(parameters["spatialRel"], ["esriSpatialRelIntersects"])
        self.assertEqual(parameters["returnGeometry"], ["false"])

    def test_identify_fallback_is_scoped_to_one_layer_and_extent(self) -> None:
        transport = ScriptedTransport([transport_response({"results": []})])
        arcgis = client(transport)
        arcgis.identify_features(
            LAYER.rsplit("/", 1)[0],
            layer_id=0,
            geometry="124.9,11.2,125.3,11.6",
            geometry_type="esriGeometryEnvelope",
            map_extent=(124.9, 11.2, 125.3, 11.6),
        )

        requested = transport.urls[0]
        self.assertTrue(urlsplit(requested).path.endswith("/MapServer/identify"))
        parameters = parse_qs(urlsplit(requested).query)
        self.assertEqual(parameters["layers"], ["all:0"])
        self.assertEqual(parameters["returnGeometry"], ["true"])
        self.assertEqual(parameters["geometryPrecision"], ["6"])

    def test_exact_domain_allowlist_blocks_ssrf(self) -> None:
        transport = ScriptedTransport([])
        with self.assertRaises(UrlNotAllowedError):
            client(transport).layer_metadata(
                "https://ulap-hazards.georisk.gov.ph.attacker.example/layer/0"
            )

    def test_cache_records_live_then_cached_provenance(self) -> None:
        transport = ScriptedTransport(
            [transport_response({"currentVersion": 11, "id": 0})]
        )
        arcgis = client(transport)
        first = arcgis.layer_metadata(LAYER)
        second = arcgis.layer_metadata(LAYER)
        self.assertFalse(first.cache.from_cache)
        self.assertTrue(second.cache.from_cache)
        self.assertEqual(first.cache.retrieved_at, second.cache.retrieved_at)
        self.assertEqual(len(transport.urls), 1)

    def test_retry_is_bounded_and_uses_successful_second_response(self) -> None:
        transport = ScriptedTransport(
            [
                transport_response(
                    {"error": {"code": 500, "message": "temporary", "details": []}},
                    status=503,
                ),
                transport_response({"currentVersion": 11, "id": 0}),
            ]
        )
        result = client(transport, max_retries=1).layer_metadata(LAYER)
        self.assertEqual(result.data["id"], 0)
        self.assertEqual(len(transport.urls), 2)

    def test_timeout_has_structured_status(self) -> None:
        transport = ScriptedTransport([TimeoutError("slow"), TimeoutError("slow")])
        with self.assertRaises(UlapTimeoutError) as raised:
            client(transport, max_retries=1).layer_metadata(LAYER)
        self.assertEqual(raised.exception.status, Status.TIMEOUT)
        self.assertEqual(len(transport.urls), 2)

    def test_498_and_499_never_expose_token(self) -> None:
        for code in (498, 499):
            with self.subTest(code=code):
                transport = ScriptedTransport(
                    [
                        transport_response(
                            {
                                "error": {
                                    "code": code,
                                    "message": "token problem",
                                    "details": [],
                                }
                            }
                        )
                    ]
                )
                with self.assertRaises(ArcGISServiceError) as raised:
                    client(transport, token="TOP-SECRET").layer_metadata(LAYER)
                self.assertEqual(
                    raised.exception.status, Status.AUTHENTICATION_REQUIRED
                )
                self.assertNotIn("TOP-SECRET", json.dumps(raised.exception.as_dict()))
                self.assertIn("token=TOP-SECRET", transport.urls[0])

    def test_request_log_has_audit_fields_without_token(self) -> None:
        transport = ScriptedTransport(
            [
                transport_response(
                    {
                        "error": {
                            "code": 498,
                            "message": "token problem",
                            "details": [],
                        }
                    }
                )
            ]
        )
        with self.assertLogs(
            "geosafe.ulap.arcgis_client", level="INFO"
        ) as captured:
            with self.assertRaises(ArcGISServiceError):
                client(transport, token="TOP-SECRET").layer_metadata(LAYER)
        rendered = "\n".join(captured.output)
        for field in (
            "dataset=MGBPublic/Flood",
            "layer_id=0",
            "requested_at=",
            "responded_at=",
            "http_status=200",
            "arcgis_error_code=498",
            "feature_count=None",
            "parsing_status=authentication_required",
        ):
            self.assertIn(field, rendered)
        self.assertNotIn("TOP-SECRET", rendered)

    def test_pagination_uses_offsets_until_short_page(self) -> None:
        calls: list[int] = []

        def paged_transport(url: str, timeout: float) -> TransportResponse:
            offset = int(parse_qs(urlsplit(url).query)["resultOffset"][0])
            calls.append(offset)
            if offset == 0:
                return transport_response(
                    {
                        "features": [{"attributes": {"id": 1}}, {"attributes": {"id": 2}}],
                        "exceededTransferLimit": True,
                    }
                )
            return transport_response(
                {
                    "features": [{"attributes": {"id": 3}}],
                    "exceededTransferLimit": False,
                }
            )

        result = client(paged_transport).query_all(LAYER, page_size=2)
        self.assertEqual(calls, [0, 2])
        self.assertEqual(result.pages, 2)
        self.assertEqual(len(result.features), 3)

    def test_coordinate_validation_rejects_non_finite_and_out_of_range(self) -> None:
        transport = ScriptedTransport([])
        arcgis = client(transport)
        for longitude, latitude in ((181, 11), (125, 91), (float("nan"), 11)):
            with self.subTest(longitude=longitude, latitude=latitude):
                with self.assertRaises(ValueError):
                    arcgis.point_query(LAYER, longitude, latitude)


if __name__ == "__main__":
    unittest.main()
