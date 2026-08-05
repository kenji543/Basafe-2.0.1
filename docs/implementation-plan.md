# GeoSafe-FIS Implementation Plan and Status

## 1. Delivery objective

GeoSafe-FIS is one unified, unauthenticated Web-GIS prototype. A user selects
a point in Basey, Samar; reviews live available flood, liquefaction, and
ground-shaking evidence plus authorized historical-incident and CLUP context;
receives an explainable fuzzy screening result only when every required hazard
value is available; and previews or downloads a PDF assessment report.

The strict scope gate remains:

> A feature is included only when it directly supports data integration, location selection, barangay identification, hazard visualization, fuzzy assessment, explainability, historical incident context, CLUP context, data-quality communication, planning-oriented recommendations, or report generation.

User types, accounts, roles, permissions, approval workflows, administrative/staff dashboards, activity monitoring, audit-log management, browser data publication, and a fuzzy-model editor remain excluded.

## 2. Implemented baseline

The implemented package version is `0.5.0`; its bundled model is `0.5.1-demo`.

### 2.1 Runtime

- Python standard-library threaded HTTP server and JSON dispatcher.
- Backend-only ArcGIS REST integration with Pydantic v2 source contracts.
- SQLite schema initialized from `db/schema.sql` with foreign keys enabled.
- Static HTML/CSS/JavaScript and Leaflet frontend.
- `config/fuzzy_model.json` as the runtime model source of truth.
- Dependency-free PDF generation from a saved assessment snapshot.
- No authentication or account subsystem.

Supported runtime configuration:

| Setting | Command/environment |
| --- | --- |
| Host | `--host` / `GEOSAFE_HOST` |
| Port | `--port` / `GEOSAFE_PORT` |
| Database | `--database` / `GEOSAFE_DB_PATH` |
| Static web root | `--web-root` / `GEOSAFE_WEB_ROOT` |
| Model file | `GEOSAFE_MODEL_PATH` |
| Schema file | `GEOSAFE_SCHEMA_PATH` |
| Technical log level | `GEOSAFE_LOG_LEVEL` |
| ULAP hazard service base | `ULAP_HAZARDS_BASE_URL` |
| ULAP boundary service base | `ULAP_NGA_BASE_URL` |
| Optional ArcGIS credential | `ULAP_TOKEN` |
| ULAP timeout/retries | `ULAP_REQUEST_TIMEOUT_SECONDS` / `ULAP_MAX_RETRIES` |
| ULAP metadata/query cache TTL | `ULAP_METADATA_CACHE_SECONDS` / `ULAP_QUERY_CACHE_SECONDS` |
| Live metadata validation | `ULAP_LIVE_VALIDATION` |
| ULAP registry | `ULAP_SERVICES_CONFIG` |

There is no implemented shared password. Any future perimeter password requires a separate scope decision and must not create accounts or roles.

### 2.2 Data schema

The implemented application tables are:

- `municipal_boundary`;
- `barangays`;
- `hazard_datasets`;
- `hazard_features`;
- `historical_incidents`;
- `clup_references`;
- `fuzzy_models`;
- `fuzzy_variables`;
- `membership_functions`;
- `fuzzy_rules`;
- `assessments`;
- `assessment_inputs`;
- `assessment_memberships`;
- `assessment_rule_activations`;
- `assessment_results`; and
- `generated_reports`.

Geometry is stored as WGS 84 GeoJSON text. The current schema does not contain spatial-extension, bounding-box, user, role, permission, session, approval, or audit-log tables.

Authorized imported hazard features store a normalized fraction from `0` through `1`; that compatibility path multiplies the fraction by 100 before fuzzy evaluation. Live ULAP results instead preserve the exact source code/official label and use the separately configured exact-code transformation for model `0.5.1-demo`.

### 2.3 Data preparation

Implemented tools:

- only `scripts/import_dataset.py` remains as a data-loading CLI, and
  `config/data_sources.json` configures no static datasets;
