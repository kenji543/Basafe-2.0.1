# GeoRisk Philippines ULAP Integration

## 1. Purpose and scope

Basafe uses a backend-only ArcGIS REST integration as a controlled data
synchronization and diagnostic source. Normal map and assessment requests use
validated local snapshots, so an upstream outage cannot interrupt an already
provisioned deployment. Official source values remain separate from the fuzzy
model transformation.

The integration does not add accounts, roles, staff dashboards, source-approval
screens, browser upload/publication, or a fuzzy-model editor. Source
configuration remains a version-controlled deployment concern.

No verified ground-shaking source is currently configured. The backend returns
it as unavailable and blocks a complete three-hazard score.

## 2. Components

| File/component | Responsibility |
| --- | --- |
| `config/ulap-services.generated.json` | Approved-host registry, service/layer paths, expected schemas/domains, field mappings, verification record, and supplied-file audit |
| `config/data_sources.json` | Deployment source requirements and supplied-boundary readiness status |
| `config/fuzzy_model.json` | Versioned source-code-to-model transformations and fuzzy model |
| `geosafe/ulap/service_registry.py` | Load/validate configuration, apply safe environment overrides, and expose typed service definitions |
| `geosafe/ulap/arcgis_client.py` | HTTPS ArcGIS metadata/query client, coordinate validation, pagination, retries, TTL cache, redirects, token injection, and SSRF allowlist |
| `geosafe/ulap/metadata_validator.py` | Compare live service/layer metadata with the registry and audit the supplied JSON |
| `geosafe/ulap/boundary_provider.py` | Point-based Basey containment and barangay identification |
| `geosafe/ulap/hazard_provider.py` | Point-based hazard retrieval, domain decoding, official-value preservation, overlap handling, and completeness gate |
| `geosafe/ulap/integration.py` | Application facade for validation state, live API summaries, Basey-filtered geometry, point results, and model transformation handoff |
| `geosafe/ulap/response_parser.py` | ArcGIS error parsing, field/domain extraction, attribute decoding, and response-shape validation |
| `geosafe/ulap/models.py` | Strict Pydantic v2 response/status contracts |
| `geosafe/ulap/errors.py` | Structured sanitized failures and secret redaction |
| `scripts/verify_ulap_services.py` | Deliberate live service/layer metadata smoke check |
| `scripts/sync_ulap_snapshot.py` | Deliberate Basey download, validation, and atomic activation into SQLite |
| `.env.example` | Non-secret deployment settings |

The ArcGIS client uses the Python standard-library HTTP stack. Pydantic v2
validates integration contracts. PyProj and Shapely are optional GIS
dependencies for data-import/audit work, not required for ordinary EPSG:4326
point queries.

## 3. Request paths

The following legacy path applies only when
`GEOSAFE_RUNTIME_DATA_MODE=live` is explicitly selected:

```text
browser
  → Basafe /api/v1 endpoint
    → coordinate and Basey workflow validation
      → ServiceRegistry
      → MetadataValidator / BoundaryProvider / HazardProvider
        → ArcGISClient
          → allowlisted GeoRisk HTTPS service
    ← typed, sanitized source result
  ← display source, status, quality, transformation, and incomplete/score state
```

Even in live mode, the browser never calls ULAP directly and never receives an
ArcGIS token. Backend routing provides schema validation, retry/cache behavior,
attribution, error normalization, and request throttling.

### Snapshot request path

```text
operator synchronization
  -> allowlisted GeoRisk HTTPS service
  -> schema / geometry / exact-code validation
  -> strict atomic import into SQLite

browser assessment
  -> local Basey containment and point-in-polygon lookup
  -> fuzzy completeness gate and calculation
  -> source, snapshot, quality, transformation, and result display
```

The browser never calls ULAP directly and never receives an ArcGIS token.
Snapshot mode also prevents assessment API calls from contacting ULAP through
the backend. Explicit `/api/v1/ulap/*` maintenance endpoints remain live
diagnostics and are not part of the assessment path.

## 4. Runtime configuration

The example environment defines:

