# Basafe Mandatory Post-Generation Evaluation

Evaluation date: 2026-08-05  
Canonical specification: the original full Basafe build prompt supplied by the user
Evaluated build: application package `0.5.0`, fuzzy model `0.5.1-demo`, frontend assets `0.5.5`

## Overall objective status

**NOT MET**

## Executive summary

Basafe is a coherent, functioning, safety-conscious research prototype. Its public landing page, Basey map, verified municipal/barangay boundaries, location selection, incomplete-assessment workflow, explainability surfaces, saved snapshots, PDF generation, source allowlisting, and missing-data safeguards are implemented and supported by automated or manual evidence.

The canonical objective is not met because mandatory critical gates fail:

- no verified ground-shaking layer exists, so the map cannot display all three required hazard layers and a complete live assessment cannot be produced;
- the live MGB flood endpoint currently advertises query capability but rejects point and feature queries with ArcGIS error 400, so flood cannot enter the assessment engine;
- the flood map uses an official ArcGIS raster export as a visual fallback, but the browser calls that service directly and no point classification can be matched to the raster value;
- the required React/TypeScript/FastAPI stack was replaced by vanilla JavaScript and a Python standard-library HTTP server;
- mandatory accessibility, mobile/tablet, offline-runtime, service-worker-update, Lighthouse/performance, and complete map/model consistency tests do not exist or were not executable;
- the UI renders the numeric source year `2016` as `Jan 1, 1970`;
- the PDF is readable but contains a schematic locator rather than the required real map snapshot and visible hazard layers, and it exposes mojibake in the model-status text.

The build is suitable for controlled demonstration of mapping, source transparency, and correct incomplete-data handling. It is not ready for a complete-assessment demonstration, public deployment, operational planning use, or any production/compliance claim.

## Validation performed

| Method or command | Result | Relevant evidence | Reproducible |
| --- | --- | --- | --- |
| `python -m unittest discover -s tests -v` using the bundled Python runtime | PASS: 92 tests; 6 skipped | Fuzzy, entropy, geometry, import, HTTP, ULAP fixture, missing-data, report, and workflow tests passed. One GIS reprojection and five opt-in live tests were skipped. | Yes |
| `LIVE_ULAP_TESTS=true python -m unittest tests.test_ulap_live -v` | FAIL: 3 passed, 2 failed | Flood point query and flood Basey GeoJSON failed with ArcGIS 400 `Requested operation is not supported by this service`; boundary, metadata, and no-ground-shaking-substitution checks passed. | Yes, subject to live service state |
| `python scripts/verify_ulap_services.py --json` | Expected nonzero exit 2 | Flood, liquefaction, municipal boundary, and barangay boundary metadata verified. Ground shaking is unavailable. The configured supplied boundary path is inaccessible. | Yes, subject to network |
| Live `POST /api/v1/assessments` at `11.290798389750039, 125.0336740411251` | PASS for safety behavior; FAIL for complete live result | Inside Basey, Barangay Tingib. Liquefaction `01 / Generally Susceptible / 50`; flood `invalid_response`; ground shaking `unavailable`; score null; missing inputs `flood, ground_shaking`. | Yes, subject to live service state |
| Browser: `/` to `/map` | PASS | Public landing page loaded without authentication; exact CTA opened GIS; boundaries and street tiles rendered. | Yes |
| Browser: GIS initial state | PARTIAL | 1 municipal polygon, 51 barangay polygons, three basemap radios, flood/liquefaction controls enabled, ground shaking disabled. | Yes |
| Browser: inside and outside coordinate checks | PASS with one state-transition defect | Inside point enabled assessment and identified Tingib. Outside point showed the canonical Basey-only message and disabled assessment. Previous result warning remained visible after the new outside selection. | Yes |
| Browser: incomplete assessment and preview | PASS for missing-data integrity | Result clearly showed incomplete, null score, unavailable hazards, normalized available input, equal-weight baseline, memberships, sources, cache status, recommendations, preview, and download. Progress remained at `Preparing report` instead of a terminal completed state. | Yes |
| Browser: basemap and hazard overlay check | PARTIAL | Streets, Esri World Imagery, and Esri World Topographic Map switch correctly. Official flood raster and four liquefaction vector paths can coexist above boundaries. Ground shaking is unavailable. | Yes, subject to live services |
| PDF download, `pdfinfo`, Poppler render, visual inspection of both pages | PARTIAL | Valid two-page PDF, readable hierarchy and no clipping. Missing hazards correctly suppress score. Actual map snapshot/visible layers are absent; locator is schematic; model status contains mojibake; PDF is untagged. | Yes |
| `python -m compileall -q geosafe scripts` | PASS | Python source imports/compiles. | Yes |
| `python -m pip check` | PASS | No broken installed requirements in the bundled runtime. | Yes |
| `node --check web/app.js` and `node --check web/service-worker.js` | PASS | JavaScript syntax valid. | Yes |
| Secret/credential scan with `rg` | PASS with caveat | No credential values or private keys found. `.env.example` contains an empty `ULAP_TOKEN`. Official public endpoints are committed by design. | Yes |
| HTTP header and OpenAPI inspection | PARTIAL | CSP, nosniff, frame denial, referrer and permissions headers present; API responses are no-store. `openapi.json` is 404 because the backend is not FastAPI. CSP allows inline styles and CDN Leaflet lacks SRI. | Yes |
| Lighthouse/axe/mobile-device/offline-network/service-worker-update audit | UNVERIFIED | No Lighthouse, axe, Pa11y, TypeScript, or ESLint tooling is included in the available runtime; browser viewport/offline emulation was unavailable. Static contracts are not substitutes for runtime audits. | No |

