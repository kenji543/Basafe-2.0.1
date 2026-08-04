# Known ULAP and Deployment Data Gaps

## 1. Release interpretation

The application can demonstrate live-source retrieval and explain incomplete
evidence. It cannot currently produce a defensible complete live three-hazard
screening result because a verified ground-shaking source is missing.

The gaps below are data and validation dependencies, not reasons to add an
administrative portal, accounts, roles, approval screens, or browser upload
workflows.

## 2. Blocking gaps

| Gap | Current evidence | Required resolution | Effect until resolved |
| --- | --- | --- | --- |
| Ground-shaking source | No ground-shaking, MMI, PEIS, PGA, PGV, or seismic-intensity endpoint was supplied or verified | Obtain an authorized endpoint/layer; verify field, unit/domain, agency, date, coverage, and attribution; approve a model transformation | `ground_shaking = unavailable`; every live three-hazard assessment is `incomplete`; score is null |
| Ground-shaking transformation | Model source/field/mapping are deliberately null/empty | Qualified PHIVOLCS/seismology and model reviewers approve the source-to-index mapping and membership implications | No substitute or assumed value is allowed |
| Fuzzy-model domain validation | Version `0.4.0-demo` mappings, functions, rules, weights, thresholds, and recommendations are capstone assumptions | Documented review and approval by qualified MGB, PHIVOLCS, geotechnical, DRRM, and planning specialists | Results remain demonstration screening only, even after all source values are available |

Active Fault, distance to a fault, liquefaction, epicenters, generic seismic
hazard, an invented intensity, zero, and the last successful result are
explicitly prohibited substitutes.

## 3. Supplied boundary gaps

The file `basey-barangay-boundary-final.json` has:

- no declared CRS;
- no issuing agency, license, source date, version, or authority statement;
- 58 features but only 52 populated barangay names;
- six unnamed features and seven features lacking several candidate
  identifiers;
- one property-level EPSG:3125 clue, which is not a GeoJSON CRS declaration;
- no reliable PSGC join field; and
- a different feature count and material boundary difference from the live PSA
  service.

EPSG:3125 is a high-confidence spatial inference, supported by a plausible
WGS 84 transformation and geometry overlay, but must be confirmed by the
issuer. All 58 interpreted geometries are topologically valid; that does not
resolve provenance or version differences.

The live PSA query returned 51 Basey barangays. Before the supplied file can be
used operationally, the project needs issuer confirmation, CRS confirmation,
PSGC reconciliation, a decision on unnamed/difference polygons, source date
and version, license/use terms, and a documented authority preference.

## 4. Hazard coverage gaps

On 2026-07-23:

- the rectangular live Basey municipal extent intersected 329 flood features
  and four liquefaction features;
- longitude `125.068`, latitude `11.282` was inside Basey and Buscada (Pob.);
  that point returned zero flood and zero liquefaction features; and
- longitude `125.0336740411251`, latitude `11.290798389750039` separately
  returned flood `fscode = 03` and liquefaction `lccode = 01`.

These observations show that service availability, municipal-envelope
intersection, and point availability are different. The current audit has not
established:

- complete flood coverage of the municipal polygon;
- complete liquefaction coverage of the municipal polygon;
- whether every apparent gap means intentionally unmapped area, true absence
  of a classified polygon, scale/generalization, or another source limitation;
- the preferred response when overlapping polygons carry conflicting classes;
  or
- fitness of the July 2018-attributed layers for a current planning decision.

Until a coverage study is completed, zero features must be reported as
`no_intersection` or `outside_coverage` when that distinction can be
established. It must never be Low or Safe.

## 5. Source date, terms, and authority gaps

Live metadata identified MGB/PHIVOLCS attribution as of July 2018. Runtime
reachability does not establish:

- whether a newer authorized dataset exists;
- the exact acquisition/mapping date for each polygon;
- suitability at parcel or site-investigation scale;
- completeness for Basey;
- permission to cache, redistribute, or embed full geometries; or
- whether additional agency/LGU attribution language is required.

Deployment owners must obtain and retain the applicable data-use terms and
document any caching, report reproduction, and retention constraints.

## 6. Historical-incident gap

No authorized historical-incident dataset is configured. Synthetic repository
records are not operational evidence.

Required work:

1. identify the municipal/provincial/national custodian and authorized
   extract;
2. define event, date, spatial, duplicate, and verification semantics;
3. document temporal and reporting completeness;
4. import through the CLI with provenance and quality notices; and
5. state that no matching record does not prove no incident occurred.

Incident context remains non-numeric in model `0.4.0-demo`.

## 7. CLUP gap

No adopted, authorized Basey CLUP reference dataset is configured. Synthetic
repository references are not operational evidence.

Required work:

1. identify the adopted edition and approval status;
2. obtain authorized plan text/maps and use terms;
3. define stable section/map/zone references;
4. document spatial precision and whether a match is point, barangay, or
   municipality context; and
5. import with source date, edition, limitations, and provenance.

CLUP context remains non-numeric in model `0.4.0-demo`.

## 8. Runtime reliability gaps

The four configured ArcGIS services responded without a token during the
2026-07-23 checks. That does not guarantee future anonymous access or uptime.
Runtime must still handle:

- DNS/TLS/network failure;
- timeouts and rate limiting;
- HTTP and ArcGIS errors;
- token requirements and ArcGIS codes 498/499;
- layer removal or ID changes;
- field/domain/schema changes;
- malformed or partial JSON;
- pagination and transfer limits; and
- expired or stale cache entries.

An expired value must not be reused indefinitely. Any explicitly allowed stale
fallback must retain its original retrieval time, expiry, and prominent stale
label. No such fallback may fabricate a missing ground-shaking value.

## 9. Testing and acceptance gaps

Isolated unit tests may use sanitized fixtures. They do not prove that a live
service is currently working. Live integration tests are opt-in through:

```text
LIVE_ULAP_TESTS=true
```

All five opt-in live tests passed on 2026-07-23. The ordinary suite ran 78
tests: 73 passed and those five network tests were skipped by default. These
dated results establish one observed service state, not future uptime or
complete coverage.

Before deployment acceptance, record successful results for:

- service and layer metadata validation;
- the Basey municipal/barangay query;
- representative flood and liquefaction point queries, including a
  zero-feature point;
- a ground-shaking query only after an authorized endpoint exists;
- timeouts, ArcGIS error objects, unknown codes, changed domains, and multiple
  intersections;
- backend normalized responses and incomplete-score blocking; and
- source/quality/disclaimer parity among interface, saved assessment, preview,
  and PDF.

The verification date and endpoint metadata must accompany every claimed live
test result.

## 10. Non-gaps by design

The following are intentionally excluded rather than missing:

- users, registration, multiple accounts, roles, and permissions;
- administrator/staff/office-specific interfaces;
- account or dataset approval workflows;
- browser-based data/model management;
- user activity monitoring and audit-log management; and
- an administrator-only fuzzy-model editor.

Data preparation, source changes, and model revisions remain version-controlled
development/deployment processes.