```text
ULAP_HAZARDS_BASE_URL=https://ulap-hazards.georisk.gov.ph/arcgis/rest/services
ULAP_NGA_BASE_URL=https://ulap-nga.georisk.gov.ph/arcgis/rest/services
ULAP_TOKEN=
ULAP_REQUEST_TIMEOUT_SECONDS=15
ULAP_MAX_RETRIES=2
ULAP_METADATA_CACHE_SECONDS=86400
ULAP_QUERY_CACHE_SECONDS=3600
ULAP_LIVE_VALIDATION=true
ULAP_ALLOW_STALE_CACHE=false
ULAP_SERVICES_CONFIG=config/ulap-services.generated.json
GEOSAFE_RUNTIME_DATA_MODE=snapshot
```

`snapshot` is the normal mode. `live` retains direct-query behavior for
diagnostics and compatibility testing, but should not be used when offline
continuity is required. Snapshot mode never silently falls through to live:
an absent local hazard remains missing and produces an incomplete assessment.

Only the two GeoRisk hosts are allowed. Base URL overrides still undergo
scheme, hostname, credential, port, and fragment validation. The token is
optional, read only on the server, and omitted from logs/cache keys/responses.

The current cache is in-process memory. It never serves expired entries and
does not implement a stale fallback; `ULAP_ALLOW_STALE_CACHE=false` documents
that deployment policy.

## 5. Metadata validation

For each configured source, validation requests:

```text
{serviceUrl}?f=pjson
{layerUrl}?f=pjson
```

It checks:

- service response and listed layer ID;
- layer existence and `Feature Layer` type;
- layer name;
- polygon geometry;
- spatial reference;
- required `Query` capability;
- classification-field presence;
- coded-value domain or unique-value renderer;
- expected/live domain differences;
- maximum record count, supported query formats, version, description, and
  attribution for reporting; and
- sanitized cache/HTTP details.

Metadata differences are returned as
`verified_with_changed_metadata`; a missing classification field or wrong
layer produces a blocking status. The provider repeats field/domain validation
before point use so a stale startup assumption cannot silently reinterpret a
live code.

The supplied boundary file is checksummed and structurally inspected by the
validator, but remains `pending_verification` because its CRS and authority are
undeclared.

## 6. Point queries

For a WGS 84 point, the client sends encoded parameters equivalent to:

```text
geometry={longitude},{latitude}
geometryType=esriGeometryPoint
inSR=4326
spatialRel=esriSpatialRelIntersects
outFields=*
returnGeometry=false
outSR=4326
f=json
```

Longitude and latitude must be finite and within `[-180, 180]` and
`[-90, 90]`. Parameter dictionaries and URL encoding are used; a user-supplied
coordinate is not concatenated into a SQL `where` clause.

The response parser requires an object root and a `features` array. It
preserves complete raw attributes, decodes known coded fields from the live
domain, records retrieval/cache information, and counts intersections.

## 7. Basey and barangay identification

The boundary provider:

1. queries the municipal polygon layer at the point;
2. compares returned municipality/province values case-insensitively with
   Basey and Samar;
3. rejects/flags a point with no municipal polygon or another municipality;
4. queries the barangay layer only for an inside-Basey point;
5. returns the official barangay spelling, municipal/provincial/barangay codes,
   and PSGC when available; and
6. reports missing or overlapping barangay results explicitly.

The provider does not rely on the unverified supplied JSON or name-only joins
for live identification.

## 8. Hazard retrieval

For each configured hazard, the provider:

1. loads current layer metadata;
2. locates the configured classification field case-insensitively;
3. loads the live coded domain/renderer;
4. performs a point query;
5. handles zero or multiple intersections;
6. preserves the raw code and complete attributes;
7. returns the unchanged official label;
8. attaches agency, service/layer, CRS, data/retrieval date, attribution, and
   cache state; and
9. blocks model use for an absent field/code/domain or changed reviewed domain.

Flood uses `fscode`; liquefaction uses `lccode`. Ground shaking has no URL,
field, domain, or mapping and returns `unavailable`.

The provider-level gate is ready only when flood, liquefaction, and ground
shaking all have status `available`. Otherwise it returns an incomplete state,
null score/category, and an explicit missing-input list. Applying the fuzzy
transformation occurs after this source gate.

## 9. Map geometry and pagination

The client supports:

