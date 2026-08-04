# GeoSafe-FIS Acceptance Criteria

## 1. Acceptance policy

GeoSafe-FIS is acceptable when the implemented prototype satisfies the approved assessment workflow and contains none of the excluded identity or administrative scope.

Automated evidence comes from the current Python standard-library suite:

```text
python -m unittest discover -s tests -v
```

The suite covers static frontend contracts, fuzzy calculations, geometry, real HTTP behavior, importing, strict scope, ULAP registry/client/provider behavior with sanitized fixtures, and the integrated assessment workflow. It is not a browser-automation framework. Criteria involving live-service reachability, visual map rendering, actual mouse/keyboard interaction, responsive layout, and PDF appearance require deliberate live/manual checks in addition to the automated contracts.

Automated-test fixtures are explicitly isolated and synthetic/sanitized.
The repository has no operational demonstration-data seed. Passing the suite
validates application behavior, not the authority of a Basey dataset or the
scientific validity of model parameters.

## 2. Current automated evidence

| Module | Evidence provided |
| --- | --- |
| `tests/test_frontend_contract.py` | Only `index.html` and `methodology.html`; required unified workflow controls; no password input; approved API references; visible disclaimer, demonstration, and missing-is-not-low language; JavaScript syntax when Node is available |
| `tests/test_fuzzy.py` | Triangular/trapezoidal memberships, complete bounded result, 12 evaluated rules, activated rules, missing-input incomplete behavior, low/very-high model span, and rejection of threshold gaps |
| `tests/test_geometry.py` | Polygon/hole checks, boundary-as-inside behavior, line/geometry-collection context, coordinate rejection, distance, and in-memory bounding-box helper |
| `tests/test_http_server.py` | Unified page over real HTTP, security headers, assessment-to-PDF path, and 404 for an admin route |
| `tests/test_importer.py` | Stored `0–1` fraction/provenance, invalid fraction rejection/error file, EPSG:3857 reprojection, demonstration-only seed labels, and prevention of a demo layer replacing an official hazard slug |
| `tests/test_scope.py` | Exact table allowlist, forbidden-table absence, and 404 responses for user/role/permission/admin/audit/registration routes |
| `tests/test_ulap_registry.py` | Service/layer resolution, environment overrides, and approved-host URL controls |
| `tests/test_ulap_response_parser.py` | ArcGIS errors, coded domains, unknown codes, and malformed responses |
| `tests/test_ulap_client.py` | TTL cache, bounded retries/timeouts, token-safe structured request logging, point queries, and coordinate validation |
| `tests/test_ulap_metadata.py` | Live-schema comparison, missing fields, changed domains, unconfigured ground shaking, and supplied-boundary pending status |
| `tests/test_ulap_providers.py` | Official flood/liquefaction extraction, zero/conflicting intersections, unavailable ground shaking, Basey/barangay identification, and completeness gate |
| `tests/test_ulap_application.py` | Backend normalized sources, incomplete live-contract persistence, provenance, and PDF disclaimer/source content |
| `tests/test_ulap_live.py` | Opt-in metadata, Basey boundary/identification, flood/liquefaction point behavior, and no ground-shaking substitution |
| `tests/test_workflow.py` | Boundary/barangay identification, official-boundary preference, complete and incomplete assessments, explanation persistence, outside rejection, pagination validation, complete/incomplete PDF behavior, report records, and non-user-scoped history |

Recorded on 2026-07-23: the default suite ran 78 tests: 73 passed and the five
network tests were skipped as designed; the separate opt-in live run passed
all five live tests.

## 3. Unified interface and location selection

### AC-UI-001 — Unified unauthenticated interface

Opening `/` must return the one Web-GIS interface without registration, login, account, role, or office selection. Only the assessment interface and `/methodology` HTML page exist.

- Automated: frontend page/password contract and real HTTP page test.
- Manual: confirm navigation and all panels render in a supported browser.

### AC-UI-002 — Map and boundaries

The Leaflet map must load and display the verified Basey municipal and barangay geometry available through the backend. Layer status and source notices must distinguish live verified metadata, unverified supplied references, demonstration fixtures, and point-level unavailability.