- `scripts/import_dataset.py` imports municipal boundaries, barangays, hazards, incidents, and CLUP references;
- GeoJSON and coordinate CSV work with the standard library;
- EPSG:4326 and EPSG:3857 transforms are built in;
- optional PyProj handles other CRS transformations;
- optional Fiona/GDAL reads Shapefile and GeoPackage; and
- optional Shapely performs topology validation/safe repair.

GeoTIFF is not loaded directly. Operators inspect and vectorize classified raster cells with Rasterio or a GIS tool, preserve their metadata, and import the resulting classification polygons.

The importer requires `official` or `demonstration` classification, accepts source and quality metadata, safely closes/deduplicates rings, logs rejected features to JSON Lines, and supports strict all-or-nothing or explicitly signalled partial import. See [data-import.md](data-import.md).

The supplied 58-feature barangay JSON is audited but not operationally loaded.
Its likely EPSG:3125 CRS, issuer, authority, six unnamed polygons, identifiers,
and differences from the live 51-feature PSA response require confirmation.
See [ulap-json-audit.md](ulap-json-audit.md).

### 2.4 Live ULAP integration

Implemented integration components include:

- a version-controlled service registry for flood, liquefaction, ground
  shaking, municipal boundary, and barangay boundary sources;
- an HTTPS/two-host-allowlisted ArcGIS client with encoded parameter
  dictionaries, redirect validation, bounded retries, timeouts, TTL caching,
  point/envelope queries, GeoJSON support, and pagination;
- service/layer metadata validation for layer identity, feature type,
  geometry, CRS, `Query` capability, classification field, domain, record
  limit, formats, version, and attribution;
- Basey municipal and barangay point identification through the PSA layers;
- flood `fscode` and liquefaction `lccode` retrieval with raw attributes and
  live domain decoding;
- explicit zero-feature, overlap, unknown-code, schema-change,
  authentication, timeout, and service-error states;
- a hard incomplete gate when any of the three required hazards is not
  `available`; and
- `scripts/verify_ulap_services.py` for deliberate live service/layer checks.

Independent requests on 2026-07-23 verified the configured service roots and
layer 0 metadata for MGB flood, PHIVOLCS liquefaction, PSA municipal, and PSA
barangay sources. No verified ground-shaking URL exists, so the smoke script
correctly exits non-zero for the complete required-source gate.

Detailed behavior is in [ulap-integration.md](ulap-integration.md) and
[ulap-error-handling.md](ulap-error-handling.md).

### 2.5 Spatial and supporting APIs

Implemented endpoint families:

- boundary and barangay GeoJSON;
- hazard layer catalogue and features;
- local barangay/coordinate search;
- Basey and barangay identification;
- complete/incomplete assessment creation and unified history;
- saved assessment explanation and PDF;
- incident and nearby-incident context;
- CLUP and location-matched CLUP context;
- methodology; and
- flattened plus structured data-source information.

Query coordinate aliases, request shapes, limits, and exact response conventions are documented in [api.md](api.md).

### 2.6 Fuzzy model

`config/fuzzy_model.json` version `0.5.1-demo` implements:

- three required 0â€“100 inputs;
- low/moderate/high triangular or trapezoidal memberships;
- a systematically generated, complete 27-rule monotonic Mamdani grid;
- minimum for `AND`, maximum for `OR`;
- weighted rule activation;
- minimum implication and maximum aggregation;
- centroid sampling at each integer from 0 through 100;
- Very Low, Low, Moderate, High, and Very High score categories; and
- controlled recommendation templates and disclaimer.

It also defines transparent demonstration lookups from live flood `fscode`
and liquefaction `lccode` values into the model input scale. Official codes and
labels remain separate. The ground-shaking source and mapping are intentionally
empty until an authorized layer and expert-approved transformation exist.

If any required hazard is missing, evaluation returns `incomplete`, a null score, an `"Incomplete"` status label instead of a vulnerability category, a missing-input list, and no activated rules. Historical incidents and CLUP references remain contextual, not numerical inputs.

The software model is implemented; the hazard mappings, membership breakpoints, rules, weights, categories, and recommendations remain demonstration assumptions pending qualified domain-expert validation.

### 2.7 Unified frontend

The public frontend uses four HTML entry documents with clean route aliases:

