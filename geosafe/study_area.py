"""Definitions and geometry helpers for the Basey routing study area."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from geosafe.geometry import GeometryError, parse_geometry


TOWN_PROPER_BARANGAYS = (
    "Mercado",
    "Palaypay",
    "Baybay",
    "Sulod",
    "Loyo",
    "Buscada",
    "Lawa-an",
)


def normalized_barangay_name(value: str) -> str:
    """Normalize display names while accepting PSA's ``(Pob.)`` suffix."""
    without_poblacion = re.sub(r"\s*\(pob\.\)\s*$", "", value, flags=re.IGNORECASE)
    return " ".join(without_poblacion.casefold().split())


def combine_polygon_geometries(
    geometries: Iterable[str | Mapping[str, Any]],
) -> dict[str, Any]:
    """Combine Polygon/MultiPolygon members without dissolving their borders."""
    polygons: list[Any] = []
    for value in geometries:
        geometry = parse_geometry(value)
        coordinates = geometry.get("coordinates")
        if geometry.get("type") == "Polygon":
            if not coordinates:
                raise GeometryError("A town-proper barangay polygon is empty.")
            polygons.append(coordinates)
        elif geometry.get("type") == "MultiPolygon":
            if not coordinates:
                raise GeometryError("A town-proper barangay multipolygon is empty.")
            polygons.extend(coordinates)
        else:
            raise GeometryError(
                "Town-proper components must be Polygon or MultiPolygon geometries."
            )
    if not polygons:
        raise GeometryError("No barangay polygons were supplied for the town proper.")
    return {"type": "MultiPolygon", "coordinates": polygons}