- attribute queries;
- point-in-polygon queries;
- WGS 84 bounding-box queries;
- ArcGIS JSON, pretty JSON, and GeoJSON responses;
- `resultOffset` / `resultRecordCount`; and
- bounded pagination, default page size 2,000 and maximum 100 pages.

Pagination ends on an empty/short page or an explicit false
`exceededTransferLimit`. Exceeding the configured maximum is an invalid
response, not a silently truncated layer.

Map routes should query only Basey or the current viewport and respect each
live layer's maximum record count. The browser must not download national
datasets.

The implemented application routes are:

```text
GET /api/v1/ulap/status?refresh=true|false
GET /api/v1/ulap/services
GET /api/v1/ulap/services/{key}/metadata
GET /api/v1/boundary
GET /api/v1/boundary/basey
GET /api/v1/barangays
GET /api/v1/location/identify
GET /api/v1/hazards/flood
GET /api/v1/hazards/liquefaction
GET /api/v1/hazards/ground-shaking
GET /api/v1/hazards/at-location
GET /api/v1/hazard-layers/{key}/features
```

Existing assessment, explanation, source, and report routes consume the same
live facade in normal server mode. Repository demonstration records are not a
runtime fallback.

## 10. Caching, retries, and security

Metadata defaults to a 24-hour TTL and query results to one hour. Cache objects
retain source, retrieval, expiry, cache-hit, stale, and metadata-version
fields. Expiry triggers live retrieval.

The client makes one initial attempt plus the configured retry count. It
retries bounded network failures, timeouts, rate limiting, and selected 5xx
responses with exponential backoff. ArcGIS error objects are parsed even when
HTTP status is 200. Details are in
[ulap-error-handling.md](ulap-error-handling.md).

Outbound redirects are revalidated against the same host allowlist. URLs with
embedded credentials, fragments, non-HTTPS schemes, unapproved ports, or
look-alike hostnames are rejected.

## 11. Verification commands

Install the project dependency and optional audit tools as appropriate:

```powershell
python -m pip install -e .
python -m pip install -e ".[gis]"
```

Run offline unit/contract tests:

```powershell
python -m unittest discover -s tests -v
```

Run the deliberate live metadata smoke check:

```powershell
python scripts/verify_ulap_services.py `
  --boundary-file "C:\Users\Austin Jeru\Downloads\basey-barangay-boundary-final.json"
```

Machine-readable output:

```powershell
python scripts/verify_ulap_services.py `
  --boundary-file "C:\Users\Austin Jeru\Downloads\basey-barangay-boundary-final.json" `
  --json
```

The script requests both service and layer metadata, validates configured
fields/domains, checks the supplied file checksum/structure, never prints the
token, and exits:

- `0` only when every required registered source is fully verified;
- `1` when configuration/startup fails; or
- `2` when any required source is not fully verified.

Exit 2 is currently expected because ground shaking is required but
unconfigured. It does not erase separately successful flood, liquefaction, or
boundary checks; inspect the per-service table.

Enable the dedicated live integration tests explicitly with:

```powershell
$env:LIVE_ULAP_TESTS = "true"
python -m unittest discover -s tests -v
```

The ordinary suite must remain deterministic and offline, using sanitized
recorded fixtures only. Fixtures are never runtime hazard data.

Verification on 2026-07-23:

- `python -m unittest discover -s tests -v`: 78 tests ran, with 73 passing
  and five opt-in live tests skipped as designed;
- `LIVE_ULAP_TESTS=true python -m unittest tests.test_ulap_live -v`: all five
  live tests passed; and
- the smoke script verified flood, liquefaction, municipal boundary, and
  barangay boundary, while correctly reporting ground shaking unavailable and
  the supplied JSON pending verification.

## 12. Operational checklist

Before claiming live integration is available:

1. verify the registry checksum/reviewed version;
2. run the smoke script from the deployment network;
3. record date, endpoint, layer ID, live fields/domains, and differences;
4. test a known Basey point and a zero-feature point;
5. verify source/quality/cache status in interface and report;
6. confirm that missing ground shaking blocks the score;
7. confirm that no token appears in browser traffic or logs; and
8. rerun after any endpoint, field, domain, or model change.

Successful checks on 2026-07-23 are historical evidence, not a substitute for
runtime validation.