## Requirements register and compliance matrix

Status meanings: **PASS**, **PARTIAL**, **FAIL**, **UNVERIFIED**, and **NOT APPLICABLE** are applied exactly as defined by the evaluation protocol.

| ID | Requirement | Status | Evidence | Validation | Gap or Risk | Required Action |
| --- | ----------- | ------ | -------- | ---------- | ----------- | --------------- |
| SCOPE-01 | Public Web-GIS and preliminary multi-hazard screening for Basey, Samar | PASS | `web/index.html`, `web/map.html`, `GeoSafeService.identify_location` | Browser and HTTP tests | None material | Retain scope language |
| SCOPE-02 | Serve the listed public target users without role-specific behavior | PASS | Public unified interface; no user/role tables or routes | `test_scope.py`; browser | None | Retain unified public access |
| SCOPE-03 | Never declare safe/unsafe or issue certification, permit, zoning, engineering, valuation, or structural conclusions | PASS | Canonical disclaimer; recommendations in `config/fuzzy_model.json` | Frontend, workflow, and PDF tests; visual PDF check | None found | Maintain wording reviews |
| SCOPE-04 | Core map and assessment require no account | PASS | No password inputs/auth middleware; public `/map` and assessment API | Browser; HTTP and scope tests | Capability-token reports are not authenticated | Keep core public; document token privacy |
| SCOPE-05 | Do not imply Basey LGU administration, validation, adoption, or endorsement | PASS | Landing/about/source language | Static inspection | None found | Retain explicit non-endorsement |
| ROUTE-01 | `/` landing page | PASS | `server.py` alias to `index.html` | Browser and HTTP tests | None | None |
| ROUTE-02 | `/map` GIS workspace | PASS | `server.py` alias to `map.html` | Browser and HTTP tests | None | None |
| ROUTE-03 | `/assessment/:id` full explanation/report preview | PASS | Regex route to `map.html`; token load in `app.js` | Browser loaded saved incomplete assessment | Route is client-rendered, not a distinct document | Retain deep-link tests |
| ROUTE-04 | `/methodology` | PASS | `methodology.html` | HTTP tests and static inspection | None | None |
| ROUTE-05 | `/data-sources` | PASS | `info.html` + `info.js` | HTTP tests | None | None |
| ROUTE-06 | `/limitations` | PASS | `info.html` + `info.js` | HTTP tests | None | None |
| ROUTE-07 | `/about` | PASS | `info.html` + `info.js` | HTTP tests | None | None |
| ROUTE-08 | `/privacy` | PASS | `info.html` + `info.js` | HTTP tests | No history deletion control | Add deletion/retention controls |
| ROUTE-09 | `/offline` | PASS | `info.html` + service-worker fallback | HTTP/static PWA tests | Offline navigation not runtime-tested | Add offline E2E test |
| LANDING-01 | Sticky responsive header with required navigation and primary CTA | PASS | `web/index.html`; `web/site.css` | Browser DOM inspection | Contact placeholder is only in footer text | Retain |
| LANDING-02 | Exact hero copy, CTA, secondary action, and disclaimer | PASS | Hero in `index.html` | Browser inspection | None | None |
| LANDING-03 | Original GIS-style visual without pretending to show real values | PASS | CSS/SVG map illustration and sample card | Browser inspection | Visual accessibility not audited | Add visual/a11y review |
| LANDING-04 | Four-item trust/feature strip | PASS | `index.html` trust strip | Static test | None | None |
| LANDING-05 | Four-step how-it-works workflow | PASS | `#how-it-works` | Static test/browser | None | None |
| LANDING-06 | Three hazard cards with source-dependent language | PASS | `#hazards` cards | Static inspection | Ground shaking has no live layer | Keep unavailable status explicit |
| LANDING-07 | Explain relative 0-100 score and five bands with warning | PASS | Score section and warning | Browser inspection | Model bands are demonstration assumptions | Retain unvalidated-model label |
| LANDING-08 | Plain explainability flow and methodology link | PASS | Explainability section | Static test | None | None |
| LANDING-09 | Public use cases and further-investigation framing | PASS | Use-case section | Static inspection | None | None |
| LANDING-10 | Data-source groups and provenance/status presentation | PARTIAL | Landing groups; `/data-sources`; `info.js` | Browser/API inspection | Numeric year is misrendered as 1970 in result UI; local sources absent | Fix year formatting and add authorized local data |
| LANDING-11 | Eight clear limitation cards | PASS | Limitations section | Static test | None | None |
| LANDING-12 | PWA benefits and honest offline limits | PASS | PWA section and banner | Static test | Runtime offline behavior unverified | Add runtime PWA tests |
| LANDING-13 | Required FAQ topics | PASS | FAQ details in `index.html` | Static test | None | None |
| LANDING-14 | Footer, quick links, privacy, project/contact, disclaimer, attribution | PASS | Landing footer | Browser inspection | Contact is a placeholder as permitted | Replace when project contact is approved |
| GIS-01 | Desktop map-first shell with map, assessment panel, controls, legend, and source status | PARTIAL | `map.html`, `styles.css` | Desktop browser check | Assessment panel is neither user-resizable nor clearly collapsible on desktop | Add collapse/resize control |
| GIS-02 | Mobile full-screen map with bottom sheet, large targets, persistent assess action, no hover-only use | PARTIAL | Mobile media queries and 44px controls | Static CSS inspection | Mobile/tablet runtime and swipe behavior unverified; no swipe implementation found | Add device E2E and swipe semantics or revise requirement |
| GIS-03 | Municipal and barangay boundaries | PASS | Live PSA layers; dedicated panes | Browser: 1 municipal and 51 barangay paths | None during check | Retain live validation |
| GIS-04 | Search, coordinate, map click, draggable pin, current location, reset | PASS | `map.html`; `selectLocation`; draggable marker; geolocation handlers | Browser coordinate check; code/tests for other paths | Search/map-click/current-location not all manually exercised this run | Add browser E2E matrix |
| GIS-05 | Selected location, coordinates, barangay, and outside-Basey validation | PASS | Results/selection components | Browser inside and outside checks | Old assessment warning remains after selecting a new outside point | Clear stale results on location change |
| GIS-06 | Zoom and orientation controls | PARTIAL | Leaflet zoom control and reset/fit action | Browser/static inspection | No orientation/compass control | Implement or document an approved alternative |
| GIS-07 | Separate basemaps and overlays with opacity/legend/source controls | PARTIAL | `BASEMAP_DEFINITIONS`, layer rows, hazard pane | Browser layer checks | Ground shaking unavailable; control metadata omits some required details | Complete source and metadata panels |
| SOURCE-01 | Individually display flood, liquefaction, and ground-shaking layers | FAIL | Flood raster fallback; liquefaction vectors; ground shaking disabled | Browser and live verifier | Critical gate failure: no ground-shaking endpoint; flood feature query broken | Obtain verified ground-shaking and working flood query source |
| SOURCE-02 | Every layer exposes legend, title, description, source/date/retrieval/status/metadata/loading/error/unavailable states | PARTIAL | Layer controls, legend, ULAP health and metadata links | Browser and code inspection | Ground-shaking legend/opacity absent; descriptions/dates/retrieval not consistently in layer panel | Expand per-layer metadata UI and tests |
| SOURCE-03 | Map value equals value passed to assessment engine | PARTIAL | Vector labels and point adapter share service/domain definitions | Fixture tests; live checks | Flood map is raster-only while point query fails; no cross-surface assertion for all live hazards | Add identify-on-map and exact consistency integration tests |
| SOURCE-04 | No invented endpoint/layer/classification/endorsement | PASS | Versioned allowlisted registry and metadata validation | Live verifier; URL/SSRF tests | Source availability can change independently | Continue scheduled validation |
| SOURCE-05 | Demonstration data are exact and prominent; mocks isolated | PASS | Demo model status; test fixtures gated from normal server | Scope/import/workflow tests | Mojibake damages one visible demo label in PDF | Fix encoding |
| SOURCE-06 | Environment-variable adapter configuration for authorized sources | PASS | `.env.example`; `ServiceRegistry` host-controlled overrides | Registry tests | Ground-shaking URL deliberately absent | Add only after authorization |
| SOURCE-07 | Preserve organization, layer, source date, retrieval, service and cache status | PARTIAL | Saved hazard/source snapshots and report fields | API/PDF inspection | UI date formatter turns year 2016 into 1970; flood date absent | Treat year-only dates separately and test |
| ASSESS-01 | Implement the specified 16-step assessment workflow | PARTIAL | `create_assessment`, frontend progress, report actions | Live/browser and workflow tests | Live flow cannot progress to a complete fuzzy score | Restore sources and run complete live E2E |
| ASSESS-02 | Visible seven-step progress indicator | PASS | `assessment-progress` list | Browser check | Final step remains active instead of terminal complete | Add completed terminal state |
| ASSESS-03 | Results include location, source summary, score/category, hazards, warnings, explanation, recommendations, methodology and actions | PASS | Results renderer in `app.js` | Browser incomplete result; workflow tests | Complete live state unavailable | Validate once sources exist |
| ASSESS-04 | Per-hazard classification, legend description, normalized input, weight, memberships, provenance, cache and availability | PARTIAL | Hazard cards and memberships | Browser result inspection | Missing hazard cards correctly lack memberships; legend description is not consistently linked in results | Add explicit legend meaning per card |
| ASSESS-05 | Cautious planning-oriented recommendations; no prohibited advice | PASS | Config recommendation templates | Tests and visual result/PDF inspection | Unvalidated templates | Obtain expert review before operation |
| MISSING-01 | Never substitute zero/Low/Very Low for missing required inputs | PASS | `FuzzyModel.evaluate`; service/source status handling | Multiple unit/integration/live checks | None found | Retain regression tests |
| MISSING-02 | Identify missing layer and connectivity/service/coverage/schema cause | PASS | Granular ULAP status model and warnings | Provider tests and live result | None | Retain |
| MISSING-03 | Withhold or mark incomplete and request retry | PASS | Null score, `Incomplete`, recommendations | Browser/API/PDF checks | No score generated live, as required | Retain |
| MISSING-04 | Use cache only with source/retrieval/expiry; never silently reuse stale data | PASS | ArcGIS cache metadata; `ULAP_ALLOW_STALE_CACHE=false`; UI cache state | Cache tests and live UI | Browser map raster bypasses backend cache policy | Proxy raster export through backend or document policy |
| FUZZY-01 | Configuration-driven Mamdani model separate from presentation | PASS | `config/fuzzy_model.json`; `geosafe/fuzzy.py` | Fuzzy tests | None structurally | Retain version control |
| FUZZY-02 | Ordered category mapping and normalization to 0-1 | PARTIAL | Exact code mappings and UI fractional display | Config/code inspection | Engine evaluates 0-100 inputs, not the specified 0-1 internal range | Align implementation/methodology and migration tests |
| FUZZY-03 | Entropy-derived objective weights with documented equal fallback | PARTIAL | `entropy_weight.py`; tests; configured pending status | Entropy tests | Entropy weights are not stored/operational; live result uses equal baseline | Supply representative dataset, calculate/version weights, validate experts |
| FUZZY-04 | Source-aligned memberships; minimum activation, maximum aggregation, centroid | PASS | `FuzzyModel.evaluate` and config | Membership/fuzzy tests | Membership breakpoints are unvalidated | Expert validation required |
| FUZZY-05 | Systematically generated complete monotonic rule base | PASS | 27-rule ordinal grid | Coverage and monotonicity tests | Canonical prompt mentions systematic rules; project docs elsewhere incorrectly mention 12 | Correct stale documentation |
| FUZZY-06 | Five output categories and `score = 100 x normalized output` | PARTIAL | Five memberships/categories; centroid on 0-100 output | Fuzzy tests | Code rounds a 0-100 centroid directly and never exposes the specified normalized output conversion | Make normalized-output conversion explicit and test it |
| FUZZY-07 | Expose inputs, normalized values, weights, memberships, principal rules, model version | PASS | Result/explanation APIs and UI | Workflow/browser tests | Complete live activated-rule presentation unavailable | Recheck after source restoration |
| FUZZY-08 | Reproducible versioned records; missing never enters engine as low | PASS | Model checksum; immutable snapshot; missing gate | Workflow/fuzzy/report tests | None found | Retain |
| REPORT-01 | Preview and download preliminary PDF | PASS | Dialog and report endpoint | Browser, HTTP, PDF render | None for incomplete report | Retain |
| REPORT-02 | Required report content including actual map snapshot and visible layers | PARTIAL | `assessment_report_lines`; `generate_pdf` | Two-page visual inspection | Locator is schematic; actual map and visible layer state are absent | Capture permitted map/layer snapshot in saved assessment/report |
| REPORT-03 | Prominent disclaimer, immutable snapshot, generation time, model/source metadata and digest | PASS | PDF code, stored report snapshot, SHA header | Workflow/HTTP/PDF checks | PDF source date formatting differs from UI but is correct for 2016 | Retain |
| REPORT-04 | Professional, accessible visual output | PARTIAL | Branded two-page PDF | Poppler visual check | Mojibake in model status; PDF untagged; long prose-heavy layout | Fix encoding; add tagged/accessible PDF plan and visual regression |
| PWA-01 | Installable manifest, icons, maskable icon, colors, standalone mode and install prompt | PARTIAL | `manifest.webmanifest`; icons; `pwa.js` | Static PWA tests | Install prompt and installability not verified by Lighthouse/device | Add Lighthouse and device checks |
| PWA-02 | Service worker, versioning, invalidation, shell and offline fallback | PASS | `service-worker.js` v7 caches | Static tests and syntax check | Runtime registration/cache update not inspected | Add runtime tests |
| PWA-03 | Cache-first static, stale-while-revalidate info, network-first hazard/assessment inputs | PARTIAL | Static/cache-first and informational SW paths; APIs call network | Code inspection | API uses network-only, not network-first with permitted cache fallback; flood raster bypasses backend | Implement documented policy or amend after source-policy review |
| PWA-04 | Offline/stale banner, update notification, iOS guidance, nonblocking install | PASS | `pwa.js`, offline banners | Static tests | Offline and update transitions not runtime-tested | Add browser automation |
| PWA-05 | Reopen permitted prior reports offline | FAIL | No report response caching/local blob persistence | Code inspection | Required PWA behavior absent | Add permission-aware local report storage and deletion |
| STACK-01 | React, TypeScript, component architecture and form/state tooling | FAIL | Vanilla HTML/CSS/JS; 3,063-line `app.js` | Repository inspection | Canonical stack not used; no component library/typecheck/build | Migrate or obtain explicit stack waiver |
| STACK-02 | Python FastAPI backend with typed request/response schemas | FAIL | `ThreadingHTTPServer`/manual dispatcher; `openapi.json` 404 | Code and HTTP inspection | No FastAPI/OpenAPI; Pydantic covers only ULAP models | Migrate backend or obtain waiver |
| STACK-03 | GeoPandas, Shapely, PyProj, Requests/Pandas and scikit-fuzzy or transparent custom engine | PARTIAL | Transparent custom fuzzy; optional Shapely/PyProj imports | Dependency/code inspection | GeoPandas/Pandas/Requests absent; Shapely/PyProj optional only | Document approved equivalents or align dependencies |
| STACK-04 | Workbox or maintained equivalent PWA tooling | PARTIAL | Handwritten service worker | Static tests | No Workbox, integration harness, or browser install audit | Adopt maintained tooling or add equivalent rigorous tests |
| API-01 | Required documented endpoints and public contracts | PASS | `api.py`; `docs/api.md`; compatibility aliases | HTTP and workflow tests | Canonical `/api/health` exists; no OpenAPI | Retain route tests |
| API-02 | Typed API schemas | PARTIAL | Pydantic ULAP models; manual JSON validation | Registry tests/code inspection | Assessment/location/report contracts are not typed schemas | Add Pydantic request/response models and OpenAPI |
| API-03 | Modular source, GIS, normalization, weighting, fuzzy, explanation, recommendation, report, cache, model and audit services | PARTIAL | ULAP package, geometry, fuzzy, entropy, service, PDF, repository | Repository inspection | Several proposed services are combined in `GeoSafeService`; no explicit audit/model-version/cache service modules | Refactor around defined interfaces |
| API-04 | Assessment metadata/audit logging and secure error handling | PARTIAL | Structured sanitized ULAP logging and safe API errors | Client tests and code | No persistent AuditLog entity/service; request correlation IDs absent | Add privacy-reviewed technical audit trail if still required |
| DATA-01 | Core spatial, hazard, assessment, fuzzy and report schemas | PASS | `db/schema.sql` | Schema allowlist tests | None for implemented scope | Retain migrations/tests |
| DATA-02 | All proposed entities including user/saved location/data source/layer/cache/audit records | FAIL | Several concepts embedded in JSON; account/cache/audit entities absent | Schema inspection | Canonical entity design incomplete, even though accounts are optional | Add schema design or document approved exclusions |
| DATA-03 | Preserve coordinate, barangay, source values/IDs/dates/cache, normalized inputs, weights, version, rules, result and report ID | PASS | Immutable assessment/report snapshots | Workflow and report tests | Live flood values absent because source fails | Retain snapshot tests |
| A11Y-01 | Semantic HTML, labels, keyboard navigation, focus states, map alternatives and descriptive errors | PARTIAL | Skip link, semantic regions, labels, focus CSS, coordinate/search alternatives | Static inspection/browser DOM | No automated keyboard/screen-reader audit; SVG role/image naming risk | Run axe and keyboard/screen-reader tests |
| A11Y-02 | High contrast, non-color meaning, touch targets and text alternatives | PARTIAL | Text statuses, patterns/labels, 44px controls | CSS/DOM inspection | Contrast ratios and mobile touch behavior not measured | Add automated contrast/touch assertions |
| A11Y-03 | Reduced motion and accessible dialogs/bottom sheets | PARTIAL | Reduced-motion media queries; native dialog | Static inspection/browser preview | Focus trap/return and mobile bottom-sheet behavior unverified | Add interaction tests |
| A11Y-04 | Accessibility tests | FAIL | Only static frontend contracts | Test inventory | No axe/Pa11y/WCAG runtime tests | Add CI accessibility suite |
| PERF-01 | Code splitting, lazy sections, minimal initial JS | FAIL | One 131,829-byte, 3,063-line `app.js`; no build pipeline | File-size/code inspection | No splitting/lazy component loading | Introduce frontend build and route/component chunks |
| PERF-02 | Optimized responsive imagery/SVG | PARTIAL | Mostly CSS/SVG illustration and PNG icons | File inspection | `web/og.png` is 1.93 MB; no responsive source set | Compress social image and audit assets |
| PERF-03 | Efficient layers, debounce/cancellation, skeletons, caching and graceful updates | PARTIAL | BBox/pagination, request aborts, loading states, SW caches | Tests/code/browser | Search is submit-only rather than debounced; flood raster is fixed 1600px; no measured budgets | Add performance budgets and map request tests |
| PERF-04 | Performance validation | UNVERIFIED | No Lighthouse/WebPageTest configuration | Tool inventory | No measured LCP/CLS/JS/map metrics | Add repeatable mobile Lighthouse audit |
| SEC-01 | Validation, encoding, rate limiting, safe headers and errors | PASS | API validation, `escapeHtml`, rate limiter, CSP and security headers | Tests and header inspection | CSP still allows inline styles | Tighten CSP where feasible |
| SEC-02 | HTTPS-ready env secrets, allowlisted source access, no credentials in frontend/repo | PARTIAL | Env-only token, SSRF allowlist, secret-safe logs | Secret scan and tests | Browser directly requests official flood raster; CDN has no SRI; app itself serves HTTP locally | Proxy raster; add SRI/self-host Leaflet; deploy behind HTTPS |
| SEC-03 | Minimal data, privacy statement, retention and user-controlled history deletion | PARTIAL | No account/PII collection; privacy page; device-local history | Code inspection | No UI to clear local history or delete persisted assessment/report snapshots; retention undefined | Add deletion and retention policy |
| SEC-04 | Protected private reports and no public PII incidents | PARTIAL | Unguessable capability token; no shared listing; incident tables empty | Workflow tests | Token possession grants report access; no authentication for saved private reports | Define threat model and protected-account option if needed |
| TEST-01 | Normalization, entropy, memberships, score, rule coverage and monotonicity tests | PASS | `test_entropy_weight.py`, `test_fuzzy.py` | 92-test suite | Explicit `100 x normalized output` test absent | Add conversion-specific assertion |
| TEST-02 | Source retrieval, missing-data, map/model consistency and boundary tests | PARTIAL | ULAP, workflow and geometry suites | Offline suite passes | Live flood tests fail; no exact rendered-map-to-point-model E2E | Restore source then add cross-surface test |
| TEST-03 | Accessibility, installability, offline, update and responsive tests | FAIL | Static PWA/frontend contracts only | Test inventory | Required runtime suites absent | Add axe, Lighthouse and device/offline browser tests |
| TEST-04 | Report and end-to-end public assessment tests | PARTIAL | HTTP workflow and PDF tests | Offline suite passes; manual incomplete live flow | No browser E2E complete assessment; no PDF visual regression; live suite fails | Add E2E and golden visual tests |
| DELIVERABLE-01 | Full landing page, GIS workspace and frontend source | PARTIAL | `web/` implementation | Browser/manual/static tests | GIS lacks required third live layer and mandated frontend stack | Complete hazards and stack decision |
| DELIVERABLE-02 | Reusable UI component library | FAIL | Shared CSS classes only | Repository inspection | No component library | Create typed accessible components during frontend migration |
| DELIVERABLE-03 | FastAPI scaffold, typed contracts and GeoRiskPH adapters | PARTIAL | Strong adapter package; manual server/API | Tests/inspection | FastAPI and full typed schemas missing | Migrate server/contracts |
| DELIVERABLE-04 | PWA configuration | PARTIAL | Manifest, SW, install/update/offline UI | Static tests | Runtime install/offline/update unverified; offline reports absent | Complete runtime PWA acceptance |
| DELIVERABLE-05 | Fuzzy engine, database schemas and report template | PARTIAL | Implemented modules/config/schema/PDF | Tests and visual PDF check | Operational entropy weights and real map report snapshot absent | Address model/report gaps |
| DELIVERABLE-06 | Environment example, setup and local-development instructions | PASS | `.env.example`, `README.md`, scripts docs | Inspection and local run | README initially understates ReportLab install wording but dependency is declared | Clarify install text |
| DELIVERABLE-07 | Deployment instructions, endpoint TODOs and scope/limitations README | PARTIAL | Extensive known-gap and integration docs | Inspection | No concrete production deployment target/runbook; no explicit code TODO markers | Add deployment runbook after platform choice |
| QUALITY-01 | Coherent functioning app, not static mockup; realistic states | PARTIAL | Interactive map/API/PDF and state UI | Browser/live tests | Complete-success live state unavailable; offline/update/report-failure transitions unverified | Add sources and state E2E |
| QUALITY-02 | Clean separation of GIS, model, data, report and PWA services | PARTIAL | Backend modules are separated | Code inspection | Frontend is a monolithic `app.js`; several backend services remain combined | Refactor |
| QUALITY-03 | Clear documentation; no unsupported scientific/government claims | PASS | README/config/docs disclaimers and validation notes | Static/PDF/browser inspection | Model remains deliberately unvalidated | Preserve warnings until expert approval |

