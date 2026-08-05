# ULAP-to-Fuzzy Data Transformations

## 1. Separation of source evidence and model output

GeoSafe-FIS model `0.5.2-demo` keeps four layers of meaning separate:

```text
official ArcGIS code and label
        â†“ exact, versioned demonstration lookup
GeoSafe-FIS normalized input (0â€“100)
        â†“ configured membership functions
low / moderate / high membership degrees (0â€“1)
        â†“ configured weighted Mamdani rules
combined vulnerability screening score (1â€“100)
```

Only the first layer is an official source classification. The normalized
input, membership degrees, rule activations, and final score are GeoSafe-FIS
model products. The interface and report must never present them as MGB or
PHIVOLCS ratings.

The transformation configuration is version controlled in
`config/fuzzy_model.json`. It is a transparent capstone demonstration and has
not been validated for official planning use. Every mapping, breakpoint, rule,
weight, category threshold, and recommendation requires review by qualified
hazard, geotechnical, DRRM, and planning specialists.

## 2. Flood transformation

Source:

```text
MGBPublic/Flood/MapServer/0
field: fscode
```

| Official `fscode` | Official label | GeoSafe-FIS `0â€“100` input |
| --- | --- | ---: |
| `01` | Low Susceptibility | 20 |
| `02` | Moderate Susceptibility | 50 |
| `03` | High Susceptibility | 75 |
| `04` | Very High Susceptibility | 95 |

These numbers are model assumptions, not values published by MGB. The exact
raw code and official label remain alongside the derived number.

Flood memberships use:

| Term | Function | Parameters |
| --- | --- | --- |
| Low | Trapezoidal | `(0, 0, 25, 45)` |
| Moderate | Triangular | `(25, 50, 75)` |
| High | Trapezoidal | `(55, 75, 100, 100)` |

For example, `fscode = 03` remains â€œHigh Susceptibility,â€ maps separately to
75 for model `0.5.2-demo`, and has flood memberships Low 0, Moderate 0, High 1
under this configuration.

## 3. Liquefaction transformation

Source:

```text
PHIVOLCSPublic/Liquefaction/MapServer/0
field: lccode
```

| Official `lccode` | Official label | GeoSafe-FIS `0â€“100` input | Transformation note |
| --- | --- | ---: | --- |
| `01` | Generally Susceptible | 50 | Broad/general class; not treated as Low Potential |
| `02` | Low Potential | 25 | Exact-code lookup |
| `03` | Moderate Potential | 50 | Exact-code lookup |
| `04` | High Potential | 80 | Exact-code lookup |
| `05` | Least Susceptible | 15 | Exact-code lookup |
| `06` | Moderately Susceptible | 55 | Exact-code lookup |
| `07` | Highly Susceptible | 90 | Exact-code lookup |

The domain combines differently worded classification families. GeoSafe-FIS
does not infer order from the code numbers and does not automatically equate
â€œPotentialâ€ with â€œSusceptible.â€ Each row is explicit so specialists can revise
or reject it independently.

Liquefaction memberships use:

| Term | Function | Parameters |
| --- | --- | --- |
| Low | Trapezoidal | `(0, 0, 20, 45)` |
| Moderate | Triangular | `(25, 50, 75)` |
| High | Trapezoidal | `(55, 80, 100, 100)` |

For example, `lccode = 01` remains â€œGenerally Susceptible,â€ maps separately to
50, and has Liquefaction memberships Low 0, Moderate 1, High 0 in model
`0.5.2-demo`. That model result does not redefine the official label.

## 4. Ground-shaking transformation

Ground shaking uses a local grid derived from four official PHIVOLCS Region
VIII 2014 deterministic-scenario raster maps. Each grid cell stores the maximum
sampled PEIS intensity across the scenarios, rounded to an exact code:

```text
source field: peiscode
classification mappings: 01/I -> 10, 02/II -> 20, ... 10/X -> 100
```

The exact scenario values, source URLs, aggregation method, grid size, and 2014
source date remain in each feature's metadata. The grid is a GeoSafe-FIS
derivative, not a PHIVOLCS-issued vector layer. Its `limited` quality status
and the demonstration transformation must remain visible until reviewed by
qualified seismology and model specialists.

The application must not use Active Fault, fault distance, liquefaction,
epicenters, a generic seismic-hazard value, an invented intensity, zero, or a
previous result in its place.

## 5. Membership calculation

For a triangular membership with parameters `(a, b, c)`:

```text
0                         when x â‰¤ a or x â‰¥ c
(x - a) / (b - a)         when a < x < b
1                         when x = b
(c - x) / (c - b)         when b < x < c
```

For a trapezoidal membership with parameters `(a, b, c, d)`:

```text
0                         when x < a or x > d
(x - a) / (b - a)         when a < x < b
1                         when b â‰¤ x â‰¤ c
(d - x) / (d - c)         when c < x < d
```

The implementation handles shoulder cases where `a = b` or `c = d`.
Memberships are retained with the assessment so the result can be reproduced
and explained.

## 6. Rule and score gate

Model `0.5.2-demo` uses three required inputs and one complete generated grid of
27 monotonic Mamdani rules, minimum for `AND`, maximum for `OR`, minimum implication, maximum aggregation,
and discrete centroid defuzzification at each integer from 1 through 100.
Configured output bands are:

| Display category | Score |
| --- | --- |
| Low | 1â€“25 |
| Moderate | 26â€“50 |
| High | 51â€“75 |
| Very High | 76â€“100 |

A complete score is calculated only when all three required source values are
available, their exact codes are recognized, and the model configuration is
valid. A genuine source-coverage gap, missing snapshot, unknown code, or
service/import failure still returns an incomplete result with a null score:

```json
{
  "status": "incomplete",
  "score": null,
  "missing_inputs": ["the_missing_hazard"]
}
```

Available evidence may still be displayed and explained, but it is never
combined into a normal three-hazard score when any required input is missing.

## 7. Missing and changed source values

The following never receive a numeric fallback:

- no intersecting polygon;
- point outside verified coverage;
- timeout or service failure;
- authentication failure;
- missing classification field;
- unknown source code;
- changed, unreviewed domain;
- malformed response; or
- absent ground-shaking source.

In each case, the input remains null/unavailable, the reason is exposed, and the
complete result is blocked. Missing information is not Low vulnerability.

## 8. Imported-data compatibility

The deployment importer can store a documented normalized fraction from 0 to 1
for an authorized static hazard dataset. That path transforms:

```text
model input = stored fraction Ã— 100
```

It is distinct from the live ULAP exact-code mappings above. A deployment must
not mix the two paths without recording the source, mapping method, model
version, and resulting value. A textual imported classification without an
approved fraction remains missing.

## 9. Required presentation

For each hazard, the result and PDF should show, when available:

- source agency, service/layer URL, retrieval time, data date, and attribution;
- raw source code and unchanged official label;
- GeoSafe-FIS normalized value and model version;
- membership values;
- rules using those memberships and their activation strengths;
- cache and data-quality notices; and
- explicit incomplete/missing reasons.

Required disclaimer:

> This output is a preliminary decision-support screening result based on the
> availability and classifications of the cited source datasets. It is not an
> official hazard certification, zoning approval, building-safety rating,
> structural assessment, engineering recommendation, or disaster forecast.
