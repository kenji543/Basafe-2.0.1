# Basafe Fuzzy-Inference Methodology

## 1. Intended use

The Basafe fuzzy model produces an explainable **vulnerability screening** result for a selected location in Basey, Samar. It combines the available flood, liquefaction, and ground-shaking inputs configured for the model version. It is a planning-oriented decision-support aid, not an engineering analysis, evacuation order, legal zoning determination, development clearance, insurance rating, or guarantee of safety.

Historical incidents and CLUP references are displayed as context. They affect the score only if a future, domain-expert-validated model explicitly defines them as input variables. The approved demonstration model must not silently turn contextual records into undocumented score adjustments.

## 2. Configuration and versioning

The model is maintained in a version-controlled JSON or YAML file, or equivalent seeded database records. There is no browser-based model editor and no administrator-only workflow.

Each model configuration defines:

- model identifier, semantic version, status, checksum, effective date, and notes;
- whether the model is demonstration-only or domain-expert validated;
- input variables and whether each is required;
- stored-source/model input domains, conversion method, and missing-value policy;
- linguistic categories;
- membership-function types and numeric parameters;
- rules in machine-readable and human-readable form;
- rule weights;
- output membership functions;
- output category thresholds;
- antecedent operators, implication, aggregation, and defuzzification methods;
- score domain, with engine-defined rounding behavior;
- validation notes; and
- disclaimer/recommendation version.

Any change to normalization semantics, membership parameters, rules, weights, output functions, thresholds, or inference algorithms creates a new model version. Existing assessments retain the version and configuration checksum that produced them.

### 2.1 Initial demonstration model

The prototype model is stored at `config/fuzzy_model.json` with version `0.5.1-demo`. It defines:

- three required hazard inputsâ€”flood, liquefaction, and ground shakingâ€”on a
  model input domain from 0â€“100;
- exact, separate demonstration transformations for verified live flood
  `fscode` and liquefaction `lccode` values;
- no ground-shaking transformation until a verified source exists;
- low, moderate, and high membership functions for each input;
- 27 generated monotonic Mamdani rules covering every three-term input combination;
- an output universe sampled at each integer from 1 through 100;
- centroid defuzzification; and
- four output categories: Low (1â€“25), Moderate (26â€“50), High (51â€“75), and Very High (76â€“100).

Historical incidents and CLUP references are context only and are not numerical inputs in this model version.

## 3. Demonstration configuration warning

All initial thresholds, mappings, rules, weights, and recommendations are demonstration assumptions until reviewed and validated by qualified specialists in the relevant hazards, disaster-risk science, GIS, and Basey planning context. Plausible-looking numbers are not treated as scientifically validated merely because the software calculates them consistently.

The methodology page, assessment result, preview, PDF, and data-source display must visibly state the model validation status. Demonstration status must not be hidden in a tooltip or technical metadata.

## 4. Inputs and normalization

The approved input variables are:

| Variable | Meaning | Required in the demonstration model | Source |
| --- | --- | --- | --- |
| `flood` | Available flood susceptibility/classification at the selected point | Yes | Verified MGB flood layer or authorized imported dataset |
| `liquefaction` | Available liquefaction susceptibility/classification at the selected point | Yes | Verified PHIVOLCS liquefaction layer or authorized imported dataset |
| `ground_shaking` | Available ground-shaking intensity/susceptibility classification at the selected point | Yes | No verified source currently configured |

Each live input record retains the raw source code, unchanged official label,
complete source attributes, and a separate Basafe `normalized_value` on
the model's 0â€“100 domain. Version `0.5.1-demo` defines exact-code lookups:

| Source field | Code-to-model values |
| --- | --- |
| Flood `fscode` | `01 â†’ 20`, `02 â†’ 50`, `03 â†’ 75`, `04 â†’ 95` |
| Liquefaction `lccode` | `01 â†’ 50`, `02 â†’ 25`, `03 â†’ 50`, `04 â†’ 80`, `05 â†’ 15`, `06 â†’ 55`, `07 â†’ 90` |
| Ground shaking | No mapping; required source unavailable |