## Mandatory critical gates

| Gate | Status | Evidence and consequence |
| --- | --- | --- |
| 1. Public landing opens without authentication | PASS | Browser and HTTP tests passed. |
| 2. Assess a Location opens GIS | PASS | Exact CTA navigated to `/map`. |
| 3. Core features require no account | PASS | No auth/account flow exists. |
| 4. Supports locations within Basey | PASS | Live inside point identified Tingib; outside point blocked. |
| 5. Supports flood, liquefaction and ground-shaking layers | FAIL | Ground shaking has no verified endpoint; flood query is currently rejected. |
| 6. Each layer has legend, source, status and metadata | FAIL | Ground shaking has no drawable layer/legend/opacity; metadata treatment is incomplete. |
| 7. Map value equals assessment value | PARTIAL | Liquefaction shares verified source/domain; flood is raster-only while point query fails; no three-layer E2E consistency proof. |
| 8. Missing data never becomes zero/Low/Very Low | PASS | Unit, integration, live API, browser and PDF evidence. |
| 9. Incomplete assessments withheld/labeled | PASS | Live score is null and clearly incomplete. |
| 10. Mock data labeled demonstration-only | PASS | Runtime fixtures are gated; demo model label is visible, aside from PDF encoding defect. |
| 11. No fabricated source or endorsement | PASS | Live metadata validation and allowlisted registry. |
| 12. Fuzzy model configuration-driven/separate | PASS | JSON model plus backend engine. |
| 13. Inputs, normalized values, weights, memberships, rules and version exposed | PASS | Result/explanation UI and API; rules are correctly absent when incomplete. |
| 14. Output includes more than final score | PASS | Full hazard/source/explanation/recommendation panels. |
| 15. Never declares safe/unsafe | PASS | Canonical disclaimers and tests. |
| 16. No official certification/permit/zoning/engineering/valuation implication | PASS | Scope and recommendations reviewed. |
| 17. Preview/download report | PASS | Browser preview and valid PDF download. |
| 18. Cached versus current distinguished | PASS | Live/cache/stale/expiry fields are exposed. |
| 19. No claim that complete new assessment always works offline | PASS | Offline banners explicitly say current access may be required. |
| 20. Mobile/tablet/desktop responsive | PARTIAL | Responsive CSS exists; only desktop runtime was verified. |
| 21. Hazard meaning not color-only | PASS | Text labels/statuses/legend entries accompany color. |
| 22. No Basey LGU administration/endorsement implication | PASS | Public research framing throughout. |
| 23. No frontend/repository credentials or administrative secrets | PASS | Secret scan and token-safety tests passed. |
| 24. Required automated tests exist and pass | FAIL | Offline suite passes, but live flood tests fail and required a11y/mobile/offline/update/map-model runtime suites are absent. |

