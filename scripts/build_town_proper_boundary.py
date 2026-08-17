#!/usr/bin/env python3
"""Build Basey's researcher-defined town-proper routing boundary.

The composite uses the loaded polygons for Mercado, Palaypay, Baybay, Sulod,
Loyo, Buscada, and Lawa-an. Component geometries retain their source metadata;
the grouping itself is not represented as an independently issued boundary.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from geosafe.geometry import geometry_bbox
from geosafe.study_area import (
    TOWN_PROPER_BARANGAYS,
    combine_polygon_geometries,
    normalized_barangay_name,
)


def _load_components(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    connection.row_factory = sqlite3.Row
    expected = {normalized_barangay_name(name): name for name in TOWN_PROPER_BARANGAYS}
    matches: dict[str, list[sqlite3.Row]] = {name: [] for name in expected}
    for row in connection.execute(
        """
        SELECT id, name, psgc_code, geometry_geojson, source_metadata_json,
               is_official, is_demo
        FROM barangays
        ORDER BY name, id
        """
    ):
        key = normalized_barangay_name(row["name"])
        if key in matches:
            matches[key].append(row)

    missing = [expected[key] for key, rows in matches.items() if not rows]
    duplicates = [expected[key] for key, rows in matches.items() if len(rows) > 1]
    if missing or duplicates:
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if duplicates:
            details.append(f"duplicate matches: {', '.join(duplicates)}")
        raise ValueError("Town-proper barangay validation failed (" + "; ".join(details) + ").")

    components: list[dict[str, Any]] = []
    for requested_name in TOWN_PROPER_BARANGAYS:
        row = matches[normalized_barangay_name(requested_name)][0]
        if not row["is_official"] or row["is_demo"]:
            raise ValueError(
                f"{row['name']} is not an official non-demo source polygon; refusing to derive the boundary."
            )
        components.append(
            {
                "id": row["id"],
                "name": row["name"],
                "psgc_code": row["psgc_code"],
                "geometry": json.loads(row["geometry_geojson"]),
                "source_metadata": json.loads(row["source_metadata_json"] or "{}"),
            }
        )
    return components


def build_boundary(args: argparse.Namespace) -> None:
    with sqlite3.connect(args.db) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        components = _load_components(connection)
        geometry = combine_polygon_geometries(item["geometry"] for item in components)
        bbox = geometry_bbox(geometry)
        if not (124 <= bbox[0] <= 126 and 10 <= bbox[1] <= 13):
            raise ValueError("The composite geometry does not appear to be WGS84 Basey data.")

        metadata = {
            "classification": "researcher_defined_composite",
            "definition_supplied_by": "Basafe project researcher",
            "definition": list(TOWN_PROPER_BARANGAYS),
            "derivation_method": "MultiPolygon aggregation without dissolve or simplification",
            "derived_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "stored_crs": "EPSG:4326",
            "component_count": len(components),
            "components": [
                {
                    "barangay_id": item["id"],
                    "name": item["name"],
                    "psgc_code": item["psgc_code"],
                    "source_name": item["source_metadata"].get("source_name"),
                    "source_url": item["source_metadata"].get("source_url"),
                    "source_date": item["source_metadata"].get("source_date"),
                    "input_sha256": item["source_metadata"].get("input_sha256"),
                }
                for item in components
            ],
            "authority_notice": (
                "The component barangay polygons are loaded official PSA records. "
                "The seven-barangay town-proper grouping is a researcher-defined "
                "study boundary and is not represented as an independently issued "
                "municipal or evacuation-planning boundary."
            ),
        }
        if args.replace:
            connection.execute("UPDATE routing_study_areas SET is_active = 0")
        connection.execute(
            """
            INSERT INTO routing_study_areas (
                name, version, geometry_geojson, source_name, source_date,
                source_metadata_json, is_official, is_active
            ) VALUES (?, ?, ?, ?, NULL, ?, 0, 1)
            """,
            (
                args.name,
                args.version,
                json.dumps(geometry, separators=(",", ":")),
                "Researcher-defined composite of loaded official PSA barangay polygons",
                json.dumps(metadata, separators=(",", ":"), sort_keys=True),
            ),
        )
        connection.commit()

    print(
        f"Built {args.name!r} from {len(components)} barangays "
        f"as version {args.version!r}."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "data" / "geosafe.db"))
    parser.add_argument("--name", default="Basey Town Proper Routing Study Area")
    parser.add_argument("--version", default="barangay-composite-v1")
    parser.add_argument("--replace", action="store_true")
    build_boundary(parser.parse_args())


if __name__ == "__main__":
    main()