The live PSA source may support boundary display/identification with attribution.
The supplied 58-feature JSON remains unverified until its issuer, EPSG:3125
inference, version, identifiers, and geometry differences are resolved.

- Automated: boundary FeatureCollection, demonstration label, and official-boundary-preference workflow tests.
- Manual: confirm map/tile rendering, boundary styling, labels, and source/quality access.

### AC-UI-003 — Location search

Search must accept at least two characters and return matching loaded barangay names/PSGC codes. It also accepts a WGS 84 pair written as `latitude, longitude`. The prototype must disclose that it does not use a third-party geocoder.

- Automated: required search form and `/location/search` frontend reference.
- Manual: select a barangay and coordinate-pair result and confirm the map pin/fields update.

### AC-UI-004 — Coordinate input

The coordinate form must accept valid latitude/longitude and visibly reject nonnumeric or out-of-range coordinates. API callers may use `latitude`/`longitude` or `lat`/`lon`.

- Automated: coordinate form contract, geometry range rejection, and API assessment/identify workflows.
- Manual: submit valid and invalid values and confirm clear field/status feedback.

### AC-UI-005 — Map-click selection

Clicking the map must set the selected marker and coordinates and use the same identification/assessment service as search and coordinate input.

Assessment creation must preserve one of `search`, `coordinates`, or `map_click` as `location.selection_method`; invalid values are rejected.

- Automated: presence of the map and run-assessment controls plus JavaScript syntax/API-reference contract.
- Manual: click inside and outside the loaded municipal boundary and inspect marker/coordinate synchronization.

### AC-UI-006 — Basey containment and barangay

An inside point must report `inside_basey: true` from the verified PSA municipal query and identify the live containing barangay/codes when available. Multiple or absent containing polygons must produce a topology/missing-information notice rather than false certainty. The authorized static-data fallback retains deterministic edge behavior.

An outside assessment request must return `422 outside_basey`.

- Automated: geometry edge/hole tests, spatial identification, official-boundary preference, and outside-rejection workflow tests.
- Live/manual: verify known inside, edge, and outside Basey control points and
  record the endpoint/retrieval date.

## 4. Hazards, incidents, and CLUP

### AC-DATA-001 — Three required hazards

A covered complete assessment must return exactly the required flood, liquefaction, and ground-shaking inputs. Each includes:

- raw source code and unchanged official classification label;
- explicit source status, such as `available`, `no_intersection`, or
  `changed_schema`;
- complete raw source attributes, layer/field, agency, URL, retrieval/cache
  time, attribution, and warnings;
- separate GeoSafe-FIS `normalized_value` from 0–100 when an exact,
  model-reviewed transformation exists;
- normalization explanation/model version;
- quality status and notice; and
- source-authority/demonstration flags.

- Automated: complete workflow and fuzzy tests.
- Manual: confirm all three cards/layers/legends are readable and match the API.

### AC-DATA-002 — Normalization semantics

For verified live sources, model `0.4.0-demo` must perform the exact
version-controlled code lookup while retaining the official value. It must not
infer order from the source code. For an authorized imported dataset, the
separate compatibility path may calculate:

```text
model input = stored normalized fraction × 100
```

It must never infer a fraction/value from an unknown label, changed domain,
empty feature response, or substitute hazard. Every transformation requires a
documented model version and domain-expert validation.

- Automated: importer fraction storage/range tests and complete workflow values.
- Inspection: `config/fuzzy_model.json` version `0.4.0-demo`,
  [fuzzy-data-transformations.md](fuzzy-data-transformations.md), and import
  documentation.

### AC-DATA-003 — Hazard visualization

The map must provide separate controls and a legend for available live flood,
liquefaction, and verified ground-shaking features. Unavailable sources and
all quality/status notices remain visible. Meaning must not rely on color
alone.

- Automated: control/legend IDs, approved hazard API reference, and JavaScript syntax.
- Manual: toggle every layer and compare features, legend, and notices.

### AC-DATA-004 — Historical incidents

The assessment must show matching incident context and its `match_reason`: within radius, covering geometry, or same barangay. If no record matches, it must say only that no matching record exists in the loaded data, not that no incident occurred.