Safety, data-integrity, and source-availability failures prevent an overall `MET` result.

## Realistic application states

| State | Status | Evidence / gap |
| --- | --- | --- |
| Initial/empty | PASS | Map empty-state instructions and disabled assessment action. |
| Loading | PASS | Map loading, search feedback, results skeleton and seven-step progress UI. |
| Successful complete assessment | UNVERIFIED | Fixture workflow passes; impossible with current live sources. |
| Invalid location/input | PASS | Validation tests and form handling. |
| Outside Basey | PASS | Manual browser state and disabled action. |
| Layer-loading failure | PASS | Per-layer failure UI; flood now uses official raster fallback. |
| Source unavailable | PASS | Ground shaking unavailable and live flood invalid response are explicit. |
| Missing required input | PASS | Null normalized values, no low substitution. |
| Partial/incomplete assessment | PASS | Live browser/API/PDF verified. |
| Offline | PARTIAL | Banner/page/SW exist; no runtime network-disconnection test. |
| Cached/stale data | PASS | Source cache, retrieval, expiry and stale fields are modeled/displayed. |
| Report-generation failure | UNVERIFIED | Catch/error UI exists; failure transition not exercised. |
| Service-worker update available | UNVERIFIED | Update-notice code exists; transition not exercised. |
| Optional-account authentication | NOT APPLICABLE | Accounts are optional and intentionally absent; core features remain public. |

