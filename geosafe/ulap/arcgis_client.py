"""Resilient standard-library ArcGIS REST client for approved ULAP hosts."""

from __future__ import annotations

import json
import logging
import math
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

from .errors import (
    ArcGISServiceError,
    UlapInvalidResponseError,
    UlapTimeoutError,
    UrlNotAllowedError,
    sanitize_endpoint,
)
from .models import (
    ArcGISResponse,
    CacheMetadata,
    PaginatedResult,
    PointQueryResult,
    Status,
)
from .response_parser import (
    metadata_version,
    parse_arcgis_error,
    response_features,
)


LOGGER = logging.getLogger(__name__)
RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}


@dataclass(slots=True, frozen=True)
class TransportResponse:
    status: int
    body: bytes
    headers: Mapping[str, str]


@dataclass(slots=True)
class _CacheEntry:
    data: dict[str, Any]
    source_url: str
    retrieved_at: datetime
    expires_at: datetime
    http_status: int
    metadata_version: str | None


class _AllowlistedRedirectHandler(HTTPRedirectHandler):
    def __init__(self, validator: Callable[[str], None]) -> None:
        super().__init__()
        self._validator = validator

    def redirect_request(
        self,
        request: Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> Request | None:
        self._validator(new_url)
        return super().redirect_request(
            request, file_pointer, code, message, headers, new_url
        )


class ArcGISClient:
    """Backend-only ArcGIS client with SSRF controls, retries, and TTL caching."""

    def __init__(
        self,
        *,
        allowed_hosts: tuple[str, ...],
        token: str | None = None,
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
        metadata_cache_seconds: int = 86400,
        query_cache_seconds: int = 3600,
        backoff_seconds: float = 0.25,
        transport: Callable[[str, float], TransportResponse] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if not allowed_hosts:
            raise ValueError("At least one approved ULAP host is required.")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative.")
        if metadata_cache_seconds < 0 or query_cache_seconds < 0:
            raise ValueError("cache durations cannot be negative.")
        self.allowed_hosts = tuple(host.casefold() for host in allowed_hosts)
        self.token = token.strip() if token and token.strip() else None
        self.timeout_seconds = float(timeout_seconds)
        self.max_retries = int(max_retries)
        self.metadata_cache_seconds = int(metadata_cache_seconds)
        self.query_cache_seconds = int(query_cache_seconds)
        self.backoff_seconds = max(0.0, float(backoff_seconds))
        self._sleeper = sleeper
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._transport = transport or self._default_transport
        self._cache: dict[str, _CacheEntry] = {}
        self._cache_lock = threading.RLock()
        self._opener = build_opener(_AllowlistedRedirectHandler(self.validate_url))

    @classmethod
    def from_registry(cls, registry: Any, **overrides: Any) -> "ArcGISClient":
        values = {
            "allowed_hosts": registry.allowed_hosts,
            "token": registry.token,
            "timeout_seconds": registry.timeout_seconds,
            "max_retries": registry.max_retries,
            "metadata_cache_seconds": registry.metadata_cache_seconds,
            "query_cache_seconds": registry.query_cache_seconds,
        }
        values.update(overrides)
        return cls(**values)

    def validate_url(self, url: str) -> None:
        parsed = urlsplit(url)
        if (
            parsed.scheme.casefold() != "https"
            or parsed.hostname is None
            or parsed.hostname.casefold() not in self.allowed_hosts
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or parsed.fragment
        ):
            raise UrlNotAllowedError(url)

    def _default_transport(self, url: str, timeout: float) -> TransportResponse:
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "GeoSafe-FIS-ULAP/1.0",
            },
            method="GET",
        )
        try:
            with self._opener.open(request, timeout=timeout) as response:
                return TransportResponse(
                    status=int(response.status),
                    body=response.read(),
                    headers=dict(response.headers.items()),
                )
        except HTTPError as exc:
            return TransportResponse(
                status=int(exc.code),
                body=exc.read(),
                headers=dict(exc.headers.items()) if exc.headers else {},
            )

    def _build_url(
        self, endpoint: str, parameters: Mapping[str, Any]
    ) -> tuple[str, str]:
        self.validate_url(endpoint)
        parts = urlsplit(endpoint)
        combined: list[tuple[str, Any]] = list(parse_qsl(parts.query, keep_blank_values=True))
        for key, value in parameters.items():
            if value is None:
                continue
            if isinstance(value, bool):
                value = "true" if value else "false"
            if isinstance(value, (list, tuple)):
                combined.extend((str(key), item) for item in value)
            else:
                combined.append((str(key), value))
        # Cache and logs never include the optional secret token.
        cache_query = urlencode(
            sorted((str(key), str(value)) for key, value in combined),
            doseq=True,
        )
        request_items = list(combined)
        if self.token:
            request_items.append(("token", self.token))
        request_query = urlencode(request_items, doseq=True)
        clean_base = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        return f"{clean_base}?{request_query}", f"{clean_base}?{cache_query}"

    def clear_cache(self) -> None:
        with self._cache_lock:
            self._cache.clear()

    def invalidate(self, source_url: str) -> int:
        sanitized = sanitize_endpoint(source_url)
        with self._cache_lock:
            keys = [
                key
                for key, entry in self._cache.items()
                if entry.source_url == sanitized
            ]
            for key in keys:
                del self._cache[key]
        return len(keys)

    @staticmethod
    def _iso(value: datetime) -> str:
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()

    @staticmethod
    def _endpoint_context(endpoint: str) -> tuple[str, str | None, str]:
        """Return a token-free dataset label, layer id, and endpoint."""
        sanitized = sanitize_endpoint(endpoint) or endpoint
        parts = urlsplit(sanitized)
        segments = [segment for segment in parts.path.split("/") if segment]
        dataset = parts.path
        layer_id: str | None = None
        try:
            services_index = next(
                index
                for index, segment in enumerate(segments)
                if segment.casefold() == "services"
            )
        except StopIteration:
            services_index = -1
        server_index = next(
            (
                index
                for index, segment in enumerate(segments)
                if segment.casefold() in {"mapserver", "featureserver"}
            ),
            -1,
        )
        if server_index >= 0:
            start = services_index + 1 if services_index >= 0 else 0
            dataset = "/".join(segments[start:server_index]) or parts.path
            if (
                server_index + 1 < len(segments)
                and segments[server_index + 1].isdigit()
            ):
                layer_id = segments[server_index + 1]
        return dataset, layer_id, sanitized

    def _log_request(
        self,
        endpoint: str,
        *,
        requested: datetime,
        responded: datetime | None,
        duration_ms: float,
        http_status: int | None,
        arcgis_error_code: int | None,
        feature_count: int | None,
        parsing_status: str,
    ) -> None:
        dataset, layer_id, sanitized = self._endpoint_context(endpoint)
        LOGGER.info(
            "ULAP request dataset=%s endpoint=%s layer_id=%s requested_at=%s "
            "responded_at=%s http_status=%s arcgis_error_code=%s "
            "duration_ms=%.3f feature_count=%s parsing_status=%s",
            dataset,
            sanitized,
            layer_id,
            self._iso(requested),
            self._iso(responded) if responded is not None else None,
            http_status,
            arcgis_error_code,
            duration_ms,
            feature_count,
            parsing_status,
        )

    def _cached_response(
        self, cache_key: str, endpoint: str
    ) -> ArcGISResponse | None:
        now = self._now()
        with self._cache_lock:
            entry = self._cache.get(cache_key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                del self._cache[cache_key]
                return None
            metadata = CacheMetadata(
                source_url=entry.source_url,
                retrieved_at=self._iso(entry.retrieved_at),
                expires_at=self._iso(entry.expires_at),
                from_cache=True,
                stale=False,
                metadata_version=entry.metadata_version,
            )
            current = self._iso(now)
            return ArcGISResponse(
                data=dict(entry.data),
                source_url=sanitize_endpoint(endpoint) or endpoint,
                requested_at=current,
                responded_at=current,
                duration_ms=0.0,
                http_status=entry.http_status,
                cache=metadata,
            )

    def request_json(
        self,
        endpoint: str,
        parameters: Mapping[str, Any],
        *,
        cache_seconds: int = 0,
    ) -> ArcGISResponse:
        request_url, cache_key = self._build_url(endpoint, parameters)
        if cache_seconds > 0:
            cached = self._cached_response(cache_key, endpoint)
            if cached is not None:
                return cached

        last_network_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            requested = self._now()
            started = time.perf_counter()
            try:
                response = self._transport(request_url, self.timeout_seconds)
            except (TimeoutError, socket.timeout) as exc:
                last_network_error = exc
                if attempt < self.max_retries:
                    self._sleeper(self.backoff_seconds * (2**attempt))
                    continue
                self._log_request(
                    endpoint,
                    requested=requested,
                    responded=None,
                    duration_ms=(time.perf_counter() - started) * 1000.0,
                    http_status=None,
                    arcgis_error_code=None,
                    feature_count=None,
                    parsing_status=Status.TIMEOUT.value,
                )
                raise UlapTimeoutError(endpoint) from exc
            except URLError as exc:
                last_network_error = exc
                if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                    if attempt < self.max_retries:
                        self._sleeper(self.backoff_seconds * (2**attempt))
                        continue
                    self._log_request(
                        endpoint,
                        requested=requested,
                        responded=None,
                        duration_ms=(time.perf_counter() - started) * 1000.0,
                        http_status=None,
                        arcgis_error_code=None,
                        feature_count=None,
                        parsing_status=Status.TIMEOUT.value,
                    )
                    raise UlapTimeoutError(endpoint) from exc
                if attempt < self.max_retries:
                    self._sleeper(self.backoff_seconds * (2**attempt))
                    continue
                self._log_request(
                    endpoint,
                    requested=requested,
                    responded=None,
                    duration_ms=(time.perf_counter() - started) * 1000.0,
                    http_status=None,
                    arcgis_error_code=None,
                    feature_count=None,
                    parsing_status=Status.SERVICE_ERROR.value,
                )
                raise ArcGISServiceError.from_info(
                    endpoint,
                    _network_error_info(str(exc.reason)),
                ) from exc
            except OSError as exc:
                last_network_error = exc
                if attempt < self.max_retries:
                    self._sleeper(self.backoff_seconds * (2**attempt))
                    continue
                self._log_request(
                    endpoint,
                    requested=requested,
                    responded=None,
                    duration_ms=(time.perf_counter() - started) * 1000.0,
                    http_status=None,
                    arcgis_error_code=None,
                    feature_count=None,
                    parsing_status=Status.SERVICE_ERROR.value,
                )
                raise ArcGISServiceError.from_info(
                    endpoint, _network_error_info(str(exc))
                ) from exc

            responded = self._now()
            duration_ms = (time.perf_counter() - started) * 1000.0
            try:
                decoded_body = response.body.decode("utf-8-sig")
                payload = json.loads(decoded_body)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                if (
                    response.status in RETRYABLE_HTTP_STATUS
                    and attempt < self.max_retries
                ):
                    self._sleeper(self.backoff_seconds * (2**attempt))
                    continue
                self._log_request(
                    endpoint,
                    requested=requested,
                    responded=responded,
                    duration_ms=duration_ms,
                    http_status=response.status,
                    arcgis_error_code=None,
                    feature_count=None,
                    parsing_status=Status.INVALID_RESPONSE.value,
                )
                raise UlapInvalidResponseError(
                    endpoint,
                    "ULAP returned a non-JSON response.",
                    http_status=response.status,
                ) from exc
            if not isinstance(payload, dict):
                self._log_request(
                    endpoint,
                    requested=requested,
                    responded=responded,
                    duration_ms=duration_ms,
                    http_status=response.status,
                    arcgis_error_code=None,
                    feature_count=None,
                    parsing_status=Status.INVALID_RESPONSE.value,
                )
                raise UlapInvalidResponseError(
                    endpoint,
                    "ULAP JSON response root must be an object.",
                    http_status=response.status,
                )

            error = parse_arcgis_error(payload, http_status=response.status)
            if error is not None:
                if (
                    error.status == Status.SERVICE_ERROR
                    and response.status in RETRYABLE_HTTP_STATUS
                    and attempt < self.max_retries
                ):
                    self._sleeper(self.backoff_seconds * (2**attempt))
                    continue
                self._log_request(
                    endpoint,
                    requested=requested,
                    responded=responded,
                    duration_ms=duration_ms,
                    http_status=response.status,
                    arcgis_error_code=error.code,
                    feature_count=None,
                    parsing_status=error.status.value,
                )
                raise ArcGISServiceError.from_info(endpoint, error)
            if response.status >= 400:
                if (
                    response.status in RETRYABLE_HTTP_STATUS
                    and attempt < self.max_retries
                ):
                    self._sleeper(self.backoff_seconds * (2**attempt))
                    continue
                self._log_request(
                    endpoint,
                    requested=requested,
                    responded=responded,
                    duration_ms=duration_ms,
                    http_status=response.status,
                    arcgis_error_code=None,
                    feature_count=None,
                    parsing_status=Status.INVALID_RESPONSE.value,
                )
                raise UlapInvalidResponseError(
                    endpoint,
                    f"ULAP request failed with HTTP status {response.status}.",
                    http_status=response.status,
                )

            expires = responded + timedelta(seconds=max(0, cache_seconds))
            cache_metadata = CacheMetadata(
                source_url=sanitize_endpoint(endpoint) or endpoint,
                retrieved_at=self._iso(responded),
                expires_at=self._iso(expires),
                from_cache=False,
                stale=False,
                metadata_version=metadata_version(payload),
            )
            result = ArcGISResponse(
                data=payload,
                source_url=sanitize_endpoint(endpoint) or endpoint,
                requested_at=self._iso(requested),
                responded_at=self._iso(responded),
                duration_ms=round(duration_ms, 3),
                http_status=response.status,
                cache=cache_metadata,
            )
            if cache_seconds > 0:
                with self._cache_lock:
                    self._cache[cache_key] = _CacheEntry(
                        data=dict(payload),
                        source_url=result.source_url,
                        retrieved_at=responded,
                        expires_at=expires,
                        http_status=response.status,
                        metadata_version=cache_metadata.metadata_version,
                    )
            feature_count = (
                len(payload["features"])
                if isinstance(payload.get("features"), list)
                else None
            )
            self._log_request(
                endpoint,
                requested=requested,
                responded=responded,
                duration_ms=duration_ms,
                http_status=response.status,
                arcgis_error_code=None,
                feature_count=feature_count,
                parsing_status="ok",
            )
            return result

        # Defensive only; every loop path returns or raises.
        raise ArcGISServiceError.from_info(
            endpoint,
            _network_error_info(str(last_network_error or "unknown network error")),
        )

    def service_metadata(self, service_url: str) -> ArcGISResponse:
        return self.request_json(
            service_url,
            {"f": "pjson"},
            cache_seconds=self.metadata_cache_seconds,
        )

    def layer_metadata(self, layer_url: str) -> ArcGISResponse:
        return self.request_json(
            layer_url,
            {"f": "pjson"},
            cache_seconds=self.metadata_cache_seconds,
        )

    def query_features(
        self,
        layer_url: str,
        *,
        where: str = "1=1",
        out_fields: tuple[str, ...] | str = "*",
        return_geometry: bool = False,
        output_spatial_reference: int = 4326,
        response_format: str = "json",
        geometry: str | None = None,
        geometry_type: str | None = None,
        input_spatial_reference: int | None = None,
        spatial_relationship: str = "esriSpatialRelIntersects",
        result_offset: int | None = None,
        result_record_count: int | None = None,
        cache_seconds: int | None = None,
    ) -> ArcGISResponse:
        if response_format not in {"json", "pjson", "geojson"}:
            raise ValueError("response_format must be json, pjson, or geojson.")
        out_fields_value = (
            out_fields if isinstance(out_fields, str) else ",".join(out_fields)
        )
        parameters: dict[str, Any] = {
            "where": where,
            "outFields": out_fields_value,
            "returnGeometry": return_geometry,
            "outSR": output_spatial_reference,
            "f": response_format,
            "geometry": geometry,
            "geometryType": geometry_type,
            "inSR": input_spatial_reference,
            "spatialRel": spatial_relationship if geometry is not None else None,
            "resultOffset": result_offset,
            "resultRecordCount": result_record_count,
        }
        return self.request_json(
            f"{layer_url.rstrip('/')}/query",
            parameters,
            cache_seconds=(
                self.query_cache_seconds
                if cache_seconds is None
                else int(cache_seconds)
            ),
        )

    def point_query(
        self,
        layer_url: str,
        longitude: float,
        latitude: float,
        *,
        out_fields: tuple[str, ...] | str = "*",
        return_geometry: bool = False,
    ) -> PointQueryResult:
        _validate_coordinate(longitude, latitude)
        response = self.query_features(
            layer_url,
            out_fields=out_fields,
            return_geometry=return_geometry,
            geometry=f"{float(longitude):.8f},{float(latitude):.8f}",
            geometry_type="esriGeometryPoint",
            input_spatial_reference=4326,
            spatial_relationship="esriSpatialRelIntersects",
            response_format="json",
        )
        features = response_features(response.source_url, response.data)
        status = Status.AVAILABLE if features else Status.NO_INTERSECTION
        warnings: list[str] = []
        if len(features) > 1:
            warnings.append(
                f"{len(features)} intersecting features were returned; the caller "
                "must check whether their classifications agree."
            )
        return PointQueryResult(
            status=status,
            source_url=response.source_url,
            retrieved_at=response.responded_at,
            features=tuple(features),
            feature_count=len(features),
            multiple_intersections=len(features) > 1,
            cache=response.cache,
            warnings=tuple(warnings),
        )

    def bounding_box_query(
        self,
        layer_url: str,
        xmin: float,
        ymin: float,
        xmax: float,
        ymax: float,
        *,
        where: str = "1=1",
        out_fields: tuple[str, ...] | str = "*",
        return_geometry: bool = True,
        response_format: str = "geojson",
    ) -> ArcGISResponse:
        for longitude, latitude in ((xmin, ymin), (xmax, ymax)):
            _validate_coordinate(longitude, latitude)
        if xmax <= xmin or ymax <= ymin:
            raise ValueError("Bounding box maximums must exceed minimums.")
        geometry = json.dumps(
            {
                "xmin": xmin,
                "ymin": ymin,
                "xmax": xmax,
                "ymax": ymax,
                "spatialReference": {"wkid": 4326},
            },
            separators=(",", ":"),
        )
        return self.query_features(
            layer_url,
            where=where,
            out_fields=out_fields,
            return_geometry=return_geometry,
            response_format=response_format,
            geometry=geometry,
            geometry_type="esriGeometryEnvelope",
            input_spatial_reference=4326,
            spatial_relationship="esriSpatialRelIntersects",
        )

    def query_all(
        self,
        layer_url: str,
        *,
        where: str = "1=1",
        out_fields: tuple[str, ...] | str = "*",
        return_geometry: bool = False,
        response_format: str = "json",
        page_size: int = 2000,
        max_pages: int = 100,
        geometry: str | None = None,
        geometry_type: str | None = None,
        input_spatial_reference: int | None = None,
    ) -> PaginatedResult:
        if page_size <= 0 or max_pages <= 0:
            raise ValueError("page_size and max_pages must be positive.")
        features: list[dict[str, Any]] = []
        cache_entries: list[CacheMetadata] = []
        retrieved_at = ""
        for page_index in range(max_pages):
            response = self.query_features(
                layer_url,
                where=where,
                out_fields=out_fields,
                return_geometry=return_geometry,
                response_format=response_format,
                geometry=geometry,
                geometry_type=geometry_type,
                input_spatial_reference=input_spatial_reference,
                result_offset=page_index * page_size,
                result_record_count=page_size,
            )
            page_features = response_features(response.source_url, response.data)
            features.extend(page_features)
            cache_entries.append(response.cache)
            retrieved_at = response.responded_at
            properties = response.data.get("properties")
            exceeded = response.data.get("exceededTransferLimit")
            if exceeded is None and isinstance(properties, dict):
                exceeded = properties.get("exceededTransferLimit")
            if not page_features or exceeded is False or (
                exceeded is None and len(page_features) < page_size
            ):
                return PaginatedResult(
                    features=tuple(features),
                    pages=page_index + 1,
                    source_url=response.source_url,
                    retrieved_at=retrieved_at,
                    cache_entries=tuple(cache_entries),
                )
        raise UlapInvalidResponseError(
            f"{layer_url.rstrip('/')}/query",
            f"Pagination exceeded the configured maximum of {max_pages} pages.",
        )


def _validate_coordinate(longitude: float, latitude: float) -> None:
    if (
        isinstance(longitude, bool)
        or isinstance(latitude, bool)
        or not isinstance(longitude, (int, float))
        or not isinstance(latitude, (int, float))
        or not math.isfinite(float(longitude))
        or not math.isfinite(float(latitude))
    ):
        raise ValueError("Longitude and latitude must be finite numbers.")
    if not -180.0 <= float(longitude) <= 180.0:
        raise ValueError("Longitude must be between -180 and 180.")
    if not -90.0 <= float(latitude) <= 90.0:
        raise ValueError("Latitude must be between -90 and 90.")


def _network_error_info(message: str) -> Any:
    from .models import ArcGISErrorInfo

    return ArcGISErrorInfo(
        code=None,
        message="ULAP service could not be reached.",
        details=(message,),
        status=Status.INACCESSIBLE,
        http_status=None,
    )
