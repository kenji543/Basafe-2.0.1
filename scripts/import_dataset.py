#!/usr/bin/env python3
"""Import GeoSafe-FIS spatial/reference data without requiring GIS packages.

GeoJSON and coordinate CSV files are supported by the Python standard library.
Fiona and pyproj are used opportunistically for additional vector formats and
coordinate reference systems, but are not required for EPSG:4326/3857 data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sqlite3
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


IMPORTER_VERSION = "1.0.0"
ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT_DIR / "db" / "schema.sql"
SUPPORTED_TARGETS = (
    "municipal-boundary",
    "barangays",
    "hazard",
    "incidents",
    "clup-references",
)


class ImportFailure(RuntimeError):
    """A fatal dataset or import configuration error."""


@dataclass
class ImportOptions:
    target: str
    input_path: Path
    database_path: Path
    schema_path: Path = DEFAULT_SCHEMA
    source_name: str = ""
    data_classification: str = ""
    source_date: str | None = None
    source_url: str | None = None
    source_license: str | None = None
    quality_status: str = "unknown"
    quality_notes: list[str] = field(default_factory=list)
    source_crs: str | None = None
    layer: str | None = None
    replace: bool = False
    strict: bool = False
    error_log: Path | None = None
    boundary_name: str = "Basey, Samar"
    slug: str | None = None
    dataset_name: str | None = None
    hazard_type: str | None = None
    name_field: str = "name"
    psgc_field: str = "psgc_code"
    classification_field: str = "classification"
    normalized_field: str = "normalized_value"
    longitude_field: str = "longitude"
    latitude_field: str = "latitude"
    incident_date_field: str = "incident_date"
    incident_type_field: str = "incident_type"
    severity_field: str = "severity"
    barangay_field: str = "barangay"
    title_field: str = "title"
    description_field: str = "description"
    reference_type_field: str = "reference_type"
    document_section_field: str = "document_section"
    planning_note_field: str = "planning_note"


@dataclass
class ImportResult:
    target: str
    input_path: str
    imported_count: int
    error_count: int
    warning_count: int
    import_batch_id: str
    error_log: str | None
    stored_crs: str = "EPSG:4326"

    def as_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "input_path": self.input_path,
            "imported_count": self.imported_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "import_batch_id": self.import_batch_id,
            "error_log": self.error_log,
            "stored_crs": self.stored_crs,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _property(properties: dict[str, Any], name: str, default: Any = None) -> Any:
    """Get a property by exact or case-insensitive field name."""
    if name in properties:
        value = properties[name]
        return default if value == "" else value
    wanted = name.casefold()
    for key, value in properties.items():
        if str(key).casefold() == wanted:
            return default if value == "" else value
    return default


def _parse_geojson_crs(document: dict[str, Any]) -> str:
    crs = document.get("crs")
    if not crs:
        # RFC 7946 GeoJSON is WGS 84 longitude/latitude.
        return "EPSG:4326"
    if isinstance(crs, dict):
        properties = crs.get("properties") or {}
        name = properties.get("name") or properties.get("code")
        if name:
            return str(name)
    raise ImportFailure(
        "The GeoJSON CRS declaration could not be interpreted. "
        "Pass --source-crs explicitly (for example, --source-crs EPSG:4326)."
    )


def _read_geojson(path: Path) -> tuple[list[dict[str, Any]], str]:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            document = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ImportFailure(f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc

    if not isinstance(document, dict):
        raise ImportFailure("GeoJSON root must be an object.")

    object_type = document.get("type")
    if object_type == "FeatureCollection":
        features = document.get("features")
        if not isinstance(features, list):
            raise ImportFailure("GeoJSON FeatureCollection.features must be an array.")
    elif object_type == "Feature":
        features = [document]
    elif object_type in {
        "Point",
        "MultiPoint",
        "LineString",
        "MultiLineString",
        "Polygon",
        "MultiPolygon",
        "GeometryCollection",
    }:
        features = [{"type": "Feature", "properties": {}, "geometry": document}]
    else:
        raise ImportFailure(
            "Expected a GeoJSON FeatureCollection, Feature, or supported geometry object."
        )
    return features, _parse_geojson_crs(document)


def _read_csv(path: Path, options: ImportOptions) -> tuple[list[dict[str, Any]], None]:
    features: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ImportFailure("CSV file has no header row.")
        for line_number, row in enumerate(reader, start=2):
            properties = dict(row)
            geometry: dict[str, Any] | None = None
            geometry_text = _property(properties, "geometry_geojson") or _property(
                properties, "geometry"
            )
            if geometry_text:
                try:
                    parsed = json.loads(str(geometry_text))
                except json.JSONDecodeError as exc:
                    properties["_csv_geometry_error"] = (
                        f"geometry column is not valid GeoJSON: {exc.msg}"
                    )
                else:
                    if isinstance(parsed, dict):
                        geometry = parsed
                    else:
                        properties["_csv_geometry_error"] = (
                            "geometry column must contain a GeoJSON object"
                        )
            else:
                longitude = _property(properties, options.longitude_field)
                latitude = _property(properties, options.latitude_field)
                if longitude is not None or latitude is not None:
                    try:
                        geometry = {
                            "type": "Point",
                            "coordinates": [float(longitude), float(latitude)],
                        }
                    except (TypeError, ValueError):
                        properties["_csv_geometry_error"] = (
                            f"{options.longitude_field} and {options.latitude_field} "
                            "must both be numeric"
                        )

            features.append(
                {
                    "type": "Feature",
                    "id": f"csv-line-{line_number}",
                    "properties": properties,
                    "geometry": geometry,
                }
            )
    return features, None


def _read_with_fiona(
    path: Path, layer: str | None
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        import fiona  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ImportFailure(
            f"{path.suffix} import requires the optional 'fiona' package and its GDAL "
            "runtime. Install Fiona, or convert the source to GeoJSON first."
        ) from exc

    if path.suffix.casefold() in {".gpkg", ".geopackage"} and layer is None:
        layers = list(fiona.listlayers(path))
        if len(layers) > 1:
            raise ImportFailure(
                "The GeoPackage contains multiple layers. Pass --layer with one of: "
                + ", ".join(layers)
            )
        if layers:
            layer = layers[0]

    try:
        with fiona.open(path, layer=layer) as source:
            crs = source.crs
            source_crs = crs.to_string() if hasattr(crs, "to_string") else str(crs or "")
            features = []
            for item in source:
                features.append(
                    {
                        "type": "Feature",
                        "id": item.get("id"),
                        "properties": dict(item.get("properties") or {}),
                        "geometry": (
                            json.loads(json.dumps(item.get("geometry")))
                            if item.get("geometry")
                            else None
                        ),
                    }
                )
    except Exception as exc:
        raise ImportFailure(f"Fiona could not read the vector dataset: {exc}") from exc
    return features, source_crs or None


def _load_features(
    path: Path, options: ImportOptions
) -> tuple[list[dict[str, Any]], str | None]:
    if not path.is_file():
        raise ImportFailure(f"Input dataset does not exist or is not a file: {path}")
    suffix = path.suffix.casefold()
    if suffix in {".geojson", ".json"}:
        return _read_geojson(path)
    if suffix == ".csv":
        return _read_csv(path, options)
    if suffix in {".shp", ".gpkg", ".geopackage"}:
        return _read_with_fiona(path, options.layer)
    if suffix in {".tif", ".tiff"}:
        raise ImportFailure(
            "GeoTIFF is a raster source and cannot be inserted directly into the "
            "prototype's vector feature table. Install 'rasterio' to inspect/vectorize "
            "the classified raster, export GeoJSON polygons with classification and "
            "normalized_value fields, then import that GeoJSON as a hazard dataset."
        )
    raise ImportFailure(
        f"Unsupported file extension '{path.suffix}'. Use GeoJSON or coordinate CSV. "
        "Shapefile and GeoPackage are available when optional Fiona/GDAL is installed."
    )


def _canonical_crs(value: str) -> str:
    normalized = value.strip().upper().replace(" ", "")
    if normalized in {
        "EPSG:4326",
        "4326",
        "CRS:84",
        "OGC:CRS84",
        "URN:OGC:DEF:CRS:OGC:1.3:CRS84",
        "URN:OGC:DEF:CRS:EPSG::4326",
    }:
        return "EPSG:4326"
    if normalized in {
        "EPSG:3857",
        "3857",
        "EPSG:900913",
        "900913",
        "URN:OGC:DEF:CRS:EPSG::3857",
    }:
        return "EPSG:3857"
    utm_match = re.fullmatch(r"(?:EPSG:)?(32[67]\d{2})", normalized)
    if utm_match:
        epsg = int(utm_match.group(1))
        if 32601 <= epsg <= 32660 or 32701 <= epsg <= 32760:
            return f"EPSG:{epsg}"
    return value.strip()


def _coordinate_transformer(
    source_crs: str,
) -> tuple[Callable[[float, float], tuple[float, float]], str]:
    canonical = _canonical_crs(source_crs)
    if canonical == "EPSG:4326":
        return (lambda x, y: (x, y)), canonical

    if canonical == "EPSG:3857":
        earth_radius = 6378137.0

        def web_mercator_to_wgs84(x: float, y: float) -> tuple[float, float]:
            longitude = math.degrees(x / earth_radius)
            latitude = math.degrees(2.0 * math.atan(math.exp(y / earth_radius)) - math.pi / 2.0)
            return longitude, latitude

        return web_mercator_to_wgs84, canonical

    utm_match = re.fullmatch(r"EPSG:(32[67]\d{2})", canonical)
    if utm_match:
        epsg = int(utm_match.group(1))
        zone = epsg % 100
        northern_hemisphere = epsg < 32700
        semi_major_axis = 6378137.0
        eccentricity_squared = 0.00669438
        scale_factor = 0.9996
        eccentricity_prime_squared = eccentricity_squared / (
            1.0 - eccentricity_squared
        )
        central_meridian = math.radians((zone - 1) * 6 - 180 + 3)

        def utm_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
            if not 100000 <= easting <= 1000000:
                raise ValueError(
                    f"UTM easting {easting} is outside the supported metre range"
                )
            if not 0 <= northing <= 10000000:
                raise ValueError(
                    f"UTM northing {northing} is outside the supported metre range"
                )
            x = easting - 500000.0
            y = northing if northern_hemisphere else northing - 10000000.0
            meridional_arc = y / scale_factor
            mu = meridional_arc / (
                semi_major_axis
                * (
                    1.0
                    - eccentricity_squared / 4.0
                    - 3.0 * eccentricity_squared**2 / 64.0
                    - 5.0 * eccentricity_squared**3 / 256.0
                )
            )
            e1 = (1.0 - math.sqrt(1.0 - eccentricity_squared)) / (
                1.0 + math.sqrt(1.0 - eccentricity_squared)
            )
            footprint_latitude = (
                mu
                + (3.0 * e1 / 2.0 - 27.0 * e1**3 / 32.0)
                * math.sin(2.0 * mu)
                + (21.0 * e1**2 / 16.0 - 55.0 * e1**4 / 32.0)
                * math.sin(4.0 * mu)
                + (151.0 * e1**3 / 96.0) * math.sin(6.0 * mu)
                + (1097.0 * e1**4 / 512.0) * math.sin(8.0 * mu)
            )
            sin_fp = math.sin(footprint_latitude)
            cos_fp = math.cos(footprint_latitude)
            tan_fp = math.tan(footprint_latitude)
            radius_curvature = semi_major_axis / math.sqrt(
                1.0 - eccentricity_squared * sin_fp**2
            )
            radius_meridian = (
                semi_major_axis
                * (1.0 - eccentricity_squared)
                / (1.0 - eccentricity_squared * sin_fp**2) ** 1.5
            )
            tangent_squared = tan_fp**2
            curvature = eccentricity_prime_squared * cos_fp**2
            d = x / (radius_curvature * scale_factor)
            latitude = footprint_latitude - (
                radius_curvature
                * tan_fp
                / radius_meridian
                * (
                    d**2 / 2.0
                    - (
                        5.0
                        + 3.0 * tangent_squared
                        + 10.0 * curvature
                        - 4.0 * curvature**2
                        - 9.0 * eccentricity_prime_squared
                    )
                    * d**4
                    / 24.0
                    + (
                        61.0
                        + 90.0 * tangent_squared
                        + 298.0 * curvature
                        + 45.0 * tangent_squared**2
                        - 252.0 * eccentricity_prime_squared
                        - 3.0 * curvature**2
                    )
                    * d**6
                    / 720.0
                )
            )
            longitude = central_meridian + (
                d
                - (1.0 + 2.0 * tangent_squared + curvature) * d**3 / 6.0
                + (
                    5.0
                    - 2.0 * curvature
                    + 28.0 * tangent_squared
                    - 3.0 * curvature**2
                    + 8.0 * eccentricity_prime_squared
                    + 24.0 * tangent_squared**2
                )
                * d**5
                / 120.0
            ) / cos_fp
            return math.degrees(longitude), math.degrees(latitude)

        return utm_to_wgs84, canonical

    try:
        from pyproj import Transformer  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ImportFailure(
            f"Reprojection from '{source_crs}' requires the optional 'pyproj' package. "
            "Install pyproj, reproject the data to EPSG:4326 in a GIS tool, or provide "
            "an EPSG:4326/3857 source."
        ) from exc
    try:
        transformer = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
    except Exception as exc:
        raise ImportFailure(
            f"pyproj could not interpret source CRS '{source_crs}': {exc}"
        ) from exc
    return (lambda x, y: transformer.transform(x, y)), canonical


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _transform_coordinates(
    coordinates: Any, transformer: Callable[[float, float], tuple[float, float]]
) -> Any:
    if (
        isinstance(coordinates, (list, tuple))
        and len(coordinates) >= 2
        and _is_number(coordinates[0])
        and _is_number(coordinates[1])
    ):
        longitude, latitude = transformer(float(coordinates[0]), float(coordinates[1]))
        return [longitude, latitude, *list(coordinates[2:])]
    if isinstance(coordinates, (list, tuple)):
        return [_transform_coordinates(item, transformer) for item in coordinates]
    raise ValueError("coordinates must be nested numeric arrays")


def _position(position: Any) -> list[float]:
    if not isinstance(position, (list, tuple)) or len(position) < 2:
        raise ValueError("coordinate position must contain longitude and latitude")
    if not _is_number(position[0]) or not _is_number(position[1]):
        raise ValueError("coordinate longitude and latitude must be numeric")
    converted = [float(value) if _is_number(value) else value for value in position]
    longitude, latitude = converted[0], converted[1]
    if not math.isfinite(longitude) or not math.isfinite(latitude):
        raise ValueError("coordinates must be finite")
    if longitude < -180.0 or longitude > 180.0:
        raise ValueError(f"longitude {longitude} is outside EPSG:4326 bounds")
    if latitude < -90.0 or latitude > 90.0:
        raise ValueError(f"latitude {latitude} is outside EPSG:4326 bounds")
    return converted


def _same_xy(first: list[Any], second: list[Any]) -> bool:
    return first[0] == second[0] and first[1] == second[1]


def _deduplicate_positions(positions: Iterable[Any]) -> tuple[list[list[Any]], bool]:
    cleaned: list[list[Any]] = []
    changed = False
    for raw_position in positions:
        current = _position(raw_position)
        if cleaned and _same_xy(cleaned[-1], current):
            changed = True
            continue
        cleaned.append(current)
    return cleaned, changed


def _repair_geometry_native(
    geometry: dict[str, Any], repairs: list[str]
) -> dict[str, Any]:
    geometry_type = geometry.get("type")
    supported = {
        "Point",
        "MultiPoint",
        "LineString",
        "MultiLineString",
        "Polygon",
        "MultiPolygon",
        "GeometryCollection",
    }
    if geometry_type not in supported:
        raise ValueError(f"unsupported geometry type '{geometry_type}'")

    if geometry_type == "GeometryCollection":
        geometries = geometry.get("geometries")
        if not isinstance(geometries, list) or not geometries:
            raise ValueError("GeometryCollection must contain at least one geometry")
        return {
            "type": "GeometryCollection",
            "geometries": [
                _repair_geometry_native(child, repairs) for child in geometries
            ],
        }

    coordinates = geometry.get("coordinates")
    if geometry_type == "Point":
        cleaned_coordinates: Any = _position(coordinates)
    elif geometry_type == "MultiPoint":
        if not isinstance(coordinates, list) or not coordinates:
            raise ValueError("MultiPoint must contain at least one position")
        cleaned_coordinates = [_position(item) for item in coordinates]
    elif geometry_type == "LineString":
        cleaned_coordinates, changed = _deduplicate_positions(coordinates or [])
        if changed:
            repairs.append("removed consecutive duplicate line coordinates")
        if len(cleaned_coordinates) < 2:
            raise ValueError("LineString must contain at least two distinct positions")
    elif geometry_type == "MultiLineString":
        if not isinstance(coordinates, list) or not coordinates:
            raise ValueError("MultiLineString must contain at least one line")
        cleaned_coordinates = []
        for raw_line in coordinates:
            line, changed = _deduplicate_positions(raw_line or [])
            if changed:
                repairs.append("removed consecutive duplicate line coordinates")
            if len(line) < 2:
                raise ValueError("each MultiLineString line must contain two positions")
            cleaned_coordinates.append(line)
    elif geometry_type == "Polygon":
        cleaned_coordinates = _repair_polygon_coordinates(coordinates, repairs)
    else:  # MultiPolygon
        if not isinstance(coordinates, list) or not coordinates:
            raise ValueError("MultiPolygon must contain at least one polygon")
        cleaned_coordinates = [
            _repair_polygon_coordinates(polygon, repairs) for polygon in coordinates
        ]
    return {"type": geometry_type, "coordinates": cleaned_coordinates}


def _repair_polygon_coordinates(
    coordinates: Any, repairs: list[str]
) -> list[list[list[Any]]]:
    if not isinstance(coordinates, list) or not coordinates:
        raise ValueError("Polygon must contain at least one linear ring")
    polygon: list[list[list[Any]]] = []
    for raw_ring in coordinates:
        ring, changed = _deduplicate_positions(raw_ring or [])
        if changed:
            repairs.append("removed consecutive duplicate polygon coordinates")
        if len(ring) >= 1 and not _same_xy(ring[0], ring[-1]):
            ring.append(list(ring[0]))
            repairs.append("closed an unclosed polygon ring")
        distinct_xy = {(position[0], position[1]) for position in ring[:-1]}
        if len(ring) < 4 or len(distinct_xy) < 3:
            raise ValueError("polygon rings require at least three distinct positions")
        signed_area = 0.0
        for first, second in zip(ring, ring[1:]):
            signed_area += first[0] * second[1] - second[0] * first[1]
        if abs(signed_area) < 1e-15:
            raise ValueError("polygon ring has zero area")
        polygon.append(ring)
    return polygon


def _optional_topology_check(
    geometry: dict[str, Any], repairs: list[str], warnings: set[str]
) -> dict[str, Any]:
    try:
        from shapely.geometry import mapping, shape  # type: ignore[import-not-found]
    except ImportError:
        warnings.add(
            "Shapely is unavailable; coordinate/ring validation was performed, "
            "but advanced self-intersection checks were not."
        )
        return geometry

    try:
        spatial_object = shape(geometry)
    except Exception as exc:
        raise ValueError(f"Shapely could not construct the geometry: {exc}") from exc
    if spatial_object.is_valid:
        return geometry

    original_type = spatial_object.geom_type
    try:
        try:
            from shapely import make_valid  # type: ignore[attr-defined]

            repaired_object = make_valid(spatial_object)
        except (ImportError, AttributeError):
            repaired_object = spatial_object.buffer(0)
    except Exception as exc:
        raise ValueError(f"invalid topology could not be repaired: {exc}") from exc

    allowed_repair_types = {
        "Polygon": {"Polygon", "MultiPolygon"},
        "MultiPolygon": {"Polygon", "MultiPolygon"},
        "LineString": {"LineString", "MultiLineString"},
        "MultiLineString": {"LineString", "MultiLineString"},
    }
    if (
        repaired_object.is_empty
        or repaired_object.geom_type not in allowed_repair_types.get(original_type, set())
    ):
        raise ValueError(
            "geometry is topologically invalid and automatic repair would change "
            f"its semantic type ({original_type} to {repaired_object.geom_type})"
        )
    repairs.append(
        f"repaired invalid topology ({original_type} to {repaired_object.geom_type})"
    )
    return json.loads(json.dumps(mapping(repaired_object)))


def _prepare_geometry(
    geometry: Any,
    transformer: Callable[[float, float], tuple[float, float]],
    warnings: set[str],
) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(geometry, dict):
        raise ValueError("feature has no GeoJSON geometry object")
    transformed = dict(geometry)
    if geometry.get("type") == "GeometryCollection":
        child_geometries = geometry.get("geometries")
        if not isinstance(child_geometries, list):
            raise ValueError("GeometryCollection.geometries must be an array")
        transformed["geometries"] = [
            _prepare_geometry(child, transformer, warnings)[0]
            for child in child_geometries
        ]
    else:
        transformed["coordinates"] = _transform_coordinates(
            geometry.get("coordinates"), transformer
        )
    repairs: list[str] = []
    cleaned = _repair_geometry_native(transformed, repairs)
    cleaned = _optional_topology_check(cleaned, repairs, warnings)
    return cleaned, repairs


def _feature_id(feature: dict[str, Any], index: int) -> str:
    identifier = feature.get("id")
    return str(identifier) if identifier is not None else f"feature-{index + 1}"


def _validate_options(options: ImportOptions) -> None:
    if options.target not in SUPPORTED_TARGETS:
        raise ImportFailure(f"Unknown import target '{options.target}'.")
    if not options.source_name.strip():
        raise ImportFailure("--source-name is required so provenance is not lost.")
    if options.data_classification not in {"official", "demonstration"}:
        raise ImportFailure(
            "--data-classification must explicitly be 'official' or 'demonstration'."
        )
    if options.quality_status not in {"verified", "provisional", "limited", "unknown"}:
        raise ImportFailure(
            "--quality-status must be verified, provisional, limited, or unknown."
        )
    if options.target == "hazard":
        missing = [
            flag
            for flag, value in (
                ("--slug", options.slug),
                ("--dataset-name", options.dataset_name),
                ("--hazard-type", options.hazard_type),
            )
            if not value
        ]
        if missing:
            raise ImportFailure("Hazard imports require " + ", ".join(missing) + ".")
        if options.hazard_type not in {"flood", "liquefaction", "ground_shaking"}:
            raise ImportFailure(
                "--hazard-type must be flood, liquefaction, or ground_shaking."
            )


def _write_error_log(path: Path, errors: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for error in errors:
            handle.write(_compact_json(error) + "\n")


def _source_metadata(
    options: ImportOptions,
    source_crs: str,
    import_batch_id: str,
    imported_count: int,
    errors: list[dict[str, Any]],
    warnings: set[str],
    repairs: list[dict[str, Any]],
) -> dict[str, Any]:
    is_demo = options.data_classification == "demonstration"
    return {
        "source_name": options.source_name,
        "source_date": options.source_date,
        "source_url": options.source_url,
        "license": options.source_license,
        "data_classification": options.data_classification,
        "required_notice": (
            "DEMONSTRATION DATA — NOT OFFICIAL. Do not use for operational, "
            "regulatory, engineering, or life-safety decisions."
            if is_demo
            else "Marked official by the importer operator; verify currency and "
            "fitness for the intended planning use."
        ),
        "quality_status": options.quality_status,
        "quality_notes": options.quality_notes,
        "availability_notice": (
            None if options.source_date else "Source date was not supplied."
        ),
        "input_file": options.input_path.name,
        "input_sha256": _file_sha256(options.input_path),
        "source_crs": source_crs,
        "stored_crs": "EPSG:4326",
        "importer_version": IMPORTER_VERSION,
        "import_batch_id": import_batch_id,
        "imported_at": _utc_now(),
        "imported_feature_count": imported_count,
        "rejected_feature_count": len(errors),
        "validation_warnings": sorted(warnings),
        "safe_geometry_repairs": repairs,
    }


def _connect_database(options: ImportOptions) -> sqlite3.Connection:
    if not options.schema_path.is_file():
        raise ImportFailure(f"Database schema was not found: {options.schema_path}")
    options.database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(options.database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        connection.executescript(options.schema_path.read_text(encoding="utf-8"))
    except (OSError, sqlite3.Error) as exc:
        connection.close()
        raise ImportFailure(f"Could not initialize the SQLite schema: {exc}") from exc
    return connection


def _resolve_barangay_id(
    connection: sqlite3.Connection, barangay_name: Any
) -> int | None:
    if barangay_name is None or not str(barangay_name).strip():
        return None
    row = connection.execute(
        "SELECT id FROM barangays WHERE lower(name) = lower(?) ORDER BY id LIMIT 1",
        (str(barangay_name).strip(),),
    ).fetchone()
    return int(row["id"]) if row else None


def _insert_prepared_rows(
    connection: sqlite3.Connection,
    options: ImportOptions,
    rows: list[dict[str, Any]],
    metadata_json: str,
) -> int:
    is_demo = int(options.data_classification == "demonstration")
    is_official = 1 - is_demo

    if options.target == "municipal-boundary":
        if options.replace:
            connection.execute(
                "DELETE FROM municipal_boundary WHERE is_demo = ?", (is_demo,)
            )
        for row in rows:
            connection.execute(
                """
                INSERT INTO municipal_boundary
                    (name, geometry_geojson, source_metadata_json, is_official, is_demo)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row["name"],
                    row["geometry_geojson"],
                    metadata_json,
                    is_official,
                    is_demo,
                ),
            )

    elif options.target == "barangays":
        if options.replace:
            connection.execute("DELETE FROM barangays WHERE is_demo = ?", (is_demo,))
        for row in rows:
            connection.execute(
                """
                INSERT INTO barangays
                    (name, psgc_code, geometry_geojson, source_metadata_json,
                     is_official, is_demo)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row["name"],
                    row["psgc_code"],
                    row["geometry_geojson"],
                    metadata_json,
                    is_official,
                    is_demo,
                ),
            )

    elif options.target == "hazard":
        existing = connection.execute(
            "SELECT id, is_official FROM hazard_datasets WHERE slug = ?",
            (options.slug,),
        ).fetchone()
        if existing and not options.replace:
            raise ImportFailure(
                f"Hazard dataset slug '{options.slug}' already exists. "
                "Use --replace to replace that dataset and its features."
            )
        if (
            existing
            and options.data_classification == "demonstration"
            and bool(existing["is_official"])
        ):
            raise ImportFailure(
                f"Demonstration import refused to replace official hazard dataset "
                f"slug '{options.slug}'. Use a distinct demonstration slug."
            )
        if existing:
            dataset_id = int(existing["id"])
            connection.execute(
                """
                UPDATE hazard_datasets
                   SET name = ?, hazard_type = ?, source_name = ?, source_date = ?,
                       quality_status = ?, is_official = ?, is_demo = ?,
                       metadata_json = ?, imported_at = CURRENT_TIMESTAMP
                 WHERE id = ?
                """,
                (
                    options.dataset_name,
                    options.hazard_type,
                    options.source_name,
                    options.source_date,
                    options.quality_status,
                    is_official,
                    is_demo,
                    metadata_json,
                    dataset_id,
                ),
            )
            connection.execute(
                "DELETE FROM hazard_features WHERE dataset_id = ?", (dataset_id,)
            )
        else:
            cursor = connection.execute(
                """
                INSERT INTO hazard_datasets
                    (slug, name, hazard_type, source_name, source_date, quality_status,
                     is_official, is_demo, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    options.slug,
                    options.dataset_name,
                    options.hazard_type,
                    options.source_name,
                    options.source_date,
                    options.quality_status,
                    is_official,
                    is_demo,
                    metadata_json,
                ),
            )
            dataset_id = int(cursor.lastrowid)
        for row in rows:
            connection.execute(
                """
                INSERT INTO hazard_features
                    (dataset_id, classification, normalized_value,
                     geometry_geojson, properties_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    dataset_id,
                    row["classification"],
                    row["normalized_value"],
                    row["geometry_geojson"],
                    row["properties_json"],
                ),
            )

    elif options.target == "incidents":
        if options.replace:
            connection.execute(
                "DELETE FROM historical_incidents WHERE is_demo = ?", (is_demo,)
            )
        for row in rows:
            barangay_id = _resolve_barangay_id(connection, row["barangay"])
            connection.execute(
                """
                INSERT INTO historical_incidents
                    (incident_date, incident_type, severity, barangay_id, barangay,
                     latitude, longitude, geometry_geojson, title, description,
                     source_metadata_json, is_official, is_demo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["incident_date"],
                    row["incident_type"],
                    row["severity"],
                    barangay_id,
                    row["barangay"],
                    row["latitude"],
                    row["longitude"],
                    row["geometry_geojson"],
                    row["title"],
                    row["description"],
                    metadata_json,
                    is_official,
                    is_demo,
                ),
            )

    elif options.target == "clup-references":
        if options.replace:
            connection.execute(
                "DELETE FROM clup_references WHERE is_demo = ?", (is_demo,)
            )
        for row in rows:
            barangay_id = _resolve_barangay_id(connection, row["barangay"])
            connection.execute(
                """
                INSERT INTO clup_references
                    (reference_type, title, description, document_section,
                     planning_note, barangay_id, geometry_geojson,
                     source_metadata_json, is_official, is_demo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["reference_type"],
                    row["title"],
                    row["description"],
                    row["document_section"],
                    row["planning_note"],
                    barangay_id,
                    row["geometry_geojson"],
                    metadata_json,
                    is_official,
                    is_demo,
                ),
            )
    return len(rows)


def import_dataset(options: ImportOptions) -> ImportResult:
    """Validate, normalize to EPSG:4326, and import one configured dataset."""
    options.input_path = options.input_path.resolve()
    options.database_path = options.database_path.resolve()
    options.schema_path = options.schema_path.resolve()
    _validate_options(options)
    features, detected_crs = _load_features(options.input_path, options)
    source_crs = options.source_crs or detected_crs
    if not source_crs:
        raise ImportFailure(
            "The source did not declare a coordinate reference system. "
            "Pass --source-crs (for example, --source-crs EPSG:4326)."
        )
    transformer, canonical_source_crs = _coordinate_transformer(source_crs)

    import_batch_id = str(uuid.uuid4())
    errors: list[dict[str, Any]] = []
    warnings: set[str] = set()
    repairs: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []

    for index, feature in enumerate(features):
        identifier = _feature_id(feature, index)
        try:
            if not isinstance(feature, dict) or feature.get("type") != "Feature":
                raise ValueError("entry is not a GeoJSON Feature")
            properties = feature.get("properties") or {}
            if not isinstance(properties, dict):
                raise ValueError("feature properties must be an object")
            csv_geometry_error = properties.pop("_csv_geometry_error", None)
            if csv_geometry_error:
                raise ValueError(csv_geometry_error)

            geometry = feature.get("geometry")
            prepared_geometry: dict[str, Any] | None = None
            feature_repairs: list[str] = []
            if geometry is not None:
                prepared_geometry, feature_repairs = _prepare_geometry(
                    geometry, transformer, warnings
                )
                if feature_repairs:
                    repairs.append(
                        {"feature_id": identifier, "actions": sorted(set(feature_repairs))}
                    )

            if options.target in {"municipal-boundary", "barangays"}:
                if prepared_geometry is None or prepared_geometry["type"] not in {
                    "Polygon",
                    "MultiPolygon",
                }:
                    raise ValueError("boundary features require Polygon or MultiPolygon geometry")

            if options.target == "municipal-boundary":
                rows.append(
                    {
                        "name": str(
                            _property(properties, options.name_field, options.boundary_name)
                        ).strip(),
                        "geometry_geojson": _compact_json(prepared_geometry),
                    }
                )
            elif options.target == "barangays":
                name = _property(properties, options.name_field)
                if name is None or not str(name).strip():
                    raise ValueError(
                        f"missing barangay name field '{options.name_field}'"
                    )
                psgc_code = _property(properties, options.psgc_field)
                rows.append(
                    {
                        "name": str(name).strip(),
                        "psgc_code": (
                            str(psgc_code).strip()
                            if psgc_code is not None and str(psgc_code).strip()
                            else None
                        ),
                        "geometry_geojson": _compact_json(prepared_geometry),
                    }
                )
            elif options.target == "hazard":
                if prepared_geometry is None:
                    raise ValueError("hazard feature has no geometry")
                classification = _property(properties, options.classification_field)
                if classification is None or not str(classification).strip():
                    raise ValueError(
                        f"missing hazard classification field "
                        f"'{options.classification_field}'"
                    )
                normalized_raw = _property(properties, options.normalized_field)
                normalized_value = None
                if normalized_raw is not None:
                    try:
                        normalized_value = float(normalized_raw)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(
                            f"'{options.normalized_field}' must be numeric"
                        ) from exc
                    if not 0.0 <= normalized_value <= 1.0:
                        raise ValueError(
                            f"'{options.normalized_field}' must be between 0 and 1"
                        )
                rows.append(
                    {
                        "classification": str(classification).strip(),
                        "normalized_value": normalized_value,
                        "geometry_geojson": _compact_json(prepared_geometry),
                        "properties_json": _compact_json(properties),
                    }
                )
            elif options.target == "incidents":
                if prepared_geometry is None or prepared_geometry["type"] != "Point":
                    raise ValueError("incident records require Point geometry/coordinates")
                incident_type = _property(properties, options.incident_type_field)
                title = _property(properties, options.title_field)
                if incident_type is None or not str(incident_type).strip():
                    raise ValueError(
                        f"missing incident type field '{options.incident_type_field}'"
                    )
                if title is None or not str(title).strip():
                    raise ValueError(f"missing title field '{options.title_field}'")
                longitude, latitude = prepared_geometry["coordinates"][:2]
                rows.append(
                    {
                        "incident_date": _property(
                            properties, options.incident_date_field
                        ),
                        "incident_type": str(incident_type).strip(),
                        "severity": _property(properties, options.severity_field),
                        "barangay": _property(properties, options.barangay_field),
                        "latitude": latitude,
                        "longitude": longitude,
                        "geometry_geojson": _compact_json(prepared_geometry),
                        "title": str(title).strip(),
                        "description": _property(
                            properties, options.description_field
                        ),
                    }
                )
            else:  # clup-references
                title = _property(properties, options.title_field)
                reference_type = _property(
                    properties, options.reference_type_field
                )
                if title is None or not str(title).strip():
                    raise ValueError(f"missing title field '{options.title_field}'")
                if reference_type is None or not str(reference_type).strip():
                    raise ValueError(
                        f"missing reference type field "
                        f"'{options.reference_type_field}'"
                    )
                rows.append(
                    {
                        "reference_type": str(reference_type).strip(),
                        "title": str(title).strip(),
                        "description": _property(
                            properties, options.description_field
                        ),
                        "document_section": _property(
                            properties, options.document_section_field
                        ),
                        "planning_note": _property(
                            properties, options.planning_note_field
                        ),
                        "barangay": _property(properties, options.barangay_field),
                        "geometry_geojson": (
                            _compact_json(prepared_geometry)
                            if prepared_geometry is not None
                            else None
                        ),
                    }
                )
        except (TypeError, ValueError) as exc:
            errors.append(
                {
                    "import_batch_id": import_batch_id,
                    "feature_id": identifier,
                    "feature_index": index,
                    "error": str(exc),
                    "recorded_at": _utc_now(),
                }
            )

    error_log_path = options.error_log
    if errors:
        if error_log_path is None:
            error_log_path = options.input_path.with_name(
                options.input_path.name + ".import-errors.jsonl"
            )
        _write_error_log(error_log_path, errors)
    if errors and options.strict:
        raise ImportFailure(
            f"{len(errors)} feature(s) failed validation; strict mode prevented import. "
            f"Details: {error_log_path}"
        )
    if not rows:
        raise ImportFailure(
            "No valid records remained after validation."
            + (f" Details: {error_log_path}" if error_log_path else "")
        )

    metadata = _source_metadata(
        options,
        canonical_source_crs,
        import_batch_id,
        len(rows),
        errors,
        warnings,
        repairs,
    )
    connection = _connect_database(options)
    try:
        with connection:
            imported_count = _insert_prepared_rows(
                connection, options, rows, _compact_json(metadata)
            )
    except sqlite3.Error as exc:
        raise ImportFailure(f"SQLite rejected the import: {exc}") from exc
    finally:
        connection.close()

    return ImportResult(
        target=options.target,
        input_path=str(options.input_path),
        imported_count=imported_count,
        error_count=len(errors),
        warning_count=len(warnings),
        import_batch_id=import_batch_id,
        error_log=str(error_log_path) if error_log_path and errors else None,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and import a GeoSafe-FIS dataset into SQLite. GeoJSON and "
            "coordinate CSV need no third-party packages."
        )
    )
    parser.add_argument("target", choices=SUPPORTED_TARGETS)
    parser.add_argument("input_path", type=Path)
    parser.add_argument("--db", dest="database_path", type=Path, required=True)
    parser.add_argument("--schema", dest="schema_path", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--source-name", required=True)
    parser.add_argument(
        "--data-classification",
        required=True,
        choices=("official", "demonstration"),
        help="Explicitly distinguish official from demonstration data.",
    )
    parser.add_argument("--source-date")
    parser.add_argument("--source-url")
    parser.add_argument("--source-license")
    parser.add_argument(
        "--quality-status",
        choices=("verified", "provisional", "limited", "unknown"),
        default="unknown",
    )
    parser.add_argument("--quality-note", action="append", default=[])
    parser.add_argument("--source-crs")
    parser.add_argument("--layer", help="Layer name for a multi-layer GeoPackage.")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Import nothing when any individual feature fails validation.",
    )
    parser.add_argument("--error-log", type=Path)
    parser.add_argument("--boundary-name", default="Basey, Samar")
    parser.add_argument("--slug")
    parser.add_argument("--dataset-name")
    parser.add_argument(
        "--hazard-type",
        choices=("flood", "liquefaction", "ground_shaking"),
    )
    parser.add_argument("--name-field", default="name")
    parser.add_argument("--psgc-field", default="psgc_code")
    parser.add_argument("--classification-field", default="classification")
    parser.add_argument(
        "--normalized-field",
        default="normalized_value",
        help=(
            "Field containing the hazard value normalized to the inclusive 0–1 "
            "range. Runtime fuzzy inputs may scale this stored fraction to 0–100."
        ),
    )
    parser.add_argument("--longitude-field", default="longitude")
    parser.add_argument("--latitude-field", default="latitude")
    parser.add_argument("--incident-date-field", default="incident_date")
    parser.add_argument("--incident-type-field", default="incident_type")
    parser.add_argument("--severity-field", default="severity")
    parser.add_argument("--barangay-field", default="barangay")
    parser.add_argument("--title-field", default="title")
    parser.add_argument("--description-field", default="description")
    parser.add_argument("--reference-type-field", default="reference_type")
    parser.add_argument("--document-section-field", default="document_section")
    parser.add_argument("--planning-note-field", default="planning_note")
    return parser


def _options_from_namespace(arguments: argparse.Namespace) -> ImportOptions:
    values = vars(arguments).copy()
    values["quality_notes"] = values.pop("quality_note")
    return ImportOptions(**values)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    try:
        result = import_dataset(_options_from_namespace(arguments))
    except (ImportFailure, OSError) as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result.as_dict(), indent=2))
    return 2 if result.error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