## Fuzzy-model evaluation

| Model requirement | Status | Evidence / finding |
| --- | --- | --- |
| Ordered source-category mapping | PASS | Exact `fscode`/`lccode` mappings; no ordinal inference from codes. |
| Normalization to 0-1 | PARTIAL | UI exposes fractions, but engine uses a 0-100 universe. |
| Entropy-derived objective weights | PARTIAL | Calculator and tests exist; operational dataset/weights do not. |
| Documented equal-weight fallback | PASS | Explicitly labeled research baseline is applied. |
| Source-aligned memberships | PARTIAL | Configured and tested, but not domain-validated. |
| Systematic monotonic rules | PASS | Complete 27-rule grid generated. |
| Minimum activation | PASS | Implemented and tested. |
| Maximum aggregation | PASS | Implemented and tested. |
| Centroid defuzzification | PASS | Implemented and tested. |
| `score = 100 x normalized output` | PARTIAL | Equivalent intent is not explicit; a 0-100 centroid is rounded directly. |
| Five output categories | PASS | Very Low through Very High. |
| Complete rule coverage | PASS | Coverage test passes. |
| Monotonicity | PASS | Representative-grid test passes. |
| Reproducibility/model version | PASS | Configuration checksum and immutable snapshots. |
| Missing input exclusion | PASS | No rules/score when required inputs are missing. |

