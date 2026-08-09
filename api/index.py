"""
Vercel WSGI entry point for GeoSafe-FIS.

Vercel calls `app(environ, start_response)` for every request routed to
this function.  Static files (everything under /web) are served directly
by Vercel's CDN via the routes defined in vercel.json – this handler only
sees /api/* requests.
"""
from __future__ import annotations

import json
import os
import sys
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

# ---------------------------------------------------------------------------
# Bootstrap – make the project root importable
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Lazy-initialise the GeoSafe service (cold-start once per instance)
# ---------------------------------------------------------------------------
_api = None


def _get_api():
    global _api
    if _api is not None:
        return _api

    from geosafe.api import Api
    from geosafe.fuzzy import FuzzyModel
    from geosafe.repository import Repository
    from geosafe.service import GeoSafeService
    from geosafe.ulap.integration import UlapIntegration

    db_path = os.environ.get(
        "GEOSAFE_DB_PATH",
        str(PROJECT_ROOT / "data" / "geosafe.db"),
    )
    config_path = os.environ.get(
        "GEOSAFE_CONFIG_PATH",
        str(PROJECT_ROOT / "config" / "fuzzy_model.json"),
    )

    repo = Repository(db_path)
    model = FuzzyModel(config_path)
    ulap = UlapIntegration()
    service = GeoSafeService(repo, model, ulap)
    _api = Api(service)
    return _api


# ---------------------------------------------------------------------------
# WSGI application
# ---------------------------------------------------------------------------
def app(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/")
    query_string = environ.get("QUERY_STRING", "")
    query = parse_qs(query_string, keep_blank_values=True)

    # Read request body for POST
    body = b""
    if method in {"POST", "PUT", "PATCH"}:
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except (ValueError, TypeError):
            length = 0
        if length > 0:
            body = environ["wsgi.input"].read(length)

    try:
        api = _get_api()
        response = api.dispatch(method, path, query, body)
    except Exception as exc:
        payload = json.dumps(
            {"error": {"code": "internal_error", "message": str(exc)}}
        ).encode()
        start_response(
            "500 Internal Server Error",
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(payload))),
            ],
        )
        return [payload]

    status_map = {
        200: "200 OK",
        201: "201 Created",
        204: "204 No Content",
        400: "400 Bad Request",
        401: "401 Unauthorized",
        403: "403 Forbidden",
        404: "404 Not Found",
        405: "405 Method Not Allowed",
        409: "409 Conflict",
        411: "411 Length Required",
        413: "413 Payload Too Large",
        422: "422 Unprocessable Entity",
        429: "429 Too Many Requests",
        500: "500 Internal Server Error",
    }
    status_line = status_map.get(response.status, f"{response.status} Unknown")

    headers = [
        # CORS – allow any origin for the public API
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type"),
        # Security
        ("X-Content-Type-Options", "nosniff"),
        ("Referrer-Policy", "strict-origin-when-cross-origin"),
    ]
    for k, v in response.headers.items():
        headers.append((k, v))

    start_response(status_line, headers)
    return [response.body] if response.body else [b""]
