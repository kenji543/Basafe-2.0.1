from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.normalize_evacuation_centers import dms_to_decimal, normalize
from tests.helpers import DemoApplication, polygon


class EvacuationCenterNormalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.application = DemoApplication()
        self.temp = tempfile.TemporaryDirectory()
        self.source = Path(self.temp.name) / "centers.csv"
        with self.application.repository.connection() as connection:
            connection.execute(
                """
                INSERT INTO routing_study_areas (
                    name, version, geometry_geojson, source_name,
                    source_metadata_json, is_official, is_active
                ) VALUES ('Test study area', 'test-area-v1', ?,
                          'Test fixture', '{}', 0, 1)
                """,
                (polygon(125.0, 11.2, 125.2, 11.4),),
            )
            connection.commit()

    def tearDown(self) -> None:
        self.temp.cleanup()
        self.application.close()

    def write_source(self) -> None:
        with self.source.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "No.",
                    "Evacuation Center / Facility",
                    "Point",
                    "Latitude",
                    "Longitude",
                    "Status",
                ]
            )
            writer.writerow(
                [1, "Test Center", "EC1", "11°16'48.00\" N", "125°04'00.00\" E", "Existing"]
            )
            writer.writerow(
                [1, "Test Center", "EC2", "11°16'55.20\" N", "125°04'07.20\" E", "Existing"]
            )

    def test_dms_conversion(self) -> None:
        self.assertAlmostEqual(dms_to_decimal("11°16'48.00\" N"), 11.28)
        self.assertAlmostEqual(dms_to_decimal("125°04'00.00\" E"), 125.0666667)
        self.assertAlmostEqual(dms_to_decimal("11°16'48.00\" S"), -11.28)

    def test_rejects_invalid_dms_minutes(self) -> None:
        with self.assertRaises(ValueError):
            dms_to_decimal("11°60'00.00\" N")

    def test_repeated_points_become_one_facility(self) -> None:
        self.write_source()
        records, metadata = normalize(self.source, self.application.database_path)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["id"], "BASEY-EC-01")
        self.assertEqual(records[0]["name"], "Test Center")
        self.assertEqual(records[0]["barangay"], "Test West")
        self.assertEqual(records[0]["photo_url"], "")
        self.assertEqual(records[0]["photo_alt"], "")
        self.assertEqual(records[0]["photo_source"], "")
        self.assertEqual(records[0]["photo_source_url"], "")
        self.assertEqual(metadata["source_row_count"], 2)
        self.assertEqual(metadata["normalized_facility_count"], 1)
        self.assertEqual(metadata["quality_notes"][0]["source_row_count"], 2)
        self.assertEqual(metadata["classification"], "operator_declared_official_source")
        self.assertEqual(
            metadata["source_authority"],
            "Municipal Disaster Risk Reduction and Management Office of Basey (MDRRMO)",
        )
        self.assertFalse(metadata["source_image_archived"])


class EvacuationCenterApiClassificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.application = DemoApplication()

    def tearDown(self) -> None:
        self.application.close()

    def test_reference_centers_are_counted_but_not_reported_as_verified(self) -> None:
        with self.application.repository.connection() as connection:
            connection.execute(
                """
                INSERT INTO evacuation_centers (
                    external_id, name, latitude, longitude, designation,
                    source_name, source_metadata_json, dataset_version,
                    is_official, active, photo_url, photo_alt,
                    photo_source, photo_source_url
                ) VALUES ('REF-1', 'Reference Center', 11.28, 125.07,
                          'Existing in supplied inventory', 'User-supplied CSV',
                          '{}', 'reference-v1', 0, 1,
                          'https://example.org/reference-center.jpg',
                          'Front of Reference Center', 'Basey MDRRMO',
                          'https://example.org/reference-center')
                """
            )
            connection.commit()
        payload = self.application.service.evacuation_centers()
        self.assertEqual(payload["status"], "reference_available")
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["official_count"], 0)
        self.assertEqual(payload["reference_count"], 1)
        self.assertIn("not enabled", payload["notice"])
        center = payload["items"][0]
        self.assertEqual(center["photo_url"], "https://example.org/reference-center.jpg")
        self.assertEqual(center["photo_alt"], "Front of Reference Center")
        self.assertEqual(center["photo_source"], "Basey MDRRMO")
        self.assertEqual(
            center["photo_source_url"], "https://example.org/reference-center"
        )


if __name__ == "__main__":
    unittest.main()
