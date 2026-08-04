# GeoSafe-FIS Data-Source Register

## 1. Status vocabulary

GeoSafe-FIS keeps source reachability separate from authority and point
availability:

| Dimension | Examples | Meaning |
| --- | --- | --- |
| Endpoint verification | `verified`, `verified_with_changed_metadata`, `authentication_required`, `inaccessible` | Whether the configured ArcGIS endpoint and expected schema can be reached now |
| Provenance/authority | `official`, `supplied_reference_unverified`, `demonstration` | Whether issuing organization, authorization, and source metadata support the designation |
| Point availability | `available`, `no_intersection`, `outside_coverage`, `unavailable` | Whether the source supplies a usable value at the selected coordinate |
| Model usability | `valid`, `changed_schema`, `unknown_code`, `incomplete` | Whether the evidence can enter the configured model |

A verified endpoint is not automatically complete at every Basey point.
Likewise, a user-supplied boundary does not become official because it appears
geographically plausible.

## 2. Current source register

Observed metadata and query status are dated 2026-07-23.

| Required source | Configured source | Agency / attribution | Verification | Operational limitation |
| --- | --- | --- | --- | --- |
| Basey municipal boundary | `PSA/Municipal/MapServer/0` through GeoRisk Philippines ULAP | Philippine Statistics Authority | Live service/layer and Basey filter verified | Confirm republication/use terms and retain runtime metadata |
| Basey barangays | `PSA/BarangayPopMF/MapServer/0` through GeoRisk Philippines ULAP | Philippine Statistics Authority | Live service/layer verified; 51 Basey features returned | Reconcile with the supplied 58-feature file; use PSGC identifiers |
| Flood | `MGBPublic/Flood/MapServer/0` | Mines and Geosciences Bureau; layer text identifies MGB as source as of July 2018 | Live service/layer, `fscode`, domain, and query behavior verified | Coverage is not continuous at every tested point; age/fitness must be stated |
| Liquefaction | `PHIVOLCSPublic/Liquefaction/MapServer/0` | Philippine Institute of Volcanology and Seismology; layer requests PHIVOLCS acknowledgement as of July 2018 | Live service/layer, `lccode`, domain, and query behavior verified | Mixed classification families and point gaps require careful handling |
| Ground shaking | None | Source not established | Not configured / unavailable | Required dependency; blocks a complete score |
| Historical incidents | None authorized/configured | To be established by deployment data owner | Not configured | Display only authorized records with date, location, provenance, and completeness limits |
| CLUP references | None authorized/configured | To be established from the adopted Basey CLUP | Not configured | Requires edition, section/map reference, adoption status, spatial meaning, and use terms |
| Fuzzy model | `config/fuzzy_model.json`, version `0.4.0-demo` | GeoSafe-FIS demonstration configuration | Software-readable and version controlled | All transformations, memberships, rules, weights, and thresholds need expert validation |

The runtime source registry is
`config/ulap-services.generated.json`. Deployment-data requirements and the
supplied-file audit summary are in `config/data_sources.json`.

## 3. Verified ArcGIS endpoints

### 3.1 Flood

```text
Service:
https://ulap-hazards.georisk.gov.ph/arcgis/rest/services/MGBPublic/Flood/MapServer

Layer:
https://ulap-hazards.georisk.gov.ph/arcgis/rest/services/MGBPublic/Flood/MapServer/0
```

- layer name: `Flood`;
- geometry: polygon;
- spatial reference: EPSG:4326;
- classification: `fscode`;
- live domain: `01` Low, `02` Moderate, `03` High, `04` Very High
  Susceptibility;
- maximum record count: 2,000; and
- tested metadata/query authentication: no token required.

### 3.2 Liquefaction

```text
Service:
https://ulap-hazards.georisk.gov.ph/arcgis/rest/services/PHIVOLCSPublic/Liquefaction/MapServer

Layer:
https://ulap-hazards.georisk.gov.ph/arcgis/rest/services/PHIVOLCSPublic/Liquefaction/MapServer/0
```

