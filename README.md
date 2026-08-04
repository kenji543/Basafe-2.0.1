# GeoSafe-FIS

GeoSafe-FIS is a focused Web-GIS decision-support prototype for Basey, Samar.
Its backend identifies a selected location and barangay through verified PSA
GeoRisk/ULAP services, retrieves available MGB flood and PHIVOLCS
liquefaction evidence, explains source and model transformations, and
generates a PDF assessment report.

The application has one unified interface. It intentionally contains no user
accounts, roles, permissions, staff dashboards, administrative portal,
approval workflow, browser upload manager, or model editor.

## Prototype status

The repository has no operational synthetic-data seed. Runtime boundary and
hazard evidence comes from the configured live ArcGIS services. Sanitized
responses and synthetic geometry exist only as isolated automated-test
fixtures and are rejected by normal server mode.

Live service/layer metadata for flood, liquefaction, municipal boundary, and
barangay boundary was independently reached on 2026-07-23. No verified
ground-shaking endpoint is configured, so a normal live three-hazard
assessment is explicitly `incomplete` with a null score. Historical incidents
and adopted CLUP references are also not configured until authorized data is
imported.

Fuzzy model `0.4.0-demo`, including its source-code transformations, is not
domain validated.

## Run locally

Use Python 3.11 or newer and install the declared Pydantic dependency:

```powershell
python -m pip install -e .
python -m geosafe.server
```

Open <http://127.0.0.1:8000>. The browser loads Leaflet and OpenStreetMap tiles
from their public CDNs. If those external resources are unavailable,
coordinate-based assessment remains available and the interface displays a
map availability notice.

The server initializes the approved schema, loads the versioned fuzzy and ULAP
registries, and retrieves live data through its backend. Configure
`ULAP_LIVE_VALIDATION=true` to validate service metadata during startup.

## Test

```powershell
python -m unittest discover -s tests -v
```

Deliberate live metadata smoke check:

```powershell
python scripts/verify_ulap_services.py `
  --boundary-file "C:\path\to\basey-barangay-boundary-final.json"
```

The smoke check currently exits `2` because required ground shaking has no
verified endpoint; inspect its per-service results for the independently
successful sources. Network integration tests are opt-in:

```powershell
$env:LIVE_ULAP_TESTS = "true"
python -m unittest tests.test_ulap_live -v
```

The test suite covers:

- ULAP registry, allowlisted URLs, ArcGIS errors, metadata/domain decoding,
  cache/retry behavior, and provider contracts with sanitized fixtures;
- spatial containment and live-provider barangay identification;
- complete and incomplete assessment workflows;
- membership functions, rule activations, score bounds, and categories;
- source status, fixture isolation, and missing-data behavior;
- PDF report generation and stored snapshots;
- GeoJSON/CSV import behavior and reprojection;
- the HTTP and frontend contracts; and
- negative scope checks proving that user, role, permission, admin, audit, and
  registration APIs/tables are absent.

## Data import

GeoJSON and coordinate CSV import require only Python. EPSG:4326 and EPSG:3857
are supported natively. Shapefile/GeoPackage and other coordinate systems can
be processed when Fiona/GDAL and PyProj are installed. Classified GeoTIFF data
must be inspected/vectorized with a GIS tool or Rasterio and imported with its
original raster metadata preserved.

See [data import](docs/data-import.md) and the
[command reference](scripts/README.md). Example:

```powershell
python scripts/import_dataset.py barangays path/to/basey_barangays.geojson `
  --db data/geosafe.db `
  --source-name "Issuing organization and dataset title" `
  --source-date "YYYY-MM-DD" `
  --data-classification official `
  --quality-status verified `
  --source-crs EPSG:4326 `
  --name-field barangay_name `
  --psgc-field psgc_code `
  --replace --strict
```

Declaring a dataset `official` records the deployer's explicit provenance
classification; the software cannot independently authenticate its issuer.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `GEOSAFE_HOST` | `127.0.0.1` | HTTP bind address |
| `GEOSAFE_PORT` | `8000` | HTTP port |
| `GEOSAFE_DB_PATH` | `data/geosafe.db` | SQLite database |
| `GEOSAFE_MODEL_PATH` | `config/fuzzy_model.json` | Versioned fuzzy model |
| `GEOSAFE_SCHEMA_PATH` | `db/schema.sql` | Approved database schema |
| `GEOSAFE_WEB_ROOT` | `web` | Unified static interface |
| `GEOSAFE_LOG_LEVEL` | `INFO` | Lightweight technical logging |
| `ULAP_HAZARDS_BASE_URL` | GeoRisk hazards REST root | Allowlisted hazard service base |
| `ULAP_NGA_BASE_URL` | GeoRisk NGA REST root | Allowlisted boundary service base |
| `ULAP_TOKEN` | empty | Optional server-only ArcGIS token |
| `ULAP_REQUEST_TIMEOUT_SECONDS` | `15` | Per-request timeout |
| `ULAP_MAX_RETRIES` | `2` | Retries after the initial request |
| `ULAP_METADATA_CACHE_SECONDS` | `86400` | In-process metadata TTL |
| `ULAP_QUERY_CACHE_SECONDS` | `3600` | In-process query TTL |
| `ULAP_LIVE_VALIDATION` | `false` | Validate configured metadata at startup |
| `ULAP_SERVICES_CONFIG` | `config/ulap-services.generated.json` | Version-controlled source registry |

Authentication is not implemented in this prototype. If deployment later
requires basic perimeter protection, that should be a separately approved
single shared application password—not accounts, roles, or permissions.

## Documentation

- [Architecture and scope](docs/architecture.md)
- [API contract](docs/api.md)
- [Fuzzy methodology](docs/fuzzy-methodology.md)
- [Implementation plan](docs/implementation-plan.md)
- [Acceptance criteria](docs/acceptance-criteria.md)
- [Dataset import procedure](docs/data-import.md)
- [ULAP integration](docs/ulap-integration.md)
- [Supplied JSON and live-service audit](docs/ulap-json-audit.md)
- [Live field mappings](docs/ulap-field-mappings.md)
- [Source register](docs/data-sources.md)
- [Fuzzy source transformations](docs/fuzzy-data-transformations.md)
- [Error and availability handling](docs/ulap-error-handling.md)
- [Known data gaps](docs/known-data-gaps.md)

## Disclaimer

This output is a preliminary decision-support screening result based on the
availability and classifications of the cited source datasets. It is not an
official hazard certification, zoning approval, building-safety rating,
structural assessment, engineering recommendation, or disaster forecast.
