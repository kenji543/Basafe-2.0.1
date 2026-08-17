#!/usr/bin/env python3
"""Normalize the supplied Basey evacuation-center inventory for safe import."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from geosafe.geometry import haversine_km, point_in_geometry

SOURCE_NAME = (
    "Municipal Disaster Risk Reduction and Management Office of Basey "
    "(MDRRMO) — researcher-transcribed scoped extract"
)
DESIGNATION = "Existing evacuation center/facility (source inventory status)"
NAME_OVERRIDES = {
    "Basey I Central Elem. School": "Basey I Central Elementary School",
    "St. Michael Parish Church, Brgy. Mercado, BS.": "St. Michael Parish Church",
    "Evacuation Facility, Brgy. Mercado, BS.": "Evacuation Facility",
    "Mun. Gymnasium, Brgy. Mercado": "Municipal Gymnasium",
    "Mun. Town Hall, Brgy. Mercado, BS.": "Municipal Town Hall",
    "BDH, Brgy. Canmanila, BS.": "Basey District Hospital (BDH)",
    "Community Evacuation Center, So. Bangon, Brgy. Canmanila, B.S.": (
        "Community Evacuation Center (Sitio Bangon)"
    ),
    "Basey Manpower Training Center, Brgy. Mercado, BS.": (
        "Basey Manpower Training Center"
    ),
    "ABC Hall, Brgy. Mercado, B.S.": "ABC Hall",
}


def dms_to_decimal(value: str) -> float:
    """Convert a DMS coordinate containing N/S/E/W into decimal degrees."""
    match = re.fullmatch(
        r"\s*(\d+)[°º]\s*(\d+)[\'’]\s*([0-9.]+)[\"”]?\s*([NSEW])\s*",
        value,
    )
    if match is None:
        raise ValueError(f"Unsupported DMS coordinate: {value!r}")
    degrees, minutes, seconds = map(float, match.group(1, 2, 3))
    if minutes >= 60 or seconds >= 60:
        raise ValueError(f"Invalid DMS coordinate: {value!r}")
    decimal = degrees + minutes / 60 + seconds / 3600
    return -decimal if match.group(4) in {"S", "W"} else decimal


def _loaded_spatial_context(db_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    connection = sqlite3.connect(db_path)
    try:
        connection.row_factory = sqlite3.Row
        area = connection.execute(
            """
            SELECT name, version, geometry_geojson
            FROM routing_study_areas
            WHERE is_active = 1
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        barangays = connection.execute(
            "SELECT name, geometry_geojson FROM barangays ORDER BY name"
        ).fetchall()
    finally:
        connection.close()
    if area is None:
        raise ValueError("No active routing study area is loaded.")
    return dict(area), [dict(row) for row in barangays]