Scientific status: all mappings, memberships, thresholds, equal weights, rules, and recommendations remain demonstration assumptions. No operational validity claim is justified without qualified domain review.

## Acceptance-criteria summary

- Passed acceptance criteria: `11/18`
- Partially met: `6/18`
- Failed: `1/18`
- Unverified: `0/18`

| AC | Status | Finding |
| --- | --- | --- |
| 1. Public landing without sign-in | PASS | Verified in browser and HTTP tests. |
| 2. CTA opens GIS | PASS | Verified. |
| 3. Rich, responsive, understandable landing | PARTIAL | Desktop verified; mobile/tablet runtime not verified. |
| 4. Installable PWA | PARTIAL | Manifest/SW/install UI present; installability not device/Lighthouse verified. |
| 5. Select a location within Basey | PASS | Verified at Tingib control point. |
| 6. Display flood, liquefaction and ground-shaking layers | FAIL | Ground shaking absent; flood query cannot supply assessment values. |
| 7. Every layer has legend/source | PARTIAL | Ground-shaking drawable legend/opacity absent. |
| 8. Map value matches engine value | PARTIAL | Liquefaction path is aligned; flood/ground shaking cannot be proven. |
| 9. Missing information does not become low | PASS | Strong automated and live evidence. |
| 10. More than final score | PASS | Full evidence/explanation panels. |
| 11. Inputs, weights, memberships and key rules | PASS | Verified; no rules shown for incomplete result by design. |
| 12. Never definitively safe/unsafe | PASS | Verified. |
| 13. Preview/download report | PASS | Verified. |
| 14. No account for core functions | PASS | Verified. |
| 15. Offline distinguishes cached/current | PARTIAL | Correct UI/code; runtime offline transition unverified. |
| 16. Mobile/tablet/desktop | PARTIAL | Responsive CSS only; runtime device coverage incomplete. |
| 17. No LGU administration/endorsement implication | PASS | Verified. |
| 18. No fabricated GeoRiskPH sources/classifications | PASS | Registry/live metadata validation verified authenticity. |

