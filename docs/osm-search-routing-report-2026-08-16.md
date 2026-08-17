# Basafe local OSM search and routing implementation report

Date: 2026-08-16  
Branch: `codex/geosafe-fis-revisions`

## 1. Architecture summary

One explicit OSMnx synchronization reads the project-defined seven-barangay
study area and creates a frozen pedestrian GraphML graph, QGIS-ready road
GeoJSON, quality metadata, and normalized SQLite street/POI rows. Search reads
the SQLite index; routing reads the same graph. Both are network-free at normal
runtime. A selected precise point remains the canonical origin for the
existing Basafe hazard calculation and routing.

OSM supplies road geometry, names, public-interest POIs, and connectivity.
Basafe's local MGB/PHIVOLCS data supplies mapped hazard evidence. The existing
Mamdani FIS supplies combined screening scores. NetworkX A* searches the graph.

## 2. Files changed

Added for the shared OSM/search subsystem:

- `config/osm_search.json`
- `geosafe/search.py`
- `scripts/sync_osm_network.py`
- `tests/test_search.py`
- `docs/osm-search.md`
- this report
- `data/routing/basey_town_proper_walk.graphml`
- `data/routing/basey_town_proper_roads.geojson`
- `data/routing/osm_snapshot_metadata.json`
- `data/routing/hazard_enrichment_metadata.json`

Extended:

- `db/schema.sql`, `data/geosafe.snapshot.db`
- `geosafe/repository.py`, `geosafe/service.py`, `geosafe/api.py`
- `scripts/sync_town_proper_network.py`, `scripts/README.md`
- `web/map.html`, `web/app.js`, `web/styles.css`, `web/service-worker.js`
- `tests/test_frontend_contract.py`
- `config/routing.json`, `vercel.json`
- `README.md`, `docs/api.md`, `docs/architecture.md`, `docs/routing.md`
- `data/routing/README.md`

The previously implemented routing files remain part of the coherent subsystem:
`geosafe/routing.py`, `scripts/enrich_route_hazards.py`,
`scripts/import_routing_data.py`, `scripts/evaluate_routing_cases.py`, and
`tests/test_routing.py`.

## 3. OSM dataset report

| Metric | Value |
| --- | ---: |
| Snapshot version | `osm-2026-08-16-v1` |
| Snapshot date | 2026-08-16 |
| Study area | Mercado, Palaypay, Baybay, Sulod, Loyo, Buscada, and Lawa-an composite |
| Network type | Pedestrian / `walk` |
| Nodes | 120 |
| Directed edges | 354 |
| Inspectable road segments | 178 |
| Named road segments | 123 |
| Unnamed road segments | 55 |
| Named segment percentage | 69.10% |
| Unique searchable street names | 20 |
| Searchable allowlisted POIs | 21 |
| Weakly connected components | 1 |
| Roads without usable geometry | 0 |

Source: © OpenStreetMap contributors. The OSM query used a dissolved geometric
union of the retained source barangay polygons because touching multipart
members are invalid as an undissolved OGC MultiPolygon.

## 4. Search implementation

`searchable_locations` stores OSM source identifiers, type, normalized and
alternate names, representative coordinates, complete GeoJSON geometry,
category/subtype, snapshot date, study-area version, and metadata. Indexed
normalized-name matching ranks exact, prefix, partial, then alternative-name
matches. Municipal scale does not require Elasticsearch or a cloud geocoder.

The map debounces input for 300 ms, groups Streets, Places, Evacuation Centers,
Barangays, and Coordinates, and supports Arrow Up/Down, Enter, and Escape.
Selecting a street highlights its complete stored geometry and asks for a
precise point; it does not score an entire road. POI, center, barangay, map,
and coordinate selections use the existing selected-location state.

## 5. Routing implementation

Shortest mode uses `C_e = D_e`. Lower-Hazard mode uses:

```text
C_e = D_e (1 + lambda H_e)
```

`D_e` is edge length in metres, `H_e` is normalized mapped exposure in `[0,1]`,
and non-negative `lambda` is `risk_factor` from `config/routing.json`. Increasing
hazard can never decrease cost. A* evaluates every reachable active designated
center, rather than choosing by straight-line distance.

Three samples were evaluated per directed edge. Results were 192 edges with
complete mapped-hazard data and 162 unknown edges. Unknown edges are rejected
in hazard-aware mode. Zero persistent assessment records were created.

An ephemeral, non-production integration center was used only to exercise the
real graph: shortest distance 1,095.17 m; lower-hazard distance 1,143.87 m. The
temporary center and database were removed afterward.

## 6. Evacuation-center dataset

