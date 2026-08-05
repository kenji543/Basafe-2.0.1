from __future__ import annotations

import json
import unittest

from geosafe.api import Api
from geosafe.service import GeoSafeService
from tests.helpers import DemoApplication


class NetworkTrap:
    """Fails the test if snapshot-mode code attempts to use ULAP."""

    def __getattr__(self, name: str):
        raise AssertionError(f"snapshot mode attempted a live ULAP call: {name}")


class SnapshotRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.application = DemoApplication()

    def tearDown(self) -> None:
        self.application.close()

    def _service(self) -> GeoSafeService:
        return GeoSafeService(
            self.application.repository,
            self.application.model,
            NetworkTrap(),
            allow_test_fixtures=True,
            runtime_data_mode="snapshot",
        )

    def test_snapshot_assessment_uses_only_local_boundaries_and_hazards(self) -> None:
        service = self._service()
        result = service.hazards_at_location(11.5, 125.25)

        self.assertEqual(result["runtimeDataMode"], "snapshot")
        self.assertEqual(result["assessment"]["status"], "complete")
        self.assertEqual(result["hazards"]["flood"]["status"], "available")
        self.assertEqual(len(service.barangays_geojson()["features"]), 2)

        assessment = service.create_assessment(11.5, 125.25)
        self.assertEqual(assessment["status"], "complete")

    def test_missing_snapshot_does_not_fall_through_to_live_service(self) -> None:
        with self.application.repository.connection() as connection:
            connection.execute(
                "DELETE FROM hazard_datasets WHERE hazard_type = 'flood'"
            )
            connection.commit()
        service = self._service()
        response = Api(service).dispatch(
            "GET",
            "/api/v1/hazards/at-location",
            {"lat": ["11.5"], "lon": ["125.25"]},
        )
        payload = json.loads(response.body)

        self.assertEqual(response.status, 200)
        self.assertEqual(payload["hazards"]["flood"]["status"], "unavailable")
        self.assertIn("flood", payload["assessment"]["missingInputs"])

    def test_unknown_runtime_mode_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            GeoSafeService(
                self.application.repository,
                self.application.model,
                runtime_data_mode="automatic-fallback",
            )


if __name__ == "__main__":
    unittest.main()
