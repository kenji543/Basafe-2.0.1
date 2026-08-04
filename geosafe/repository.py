"""SQLite persistence for the focused GeoSafe-FIS workflow."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .fuzzy import FuzzyModel, ModelConfigurationError


def json_value(value: str | None, fallback: Any) -> Any:
    if value is None or value == "":
        return fallback
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return fallback


class RepositoryError(RuntimeError):
    """Raised for unavailable or inconsistent application persistence."""


class Repository:
    """Short-lived SQLite connections suitable for a threaded HTTP server."""

    def __init__(self, database_path: str | Path, schema_path: str | Path):
        self.database_path = Path(database_path)
        self.schema_path = Path(schema_path)
        self.model_id: int | None = None

    @contextmanager
    def connection(self) -> Iterable[sqlite3.Connection]:
        connection = sqlite3.connect(
            self.database_path,
            timeout=10,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self, model: FuzzyModel) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.schema_path.exists():
            raise RepositoryError(f"Database schema not found: {self.schema_path}")
        with self.connection() as connection:
            connection.executescript(self.schema_path.read_text(encoding="utf-8"))
            connection.execute("PRAGMA journal_mode = WAL")
            connection.commit()
        self.model_id = self._synchronize_model(model)

    def _synchronize_model(self, model: FuzzyModel) -> int:
        configuration = model.configuration
        canonical = json.dumps(configuration, sort_keys=True, separators=(",", ":"))
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT id, configuration_json FROM fuzzy_models WHERE version = ?",
                (model.version,),
            ).fetchone()
            if existing:
                existing_configuration = json_value(
                    existing["configuration_json"], None
                )
                if existing_configuration != configuration:
                    raise ModelConfigurationError(
                        "The database already contains a different fuzzy model "
                        f"configuration with immutable version {model.version!r}. "
                        "Increment model_version before changing validated model content."
                    )
                return int(existing["id"])

            cursor = connection.execute(
                """
                INSERT INTO fuzzy_models (
                    version, name, description, defuzzification_method,
                    output_min, output_max, validation_notes,
                    configuration_json, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    model.version,
                    configuration.get("model_name", "GeoSafe-FIS fuzzy model"),
                    configuration.get("status"),
                    configuration["inference"]["defuzzification"],
                    configuration["output"]["universe"][0],
                    configuration["output"]["universe"][1],
                    json.dumps(configuration.get("validation_notes", [])),
                    canonical,
                ),
            )
            model_id = int(cursor.lastrowid)
            connection.execute(
                "UPDATE fuzzy_models SET is_active = 0 WHERE id <> ?", (model_id,)
            )

            variable_ids: dict[str, int] = {}
            variables = [
                *configuration["inputs"],
                {
                    **configuration["output"],
                    "unit": "normalized screening score",
                    "required": False,
                },
            ]
            for order, variable in enumerate(variables):
                kind = (
                    "output"
                    if variable["id"] == configuration["output"]["id"]
                    else "input"
                )
                variable_cursor = connection.execute(
                    """
                    INSERT INTO fuzzy_variables (
                        model_id, slug, name, variable_kind, units,
                        minimum_value, maximum_value, is_required,
                        sort_order, configuration_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        model_id,
                        variable["id"],
                        variable["name"],
                        kind,
                        variable.get("unit"),
                        variable["universe"][0],
                        variable["universe"][1],
                        int(bool(variable.get("required", False))),
                        order,
                        json.dumps(variable, sort_keys=True),
                    ),
                )
                variable_id = int(variable_cursor.lastrowid)
                variable_ids[variable["id"]] = variable_id
                for membership_order, membership in enumerate(
                    variable["memberships"]
                ):
                    connection.execute(
                        """
                        INSERT INTO membership_functions (
                            variable_id, linguistic_label, function_type,
                            parameters_json, sort_order
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            variable_id,
                            membership["term"],
                            membership["type"],
                            json.dumps(membership["parameters"]),
                            membership_order,
                        ),
                    )

            for order, rule in enumerate(configuration["rules"]):
                connection.execute(
                    """
                    INSERT INTO fuzzy_rules (
                        model_id, rule_code, rule_statement, antecedent_json,
                        consequent_label, weight, explanation, sort_order
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        model_id,
                        rule["id"],
                        rule["statement"],
                        json.dumps(
                            {
                                "operator": rule["operator"],
                                "conditions": rule["conditions"],
                            }
                        ),
                        rule["consequent"],
                        rule["weight"],
                        rule.get("rationale"),
                        order,
                    ),
                )
            connection.commit()
            return model_id

    def municipal_boundaries(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM municipal_boundary ORDER BY is_official DESC, id"
            ).fetchall()
        return [self._boundary_row(row) for row in rows]

    @staticmethod
    def _boundary_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "geometry": json_value(row["geometry_geojson"], None),
            "source_metadata": json_value(row["source_metadata_json"], {}),
            "is_official": bool(row["is_official"]),
            "is_demo": bool(row["is_demo"]),
            "data_status": (
                "official" if row["is_official"] else "demonstration"
            ),
            "created_at": row["created_at"],
        }

    def barangays(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM barangays ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [self._barangay_row(row) for row in rows]

    def barangay(self, barangay_id: int) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM barangays WHERE id = ?", (barangay_id,)
            ).fetchone()
        return self._barangay_row(row) if row else None

    def search_barangays(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        escaped = (
            query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM barangays
                WHERE name LIKE ? ESCAPE '\\'
                   OR COALESCE(psgc_code, '') LIKE ? ESCAPE '\\'
                ORDER BY
                    CASE WHEN lower(name) = lower(?) THEN 0
                         WHEN lower(name) LIKE lower(?) THEN 1
                         ELSE 2 END,
                    name COLLATE NOCASE
                LIMIT ?
                """,
                (f"%{escaped}%", f"%{escaped}%", query, f"{escaped}%", limit),
            ).fetchall()
        return [self._barangay_row(row) for row in rows]

    @staticmethod
    def _barangay_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "psgc_code": row["psgc_code"],
            "geometry": json_value(row["geometry_geojson"], None),
            "source_metadata": json_value(row["source_metadata_json"], {}),
            "is_official": bool(row["is_official"]),
            "is_demo": bool(row["is_demo"]),
            "data_status": (
                "official" if row["is_official"] else "demonstration"
            ),
            "created_at": row["created_at"],
        }

    def hazard_datasets(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT d.*, COUNT(f.id) AS feature_count
                FROM hazard_datasets d
                LEFT JOIN hazard_features f ON f.dataset_id = d.id
                GROUP BY d.id
                ORDER BY d.hazard_type, d.is_official DESC,
                         COALESCE(d.source_date, '') DESC, d.id DESC
                """
            ).fetchall()
        return [self._hazard_dataset_row(row) for row in rows]

    def hazard_dataset(self, dataset_id_or_slug: int | str) -> dict[str, Any] | None:
        field = "id" if isinstance(dataset_id_or_slug, int) else "slug"
        with self.connection() as connection:
            row = connection.execute(
                f"""
                SELECT d.*, COUNT(f.id) AS feature_count
                FROM hazard_datasets d
                LEFT JOIN hazard_features f ON f.dataset_id = d.id
                WHERE d.{field} = ?
                GROUP BY d.id
                """,
                (dataset_id_or_slug,),
            ).fetchone()
        return self._hazard_dataset_row(row) if row else None

    @staticmethod
    def _hazard_dataset_row(row: sqlite3.Row) -> dict[str, Any]:
        keys = set(row.keys())
        return {
            "id": row["id"],
            "slug": row["slug"],
            "name": row["name"],
            "hazard_type": row["hazard_type"],
            "source_name": row["source_name"],
            "source_date": row["source_date"],
            "quality_status": row["quality_status"],
            "is_official": bool(row["is_official"]),
            "is_demo": bool(row["is_demo"]),
            "data_status": (
                "official" if row["is_official"] else "demonstration"
            ),
            "metadata": json_value(row["metadata_json"], {}),
            "imported_at": row["imported_at"],
            "feature_count": row["feature_count"] if "feature_count" in keys else None,
        }

    def hazard_features(self, dataset_id: int) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM hazard_features WHERE dataset_id = ? ORDER BY id",
                (dataset_id,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "dataset_id": row["dataset_id"],
                "classification": row["classification"],
                "normalized_fraction": row["normalized_value"],
                "geometry": json_value(row["geometry_geojson"], None),
                "properties": json_value(row["properties_json"], {}),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def incidents(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM historical_incidents
                ORDER BY COALESCE(incident_date, '') DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._incident_row(row) for row in rows]

    @staticmethod
    def _incident_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "incident_date": row["incident_date"],
            "incident_type": row["incident_type"],
            "severity": row["severity"],
            "barangay_id": row["barangay_id"],
            "barangay": row["barangay"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "geometry": json_value(row["geometry_geojson"], None),
            "title": row["title"],
            "description": row["description"],
            "source_metadata": json_value(row["source_metadata_json"], {}),
            "is_official": bool(row["is_official"]),
            "is_demo": bool(row["is_demo"]),
            "data_status": (
                "official" if row["is_official"] else "demonstration"
            ),
            "created_at": row["created_at"],
        }

    def clup_references(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM clup_references ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._clup_row(row) for row in rows]

    @staticmethod
    def _clup_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "reference_type": row["reference_type"],
            "title": row["title"],
            "description": row["description"],
            "document_section": row["document_section"],
            "planning_note": row["planning_note"],
            "barangay_id": row["barangay_id"],
            "geometry": json_value(row["geometry_geojson"], None),
            "source_metadata": json_value(row["source_metadata_json"], {}),
            "is_official": bool(row["is_official"]),
            "is_demo": bool(row["is_demo"]),
            "data_status": (
                "official" if row["is_official"] else "demonstration"
            ),
            "created_at": row["created_at"],
        }

    def save_assessment(
        self,
        snapshot: Mapping[str, Any],
        label: str | None,
    ) -> dict[str, Any]:
        if self.model_id is None:
            raise RepositoryError("Repository has not been initialized with a model.")
        location = snapshot["location"]
        result = snapshot["result"]
        missing = result.get("missing_inputs", [])
        incomplete_reason = (
            "Missing required hazard inputs: " + ", ".join(missing)
            if result["status"] == "incomplete"
            else None
        )
        with self.connection() as connection:
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO assessments (
                        model_id, barangay_id, location_label,
                        selected_latitude, selected_longitude, status,
                        incomplete_reason, source_snapshot_json,
                        recommendations_json, disclaimer
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, '{}', ?, ?)
                    """,
                    (
                        self.model_id,
                        (location.get("barangay") or {}).get("id"),
                        label,
                        location["latitude"],
                        location["longitude"],
                        result["status"],
                        incomplete_reason,
                        json.dumps(snapshot.get("recommendations", [])),
                        snapshot["disclaimer"],
                    ),
                )
                assessment_id = int(cursor.lastrowid)
                for hazard in snapshot["hazards"]:
                    normalized_model_value = hazard.get("normalized_value")
                    normalized_fraction = (
                        normalized_model_value / 100
                        if normalized_model_value is not None
                        else None
                    )
                    # The public assessment snapshot preserves the granular ULAP
                    # status (for example unavailable, timeout, no_intersection,
                    # or changed_schema).  This relational column intentionally
                    # stores only the model-input availability state so existing
                    # databases with the original three-value CHECK constraint
                    # remain compatible.
                    reported_availability = hazard.get(
                        "availability_status", "missing"
                    )
                    persisted_availability = (
                        reported_availability
                        if reported_availability
                        in {"available", "missing", "not_applicable"}
                        else "missing"
                    )
                    connection.execute(
                        """
                        INSERT INTO assessment_inputs (
                            assessment_id, variable_slug, classification,
                            raw_value, normalized_value, availability_status,
                            source_metadata_json, quality_notice
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            assessment_id,
                            hazard["hazard_type"],
                            hazard.get("classification"),
                            normalized_model_value,
                            normalized_fraction,
                            persisted_availability,
                            json.dumps(hazard.get("source", {})),
                            hazard.get("quality_notice"),
                        ),
                    )
                for variable, memberships in result.get("memberships", {}).items():
                    for label_name, value in memberships.items():
                        connection.execute(
                            """
                            INSERT INTO assessment_memberships (
                                assessment_id, variable_slug,
                                linguistic_label, membership_value
                            ) VALUES (?, ?, ?, ?)
                            """,
                            (assessment_id, variable, label_name, value),
                        )
                for rule in result.get("evaluated_rules", []):
                    connection.execute(
                        """
                        INSERT INTO assessment_rule_activations (
                            assessment_id, rule_code, rule_statement,
                            activation_strength, weighted_strength,
                            consequent_label, contribution
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            assessment_id,
                            rule["id"],
                            rule["statement"],
                            rule["raw_activation"],
                            rule["activation"],
                            rule["consequent"],
                            rule["activation"],
                        ),
                    )
                connection.execute(
                    """
                    INSERT INTO assessment_results (
                        assessment_id, final_score, category,
                        completeness_status, summary, data_quality_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        assessment_id,
                        result.get("score"),
                        (
                            result.get("category")
                            if result["status"] == "complete"
                            else None
                        ),
                        result["status"],
                        result["message"],
                        json.dumps(snapshot.get("data_quality_notices", [])),
                    ),
                )
                saved_snapshot = dict(snapshot)
                saved_snapshot["id"] = assessment_id
                created_at = connection.execute(
                    "SELECT created_at FROM assessments WHERE id = ?",
                    (assessment_id,),
                ).fetchone()["created_at"]
                saved_snapshot["created_at"] = created_at
                saved_snapshot["status"] = result["status"]
                connection.execute(
                    "UPDATE assessments SET source_snapshot_json = ? WHERE id = ?",
                    (
                        json.dumps(saved_snapshot, separators=(",", ":")),
                        assessment_id,
                    ),
                )
                connection.commit()
                return saved_snapshot
            except Exception:
                connection.rollback()
                raise

    def assessment(self, assessment_id: int) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT source_snapshot_json FROM assessments WHERE id = ?",
                (assessment_id,),
            ).fetchone()
        if not row:
            return None
        return json_value(row["source_snapshot_json"], {})

    def assessments(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.connection() as connection:
            count = connection.execute(
                "SELECT COUNT(*) AS count FROM assessments"
            ).fetchone()["count"]
            rows = connection.execute(
                """
                SELECT id, created_at, status, location_label,
                       selected_latitude, selected_longitude,
                       source_snapshot_json
                FROM assessments
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        items = []
        for row in rows:
            snapshot = json_value(row["source_snapshot_json"], {})
            result = snapshot.get("result", {})
            location = snapshot.get("location", {})
            items.append(
                {
                    "id": row["id"],
                    "created_at": row["created_at"],
                    "status": row["status"],
                    "location_label": row["location_label"],
                    "latitude": row["selected_latitude"],
                    "longitude": row["selected_longitude"],
                    "barangay": (location.get("barangay") or {}).get("name"),
                    "score": result.get("score"),
                    "category": result.get("category"),
                    "model_version": result.get("model_version"),
                    "report_url": f"/api/v1/assessments/{row['id']}/report",
                }
            )
        return {"items": items, "count": count, "limit": limit, "offset": offset}

    def save_report_record(
        self,
        assessment_id: int,
        pdf_content: bytes,
        snapshot: Mapping[str, Any],
    ) -> dict[str, Any]:
        digest = hashlib.sha256(pdf_content).hexdigest()
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO generated_reports (
                    assessment_id, report_format, sha256, content_snapshot_json
                ) VALUES (?, 'pdf', ?, ?)
                """,
                (
                    assessment_id,
                    digest,
                    json.dumps(snapshot, separators=(",", ":")),
                ),
            )
            report_id = int(cursor.lastrowid)
            generated_at = connection.execute(
                "SELECT generated_at FROM generated_reports WHERE id = ?",
                (report_id,),
            ).fetchone()["generated_at"]
            connection.commit()
        return {
            "id": report_id,
            "assessment_id": assessment_id,
            "sha256": digest,
            "generated_at": generated_at,
        }
