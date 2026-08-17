#!/usr/bin/env python3
"""Import verified routing-area and designated-center data into SQLite."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from geosafe.geometry import geometry_bbox, parse_geometry, validate_wgs84_point


def _classification(value: str) -> tuple[int, str]:
    if value == "official":
        return 1, "official"
    if value == "supplied-reference":
        return 0, "user_supplied_reference_pending_authority_verification"
    return 0, "non_authoritative_development_placeholder"


def _metadata(path: Path, args: argparse.Namespace) -> dict[str, Any]:
    return {
        "input_file": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_url": args.source_url,
        "source_license": args.source_license,
        "classification": _classification(args.data_classification)[1],
        "import_notice": (
            "Operator-declared official source; issuing authority must be documented."
            if args.data_classification == "official"
            else (
                "User-supplied reference pending issuing-authority verification; "
                "not enabled as an operational route destination."
                if args.data_classification == "supplied-reference"
                else "NON-AUTHORITATIVE DEVELOPMENT PLACEHOLDER — NOT FOR OPERATIONAL USE"
            )
        ),
    }


def import_area(args: argparse.Namespace) -> None:
    path = Path(args.input)
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features") if payload.get("type") == "FeatureCollection" else [payload]
    if not isinstance(features, list) or len(features) != 1:
        raise ValueError("The routing-area file must contain exactly one polygon feature.")
    geometry = parse_geometry(features[0])
    if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
        raise ValueError("The routing study area must be a Polygon or MultiPolygon.")
    bbox = geometry_bbox(geometry)
    if not (124 <= bbox[0] <= 126 and 10 <= bbox[1] <= 13):
        raise ValueError("The routing study area does not appear to be WGS84 Basey data.")
    is_official, _ = _classification(args.data_classification)
    metadata = _metadata(path, args)
    with sqlite3.connect(args.db) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        if args.replace:
            connection.execute("UPDATE routing_study_areas SET is_active = 0")
        connection.execute(
            """
            INSERT INTO routing_study_areas (
                name, version, geometry_geojson, source_name, source_date,
                source_metadata_json, is_official, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                args.name,
                args.version,
                json.dumps(geometry, separators=(",", ":")),
                args.source_name,
                args.source_date,
                json.dumps(metadata, sort_keys=True),
                is_official,
            ),
        )
    print(f"Imported routing study area {args.name!r} ({args.version}).")


def _optional_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    parsed = int(value)
    if parsed < 0:
        raise ValueError("capacity must not be negative")
    return parsed


def import_centers(args: argparse.Namespace) -> None:
    path = Path(args.input)
    metadata = _metadata(path, args)
    is_official, _ = _classification(args.data_classification)
    records: list[tuple[Any, ...]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        for line_number, row in enumerate(csv.DictReader(source), 2):
            name = (row.get("name") or "").strip()
            designation = (row.get("designation") or "").strip()
            source_name = (row.get("source") or args.source_name or "").strip()
            if not name or not designation or not source_name:
                raise ValueError(
                    f"Line {line_number}: name, designation, and source are required."
                )
            lat, lon = validate_wgs84_point(row.get("latitude"), row.get("longitude"))
            active_text = (row.get("active") or "true").strip().casefold()
            if active_text not in {"1", "0", "true", "false", "yes", "no"}:
                raise ValueError(f"Line {line_number}: active must be true or false.")
            records.append(
                (
                    (row.get("id") or "").strip() or None,
                    name,
                    lat,
                    lon,
                    (row.get("barangay") or "").strip() or None,
                    designation,
                    source_name,
                    (row.get("source_date") or args.source_date or "").strip() or None,
                    json.dumps(metadata, sort_keys=True),
                    args.version,
                    is_official,
                    int(active_text in {"1", "true", "yes"}),
                    _optional_int(row.get("capacity")),
                    (row.get("notes") or "").strip() or None,
                    (row.get("photo_url") or "").strip() or None,
                    (row.get("photo_alt") or "").strip() or None,
                    (row.get("photo_source") or "").strip() or None,
                    (row.get("photo_source_url") or "").strip() or None,
                )
            )
    if not records:
        raise ValueError("The center file contains no records; no fake centers were inserted.")
    with sqlite3.connect(args.db) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        if args.replace:
            connection.execute("UPDATE evacuation_centers SET active = 0")
        connection.executemany(
            """
            INSERT INTO evacuation_centers (
                external_id, name, latitude, longitude, barangay, designation,
                source_name, source_date, source_metadata_json, dataset_version,
                is_official, active, capacity, notes, photo_url, photo_alt,
                photo_source, photo_source_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )
    print(f"Imported {len(records)} designated evacuation-center record(s).")


def common(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument("input")
    subparser.add_argument("--db", default=str(ROOT / "data" / "geosafe.db"))
    subparser.add_argument("--version", required=True)
    subparser.add_argument("--source-name", required=True)
    subparser.add_argument("--source-date")
    subparser.add_argument("--source-url")
    subparser.add_argument("--source-license")
    subparser.add_argument(
        "--data-classification",
        choices=("official", "supplied-reference", "development-placeholder"),
        required=True,
    )
    subparser.add_argument("--replace", action="store_true")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    area = commands.add_parser("study-area")
    common(area)
    area.add_argument("--name", required=True)
    area.set_defaults(handler=import_area)
    centers = commands.add_parser("centers")
    common(centers)
    centers.set_defaults(handler=import_centers)
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
