from __future__ import annotations

import os
import unittest
from pathlib import Path

from geosafe.ulap import (
    ArcGISClient,
    BoundaryProvider,
    HazardProvider,
    MetadataValidator,
    ServiceRegistry,
    UlapIntegration,
)
from geosafe.ulap.models import Status


LIVE = os.getenv("LIVE_ULAP_TESTS", "").strip().casefold() == "true"
ROOT = Path(__file__).resolve().parent.parent
# Confirmed common coverage point: Basey; live flood fscode=03 and
# liquefaction lccode=01 when verified on 2026-07-23.
BASEY_COVERAGE_POINT = (125.0336740411251, 11.290798389750039)
@unittest.skipUnless(LIVE, "Set LIVE_ULAP_TESTS=true to contact official ULAP services.")
class LiveUlapIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = ServiceRegistry(
            ROOT / "config" / "ulap-services.generated.json"
        )
        cls.client = ArcGISClient.from_registry(cls.registry)

    def test_live_required_configured_metadata(self) -> None:
        validator = MetadataValidator(self.client, self.registry)
        for key in (
            "flood",
            "liquefaction",
            "ground_shaking",
            "municipal_boundary",
            "barangay_boundary",
        ):
            with self.subTest(service=key):
                result = validator.validate(self.registry.get(key))
                self.assertEqual(
                    result.status,
                    Status.VERIFIED,
                    msg=result.to_dict(),
                )

    def test_live_basey_boundary_identification(self) -> None:
        result = BoundaryProvider(self.client, self.registry).identify(
            *BASEY_COVERAGE_POINT
        )
        self.assertEqual(result.status, Status.AVAILABLE, msg=result.to_dict())
        self.assertTrue(result.inside_basey)
        self.assertIsNotNone(result.barangay)

    def test_live_flood_and_liquefaction_point_queries(self) -> None:
        provider = HazardProvider(self.client, self.registry)
        for key in ("flood", "liquefaction"):
            with self.subTest(hazard=key):
                result = provider.at_location(key, *BASEY_COVERAGE_POINT)
                self.assertEqual(
                    result.status,
                    Status.AVAILABLE,
                    msg=result.to_dict(),
                )
                self.assertIsNotNone(result.raw_code)
                self.assertIsNotNone(result.official_label)

    def test_live_basey_filtered_map_geojson(self) -> None:
        boundary_provider = BoundaryProvider(self.client, self.registry)
        municipal = boundary_provider.basey_municipal_geojson()
        barangays = boundary_provider.basey_barangays_geojson()
        self.assertEqual(municipal.status, Status.AVAILABLE, municipal.to_dict())
        self.assertEqual(barangays.status, Status.AVAILABLE, barangays.to_dict())
        self.assertGreater(len(municipal.feature_collection["features"]), 0)
        self.assertGreater(len(barangays.feature_collection["features"]), 0)

        integration = UlapIntegration(self.client, self.registry)
        for key in ("flood", "liquefaction"):
            with self.subTest(hazard=key):
                layer = integration.hazard_geojson(key)
                self.assertEqual(layer["status"], Status.AVAILABLE.value, layer)
                self.assertGreater(len(layer["features"]), 0)

    def test_ground_shaking_is_not_substituted(self) -> None:
        result = HazardProvider(self.client, self.registry).at_location(
            "ground_shaking", *BASEY_COVERAGE_POINT
        )
        self.assertIn(result.status, (Status.AVAILABLE, Status.NO_INTERSECTION))
        self.assertIsNotNone(result.source_url)
        self.assertIn("phivolcs", result.source_url.casefold())


if __name__ == "__main__":
    unittest.main()