## Deliverables summary

| Deliverable | Classification | Notes |
| --- | --- | --- |
| Full responsive landing page | Complete | Desktop verified; device-specific runtime audit remains. |
| Full GIS workspace | Partial | Functional Basey map; third hazard absent and flood point query broken. |
| Reusable UI component library | Missing | Shared CSS is not a reusable component library. |
| PWA configuration | Partial | Structural implementation present; runtime acceptance and offline reports absent. |
| Frontend source code | Partial | Complete vanilla frontend, but required React/TypeScript stack is not used. |
| FastAPI backend scaffold | Missing | Manual Python HTTP server used instead. |
| Typed API contracts | Partial | ULAP models typed; general API contracts are manual/documented only. |
| GeoRiskPH adapter interfaces | Complete | Registry/client/providers/validators implemented and tested. |
| Clearly labeled mock development adapter | Complete | Fixtures/test doubles isolated; operational demo seed rejected. |
| Fuzzy-engine module structure | Partial | Strong engine; operational entropy weights and exact scale contract incomplete. |
| Database schemas | Partial | Core schema complete; several proposed entities absent. |
| Report template | Partial | Valid/readable PDF; actual map/layers and encoding/accessibility need work. |
| Accessibility implementation | Partial | Good foundations; no runtime WCAG audit. |
| Automated tests | Partial | Strong 92-test offline suite; live flood and required runtime suites fail/missing. |
| Environment-variable example | Complete | Present with empty token. |
| Setup instructions | Complete | Present in README. |
| Local-development instructions | Complete | Present and reproducible. |
| Deployment instructions | Partial | Data/security notes exist; no production platform/runbook. |
| Authorized-endpoint TODOs | Partial | Known gaps are explicit, but no concrete code TODO workflow. |
| Scope/limitations README | Complete | Clear prototype status and disclaimers. |

