"""Validated Pydantic v2 data contracts for the ULAP integration."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Status(str, Enum):
    AVAILABLE = "available"
    NO_INTERSECTION = "no_intersection"
    OUTSIDE_COVERAGE = "outside_coverage"
    UNAVAILABLE = "unavailable"
    AUTHENTICATION_REQUIRED = "authentication_required"
    SERVICE_ERROR = "service_error"
    TIMEOUT = "timeout"
    INVALID_RESPONSE = "invalid_response"
    CHANGED_SCHEMA = "changed_schema"
    INCOMPLETE = "incomplete"
    PENDING_VERIFICATION = "pending_verification"
    VERIFIED = "verified"
    VERIFIED_CHANGED_METADATA = "verified_with_changed_metadata"
    INACCESSIBLE = "inaccessible"
    INVALID_LAYER = "invalid_layer"
    MISSING_CLASSIFICATION_FIELD = "missing_classification_field"


class Serializable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class CacheMetadata(Serializable):
    source_url: str = Field(min_length=1)
    retrieved_at: str = Field(min_length=1)
    expires_at: str = Field(min_length=1)
    from_cache: bool
    stale: bool = False
    metadata_version: str | None = None


class ArcGISErrorInfo(Serializable):
    code: int | None
    message: str = Field(min_length=1)
    details: tuple[str, ...]
    status: Status
    http_status: int | None = Field(default=None, ge=100, le=599)


class ArcGISResponse(Serializable):
    data: dict[str, Any]
    source_url: str = Field(min_length=1)
    requested_at: str = Field(min_length=1)
    responded_at: str = Field(min_length=1)
    duration_ms: float = Field(ge=0)
    http_status: int = Field(ge=100, le=599)
    cache: CacheMetadata


class DecodedAttributes(Serializable):
    raw: dict[str, Any]
    decoded: dict[str, Any]
    unknown_codes: dict[str, Any] = Field(default_factory=dict)


class ServiceDefinition(Serializable):
    key: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    dataset_type: str = Field(pattern=r"^(hazard|boundary)$")
    required: bool
    configured: bool
    agency: str | None
    attribution: str | None
    service_url: str | None
    layer_url: str | None
    layer_id: int | None = Field(default=None, ge=0)
    expected_layer_name: str | None
    expected_geometry_type: str | None
    classification_field: str | None
    expected_spatial_reference: int | None = Field(default=None, gt=0)
    expected_domain: dict[str, str]
    preserve_fields: tuple[str, ...]
    identity_fields: dict[str, str]
    required_capabilities: tuple[str, ...]
    verification: dict[str, Any]

    @model_validator(mode="after")
    def configured_service_has_urls(self) -> "ServiceDefinition":
        if self.configured and (not self.service_url or not self.layer_url):
            raise ValueError("configured services require service_url and layer_url")
        if not self.configured and (self.service_url or self.layer_url):
            raise ValueError("unconfigured services cannot expose active URLs")
        if self.dataset_type == "hazard" and self.configured and not self.classification_field:
            raise ValueError("configured hazard services require classification_field")
        return self


class ValidationResult(Serializable):
    service: str = Field(min_length=1)
    status: Status
    required: bool
    source_url: str | None
    checked_at: str = Field(min_length=1)
    message: str = Field(min_length=1)
    differences: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)
    http_status: int | None = Field(default=None, ge=100, le=599)
    arcgis_error_code: int | None = None


class PaginatedResult(Serializable):
    features: tuple[dict[str, Any], ...]
    pages: int = Field(ge=1)
    source_url: str = Field(min_length=1)
    retrieved_at: str = Field(min_length=1)
    cache_entries: tuple[CacheMetadata, ...]


class FeatureCollectionResult(Serializable):
    status: Status
    dataset: str = Field(min_length=1)
    feature_collection: dict[str, Any]
    source_url: str | None
    retrieved_at: str
    pages: int = Field(default=0, ge=0)
    cache_entries: tuple[CacheMetadata, ...] = ()
    attribution: str | None = None
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def valid_geojson_feature_collection(self) -> "FeatureCollectionResult":
        if self.feature_collection.get("type") != "FeatureCollection":
            raise ValueError("feature_collection.type must be FeatureCollection")
        if not isinstance(self.feature_collection.get("features"), list):
            raise ValueError("feature_collection.features must be a list")
        if not all(
            isinstance(feature, dict)
            for feature in self.feature_collection["features"]
        ):
            raise ValueError("every feature_collection feature must be an object")
        return self


class PointQueryResult(Serializable):
    status: Status
    source_url: str = Field(min_length=1)
    retrieved_at: str = Field(min_length=1)
    features: tuple[dict[str, Any], ...]
    feature_count: int = Field(ge=0)
    multiple_intersections: bool
    cache: CacheMetadata
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def feature_count_matches(self) -> "PointQueryResult":
        if self.feature_count != len(self.features):
            raise ValueError("feature_count must match features")
        if self.multiple_intersections != (self.feature_count > 1):
            raise ValueError("multiple_intersections must match feature_count")
        return self


class HazardResult(Serializable):
    hazard: str = Field(min_length=1)
    status: Status
    agency: str | None
    service: str | None
    layer_id: int | None = Field(default=None, ge=0)
    classification_field: str | None
    raw_code: Any
    official_label: str | None
    raw_attributes: dict[str, Any]
    decoded_attributes: dict[str, Any]
    intersections: tuple[dict[str, Any], ...] = ()
    source_url: str | None
    spatial_reference: int | None = Field(default=None, gt=0)
    retrieved_at: str = Field(min_length=1)
    data_date: Any = None
    attribution: str | None = None
    warnings: tuple[str, ...] = ()
    feature_count: int = Field(default=0, ge=0)
    cache: CacheMetadata | None = None

    @model_validator(mode="after")
    def available_result_has_official_value(self) -> "HazardResult":
        if self.status == Status.AVAILABLE and (
            self.raw_code is None or not self.official_label
        ):
            raise ValueError(
                "available hazard results require raw_code and official_label"
            )
        if self.feature_count != len(self.intersections):
            raise ValueError("feature_count must match intersections")
        return self


class BoundaryIdentification(Serializable):
    status: Status
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    inside_basey: bool
    municipality: str | None
    province: str | None
    barangay: str | None
    municipality_code: str | None = None
    province_code: str | None = None
    barangay_code: str | None = None
    psgc: str | None = None
    source_urls: tuple[str, ...] = ()
    retrieved_at: str | None = None
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def basey_identity_is_consistent(self) -> "BoundaryIdentification":
        if self.inside_basey and (
            str(self.municipality or "").casefold() != "basey"
            or str(self.province or "").casefold() != "samar"
        ):
            raise ValueError(
                "inside_basey results must identify Basey municipality and Samar province"
            )
        return self
