# ULAP Source-Reference and JSON Audit

## 1. Audit identity and evidentiary boundary

This audit was performed on 2026-07-23 against the user-supplied file:

```text
C:\Users\Austin Jeru\Downloads\basey-barangay-boundary-final.json
```

| Item | Observed value |
| --- | --- |
| SHA-256 | `027b6dbaacdee9fd83e1ce680e2015916ecd44d1ede2440571a86358d0b5a581` |
| File size | 234,033 bytes |
| Root type | GeoJSON `FeatureCollection` |
| Root keys | `type`, `features` |
| Feature count | 58 |
| Geometry types | 55 `Polygon`; 3 `MultiPolygon` |
| Declared CRS | None |
| Embedded HTTP/HTTPS URLs | None |
| ArcGIS service/layer identifiers | None |
| Hazard fields or classifications | None |
| Issuing agency, license, or official-status declaration | None |

The file is a supplied Basey barangay-boundary reference. It is not an API
manifest: it contains no service URL, layer ID, query endpoint, authentication
requirement, ArcGIS metadata, flood field, liquefaction field, or
ground-shaking source.

The ULAP service URLs in this project were supplied separately in the project
integration brief and were then checked independently against live ArcGIS REST
metadata. They were not discovered in this JSON. This distinction is retained
in `config/ulap-services.generated.json`.

The file must not be described as official merely because its filename contains
`final`. Its provenance and authorization remain unconfirmed.

## 2. Geometry and CRS audit

All 7,509 coordinate positions use projected-looking values. Their raw
coordinate envelope is:

```text
xmin 497286.29
ymin 1239443.00333612
xmax 533300.03055245
ymax 1280093.76597996
```

Those values are not valid RFC 7946 longitude/latitude coordinates. Every
observed `x` is outside the longitude range and every observed `y` is outside
the latitude range.

One feature has a `path` property containing the text
`MultiPolygon?crs=EPSG:3125&field=...`; the other 57 `path` values are blank.
The coordinate pattern, Basey location, and this isolated property make
`EPSG:3125` (PRS92 / Philippines zone 5) a high-confidence inference. It is
still not a declared CRS. The importer must require issuer confirmation or an
operator-supplied, documented `--source-crs EPSG:3125`; it must not silently
adopt the inference.

Importing the file without a confirmed source CRS is unsafe. Treating it as
GeoJSON-default `EPSG:4326` correctly fails coordinate-range validation.

As a diagnostic only, PyProj interpretation as EPSG:3125 transformed sample
coordinate `(507354.79, 1247401.673)` to approximately
`(125.068795687, 11.279742050)` and produced this WGS 84 envelope:

```text
xmin 124.9765745
ymin 11.2077799
xmax 125.3065567
ymax 11.5752297
```

All 58 interpreted geometries passed Shapely structural/topological validity
checks. Plausible placement and valid topology strengthen the CRS inference,
but they do not establish provenance, currency, or official authority.

## 3. Attribute completeness

The union of property keys is:

```text
AREA, BARANGAY, BRGY_INDEX, color_id, fid, id, IN_POB, layer,
NO., OUT_POB, path, POB, Population
```

| Field | Blank or null features | Audit note |
| --- | ---: | --- |
| `BARANGAY` | 6 | 52 populated values; all 52 are unique |
| `BRGY_INDEX` | 7 | Cannot be treated as a complete identifier |
| `fid` | 7 | Cannot be treated as a complete identifier |
| `NO.` | 7 | Cannot be treated as a complete identifier |
| `id` | 58 | Entirely empty |
| `Population` | 57 | Not usable as a barangay population source |
| `path` | 57 | The one populated value is a processing clue, not provenance |
| `layer` | 57 | One feature is labelled `Difference` |
| `AREA` | 0 | Unit, calculation method, and source are not declared |

Specific anomalies include:

- two named polygons, `BASIAO` and `PANUNUBULON`, lack `fid`,
  `BRGY_INDEX`, and `NO.`;
- one unnamed `MultiPolygon` has `fid` 29, `BRGY_INDEX` 0031,
  `OUT_POB` 0031, `NO.` 31, and `layer` `Difference`;
- five additional polygons have no barangay name or reliable identifier; and
- punctuation, spelling, capitalization, and parenthetical `Pob.` conventions
  differ from the live PSA barangay service, so names are not safe join keys.

On 2026-07-23, the live PSA barangay query for Basey, Samar returned 51
features, while this file has 52 populated barangay names and six unnamed
features. The count difference does not by itself prove that either source is
wrong, but it blocks automatic replacement or joining. Reconciliation should
use confirmed PSGC codes and issuer documentation, followed by a geometry
comparison.

Using the inferred EPSG:3125 solely for comparison, the supplied feature union
and live PSA Basey municipal geometry showed:

| Comparison measure | Result |
| --- | ---: |
| Supplied union area in geographic-coordinate square degrees | 0.0547913 |
| Live PSA municipal area in geographic-coordinate square degrees | 0.0493632 |
| Share of live PSA geometry overlapped by supplied union | 98.57% |
| Share of supplied union overlapped by live PSA geometry | 88.81% |
| Jaccard overlap | 87.68% |