## Critical issues

1. **Source/data integrity:** the official flood query operation currently fails. The raster export is visual only and cannot safely supply a point classification to the model.
2. **Required hazard absence:** no authorized ground-shaking source exists. Every live assessment must remain incomplete.
3. **Map/model consistency:** flood and ground shaking cannot satisfy end-to-end value equality; the direct browser raster call also contradicts the documented backend-only source boundary.
4. **Model validity:** entropy weights are not operational and all transformations, membership functions, thresholds, rules and recommendations remain unvalidated demonstration assumptions.
5. **Testing:** two opt-in live tests fail; required accessibility, mobile/tablet, offline, update, installability and map/model consistency runtime tests are absent.
6. **Report accuracy/accessibility:** actual map/layers are absent, model-status text has mojibake, and the PDF is untagged.
7. **Frontend accuracy:** a year-only source date (`2016`) is rendered as `Jan 1, 1970`.
8. **Technology compliance:** React, TypeScript and FastAPI are not used; no OpenAPI contract is generated.
9. **Privacy:** device-local history and server snapshots have no user-facing deletion or defined retention process.

## Noncritical improvements

- Clear results and quality banners whenever a new location is selected.
- Mark the final assessment progress step complete instead of leaving it active.
- Add a desktop collapse/resize control and an orientation/compass control.
- Put description, source/publication date, retrieval time and complete status metadata directly in every layer panel.
- Split the monolithic frontend and optimize the 1.93 MB social image.
- Self-host or add integrity metadata for Leaflet and tighten the CSP.
- Correct stale documentation that still mentions 12 fuzzy rules when the implementation generates 27.

## Prioritized next steps

### 1. Must fix before further evaluation

1. **Restore authoritative hazard retrieval.** Affected: `config/ulap-services.generated.json`, `geosafe/ulap/*`, `tests/test_ulap_live.py`. Completion: flood point and Basey geometry queries pass from the intended deployment network; a verified ground-shaking layer, field, domain, date, coverage and attribution are configured. Validation: live verifier exits 0 and all five live tests pass.
2. **Prove map/model equality.** Affected: hazard overlay/identify API and `web/app.js`. Completion: clicking an overlay yields the exact raw code/label saved into the assessment snapshot, for all three hazards. Validation: automated browser/API consistency test.
3. **Resolve the mandated stack decision.** Affected: full frontend/backend. Completion: migrate to React/TypeScript/FastAPI with typed OpenAPI contracts, or obtain an explicit user-approved specification waiver. Validation: build, typecheck, API schema and E2E tests.

### 2. Must fix before public demonstration

1. Fix year-only source-date rendering in `web/app.js`; validate `2016` remains `2016`.
2. Clear stale results on new selection and finish the progress state.
3. Add actual map/layer capture to `geosafe/pdf.py`; fix encoding and visually inspect complete/incomplete PDFs.
4. Run desktop, tablet and mobile browser E2E, keyboard, axe/contrast, installability, offline and update checks.
5. Version and clearly display expert-reviewed weights or keep all score demonstrations disabled.

### 3. Must fix before deployment

1. Define deployment platform, HTTPS/reverse proxy, retention, backup, monitoring and recovery runbook.
2. Add local-history and persisted-assessment/report deletion; document retention.
3. Proxy the flood raster through the backend and enforce source/cache policy consistently.
4. Add SRI or self-host Leaflet, tighten CSP, and perform dependency/security scanning.
5. Obtain documented authorization and expert validation for all hazard sources, transformations and methodology.

### 4. Recommended future enhancement

1. Build reusable accessible UI components and split frontend bundles.
2. Add responsive map-image requests, asset compression and measurable performance budgets.
3. Add permission-aware offline reopening of prior reports.
4. Add production observability without creating an inappropriate public administrative subsystem.

### Your evaluation requested

No user evaluation is required for the verified items. Input is needed only for the decisions listed below.

### Decisions needed

1. Provide or authorize the verified GeoRiskPH ground-shaking service metadata: endpoint, layer ID, field/unit/domain, source date, coverage, attribution, and access requirements.
2. Confirm whether the canonical React/TypeScript/FastAPI stack remains mandatory or whether the current vanilla JavaScript/standard-library Python architecture is approved as an explicit exception.
3. Identify the intended deployment environment so HTTPS, caching, storage, deletion, retention and monitoring requirements can be validated.

### Recommended next action

Resolve the source-integrity gate first: obtain a working authorized flood query path and verified ground-shaking source, then rerun the live suite and implement the exact map-to-model consistency test before any other major revision.

### Available response choices

- **Approve the current phase** as a limited incomplete-assessment prototype
- **Fix all critical failures**
- **Fix a specific requirement** by ID
- **Implement the recommended next action**
- **Re-run the full evaluation** after source or architecture changes
- **Provide missing source or configuration information**