1. `/` (`web/index.html`) is the public education and trust landing page.
2. `/map` (`web/map.html`) contains location selection, map controls, results, report preview/download, and unified history.
3. `/methodology` (`web/methodology.html`) explains model definitions and limitations.
4. `/data-sources`, `/limitations`, `/about`, `/privacy`, and `/offline` use the shared `web/info.html` shell with route-specific content.

The history panel combines server history with a small browser-local recent-assessment cache. It has no user ownership or role filtering.

### 2.8 Reports

The report endpoint:

1. reads the immutable saved assessment snapshot;
2. regenerates the PDF without rerunning spatial lookup or fuzzy inference;
3. calculates a SHA-256 digest;
4. stores a `generated_reports` metadata/content-snapshot record; and
5. returns a controlled attachment filename and `X-Report-SHA256` header.

Repeated downloads create new generation records; the implementation does not claim one idempotent report row.

## 3. Remaining deployment work

The application implementation is a prototype. Deployment for real planning evaluation still requires:

1. Confirming the selected boundary authority and use terms; the live PSA
   service is reachable, while the supplied local file still needs issuer/CRS/
   identifier/version reconciliation.
2. Obtaining an authorized, verified ground-shaking layer and documenting its
   unit/domain, coverage, date, attribution, and source-to-model mapping.
3. Evaluating currentness, coverage, scale, and permitted caching/report use
   for the July 2018-attributed flood and liquefaction sources.
4. Importing available authorized historical incidents and adopted CLUP
   references with honest spatial/date precision.
5. Reviewing coordinate control points, boundary overlaps/gaps, zero-feature
   hazard areas, and multiple-intersection behavior.
6. Validating the fuzzy mappings, functions, rules, weights, output thresholds,
   and recommendation text with qualified experts.
7. Performing manual supported-browser, responsive-layout, keyboard,
   map-tile/network-failure, live-service-failure, and PDF visual checks.
8. Placing the service behind HTTPS/reverse-proxy controls when exposed outside
   a trusted prototype environment.
9. Defining cache, assessment/report retention, data-use, and backup practices
   appropriate to the deployment.

None of these tasks requires a browser administration portal.

## 4. Verification strategy

Run the current suite from the project root:

```text
python -m unittest discover -s tests -v
```

The suite uses Python `unittest`; it does not depend on a browser-testing framework. Its current coverage is:

| Test module | Implemented evidence |
| --- | --- |
| `tests/test_frontend_contract.py` | Only approved HTML pages, required workflow control IDs, approved API references, visible disclaimer/demo/missing-data language, and JavaScript syntax when Node is available |
| `tests/test_fuzzy.py` | Membership boundaries, bounded/explainable complete result, missing-input behavior, 27 generated rules, monotonicity, category span, and rejection of threshold gaps |
| `tests/test_geometry.py` | Polygon/hole/edge behavior, line/geometry-collection context, in-memory bounding box/distance helper, and invalid coordinate rejection |
| `tests/test_http_server.py` | Unified page over HTTP, assessment-to-PDF workflow, response security headers, and missing admin endpoint |
| `tests/test_importer.py` | Fraction/provenance storage, out-of-range rejection/error record, EPSG:3857 and explicit projected-CRS behavior, and fixture isolation |
| `tests/test_scope.py` | Exact approved table allowlist, forbidden-table absence, and missing user/role/admin APIs |
| `tests/test_ulap_registry.py` | Registry parsing, exact service/layer resolution, safe overrides, and URL allowlist rejection |
| `tests/test_ulap_response_parser.py` | ArcGIS 498/499 parsing, domain decoding, unknown codes, and malformed feature payloads |
| `tests/test_ulap_client.py` | Metadata TTL cache, retry/timeout behavior, ArcGIS errors, token-safe structured request logging, and coordinate validation |
| `tests/test_ulap_metadata.py` | Metadata identity/schema/domain comparison and supplied-boundary pending-verification behavior |
| `tests/test_ulap_providers.py` | Flood/liquefaction extraction, zero/conflicting features, missing ground shaking, Basey/barangay identification, and assessment gate |
| `tests/test_ulap_application.py` | Normalized source response, granular/coarse missing-state persistence, provenance, and report content |
| `tests/test_ulap_live.py` | Opt-in service metadata, Basey boundary/identification, point-query, and no-substitution checks |
| `tests/test_workflow.py` | Spatial identification, official-boundary preference, complete/incomplete assessment persistence, outside rejection, explanation, complete/incomplete PDFs, private-token access, report records, and disabled shared history |

