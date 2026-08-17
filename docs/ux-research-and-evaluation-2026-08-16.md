# Basafe UX Research, Audit, and Evaluation Plan

Date: 2026-08-16  
Scope: current public landing page, map/scoring workspace, source and methodology pages  
Baseline branch: `codex/geosafe-fis-revisions` at `635dd83`

## 1. Research method and limits

This review combined direct inspection of the current Basafe application at
1440 x 900, 768 x 1024, and 390 x 844 viewports; keyboard/DOM inspection; a
manual location-selection and scoring workflow; an incomplete-data workflow;
and review of the public design guidance listed below. No user-research results
are claimed. The usability tasks later in this document are a measurement plan,
not evidence from participants.

| Source studied | Pattern observed | Relevant Basafe problem | Basafe adaptation | Status |
| --- | --- | --- | --- | --- |
| [Esri Calcite Design System](https://developers.arcgis.com/calcite-design-system/sample-code/app-workspace-application/) | A map or spatial canvas remains the focal surface while task content lives in shell panels. Related controls are grouped in blocks; non-critical blocks may collapse. Small screens use an adaptive docked panel and require explicit focus management. | Tablet currently places the entire result beneath a 620 px map, so the result is outside the first viewport. Technical controls also compete with location selection. | Retain the map-first shell; make the tablet result a visible docked sheet; keep critical selection controls visible and put secondary data/layer detail in collapsible sections. | Implemented and browser-verified |
| [Mapbox Navigation documentation](https://docs.mapbox.com/android/navigation/api/coreframework/3.11.5/navigation/com.mapbox.navigation.core.preview/-routes-preview/) | Destination preview precedes route preview. Alternatives retain a stable list order while one route is selected as primary. Route information is shown as user-facing alternatives rather than raw graph costs. | The requested future routing flow needs a truthful way to compare shortest and lower-hazard alternatives. | Document a stable two-route comparison card with distance, estimated walking time, elevated-hazard distance, and maximum mapped exposure. Do not implement it until a routing API and approved evacuation data exist. | Documented only; routing is absent from the repository |
| [Mobbin](https://mobbin.com/) | The public landing page supports searching for patterns and complete product flows. Specific map/navigation screens require an authenticated or paid workflow in the available environment. | Reference research should examine familiar map/search and bottom-sheet patterns without copying proprietary screens. | Use only general, independently supported patterns: prominent map search, concise location summary, docked mobile sheet, and progressive detail. | Limited access; no proprietary screen was used |
| [Page Flows](https://pageflows.com/) | The public Waze index exposed a flow sequence from map to search, location details, and route details. The detailed flow returned HTTP 403 and was sign-up gated. | Basafe needs a short, state-driven flow rather than disconnected screens. | Maintain one continuous map flow: search/select, inspect hazards, calculate, interpret, then open details. Future routing should add destination then route comparison without leaving the map context. | Limited access; sequence only |
| [Figma Community / Figma Learn](https://help.figma.com/hc/en-us/articles/35898387859607-Figma-Sites-collection-Figma-Sites-playground-file-hands-on-exercises) | Direct Community search was blocked in the available research environment. Official Figma learning material emphasizes breakpoints, auto layout, reusable blocks, and interaction prototypes. | Existing responsive behavior has separate desktop/tablet/mobile rules but tablet does not preserve result visibility. | Treat desktop, tablet, and mobile as intentional states; reuse existing CSS tokens and components rather than introduce a generic dashboard kit. | Community inaccessible; official learning material reviewed and responsive states implemented |
| [Nielsen Norman Group heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/) | Keep system state visible, use real-world language, prevent errors, reduce recall, preserve user control, and make errors constructive. [Progressive disclosure](https://www.nngroup.com/articles/progressive-disclosure/) keeps primary features visible while deferring specialized options. | Selection state is not reflected in the empty result panel, raw normalization appears in the primary hazard view, and incomplete copy duplicates hazard names. | Synchronize selection/result states, lead with mapped conditions, move model transformations to technical detail, and make recovery actions explicit. | Applied, implemented, and browser-verified |
| [Maze usability-testing guidance](https://maze.co/guides/usability-testing/) | Combine task completion, direct/indirect success, time on task, errors, misclicks, path analysis, and satisfaction with qualitative observation. Pilot tasks before a larger study. | The project needs defensible evaluation criteria rather than design opinion. | Define seven realistic missions, expected paths, comprehension questions, and device-segmented metrics. | Measurement plan prepared; no results fabricated |

## 2. Baseline workflow evidence

### Flow A - location and score

At desktop size, a map click returned Magallanes and the three mapped
conditions. The enabled `Calculate score` action produced a score of 65, High,
with hazard, model, CDRA/CLUP, and details tabs. The primary score was clear,
but the hazard tab also exposed source codes and normalized values before the
user requested technical explanation.

At mobile size, a map click returned Manlilinab. Flood and liquefaction had no
intersection and ground shaking returned PEIS VII. The interface correctly
withheld a three-hazard score and stated that missing data is not low
vulnerability. It also duplicated the missing hazards in two naming forms:
`flood, liquefaction, Flood, Liquefaction`.

### Flow B - hazard layers

The layer panel supports mutually exclusive Streets, Satellite, and Terrain
base maps, Basey reference boundaries, three independent hazard overlays,
per-layer opacity, source links, and a legend that appears when an overlay is
enabled. The controls are complete, but agency, feature count, quality term,
URL, and opacity are exposed simultaneously for every layer.

### Flow C - incomplete and error states

The app has visible checking, evaluating, unavailable, no-intersection,
incomplete, offline, basemap-error, and outside-Basey states. Outside-Basey
coordinate entry explains the supported area. However, the result panel still
says `Select a Basey location to begin` after a point has been selected outside
Basey, which creates contradictory system feedback.

### Flow D - evacuation routing

No evacuation-center dataset, road-network graph, routing endpoint, route
comparison model, or route UI exists in the current repository. Adding a
visual-only route experience would fabricate application capability. Routing
therefore remains a documented future design and an unresolved product
dependency.

## 3. Nielsen heuristic evaluation

Severity: 0 not an issue, 1 cosmetic, 2 minor, 3 major, 4 critical.

| Issue | Screen / flow | Heuristic violated | Severity | Evidence | Recommended fix |
| --- | --- | --- | ---: | --- | --- |
| Tablet result is below the first viewport | 768 x 1024 scoring | Visibility of system status; flexibility and efficiency | 3 | The left rail and map occupy the first 620+ px row; the result begins below it. | Use a docked result sheet at tablet widths and bring it into view on selection/scoring. |
| Result empty state remains stale after a point is selected | All sizes, selected location before score | Visibility of system status; match with real world | 3 | Left panel shows the barangay while right panel still asks the user to select a location. | Render a selected-location ready state with the next action. |
| Primary hazard cards expose model normalization by default | Completed and incomplete score | Aesthetic and minimalist design; recognition rather than recall | 3 | Users see `Normalized input (0-1)` and model index beside the mapped condition before opening Model. | Keep mapped condition and source as the default; move source code, normalization, weight, and cache into technical detail. |
| Duplicate missing-hazard names | Incomplete score | Consistency and standards; error recovery | 2 | The warning listed machine keys and display labels together. | Canonicalize by hazard key and show each display label once. |
| Mobile selected location is hidden unless the layers sheet is opened | Mobile selection | Visibility of system status; recognition rather than recall | 3 | Map shows only a popup and bottom action; barangay and three hazard conditions are in a closed sheet. | Add a compact selected-location summary above the mobile action and open full details on demand. |
| Tablet is neither a true desktop shell nor a mobile sheet | Tablet | Consistency and standards | 3 | Controls remain a full left rail while results become a long page section. | Treat tablet as an adaptive map plus docked result sheet, with secondary controls in an overlay sheet. |
| Results tabs lack arrow-key behavior | Score explanation | Consistency and standards; accessibility | 2 | Tabs respond to click but do not implement Left/Right/Home/End keyboard interaction or roving tabindex. | Add ARIA tab keyboard behavior and focus transfer. |
| Several helper labels are below comfortable reading size | Map hints, mini steps, layer metadata | Accessibility; aesthetic and minimalist design | 2 | CSS uses 0.64-0.68 rem for important guidance. | Raise functional supporting text to at least 0.75-0.8 rem and retain strong contrast. |
| Update notice can obscure actions | Desktop and mobile | Visibility of system status; user control | 2 | The fixed notice spans much of the bottom edge and competes with scoring/report actions. | Use a compact dismissible notice and reserve mobile space without covering the primary action. |
| Layer rows expose all provenance at once | Layer configuration | Progressive disclosure; aesthetic and minimalist design | 2 | Three layers each show status, quality, feature count, agency, URL, and opacity. | Lead with toggle and label; move provenance and opacity into per-layer details. Keep legend visible for active layers. |
| Initial result copy emphasizes fuzzy implementation | Initial state | Match between system and real world | 2 | Empty copy promises fuzzy memberships and activated rules before explaining ordinary-user value. | Promise mapped hazards, combined score, explanation, and limitations; keep fuzzy detail secondary. |
| Mobile action has no selected-place label | Mobile selection | Recognition rather than recall | 2 | Sticky button says only `Calculate score`; the user must recall which point is active. | Pair action with a compact barangay/area summary. |
| Outside-area state offers no direct recovery action | Coordinate entry | Help users recover from errors | 2 | Message explains the limitation but does not offer `Fit Basey` or clear/reset in the same context. | Add a visible `Return to Basey` action near the message. |
| Color badges often carry status but generally include text | Hazard/result states | Accessibility | 0 | Availability and severity have text labels in addition to color. | Preserve text and shape/border cues. |
| Touch targets are generally 44-48 px | Mobile map | Accessibility | 0 | Search, toolbar, sheet close, tabs, and scoring actions meet the current target. | Preserve minimum target sizes. |

## 4. Priorities

### P0 - blocks core task

No P0 defect was found in the current local snapshot workflow. Search,
selection, scoring, missing-data handling, layer toggles, and reports are
operable.

### P1 - major user confusion

1. Make tablet results visible without a full-page hunt.
2. Synchronize the result empty/ready state with location selection.
3. Show a compact selected-location and hazard summary on mobile.
4. Lead with mapped hazard conditions and defer model values.
5. Remove duplicate incomplete-data names.

### P2 - significant friction

1. Add complete keyboard behavior to result tabs.
2. Reduce default layer-control density while retaining transparency.
3. Raise undersized supporting text.
4. Add an adjacent recovery action for outside-Basey selection.
5. Reduce the update notice's obstruction.

### P3 - polish

1. Tighten labels and spacing after the primary workflows are stable.
2. Add optional motion only where it communicates state, respecting reduced
   motion.

## 5. Basafe design principles

1. Map first.
2. One obvious next action per state.
3. Plain-language mapped conditions before model mathematics.
4. Technical transparency on demand, never removed.
5. System state follows the selected point everywhere.
6. Missing information is never translated into low hazard.
7. Government/source evidence is distinct from Basafe-generated scores.
8. Mobile uses a map plus an accessible docked sheet.
9. Legends describe active layers with text as well as color.
10. No claim that a score, site, or future route is safe.

## 6. Layout proposal before implementation

### Desktop

```text
+---------------------------------------------------------------+
| Basafe                  Map  Sources  Methodology    Data ready |
+-------------+------------------------------+------------------+
| Location    | Search Basey                 | Screening score  |
| summary     |                              | selected state / |
| [Calculate] |             MAP              | result           |
|             |                              |                  |
| Data        |                              | Hazards | Why |  |
| Layers      |                    controls  | Context | Details |
| History     |                              |                  |
+-------------+------------------------------+------------------+
```

The desktop structure remains intact. The change is primarily information
hierarchy: a selected ready-state replaces stale empty content, and primary
hazard cards show the mapped condition and source before technical values.

### Tablet

```text
+--------------------------------------------------+
| Header                                           |
+--------------+-----------------------------------+
| Location     | Search                            |
| + primary    |               MAP                 |
| controls     |                                   |
+--------------+-----------------------------------+
| Docked selected-location / result sheet          |
+--------------------------------------------------+
```

The sheet begins with a compact result summary and remains reachable in the
same viewport after calculation. It expands for tabs and report actions.

### Mobile

```text
+-------------------------------+
| Basafe                 Menu    |
| Search Basey                   |
|                               |
|              MAP              |
|                               |
| [Layers] [Locate] [Fit]        |
|-------------------------------|
| Manlilinab       Inside Basey  |
| Flood --  Liquefaction --      |
| Ground shaking VII             |
| [Calculate score]              |
+-------------------------------+
```

The compact summary acts as the collapsed state. Full location/layer controls
remain in the existing sheet. After scoring, the result sheet becomes the
focused content and can be expanded and scrolled without trapping map users.

## 7. Required state coverage

| State | Baseline coverage | Implemented result |
| --- | --- | --- |
| Initial map | Implemented | Empty copy now names the selection-to-score task and preserves prominent search |
| Searching | Implemented | Search remains visible and form submission works from the keyboard |
| Location selected | Partial | Synchronized result-ready state plus compact mobile location/hazard summary |
| Hazard layers active | Implemented | Active legend remains visible; provenance and opacity are in per-layer disclosure controls |
| Score loading | Implemented | Meaningful step names retained; no fake percentage added |
| Score result | Implemented | Plain-language main mapped condition added before the tabbed evidence |
| Technical explanation expanded | Implemented | Shorter tab labels, ARIA labels, roving tabindex, and arrow/Home/End navigation |
| Missing/incomplete data | Implemented | Canonical display names and explicit `missing is not low` guidance |
| Evacuation routing configuration | Not implemented | Requires product/data/backend work |
| Route loading/result/comparison | Not implemented | Requires product/data/backend work |
| No route available | Not implemented | Define copy only when routing capability exists |
| Outside Basey | Implemented | Result state and adjacent `Return to Basey` action added |
| Mobile equivalents | Partial | Compact location/hazard card, non-obscuring update notice, and tablet result dock implemented |

## 8. Future routing interaction specification

This specification is intentionally not implemented without a routing service,
approved evacuation centers, road data, and hazard-exposure semantics.

1. User selects an inside-Basey origin.
2. `Find evacuation route` opens a destination sheet listing designated
   centers with source and update date.
3. Route loading names truthful states: finding reachable centers, comparing
   routes, and evaluating mapped exposure.
4. Results keep a stable two-card order: `Shortest` then `Lower mapped hazard
   exposure`.
5. Each card shows destination, distance, estimated walking time, elevated-
   hazard distance, and maximum mapped exposure.
6. The map uses different line weights and dash patterns in addition to color.
7. A comparison sentence explains the distance/time tradeoff.
8. A persistent `Planning aid only` notice states that road closure,
   passability, traffic, crowds, current hazards, and evacuation orders are not
   represented unless a future verified service explicitly supplies them.

## 9. Maze-style usability-test plan

Recruit a mix of Basey residents, students, planners, and public users with
varied map familiarity. Run a pilot first. Test desktop and mobile separately;
do not pool their time-on-task baselines.

| Task | Success criterion | Expected path | Comprehension check |
| --- | --- | --- | --- |
| Find the flood condition for a selected Basey location | Correct mapped flood label identified | Search or map click -> location summary -> Flood | Is this an agency classification or Basafe score? |
| Determine the combined multi-hazard result | Category and score identified, or incomplete state correctly reported | Select -> Calculate -> result summary | Does missing information count as low? |
| Identify the main contributing mapped condition | Correct condition named | Result summary -> Why this result | What evidence led to the result? |
| Find the flood source | Agency/dataset source identified | Hazards -> View source details | Which organization supplied it? |
| Find a lower-hazard route to a designated center | Route and destination identified | Future only: Evacuation -> destination -> route | Is this an official evacuation order? |
| Compare lower-hazard and shortest routes | Distance/time/exposure tradeoff correctly described | Future only: Compare routes | Why may the lower-hazard route be longer? |
| Determine whether Basafe guarantees route safety | User answers `No` | Route result -> planning-aid notice | What real-time conditions are not represented? |

For each task collect:

- completion and direct/indirect success rate;
- time on task and time on key screens;
- first-click/tap accuracy and misclick rate;
- number and type of errors or unnecessary actions;
- expected versus actual path;
- abandonment and help requests;
- hazard-interpretation and source-identification accuracy;
- route-comparison accuracy when routing exists;
- disclaimer comprehension;
- post-task Single Ease Question and final satisfaction rating;
- think-aloud comments and a final open question about confidence.

No benchmark values are asserted until representative participants complete
the study.

## 10. Before/after implementation evidence

| Dimension | Before | After |
| --- | --- | --- |
| Steps to score a map-selected location | Click point -> Calculate (2 direct actions) | Still 2 direct actions; no artificial step was added. Selection and readiness are now visible in both the map and result regions. |
| Steps to find route | Not possible | Not implemented without routing dependencies |
| Primary controls visible | Search, coordinates, 4 map utilities, selection action, 3 collapsed panels, empty result | Primary search/map controls remain visible. The result changes from initial to ready, outside, loading, complete, or incomplete without contradicting the selected point. |
| Technical information shown by default | Source code, normalized input, model index, source date in each hazard card | Default hazard card shows mapped classification and source agency. Code, normalized input, model index, date, weight, CRS, cache, and URL remain available under technical details. |
| Mobile usability | Map-first; result auto-scrolls after scoring; selected details hidden in control sheet | Selected barangay and all three hazard statuses appear in a compact map card. Full controls remain in the existing accessible sheet. The card yields to the score after calculation. |
| Tablet usability | Result begins below map row | Result is docked over the lower map edge in the same viewport: compact while ready and expanded after scoring. |
| Error clarity | Strong missing/outside messages; duplicate missing names and stale empty state | Missing hazards appear once using official display labels. Outside selection synchronizes the result and provides `Return to Basey`. |
| Accessibility issues | Good landmarks/touch targets; incomplete tab keyboard behavior and undersized helper text | Existing landmarks and targets preserved; tabs now support Left/Right/Home/End with roving tabindex; functional helper/status text was enlarged; reduced-motion scrolling is respected. |
| Route-comparison clarity | Not applicable | Not applicable until capability exists |

These are interface observations from deterministic browser checks, not
participant usability metrics. The two-action score path did not become
shorter; its state clarity improved.

## 11. Implementation inventory

- `web/map.html`: selected-ready result content, compact mobile selection card,
  and clearer tab labels.
- `web/app.js`: synchronized workflow states, canonical missing-hazard labels,
  main mapped-condition summary, progressive source/technical disclosure,
  outside-area recovery, and keyboard-complete result tabs.
- `web/styles.css`: mobile card, tablet docked result, legibility, disclosure,
  update-notice, and reduced-motion refinements.
- `web/pwa.js` and `web/site.css`: compact refresh/later update prompt that does
  not monopolize the action area.
- `web/index.html`, `web/info.html`, `web/methodology.html`, and
  `web/service-worker.js`: synchronized asset versions and offline cache.
- `tests/test_frontend_contract.py`: regression contract for the new workflow,
  disclosure, tabs, responsive states, and dismissible update prompt.

No API path, database model, hazard classification, fuzzy rule, weight, score
formula, or report contract was changed.

## 12. Browser and regression verification

Browser checks used the running local application and real local endpoints.

| Viewport / scenario | Result |
| --- | --- |
| 1440 x 900, Magallanes `11.303079, 125.119734` | Three-column map-first shell preserved; all hazards available; score 65, High; main mapped condition Ground shaking, PEIS VII; technical values hidden until disclosure is opened. |
| 768 x 1024, same Magallanes point | Selected-ready and completed result remain docked in the first viewport while the map stays visible. |
| 390 x 844, same Magallanes point | Complete score is readable as a single result sheet; four result tabs remain visible and technical details are collapsed. |
| 390 x 844, Manlilinab `11.370992, 125.132772` | Compact card shows Flood and Liquefaction as No Intersection and Ground shaking as PEIS VII; incomplete result lists `Flood, Liquefaction` once and shows no numeric score. |
| 390 x 844, outside point `12, 126` | Result changes to `Choose a point inside Basey` and exposes one direct `Return to Basey` action. |
| Keyboard result navigation | ArrowRight moved focus and selection from Hazards to Why; the tablist maintained one `tabindex="0"`. Home/End and ArrowLeft are covered by the same handler and regression contract. |
| Progressive disclosure | `Normalized input` was not visible before expanding technical details and was visible afterward. Layer source information likewise remained hidden until `Layer details` was opened. |
| Automated regression | `python -m unittest discover -s tests -q`: 99 tests passed, 6 skipped. JavaScript syntax checks and `git diff --check` passed. |

## 13. Remaining issues and dependencies

1. The findings still require representative-user testing before claiming
   improved completion time, comprehension, confidence, or satisfaction.
2. Mobile geolocation depends on browser permission and device accuracy.
3. Basemap tiles still depend on external providers; local hazard scoring is
   independent of the imagery, but imagery availability can vary.
4. No evacuation routing capability exists. It needs approved centers, a road
   graph/service, route-exposure semantics, and product validation before UI
   implementation.
5. No new focus-management library or UI framework was introduced; the app
   continues to use its existing native controls and Leaflet shell.

## 14. Self-review gate

Browser verification produced the following self-review answers. Routing is
explicitly marked as an unimplemented dependency rather than represented as a
working feature:

- Yes - the initial and selected-ready states name the next action.
- Yes - mapped conditions and the combined score are presented before fuzzy
  implementation details.
- Yes - normalization, model index, weights, memberships, rules, and provenance
  remain available on demand.
- Yes - the result calls hazard cards `Source evidence` and labels the combined
  output `Multi-hazard score`.
- Yes - source agencies are shown on hazard cards while Basafe-generated output
  is contained in the score summary.
- Yes - each hazard and map layer retains expandable source information.
- Yes - incomplete copy states that missing is not low, and outside points have
  a direct recovery action.
- Yes - mobile exposes the selected place and three hazard statuses before the
  score action.
- Yes - search is a native form, actions are buttons, and result tabs support
  arrow/Home/End navigation.
- Yes - warnings are contained in the result sheet and the compact update notice
  can be dismissed.
- Yes - the map remains the central surface at all three tested viewports.
- Not implemented - dependency missing: evacuation routing and route
  comparison.
