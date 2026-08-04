"""High-level ULAP facade used by the GeoSafe-FIS application service."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..geometry import geometry_bbox
from .arcgis_client import ArcGISClient
from .boundary_provider import BoundaryProvider
from .errors import UlapError
from .hazard_provider import HazardProvider
from .metadata_validator import MetadataValidator
from .models import HazardResult, Status, ValidationResult
from .response_parser import (
    extract_attribution,
    extract_coded_domains,
    extract_spatial_reference,
)
from .service_registry import DEFAULT_REGISTRY_PATH, ServiceRegistry


BASEY_FILTER = "city_name='Basey' AND prov_name='Samar'"
REQUIRED_HAZARDS = ("flood", "liquefaction", "ground_shaking")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _status_value(value: Status | str) -> str:
    return value.value if isinstance(value, Status) else str(value)


class UlapIntegration:
    """Own the live registry, client, providers, and runtime validation state."""

    def __init__(
        self,
        registry: ServiceRegistry,
        client: ArcGISClient,
    ) -> None:
        self.registry = registry
        self.client = client
        self.hazards = HazardProvider(client, registry)
        self.boundaries = BoundaryProvider(client, registry)
        self.validator = MetadataValidator(client, registry)
        self._validation: dict[str, ValidationResult] = {}
        self._validation_lock = threading.RLock()

    @classmethod
    def from_environment(
        cls, registry_path: str | Path | None = None
    ) -> "UlapIntegration":
        registry = ServiceRegistry(
            Path(registry_path) if registry_path else DEFAULT_REGISTRY_PATH
        )
        return cls(registry, ArcGISClient.from_registry(registry))

    def validate_services(self, *, force: bool = False) -> list[dict[str, Any]]:
        with self._validation_lock:
            if force:
                self.client.clear_cache()
            results = self.validator.validate_all()
            self._validation = {result.service: result for result in results}
            return [result.to_dict() for result in results]

    def status(self, *, refresh: bool = False) -> dict[str, Any]:
        with self._validation_lock:
            if refresh or not self._validation:
                results = self.validate_services(force=refresh)
            else:
                results = [
                    self._validation[key].to_dict()
                    for key in sorted(self._validation)
                ]
        required_failures = [
            result
            for result in results
            if result.get("required")
            and result.get("status")
            != Status.VERIFIED.value
        ]
        return {
            "status": "degraded" if required_failures else "verified",
            "complete_assessment_available": not required_failures,
            "checked_at": _now_iso(),
            "services": results,
            "required_failures": required_failures,
            "notice": (
                "Service availability is reported independently. A required "
                "hazard failure blocks the three-hazard score."
            ),
        }

    def services(self) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        for definition in self.registry.all():
            item = definition.to_dict()
            runtime_validation = (
                self._validation[definition.key].to_dict()
                if definition.key in self._validation
                else {
                    "service": definition.key,
                    "status": "pending_verification",
                    "message": "Runtime metadata validation has not run in this process.",
                }
            )
            item["runtime_validation"] = runtime_validation
            item["name"] = (
                definition.expected_layer_name
                or definition.key.replace("_", " ").title()
            )
            item["hazard_type"] = (
                definition.key if definition.dataset_type == "hazard" else None
            )
            item["verification_status"] = (
                runtime_validation.get("status")
                if runtime_validation.get("status") != "pending_verification"
                else definition.verification.get(
                    "status", "pending_verification"
                )
            )
            item["classification_domain"] = definition.expected_domain
            item["display_url"] = (
                f"/hazard-layers/{definition.key}/features"
                if definition.dataset_type == "hazard"
                and definition.configured
                else None
            )
            items.append(item)
        return {
            "items": items,
            "count": len(items),
            "manifest_audit": self.registry.source_manifest_audit,
        }

    def service_metadata(self, key: str) -> dict[str, Any]:
        definition = self.registry.get(key)
        result = self.validator.validate(definition)
        with self._validation_lock:
            self._validation[key] = result
        return {
            "service": definition.to_dict(),
            "validation": result.to_dict(),
        }

    def identify(self, latitude: float, longitude: float) -> dict[str, Any]:
        result = self.boundaries.identify(longitude, latitude)
        return result.to_dict()

    def hazard_at_location(
        self, hazard: str, latitude: float, longitude: float
    ) -> dict[str, Any]:
        return self.hazards.at_location(hazard, longitude, latitude).to_dict()

    def hazards_at_location(
        self, latitude: float, longitude: float
    ) -> dict[str, Any]:
        results = self.hazards.all_at_location(longitude, latitude)
        return {
            "hazards": {
                key: value.to_dict()
                for key, value in results.items()
            },
            "assessment": self.hazards.assessment_gate(results),
            "retrievedAt": _now_iso(),
        }

    def boundary_geojson(self, kind: str) -> dict[str, Any]:
        if kind not in {"municipal_boundary", "barangay_boundary"}:
            raise ValueError("Boundary kind must be municipal_boundary or barangay_boundary.")
        definition = self.registry.get(kind)
        if not definition.configured or not definition.layer_url:
            return self._empty_collection(
                kind,
                Status.UNAVAILABLE,
                "No verified live boundary layer is configured.",
                definition.layer_url,
            )
        try:
            page_size = self._page_size(definition.layer_url)
            result = self.client.query_all(
                definition.layer_url,
                where=BASEY_FILTER,
                out_fields=definition.preserve_fields or "*",
                return_geometry=True,
                response_format="geojson",
                page_size=page_size,
            )
        except UlapError as exc:
            return self._empty_collection(
                kind, exc.status, exc.message, exc.endpoint or definition.layer_url
            )
        return {
            "type": "FeatureCollection",
            "features": list(result.features),
            "status": Status.AVAILABLE.value if result.features else Status.NO_INTERSECTION.value,
            "dataset": {
                "key": definition.key,
                "agency": definition.agency,
                "sourceUrl": definition.layer_url,
                "attribution": definition.attribution,
                "spatialReference": 4326,
                "retrievedAt": result.retrieved_at,
                "pages": result.pages,
                "cache": [item.to_dict() for item in result.cache_entries],
                "filter": BASEY_FILTER,
            },
            "notices": (
                []
                if result.features
                else [
                    "The live boundary query returned no Basey features. This "
                    "does not authorize an assessment."
                ]
            ),
        }

    def hazard_geojson(self, hazard: str) -> dict[str, Any]:
        definition = self.registry.get(hazard)
        if definition.dataset_type != "hazard":
            raise ValueError(f"'{hazard}' is not a hazard service.")
        if not definition.configured or not definition.layer_url:
            return self._empty_collection(
                hazard,
                Status.UNAVAILABLE,
                str(
                    definition.verification.get("reason")
                    or "No verified live hazard layer is configured."
                ),
                definition.layer_url,
            )
        municipal = self.boundary_geojson("municipal_boundary")
        features = municipal.get("features")
        if not isinstance(features, list) or not features:
            return self._empty_collection(
                hazard,
                Status.OUTSIDE_COVERAGE,
                "Basey extent could not be established from the live municipal layer.",
                definition.layer_url,
            )
        bboxes = [
            geometry_bbox(feature["geometry"])
            for feature in features
            if isinstance(feature, dict) and isinstance(feature.get("geometry"), dict)
        ]
        if not bboxes:
            return self._empty_collection(
                hazard,
                Status.INVALID_RESPONSE,
                "The live Basey boundary response contains no usable geometry.",
                definition.layer_url,
            )
        xmin = min(item[0] for item in bboxes)
        ymin = min(item[1] for item in bboxes)
        xmax = max(item[2] for item in bboxes)
        ymax = max(item[3] for item in bboxes)
        envelope = json.dumps(
            {
                "xmin": xmin,
                "ymin": ymin,
                "xmax": xmax,
                "ymax": ymax,
                "spatialReference": {"wkid": 4326},
            },
            separators=(",", ":"),
        )
        try:
            metadata_response = self.client.layer_metadata(definition.layer_url)
            metadata = metadata_response.data
            domains = extract_coded_domains(metadata)
            field_name = definition.classification_field or ""
            domain = domains.get(field_name, {})
            result = self.client.query_all(
                definition.layer_url,
                out_fields=definition.preserve_fields or "*",
                return_geometry=True,
                response_format="geojson",
                page_size=self._page_size(definition.layer_url, metadata),
                geometry=envelope,
                geometry_type="esriGeometryEnvelope",
                input_spatial_reference=4326,
            )
        except UlapError as exc:
            return self._empty_collection(
                hazard, exc.status, exc.message, exc.endpoint or definition.layer_url
            )
        rendered_features: list[dict[str, Any]] = []
        for feature in result.features:
            rendered = dict(feature)
            properties = dict(rendered.get("properties") or {})
            raw_code = properties.get(field_name)
            properties["officialLabel"] = (
                domain.get(str(raw_code)) if raw_code is not None else None
            )
            rendered["properties"] = properties
            rendered_features.append(rendered)
        return {
            "type": "FeatureCollection",
            "features": rendered_features,
            "status": Status.AVAILABLE.value if rendered_features else Status.NO_INTERSECTION.value,
            "dataset": {
                "key": definition.key,
                "agency": definition.agency,
                "sourceUrl": definition.layer_url,
                "classificationField": field_name or None,
                "classificationDomain": domain,
                "attribution": extract_attribution(metadata) or definition.attribution,
                "spatialReference": extract_spatial_reference(metadata),
                "retrievedAt": result.retrieved_at,
                "pages": result.pages,
                "cache": [item.to_dict() for item in result.cache_entries],
                "queryExtent": [xmin, ymin, xmax, ymax],
            },
            "notices": (
                []
                if rendered_features
                else [
                    "The verified layer returned no features intersecting the "
                    "Basey bounding box. This is not a Low or Safe classification."
                ]
            ),
        }

    def assessment_hazards(
        self,
        latitude: float,
        longitude: float,
        model: Any,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        results = self.hazards.all_at_location(longitude, latitude)
        hazards: list[dict[str, Any]] = []
        notices: list[str] = []
        for key in REQUIRED_HAZARDS:
            result = results[key]
            rendered = self._assessment_hazard(result, model)
            hazards.append(rendered)
            notices.extend(
                f"{key.replace('_', ' ').title()}: {warning}"
                for warning in rendered.get("warnings", [])
            )
        return hazards, notices

    @staticmethod
    def _assessment_hazard(result: HazardResult, model: Any) -> dict[str, Any]:
        key = result.hazard
        status = _status_value(result.status)
        normalization = dict(
            (model.inputs.get(key) or {}).get("normalization") or {}
        )
        mappings = normalization.get("classification_mappings")
        mapping = (
            mappings.get(str(result.raw_code))
            if isinstance(mappings, dict) and result.raw_code is not None
            else None
        )
        warnings = list(result.warnings)
        normalized_value: float | None = None
        if result.status == Status.AVAILABLE:
            if not isinstance(mapping, dict):
                status = Status.CHANGED_SCHEMA.value
                warnings.append(
                    f"No model transformation is configured for official code "
                    f"'{result.raw_code}'."
                )
            elif str(mapping.get("official_label")) != str(result.official_label):
                status = Status.CHANGED_SCHEMA.value
                warnings.append(
                    "The live official label differs from the model transformation "
                    "configuration; normalization is blocked."
                )
            else:
                try:
                    candidate = float(mapping["normalized_value"])
                except (KeyError, TypeError, ValueError):
                    status = Status.CHANGED_SCHEMA.value
                    warnings.append("Configured normalized value is invalid.")
                else:
                    if 0 <= candidate <= 100:
                        normalized_value = candidate
                    else:
                        status = Status.CHANGED_SCHEMA.value
                        warnings.append(
                            "Configured normalized value lies outside 0–100."
                        )
        available = status == Status.AVAILABLE.value and normalized_value is not None
        cache = result.cache.to_dict() if result.cache else None
        source = {
            "dataset_slug": key,
            "dataset_name": key.replace("_", " ").title(),
            "source_name": result.agency,
            "source_date": result.data_date,
            "source_url": result.source_url,
            "quality_status": status,
            "is_official": True,
            "is_demo": False,
            "data_status": status,
            "metadata": {
                "agency": result.agency,
                "service": result.service,
                "layer_id": result.layer_id,
                "classification_field": result.classification_field,
                "raw_code": result.raw_code,
                "official_label": result.official_label,
                "spatial_reference": result.spatial_reference,
                "retrieved_at": result.retrieved_at,
                "attribution": result.attribution,
                "cache": cache,
            },
        }
        quality_notice = "; ".join(warnings) or None
        if not available and quality_notice is None:
            quality_notice = (
                f"Status is {status}. Missing information is not low vulnerability."
            )
        return {
            "hazard_type": key,
            "hazard": key,
            "name": key.replace("_", " ").title(),
            "status": status,
            # Preserve the granular live condition in `status`; this field is
            # the coarse completeness state consumed by the fuzzy workflow and
            # persisted by the three-value assessment_inputs schema.
            "availability_status": "available" if available else "missing",
            "classification": result.official_label,
            "official_label": result.official_label,
            "raw_code": result.raw_code,
            "classification_field": result.classification_field,
            "raw_attributes": result.raw_attributes,
            "decoded_attributes": result.decoded_attributes,
            "normalized_value": normalized_value if available else None,
            "normalized_fraction": (
                normalized_value / 100 if available and normalized_value is not None else None
            ),
            "model_transformation": {
                "official_value": {
                    "code": result.raw_code,
                    "label": result.official_label,
                },
                "normalized_value": normalized_value if available else None,
                "mapping": mapping,
                "method": normalization.get("method"),
                "model_version": model.version,
                "validation_requirement": normalization.get(
                    "validation_requirement"
                ),
                "notice": (
                    "This normalized index is a GeoSafe-FIS model transformation, "
                    "not an official agency numerical rating."
                ),
            },
            "normalization": normalization,
            "source": source,
            "source_name": result.agency,
            "source_date": result.data_date,
            "source_url": result.source_url,
            "retrieved_at": result.retrieved_at,
            "spatial_reference": result.spatial_reference,
            "attribution": result.attribution,
            "cache": cache,
            "warnings": warnings,
            "quality_status": status,
            "is_official": True,
            "is_demo": False,
            "data_status": status,
            "quality_notice": quality_notice,
            "feature_count": result.feature_count,
        }

    def _page_size(
        self, layer_url: str, metadata: dict[str, Any] | None = None
    ) -> int:
        if metadata is None:
            metadata = self.client.layer_metadata(layer_url).data
        try:
            value = int(metadata.get("maxRecordCount") or 2000)
        except (TypeError, ValueError):
            value = 2000
        return max(1, min(value, 50000))

    @staticmethod
    def _empty_collection(
        key: str,
        status: Status | str,
        notice: str,
        source_url: str | None,
    ) -> dict[str, Any]:
        return {
            "type": "FeatureCollection",
            "features": [],
            "status": _status_value(status),
            "dataset": {
                "key": key,
                "sourceUrl": source_url,
                "retrievedAt": _now_iso(),
            },
            "notices": [notice],
        }