Verified designated evacuation-center records available: **No**. Import schema,
template, provenance, status, search integration, destination screening, and
routing logic are implemented. Production routing remains blocked; no center
name or coordinate was fabricated.

## 7. APIs

- `GET /api/v1/location/search?q=...&limit=...&type=...`
- `GET /api/search` compatibility alias
- `GET /api/v1/routing/status`
- `GET /api/v1/evacuation-centers`
- `POST /api/v1/route`

## 8. Frontend workflow

The map accepts an OSM street/POI, designated center when available, barangay,
coordinate pair, current location, or map click. A street result zooms and
highlights the road; the user then chooses a precise point. That point drives
the existing Basafe score and becomes the routing origin. When verified
centers exist, the routing panel compares Shortest and Lower-Hazard routes,
their destination, distance, time, exposure, completeness, and tradeoff.
Changing the point clears prior route state.

## 9. Test results

Commands:

```powershell
python -m unittest discover -s tests -q
node --check web/app.js
python -m compileall -q geosafe scripts tests
git diff --check
vercel build
```

Final result: **130 tests passed, 0 failed, 6 skipped**. JavaScript syntax,
Python compilation, diff integrity, SQLite integrity, and the Vercel preview
build passed. The Vercel function manifest includes the frozen GraphML, road
GeoJSON, OSM metadata, configuration, and sanitized deployment database.

In-app browser checks confirmed real street autocomplete and grouping,
street highlighting followed by an exact map click, complete hazard scoring,
POI search, Arrow/Enter keyboard selection, route-state clearing on location
change, and the truthful missing-center routing state. Mobile layout behavior
remains covered by the frontend responsive contract tests; a separate
verified-center browser route could not be exercised because that dataset is
absent.

## 10. Offline verification

Automated search tests patch network access to fail and still return local
street results. Routing tests patch network access to fail and still calculate
from local GraphML. Runtime search contains no Nominatim/Overpass call, and
runtime routing contains no OSMnx download or external routing API.

## 11. Data limitations

- 55 of 178 OSM road segments are unnamed and cannot be searched by an
  invented street name.
- POIs reflect OSM completeness and the configured public-interest allowlist;
  missing POIs are not invented.
- House numbers are not indexed.
- Street search improves discovery, not hazard resolution or scientific
  precision.
- 162 directed road edges have unknown/incomplete three-hazard evidence and
  are excluded from Lower-Hazard routing under the configured policy.
- Routes do not represent real-time closures, flood depth, damage, traffic,
  crowds, passability, or evacuation orders.

## 12. Research metrics

The route API and CSV evaluator expose test-case/start/destination, shortest and
lower-hazard distance, approximate walking time, distance increase and percent,
mean/maximum mapped exposure, elevated-exposure distance, completeness,
generalized cost, and computation time. The exporter does not generate a
research conclusion.

## 13. Completion matrix

| Requirement | Status | Evidence |
| --- | --- | --- |
| One OSM snapshot for search and routing | Complete | One sync command, GraphML, GeoJSON, SQLite rows, shared version |
| Town-proper scope | Complete | Seven-barangay researcher-defined composite with source provenance |
| Actual pedestrian graph | Complete | 120 nodes, 354 directed edges, one weak component |
| QGIS road export | Complete | `basey_town_proper_roads.geojson` |
| Data-quality report | Complete | `osm_snapshot_metadata.json` and metrics above |
| Street search/ranking | Complete | Local indexed normalization and tests |
| Allowlisted POI search | Complete | 21 synchronized POIs |
| Evacuation-center search | Complete when data exist | Reads verified center table without duplication |
| Barangay/coordinate regression | Complete | Unified API and regression tests |
| Autocomplete and keyboard interaction | Complete | Debounce, grouping, arrows, Enter, Escape |
| Street highlight then exact point | Complete | Leaflet GeoJSON highlight; no street-wide score |
| Shortest and Lower-Hazard A* | Complete | Real-graph smoke check plus synthetic algorithm tests |
| Road hazard enrichment | Complete | 3 samples/edge; 192 complete, 162 unknown |
| Missing-data integrity | Complete | `reject_edge`; missing never becomes zero |
| Verified evacuation-center dataset | Blocked by Missing Dataset | Zero production records; no fabricated destinations |
| Production route generation | Blocked by Missing Dataset | Requires verified designated centers |
| Offline runtime | Complete | Network-blocked search and routing tests |
| Flood-only routing | Not Implemented | Requires scenario-specific validation |
| Earthquake-only routing | Not Implemented | Requires validated liquefaction/shaking combination |
| Browser route-to-real-center workflow | Blocked by Missing Dataset | Search/point/missing-center states testable; real destination absent |