- layer name: `Liquefaction`;
- geometry: polygon;
- spatial reference: EPSG:4326;
- classification: `lccode`;
- live domain: codes `01` through `07`, documented in
  [ulap-field-mappings.md](ulap-field-mappings.md);
- maximum record count: 2,000; and
- tested metadata/query authentication: no token required.

### 3.3 Municipal and barangay boundaries

```text
https://ulap-nga.georisk.gov.ph/arcgis/rest/services/PSA/Municipal/MapServer/0
https://ulap-nga.georisk.gov.ph/arcgis/rest/services/PSA/BarangayPopMF/MapServer/0
```

Both are EPSG:4326 polygon layers. The live filter
`city_name='Basey' AND prov_name='Samar'` returned one municipality and 51
barangays. The municipal record used PSGC `0806002000`.

All configured ArcGIS requests are made by the GeoSafe-FIS backend. Service
tokens, if later required, are server-side environment values and must not
appear in browser code, logs, saved assessment source URLs, or reports.

## 4. Supplied boundary reference

The supplied file is:

```text
basey-barangay-boundary-final.json
SHA-256:
027b6dbaacdee9fd83e1ce680e2015916ecd44d1ede2440571a86358d0b5a581
```

It contains 58 barangay-like polygons/multipolygons, including 52 populated
barangay names and six blank names. It contains no agency, license, source
date, declared CRS, service URL, or official-status declaration. EPSG:3125 is
a strong but unconfirmed inference. Its geometry overlaps most of the live PSA
Basey municipality but differs materially at the edges and in feature count.

Status:

```text
supplied_reference_unverified
operational_use: false
```

See [ulap-json-audit.md](ulap-json-audit.md) for the complete audit.

## 5. Point-level evidence

Every hazard result must carry:

- status and explicit reason when unavailable;
- source agency and layer URL;
- layer ID, classification field, raw code, and unchanged official label;
- complete raw attributes and decoded attributes;
- spatial reference;
- source/map/publication dates when genuinely available;
- retrieval timestamp;
- cache retrieval/expiration state;
- attribution; and
- schema, coverage, overlap, unknown-code, and quality warnings.

A live check at longitude `125.068`, latitude `11.282` identified Basey and
Buscada (Pob.) but returned no flood or liquefaction polygon at that point.
That observation is evidence of point-level non-intersection, not Low
susceptibility. Broader envelope checks found some flood and liquefaction
features intersecting Basey's rectangular extent, so neither a point gap nor
an envelope hit establishes complete municipal coverage.

At a separate control point, longitude `125.0336740411251`, latitude
`11.290798389750039`, the live services returned one flood feature
(`fscode = 03`) and one liquefaction feature (`lccode = 01`). Both the
available and no-intersection control points should remain in deployment
regression checks.

## 6. Historical incidents

No authorized historical-incident dataset is currently configured. Repository
files labelled demonstration or synthetic must not be displayed in a live
ULAP assessment or report as official evidence.

An operational incident import must record, at minimum:

- record identifier and incident type;
- event date/time and date precision;
- coordinates, geometry, barangay, and spatial precision;
- source organization, document/reference, and retrieval/import date;
- verification status and completeness limitations;
- whether the record is a point, nearby, barangay-wide, or broader context;
  and
- authorization/use restrictions.

Absence of an incident record means “no available record in the configured
source,” not “no incident occurred.”

## 7. CLUP references

No adopted CLUP dataset/reference set is currently configured. Operational
references must identify:

- CLUP edition and adoption/approval status;
- section, policy, map sheet, zone, or document reference;
- source/custodian and use terms;
- effective/publication date;
- geometry or stated spatial relationship;
- whether the reference is point-covering, barangay-wide, or
  municipality-wide; and
- interpretation and currency limitations.

CLUP context is explanatory planning evidence, not a numeric fuzzy input in
model `0.4.0-demo`.

## 8. Demonstration-data rule

Synthetic files may remain as isolated fixtures for automated tests. They must
never be returned by production/development live-source routes, shown in a
demonstration as though official, used to fill a missing ULAP result, or
included in a report without a prominent demonstration label.

No source status may be upgraded by filename, URL hostname, spatial overlap, or
developer assumption alone.
