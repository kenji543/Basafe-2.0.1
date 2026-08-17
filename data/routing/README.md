# Basey town-proper routing data

Runtime routing reads only frozen local files and SQLite records. It never
downloads road data while a user is requesting a route.

The study boundary is present in SQLite as a researcher-defined composite of
the loaded official PSA barangay polygons for Mercado, Palaypay, Baybay, Sulod,
Loyo, Buscada, and Lawa-an. It can be rebuilt deterministically with
`scripts/build_town_proper_boundary.py --replace`. The grouping itself is not
labelled official.

The frozen OSM walking graph, QGIS-ready road GeoJSON, snapshot quality report,
and local street/POI index are generated together by `scripts/sync_osm_network.py`.

The supplied 2026-08-18 CSV has been preserved and normalized into nine
facility-level records. Its 17 source rows include nine point labels for Basey
I Central Elementary School, so those rows are retained as one facility with a
representative centroid. All nine normalized facilities fall inside the
seven-barangay study area and snap to the connected local road graph within
48 metres.

The researcher confirmed on 2026-08-18 that the source photograph was acquired
directly from the Basey MDRRMO. The nine in-scope facilities are therefore
loaded as an operator-declared official MDRRMO scoped extract and are enabled as
route destinations. The photograph also showed unrelated out-of-scope centers,
which were intentionally excluded. The source image, publication date,
capacity, and activation conditions remain documentation gaps and must not be
inferred.

The templates in this directory define the expected interchange format. An
`official` import records the operator's source declaration; it does not replace
archiving the issuing document or confirming current activation during an
emergency.

Use `scripts/normalize_evacuation_centers.py` to reproduce the DMS conversion,
facility grouping, town-proper validation, and PSA barangay matching. Use
`scripts/import_routing_data.py` if an independently issued study area is later
supplied, and for the centers. Use `scripts/sync_town_proper_network.py`
as an explicit operator-only OSMnx preprocessing command after the derived
boundary definition is accepted for the research study. Use
`scripts/enrich_route_hazards.py` to attach local BaSafe hazard/FIS evidence to
the frozen graph before deployment; `--centers-only` screens newly imported
centers without recalculating all road edges.

Optional facility photographs can be added to the normalized center CSV with
`photo_url`, `photo_alt`, `photo_source`, and `photo_source_url`. Use a stable,
permission-cleared HTTPS URL or a root-relative file placed under `web/`.
Leave these fields blank when a verified photograph is unavailable; the public
map identifies that absence instead of substituting unrelated imagery.
