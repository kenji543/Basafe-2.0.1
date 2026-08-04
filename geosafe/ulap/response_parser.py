"""Validate ArcGIS payloads and decode fields without losing raw values."""

from __future__ import annotations

from typing import Any

from .errors import ArcGISServiceError, UlapInvalidResponseError
from .models import ArcGISErrorInfo, DecodedAttributes, Status


def _error_status(code: int | None, http_status: int | None) -> Status:
    if code in {498, 499} or http_status in {401, 403}:
        return Status.AUTHENTICATION_REQUIRED
    if code == 404 or http_status == 404:
        return Status.INVALID_LAYER
    if code == 400 or http_status == 400:
        return Status.INVALID_RESPONSE
    if http_status is not None and http_status >= 500:
        return Status.SERVICE_ERROR
    return Status.SERVICE_ERROR


def parse_arcgis_error(
    payload: Any, *, http_status: int | None = None
) -> ArcGISErrorInfo | None:
    error: Any = payload.get("error") if isinstance(payload, dict) else None
    if error is None and http_status is not None and http_status >= 400:
        return ArcGISErrorInfo(
            code=http_status,
            message=f"ULAP HTTP request failed with status {http_status}.",
            details=(),
            status=_error_status(None, http_status),
            http_status=http_status,
        )
    if error is None:
        return None
    if not isinstance(error, dict):
        return ArcGISErrorInfo(
            code=None,
            message="ArcGIS returned a malformed error object.",
            details=(),
            status=Status.INVALID_RESPONSE,
            http_status=http_status,
        )
    raw_code = error.get("code")
    try:
        code = int(raw_code) if raw_code is not None else None
    except (TypeError, ValueError):
        code = None
    message = str(error.get("message") or "ArcGIS service error.")
    raw_details = error.get("details") or []
    if not isinstance(raw_details, list):
        raw_details = [raw_details]
    return ArcGISErrorInfo(
        code=code,
        message=message,
        details=tuple(str(detail) for detail in raw_details),
        status=_error_status(code, http_status),
        http_status=http_status,
    )


def raise_for_arcgis_error(
    endpoint: str, payload: Any, *, http_status: int | None = None
) -> None:
    info = parse_arcgis_error(payload, http_status=http_status)
    if info is not None:
        raise ArcGISServiceError.from_info(endpoint, info)


def extract_coded_domains(metadata: dict[str, Any]) -> dict[str, dict[str, str]]:
    domains: dict[str, dict[str, str]] = {}
    fields = metadata.get("fields") or []
    if isinstance(fields, list):
        for field in fields:
            if not isinstance(field, dict) or not field.get("name"):
                continue
            domain = field.get("domain")
            if not isinstance(domain, dict):
                continue
            coded_values = domain.get("codedValues")
            if not isinstance(coded_values, list):
                continue
            mapping = {
                str(item.get("code")): str(item.get("name"))
                for item in coded_values
                if isinstance(item, dict)
                and item.get("code") is not None
                and item.get("name") is not None
            }
            if mapping:
                domains[str(field["name"])] = mapping

    renderer = ((metadata.get("drawingInfo") or {}).get("renderer") or {})
    renderer_field = renderer.get("field1")
    unique_values = renderer.get("uniqueValueInfos")
    if renderer_field and isinstance(unique_values, list):
        rendered_mapping = {
            str(item.get("value")): str(item.get("label"))
            for item in unique_values
            if isinstance(item, dict)
            and item.get("value") is not None
            and item.get("label") is not None
        }
        domains.setdefault(str(renderer_field), rendered_mapping)
    return domains


def actual_field_name(metadata: dict[str, Any], expected: str) -> str | None:
    wanted = expected.casefold()
    fields = metadata.get("fields")
    if not isinstance(fields, list):
        return None
    for item in fields:
        if isinstance(item, dict) and str(item.get("name", "")).casefold() == wanted:
            return str(item["name"])
    return None


def decode_attributes(
    attributes: dict[str, Any],
    domains: dict[str, dict[str, str]],
) -> DecodedAttributes:
    decoded = dict(attributes)
    unknown: dict[str, Any] = {}
    domain_by_casefold = {
        field.casefold(): mapping for field, mapping in domains.items()
    }
    for field, raw_value in attributes.items():
        mapping = domain_by_casefold.get(str(field).casefold())
        if not mapping or raw_value is None:
            continue
        lookup = str(raw_value)
        if lookup in mapping:
            decoded[field] = mapping[lookup]
        else:
            unknown[field] = raw_value
    return DecodedAttributes(raw=dict(attributes), decoded=decoded, unknown_codes=unknown)


def feature_attributes(feature: Any) -> dict[str, Any]:
    if not isinstance(feature, dict):
        raise ValueError("ArcGIS feature must be an object.")
    attributes = feature.get("attributes")
    if attributes is None:
        attributes = feature.get("properties")
    if not isinstance(attributes, dict):
        raise ValueError("ArcGIS feature has no attributes/properties object.")
    return dict(attributes)


def response_features(endpoint: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    if "features" not in payload:
        raise UlapInvalidResponseError(
            endpoint,
            "ArcGIS query response does not contain a features array.",
        )
    features = payload["features"]
    if not isinstance(features, list):
        raise UlapInvalidResponseError(
            endpoint,
            "ArcGIS query response features value is not an array.",
        )
    if not all(isinstance(feature, dict) for feature in features):
        raise UlapInvalidResponseError(
            endpoint,
            "ArcGIS query response contains a non-object feature.",
        )
    return features


def extract_spatial_reference(metadata: dict[str, Any]) -> int | None:
    candidates = [
        metadata.get("sourceSpatialReference"),
        metadata.get("spatialReference"),
        (metadata.get("extent") or {}).get("spatialReference"),
    ]
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        value = candidate.get("latestWkid") or candidate.get("wkid")
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            continue
    return None


def extract_attribution(metadata: dict[str, Any]) -> str | None:
    value = metadata.get("copyrightText") or metadata.get("serviceDescription")
    return str(value).strip() if value and str(value).strip() else None


def metadata_version(metadata: dict[str, Any]) -> str | None:
    version = metadata.get("currentVersion")
    editing = metadata.get("editingInfo")
    last_edit = editing.get("lastEditDate") if isinstance(editing, dict) else None
    values = [str(value) for value in (version, last_edit) if value is not None]
    return ":".join(values) if values else None