- Automated: complete workflow fixture confirms incident context.
- Manual/data review: verify source/date/spatial precision wording against deployed records.

### AC-DATA-005 — CLUP references

The assessment must show matching CLUP context and whether it covers the point, matches the barangay, or is municipality-wide. The interface/report must not portray it as a legal zoning or permitting determination.

- Automated: complete workflow fixture confirms CLUP context and visible disclaimer contract.
- Manual/data review: verify adopted document edition, section, and spatial relationship after official import.

### AC-DATA-006 — Official versus demonstration

Every dataset must be imported as either `official` or `demonstration`; missing classification cannot default to official. Demonstration data/model status must remain visible in layers, results, methodology/source presentation, preview, and report.

- Automated: importer fixture-isolation, boundary/source workflow, frontend
  language, and PDF-generation workflow tests.
- Manual: confirm that test fixtures cannot appear in normal server results or
  reports and cross-check all source-status labels.

### AC-DATA-007 — Live ULAP integrity

The backend, not the browser, must call only the allowlisted GeoRisk HTTPS
hosts. Runtime metadata must validate the exact service/layer ID, Feature Layer
type, geometry, CRS, Query capability, classification field, and coded domain.
The browser, cache key, log, response, and report must never expose
`ULAP_TOKEN`.

Flood must use verified layer 0 and `fscode`; liquefaction must use verified
layer 0 and `lccode`. Zero features are not Low. Unknown codes, changed
domains, conflicting intersections, timeouts, authentication errors, and
invalid responses remain explicit unavailable states.

Ground shaking may be used only after a true ground-shaking endpoint and field
are verified. Until then it is `unavailable` and the assessment is
`incomplete`; Active Fault and other seismic proxies are prohibited.

- Automated: ULAP registry/client/parser/provider tests.
- Live: `scripts/verify_ulap_services.py`; record endpoint, date, layer, fields,
  domains, differences, and expected non-zero exit while ground shaking is
  unavailable.

## 5. Fuzzy assessment and explainability

### AC-FIS-001 — Model configuration

`config/fuzzy_model.json` must identify `0.4.0-demo` and define:

- exact live-code/model `0–100` transformations, imported `0–1`
  compatibility semantics, and missing-value policy;
- three required hazard variables;
- low/moderate/high input membership functions;
- 12 rule statements, conditions, consequents, rationales, and weights;
- output memberships;
- Low 1–25, Moderate 26–50, High 51–75, and Very High 76–100 thresholds;
- Mamdani operators and centroid sampling interval 1; and
- validation notes, recommendations, and disclaimer.

- Automated: model load/evaluation tests and methodology frontend/API references.
- Inspection: methodology page renders the active API model/checksum/status.

### AC-FIS-002 — Complete result

When all required values are available, the result must contain:

- normalized inputs;
- every low/moderate/high membership degree;
- all 12 evaluated rules;
- only positive weighted rules in `activated_rules`;
- raw activation, weight, weighted activation, conditions/memberships, consequent, and rationale;
- unrounded centroid;
- integer score from 1 through 100; and
- exactly one configured vulnerability category.

- Automated: fuzzy and complete workflow/explanation tests.
- Manual: compare the result and rule explanation presentation to the API.

### AC-FIS-003 — Missing required data

If any required hazard has no verified dataset, no covering feature, no
recognized code/transformation, or no authorized imported normalized fraction:

- its runtime `availability_status` is `missing`;
- its normalized values are null;
- top-level and result status are `incomplete`;
- score is null;
- no vulnerability category is assigned (`"Incomplete"` is only a status label);
- `missing_inputs` identifies the variable;
- no rule is activated; and
- the interface/report states that missing is not low vulnerability.

- Automated: fuzzy missing-input, integrated incomplete-workflow, and frontend-language contracts.
- Manual: inspect an incomplete result, preview, and downloaded PDF.

### AC-FIS-004 — Demonstration validation status

Model functions, rules, weights, thresholds, live-code/imported-fraction
mappings, and recommendations must remain marked as demonstration assumptions
until qualified specialists validate them.

