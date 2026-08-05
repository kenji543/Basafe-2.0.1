# GeoSafe-FIS data preparation

These command-line tools keep dataset preparation outside the Web-GIS
interface. They create no accounts, roles, approval queues, or administrative
pages.

## Synchronize official-service snapshots

Ordinary map and assessment requests use local snapshots and do not contact
ULAP. Run synchronization deliberately during deployment or scheduled
maintenance:

```powershell
python scripts/sync_ulap_snapshot.py `
  --db data/geosafe.db `
  --target municipal_boundary `
  --target barangay_boundary `
  --target flood `
  --target liquefaction `
  --target ground_shaking
```

Targets may be repeated and include `flood`, `liquefaction`, and
`ground_shaking`. The synchronizer downloads only Basey-filtered boundary or
hazard data, validates exact source codes against the versioned model mapping,
then uses the standard strict importer. Flood can fall back from a rejected
ArcGIS `Query` request to the official MapServer `identify` operation. Ground
shaking is generated from four fixed, allowlisted official PHIVOLCS 2014
Region VIII deterministic-scenario KMZs: their PEIS rasters are sampled into a
roughly 550 m Basey grid and the maximum of the four scenario intensities is
stored. This derivative is marked `limited`, not represented as an official
PHIVOLCS vector product, and must be domain-validated before operational use.
It never replaces an existing snapshot when download, schema, geometry, or
mapping validation fails. A partial run exits with code `2` and reports each
preserved target.

The synchronized files are temporary; the durable copy, provenance, checksum,
and import-batch metadata are stored in SQLite. Confirm source authority,
currency, licensing, and fitness before operational deployment.

## No operational demonstration seed

The repository intentionally has no development/demo seeder and ships no
synthetic hazard polygons. Runtime hazard values must come from activated,
validated local snapshots. Mock ArcGIS payloads exist only in isolated
automated-test fixtures.

Verify the live service registry with:

```powershell
$env:LIVE_ULAP_TESTS = "true"
python scripts/verify_ulap_services.py `
  --manifest "C:\path\to\basey-barangay-boundary-final.json"
```

The supplied JSON is a projected barangay FeatureCollection rather than an
ArcGIS-service manifest. The verifier reports that distinction and validates
the independently configured service candidates without claiming they came
from the file.

## Import an authoritative dataset

The operator must explicitly classify every import and supply its provenance.
Marking an import `official` records the operator's declaration; it does not
independently authenticate or validate the issuing organization.

The supplied `basey-barangay-boundary-final.json` has no declared CRS or issuing
agency metadata. Its coordinate ranges strongly indicate EPSG:3125 (PRS92 /
Philippines zone 5), but that inference, its six unnamed features, and its
differences from the live PSA boundary must be confirmed before import. After
confirmation, install the GIS dependencies and use an explicit CRS:

```powershell
python -m pip install -e ".[gis]"
python scripts/import_dataset.py barangays `
  "C:\path\to\basey-barangay-boundary-final.json" `
  --db data/geosafe.db `
  --source-name "Confirmed issuing LGU and dataset title" `
  --source-date "YYYY-MM-DD" `
  --data-classification official `
  --quality-status provisional `
  --quality-note "CRS and source authority confirmed by: ..." `
  --source-crs EPSG:3125 `
  --name-field BARANGAY `
  --psgc-field BRGY_INDEX `
  --replace `
  --strict
```

The current file will fail strict import until its six blank `BARANGAY` values
are resolved. This is intentional; unnamed polygons must not be silently
discarded from an authoritative boundary load.

```powershell
python scripts/import_dataset.py barangays path/to/basey_barangays.geojson `
  --db data/geosafe.db `
  --source-name "Issuing organization and dataset title" `
  --source-date "YYYY-MM-DD" `
  --source-url "https://source.example/dataset" `
  --source-license "Applicable terms" `
  --data-classification official `
  --quality-status verified `
  --source-crs EPSG:4326 `
  --name-field barangay_name `
  --psgc-field psgc_code `
  --replace `
  --strict
```

Hazard imports additionally require a stable slug, display name, and one of
the approved hazard types. `normalized_value` is stored as a fraction from
`0` through `1`; runtime assessment code may multiply it by 100 when a fuzzy
model uses a 0–100 input domain.

```powershell
python scripts/import_dataset.py hazard path/to/flood.geojson `
  --db data/geosafe.db `
  --slug flood-current `
  --dataset-name "Flood susceptibility" `
  --hazard-type flood `
  --classification-field class `
  --normalized-field normalized_value `
  --source-name "Issuing organization and dataset title" `
  --source-date "YYYY-MM-DD" `
  --data-classification official `
  --quality-status provisional `
  --quality-note "State the known spatial, temporal, and classification limits." `
  --replace `
  --strict
```

Valid import targets are:

- `municipal-boundary`
- `barangays`
- `hazard` (`flood`, `liquefaction`, or `ground_shaking`)
- `incidents`
- `clup-references`

Run `python scripts/import_dataset.py --help` for field-mapping switches.

## Formats and coordinate systems

GeoJSON and CSV containing longitude/latitude columns use only the Python
standard library. CSV files do not declare a coordinate reference system, so
pass `--source-crs`. A CSV `geometry_geojson` column may alternatively contain
a GeoJSON geometry object.

EPSG:4326, EPSG:3857, and WGS84 UTM zones are supported natively. Other
coordinate reference systems, including EPSG:3125, require the optional
`pyproj` dependency; the command stops with installation or pre-conversion
guidance when it is unavailable.

Shapefile and GeoPackage input is enabled when optional Fiona/GDAL is
installed. Multi-layer GeoPackages require `--layer`. GeoTIFF is not stored
directly in the vector-only prototype schema: inspect and vectorize its
classified cells with Rasterio or a GIS tool, preserve the raster's source
metadata, export classification polygons to GeoJSON, and import those
polygons.

## Validation and error records

The importer:

- checks required fields, coordinate finiteness/ranges, geometry types, ring
  size, and normalized values;
- reprojects all stored geometry to EPSG:4326;
- safely removes consecutive duplicate vertices and closes open polygon rings;
- uses Shapely, when present, to validate and safely repair topology without
  changing the semantic geometry family;
- stores source, date, license, input checksum, CRS, quality, import batch, and
  validation details as JSON metadata; and
- writes rejected feature details to
  `<input-name>.import-errors.jsonl` (or `--error-log`) without adding an
  administrative/audit subsystem.

With `--strict`, any rejected feature prevents database insertion. Without it,
valid records are committed and the process exits with code `2` to flag the
partial import. Fatal configuration or dataset errors exit with code `1`.

Missing required hazard data must remain missing. Import scripts never convert
absence into a low classification; assessment logic must mark the result
incomplete.