These are Basafe demonstration transformations, not official numerical
ratings. They require domain-expert validation. Liquefaction codes are mapped
individually because their labels span different classification families and
their identifiers do not form a simple severity sequence.

Authorized imported features retain the compatibility contract
`normalized_value = normalized_fraction Ã— 100`. A textual imported
classification without an approved fraction remains missing. The live and
imported transformation paths must never be mixed without recording the
source, mapping method, and model version. Exact tables and examples are in
[fuzzy-data-transformations.md](fuzzy-data-transformations.md).

## 5. Availability gate

Before fuzzification, the engine checks every required input:

1. Is an active source dataset configured?
2. Does it cover the selected point?
3. Does the result contain a recognized exact source code and unchanged
   official label, or an authorized imported normalized fraction?
4. Does the live domain still match the model-reviewed mapping?

If any required value is absent:

- the assessment status is `incomplete`;
- the unavailable variable and reason are reported;
- its normalized value and memberships are `null`/empty;
- no final score or vulnerability category is produced (`"Incomplete"` is returned only as a status label);
- missingness is not represented as low membership or low vulnerability; and
- available hazard, incident, CLUP, source, and quality context may still be shown.

The current live workflow always reaches this incomplete gate because no
verified ground-shaking source is configured. Flood or liquefaction
availability cannot override that requirement, and no other seismic layer is
substituted.

If all inputs are present but no output set is activated because of a configuration defect, the fuzzy engine raises a model-configuration error. It never substitutes a default score.

## 6. Membership functions

The initial engine supports documented, deterministic piecewise-linear functions:

- triangular: `triangle(a, b, c)`;
- trapezoidal: `trapezoid(a, b, c, d)`; and
- shoulder sets represented by equal end parameters where the implementation explicitly supports them.

For a triangular set:

\[
\mu(x)=
\begin{cases}
0 & x \le a \text{ or } x \ge c \\
(x-a)/(b-a) & a < x < b \\
(c-x)/(c-b) & b \le x < c
\end{cases}
\]

with \(\mu(b)=1\). Degenerate shoulders are handled by explicit implementation rules rather than division by zero.

For a trapezoidal set:

\[
\mu(x)=
\begin{cases}
0 & x \le a \text{ or } x \ge d \\
(x-a)/(b-a) & a < x < b \\
1 & b \le x \le c \\
(d-x)/(d-c) & c < x < d
\end{cases}
\]

The configuration validator requires ordered, in-domain parameters and membership values in `[0, 1]`. It also checks that the configured linguistic sets cover the intended input/output domain without unintended gaps.

Every assessment exposes the membership degree for every configured linguistic category, including zero values when the interface needs the full membership profile. Displayed degrees may be rounded, while rule evaluation uses unrounded values.

### 6.1 Configured membership functions

Version `0.5.1-demo` contains these input sets:

| Input | Low | Moderate | High |
| --- | --- | --- | --- |
| Flood | trapezoid `(0, 0, 25, 45)` | triangle `(25, 50, 75)` | trapezoid `(55, 75, 100, 100)` |
| Liquefaction | trapezoid `(0, 0, 20, 45)` | triangle `(25, 50, 75)` | trapezoid `(55, 80, 100, 100)` |
| Ground shaking | trapezoid `(0, 0, 25, 45)` | triangle `(25, 50, 75)` | trapezoid `(55, 75, 100, 100)` |

Its 0â€“100 output universe contains:

| Output term | Membership function |
| --- | --- |
| Very Low | trapezoid `(0, 0, 10, 25)` |
| Low | triangle `(15, 30, 45)` |
| Moderate | triangle `(35, 50, 65)` |
| High | triangle `(55, 70, 85)` |
| Very High | trapezoid `(75, 90, 100, 100)` |