Square degrees are used here only as a reproducible overlay diagnostic, not a
land-area measurement. The asymmetric overlap is material and reinforces the
need to reconcile boundary version, authority, unnamed pieces, and barangay
identifiers before operational use.

## 4. Live service audit

The checks below used independent HTTPS requests with `f=pjson` against both
the service root and layer 0 on 2026-07-23. All four service roots returned
ArcGIS version 11.0, advertised `Map,Query,Data`, and listed layer 0. Layer
metadata was then checked for geometry, spatial reference, fields, domains,
record limits, and attribution.

| Dataset | Agency | Service URL | Layer | Geometry / CRS | Classification field and live domain | Authentication observed | Verification status |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| Flood | Mines and Geosciences Bureau | `https://ulap-hazards.georisk.gov.ph/arcgis/rest/services/MGBPublic/Flood/MapServer` | `0` | Polygon / EPSG:4326 | `fscode`: `01` Low, `02` Moderate, `03` High, `04` Very High Susceptibility | No token required for the tested metadata and query requests | Verified live 2026-07-23 |
| Liquefaction | Philippine Institute of Volcanology and Seismology | `https://ulap-hazards.georisk.gov.ph/arcgis/rest/services/PHIVOLCSPublic/Liquefaction/MapServer` | `0` | Polygon / EPSG:4326 | `lccode`: `01` Generally Susceptible; `02` Low, `03` Moderate, `04` High Potential; `05` Least, `06` Moderately, `07` Highly Susceptible | No token required for the tested metadata and query requests | Verified live 2026-07-23 |
| Municipal boundary | Philippine Statistics Authority | `https://ulap-nga.georisk.gov.ph/arcgis/rest/services/PSA/Municipal/MapServer` | `0` | Polygon / EPSG:4326 | Not a hazard classification; identity fields include `city_name`, `city_code`, `prov_name`, `prov_code`, and `psgc_10d` | No token required for the tested metadata and query requests | Verified live 2026-07-23 |
| Barangay boundary | Philippine Statistics Authority | `https://ulap-nga.georisk.gov.ph/arcgis/rest/services/PSA/BarangayPopMF/MapServer` | `0` | Polygon / EPSG:4326 | Not a hazard classification; identity fields include `brgy_name`, `brgy_code`, `city_name`, `city_code`, and `psgc_10d` | No token required for the tested metadata and query requests | Verified live 2026-07-23 |
| Ground shaking | Source not established | None supplied or found | None | Unknown | No verified ground-shaking, MMI, PEIS, PGA, PGV, or seismic-intensity field/domain | Unknown | `unavailable`; blocks a complete score |

The flood layer advertised a maximum record count of 2,000. Its attribution
states that the Mines and Geosciences Bureau is the source as of July 2018.
The liquefaction layer also advertised a maximum record count of 2,000 and asks
users to acknowledge PHIVOLCS, as of July 2018. The municipal and barangay
layers advertised maximum record counts of 20,000 and 50,000 respectively.

“Verified” here means that the stated endpoint and observed schema responded
successfully on the stated date. It is not a claim about data fitness,
completeness, currentness, license, authorization for republication, or future
availability. Runtime validation remains mandatory.

## 5. Live Basey observations

The live municipal filter:

```text
city_name='Basey' AND prov_name='Samar'
```

returned one municipal feature and this EPSG:4326 extent:

```text
xmin 124.97644983900011
ymin 11.25408277400004
xmax 125.30911645700007
ymax 11.564051392000067
```

The corresponding live barangay filter returned 51 features.

A point query at longitude `125.068`, latitude `11.282` returned:

- one municipal feature: Basey, Samar, PSGC `0806002000`;
- one barangay feature: Buscada (Pob.), PSGC `0806002035`;
- zero flood features; and
- zero liquefaction features.

Zero hazard features at that point are recorded as `no_intersection` or another
explicit unavailable state after coverage evaluation. They are never
interpreted as Low susceptibility.

A separate coverage control point at longitude `125.0336740411251`, latitude
`11.290798389750039` returned one flood feature with raw `fscode = 03` and one
liquefaction feature with raw `lccode = 01`. The opt-in live integration suite
used this point and passed all five tests on 2026-07-23. These observations
demonstrate both an available point and a nearby no-intersection point; they do
not establish complete municipal coverage.

As a separate coverage diagnostic, the rectangular Basey municipal extent
intersected 329 flood features and four liquefaction features. This proves that
both services have some features intersecting the bounding rectangle; it does
not prove complete coverage inside Basey, because an extent is not the
municipal polygon and point coverage can contain gaps.

## 6. Import decision for the supplied file

The supplied JSON is retained as an audited reference but is not ready for
authoritative import. Release use requires:

1. issuer and official-status confirmation;
2. license/use terms and source date;
3. explicit confirmation of the source CRS, with EPSG:3125 currently only an
   inference;
4. reconciliation of 58 geometries, 52 names, six unnamed features, and the
   live PSA count of 51;
5. stable PSGC-based identifiers;
6. topology validation after reprojection; and
7. a recorded comparison against the selected authoritative Basey boundary
   source.

Until those conditions are met, the file must be labelled
`supplied_reference_unverified`, not `official`.