def normalize(source: Path, db_path: Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "No.",
            "Evacuation Center / Facility",
            "Point",
            "Latitude",
            "Longitude",
            "Status",
        }
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"Source CSV must contain: {', '.join(sorted(required))}")
        source_rows = list(reader)
    if not source_rows:
        raise ValueError("Source CSV contains no evacuation-center rows.")

    grouped: OrderedDict[tuple[str, str], list[dict[str, Any]]] = OrderedDict()
    for line_number, row in enumerate(source_rows, 2):
        source_id = row["No."].strip()
        source_name = row["Evacuation Center / Facility"].strip()
        status = row["Status"].strip()
        if not source_id or not source_name or not status:
            raise ValueError(f"Line {line_number}: number, facility, and status are required.")
        grouped.setdefault((source_id, source_name), []).append(
            {
                "line": line_number,
                "point": row["Point"].strip(),
                "latitude": dms_to_decimal(row["Latitude"]),
                "longitude": dms_to_decimal(row["Longitude"]),
                "status": status,
            }
        )

    area, barangays = _loaded_spatial_context(db_path)
    records: list[dict[str, str]] = []
    quality_notes: list[dict[str, Any]] = []
    for (source_id, source_facility), points in grouped.items():
        statuses = {item["status"].casefold() for item in points}
        if statuses != {"existing"}:
            raise ValueError(
                f"Facility {source_id} has unsupported or mixed status values: {statuses}"
            )
        latitude = sum(item["latitude"] for item in points) / len(points)
        longitude = sum(item["longitude"] for item in points) / len(points)
        if not point_in_geometry(latitude, longitude, area["geometry_geojson"]):
            raise ValueError(f"Facility {source_id} is outside the active routing study area.")
        matched_barangays = [
            barangay["name"]
            for barangay in barangays
            if point_in_geometry(
                latitude, longitude, barangay["geometry_geojson"]
            )
        ]
        if len(matched_barangays) != 1:
            raise ValueError(
                f"Facility {source_id} must match exactly one loaded barangay polygon; "
                f"found {matched_barangays}."
            )
        max_spread_m = max(
            haversine_km(
                latitude,
                longitude,
                item["latitude"],
                item["longitude"],
            )
            * 1000
            for item in points
        )
        point_labels = [item["point"] for item in points if item["point"]]
        note_parts = [
            f"Normalized from {len(points)} source coordinate row(s).",
            f"PSA polygon match: {matched_barangays[0]}.",
            "Transcribed from a photographed MDRRMO inventory supplied directly "
            "to the researcher; out-of-scope centers shown in the image were excluded.",
            "The source image and its publication date are not yet archived in the repository.",
        ]
        if point_labels:
            note_parts.append(f"Source point labels: {', '.join(point_labels)}.")
        records.append(
            {
                "id": f"BASEY-EC-{int(source_id):02d}",
                "name": NAME_OVERRIDES.get(source_facility, source_facility),
                "latitude": f"{latitude:.7f}",
                "longitude": f"{longitude:.7f}",
                "barangay": matched_barangays[0],
                "designation": DESIGNATION,
                "source": SOURCE_NAME,
                "source_date": "",
                "active": "true",
                "capacity": "",
                "notes": " ".join(note_parts),
                "photo_url": "",
                "photo_alt": "",
                "photo_source": "",
                "photo_source_url": "",
            }
        )
        quality_notes.append(
            {
                "id": records[-1]["id"],
                "source_facility": source_facility,
                "normalized_name": records[-1]["name"],
                "source_row_count": len(points),
                "max_distance_from_representative_point_m": round(max_spread_m, 1),
                "polygon_barangay": matched_barangays[0],
            }
        )
    metadata = {
        "source_file": source.name,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_row_count": len(source_rows),
        "normalized_facility_count": len(records),
        "study_area_name": area["name"],
        "study_area_version": area["version"],
        "coordinate_reference_system": "EPSG:4326",
        "classification": "operator_declared_official_source",
        "source_authority": (
            "Municipal Disaster Risk Reduction and Management Office of Basey (MDRRMO)"
        ),
        "authority_confirmation_basis": (
            "Researcher states the photographed inventory was acquired directly "
            "from the MDRRMO office."
        ),
        "authority_confirmed_on": "2026-08-18",
        "source_medium": "Photograph transcribed to CSV",
        "scope_filter": (
            "Only facilities aligned with the seven-barangay town-proper study "
            "scope were transcribed; unrelated facilities visible in the source "
            "image were intentionally excluded."
        ),
        "source_image_archived": False,
        "transformation": (
            "DMS coordinates converted to decimal degrees; repeated facility rows "
            "collapsed to one arithmetic-mean representative point."
        ),
        "quality_notes": quality_notes,
    }
    return records, metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("--db", default=str(ROOT / "data" / "geosafe.db"))
    parser.add_argument(
        "--output",
        default=str(ROOT / "data" / "routing" / "basey_town_proper_evacuation_centers.csv"),
    )
    parser.add_argument(
        "--metadata-output",
        default=str(
            ROOT
            / "data"
            / "routing"
            / "basey_town_proper_evacuation_centers.metadata.json"
        ),
    )
    args = parser.parse_args()
    records, metadata = normalize(Path(args.source), Path(args.db))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    metadata_output = Path(args.metadata_output)
    metadata_output.parent.mkdir(parents=True, exist_ok=True)
    metadata_output.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Normalized {metadata['source_row_count']} rows into "
        f"{metadata['normalized_facility_count']} facilities."
    )


if __name__ == "__main__":
    main()
