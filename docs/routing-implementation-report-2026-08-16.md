# Basafe routing implementation report

Date: 2026-08-16  
Branch: `codex/geosafe-fis-revisions`

## 1. Architecture

Routing is a dedicated `HazardAwareRouter` beside, not inside, the fuzzy
engine. `GeoSafeService` exposes a non-persistent `evaluate_point` boundary for
offline edge enrichment and delegates runtime route work to the router. SQLite
stores the town-proper polygon and designated centers. NetworkX loads a frozen
GraphML graph and runs A* locally. The existing framework-free API and Leaflet
map expose routing without replacing the assessment workflow.

## 2. Files changed for routing

Added:

- `config/routing.json`
- `geosafe/routing.py`
- `scripts/import_routing_data.py`
- `scripts/build_town_proper_boundary.py`
- `scripts/sync_town_proper_network.py`
- `scripts/enrich_route_hazards.py`
- `scripts/evaluate_routing_cases.py`
- `data/routing/README.md`
- `data/routing/town_proper_boundary.template.geojson`
- `data/routing/evacuation_centers.template.csv`
- `data/routing/evaluation_cases.template.csv`
- `tests/test_routing.py`
- `tests/test_study_area.py`
- `docs/routing.md`
- this report

Modified:

- backend/API: `geosafe/api.py`, `geosafe/service.py`,
  `geosafe/repository.py`, `geosafe/server.py`, `api/index.py`
- persistence/deployment: `db/schema.sql`, `data/geosafe.snapshot.db`
- frontend/offline: `web/map.html`, `web/app.js`, `web/styles.css`,
  `web/methodology.html`, `web/service-worker.js`
- dependencies: `pyproject.toml`, `requirements.txt`, `uv.lock`
- tests/docs: `tests/test_frontend_contract.py`, `tests/test_scope.py`,
  `README.md`, `scripts/README.md`, `docs/api.md`, `docs/architecture.md`,
  `docs/known-data-gaps.md`

Other pre-existing uncommitted workspace changes were preserved.

## 3. Implemented algorithm

Shortest route:

```text
C_e = D_e
```

Lower-Hazard Route:

```text
C_e = D_e (1 + lambda H_e)
```

`D_e` is edge length in metres, `H_e` is the precomputed multi-hazard mapped
exposure normalized to `[0,1]`, and non-negative `lambda` is the configurable
`risk_factor`. Missing exposure rejects the edge in hazard-aware mode; it is
never zero. A* uses geodesic remaining distance, which is admissible because
generalized cost cannot be less than distance.

## 4. Road network

| Item | Current value |
| --- | --- |
| Source | © OpenStreetMap contributors through explicit OSMnx operator synchronization |
| Type | Pedestrian / `walk` |
| Node count | 120 |
| Edge count | 354 directed edges |
| Snapshot path | `data/routing/basey_town_proper_walk.graphml` |
| Acquisition date | 2026-08-16 |

No graph was fabricated or downloaded. The study polygon is now available as
a researcher-defined composite of seven loaded official PSA barangay polygons;
the explicit operator network-synchronization step has not yet been run.

## 5. Evacuation-center data

Verified centers available: **No**. The schema, importer, empty CSV template,
provenance fields, active/version handling, optional capacity, and separately
stored destination mapped-hazard screening are implemented. No fake center was
inserted into either local or deployment SQLite.

## 6. Hazard enrichment

The enrichment command samples edge geometry, calls the existing BaSafe FIS
with `persist=False` and `local_only=True`, aggregates supported flood,
liquefaction, ground-shaking, and multi-hazard values, and writes completeness,
mean, maximum, sample count, model version, and hazard-data versions to GraphML.
It also screens each imported center without changing its official designation.
Runtime route requests do not call the FIS or perform enrichment.

## 7. API

- `GET /api/v1/routing/status`
- `GET /api/v1/evacuation-centers`
- `POST /api/v1/route`

Compatibility aliases are also provided under `/api/...`. Structured errors
cover invalid/outside points, missing graph/centers, disconnected centers,
incomplete hazards, absent hazard-aware paths, and generation failures.

## 8. Frontend workflow

