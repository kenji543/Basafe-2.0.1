from __future__ import annotations

import unittest
from pathlib import Path

from pydantic import ValidationError

from geosafe.ulap.errors import UrlNotAllowedError
from geosafe.ulap.models import ServiceDefinition
from geosafe.ulap.service_registry import ServiceRegistry


ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "config" / "ulap-services.generated.json"


class ServiceRegistryTests(unittest.TestCase):
    def test_registry_preserves_verified_hazard_urls(self) -> None:
        registry = ServiceRegistry(REGISTRY, environment={})
        self.assertEqual(
            registry.get("flood").layer_url,
            "https://ulap-hazards.georisk.gov.ph/arcgis/rest/services/"
            "MGBPublic/Flood/MapServer/0",
        )
        self.assertEqual(registry.get("flood").classification_field, "fscode")
        self.assertEqual(
            registry.get("liquefaction").classification_field, "lccode"
        )
        ground = registry.get("ground_shaking")
        self.assertTrue(ground.configured)
        self.assertEqual(ground.classification_field, "peiscode")
        self.assertEqual(
            ground.layer_url,
            "https://gisweb.phivolcs.dost.gov.ph/arcgis/rest/services/"
            "PHIVOLCSPublic/GroundShaking/MapServer/0",
        )
        self.assertEqual(ground.verification["status"], "verified")

    def test_supplied_file_provenance_is_explicitly_non_operational(self) -> None:
        audit = ServiceRegistry(REGISTRY, environment={}).source_manifest_audit
        self.assertEqual(audit["feature_count"], 58)
        self.assertEqual(
            audit["sha256"],
            "027b6dbaacdee9fd83e1ce680e2015916ecd44d1ede2440571a86358d0b5a581",
        )
        self.assertFalse(audit["contains_service_urls"])
        self.assertIsNone(audit["declared_crs"])
        self.assertEqual(audit["likely_crs"], "EPSG:3125")
        self.assertFalse(audit["operational_use"])
        self.assertEqual(audit["geometry_validation"]["valid_features"], 58)
        self.assertEqual(audit["name_completeness"]["blank_name_features"], 6)

    def test_base_url_override_must_remain_on_exact_allowlisted_host(self) -> None:
        with self.assertRaises(UrlNotAllowedError):
            ServiceRegistry(
                REGISTRY,
                environment={
                    "ULAP_HAZARDS_BASE_URL": "https://attacker.example/arcgis"
                },
            )

    def test_approved_base_override_rebuilds_service_and_layer_urls(self) -> None:
        registry = ServiceRegistry(
            REGISTRY,
            environment={
                "ULAP_HAZARDS_BASE_URL": (
                    "https://ulap-hazards.georisk.gov.ph/arcgis/rest/services/"
                )
            },
        )
        flood = registry.get("flood")
        self.assertTrue(flood.service_url.endswith("/MGBPublic/Flood/MapServer"))
        self.assertEqual(flood.layer_url, f"{flood.service_url}/0")

    def test_pydantic_contract_rejects_configured_service_without_urls(self) -> None:
        with self.assertRaises(ValidationError):
            ServiceDefinition(
                key="broken",
                dataset_type="hazard",
                required=True,
                configured=True,
                agency=None,
                attribution=None,
                service_url=None,
                layer_url=None,
                layer_id=0,
                expected_layer_name="Broken",
                expected_geometry_type="esriGeometryPolygon",
                classification_field="code",
                expected_spatial_reference=4326,
                expected_domain={},
                preserve_fields=(),
                identity_fields={},
                required_capabilities=("Query",),
                verification={},
            )


if __name__ == "__main__":
    unittest.main()
