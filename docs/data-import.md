# GeoSafe-FIS Data Import Guide

## 1. Purpose and boundary

Dataset preparation is a command-line deployment task. GeoSafe-FIS has no browser upload, publication, approval, administrator, or content-management workflow.

The implemented import tool is `scripts/import_dataset.py` for a single
municipal boundary, barangay, hazard, incident, or CLUP dataset. The repository
has no operational demonstration-data seeder.

Run commands from the project root. Use `python scripts/import_dataset.py --help` for the full field-mapping interface.

## 2. Supported targets

`import_dataset.py` accepts:

| Target | Required purpose-specific data |
| --- | --- |
| `municipal-boundary` | Polygon/MultiPolygon and a name field or `--boundary-name` |
| `barangays` | Polygon/MultiPolygon, barangay name, optional PSGC code |
| `hazard` | Geometry, classification, optional normalized fraction, dataset slug/name, and hazard type |
| `incidents` | Point/coordinates, incident type, title, and optional date/severity/barangay/description |
| `clup-references` | Reference type, title, optional geometry/barangay/document section/planning note |

Hazard type must be `flood`, `liquefaction`, or `ground_shaking`.

## 3. Supported formats and dependencies

| Input | Current support |
| --- | --- |
| GeoJSON/JSON | Standard library; FeatureCollection, Feature, or a supported geometry object |
| CSV | Standard library; longitude/latitude fields or a `geometry_geojson`/`geometry` column |
| Shapefile | Optional Fiona/GDAL |
| GeoPackage | Optional Fiona/GDAL; use `--layer` when it has multiple layers |
| GeoTIFF | Not inserted directly; inspect/vectorize externally and import classification polygons |

For a classified GeoTIFF, use Rasterio or a GIS tool to inspect its CRS, nodata values, band legend, extent, and resolution. Vectorize the relevant classified cells to GeoJSON with `classification` and `normalized_value` properties, then import that vector output. Preserve the raster provenance in the source/quality arguments. The prototype does not claim direct raster sampling.

## 4. Required provenance

Every import requires:

- `--source-name`; and
- `--data-classification official|demonstration`.

Supported additional provenance/quality options are:

- `--source-date`;
- `--source-url`;
- `--source-license`;
- `--quality-status verified|provisional|limited|unknown`;
- repeatable `--quality-note`;
- `--source-crs`; and
- optional `--error-log`.

Marking a dataset `official` records the operator’s explicit declaration. It does not independently authenticate the source or prove fitness for use. The operator must verify the issuing organization, currency, coverage, scale, and allowed use.

The importer stores:

- source name/date/URL/license;
- official/demonstration and quality status;
- source/stored CRS;
- original filename and SHA-256 digest;
- importer version and import-batch UUID;
- import time and accepted/rejected counts;
- validation warnings; and
- logged safe geometry repairs.

Only `official` and `demonstration` are accepted data classifications. The importer never defaults an unspecified dataset to official.

## 5. Hazard normalization contract

Hazard imports use two distinct domains:

1. `normalized_value` in the import file and SQLite is a documented fraction from `0` through `1`.
2. The assessment service multiplies that fraction by 100 and supplies the resulting `0` through `100` value to model `0.4.0-demo`.

For example, an imported fraction of `0.82` is exposed as:

```json
{
  "normalized_fraction": 0.82,
  "normalized_value": 82.0
}
```

The classification text and fraction are separate fields. The importer and model never infer a fraction from labels such as “Low,” “Moderate,” or “High.” Each deployment dataset must document and receive domain-expert validation for its class-to-fraction or measurement-to-fraction mapping.

This imported-data contract is separate from the live ULAP exact-code
transformations documented in
[fuzzy-data-transformations.md](fuzzy-data-transformations.md). A deployment
must retain which path produced each normalized value.

A hazard feature may retain a classification while its fraction is absent. At assessment time that input is `missing`, and because all three hazards are required, the assessment is incomplete. Missing is not converted to `0`.

## 6. Example imports

### 6.1 Municipal boundary

```powershell
python scripts/import_dataset.py municipal-boundary path/to/basey.geojson `
  --db data/geosafe.db `
  --source-name "Issuing organization and boundary title" `
  --source-date "YYYY-MM-DD" `
  --source-url "https://source.example/boundary" `
  --source-license "Applicable terms" `
  --data-classification official `
  --quality-status verified `
  --source-crs EPSG:4326 `
  --name-field name `
  --replace `
  --strict
```

### 6.2 Barangays

```powershell
python scripts/import_dataset.py barangays path/to/basey_barangays.geojson `
  --db data/geosafe.db `
  --source-name "Issuing organization and barangay dataset title" `
  --source-date "YYYY-MM-DD" `
  --data-classification official `
  --quality-status verified `
  --source-crs EPSG:4326 `
  --name-field barangay_name `
  --psgc-field psgc_code `
  --replace `
  --strict
```

### 6.3 Hazard layer

```powershell
python scripts/import_dataset.py hazard path/to/flood.geojson `
  --db data/geosafe.db `
  --slug flood-current `
  --dataset-name "Flood susceptibility" `
  --hazard-type flood `
  --classification-field class `
  --normalized-field normalized_value `
  --source-name "Issuing organization and hazard dataset title" `
  --source-date "YYYY-MM-DD" `
  --data-classification official `
  --quality-status provisional `
  --quality-note "State spatial, temporal, and classification limitations." `
  --replace `
  --strict
```

### 6.4 Incidents from coordinate CSV

```powershell
python scripts/import_dataset.py incidents path/to/incidents.csv `
  --db data/geosafe.db `
  --source-name "Incident-record custodian" `
  --source-date "YYYY-MM-DD" `
  --data-classification official `
  --quality-status provisional `
  --source-crs EPSG:4326 `
  --longitude-field longitude `
  --latitude-field latitude `
  --incident-date-field incident_date `
  --incident-type-field incident_type `
  --barangay-field barangay `
  --title-field title `
  --description-field description `
  --strict
```