- Automated: model/front-end demonstration status contracts.
- Required project review: retain signed/versioned expert validation notes before any operational claim.

## 6. Results, history, and reports

### AC-OUT-001 — Results and recommendations

The result panel must show location, coordinates, barangay, hazards, normalized values, memberships, activated rules, score/category or incomplete state, incidents, CLUP, quality/missing notices, recommendations, and disclaimer.

Recommendations must remain planning-oriented and encourage authoritative data, site-specific review, and qualified advice. They must not claim engineering, evacuation, legal, permitting, or investment authority.

- Automated: complete/incomplete snapshot fields and required frontend controls/language.
- Manual: content and layout review for complete and incomplete cases.

### AC-OUT-002 — Unified history

Saved history must use `limit`/`offset`, return a total `count`, and have no user ownership or role scope. The frontend may combine server history with browser-local recent IDs.

- Automated: unified-history workflow test.
- Manual: create, reopen, and redownload multiple assessments.

### AC-OUT-003 — Report preview

The preview dialog must use the selected saved assessment and include the substantive result, context, sources/quality, recommendations, missing-data state, model version, and disclaimer intended for download.

- Automated: required preview/download controls, frontend syntax, and saved report-preview metadata.
- Manual: compare preview with the visible result and downloaded PDF.

### AC-OUT-004 — PDF report

`GET /api/v1/assessments/{id}/report` must regenerate a valid PDF from the immutable saved assessment snapshot without rerunning hazard lookup or fuzzy inference. Each generation records its content snapshot and SHA-256 digest and returns `X-Report-SHA256`.

The PDF must include no score or vulnerability category for an incomplete assessment and must preserve the missing-is-not-low warning and disclaimer.

- Automated: PDF magic/content header, SHA header, generated-report record, and real HTTP workflow.
- Manual: visually inspect one complete and one incomplete PDF and compare material fields with the saved JSON.

### AC-OUT-005 — Methodology and sources

`/methodology`, `/api/v1/methodology`, and `/api/v1/data-sources` must expose the active model/version/checksum, normalization semantics, functions/rules/output thresholds, validation notes, limitations, and source status.

The data-source response must include both flattened `items` and structured boundary, barangay, hazard, incident, CLUP, and fuzzy-model groups.

- Automated: approved methodology/source frontend references and JavaScript syntax.
- Manual/API inspection: confirm the methodology and structured/flattened source responses render and long source/quality content remains usable.

### AC-OUT-006 — Disclaimer

The interface and report must display the configured disclaimer:

> GeoSafe-FIS is a planning-oriented screening prototype. It does not replace official hazard certifications, site-specific engineering or geotechnical studies, emergency instructions, or decisions by competent authorities. Demonstration data and an unvalidated fuzzy model must not be used as the sole basis for life-safety, permitting, zoning, investment, or development decisions.

- Automated: frontend text contract and assessment/report workflow.
- Manual: confirm visibility without requiring a tooltip or role-specific page.

## 7. Import and persistence

### AC-IMP-001 — Formats and CRS

The documented deployment process must support:

- GeoJSON and coordinate/GeoJSON-geometry CSV with the standard library;
- Shapefile and GeoPackage with optional Fiona/GDAL;
- built-in EPSG:4326/EPSG:3857 handling;
- other CRS through optional PyProj or prior reprojection; and
- externally inspected/vectorized GeoTIFF classifications imported as vector features.

Direct GeoTIFF storage/sampling is not claimed.

- Automated: GeoJSON import and EPSG:3857 conversion tests.
- Deployment verification: run representative format fixtures using the dependencies intended for that deployment.

### AC-IMP-002 — Validation, provenance, and errors

The importer must validate required fields, coordinates, geometry structure, and `0–1` hazard fractions; perform only documented safe repairs; preserve provenance/checksum/CRS/quality metadata; and write rejected feature records outside the application UI.

Strict mode must prevent insertion when any feature fails. Non-strict mode may commit valid rows but must log errors and exit with code 2.

- Automated: valid provenance, invalid fraction/strict rollback, reprojection, and seed tests.
- Manual/data review: cross-feature boundary topology, coverage, control points, and source authority.

### AC-DB-001 — Approved table allowlist

