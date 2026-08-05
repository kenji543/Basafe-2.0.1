"""Normalize live ULAP hazard responses while preserving official values."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

from .arcgis_client import ArcGISClient
from .errors import UlapError, UlapInvalidResponseError
from .models import (
    CacheMetadata,
    FeatureCollectionResult,
    HazardResult,
    PointQueryResult,
    Status,
)
from .response_parser import (
    actual_field_name,
    decode_attributes,
    extract_attribution,
    extract_coded_domains,
    extract_spatial_reference,
    feature_attributes,
)
from .service_registry import ServiceRegistry


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class HazardProvider:
    """Retrieve official labels; model normalization remains a separate concern."""

    def __init__(self, client: ArcGISClient, registry: ServiceRegistry) -> None:
        self.client = client
        self.registry = registry

    def at_location(
        self, hazard: str, longitude: float, latitude: float
    ) -> HazardResult:
        definition = self.registry.get(hazard)
        if definition.dataset_type != "hazard":
            raise ValueError(f"'{hazard}' is not a hazard service.")
        if not definition.configured or not definition.layer_url:
            return self._unavailable(
                hazard,
                definition,
                str(
                    definition.verification.get("reason")
                    or "No verified layer URL is configured."
                ),
            )
        try:
            metadata_response = self.client.layer_metadata(definition.layer_url)
            metadata = metadata_response.data
            if not definition.classification_field:
                return self._status_result(
                    hazard,
                    definition,
                    Status.CHANGED_SCHEMA,
                    "No classification field is configured.",
                    metadata_response.cache,
                    metadata_response.responded_at,
                )
            field_name = actual_field_name(metadata, definition.classification_field)
            if field_name is None:
                return self._status_result(
                    hazard,
                    definition,
                    Status.CHANGED_SCHEMA,
                    (
                        f"Live metadata is missing classification field "
                        f"'{definition.classification_field}'."
                    ),
                    metadata_response.cache,
                    metadata_response.responded_at,
                )
            domains = extract_coded_domains(metadata)
            live_domain = domains.get(field_name, {})
            try:
                query = self.client.point_query(
                    definition.layer_url,
                    longitude,
                    latitude,
                    out_fields="*",
                    return_geometry=False,
                )
            except UlapError as query_error:
                query = self._identify_at_location(
                    definition,
                    field_name,
                    live_domain,
                    longitude,
                    latitude,
                    query_error,
                )
        except UlapError as exc:
            return HazardResult(
                hazard=hazard,
                status=exc.status,
                agency=definition.agency,
                service=definition.service_url,
                layer_id=definition.layer_id,
                classification_field=definition.classification_field,
                raw_code=None,
                official_label=None,
                raw_attributes={},
                decoded_attributes={},
                source_url=exc.endpoint or definition.layer_url,
                spatial_reference=None,
                retrieved_at=_now_iso(),
                attribution=definition.attribution,
                warnings=(exc.message,),
            )

        if query.status == Status.NO_INTERSECTION:
            outside_extent = _outside_wgs84_extent(
                metadata, longitude, latitude
            )
            return HazardResult(
                hazard=hazard,
                status=(
                    Status.OUTSIDE_COVERAGE
                    if outside_extent
                    else Status.NO_INTERSECTION
                ),
                agency=definition.agency,
                service=definition.service_url,
                layer_id=definition.layer_id,
                classification_field=field_name,
                raw_code=None,
                official_label=None,
                raw_attributes={},
                decoded_attributes={},
                source_url=definition.layer_url,
                spatial_reference=extract_spatial_reference(metadata),
                retrieved_at=query.retrieved_at,
                attribution=extract_attribution(metadata) or definition.attribution,
                warnings=(
                    (
                        "The point is outside the extent declared by the live "
                        "layer. This is not a Low or Safe classification."
                        if outside_extent
                        else "No intersecting hazard polygon was returned. This "
                        "is not a Low or Safe classification."
                    ),
                ),
                feature_count=0,
                cache=query.cache,
            )

        attributes = [feature_attributes(feature) for feature in query.features]
        field_lookup = field_name.casefold()
        raw_codes: list[Any] = []
        for item in attributes:
            value = next(
                (
                    value
                    for name, value in item.items()
                    if str(name).casefold() == field_lookup
                ),
                None,
            )
            raw_codes.append(value)
        unique_codes = {str(code) for code in raw_codes}
        if len(unique_codes) > 1:
            return HazardResult(
                hazard=hazard,
                status=Status.INVALID_RESPONSE,
                agency=definition.agency,
                service=definition.service_url,
                layer_id=definition.layer_id,
                classification_field=field_name,
                raw_code=None,
                official_label=None,
                raw_attributes={"intersections": attributes},
                decoded_attributes={},
                intersections=tuple(attributes),
                source_url=definition.layer_url,
                spatial_reference=extract_spatial_reference(metadata),
                retrieved_at=query.retrieved_at,
                attribution=extract_attribution(metadata) or definition.attribution,
                warnings=(
                    "Multiple intersecting polygons returned conflicting official "
                    "classification codes; no code was selected.",
                ),
                feature_count=len(attributes),
                cache=query.cache,
            )

        raw_code = raw_codes[0] if raw_codes else None
        decoded = decode_attributes(attributes[0], domains)
        official_label = (
            live_domain.get(str(raw_code)) if raw_code is not None else None
        )
        warnings = list(query.warnings)
        status = Status.AVAILABLE
        if raw_code is None:
            status = Status.CHANGED_SCHEMA
            warnings.append(
                f"Returned feature has no value for '{field_name}'."
            )
        elif official_label is None:
            status = Status.CHANGED_SCHEMA
            warnings.append(
                f"Unknown live classification code '{raw_code}' for '{field_name}'; "
                "it was not reinterpreted."
            )
        if not live_domain:
            status = Status.CHANGED_SCHEMA
            warnings.append(
                f"Live metadata provides no coded domain or renderer for '{field_name}'."
            )
        elif definition.expected_domain and live_domain != definition.expected_domain:
            status = Status.CHANGED_SCHEMA
            warnings.append(
                "Live classification domain differs from the model-reviewed "
                "registry; official values are preserved but model use is blocked."
            )
        if len(attributes) > 1:
            warnings.append(
                f"{len(attributes)} overlapping polygons returned the same code "
                f"'{raw_code}'."
            )
        data_date = _first_value(
            attributes[0],
            ("publishdate", "datemapped", "last_edited_date", "created_date"),
        )
        return HazardResult(
            hazard=hazard,
            status=status,
            agency=definition.agency,
            service=definition.service_url,
            layer_id=definition.layer_id,
            classification_field=field_name,
            raw_code=raw_code,
            official_label=official_label,
            raw_attributes=dict(attributes[0]),
            decoded_attributes=decoded.decoded,
            intersections=tuple(attributes),
            source_url=definition.layer_url,
            spatial_reference=extract_spatial_reference(metadata),
            retrieved_at=query.retrieved_at,
            data_date=data_date,
            attribution=extract_attribution(metadata) or definition.attribution,
            warnings=tuple(warnings),
            feature_count=len(attributes),
            cache=query.cache,
        )

    def _identify_at_location(
        self,
        definition: Any,
        field_name: str,
        live_domain: dict[str, str],
        longitude: float,
        latitude: float,
        query_error: UlapError,
    ) -> PointQueryResult:
        if not definition.service_url or definition.layer_id is None:
            raise query_error
        delta = 0.05
        extent = (
            max(-180.0, longitude - delta),
            max(-90.0, latitude - delta),
            min(180.0, longitude + delta),
            min(90.0, latitude + delta),
        )
        response = self.client.identify_features(
            definition.service_url,
            layer_id=definition.layer_id,
            geometry=f"{longitude:.8f},{latitude:.8f}",
            geometry_type="esriGeometryPoint",
            map_extent=extent,
            return_geometry=False,
            tolerance=0,
        )
        results = response.data.get("results")
        if not isinstance(results, list):
            raise UlapInvalidResponseError(
                definition.service_url,
                "ArcGIS identify response does not contain a results array.",
            )
        reverse_domain = {label: code for code, label in live_domain.items()}
        features: list[dict[str, Any]] = []
        for result in results:
            if not isinstance(result, dict) or result.get("layerId") != definition.layer_id:
                continue
            attributes = result.get("attributes")
            if not isinstance(attributes, dict):
                raise UlapInvalidResponseError(
                    definition.service_url,
                    "ArcGIS identify returned invalid feature attributes.",
                )
            official_label = str(result.get("value") or "").strip()
            raw_code = reverse_domain.get(official_label)
            properties = dict(attributes)
            properties[field_name] = (
                raw_code if raw_code is not None else f"unmapped:{official_label}"
            )
            features.append({"attributes": properties})
        warnings = [
            "The layer rejected its advertised Query operation; the official "
            "MapServer identify operation supplied the point result instead."
        ]
        if len(features) > 1:
            warnings.append(
                f"{len(features)} intersecting features were returned; their "
                "classification codes must agree."
            )
        return PointQueryResult(
            status=Status.AVAILABLE if features else Status.NO_INTERSECTION,
            source_url=definition.layer_url,
            retrieved_at=response.responded_at,
            features=tuple(features),
            feature_count=len(features),
            multiple_intersections=len(features) > 1,
            cache=response.cache,
            warnings=tuple(warnings),
        )

    def all_at_location(
        self, longitude: float, latitude: float
    ) -> dict[str, HazardResult]:
        return {
            definition.key: self.at_location(
                definition.key, longitude, latitude
            )
            for definition in self.registry.hazards()
        }

    def basey_bbox_geojson(
        self,
        hazard: str,
        bbox: tuple[float, float, float, float],
    ) -> FeatureCollectionResult:
        """Return paginated live hazard GeoJSON clipped by a caller-supplied Basey bbox."""
        definition = self.registry.get(hazard)
        if definition.dataset_type != "hazard":
            raise ValueError(f"'{hazard}' is not a hazard service.")
        if not definition.configured or not definition.layer_url:
            return FeatureCollectionResult(
                status=Status.UNAVAILABLE,
                dataset=hazard,
                feature_collection={"type": "FeatureCollection", "features": []},
                source_url=None,
                retrieved_at=_now_iso(),
                attribution=definition.attribution,
                warnings=(
                    str(
                        definition.verification.get("reason")
                        or "No verified layer URL is configured."
                    ),
                ),
            )
        xmin, ymin, xmax, ymax = _validated_bbox(bbox)
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
            result = self.client.query_all(
                definition.layer_url,
                out_fields="*",
                return_geometry=True,
                response_format="geojson",
                page_size=2000,
                geometry=envelope,
                geometry_type="esriGeometryEnvelope",
                input_spatial_reference=4326,
            )
        except UlapError as exc:
            return FeatureCollectionResult(
                status=exc.status,
                dataset=hazard,
                feature_collection={"type": "FeatureCollection", "features": []},
                source_url=exc.endpoint or definition.layer_url,
                retrieved_at=_now_iso(),
                attribution=definition.attribution,
                warnings=(exc.message,),
            )
        status = Status.AVAILABLE if result.features else Status.NO_INTERSECTION
        warnings = (
            ()
            if result.features
            else (
                "No hazard polygons intersect the requested extent. This does not "
                "mean Low or Safe.",
            )
        )
        return FeatureCollectionResult(
            status=status,
            dataset=hazard,
            feature_collection={
                "type": "FeatureCollection",
                "features": list(result.features),
            },
            source_url=definition.layer_url,
            retrieved_at=result.retrieved_at,
            pages=result.pages,
            cache_entries=result.cache_entries,
            attribution=definition.attribution,
            warnings=warnings,
        )

    @staticmethod
    def assessment_gate(results: dict[str, HazardResult]) -> dict[str, Any]:
        required = ("flood", "liquefaction", "ground_shaking")
        missing = [
            hazard
            for hazard in required
            if hazard not in results or results[hazard].status != Status.AVAILABLE
        ]
        if missing:
            return {
                "assessmentStatus": "incomplete",
                "score": None,
                "category": None,
                "missingInputs": missing,
                "message": (
                    "A complete assessment cannot be calculated because verified "
                    "values are unavailable for: " + ", ".join(missing) + "."
                ),
            }
        return {
            "assessmentStatus": "ready",
            "score": None,
            "category": None,
            "missingInputs": [],
            "message": (
                "All official hazard classifications are available. Apply the "
                "separately configured and validated fuzzy transformation next."
            ),
        }

    def _unavailable(
        self, hazard: str, definition: Any, reason: str
    ) -> HazardResult:
        return HazardResult(
            hazard=hazard,
            status=Status.UNAVAILABLE,
            agency=definition.agency,
            service=None,
            layer_id=None,
            classification_field=None,
            raw_code=None,
            official_label=None,
            raw_attributes={},
            decoded_attributes={},
            source_url=None,
            spatial_reference=None,
            retrieved_at=_now_iso(),
            attribution=definition.attribution,
            warnings=(reason,),
        )

    def _status_result(
        self,
        hazard: str,
        definition: Any,
        status: Status,
        warning: str,
        cache: CacheMetadata,
        retrieved_at: str,
    ) -> HazardResult:
        return HazardResult(
            hazard=hazard,
            status=status,
            agency=definition.agency,
            service=definition.service_url,
            layer_id=definition.layer_id,
            classification_field=definition.classification_field,
            raw_code=None,
            official_label=None,
            raw_attributes={},
            decoded_attributes={},
            source_url=definition.layer_url,
            spatial_reference=None,
            retrieved_at=retrieved_at,
            attribution=definition.attribution,
            warnings=(warning,),
            cache=cache,
        )


def _first_value(attributes: dict[str, Any], names: tuple[str, ...]) -> Any:
    lookup = {str(key).casefold(): value for key, value in attributes.items()}
    for name in names:
        value = lookup.get(name.casefold())
        if value not in (None, ""):
            return value
    return None


def _validated_bbox(
    bbox: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    if len(bbox) != 4:
        raise ValueError("bbox must contain xmin, ymin, xmax, ymax.")
    values = tuple(float(value) for value in bbox)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("bbox coordinates must be finite.")
    xmin, ymin, xmax, ymax = values
    if not (-180 <= xmin < xmax <= 180 and -90 <= ymin < ymax <= 90):
        raise ValueError("bbox must be an ordered EPSG:4326 extent.")
    return xmin, ymin, xmax, ymax


def _outside_wgs84_extent(
    metadata: dict[str, Any], longitude: float, latitude: float
) -> bool:
    extent = metadata.get("extent")
    if not isinstance(extent, dict):
        return False
    spatial_reference = extent.get("spatialReference")
    if not isinstance(spatial_reference, dict):
        return False
    wkid = spatial_reference.get("latestWkid") or spatial_reference.get("wkid")
    try:
        if int(wkid) != 4326:
            return False
        return not (
            float(extent["xmin"]) <= float(longitude) <= float(extent["xmax"])
            and float(extent["ymin"]) <= float(latitude) <= float(extent["ymax"])
        )
    except (KeyError, TypeError, ValueError):
        return False
