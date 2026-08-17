# Evacuation-center inventory ingestion — 2026-08-18

## Outcome

The supplied `basey_townpropoer_evacutation_centers.csv` is preserved in the
repository and normalized for SQLite import. The source contains 17 coordinate
rows but nine facility numbers. Nine rows belong to Basey I Central Elementary
School (`EC1` through `EC9`), so they are represented as one facility at the
arithmetic-mean point rather than as nine duplicate destinations.

The researcher confirmed that the photographed inventory was acquired directly
from the Basey Municipal Disaster Risk Reduction and Management Office
(MDRRMO). The normalized dataset version is
`mdrrmo-town-proper-scoped-extract-2026-08-18-v1` and is loaded as an
operator-declared official source. Unrelated centers visible in the photograph
were intentionally excluded because they fall outside the seven-barangay study
scope. The original photograph, publication date, capacity, operating-status
criteria, and activation conditions are not yet archived and are not inferred.

## Validation results

| Check | Result |
| --- | --- |
| Source SHA-256 | `7e9a25e779db780452d1c051b788aa0f6b1c866c6e48cacf718d3edd69f7e393` |
| Source rows | 17 |
| Normalized facilities | 9 |
| Coordinate conversion | DMS to WGS 84 decimal degrees |
| Inside seven-barangay study area | 9 of 9 |
| Road-graph component | 9 of 9 in the same connected component |
| Nearest road-node distance | 5.4–48.0 metres |
| Duplicate destination prevention | Basey I Central School's nine site points consolidated |
| Issuing authority | Basey MDRRMO, confirmed by researcher |
| Source medium | Photograph transcribed to CSV |
| Publication date/image archived | No |
| Capacity available | No |

The loaded PSA barangay polygons place the normalized facilities in either
Loyo (Pob.) or Mercado (Pob.). Three source labels require issuer review:

- the row named `Evacuation Facility, Brgy. Mercado` falls in Loyo (Pob.);
- the rows naming Basey District Hospital and the Sitio Bangon Community
  Evacuation Center as Canmanila fall in Loyo (Pob.); and
- the nine Basey I Central School points cross the Buscada/Loyo polygon line,
  while their representative point falls in Loyo.

The normalized `barangay` field uses the point-in-polygon result and preserves
the original labels in the immutable source CSV. These differences may reflect
a site crossing a boundary, coordinate generalization, an older boundary, or a
source-label error; the application does not choose among those explanations.

## Hazard and routing readiness

All nine facilities were screened against the local hazard database without
creating assessment-history records:

- ground shaking is available at all nine;
- liquefaction intersects three of nine; and
- flood intersects none of nine.

Consequently, all nine destination screenings are currently incomplete. This
does not turn missing flood/liquefaction evidence into a low value. The road
graph itself has 192 hazard-complete directed edges and 162 unknown edges; the
Lower-Hazard mode continues to reject unknown edges.

Center search and public shortest-route generation are enabled for all nine
representative points. A real-graph check from the northern study-area road
network selected St. Michael Parish Church at approximately 1,119.65 metres.
Lower-Hazard routing remained unavailable for that test origin because no
complete-hazard path reached a center under the existing `reject_edge` policy;
the application did not silently fall back or treat missing data as low.

## Reproduction

```powershell
python scripts/normalize_evacuation_centers.py `
  data/routing/source/basey_town_proper_evacuation_centers_source.csv

python scripts/import_routing_data.py centers `
  data/routing/basey_town_proper_evacuation_centers.csv `
  --db data/geosafe.db `
  --version mdrrmo-town-proper-scoped-extract-2026-08-18-v1 `
  --source-name "Municipal Disaster Risk Reduction and Management Office of Basey (MDRRMO)" `
  --data-classification official `
  --replace

python scripts/enrich_route_hazards.py --db data/geosafe.db --centers-only
```

The operator-declared authority is retained in the normalized metadata. Archive
the original photograph when it becomes available so future reviewers can
verify the transcription, excluded out-of-scope rows, and any document date.