A fresh database may contain SQLite internals plus only:

```text
municipal_boundary
barangays
hazard_datasets
hazard_features
historical_incidents
clup_references
fuzzy_models
fuzzy_variables
membership_functions
fuzzy_rules
assessments
assessment_inputs
assessment_memberships
assessment_rule_activations
assessment_results
generated_reports
```

- Automated: exact schema allowlist and forbidden-table tests.

### AC-DB-002 — Immutable assessment snapshot

Reopening an assessment or regenerating its report must use the stored source/model/result snapshot. Later imports or model-file changes must not silently recalculate that saved result.

- Automated: assessment persistence, explanation, and report-from-snapshot workflow.
- Inspection: report generation reads the saved assessment before writing its generation record.

## 8. API and strict negative scope

### AC-API-001 — Approved API allowlist

Application endpoints are limited to:

```text
GET  /api/v1/ulap/status
GET  /api/v1/ulap/services
GET  /api/v1/ulap/services/{key}/metadata
GET  /api/v1/boundary
GET  /api/v1/boundary/basey
GET  /api/v1/barangays
GET  /api/v1/barangays/{id}
GET  /api/v1/hazard-layers
GET  /api/v1/hazard-layers/{id-or-slug}/features
GET  /api/v1/location/search
GET  /api/v1/location/identify
GET  /api/v1/hazards/flood
GET  /api/v1/hazards/liquefaction
GET  /api/v1/hazards/ground-shaking
GET  /api/v1/hazards/at-location
POST /api/v1/assessments
GET  /api/v1/assessments
GET  /api/v1/assessments/{id}
GET  /api/v1/assessments/{id}/explanation
GET  /api/v1/assessments/{id}/report
GET  /api/v1/incidents
GET  /api/v1/incidents/nearby
GET  /api/v1/clup-references
GET  /api/v1/clup-references/by-location
GET  /api/v1/methodology
GET  /api/v1/data-sources
```

Static assets, `/`, `/methodology`, `OPTIONS`, and standard method/error handling do not expand application scope.

### AC-SCOPE-001 — No identity or RBAC

There must be no registration, multiple accounts, users, roles, permissions, staff profiles, user sessions, account approval, or role-based access checks.

### AC-SCOPE-002 — No administrative subsystem

There must be no admin/staff dashboard, office-specific interface, permission matrix, dataset/model approval queue, browser upload/publication, content-management page, or fuzzy-model editor.

### AC-SCOPE-003 — No audit-management feature

There must be no user-activity monitor or audit-log page/API/table. Normal server logging and importer error JSON Lines are technical diagnostics, not application features.

Automated evidence for AC-API-001 and AC-SCOPE-001–003:

- exact table allowlist and forbidden-table checks;
- 404 checks for user, role, permission, admin, audit, and registration paths;
- static frontend approved-page/API-group checks;
- no password input; and
- real HTTP 404 for `/api/v1/admin`.

## 9. Final manual checklist

After the automated suite passes:

- [ ] Open `/` and `/methodology` in each supported browser.
- [ ] Confirm map tiles, municipal/barangay layers, hazard toggles, and legend.
- [ ] Select the same inside point by search, coordinates, and map click.
- [ ] Confirm an outside point is rejected.
- [ ] At the documented coverage point, confirm raw flood `03` and
  liquefaction `01` remain separate from model values.
- [ ] Confirm missing ground shaking produces an incomplete result and null
  score; do not require a live complete result until its verified dependency
  exists.
- [ ] Confirm no-intersection, unknown-code/schema, and service-failure
  messages are distinct and never shown as Low.
- [ ] Confirm current missing incident/CLUP notices; after authorized import,
  confirm match reasons and source metadata.
- [ ] Compare result, report preview, saved assessment JSON, and PDF.
- [ ] Confirm sanitized/synthetic test fixtures cannot appear in normal server
  results or reports.
- [ ] Review the demonstration-model label and exact disclaimer across all
  surfaces.
- [ ] Check keyboard focus, labels, non-color meaning, and responsive layouts.
- [ ] Confirm no login, user, role, admin, staff, approval, audit, upload, or model-editor surface exists.