These tests establish core calculation, persistence, HTTP, import, static frontend-contract, and strict-scope behavior. They do not simulate a full browser. The following remain manual acceptance checks:

- Leaflet and map tiles render in a supported browser;
- search, coordinate submit, and map-click visibly select the expected point;
- hazard toggles and legend update correctly;
- result, preview, history, and methodology presentation remain usable at supported viewport sizes;
- keyboard/focus behavior and non-color meaning are acceptable; and
- generated complete and incomplete PDFs are visually reviewed.

Live checks are deliberately separate from the default deterministic suite:

```text
python scripts/verify_ulap_services.py --boundary-file <path>
```

The command currently exits 2 because required ground shaking is unavailable;
its per-source output must still show the separately verified services. Future
network integration tests must be opt-in with `LIVE_ULAP_TESTS=true`.

## 5. Phase-by-phase implementation record

### Phase 1 â€” Source audit and versioned configuration

Files:

- `config/ulap-services.generated.json`;
- `config/data_sources.json`;
- `config/fuzzy_model.json`;
- `.env.example`; and
- `docs/ulap-json-audit.md`.

Commands/evidence:

```powershell
Get-FileHash `
  "C:\Users\Austin Jeru\Downloads\basey-barangay-boundary-final.json" `
  -Algorithm SHA256

python scripts/verify_ulap_services.py `
  --boundary-file "C:\Users\Austin Jeru\Downloads\basey-barangay-boundary-final.json"