These breakpoints are implementation documentation for the demonstration model, not validated hazard-science thresholds.

## 7. Rule evaluation

A rule contains:

- stable rule ID;
- human-readable statement;
- structured antecedent;
- output consequent;
- weight in `[0, 1]`;
- optional rationale/reference.

The default demonstration inference is Mamdani-style:

- `AND`: minimum membership;
- `OR`: maximum membership;
- optional `NOT`: `1 - membership`;
- antecedent strength: result of the structured antecedent;
- effective activation: antecedent strength multiplied by rule weight;
- implication: clip the consequent output membership function at the effective activation; and
- aggregation: maximum across all implicated output sets.

These operators are configuration/version metadata, not hidden assumptions.

### 7.1 Configured rule catalogue

Version `0.5.1-demo` generates all 27 combinations of low, moderate, and high across the three required inputs. Each rule uses `ALL`/minimum and weight `1.00`. The consequent is selected by the sum of the antecedent ordinals (`low=0`, `moderate=1`, `high=2`):

| Ordinal sum | Consequent |
| ---: | --- |
| 0 | Very Low |
| 1â€“2 | Low |
| 3 | Moderate |
| 4â€“5 | High |
| 6 | Very High |

This complete grid prevents uncovered linguistic combinations. Its mapping is monotonic: increasing one input term while holding the other two constant cannot lower the consequent. Automated tests also sweep a representative 125-point numeric grid for score reversals.

The full human-readable statements and rationales remain in `config/fuzzy_model.json` and are returned by the methodology/explanation API. In particular, lower-output rules do not override stronger evidence: all clipped consequent sets are aggregated by maximum before centroid calculation.

For each activated rule (effective activation greater than zero), the result records and displays:

- rule ID and full statement;
- the relevant input membership values;
- antecedent operator and unweighted strength;
- rule weight;
- effective activation strength; and
- output consequent.

Rules must cover the meaningful combinations of the configured input linguistic categories. Model-load validation detects invalid variable/category references, duplicate IDs, invalid operators, unknown consequents, and out-of-range weights. Evaluation raises an error rather than manufacturing a score if a complete input set activates no output.

## 8. Defuzzification and 0â€“100 score

The default demonstration method is centroid defuzzification over the configured output universe:

\[
z^* = \frac{\int_{0}^{100} z \,\mu_{aggregated}(z)\,dz}
{\int_{0}^{100} \mu_{aggregated}(z)\,dz}
\]

Version `0.5.1-demo` uses a deterministic discrete approximation sampled at every integer from 0 through 100. The unrounded centroid is retained for reproducibility; the displayed score is rounded to the nearest integer and bounded to the configured `0` through `100` range.

The configured output universe is already 0â€“100, so no additional score conversion is applied.

\[
score = z^*
\]

The model config states whether this conversion applies. A zero aggregated-area denominator raises a model-configuration error; it is never converted to score 1.

## 9. Descriptive categories

Version `0.5.1-demo` defines:

| Displayed score | Category |
| --- | --- |
| 0â€“20 | Very Low |
| 21â€“40 | Low |
| 41â€“60 | Moderate |
| 61â€“80 | High |
| 81â€“100 | Very High |

The validator requires:

- complete, non-overlapping coverage of scores 0â€“100;
- unambiguous boundary behavior;
- an ordered severity meaning; and
- a display label and cautious interpretation for every category.

Category assignment occurs after score rounding according to the documented configuration. These numeric thresholds are demonstration assumptions and require domain-expert validation. Interface code and reports must read category labels/thresholds from the model response rather than duplicating them.

## 10. Worked explanation format

A user-facing explanation should read in this order:

1. **Source input:** â€œFlood classification: [source value], from [dataset/version/date/status].â€
2. **Normalization:** â€œThe imported fraction is [fraction]; model [version] multiplies it by 100 to obtain [normalized value].â€
3. **Memberships:** â€œAt that value, membership is [degree] in [label], â€¦â€
4. **Rule contribution:** â€œRule [ID] activated at [antecedent strength]; after weight [weight], effective activation is [strength].â€
5. **Aggregation and score:** identify the configured implication, aggregation, and defuzzification methods and show the unrounded/rounded result as appropriate.
6. **Category:** give the threshold band that contains the score.
7. **Context and caution:** list quality/missing-data notices, incidents and CLUP context, recommendations, validation status, and disclaimer.

An illustrative rule explanation may say:

> IF flood is high AND liquefaction is moderate THEN vulnerability is high. Flood-high membership is 0.70 and liquefaction-moderate membership is 0.40, so minimum antecedent strength is 0.40. With rule weight 0.75, effective activation is 0.30.

This example explains arithmetic only. It is not an approved Basey rule or evidence for the example weight.

## 11. Data quality in model output

Data quality is not reduced to a hidden numeric penalty unless qualified domain experts explicitly validate such a method. Instead, the assessment preserves:

- source organization and reference;
- source, publication, and import dates when known;
- spatial scale/resolution and coverage;
- official/demonstration status;
- original and transformed CRS;
- known limitations and validation messages;
- availability/nodata state; and
- model/dataset versions.

A quality warning does not lower the hazard score and thereby create false reassurance. The current prototype evaluates any present normalized fraction while displaying its quality status and notices. Operators must withhold unsuitable datasets during preparation; the runtime does not implement an expert quality-acceptance policy.

## 12. Historical incident and CLUP context

Location-matched incident output states whether a record is:

- within the configured radius of the point;
- covered by an incident geometry; or
- associated with the identified barangay.

The absence of a matching historical record is reported as â€œno matching record is available in the loaded dataset,â€ not â€œno incident occurred.â€

CLUP output states whether a reference geometry covers the point, is associated with the barangay, or is municipality-wide. References include available document/section and source metadata. Basafe does not decide legal conformity, land-use approval, structural suitability, or permitting status.

## 13. Recommendations

Recommendations are configuration/version-controlled and planning-oriented. They should:

- encourage verification with current official maps and competent offices;
- recommend detailed site-specific technical studies where relevant;
- highlight the dominant available hazard inputs without asserting causation;
- state when incident or CLUP context is approximate;
- identify missing or low-quality data; and
- avoid mandatory legal, evacuation, engineering-design, or investment instructions.

An incomplete assessment receives data-gap and verification guidance, not score-based recommendations.

## 14. Validation

Model validation has two distinct layers.

### Current software verification

The current `unittest` suite verifies triangular interpolation, trapezoidal shoulders, a complete bounded/explainable result with all 27 evaluated rules, category span for all-low/all-high inputs, monotonicity on a representative grid, and missing-required-input behavior. Workflow tests verify that normalized values, memberships, activated rules, score, and model version survive in the saved snapshot and explanation response.

The model loader also validates configuration structure, domains, membership parameters, rule references/weights, inference settings, and output thresholds before serving assessments.

### Required domain validation

- review of source-to-normalized mappings;
- review of membership shapes and overlap;
- rule completeness, weights, and rationale;
- output functions and category thresholds;
- representative Basey case review against expert judgment and known observations;
- sensitivity and edge-case analysis; and
- signed/versioned validation notes by qualified domain experts.

Passing software tests does not imply domain validation. Until the second layer is complete, the model status remains demonstration-only.

## 15. Required disclaimer

The configured disclaimer shown by the interface and report is:

> This output is a preliminary decision-support screening result based on the
> availability and classifications of the cited source datasets. It is not an
> official hazard certification, zoning approval, building-safety rating,
> structural assessment, engineering recommendation, or disaster forecast.

An incomplete assessment adds:

> No vulnerability score or category was produced because one or more required hazard inputs were missing. Missing information must not be interpreted as low vulnerability or safety.
