from __future__ import annotations

import json
import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from import_dataset import ImportFailure, ImportOptions, import_dataset  # noqa: E402


def feature_collection(
    properties: dict[str, object],
    coordinates: list[list[list[float]]] | None = None,
    crs: str = "EPSG:4326",
) -> dict[str, object]:
    return {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": crs}},
        "features": [
            {
                "type": "Feature",
                "properties": properties,
                "geometry": {
                    "type": "Polygon",
                    "coordinates": coordinates
                    or [
                        [
                            [125.0, 11.0],
                            [125.1, 11.0],
                            [125.1, 11.1],
                            [125.0, 11.1],
                            [125.0, 11.0],
                        ]
                    ],
                },
            }
        ],
    }


class ImporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database = self.root / "import.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _write_geojson(self, name: str, payload: dict[str, object]) -> Path:
        path = self.root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_hazard_import_validates_fraction_and_records_provenance(self) -> None:
        source = self._write_geojson(
            "flood.geojson",
            feature_collection(
                {"classification": "High", "normalized_value": 0.8}
            ),
        )
        result = import_dataset(
            ImportOptions(
                target="hazard",
                input_path=source,
                database_path=self.database,
                source_name="Official test issuer",
                source_date="2026-01-01",
                data_classification="official",
                quality_status="verified",
                slug="official-test-flood",
                dataset_name="Official test flood",
                hazard_type="flood",
                strict=True,
            )
        )
        self.assertEqual(result.imported_count, 1)
        connection = sqlite3.connect(self.database)
        try:
            dataset = connection.execute(
                """
                SELECT is_official, is_demo, metadata_json
                FROM hazard_datasets WHERE slug = 'official-test-flood'
                """
            ).fetchone()
            stored_value = connection.execute(
                "SELECT normalized_value FROM hazard_features"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(dataset[:2], (1, 0))
        metadata = json.loads(dataset[2])
        self.assertEqual(metadata["source_name"], "Official test issuer")
        self.assertRegex(metadata["input_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(stored_value, 0.8)

    def test_strict_import_rejects_out_of_range_normalized_value(self) -> None:
        source = self._write_geojson(
            "invalid.geojson",
            feature_collection(
                {"classification": "High", "normalized_value": 80}
            ),
        )
        error_log = self.root / "errors.jsonl"
        with self.assertRaises(ImportFailure):
            import_dataset(
                ImportOptions(
                    target="hazard",
                    input_path=source,
                    database_path=self.database,
                    source_name="Test source",
                    data_classification="demonstration",
                    quality_status="provisional",
                    slug="invalid-flood",
                    dataset_name="Invalid flood",
                    hazard_type="flood",
                    strict=True,
                    error_log=error_log,
                )
            )
        self.assertTrue(error_log.exists())
        self.assertIn("between 0 and 1", error_log.read_text(encoding="utf-8"))
        self.assertFalse(self.database.exists())

    def test_demo_hazard_cannot_replace_official_slug(self) -> None:
        source = self._write_geojson(
            "shared-slug.geojson",
            feature_collection(
                {"classification": "High", "normalized_value": 0.8}
            ),
        )
        common = {
            "target": "hazard",
            "input_path": source,
            "database_path": self.database,
            "source_name": "Official issuer",
            "quality_status": "verified",
            "slug": "shared-slug",
            "dataset_name": "Shared slug dataset",
            "hazard_type": "flood",
            "strict": True,
        }
        import_dataset(
            ImportOptions(**common, data_classification="official")
        )
        with self.assertRaisesRegex(ImportFailure, "refused to replace official"):
            import_dataset(
                ImportOptions(
                    **{
                        **common,
                        "source_name": "Demonstration seed",
                        "quality_status": "limited",
                        "data_classification": "demonstration",
                        "replace": True,
                    }
                )
            )
        connection = sqlite3.connect(self.database)
        try:
            flags = connection.execute(
                "SELECT is_official, is_demo FROM hazard_datasets WHERE slug = ?",
                ("shared-slug",),
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(flags, (1, 0))

    def test_epsg_3857_geometry_is_reprojected_to_wgs84(self) -> None:
        source = self._write_geojson(
            "mercator.geojson",
            feature_collection(
                {"name": "Reprojected boundary"},
                coordinates=[
                    [
                        [0, 0],
                        [111319.4908, 0],
                        [111319.4908, 111325.1429],
                        [0, 111325.1429],
                        [0, 0],
                    ]
                ],
                crs="EPSG:3857",
            ),
        )
        import_dataset(
            ImportOptions(
                target="municipal-boundary",
                input_path=source,
                database_path=self.database,
                source_name="Projection test",
                data_classification="demonstration",
                quality_status="provisional",
                strict=True,
            )
        )
        connection = sqlite3.connect(self.database)
        try:
            geometry = json.loads(
                connection.execute(
                    "SELECT geometry_geojson FROM municipal_boundary"
                ).fetchone()[0]
            )
        finally:
            connection.close()
        upper_right = geometry["coordinates"][0][2]
        self.assertAlmostEqual(upper_right[0], 1.0, places=4)
        self.assertAlmostEqual(upper_right[1], 1.0, places=4)

    @unittest.skipUnless(
        importlib.util.find_spec("pyproj"),
        "EPSG:3125 reprojection requires the optional GIS dependencies",
    )
    def test_prs92_zone_5_boundary_is_reprojected_when_crs_is_explicit(self) -> None:
        source = self._write_geojson(
            "basey-prs92.geojson",
            feature_collection(
                {"BARANGAY": "Projection test"},
                coordinates=[
                    [
                        [507354.79, 1247401.6729645291],
                        [507454.79, 1247401.6729645291],
                        [507454.79, 1247501.6729645291],
                        [507354.79, 1247501.6729645291],
                        [507354.79, 1247401.6729645291],
                    ]
                ],
                crs="EPSG:3125",
            ),
        )
        import_dataset(
            ImportOptions(
                target="barangays",
                input_path=source,
                database_path=self.database,
                source_name="Supplied-file projection test",
                data_classification="official",
                quality_status="provisional",
                source_crs="EPSG:3125",
                name_field="BARANGAY",
                strict=True,
            )
        )
        connection = sqlite3.connect(self.database)
        try:
            stored = json.loads(
                connection.execute(
                    "SELECT geometry_geojson FROM barangays"
                ).fetchone()[0]
            )
        finally:
            connection.close()
        longitude, latitude = stored["coordinates"][0][0]
        self.assertAlmostEqual(longitude, 125.068795687, places=6)
        self.assertAlmostEqual(latitude, 11.27974205, places=6)


if __name__ == "__main__":
    unittest.main()
