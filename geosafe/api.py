"""Framework-free HTTP API dispatcher for Basafe."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import unquote

from .service import GeoSafeService, ServiceError, ValidationError


@dataclass
class Response:
    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def json(
        cls,
        payload: Any,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> "Response":
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return cls(
            status,
            encoded,
            {
                "Content-Type": "application/json; charset=utf-8",
                "Content-Length": str(len(encoded)),
                "Cache-Control": "no-store",
                **(headers or {}),
            },
        )


class Api:
    """Maps the approved endpoint allowlist to application services."""

    def __init__(self, service: GeoSafeService):
        self.service = service

    @staticmethod
    def _one(
        query: dict[str, list[str]], key: str, default: str | None = None
    ) -> str | None:
        values = query.get(key)
        return values[-1] if values else default

    @classmethod
    def _float(
        cls,
        query: dict[str, list[str]],
        key: str,
        required: bool = True,
        default: float | None = None,
    ) -> float | None:
        raw = cls._one(query, key)
        if raw is None:
            if required:
                raise ValidationError(f"Query parameter {key!r} is required.")
            return default
        try:
            return float(raw)
        except ValueError as exc:
            raise ValidationError(f"Query parameter {key!r} must be numeric.") from exc

    @classmethod
    def _coordinate(
        cls,
        query: dict[str, list[str]],
        short_name: str,
        long_name: str,
    ) -> float:
        raw = cls._one(query, short_name)
        if raw is None:
            raw = cls._one(query, long_name)
        if raw is None:
            raise ValidationError(
                f"Query parameter {long_name!r} (or {short_name!r}) is required."
            )
        try:
            return float(raw)
        except ValueError as exc:
            raise ValidationError(
                f"Query parameter {long_name!r} must be numeric."
            ) from exc

    @classmethod
    def _int(
        cls,
        query: dict[str, list[str]],
        key: str,
        required: bool = True,
        default: int | None = None,
    ) -> int | None:
        raw = cls._one(query, key)
        if raw is None:
            if required:
                raise ValidationError(f"Query parameter {key!r} is required.")
            return default
        try:
            return int(raw)
        except ValueError as exc:
            raise ValidationError(
                f"Query parameter {key!r} must be an integer."
            ) from exc

    @classmethod
    def _bool(
        cls,
        query: dict[str, list[str]],
        key: str,
        *,
        default: bool = False,
    ) -> bool:
        raw = cls._one(query, key)
        if raw is None:
            return default
        normalized = raw.strip().casefold()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        raise ValidationError(
            f"Query parameter {key!r} must be true or false."
        )

    @staticmethod
    def _json_body(body: bytes) -> dict[str, Any]:
        if not body:
            raise ValidationError("A JSON request body is required.")
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValidationError("Request body contains invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise ValidationError("Request body must be a JSON object.")
        return payload

    def dispatch(
        self,
        method: str,
        path: str,
        query: dict[str, list[str]] | None = None,
        body: bytes = b"",
    ) -> Response:
        query = query or {}
        normalized_path = path.rstrip("/") or "/"
        compatibility_aliases = {
            "/api/source-status": "/api/v1/ulap/status",
            "/api/layers": "/api/v1/hazard-layers",
            "/api/model/current": "/api/v1/methodology",
            "/api/model/current/methodology": "/api/v1/methodology",
        }
        normalized_path = compatibility_aliases.get(normalized_path, normalized_path)
        if normalized_path.startswith("/api/assessments"):
            normalized_path = normalized_path.replace(
                "/api/assessments", "/api/v1/assessments", 1
            )
        layer_metadata_match = re.fullmatch(
            r"/api/layers/([^/]+)/metadata", normalized_path
        )
        if layer_metadata_match:
            normalized_path = (
                "/api/v1/ulap/services/"
                f"{layer_metadata_match.group(1)}/metadata"
            )
        try:
            if method == "OPTIONS":
                return Response(204, b"", {"Content-Length": "0"})
            if method == "GET" and normalized_path in {
                "/api/health",
                "/api/v1/health",
            }:
                return Response.json(
                    {
                        "status": "ok",
                        "application": "Basafe",
                        "model_version": self.service.model.version,
                        "runtime_data_mode": self.service.runtime_data_mode,
                    }
                )
            if method == "POST" and normalized_path == "/api/location/validate":
                payload = self._json_body(body)
                latitude = payload.get("latitude", payload.get("lat"))
                longitude = payload.get(
                    "longitude", payload.get("lon", payload.get("lng"))
                )
                if latitude is None or longitude is None:
                    raise ValidationError("latitude and longitude are required.")
                return Response.json(
                    self.service.identify_location(latitude, longitude)
                )
            if method == "POST" and normalized_path == "/api/hazards/query":
                payload = self._json_body(body)
                latitude = payload.get("latitude", payload.get("lat"))
                longitude = payload.get(
                    "longitude", payload.get("lon", payload.get("lng"))
                )
                if latitude is None or longitude is None:
                    raise ValidationError("latitude and longitude are required.")
                return Response.json(
                    self.service.hazards_at_location(latitude, longitude)
                )
            if method == "GET" and normalized_path == "/api/v1/ulap/status":
                return Response.json(
                    self.service.ulap_status(
                        refresh=self._bool(query, "refresh", default=False)
                    )
                )
            if method == "GET" and normalized_path == "/api/v1/ulap/services":
                return Response.json(self.service.ulap_services())
            match = re.fullmatch(
                r"/api/v1/ulap/services/([^/]+)/metadata", normalized_path
            )
            if method == "GET" and match:
                return Response.json(
                    self.service.ulap_service_metadata(unquote(match.group(1)))
                )
            if method == "GET" and normalized_path in {
                "/api/v1/boundary",
                "/api/v1/boundary/basey",
            }:
                return Response.json(self.service.boundary_geojson())
            if method == "GET" and normalized_path == "/api/v1/barangays":
                return Response.json(self.service.barangays_geojson())

            match = re.fullmatch(r"/api/v1/barangays/(\d+)", normalized_path)
            if method == "GET" and match:
                return Response.json(
                    self.service.barangay_geojson(int(match.group(1)))
                )

            if method == "GET" and normalized_path == "/api/v1/hazard-layers":
                return Response.json(self.service.hazard_layers())
            match = re.fullmatch(
                r"/api/v1/hazard-layers/([^/]+)/features", normalized_path
            )
            if method == "GET" and match:
                layer_token = unquote(match.group(1))
                layer_identifier: int | str = (
                    int(layer_token) if layer_token.isdigit() else layer_token
                )
                return Response.json(
                    self.service.hazard_layer_features(layer_identifier)
                )

            if method == "GET" and normalized_path == "/api/v1/location/search":
                search_query = self._one(query, "q", "") or ""
                limit = self._int(query, "limit", required=False, default=10)
                return Response.json(
                    self.service.search_locations(search_query, limit=limit)
                )
            if method == "GET" and normalized_path == "/api/v1/location/identify":
                latitude = self._coordinate(query, "lat", "latitude")
                longitude = self._coordinate(query, "lon", "longitude")
                return Response.json(
                    self.service.identify_location(latitude, longitude)
                )

            if (
                method == "GET"
                and normalized_path == "/api/v1/hazards/at-location"
            ):
                latitude = self._coordinate(query, "lat", "latitude")
                longitude = self._coordinate(query, "lon", "longitude")
                return Response.json(
                    self.service.hazards_at_location(latitude, longitude)
                )
            match = re.fullmatch(
                r"/api/v1/hazards/(flood|liquefaction|ground-shaking)",
                normalized_path,
            )
            if method == "GET" and match:
                latitude = self._coordinate(query, "lat", "latitude")
                longitude = self._coordinate(query, "lon", "longitude")
                return Response.json(
                    self.service.hazard_at_location(
                        match.group(1), latitude, longitude
                    )
                )

            if method == "POST" and normalized_path == "/api/v1/assessments":
                payload = self._json_body(body)
                nested_location = payload.get("location", {})
                if not isinstance(nested_location, dict):
                    raise ValidationError("location must be a JSON object when supplied.")
                latitude = payload.get(
                    "latitude",
                    payload.get(
                        "lat",
                        nested_location.get("latitude", nested_location.get("lat")),
                    ),
                )
                longitude = payload.get(
                    "longitude",
                    payload.get(
                        "lon",
                        nested_location.get("longitude", nested_location.get("lon")),
                    ),
                )
                if latitude is None or longitude is None:
                    raise ValidationError(
                        "latitude and longitude are required in the JSON body."
                    )
                requested_model = payload.get("model_version")
                if (
                    requested_model is not None
                    and requested_model != self.service.model.version
                ):
                    raise ValidationError(
                        f"Model version {requested_model!r} is not active. "
                        f"The available version is {self.service.model.version!r}."
                    )
                label = payload.get(
                    "location_label", nested_location.get("display_label")
                )
                if label is not None:
                    if not isinstance(label, str):
                        raise ValidationError("location_label must be a string.")
                    label = label.strip() or None
                    if label and len(label) > 200:
                        raise ValidationError(
                            "location_label must not exceed 200 characters."
                        )
                selection_method = payload.get(
                    "selection_method",
                    nested_location.get("selection_method", "coordinates"),
                )
                if selection_method not in {"search", "coordinates", "map_click"}:
                    raise ValidationError(
                        "selection_method must be search, coordinates, or map_click."
                    )
                assessment = self.service.create_assessment(
                    latitude, longitude, label, selection_method
                )
                return Response.json(
                    assessment,
                    status=201,
                    headers={"Location": assessment["links"]["self"]},
                )
            if method == "GET" and normalized_path == "/api/v1/assessments":
                return Response.json(
                    {
                        "error": {
                            "code": "private_history",
                            "message": (
                                "Assessment history is private to each device and "
                                "is not available as a shared service listing."
                            ),
                        }
                    },
                    status=404,
                )

            match = re.fullmatch(
                r"/api/v1/assessments/([A-Za-z0-9_-]{20,128})/explanation",
                normalized_path,
            )
            if method == "GET" and match:
                return Response.json(
                    self.service.explanation(match.group(1))
                )
            match = re.fullmatch(
                r"/api/v1/assessments/([A-Za-z0-9_-]{20,128})/report",
                normalized_path,
            )
            if method == "GET" and match:
                public_token = match.group(1)
                pdf_content, metadata = self.service.assessment_report(public_token)
                return Response(
                    200,
                    pdf_content,
                    {
                        "Content-Type": "application/pdf",
                        "Content-Length": str(len(pdf_content)),
                        "Content-Disposition": (
                            f'attachment; filename="basafe-assessment-{public_token[:12]}.pdf"'
                        ),
                        "Cache-Control": "no-store",
                        "X-Report-SHA256": metadata["sha256"],
                    },
                )
            match = re.fullmatch(
                r"/api/v1/assessments/([A-Za-z0-9_-]{20,128})",
                normalized_path,
            )
            if method == "GET" and match:
                return Response.json(
                    self.service.assessment(match.group(1))
                )

            if method == "GET" and normalized_path == "/api/v1/incidents/nearby":
                latitude = self._coordinate(query, "lat", "latitude")
                longitude = self._coordinate(query, "lon", "longitude")
                radius = self._float(
                    query, "radius_km", required=False, default=10
                )
                radius_metres = self._float(
                    query, "radius_m", required=False, default=None
                )
                if radius_metres is not None:
                    radius = radius_metres / 1000
                barangay_id = self._int(
                    query, "barangay_id", required=False, default=None
                )
                items = self.service.nearby_incidents(
                    latitude,
                    longitude,
                    radius_km=radius,
                    barangay_id=barangay_id,
                )
                return Response.json({"items": items, "count": len(items)})
            if method == "GET" and normalized_path == "/api/v1/incidents":
                limit = self._int(query, "limit", required=False, default=200)
                return Response.json(self.service.all_incidents(limit))

            if (
                method == "GET"
                and normalized_path == "/api/v1/clup-references/by-location"
            ):
                latitude = self._coordinate(query, "lat", "latitude")
                longitude = self._coordinate(query, "lon", "longitude")
                barangay_id = self._int(
                    query, "barangay_id", required=False, default=None
                )
                items = self.service.clup_by_location(
                    latitude, longitude, barangay_id=barangay_id
                )
                return Response.json({"items": items, "count": len(items)})
            if method == "GET" and normalized_path == "/api/v1/clup-references":
                limit = self._int(query, "limit", required=False, default=200)
                return Response.json(
                    self.service.all_clup_references(limit)
                )

            if method == "GET" and normalized_path == "/api/v1/methodology":
                return Response.json(self.service.methodology())
            if method == "GET" and normalized_path == "/api/v1/data-sources":
                return Response.json(self.service.data_sources())

            return Response.json(
                {
                    "error": {
                        "code": "not_found",
                        "message": "The requested API endpoint does not exist.",
                    }
                },
                status=404,
            )
        except ServiceError as exc:
            error: dict[str, Any] = {
                "code": exc.code,
                "message": str(exc),
            }
            if exc.details is not None:
                error["details"] = exc.details
            return Response.json({"error": error}, status=exc.status_code)
