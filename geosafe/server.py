"""Development/deployment HTTP server for the unified Basafe interface."""

from __future__ import annotations

import argparse
import logging
import mimetypes
import os
import re
import shutil
import sys
import threading
import time
from collections import defaultdict, deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .api import Api, Response
from .fuzzy import FuzzyModel
from .repository import Repository
from .service import GeoSafeService
from .ulap.integration import UlapIntegration


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGGER = logging.getLogger("geosafe")
MAX_REQUEST_BYTES = 1_048_576
RATE_LIMIT_WINDOW_SECONDS = 60


def _environment_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false.")


def _environment_positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive.")
    return value


class GeoSafeServer(ThreadingHTTPServer):
    """HTTP server carrying application and static-root references."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        api: Api,
        web_root: Path,
    ):
        self.api = api
        self.web_root = web_root.resolve()
        self.api_rate_limit = _environment_positive_int(
            "GEOSAFE_API_REQUESTS_PER_MINUTE", 240
        )
        self.assessment_rate_limit = _environment_positive_int(
            "GEOSAFE_ASSESSMENTS_PER_MINUTE", 12
        )
        self._rate_limit_lock = threading.Lock()
        self._rate_limit_windows: dict[
            tuple[str, str], deque[float]
        ] = defaultdict(deque)
        super().__init__(server_address, GeoSafeRequestHandler)

    def check_rate_limit(
        self, client_ip: str, bucket: str
    ) -> tuple[bool, int, int, int]:
        limit = (
            self.assessment_rate_limit
            if bucket == "assessment"
            else self.api_rate_limit
        )
        now = time.monotonic()
        cutoff = now - RATE_LIMIT_WINDOW_SECONDS
        key = (client_ip, bucket)
        with self._rate_limit_lock:
            requests = self._rate_limit_windows[key]
            while requests and requests[0] <= cutoff:
                requests.popleft()
            if len(requests) >= limit:
                retry_after = max(1, int(RATE_LIMIT_WINDOW_SECONDS - (now - requests[0])) + 1)
                return False, limit, 0, retry_after
            requests.append(now)
            return True, limit, max(0, limit - len(requests)), 0

    def handle_error(self, request: object, client_address: object) -> None:
        error = sys.exc_info()[1]
        if isinstance(error, (BrokenPipeError, ConnectionResetError)):
            LOGGER.debug("Client disconnected before the response completed")
            return
        super().handle_error(request, client_address)


class GeoSafeRequestHandler(BaseHTTPRequestHandler):
    server: GeoSafeServer
    protocol_version = "HTTP/1.1"

    def _send(self, response: Response, head_only: bool = False) -> None:
        self.send_response(response.status)
        headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(self)",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' https://unpkg.com; "
                "style-src 'self' 'unsafe-inline' https://unpkg.com; "
                "img-src 'self' data: blob: https://*.tile.openstreetmap.org "
                "https://server.arcgisonline.com https://services.arcgisonline.com "
                "https://ulap-hazards.georisk.gov.ph; "
                "connect-src 'self' https://*.tile.openstreetmap.org "
                "https://server.arcgisonline.com https://services.arcgisonline.com; "
                "font-src 'self'; object-src 'none'; base-uri 'self'; "
                "frame-ancestors 'none'; worker-src 'self'; manifest-src 'self'"
            ),
            **response.headers,
        }
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        if not head_only and response.body:
            self.wfile.write(response.body)

    def _api_response(self, method: str) -> Response:
        split = urlsplit(self.path)
        bucket = (
            "assessment"
            if method == "POST"
            and split.path.rstrip("/") in {
                "/api/assessments",
                "/api/v1/assessments",
            }
            else "api"
        )
        allowed, limit, remaining, retry_after = self.server.check_rate_limit(
            self.client_address[0], bucket
        )
        if not allowed:
            return Response.json(
                {
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": "Too many requests. Wait before trying again.",
                    }
                },
                status=429,
                headers={
                    "Retry-After": str(retry_after),
                    "RateLimit-Limit": str(limit),
                    "RateLimit-Remaining": "0",
                },
            )
        body = b""
        if method in {"POST", "PUT", "PATCH"}:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                return Response.json(
                    {
                        "error": {
                            "code": "length_required",
                            "message": "Content-Length is required.",
                        }
                    },
                    status=411,
                )
            try:
                content_length = int(raw_length)
            except ValueError:
                return Response.json(
                    {
                        "error": {
                            "code": "invalid_content_length",
                            "message": "Content-Length must be an integer.",
                        }
                    },
                    status=400,
                )
            if content_length < 0 or content_length > MAX_REQUEST_BYTES:
                return Response.json(
                    {
                        "error": {
                            "code": "request_too_large",
                            "message": "Request body exceeds the 1 MiB limit.",
                        }
                    },
                    status=413,
                )
            body = self.rfile.read(content_length)
        return self.server.api.dispatch(
            method,
            split.path,
            parse_qs(split.query, keep_blank_values=True),
            body,
        )

    def _serve_static(self, head_only: bool = False) -> None:
        split = urlsplit(self.path)
        route = split.path
        aliases = {
            "/": "index.html",
            "/map": "map.html",
            "/map/": "map.html",
            "/methodology": "methodology.html",
            "/methodology/": "methodology.html",
            "/data-sources": "info.html",
            "/data-sources/": "info.html",
            "/limitations": "info.html",
            "/limitations/": "info.html",
            "/about": "info.html",
            "/about/": "info.html",
            "/privacy": "info.html",
            "/privacy/": "info.html",
            "/offline": "info.html",
            "/offline/": "info.html",
        }
        relative = aliases.get(route, route.lstrip("/"))
        if re.fullmatch(r"/assessment/[A-Za-z0-9_-]{20,128}/?", route):
            relative = "map.html"
        if not relative or "\x00" in relative:
            self._send(
                Response.json(
                    {"error": {"code": "not_found", "message": "Page not found."}},
                    status=404,
                ),
                head_only,
            )
            return
        candidate = (self.server.web_root / relative).resolve()
        try:
            candidate.relative_to(self.server.web_root)
        except ValueError:
            self._send(
                Response.json(
                    {"error": {"code": "not_found", "message": "Page not found."}},
                    status=404,
                ),
                head_only,
            )
            return
        if not candidate.is_file():
            self._send(
                Response.json(
                    {"error": {"code": "not_found", "message": "Page not found."}},
                    status=404,
                ),
                head_only,
            )
            return
        content = candidate.read_bytes()
        content_type, _ = mimetypes.guess_type(candidate.name)
        if candidate.suffix == ".js":
            content_type = "text/javascript"
        elif candidate.suffix == ".webmanifest":
            content_type = "application/manifest+json"
        self._send(
            Response(
                200,
                content,
                {
                    "Content-Type": f"{content_type or 'application/octet-stream'}; charset=utf-8",
                    "Content-Length": str(len(content)),
                    "Cache-Control": (
                        "no-cache"
                        if candidate.suffix in {".html", ".js", ".css"}
                        else "public, max-age=3600"
                    ),
                },
            ),
            head_only,
        )

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if urlsplit(self.path).path.startswith("/api/"):
            try:
                self._send(self._api_response("GET"))
            except Exception:
                LOGGER.exception("Unhandled API error")
                self._send(
                    Response.json(
                        {
                            "error": {
                                "code": "internal_error",
                                "message": "The request could not be completed.",
                            }
                        },
                        status=500,
                    )
                )
        else:
            self._serve_static()

    def do_HEAD(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if urlsplit(self.path).path.startswith("/api/"):
            self._send(
                Response.json(
                    {
                        "error": {
                            "code": "method_not_allowed",
                            "message": "HEAD is not supported for API resources.",
                        }
                    },
                    status=405,
                    headers={"Allow": "GET, POST, OPTIONS"},
                ),
                head_only=True,
            )
        else:
            self._serve_static(head_only=True)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if not urlsplit(self.path).path.startswith("/api/"):
            self._send(
                Response.json(
                    {
                        "error": {
                            "code": "method_not_allowed",
                            "message": "POST is allowed only for approved API resources.",
                        }
                    },
                    status=405,
                    headers={"Allow": "GET, HEAD"},
                )
            )
            return
        try:
            self._send(self._api_response("POST"))
        except Exception:
            LOGGER.exception("Unhandled API error")
            self._send(
                Response.json(
                    {
                        "error": {
                            "code": "internal_error",
                            "message": "The request could not be completed.",
                        }
                    },
                    status=500,
                )
            )

    def do_OPTIONS(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._send(self._api_response("OPTIONS"))

    def log_message(self, format_string: str, *args: object) -> None:
        # Routine per-request activity is deliberately not an application feature.
        # Debug output is available for local protocol troubleshooting only.
        LOGGER.debug("HTTP %s", format_string % args)


def create_application(
    database_path: str | Path | None = None,
    model_path: str | Path | None = None,
    schema_path: str | Path | None = None,
    *,
    enable_ulap: bool = True,
    allow_test_fixtures: bool = False,
    runtime_data_mode: str | None = None,
) -> tuple[Api, Repository, FuzzyModel]:
    configured_database = database_path or os.environ.get("GEOSAFE_DB_PATH")
    resolved_database = Path(configured_database or PROJECT_ROOT / "data" / "geosafe.db")
    if configured_database is None and not resolved_database.exists():
        bundled_snapshot = PROJECT_ROOT / "data" / "geosafe.snapshot.db"
        if bundled_snapshot.is_file():
            resolved_database.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled_snapshot, resolved_database)

    model = FuzzyModel.from_file(
        model_path
        or os.environ.get("GEOSAFE_MODEL_PATH")
        or PROJECT_ROOT / "config" / "fuzzy_model.json"
    )
    repository = Repository(
        resolved_database,
        schema_path
        or os.environ.get("GEOSAFE_SCHEMA_PATH")
        or PROJECT_ROOT / "db" / "schema.sql",
    )
    repository.initialize(model)
    ulap = None
    if enable_ulap:
        configured_registry = os.environ.get("ULAP_SERVICES_CONFIG")
        registry_path = None
        if configured_registry:
            candidate = Path(configured_registry)
            registry_path = (
                candidate
                if candidate.is_absolute()
                else PROJECT_ROOT / candidate
            )
        ulap = UlapIntegration.from_environment(registry_path)
    service = GeoSafeService(
        repository,
        model,
        ulap,
        allow_test_fixtures=allow_test_fixtures,
        runtime_data_mode=(
            runtime_data_mode
            or os.environ.get("GEOSAFE_RUNTIME_DATA_MODE", "snapshot")
        ).strip().casefold(),
    )
    if ulap is not None and _environment_flag(
        "ULAP_LIVE_VALIDATION", default=False
    ):
        results = ulap.validate_services()
        LOGGER.info(
            "ULAP startup validation: %s",
            ", ".join(
                f"{item['service']}={item['status']}" for item in results
            ),
        )
    return Api(service), repository, model


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the unified Basafe Web-GIS prototype."
    )
    parser.add_argument(
        "--host", default=os.environ.get("GEOSAFE_HOST", "127.0.0.1")
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("GEOSAFE_PORT", "8000")),
    )
    parser.add_argument(
        "--database", default=os.environ.get("GEOSAFE_DB_PATH")
    )
    parser.add_argument(
        "--web-root",
        default=os.environ.get("GEOSAFE_WEB_ROOT", str(PROJECT_ROOT / "web")),
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=os.environ.get("GEOSAFE_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    api, _, model = create_application(database_path=args.database)
    server = GeoSafeServer((args.host, args.port), api, Path(args.web_root))
    LOGGER.info(
        "Basafe %s listening at http://%s:%s "
        "(runtime data mode: %s; unified interface; no user roles)",
        model.version,
        args.host,
        args.port,
        api.service.runtime_data_mode,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Stopping Basafe")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
