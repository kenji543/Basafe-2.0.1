"""Point-based Basey municipality and barangay identification through ULAP."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .arcgis_client import ArcGISClient
from .errors import UlapError
from .models import BoundaryIdentification, FeatureCollectionResult, Status
from .response_parser import feature_attributes
from .service_registry import ServiceRegistry


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _value(attributes: dict[str, Any], field: str | None) -> Any:
    if not field:
        return None
    wanted = field.casefold()
    for key, value in attributes.items():
        if str(key).casefold() == wanted:
            return value
    return None


def _matches_basey(
    attributes: dict[str, Any], identity_fields: dict[str, str]
) -> bool:
    municipality = _value(attributes, identity_fields.get("municipality"))
    province = _value(attributes, identity_fields.get("province"))
    return (
        str(municipality or "").strip().casefold() == "basey"
        and str(province or "").strip().casefold() == "samar"
    )


class BoundaryProvider:
    def __init__(self, client: ArcGISClient, registry: ServiceRegistry) -> None:
        self.client = client
        self.registry = registry

    def identify(self, longitude: float, latitude: float) -> BoundaryIdentification:
        municipal = self.registry.get("municipal_boundary")
        barangay = self.registry.get("barangay_boundary")
        if not municipal.configured or not municipal.layer_url:
            return self._error(
                longitude,
                latitude,
                Status.UNAVAILABLE,
                "No verified municipal boundary layer is configured.",
            )
        try:
            municipal_query = self.client.point_query(
                municipal.layer_url,
                longitude,
                latitude,
                out_fields="*",
                return_geometry=False,
            )
        except UlapError as exc:
            return self._error(longitude, latitude, exc.status, exc.message)
        if not municipal_query.features:
            return BoundaryIdentification(
                status=Status.OUTSIDE_COVERAGE,
                longitude=float(longitude),
                latitude=float(latitude),
                inside_basey=False,
                municipality=None,
                province=None,
                barangay=None,
                source_urls=(municipal.layer_url,),
                retrieved_at=municipal_query.retrieved_at,
                warnings=(
                    "No municipal polygon intersects the point; a Basey assessment "
                    "must not run.",
                ),
            )

        municipal_attributes = [
            feature_attributes(feature) for feature in municipal_query.features
        ]
        basey_matches = [
            attributes
            for attributes in municipal_attributes
            if _matches_basey(attributes, municipal.identity_fields)
        ]
        if not basey_matches:
            first = municipal_attributes[0]
            return BoundaryIdentification(
                status=Status.OUTSIDE_COVERAGE,
                longitude=float(longitude),
                latitude=float(latitude),
                inside_basey=False,
                municipality=_text(
                    _value(first, municipal.identity_fields.get("municipality"))
                ),
                province=_text(
                    _value(first, municipal.identity_fields.get("province"))
                ),
                barangay=None,
                source_urls=(municipal.layer_url,),
                retrieved_at=municipal_query.retrieved_at,
                warnings=(
                    "The intersecting municipality is not Basey, Samar; a normal "
                    "Basey assessment must not run.",
                ),
            )
        selected_municipal = basey_matches[0]
        warnings: list[str] = []
        if len(basey_matches) > 1:
            warnings.append(
                f"{len(basey_matches)} Basey municipal polygons intersected the point."
            )

        if not barangay.configured or not barangay.layer_url:
            return BoundaryIdentification(
                status=Status.UNAVAILABLE,
                longitude=float(longitude),
                latitude=float(latitude),
                inside_basey=True,
                municipality="Basey",
                province="Samar",
                barangay=None,
                municipality_code=_text(
                    _value(
                        selected_municipal,
                        municipal.identity_fields.get("municipality_code"),
                    )
                ),
                province_code=_text(
                    _value(
                        selected_municipal,
                        municipal.identity_fields.get("province_code"),
                    )
                ),
                source_urls=(municipal.layer_url,),
                retrieved_at=municipal_query.retrieved_at,
                warnings=tuple(
                    warnings + ["No verified barangay boundary layer is configured."]
                ),
            )
        try:
            barangay_query = self.client.point_query(
                barangay.layer_url,
                longitude,
                latitude,
                out_fields="*",
                return_geometry=False,
            )
        except UlapError as exc:
            return BoundaryIdentification(
                status=exc.status,
                longitude=float(longitude),
                latitude=float(latitude),
                inside_basey=True,
                municipality="Basey",
                province="Samar",
                barangay=None,
                source_urls=(municipal.layer_url, barangay.layer_url),
                retrieved_at=_now_iso(),
                warnings=tuple(warnings + [exc.message]),
            )
        barangay_attributes = [
            feature_attributes(feature) for feature in barangay_query.features
        ]
        barangay_matches = [
            attributes
            for attributes in barangay_attributes
            if _matches_basey(attributes, barangay.identity_fields)
        ]
        if not barangay_matches:
            return BoundaryIdentification(
                status=Status.NO_INTERSECTION,
                longitude=float(longitude),
                latitude=float(latitude),
                inside_basey=True,
                municipality="Basey",
                province="Samar",
                barangay=None,
                municipality_code=_text(
                    _value(
                        selected_municipal,
                        municipal.identity_fields.get("municipality_code"),
                    )
                ),
                province_code=_text(
                    _value(
                        selected_municipal,
                        municipal.identity_fields.get("province_code"),
                    )
                ),
                source_urls=(municipal.layer_url, barangay.layer_url),
                retrieved_at=barangay_query.retrieved_at,
                warnings=tuple(
                    warnings
                    + [
                        "The point is inside the Basey municipal result, but no "
                        "Basey barangay polygon was returned."
                    ]
                ),
            )
        selected_barangay = barangay_matches[0]
        if len(barangay_matches) > 1:
            warnings.append(
                f"{len(barangay_matches)} Basey barangay polygons intersected the point."
            )
        return BoundaryIdentification(
            status=Status.AVAILABLE,
            longitude=float(longitude),
            latitude=float(latitude),
            inside_basey=True,
            municipality="Basey",
            province="Samar",
            barangay=_text(
                _value(selected_barangay, barangay.identity_fields.get("barangay"))
            ),
            municipality_code=_text(
                _value(
                    selected_barangay,
                    barangay.identity_fields.get("municipality_code"),
                )
            )
            or _text(
                _value(
                    selected_municipal,
                    municipal.identity_fields.get("municipality_code"),
                )
            ),
            province_code=_text(
                _value(
                    selected_barangay, barangay.identity_fields.get("province_code")
                )
            )
            or _text(
                _value(
                    selected_municipal, municipal.identity_fields.get("province_code")
                )
            ),
            barangay_code=_text(
                _value(
                    selected_barangay, barangay.identity_fields.get("barangay_code")
                )
            ),
            psgc=_text(
                _value(selected_barangay, barangay.identity_fields.get("psgc"))
            ),
            source_urls=(municipal.layer_url, barangay.layer_url),
            retrieved_at=barangay_query.retrieved_at,
            warnings=tuple(warnings),
        )

    def basey_municipal_geojson(self) -> FeatureCollectionResult:
        return self._basey_geojson("municipal_boundary")

    def basey_barangays_geojson(self) -> FeatureCollectionResult:
        return self._basey_geojson("barangay_boundary")

    def _basey_geojson(self, service_key: str) -> FeatureCollectionResult:
        definition = self.registry.get(service_key)
        if not definition.configured or not definition.layer_url:
            return FeatureCollectionResult(
                status=Status.UNAVAILABLE,
                dataset=service_key,
                feature_collection={"type": "FeatureCollection", "features": []},
                source_url=None,
                retrieved_at=_now_iso(),
                attribution=definition.attribution,
                warnings=("No verified boundary layer URL is configured.",),
            )
        municipality_field = definition.identity_fields.get("municipality")
        province_field = definition.identity_fields.get("province")
        if not municipality_field or not province_field:
            return FeatureCollectionResult(
                status=Status.CHANGED_SCHEMA,
                dataset=service_key,
                feature_collection={"type": "FeatureCollection", "features": []},
                source_url=definition.layer_url,
                retrieved_at=_now_iso(),
                attribution=definition.attribution,
                warnings=("Boundary identity field mapping is incomplete.",),
            )
        # Field names come only from the reviewed registry; values are constants.
        where = (
            f"{municipality_field}='Basey' AND {province_field}='Samar'"
        )
        try:
            result = self.client.query_all(
                definition.layer_url,
                where=where,
                out_fields=definition.preserve_fields or "*",
                return_geometry=True,
                response_format="geojson",
                page_size=2000,
            )
        except UlapError as exc:
            return FeatureCollectionResult(
                status=exc.status,
                dataset=service_key,
                feature_collection={"type": "FeatureCollection", "features": []},
                source_url=exc.endpoint or definition.layer_url,
                retrieved_at=_now_iso(),
                attribution=definition.attribution,
                warnings=(exc.message,),
            )
        status = Status.AVAILABLE if result.features else Status.NO_INTERSECTION
        return FeatureCollectionResult(
            status=status,
            dataset=service_key,
            feature_collection={
                "type": "FeatureCollection",
                "features": list(result.features),
            },
            source_url=definition.layer_url,
            retrieved_at=result.retrieved_at,
            pages=result.pages,
            cache_entries=result.cache_entries,
            attribution=definition.attribution,
            warnings=(
                ()
                if result.features
                else ("No Basey, Samar features were returned by the live layer.",)
            ),
        )

    @staticmethod
    def _error(
        longitude: float,
        latitude: float,
        status: Status,
        warning: str,
    ) -> BoundaryIdentification:
        return BoundaryIdentification(
            status=status,
            longitude=float(longitude),
            latitude=float(latitude),
            inside_basey=False,
            municipality=None,
            province=None,
            barangay=None,
            retrieved_at=_now_iso(),
            warnings=(warning,),
        )


def _text(value: Any) -> str | None:
    if value is None or not str(value).strip():
        return None
    return str(value).strip()