```

Result on 2026-07-23: the supplied checksum matched; the four configured
service/layer pairs returned verified metadata; ground shaking returned
`unavailable`; and the supplied boundary remained `pending_verification`.
The smoke script therefore reached its intentional required-source failure
exit (`2` in the script contract).

### Phase 2 â€” ArcGIS client, validation, and providers

Files:

- `geosafe/ulap/arcgis_client.py`;
- `geosafe/ulap/service_registry.py`;
- `geosafe/ulap/metadata_validator.py`;
- `geosafe/ulap/hazard_provider.py`;
- `geosafe/ulap/boundary_provider.py`;
- `geosafe/ulap/response_parser.py`;
- `geosafe/ulap/errors.py`;
- `geosafe/ulap/models.py`;
- `geosafe/ulap/integration.py`; and
- `tests/fixtures/ulap/*`, `tests/test_ulap_*.py`.

Commands:

```powershell
python -m unittest `
  tests.test_ulap_registry `
  tests.test_ulap_response_parser `
  tests.test_ulap_client `
  tests.test_ulap_metadata `
  tests.test_ulap_providers -v

$env:LIVE_ULAP_TESTS = "true"
python -m unittest tests.test_ulap_live -v
```

Result: offline contracts cover allowlisting, typed registry/schema, errors,
domains, cache/retries, pagination, point and extent queries, overlap/gap
behavior, source preservation, and score blocking. All five opt-in live tests
passed on 2026-07-23.

### Phase 3 â€” Runtime API and unified Web-GIS integration

Files:

- `geosafe/api.py`;
- `geosafe/service.py`;
- `geosafe/server.py`;
- `geosafe/repository.py`;
- `geosafe/pdf.py`;
- `web/index.html`;
- `web/app.js`;
- `web/methodology.html`;
- `web/methodology.js`;
- `web/styles.css`;
- `tests/test_frontend_contract.py`;
- `tests/test_http_server.py`;
- `tests/test_ulap_application.py`; and
- `tests/test_workflow.py`.

Implemented routes include ULAP status/services/metadata, live Basey and
barangay geometry, individual/all point hazards, Basey-bounded hazard map
geometry, live-source assessment creation, explanations, and reports. Normal
server mode rejects demonstration repository hazards; tests must explicitly
opt into fixtures.

Command:

```powershell
python -m unittest discover -s tests -v
```

Result on 2026-07-23: 78 tests ran; 73 passed and five network tests were
skipped by default as designed. The separate opt-in run passed all five live
tests.

### Phase 4 â€” Import boundary and fixture isolation

Files:

- `scripts/import_dataset.py`;
- `scripts/README.md`;
- `tests/test_importer.py`; and
- `docs/data-import.md`.

The runtime fixture-loading path and synthetic runtime datasets were removed.
The importer supports explicit EPSG:3125 reprojection
when confirmed by the operator, but the supplied file remains blocked from
operational use until its issuer/CRS/identifier differences are resolved.
Importer tests are part of the 78-test default run.

### Phase 5 â€” Method, sources, limits, and handoff documentation

Files:

- `docs/ulap-integration.md`;
- `docs/ulap-field-mappings.md`;
- `docs/ulap-error-handling.md`;
- `docs/data-sources.md`;
- `docs/fuzzy-data-transformations.md`;
- `docs/known-data-gaps.md`;
- `docs/architecture.md`;
- `docs/api.md`;
- `docs/fuzzy-methodology.md`;
- `docs/acceptance-criteria.md`;
- `docs/implementation-plan.md`; and
- `README.md`.

Documentation records exact URLs/layers/fields/domains, independent
verification date, source/model separation, cache/error behavior, the
unconfirmed EPSG:3125 inference, all missing-data gates, strict scope, commands,
and test outcomes. It does not call the supplied boundary official or claim a
complete live score.

## 6. Objective traceability

| Approved function | Implemented component | Current verification |
| --- | --- | --- |
| Data integration | ULAP registry/client/providers, CLI importer, SQLite source snapshots | ULAP offline tests plus live smoke script; ground shaking/incidents/CLUP still required |
| Location selection | Search/coordinate/map-click controls, identify API | Static control/API contract tests; manual browser interaction |
| Barangay identification | Live PSA municipal/barangay point queries plus local authorized-data fallback | Provider/geometry/workflow tests; live smoke evidence |
| Hazard visualization | Backend-limited ULAP geometry requests, Leaflet layers, controls, legends | Static/frontend/provider contract; manual live rendering |
| Fuzzy assessment | Versioned `FuzzyModel` and exact live-code transformation configuration | Membership/model/provider-gate tests; expert validation pending |
| Explainability | Saved memberships and all rule activations | Fuzzy/workflow/explanation tests |
| Incident context | Nearby/same-barangay/covering matching | Complete workflow fixture |
| CLUP context | Same-barangay/covering/municipal matching | Complete workflow fixture |
| Data quality | Source flags, quality status/notices, missing gate | Importer, workflow, and frontend-contract tests |
| Recommendations | Model-versioned templates | Complete/incomplete workflow output; expert review pending |
| PDF report | Snapshot renderer and report endpoint | Workflow and real HTTP PDF tests; manual visual check |
| Strict scope | Endpoint/table/page allowlists | Scope, frontend-contract, and HTTP tests |

## 7. Release gates

A prototype release is rejected if:

- missing required data can produce a numeric score;
- missing is presented as low vulnerability;
- a zero-feature ArcGIS response, unknown code, or changed domain is converted
  to a vulnerability value;
- a non-ground-shaking source is substituted for ground shaking;
- official source codes/labels are overwritten by model-generated values;
- the browser calls ULAP directly or exposes an ArcGIS token;
- a demonstration source/model is not visibly identified;
- normalized values, memberships, rules, weights, and activations cannot explain a result;
- source/quality notices or the disclaimer disappear from the assessment/report;
- a PDF is recalculated from current spatial/model data rather than the saved snapshot;
- a user, role, permission, staff, approval, audit-management, browser-upload, CMS, or model-editor feature appears; or
- documentation describes demonstration parameters as domain validated.

## 8. Deferred and out-of-scope ideas

The following are not active backlog items:

- shared deployment password;
- accounts or personal workspaces;
- office-specific interfaces;
- role-based access;
- browser data upload/publication;
- interactive fuzzy-model editing; and
- approval or audit-management workflows.

They must not leave placeholder pages, routes, tables, or dependencies in the prototype.
