"""Structured and sanitized failures for ULAP/ArcGIS operations."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .models import ArcGISErrorInfo, Status


SENSITIVE_KEYS = {"token", "access_token", "authorization", "password", "key"}


def sanitize_endpoint(url: str | None) -> str | None:
    if not url:
        return url
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def sanitize_details(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if str(key).casefold() in SENSITIVE_KEYS
                else sanitize_details(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_details(item) for item in value]
    return value


class UlapError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status: Status,
        endpoint: str | None = None,
        http_status: int | None = None,
        arcgis_code: int | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.endpoint = sanitize_endpoint(endpoint)
        self.http_status = http_status
        self.arcgis_code = arcgis_code
        self.details = sanitize_details(details)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "message": self.message,
            "endpoint": self.endpoint,
            "http_status": self.http_status,
            "arcgis_error_code": self.arcgis_code,
            "details": self.details,
        }


class UrlNotAllowedError(UlapError):
    def __init__(self, endpoint: str, message: str = "ULAP endpoint is not allowlisted.") -> None:
        super().__init__(
            message,
            status=Status.INVALID_RESPONSE,
            endpoint=endpoint,
        )


class UlapTimeoutError(UlapError):
    def __init__(self, endpoint: str, message: str = "ULAP request timed out.") -> None:
        super().__init__(message, status=Status.TIMEOUT, endpoint=endpoint)


class UlapInvalidResponseError(UlapError):
    def __init__(
        self,
        endpoint: str,
        message: str,
        *,
        http_status: int | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(
            message,
            status=Status.INVALID_RESPONSE,
            endpoint=endpoint,
            http_status=http_status,
            details=details,
        )


class ArcGISServiceError(UlapError):
    @classmethod
    def from_info(cls, endpoint: str, info: ArcGISErrorInfo) -> "ArcGISServiceError":
        instance = cls.__new__(cls)
        UlapError.__init__(
            instance,
            info.message,
            status=info.status,
            endpoint=endpoint,
            http_status=info.http_status,
            arcgis_code=info.code,
            details=list(info.details),
        )
        return instance
