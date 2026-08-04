#!/usr/bin/env python3
"""Live ULAP metadata smoke check.

The normal unit suite is offline. Run this script deliberately when network
verification is wanted; it exits non-zero while any required source (including
ground shaking) is not fully verified.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from geosafe.ulap import ArcGISClient, MetadataValidator, ServiceRegistry
from geosafe.ulap.models import Status, ValidationResult
from geosafe.ulap.service_registry import DEFAULT_REGISTRY_PATH, RegistryError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Request live ArcGIS service/layer metadata, validate configured fields, "
            "and report the supplied boundary GeoJSON audit. Tokens are read only "
            "from ULAP_TOKEN and are never printed."
        )
    )
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument(
        "--boundary-file",
        "--manifest",
        dest="boundary_file",
        type=Path,
        help=(
            "Override the supplied boundary file path recorded in the generated "
            "registry."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a table.",
    )
    return parser


def _result_row(result: ValidationResult) -> dict[str, Any]:
    return {
        "service": result.service,
        "required": result.required,
        "status": result.status.value,
        "http_status": result.http_status,
        "arcgis_error_code": result.arcgis_error_code,
        "source_url": result.source_url,
        "message": result.message,
        "differences": list(result.differences),
    }


def _table(results: list[ValidationResult]) -> str:
    headers = ("SERVICE", "REQUIRED", "STATUS", "HTTP", "MESSAGE")
    rows = [
        (
            result.service,
            "yes" if result.required else "no",
            result.status.value,
            str(result.http_status or "-"),
            result.message.replace("\n", " "),
        )
        for result in results
    ]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]
    rendered = [
        "  ".join(
            headers[index].ljust(widths[index]) for index in range(len(headers))
        ),
        "  ".join("-" * width for width in widths),
    ]
    for row in rows:
        rendered.append(
            "  ".join(
                row[index].ljust(widths[index]) for index in range(len(headers))
            )
        )
    return "\n".join(rendered)


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        registry = ServiceRegistry(arguments.registry)
        client = ArcGISClient.from_registry(registry)
        validator = MetadataValidator(client, registry)
        results = list(validator.validate_all())
        results.append(validator.validate_supplied_boundary(arguments.boundary_file))
    except (RegistryError, OSError, ValueError) as exc:
        print(f"ULAP verification could not start: {exc}", file=sys.stderr)
        return 1

    if arguments.json:
        print(
            json.dumps(
                {
                    "registry": str(arguments.registry.resolve()),
                    "results": [_result_row(result) for result in results],
                    "token_exposed": False,
                },
                indent=2,
            )
        )
    else:
        print(_table(results))

    invalid_required = [
        result
        for result in results
        if result.required and result.status != Status.VERIFIED
    ]
    if invalid_required:
        print(
            "\nRequired ULAP services are not fully verified: "
            + ", ".join(result.service for result in invalid_required),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
