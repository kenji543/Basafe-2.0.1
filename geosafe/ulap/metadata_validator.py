"""Runtime validation of configured ArcGIS services and supplied local GeoJSON."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .arcgis_client import ArcGISClient
from .errors import UlapError
from .models import ServiceDefinition, Status, ValidationResult
from .response_parser import (
    actual_field_name,
    extract_attribution,
    extract_coded_domains,
    extract_spatial_reference,
)
from .service_registry import ServiceRegistry


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class MetadataValidator:
    def __init__(self, client: ArcGISClient, registry: ServiceRegistry) -> None:
        self.client = client
        self.registry = registry

    def validate(self, definition: ServiceDefinition) -> ValidationResult:
        checked_at = _now_iso()
        if not definition.configured or not definition.layer_url:
            reason = str(
                definition.verification.get("reason")
                or "No verified ArcGIS layer URL is configured."
            )
            return ValidationResult(
                service=definition.key,
                status=Status.UNAVAILABLE,
                required=definition.required,
                source_url=definition.layer_url,
                checked_at=checked_at,
                message=reason,
            )

        try:
            service_response = (
                self.client.service_metadata(definition.service_url)
                if definition.service_url
                else None
            )
            layer_response = self.client.layer_metadata(definition.layer_url)
        except UlapError as exc:
            return ValidationResult(
                service=definition.key,
                status=exc.status,
                required=definition.required,
                source_url=exc.endpoint or definition.layer_url,
                checked_at=checked_at,
                message=exc.message,
                http_status=exc.http_status,
                arcgis_error_code=exc.arcgis_code,
            )

        metadata = layer_response.data
        differences: list[str] = []
        layer_type = str(metadata.get("type") or "")
        if layer_type.casefold() != "feature layer":
            return ValidationResult(
                service=definition.key,
                status=Status.INVALID_LAYER,
                required=definition.required,
                source_url=definition.layer_url,
                checked_at=checked_at,
                message=f"Expected Feature Layer, received '{layer_type or 'unknown'}'.",
                metadata=_metadata_summary(metadata),
                http_status=layer_response.http_status,
            )
        try:
            returned_id = int(metadata.get("id"))
        except (TypeError, ValueError):
            returned_id = None
        if definition.layer_id is not None and returned_id != definition.layer_id:
            return ValidationResult(
                service=definition.key,
                status=Status.INVALID_LAYER,
                required=definition.required,
                source_url=definition.layer_url,
                checked_at=checked_at,
                message=(
                    f"Configured layer ID {definition.layer_id} returned metadata "
                    f"for layer ID {returned_id!r}."
                ),
                metadata=_metadata_summary(metadata),
                http_status=layer_response.http_status,
            )

        service_layers = (
            service_response.data.get("layers")
            if service_response is not None
            else None
        )
        if isinstance(service_layers, list) and definition.layer_id is not None:
            service_layer_ids = {
                int(item["id"])
                for item in service_layers
                if isinstance(item, dict)
                and isinstance(item.get("id"), (int, float))
            }
            if definition.layer_id not in service_layer_ids:
                return ValidationResult(
                    service=definition.key,
                    status=Status.INVALID_LAYER,
                    required=definition.required,
                    source_url=definition.layer_url,
                    checked_at=checked_at,
                    message="Configured layer is absent from service metadata.",
                    metadata=_metadata_summary(metadata),
                    http_status=layer_response.http_status,
                )

        if (
            definition.expected_layer_name
            and str(metadata.get("name", "")).casefold()
            != definition.expected_layer_name.casefold()
        ):
            differences.append(
                f"Layer name changed from '{definition.expected_layer_name}' "
                f"to '{metadata.get('name')}'."
            )
        if (
            definition.expected_geometry_type
            and metadata.get("geometryType") != definition.expected_geometry_type
        ):
            differences.append(
                f"Geometry type changed from '{definition.expected_geometry_type}' "
                f"to '{metadata.get('geometryType')}'."
            )

        spatial_reference = extract_spatial_reference(metadata)
        if (
            definition.expected_spatial_reference is not None
            and spatial_reference != definition.expected_spatial_reference
        ):
            differences.append(
                f"Spatial reference changed from "
                f"{definition.expected_spatial_reference} to {spatial_reference}."
            )

        capabilities = {
            capability.strip().casefold()
            for capability in str(metadata.get("capabilities") or "").split(",")
            if capability.strip()
        }
        missing_capabilities = [
            capability
            for capability in definition.required_capabilities
            if capability.casefold() not in capabilities
        ]
        if missing_capabilities:
            differences.append(
                "Missing required capabilities: " + ", ".join(missing_capabilities)
            )

        actual_classification_field = None
        live_domain: dict[str, str] = {}
        if definition.classification_field:
            actual_classification_field = actual_field_name(
                metadata, definition.classification_field
            )
            if actual_classification_field is None:
                return ValidationResult(
                    service=definition.key,
                    status=Status.MISSING_CLASSIFICATION_FIELD,
                    required=definition.required,
                    source_url=definition.layer_url,
                    checked_at=checked_at,
                    message=(
                        f"Classification field '{definition.classification_field}' "
                        "is absent from live layer metadata."
                    ),
                    metadata=_metadata_summary(metadata),
                    http_status=layer_response.http_status,
                )
            domains = extract_coded_domains(metadata)
            live_domain = domains.get(actual_classification_field, {})
            if not live_domain:
                differences.append(
                    f"No coded-value domain or unique-value renderer was found for "
                    f"'{actual_classification_field}'."
                )
            elif definition.expected_domain and live_domain != definition.expected_domain:
                differences.append(
                    f"Live classification domain differs from the configured "
                    f"expectation for '{actual_classification_field}'."
                )

        status = (
            Status.VERIFIED_CHANGED_METADATA
            if differences
            else Status.VERIFIED
        )
        message = (
            "Live service and layer metadata verified."
            if not differences
            else "Live endpoint responded, but metadata differences require review."
        )
        summary = _metadata_summary(metadata)
        summary.update(
            {
                "classification_field": actual_classification_field,
                "classification_domain": live_domain,
                "attribution": extract_attribution(metadata)
                or definition.attribution,
                "service_cache": (
                    service_response.cache.to_dict()
                    if service_response is not None
                    else None
                ),
                "layer_cache": layer_response.cache.to_dict(),
            }
        )
        return ValidationResult(
            service=definition.key,
            status=status,
            required=definition.required,
            source_url=definition.layer_url,
            checked_at=checked_at,
            message=message,
            differences=tuple(differences),
            metadata=summary,
            http_status=layer_response.http_status,
        )

    def validate_all(self) -> tuple[ValidationResult, ...]:
        return tuple(self.validate(definition) for definition in self.registry.all())

    def validate_supplied_boundary(
        self, path: Path | None = None
    ) -> ValidationResult:
        audit = self.registry.source_manifest_audit
        source_path = Path(path or str(audit.get("supplied_path") or ""))
        checked_at = _now_iso()
        if not source_path.is_file():
            return ValidationResult(
                service="supplied_barangay_boundary",
                status=Status.INACCESSIBLE,
                required=False,
                source_url=None,
                checked_at=checked_at,
                message=f"Supplied boundary file is not accessible: {source_path}",
            )
        try:
            payload = json.loads(source_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            return ValidationResult(
                service="supplied_barangay_boundary",
                status=Status.INVALID_RESPONSE,
                required=False,
                source_url=None,
                checked_at=checked_at,
                message=f"Supplied boundary file is not valid readable JSON: {exc}",
            )

        differences: list[str] = []
        checksum = _checksum(source_path)
        expected_checksum = str(audit.get("sha256") or "").casefold()
        if expected_checksum and checksum.casefold() != expected_checksum:
            differences.append("File checksum differs from the audited attachment.")
        features = payload.get("features") if isinstance(payload, dict) else None
        if (
            not isinstance(payload, dict)
            or payload.get("type") != "FeatureCollection"
            or not isinstance(features, list)
        ):
            return ValidationResult(
                service="supplied_barangay_boundary",
                status=Status.INVALID_RESPONSE,
                required=False,
                source_url=None,
                checked_at=checked_at,
                message="Supplied boundary must be a GeoJSON FeatureCollection.",
            )
        expected_count = audit.get("feature_count")
        if expected_count is not None and len(features) != int(expected_count):
            differences.append(
                f"Feature count changed from {expected_count} to {len(features)}."
            )
        geometry_types = sorted(
            {
                str((feature.get("geometry") or {}).get("type"))
                for feature in features
                if isinstance(feature, dict)
            }
        )
        if payload.get("crs") is None:
            differences.append(
                "Coordinate reference system is undeclared. The coordinate range "
                "strongly suggests EPSG:3125 (PRS92 / Philippines zone 5), but this "
                "must be confirmed by the issuing source before reprojection."
            )
        if audit.get("agency") is None:
            differences.append(
                "Issuing agency and authoritative status are not declared in the file."
            )
        status = (
            Status.CHANGED_SCHEMA
            if any("checksum" in item.casefold() for item in differences)
            else Status.PENDING_VERIFICATION
        )
        return ValidationResult(
            service="supplied_barangay_boundary",
            status=status,
            required=False,
            source_url=None,
            checked_at=checked_at,
            message=(
                "Boundary file structure checked, but it is not spatially ready "
                "or authority-verified."
            ),
            differences=tuple(differences),
            metadata={
                "path": str(source_path),
                "sha256": checksum,
                "feature_count": len(features),
                "geometry_types": geometry_types,
                "declared_crs": payload.get("crs"),
                "likely_crs": audit.get("likely_crs"),
                "likely_crs_status": audit.get("likely_crs_status"),
                "operational_use": bool(audit.get("operational_use", False)),
            },
        )


def _metadata_summary(metadata: dict[str, Any]) -> dict[str, Any]:
    fields = metadata.get("fields")
    field_items = fields if isinstance(fields, list) else []
    return {
        "id": metadata.get("id"),
        "name": metadata.get("name"),
        "type": metadata.get("type"),
        "geometry_type": metadata.get("geometryType"),
        "spatial_reference": extract_spatial_reference(metadata),
        "capabilities": metadata.get("capabilities"),
        "supported_query_formats": metadata.get("supportedQueryFormats"),
        "max_record_count": metadata.get("maxRecordCount"),
        "current_version": metadata.get("currentVersion"),
        "field_names": [
            str(field.get("name"))
            for field in field_items
            if isinstance(field, dict) and field.get("name")
        ],
        "attribution": extract_attribution(metadata),
        "description": metadata.get("description"),
    }
