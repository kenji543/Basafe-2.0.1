"""Small, dependency-free geographic helpers for the prototype.

The runtime stores normalized WGS84 GeoJSON. Heavyweight validation,
reprojection, and safe repair belong in the import pipeline rather than the
request path.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from typing import Any


class GeometryError(ValueError):
    """Raised when a geometry cannot be interpreted safely."""


def parse_geometry(value: str | Mapping[str, Any]) -> dict[str, Any]:
    """Return a GeoJSON geometry from a JSON string, Feature, or geometry."""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise GeometryError("Geometry contains invalid JSON.") from exc
    elif isinstance(value, Mapping):
        parsed = dict(value)
    else:
        raise GeometryError("Geometry must be a GeoJSON object or JSON string.")

    if parsed.get("type") == "Feature":
        parsed = parsed.get("geometry")
    if not isinstance(parsed, dict) or "type" not in parsed:
        raise GeometryError("GeoJSON geometry type is missing.")
    return parsed


def validate_wgs84_point(latitude: float, longitude: float) -> tuple[float, float]:
    """Validate and normalize a WGS84 latitude/longitude pair."""
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError) as exc:
        raise GeometryError("Latitude and longitude must be numbers.") from exc
    if not math.isfinite(lat) or not math.isfinite(lon):
        raise GeometryError("Latitude and longitude must be finite numbers.")
    if not -90 <= lat <= 90:
        raise GeometryError("Latitude must be between -90 and 90.")
    if not -180 <= lon <= 180:
        raise GeometryError("Longitude must be between -180 and 180.")
    return lat, lon


def _point_on_segment(
    x: float,
    y: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    epsilon: float = 1e-10,
) -> bool:
    squared_length = (x2 - x1) ** 2 + (y2 - y1) ** 2
    if squared_length <= epsilon**2:
        return abs(x - x1) <= epsilon and abs(y - y1) <= epsilon
    cross = (y - y1) * (x2 - x1) - (x - x1) * (y2 - y1)
    if abs(cross) > epsilon:
        return False
    dot = (x - x1) * (x2 - x1) + (y - y1) * (y2 - y1)
    if dot < -epsilon:
        return False
    return dot <= squared_length + epsilon


def point_in_ring(longitude: float, latitude: float, ring: Iterable[Any]) -> bool:
    """Return whether a point is inside (or on the edge of) a linear ring."""
    points = list(ring)
    if len(points) < 4:
        return False
    inside = False
    previous = points[-1]
    for current in points:
        try:
            x1, y1 = float(previous[0]), float(previous[1])
            x2, y2 = float(current[0]), float(current[1])
        except (TypeError, ValueError, IndexError) as exc:
            raise GeometryError("A polygon coordinate is invalid.") from exc
        if _point_on_segment(longitude, latitude, x1, y1, x2, y2):
            return True
        crosses = (y1 > latitude) != (y2 > latitude)
        if crosses:
            x_intersection = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
            if longitude < x_intersection:
                inside = not inside
        previous = current
    return inside


def _point_in_polygon(longitude: float, latitude: float, polygon: list[Any]) -> bool:
    if not polygon or not point_in_ring(longitude, latitude, polygon[0]):
        return False
    return not any(point_in_ring(longitude, latitude, hole) for hole in polygon[1:])


def point_in_geometry(
    latitude: float,
    longitude: float,
    geometry: str | Mapping[str, Any],
) -> bool:
    """Test a WGS84 point against GeoJSON Polygon or MultiPolygon geometry."""
    lat, lon = validate_wgs84_point(latitude, longitude)
    parsed = parse_geometry(geometry)
    coordinates = parsed.get("coordinates")
    if parsed["type"] == "Polygon":
        return _point_in_polygon(lon, lat, coordinates or [])
    if parsed["type"] == "MultiPolygon":
        return any(_point_in_polygon(lon, lat, polygon) for polygon in coordinates or [])
    if parsed["type"] == "Point":
        try:
            return math.isclose(lon, float(coordinates[0])) and math.isclose(
                lat, float(coordinates[1])
            )
        except (TypeError, ValueError, IndexError) as exc:
            raise GeometryError("Point coordinates are invalid.") from exc
    if parsed["type"] == "MultiPoint":
        try:
            return any(
                math.isclose(lon, float(position[0]))
                and math.isclose(lat, float(position[1]))
                for position in coordinates or []
            )
        except (TypeError, ValueError, IndexError) as exc:
            raise GeometryError("MultiPoint coordinates are invalid.") from exc
    if parsed["type"] in {"LineString", "MultiLineString"}:
        lines = [coordinates] if parsed["type"] == "LineString" else coordinates
        try:
            for line in lines or []:
                for start, end in zip(line, line[1:]):
                    if _point_on_segment(
                        lon,
                        lat,
                        float(start[0]),
                        float(start[1]),
                        float(end[0]),
                        float(end[1]),
                    ):
                        return True
            return False
        except (TypeError, ValueError, IndexError) as exc:
            raise GeometryError("Line coordinates are invalid.") from exc
    if parsed["type"] == "GeometryCollection":
        geometries = parsed.get("geometries")
        if not isinstance(geometries, list):
            raise GeometryError("GeometryCollection.geometries must be a list.")
        return any(point_in_geometry(lat, lon, child) for child in geometries)
    raise GeometryError(
        f"Point identification does not support GeoJSON type {parsed['type']!r}."
    )


def _iter_positions(coordinates: Any) -> Iterable[tuple[float, float]]:
    if (
        isinstance(coordinates, (list, tuple))
        and len(coordinates) >= 2
        and all(isinstance(value, (int, float)) for value in coordinates[:2])
    ):
        yield float(coordinates[0]), float(coordinates[1])
        return
    if isinstance(coordinates, (list, tuple)):
        for child in coordinates:
            yield from _iter_positions(child)


def geometry_bbox(geometry: str | Mapping[str, Any]) -> list[float]:
    """Return a GeoJSON-style [min_lon, min_lat, max_lon, max_lat] bbox."""
    parsed = parse_geometry(geometry)
    positions = list(_iter_positions(parsed.get("coordinates")))
    if not positions:
        raise GeometryError("Geometry has no usable coordinates.")
    longitudes, latitudes = zip(*positions)
    return [min(longitudes), min(latitudes), max(longitudes), max(latitudes)]


def representative_point(geometry: str | Mapping[str, Any]) -> dict[str, float]:
    """Return the bounding-box center for search-result map positioning."""
    min_lon, min_lat, max_lon, max_lat = geometry_bbox(geometry)
    return {
        "latitude": round((min_lat + max_lat) / 2, 6),
        "longitude": round((min_lon + max_lon) / 2, 6),
    }


def haversine_km(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    """Great-circle distance between two WGS84 coordinates in kilometres."""
    lat_a, lon_a = validate_wgs84_point(latitude_a, longitude_a)
    lat_b, lon_b = validate_wgs84_point(latitude_b, longitude_b)
    radius_km = 6371.0088
    phi_a, phi_b = math.radians(lat_a), math.radians(lat_b)
    delta_phi = math.radians(lat_b - lat_a)
    delta_lambda = math.radians(lon_b - lon_a)
    hav = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi_a) * math.cos(phi_b) * math.sin(delta_lambda / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(hav), math.sqrt(1 - hav))


def as_feature(
    geometry: str | Mapping[str, Any],
    properties: Mapping[str, Any],
    feature_id: str | int | None = None,
) -> dict[str, Any]:
    """Create a serializable GeoJSON Feature."""
    feature: dict[str, Any] = {
        "type": "Feature",
        "geometry": parse_geometry(geometry),
        "properties": dict(properties),
    }
    if feature_id is not None:
        feature["id"] = feature_id
    return feature
