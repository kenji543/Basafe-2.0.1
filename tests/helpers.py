from __future__ import annotations

import json
import tempfile
from pathlib import Path

from geosafe.api import Api
from geosafe.fuzzy import FuzzyModel
from geosafe.repository import Repository
from geosafe.service import GeoSafeService


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def polygon(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> str:
    return json.dumps(
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [min_lon, min_lat],
                    [max_lon, min_lat],
                    [max_lon, max_lat],
                    [min_lon, max_lat],
                    [min_lon, min_lat],
                ]
            ],
        }
    )


class DemoApplication:
    def __init__(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "workflow-test.sqlite3"
        )
        self.model = FuzzyModel.from_file(
            PROJECT_ROOT / "config" / "fuzzy_model.json"
        )
        self.repository = Repository(
            self.database_path, PROJECT_ROOT / "db" / "schema.sql"
        )
        self.repository.initialize(self.model)
        self._seed()
        self.service = GeoSafeService(
            self.repository,
            self.model,
            allow_test_fixtures=True,
        )
        self.api = Api(self.service)

    def close(self) -> None:
        self.temporary_directory.cleanup()

    def _seed(self) -> None:
        source = json.dumps(
            {
                "label": "TEST FIXTURE — DEMONSTRATION DATA — NOT OFFICIAL",
                "source_name": "Automated test fixture",
                "source_date": "2026-01-01",
            }
        )
        with self.repository.connection() as connection:
            boundary = polygon(125.0, 11.0, 126.0, 12.0)
            connection.execute(
                """
                INSERT INTO municipal_boundary (
                    name, geometry_geojson, source_metadata_json,
                    is_official, is_demo
                ) VALUES ('Basey test extent', ?, ?, 0, 1)
                """,
                (boundary, source),
            )
            left_barangay = connection.execute(
                """
                INSERT INTO barangays (
                    name, psgc_code, geometry_geojson, source_metadata_json,
                    is_official, is_demo
                ) VALUES ('Test West', 'TEST-WEST', ?, ?, 0, 1)
                """,
                (polygon(125.0, 11.0, 125.5, 12.0), source),
            ).lastrowid
            connection.execute(
                """
                INSERT INTO barangays (
                    name, psgc_code, geometry_geojson, source_metadata_json,
                    is_official, is_demo
                ) VALUES ('Test East', 'TEST-EAST', ?, ?, 0, 1)
                """,
                (polygon(125.5, 11.0, 126.0, 12.0), source),
            )
            hazard_values = {
                "flood": ("High", 0.82, boundary),
                # Liquefaction intentionally covers only the west half so an east
                # assessment exercises mandatory incomplete-data behavior.
                "liquefaction": (
                    "Moderate",
                    0.55,
                    polygon(125.0, 11.0, 125.5, 12.0),
                ),
                "ground_shaking": ("High", 0.76, boundary),
            }
            for hazard_type, (
                classification,
                normalized_fraction,
                geometry,
            ) in hazard_values.items():
                dataset_id = connection.execute(
                    """
                    INSERT INTO hazard_datasets (
                        slug, name, hazard_type, source_name, source_date,
                        quality_status, is_official, is_demo, metadata_json
                    ) VALUES (?, ?, ?, 'Automated test fixture', '2026-01-01',
                              'provisional', 0, 1, ?)
                    """,
                    (
                        f"test-{hazard_type}",
                        f"Test {hazard_type.replace('_', ' ').title()}",
                        hazard_type,
                        source,
                    ),
                ).lastrowid
                connection.execute(
                    """
                    INSERT INTO hazard_features (
                        dataset_id, classification, normalized_value,
                        geometry_geojson, properties_json
                    ) VALUES (?, ?, ?, ?, '{}')
                    """,
                    (
                        dataset_id,
                        classification,
                        normalized_fraction,
                        geometry,
                    ),
                )
            connection.execute(
                """
                INSERT INTO historical_incidents (
                    incident_date, incident_type, severity, barangay_id,
                    barangay, latitude, longitude, title, description,
                    source_metadata_json, is_official, is_demo
                ) VALUES (
                    '2024-01-10', 'Flood', 'Moderate', ?, 'Test West',
                    11.5, 125.25, 'Test flood incident',
                    'Demonstration incident context.', ?, 0, 1
                )
                """,
                (left_barangay, source),
            )
            connection.execute(
                """
                INSERT INTO clup_references (
                    reference_type, title, description, document_section,
                    planning_note, barangay_id, source_metadata_json,
                    is_official, is_demo
                ) VALUES (
                    'land_use', 'Test CLUP reference',
                    'Demonstration land-use context.', 'Test section',
                    'Verify against an adopted official CLUP.', ?, ?, 0, 1
                )
                """,
                (left_barangay, source),
            )
            connection.commit()
