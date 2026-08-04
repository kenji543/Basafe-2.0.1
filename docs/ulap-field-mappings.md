# ULAP Field and Domain Mappings

## 1. Mapping policy

These mappings describe the ArcGIS schemas observed live on 2026-07-23 and the
corresponding GeoSafe-FIS source objects. They are runtime expectations, not a
license to trust a stale schema.

For every request, the backend must:

1. validate the current layer metadata;
2. locate fields case-insensitively by their configured names;
3. obtain coded-value labels from the live field domain, using the renderer
   only as a documented fallback;
4. retain the original field name, code, complete raw attribute object, layer
   URL, retrieval time, and attribution;
5. compare the live domain with the version-controlled expectation; and
6. reject a missing field or unknown code as missing model evidence rather
   than inventing a label or number.

Official codes and labels are immutable source evidence. GeoSafe-FIS model
indices, memberships, and the combined screening score are separate derived
values. See [fuzzy-data-transformations.md](fuzzy-data-transformations.md).

## 2. Flood

| Item | Mapping |
| --- | --- |
| Service | `MGBPublic/Flood/MapServer` |
| Layer | `0` (`Flood`) |
| Layer URL | `https://ulap-hazards.georisk.gov.ph/arcgis/rest/services/MGBPublic/Flood/MapServer/0` |
| Agency | Mines and Geosciences Bureau |
| Geometry / CRS | `esriGeometryPolygon` / EPSG:4326 |
| Classification field | `fscode` |
| Supporting theme field | `gthcode` |
| Other preserved fields when present | `created_date`, `last_edited_date`, `orig_fid`, `globalid` |

The live `fscode` coded-value domain was:

| Raw code | Official label |
| --- | --- |
| `01` | Low Susceptibility |
| `02` | Moderate Susceptibility |
| `03` | High Susceptibility |
| `04` | Very High Susceptibility |

Normalized source response mapping:

| GeoSafe-FIS field | ArcGIS/source value |
| --- | --- |
| `hazard` | constant `flood` |
| `status` | request/coverage result, for example `available` |
| `agency` | registry agency plus live attribution |
| `service` | configured service key/URL |
| `layer_id` | `0` |
| `classification_field` | live-cased field matching `fscode` |
| `raw_code` | unmodified `fscode` value |
| `official_label` | live domain label for the exact raw code |
| `raw_attributes` | complete returned attributes |
| `decoded_attributes` | copy with known coded fields decoded |
| `source_url` | layer/query source without a token |
| `spatial_reference` | validated layer/query CRS |
| `retrieved_at` | UTC retrieval timestamp |
| `data_date` | source date only when supported by metadata/attributes |
| `attribution` | live copyright/source text and configured agency |
| `warnings` | schema, domain, overlap, coverage, cache, or quality notices |

`gthcode` is preserved as source context. It is not substituted for `fscode`
and is not independently converted into a fuzzy input.

## 3. Liquefaction

| Item | Mapping |
| --- | --- |
| Service | `PHIVOLCSPublic/Liquefaction/MapServer` |
| Layer | `0` (`Liquefaction`) |
| Layer URL | `https://ulap-hazards.georisk.gov.ph/arcgis/rest/services/PHIVOLCSPublic/Liquefaction/MapServer/0` |
| Agency | Philippine Institute of Volcanology and Seismology |
| Geometry / CRS | `esriGeometryPolygon` / EPSG:4326 |
| Classification field | `lccode` |
| Other preserved fields when present | `liqcode`, `mappers`, `project`, `province`, `otherinfo`, `datemapped`, `publishdate`, `globalid`, `createdate`, `modifydate` |

The live `lccode` coded-value domain was:

| Raw code | Official label | Classification family note |
| --- | --- | --- |
| `01` | Generally Susceptible | Broad/general category |
| `02` | Low Potential | Potential family |
| `03` | Moderate Potential | Potential family |
| `04` | High Potential | Potential family |
| `05` | Least Susceptible | Susceptibility family |
| `06` | Moderately Susceptible | Susceptibility family |
| `07` | Highly Susceptible | Susceptibility family |

The code numbers are identifiers, not a scientifically valid ordinal scale.
In particular, `01` must not be treated as lower than `02`, and the “Potential”
and “Susceptible” families must not be collapsed by number. Each exact code has
an explicit, independently reviewable demonstration transformation in the
fuzzy configuration.

The normalized response uses the same source-object fields described for
flood, with `hazard = liquefaction`, `classification_field = lccode`, and the
PHIVOLCS attribution. Mapping/publication attributes are retained as returned.
An integer date-like field must not be reformatted into a calendar date unless
its ArcGIS field definition and provider semantics support that conversion.

## 4. Municipal boundary

| GeoSafe-FIS identity | Live ArcGIS field |
| --- | --- |
| Municipality | `city_name` |
| Municipality code | `city_code` |
| Province | `prov_name` |
| Province code | `prov_code` |
| Region | `reg_name` |
| Region code | `reg_code` |
| PSGC | `psgc_10d` |

Configured layer:

```text
https://ulap-nga.georisk.gov.ph/arcgis/rest/services/PSA/Municipal/MapServer/0
```

The verified Basey filter is:

```sql
city_name='Basey' AND prov_name='Samar'
```

It returned one feature on 2026-07-23. Text comparison should be
case-insensitive at validation time, while the returned official spelling is
preserved for display.

## 5. Barangay boundary

| GeoSafe-FIS identity | Live ArcGIS field |
| --- | --- |
| Barangay | `brgy_name` |
| Barangay code | `brgy_code` |
| Municipality | `city_name` |
| Municipality code | `city_code` |
| Province | `prov_name` |
| Province code | `prov_code` |
| Region | `reg_name` |
| Region code | `reg_code` |
| PSGC | `psgc_10d` |

Configured layer:

```text
https://ulap-nga.georisk.gov.ph/arcgis/rest/services/PSA/BarangayPopMF/MapServer/0
```

The same Basey/Samar filter returned 51 features on 2026-07-23. `psgc_10d` or
the corresponding official code is the preferred join identifier. Display
names alone are unsafe because punctuation, hyphenation, spelling, casing, and
`(Pob.)` qualifiers vary among sources.

## 6. Ground shaking

There is no field mapping because no authorized and verified ground-shaking
endpoint was supplied or found. A future mapping cannot be enabled until its
service and layer metadata establish all of the following:

- the field truly measures or classifies ground shaking;
- unit or classification system, such as documented PEIS/MMI or ground-motion
  measure;
- field name and coded domain or numeric unit;
- source agency, dataset date, coverage, resolution, and attribution; and
- a domain-expert-approved transformation into the model input scale.

Active Fault, distance to a fault, liquefaction, earthquake epicenters, and
generic seismic-hazard layers are not substitutes.

## 7. Schema-change rules

| Observation | Required behavior |
| --- | --- |
| Expected field differs only in case | Use the live field spelling and record the observation |
| Expected field is absent | `missing_classification_field`; do not assess that hazard |
| Live domain adds/removes/renames codes | `verified_with_changed_metadata` at validation; unknown point code remains unavailable until configured |
| Point code has no live/configured label | Preserve the raw code, emit an unknown-code warning, and block the complete assessment |
| Geometry type or CRS changes | `changed_schema`; validate query/transform behavior before reuse |
| Multiple polygons intersect | Preserve feature count and all evidence needed for diagnosis; never silently select a lower class |
| Zero polygons intersect | `no_intersection` or `outside_coverage` after coverage evaluation; never Low |