The existing map contains a collapsed `Evacuation routing` panel. A configured
deployment lets an inside-Basey point request either Multi-Hazard Planning
Lower-Hazard or Shortest routing. The result adds center and route layers,
approximate time/distance/exposure, destination screening, a two-route table,
plain-language tradeoff, technical provenance on demand, layer toggles, removal,
and a persistent planning-aid disclaimer. The current data-missing deployment
shows `Data required` and the exact dependency.

## 9. Tests

Commands:

```powershell
python -m unittest discover -s tests -q
node --check web/app.js
python -m compileall -q geosafe scripts tests
git diff --check
vercel build
```

Result after the shared OSM search integration: **130 tests passed, 6 skipped**.
JavaScript syntax, Python compilation,
SQLite integrity, and diff checks passed. Routing coverage includes shortest,
longer lower-exposure alternative, equal hazard, monotonicity, missing hazard,
MultiDiGraph parallel edges, disconnected/multiple centers, town-proper scope,
no route, GeoJSON coordinate order, API responses, non-persistent evaluation,
and a patched-network zero-download local GraphML request.

The Vercel preview build completed successfully. On this Windows path, the
Python Scripts directory had to be supplied through its no-space short path to
work around a Vercel CLI command-quoting issue; the application build itself
completed without errors.

Browser checks at desktop and mobile sizes confirmed the truthful missing-data
state and an unchanged complete Magallanes assessment (score 65, High).

## 10. Research metrics

The API and batch CSV command expose test-case/start/destination, each route's
distance, approximate walking time, mean/maximum exposure, elevated-exposure
distance, completeness, distance difference/increase, and computation time.
No superiority claim is generated.

## 11. Remaining limitations

1. Production routing is blocked by the missing verified designated
   evacuation-center dataset.
2. The seven-barangay town-proper grouping is researcher-defined; only its
   component PSA barangay polygons are represented as official source records.
3. The current implemented scenario is `multi_hazard`; flood-only and
   earthquake-only routing are not asserted without separate scientific
   validation.
4. The fuzzy model remains a research model requiring domain validation.
5. Routes do not include real-time closures, water depth, structural damage,
   traffic, crowds, passability, or official orders.
6. Walking time is a constant-speed estimate.
7. Representative-user testing and field validation have not been performed.

## 12. Completion matrix

| Requirement | Status | Evidence |
| --- | --- | --- |
| Repository inspection and integration plan | Complete | Architecture summary and `docs/routing.md` |
| Town-proper support | Complete for the declared research scope | Reproducible composite of Mercado, Palaypay, Baybay, Sulod, Loyo, Buscada, and Lawa-an; component provenance retained; grouping explicitly non-official |
| Frozen pedestrian graph runtime | Complete | 120-node/354-edge GraphML loaded locally and included in the Vercel function bundle |
| Verified evacuation centers | Blocked by Missing Dataset | Empty template/import/schema; zero production rows |
| Dedicated routing module | Complete | `geosafe/routing.py` |
| Non-persistent FIS reuse | Complete | `evaluate_point(..., persist=False, local_only=True)` |
| Offline edge hazard enrichment | Complete | `scripts/enrich_route_hazards.py` |
| Missing-is-unknown policy | Complete | `reject_edge`, tests |
| Shortest scenario | Complete | Distance A* and tests |
| Multi-hazard Lower-Hazard scenario | Complete | Generalized cost A* and tests |
| Flood-only scenario | Not Implemented | Requires scenario-specific validation |
| Earthquake-only scenario | Not Implemented | Requires validated liquefaction/shaking combination |
| Evaluate every reachable center | Complete | Candidate loop and ranking tests |
| Route metrics and GeoJSON | Complete | API payload and tests |
| Routing APIs | Complete | Three versioned endpoints |
| Frontend request/comparison/layers | Complete | Existing Leaflet map extension and contract tests |
| Runtime network isolation | Complete | Local GraphML test with network patched to fail |
| Research CSV export | Complete | `scripts/evaluate_routing_cases.py` |
| Production Basey routing | Blocked by Missing Dataset | Status endpoint reports the missing designated-center input |