### 6.5 CLUP references

```powershell
python scripts/import_dataset.py clup-references path/to/clup_references.geojson `
  --db data/geosafe.db `
  --source-name "Adopted CLUP title and issuing office" `
  --source-date "YYYY-MM-DD" `
  --data-classification official `
  --quality-status verified `
  --reference-type-field reference_type `
  --document-section-field document_section `
  --planning-note-field planning_note `
  --strict
```

## 7. CRS behavior

- RFC 7946 GeoJSON without a `crs` object is treated as `EPSG:4326`.
- A recognizable GeoJSON/Fiona CRS is detected when present.
- CSV has no embedded CRS, so provide `--source-crs`.
- `--source-crs` takes precedence over detected metadata; the operator must ensure an override is correct.
- EPSG:4326 and EPSG:3857 conversion is implemented without third-party packages.
- Other source CRS values require optional PyProj or prior GIS reprojection.
- PyProj uses longitude/easting first through `always_xy=True`.
- All stored geometry is WGS 84 GeoJSON, and resulting coordinates are checked for finiteness and valid longitude/latitude ranges.

The current importer does not automatically compare an explicit CRS override to embedded metadata or perform a Basey-specific extent/control-point test. Operators must review the imported layer in the map and against known control points.

## 8. Geometry and attribute validation

The native validator:

- accepts Point, MultiPoint, LineString, MultiLineString, Polygon, MultiPolygon, and GeometryCollection;
- requires boundary targets to be Polygon/MultiPolygon;
- requires incident targets to be Point;
- checks nested numeric coordinates, coordinate ranges, minimum line/ring size, and nonzero polygon-ring area;
- removes consecutive duplicate positions;
- closes open polygon rings; and
- rejects unsupported, empty, or structurally invalid geometry.

When Shapely is installed, the importer also checks topology. It attempts `make_valid` or `buffer(0)` and accepts a repair only if it is non-empty, valid, and preserves the semantic geometry family. Without Shapely, the import result records that advanced self-intersection checks were not performed.

The current importer does not automatically validate municipal/barangay gaps, cross-feature overlap, hazard precedence, or full municipal coverage. Those require deployment review and control-point checks.

Required attribute checks include:

- nonblank barangay names;
- nonblank hazard classifications;
- hazard fractions numeric and within `0–1` when supplied;
- incident type/title and point coordinates; and
- CLUP reference type/title.

Field names are configurable and matched case-insensitively.

## 9. Error and transaction behavior

All source features are prepared and validated before the database is opened for insertion.

- Rejected features are written as JSON Lines to `<input>.import-errors.jsonl` or the `--error-log` path.
- Each error includes import batch ID, feature ID/index, message, and time.
- With `--strict`, any rejected feature prevents all database insertion and the command exits with code `1`.
- Without `--strict`, valid rows are committed, rejected rows are logged, and the command exits with code `2`.
- Fatal configuration, input, CRS, or SQLite errors exit with code `1`.
- A fully successful import exits with code `0`.
- Database insertion itself is transactional.

The CLI does not currently expose a separate dry-run or validation-only command. Use `--strict` with a disposable/staging database for a non-production validation run.

## 10. Replacement behavior

`--replace` is intentionally scoped:

- municipal boundaries, barangays, incidents, and CLUP references replace only records with the same official/demonstration classification;
- hazard replacement operates on the supplied stable dataset slug.

Without `--replace`, hazard slug conflicts fail. Other targets append records, subject to database constraints.

Imports are not a publication workflow. Runtime selection prefers official records where implemented, but operators must still verify the active/visible data through `/api/v1/data-sources`, the map, and control-point assessments.

## 11. Supplied Basey boundary file

`basey-barangay-boundary-final.json` must not be imported as default WGS 84.
It has no declared CRS. EPSG:3125 is a high-confidence inference, not issuer
confirmation. It also contains six unnamed features and differs from the live
PSA barangay count/boundary.

Operational import is blocked until issuer, CRS, version, use terms, PSGC
identifiers, and unnamed geometries are resolved. When confirmed, pass the
source CRS explicitly and retain the confirmation in source metadata. See
[ulap-json-audit.md](ulap-json-audit.md).

## 12. No operational synthetic seed

`config/data_sources.json` has an empty `datasets` array. Runtime hazards come
from the configured ULAP services; incidents and CLUP references remain absent
until authorized imports are performed.

Sanitized ArcGIS responses and synthetic geometries may exist only under
`tests/fixtures` or in explicit test setup. They are not production/development
assessment data, cannot fill a missing ULAP value, and cannot appear in a
report as official evidence. The runtime loads and normalizes
`config/fuzzy_model.json` independently.

## 13. Verification

The current `unittest` importer coverage verifies:

- an official hazard fraction is stored with provenance and SHA-256 metadata;
- an out-of-range fraction is rejected, logged, and not inserted in strict mode;
- EPSG:3857 geometry is transformed to WGS 84; and
- test fixtures require explicit test-mode opt-in and remain non-operational;
  and
- the supplied projected boundary fails unsafe no-CRS import and can be
  transformed only with an explicit supported CRS.

Before deploying real data, also perform manual/data-review checks for:

- source authority, licensing, currency, and completeness;
- expected row/feature counts and class distribution;
- Basey extent and coordinate-axis correctness;
- municipal/barangay gaps and overlaps;
- representative barangay and hazard lookup control points;
- incident and CLUP spatial/date precision;
- raster nodata remaining missing after vectorization; and
- visible official/demonstration and quality labels in the interface and PDF.
