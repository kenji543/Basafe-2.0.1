"""Load the generated ULAP registry and apply safe environment overrides."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from .errors import UrlNotAllowedError
from .models import ServiceDefinition


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "config" / "ulap-services.generated.json"


class RegistryError(ValueError):
    pass


def _env_int(
    environment: Mapping[str, str],
    name: str,
    default: int,
    *,
    minimum: int = 0,
) -> int:
    raw = environment.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RegistryError(f"{name} must be an integer.") from exc
    if value < minimum:
        raise RegistryError(f"{name} must be at least {minimum}.")
    return value


def _env_float(
    environment: Mapping[str, str],
    name: str,
    default: float,
    *,
    minimum: float = 0.001,
) -> float:
    raw = environment.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise RegistryError(f"{name} must be numeric.") from exc
    if value < minimum:
        raise RegistryError(f"{name} must be at least {minimum}.")
    return value


class ServiceRegistry:
    def __init__(
        self,
        path: Path = DEFAULT_REGISTRY_PATH,
        *,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self.path = Path(path).resolve()
        self.environment = environment if environment is not None else os.environ
        try:
            self.configuration = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise RegistryError(f"ULAP registry not found: {self.path}") from exc
        except json.JSONDecodeError as exc:
            raise RegistryError(
                f"Invalid ULAP registry JSON at line {exc.lineno}: {exc.msg}"
            ) from exc
        if not isinstance(self.configuration, dict):
            raise RegistryError("ULAP registry root must be an object.")
        self.settings = self._load_settings(self.configuration.get("settings"))
        self._services = self._load_services(self.configuration.get("services"))

    def _load_settings(self, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise RegistryError("ULAP registry needs a settings object.")
        hosts = raw.get("allowed_hosts")
        if not isinstance(hosts, list) or not hosts:
            raise RegistryError("ULAP registry needs at least one allowed host.")
        schemes = raw.get("allowed_schemes", ["https"])
        if schemes != ["https"]:
            raise RegistryError("Only HTTPS ULAP endpoints are permitted.")
        return dict(raw)

    @property
    def allowed_hosts(self) -> tuple[str, ...]:
        return tuple(str(host).casefold() for host in self.settings["allowed_hosts"])

    @property
    def timeout_seconds(self) -> float:
        name = str(
            self.settings.get(
                "request_timeout_environment_variable",
                "ULAP_REQUEST_TIMEOUT_SECONDS",
            )
        )
        return _env_float(
            self.environment,
            name,
            float(self.settings.get("default_request_timeout_seconds", 15)),
        )

    @property
    def max_retries(self) -> int:
        name = str(
            self.settings.get("max_retries_environment_variable", "ULAP_MAX_RETRIES")
        )
        return _env_int(
            self.environment,
            name,
            int(self.settings.get("default_max_retries", 2)),
        )

    @property
    def metadata_cache_seconds(self) -> int:
        name = str(
            self.settings.get(
                "metadata_cache_environment_variable",
                "ULAP_METADATA_CACHE_SECONDS",
            )
        )
        return _env_int(
            self.environment,
            name,
            int(self.settings.get("default_metadata_cache_seconds", 86400)),
        )

    @property
    def query_cache_seconds(self) -> int:
        name = str(
            self.settings.get(
                "query_cache_environment_variable",
                "ULAP_QUERY_CACHE_SECONDS",
            )
        )
        return _env_int(
            self.environment,
            name,
            int(self.settings.get("default_query_cache_seconds", 3600)),
        )

    @property
    def token(self) -> str | None:
        name = str(self.settings.get("token_environment_variable", "ULAP_TOKEN"))
        token = self.environment.get(name)
        return token if token and token.strip() else None

    @property
    def source_manifest_audit(self) -> dict[str, Any]:
        value = self.configuration.get("source_manifest_audit")
        return dict(value) if isinstance(value, dict) else {}

    def _validate_url(self, url: str) -> None:
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

    def _resolved_urls(self, item: dict[str, Any]) -> tuple[str | None, str | None]:
        if not bool(item.get("configured")):
            return None, None
        relative_path = item.get("relative_service_path")
        base_env_name = item.get("base_environment_variable")
        base_url = (
            self.environment.get(str(base_env_name), "").strip()
            if base_env_name
            else ""
        ) or str(item.get("default_base_url") or "")
        if relative_path:
            service_url = f"{base_url.rstrip('/')}/{str(relative_path).lstrip('/')}"
            layer_id = item.get("layer_id")
            layer_url = (
                f"{service_url}/{int(layer_id)}" if layer_id is not None else None
            )
        else:
            service_url = item.get("service_url")
            layer_url = item.get("layer_url")
        if service_url:
            self._validate_url(str(service_url))
        if layer_url:
            self._validate_url(str(layer_url))
        return (
            str(service_url) if service_url else None,
            str(layer_url) if layer_url else None,
        )

    def _load_services(self, raw: Any) -> dict[str, ServiceDefinition]:
        if not isinstance(raw, list):
            raise RegistryError("ULAP registry needs a services array.")
        definitions: dict[str, ServiceDefinition] = {}
        for item in raw:
            if not isinstance(item, dict):
                raise RegistryError("Every ULAP service entry must be an object.")
            key = str(item.get("key") or "").strip()
            if not key or key in definitions:
                raise RegistryError(f"Invalid or duplicate ULAP service key '{key}'.")
            service_url, layer_url = self._resolved_urls(item)
            expected_domain = item.get("expected_domain") or {}
            identity_fields = item.get("identity_fields") or {}
            if not isinstance(expected_domain, dict) or not isinstance(
                identity_fields, dict
            ):
                raise RegistryError(f"Service '{key}' contains invalid field mappings.")
            definitions[key] = ServiceDefinition(
                key=key,
                dataset_type=str(item.get("dataset_type") or ""),
                required=bool(item.get("required")),
                configured=bool(item.get("configured")),
                agency=(
                    str(item["agency"]) if item.get("agency") is not None else None
                ),
                attribution=(
                    str(item["attribution"])
                    if item.get("attribution") is not None
                    else None
                ),
                service_url=service_url,
                layer_url=layer_url,
                layer_id=(
                    int(item["layer_id"]) if item.get("layer_id") is not None else None
                ),
                expected_layer_name=(
                    str(item["expected_layer_name"])
                    if item.get("expected_layer_name") is not None
                    else None
                ),
                expected_geometry_type=(
                    str(item["expected_geometry_type"])
                    if item.get("expected_geometry_type") is not None
                    else None
                ),
                classification_field=(
                    str(item["classification_field"])
                    if item.get("classification_field") is not None
                    else None
                ),
                expected_spatial_reference=(
                    int(item["expected_spatial_reference"])
                    if item.get("expected_spatial_reference") is not None
                    else None
                ),
                expected_domain={
                    str(code): str(label)
                    for code, label in expected_domain.items()
                },
                preserve_fields=tuple(
                    str(field) for field in item.get("preserve_fields", [])
                ),
                identity_fields={
                    str(role): str(field)
                    for role, field in identity_fields.items()
                },
                required_capabilities=tuple(
                    str(value) for value in item.get("required_capabilities", [])
                ),
                verification=(
                    dict(item.get("verification"))
                    if isinstance(item.get("verification"), dict)
                    else {}
                ),
            )
        return definitions

    def get(self, key: str) -> ServiceDefinition:
        try:
            return self._services[key]
        except KeyError as exc:
            raise RegistryError(f"Unknown ULAP service '{key}'.") from exc

    def all(self) -> tuple[ServiceDefinition, ...]:
        return tuple(self._services.values())

    def hazards(self) -> tuple[ServiceDefinition, ...]:
        return tuple(
            definition
            for definition in self._services.values()
            if definition.dataset_type == "hazard"
        )

    def required(self) -> tuple[ServiceDefinition, ...]:
        return tuple(
            definition
            for definition in self._services.values()
            if definition.required
        )
