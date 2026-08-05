from __future__ import annotations

import json
import unittest
from pathlib import Path

from geosafe.ulap.boundary_provider import BoundaryProvider
from geosafe.ulap.hazard_provider import HazardProvider
from geosafe.ulap.models import (
    ArcGISResponse,
    CacheMetadata,
    PaginatedResult,
    PointQueryResult,
    Status,
)
from geosafe.ulap.service_registry import ServiceRegistry


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ulap"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def cache(url: str) -> CacheMetadata:
    return CacheMetadata(
        source_url=url,
        retrieved_at="2026-07-23T00:00:00+00:00",
        expires_at="2026-07-24T00:00:00+00:00",
        from_cache=False,
    )


def metadata_response(url: str, payload: dict) -> ArcGISResponse:
    return ArcGISResponse(
        data=payload,
        source_url=url,
        requested_at="2026-07-23T00:00:00+00:00",
        responded_at="2026-07-23T00:00:01+00:00",
        duration_ms=12,
        http_status=200,
        cache=cache(url),
    )


def point_result(url: str, payload: dict) -> PointQueryResult:
    features = tuple(payload["features"])
    return PointQueryResult(
        status=Status.AVAILABLE if features else Status.NO_INTERSECTION,
        source_url=url,
        retrieved_at="2026-07-23T00:00:01+00:00",
        features=features,
        feature_count=len(features),
        multiple_intersections=len(features) > 1,
        cache=cache(url),
        warnings=(
            ("Multiple features returned.",) if len(features) > 1 else ()
        ),
    )


class HazardStubClient:
    def __init__(self, metadata: dict, point_payload: dict) -> None:
        self.metadata = metadata
        self.point_payload = point_payload
        self.calls = 0

    def layer_metadata(self, url: str) -> ArcGISResponse:
        self.calls += 1
        return metadata_response(url, self.metadata)

    def point_query(self, url: str, *args, **kwargs) -> PointQueryResult:
        self.calls += 1
        return point_result(url, self.point_payload)


class BoundaryStubClient:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = list(payloads)

    def point_query(self, url: str, *args, **kwargs) -> PointQueryResult:
        return point_result(url, self.payloads.pop(0))


class GeoJSONStubClient:
    def __init__(self, features: list[dict]) -> None:
        self.features = features
        self.arguments: dict = {}

    def query_all(self, url: str, **kwargs) -> PaginatedResult:
        self.arguments = {"url": url, **kwargs}
        return PaginatedResult(
            features=tuple(self.features),
            pages=1,
            source_url=f"{url}/query",
            retrieved_at="2026-07-23T00:00:01+00:00",
            cache_entries=(cache(f"{url}/query"),),
        )


class HazardProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = ServiceRegistry(
            ROOT / "config" / "ulap-services.generated.json", environment={}
        )

    def test_flood_returns_raw_official_and_decoded_values_separately(self) -> None:
        stub = HazardStubClient(
            fixture("flood_layer_metadata.json"),
            fixture("flood_point_available.json"),
        )
        result = HazardProvider(stub, self.registry).at_location(
            "flood", 125.05, 11.28
        )
        self.assertEqual(result.status, Status.AVAILABLE)
        self.assertEqual(result.raw_code, "03")
        self.assertEqual(result.official_label, "High Susceptibility")
        self.assertEqual(result.raw_attributes["fscode"], "03")
        self.assertEqual(
            result.decoded_attributes["fscode"], "High Susceptibility"
        )
        self.assertEqual(len(result.intersections), 1)
        self.assertNotIn("normalized_value", result.to_dict())

    def test_liquefaction_preserves_theme_and_publication_context(self) -> None:
        result = HazardProvider(
            HazardStubClient(
                fixture("liquefaction_layer_metadata.json"),
                fixture("liquefaction_point_available.json"),
            ),
            self.registry,
        ).at_location("liquefaction", 125.05, 11.28)
        self.assertEqual(result.status, Status.AVAILABLE)
        self.assertEqual(result.raw_code, "06")
        self.assertEqual(result.official_label, "Moderately Susceptible")
        self.assertEqual(result.raw_attributes["liqcode"], "LIQ-THEME-06")
        self.assertEqual(result.data_date, 2018)

    def test_zero_feature_response_is_not_low(self) -> None:
        result = HazardProvider(
            HazardStubClient(
                fixture("flood_layer_metadata.json"),
                fixture("point_zero_features.json"),
            ),
            self.registry,
        ).at_location("flood", 125.05, 11.28)
        self.assertEqual(result.status, Status.NO_INTERSECTION)
        self.assertIsNone(result.raw_code)
        self.assertIsNone(result.official_label)
        self.assertIn("not a Low", result.warnings[0])

    def test_conflicting_intersections_are_not_silently_selected(self) -> None:
        result = HazardProvider(
            HazardStubClient(
                fixture("flood_layer_metadata.json"),
                fixture("point_conflicting_features.json"),
            ),
            self.registry,
        ).at_location("flood", 125.05, 11.28)
        self.assertEqual(result.status, Status.INVALID_RESPONSE)
        self.assertIsNone(result.raw_code)
        self.assertEqual(len(result.raw_attributes["intersections"]), 2)
        self.assertEqual(len(result.intersections), 2)

    def test_zero_features_outside_declared_extent_is_outside_coverage(self) -> None:
        metadata = fixture("flood_layer_metadata.json")
        metadata["extent"] = {
            "xmin": 120,
            "ymin": 5,
            "xmax": 126,
            "ymax": 20,
            "spatialReference": {"wkid": 4326},
        }
        result = HazardProvider(
            HazardStubClient(metadata, fixture("point_zero_features.json")),
            self.registry,
        ).at_location("flood", 119, 11.28)
        self.assertEqual(result.status, Status.OUTSIDE_COVERAGE)
        self.assertIn("outside the extent", result.warnings[0])

    def test_unknown_code_blocks_model_use(self) -> None:
        payload = fixture("flood_point_available.json")
        payload["features"][0]["attributes"]["fscode"] = "99"
        result = HazardProvider(
            HazardStubClient(fixture("flood_layer_metadata.json"), payload),
            self.registry,
        ).at_location("flood", 125.05, 11.28)
        self.assertEqual(result.status, Status.CHANGED_SCHEMA)
        self.assertEqual(result.raw_code, "99")
        self.assertIsNone(result.official_label)

    def test_ground_shaking_point_without_polygon_blocks_complete_assessment(self) -> None:
        stub = HazardStubClient(
            fixture("ground_shaking_layer_metadata.json"),
            fixture("point_zero_features.json"),
        )
        provider = HazardProvider(stub, self.registry)
        ground = provider.at_location("ground_shaking", 125.05, 11.28)
        self.assertEqual(ground.status, Status.NO_INTERSECTION)
        self.assertEqual(stub.calls, 2)
        gate = provider.assessment_gate(
            {
                "flood": HazardProvider(
                    HazardStubClient(
                        fixture("flood_layer_metadata.json"),
                        fixture("flood_point_available.json"),
                    ),
                    self.registry,
                ).at_location("flood", 125.05, 11.28),
                "liquefaction": HazardProvider(
                    HazardStubClient(
                        fixture("liquefaction_layer_metadata.json"),
                        fixture("liquefaction_point_available.json"),
                    ),
                    self.registry,
                ).at_location("liquefaction", 125.05, 11.28),
                "ground_shaking": ground,
            }
        )
        self.assertEqual(gate["assessmentStatus"], "incomplete")
        self.assertIsNone(gate["score"])
        self.assertEqual(gate["missingInputs"], ["ground_shaking"])

    def test_hazard_visualization_is_bbox_filtered_paginated_geojson(self) -> None:
        stub = GeoJSONStubClient(
            [
                {
                    "type": "Feature",
                    "properties": {"fscode": "03"},
                    "geometry": {"type": "Polygon", "coordinates": []},
                }
            ]
        )
        result = HazardProvider(stub, self.registry).basey_bbox_geojson(
            "flood", (124.97, 11.20, 125.31, 11.58)
        )
        self.assertEqual(result.status, Status.AVAILABLE)
        self.assertEqual(result.feature_collection["type"], "FeatureCollection")
        self.assertEqual(stub.arguments["response_format"], "geojson")
        self.assertEqual(stub.arguments["geometry_type"], "esriGeometryEnvelope")
        self.assertEqual(stub.arguments["input_spatial_reference"], 4326)


class BoundaryProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = ServiceRegistry(
            ROOT / "config" / "ulap-services.generated.json", environment={}
        )

    def test_case_insensitive_basey_and_barangay_identification(self) -> None:
        provider = BoundaryProvider(
            BoundaryStubClient(
                [
                    fixture("municipal_point_basey.json"),
                    fixture("barangay_point_basey.json"),
                ]
            ),
            self.registry,
        )
        result = provider.identify(125.05, 11.28)
        self.assertEqual(result.status, Status.AVAILABLE)
        self.assertTrue(result.inside_basey)
        self.assertEqual(result.barangay, "CAN-ABAY")
        self.assertEqual(result.psgc, "0806001020")

    def test_non_basey_intersection_is_outside(self) -> None:
        payload = fixture("municipal_point_basey.json")
        payload["features"][0]["attributes"]["city_name"] = "Palo"
        provider = BoundaryProvider(BoundaryStubClient([payload]), self.registry)
        result = provider.identify(125.05, 11.28)
        self.assertEqual(result.status, Status.OUTSIDE_COVERAGE)
        self.assertFalse(result.inside_basey)

    def test_basey_barangay_geojson_uses_server_side_filter_and_pagination(self) -> None:
        stub = GeoJSONStubClient(
            [
                {
                    "type": "Feature",
                    "properties": {"brgy_name": "CAN-ABAY"},
                    "geometry": {"type": "Polygon", "coordinates": []},
                }
            ]
        )
        result = BoundaryProvider(stub, self.registry).basey_barangays_geojson()
        self.assertEqual(result.status, Status.AVAILABLE)
        self.assertEqual(
            stub.arguments["where"],
            "city_name='Basey' AND prov_name='Samar'",
        )
        self.assertEqual(stub.arguments["response_format"], "geojson")
        self.assertTrue(stub.arguments["return_geometry"])


if __name__ == "__main__":
    unittest.main()
