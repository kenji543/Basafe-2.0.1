from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from geosafe.ulap.metadata_validator import MetadataValidator
from geosafe.ulap.models import ArcGISResponse, CacheMetadata, Status
from geosafe.ulap.service_registry import ServiceRegistry


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ulap"
REGISTRY_PATH = ROOT / "config" / "ulap-services.generated.json"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def response(url: str, payload: dict) -> ArcGISResponse:
    cached = CacheMetadata(
        source_url=url,
        retrieved_at="2026-07-23T00:00:00+00:00",
        expires_at="2026-07-24T00:00:00+00:00",
        from_cache=False,
    )
    return ArcGISResponse(
        data=payload,
        source_url=url,
        requested_at="2026-07-23T00:00:00+00:00",
        responded_at="2026-07-23T00:00:01+00:00",
        duration_ms=10,
        http_status=200,
        cache=cached,
    )


class MetadataStubClient:
    def __init__(self, layer_payload: dict) -> None:
        self.layer_payload = layer_payload

    def service_metadata(self, url: str) -> ArcGISResponse:
        payload = fixture("map_service_metadata.json")
        payload["layers"][0]["name"] = self.layer_payload.get("name")
        return response(url, payload)

    def layer_metadata(self, url: str) -> ArcGISResponse:
        return response(url, self.layer_payload)


class MetadataValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ServiceRegistry(REGISTRY_PATH, environment={})

    def test_verified_flood_metadata(self) -> None:
        validator = MetadataValidator(
            MetadataStubClient(fixture("flood_layer_metadata.json")),
            self.registry,
        )
        result = validator.validate(self.registry.get("flood"))
        self.assertEqual(result.status, Status.VERIFIED)
        self.assertEqual(result.metadata["classification_field"], "fscode")
        self.assertEqual(
            result.metadata["classification_domain"]["04"],
            "Very High Susceptibility",
        )

    def test_changed_domain_is_reported_not_silently_accepted(self) -> None:
        metadata = fixture("flood_layer_metadata.json")
        metadata["fields"][1]["domain"]["codedValues"][3]["name"] = "Renamed"
        result = MetadataValidator(
            MetadataStubClient(metadata), self.registry
        ).validate(self.registry.get("flood"))
        self.assertEqual(result.status, Status.VERIFIED_CHANGED_METADATA)
        self.assertTrue(
            any("domain differs" in difference for difference in result.differences)
        )

    def test_missing_classification_field_is_explicit(self) -> None:
        metadata = fixture("flood_layer_metadata.json")
        metadata["fields"] = [
            field for field in metadata["fields"] if field["name"] != "fscode"
        ]
        result = MetadataValidator(
            MetadataStubClient(metadata), self.registry
        ).validate(self.registry.get("flood"))
        self.assertEqual(result.status, Status.MISSING_CLASSIFICATION_FIELD)

    def test_unconfigured_ground_shaking_is_unavailable_without_request(self) -> None:
        result = MetadataValidator(
            MetadataStubClient({}), self.registry
        ).validate(self.registry.get("ground_shaking"))
        self.assertEqual(result.status, Status.UNAVAILABLE)
        self.assertIn("No ground-shaking", result.message)

    def test_supplied_boundary_stays_pending_even_when_structure_matches(self) -> None:
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"BARANGAY": "Fixture"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [499000, 1250000],
                                [500000, 1250000],
                                [500000, 1251000],
                                [499000, 1251000],
                                [499000, 1250000]
                            ]
                        ]
                    }
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            boundary = Path(directory) / "boundary.json"
            raw = json.dumps(payload).encode("utf-8")
            boundary.write_bytes(raw)
            config = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
            config["source_manifest_audit"].update(
                {
                    "supplied_path": str(boundary),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "feature_count": 1,
                    "likely_crs": "EPSG:3125",
                }
            )
            temporary_registry = Path(directory) / "registry.json"
            temporary_registry.write_text(json.dumps(config), encoding="utf-8")
            registry = ServiceRegistry(temporary_registry, environment={})
            result = MetadataValidator(
                MetadataStubClient({}), registry
            ).validate_supplied_boundary()
        self.assertEqual(result.status, Status.PENDING_VERIFICATION)
        self.assertEqual(result.metadata["likely_crs"], "EPSG:3125")
        self.assertTrue(
            any("must be confirmed" in item for item in result.differences)
        )


if __name__ == "__main__":
    unittest.main()
