from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from geosafe.fuzzy import FuzzyModel
from geosafe.pdf import assessment_report_lines
from geosafe.repository import Repository
from geosafe.service import GeoSafeService
from geosafe.ulap.integration import UlapIntegration
from geosafe.ulap.models import CacheMetadata, HazardResult, Status
from geosafe.ulap.service_registry import ServiceRegistry


ROOT = Path(__file__).resolve().parent.parent


class OfflineUlap:
    """Deterministic live-contract double; it never supplies synthetic hazards."""

    def __init__(self) -> None:
        self.registry = ServiceRegistry(
            ROOT / "config" / "ulap-services.generated.json",
            environment={},
        )

    def identify(self, latitude: float, longitude: float) -> dict:
        return {
            "status": "available",
            "inside_basey": True,
            "municipality": "Basey",
            "province": "Samar",
            "barangay": "Can-abay",
            "municipality_code": "086002000",
            "province_code": "086000000",
            "barangay_code": "086002020",
            "psgc": "0806002020",
            "source_urls": [
                self.registry.get("municipal_boundary").layer_url,
                self.registry.get("barangay_boundary").layer_url,
            ],
            "retrieved_at": "2026-07-23T00:00:00+00:00",
            "warnings": [],
        }

    def assessment_hazards(
        self, latitude: float, longitude: float, model: FuzzyModel
    ) -> tuple[list[dict], list[str]]:
        cache = CacheMetadata(
            source_url="https://ulap-hazards.georisk.gov.ph/query",
            retrieved_at="2026-07-23T00:00:00+00:00",
            expires_at="2026-07-23T01:00:00+00:00",
            from_cache=False,
        )
        results = [
            HazardResult(
                hazard="flood",
                status=Status.AVAILABLE,
                agency="Mines and Geosciences Bureau",
                service=self.registry.get("flood").service_url,
                layer_id=0,
                classification_field="fscode",
                raw_code="03",
                official_label="High Susceptibility",
                raw_attributes={"fscode": "03"},
                decoded_attributes={"fscode": "High Susceptibility"},
                intersections=({"fscode": "03"},),
                source_url=self.registry.get("flood").layer_url,
                spatial_reference=4326,
                retrieved_at="2026-07-23T00:00:00+00:00",
                data_date="2018-07",
                attribution="Mines and Geosciences Bureau",
                feature_count=1,
                cache=cache,
            ),
            HazardResult(
                hazard="liquefaction",
                status=Status.AVAILABLE,
                agency="Philippine Institute of Volcanology and Seismology",
                service=self.registry.get("liquefaction").service_url,
                layer_id=0,
                classification_field="lccode",
                raw_code="01",
                official_label="Generally Susceptible",
                raw_attributes={"lccode": "01"},
                decoded_attributes={"lccode": "Generally Susceptible"},
                intersections=({"lccode": "01"},),
                source_url=self.registry.get("liquefaction").layer_url,
                spatial_reference=4326,
                retrieved_at="2026-07-23T00:00:00+00:00",
                data_date="2018-07",
                attribution="Philippine Institute of Volcanology and Seismology",
                feature_count=1,
                cache=cache,
            ),
            HazardResult(
                hazard="ground_shaking",
                status=Status.UNAVAILABLE,
                agency="Philippine Institute of Volcanology and Seismology",
                service=None,
                layer_id=None,
                classification_field=None,
                raw_code=None,
                official_label=None,
                raw_attributes={},
                decoded_attributes={},
                source_url=None,
                spatial_reference=None,
                retrieved_at="2026-07-23T00:00:00+00:00",
                warnings=("No verified ground-shaking endpoint is configured.",),
            ),
        ]
        rendered = [
            UlapIntegration._assessment_hazard(result, model)
            for result in results
        ]
        return rendered, [
            warning
            for hazard in rendered
            for warning in hazard.get("warnings", [])
        ]


class UlapApplicationIntegrationTests(unittest.TestCase):
    def test_missing_ground_shaking_persists_incomplete_assessment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            model = FuzzyModel.from_file(ROOT / "config" / "fuzzy_model.json")
            repository = Repository(
                Path(temporary_directory) / "ulap-integration.sqlite3",
                ROOT / "db" / "schema.sql",
            )
            repository.initialize(model)
            service = GeoSafeService(repository, model, OfflineUlap())

            point_result = service.live_hazards_at_location(
                11.290798, 125.033674
            )
            flood_source = next(
                source
                for source in point_result["sources"]
                if source["hazard"] == "flood"
            )
            self.assertEqual(
                flood_source["source_url"],
                OfflineUlap().registry.get("flood").layer_url,
            )
            self.assertEqual(flood_source["raw_code"], "03")
            self.assertEqual(
                flood_source["official_label"], "High Susceptibility"
            )
            self.assertEqual(flood_source["data_status"], "available")
            self.assertEqual(
                flood_source["retrieved_at"],
                "2026-07-23T00:00:00+00:00",
            )

            assessment = service.create_assessment(11.290798, 125.033674)

            self.assertEqual(assessment["status"], "incomplete")
            self.assertEqual(assessment["assessment"]["status"], "incomplete")
            self.assertIsNone(assessment["result"]["score"])
            self.assertIsNone(assessment["assessment"]["category"])
            self.assertEqual(
                assessment["result"]["missing_inputs"], ["ground_shaking"]
            )
            ground = next(
                item
                for item in assessment["hazards"]
                if item["hazard_type"] == "ground_shaking"
            )
            self.assertEqual(ground["status"], "unavailable")
            self.assertEqual(ground["availability_status"], "missing")
            self.assertIsNone(ground["normalized_value"])

            with repository.connection() as connection:
                persisted = connection.execute(
                    """
                    SELECT availability_status, source_metadata_json
                    FROM assessment_inputs AS input
                    JOIN assessments AS assessment
                      ON assessment.id = input.assessment_id
                    WHERE assessment.public_token = ?
                      AND input.variable_slug = 'ground_shaking'
                    """,
                    (assessment["id"],),
                ).fetchone()
            self.assertEqual(persisted["availability_status"], "missing")
            source_snapshot = json.loads(persisted["source_metadata_json"])
            self.assertEqual(source_snapshot["data_status"], "unavailable")

            flood = next(
                item
                for item in assessment["hazards"]
                if item["hazard_type"] == "flood"
            )
            self.assertEqual(flood["raw_code"], "03")
            self.assertEqual(flood["official_label"], "High Susceptibility")
            self.assertEqual(flood["normalized_value"], 75.0)
            self.assertEqual(
                flood["source_url"], OfflineUlap().registry.get("flood").layer_url
            )

            report_lines = assessment_report_lines(
                assessment, assessment["disclaimer"]
            )
            self.assertIn(assessment["disclaimer"], report_lines)
            self.assertTrue(
                any(flood["source_url"] in line for line in report_lines)
            )
            self.assertTrue(
                any("Missing information was not interpreted as low" in line for line in report_lines)
            )


if __name__ == "__main__":
    unittest.main()
