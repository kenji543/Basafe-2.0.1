# ULAP Error, Availability, and Cache Handling

## 1. Principle

Basafe must explain why evidence is unavailable. “No data” is too
ambiguous, and missing evidence must never become zero, Low, Safe, or a reused
previous result.

The backend normalizes ArcGIS, HTTP, network, schema, coverage, and model-gate
outcomes into explicit statuses while retaining sanitized diagnostic details.

## 2. Status catalogue

| Status | Meaning | Assessment effect |
| --- | --- | --- |
| `available` | A point feature has a recognized required field/code and the live domain matches the reviewed registry | May enter the separately configured model |
| `no_intersection` | The service returned a valid empty `features` array for the point | Input missing; never Low |
| `outside_coverage` | Boundary/coverage evidence establishes the point is outside the supported area | Reject Basey workflow or mark input missing, as applicable |
| `unavailable` | No verified/configured source exists, including current ground shaking | Input missing |
| `authentication_required` | HTTP 401/403 or ArcGIS 498/499 | Input missing; operator must supply authorized server-side credentials |
| `service_error` | ArcGIS/HTTP upstream failure not otherwise classified | Input missing; retry rules may apply |
| `timeout` | Request exhausted the configured timeout/retry allowance | Input missing |
| `invalid_response` | Non-JSON, wrong JSON shape, absent/non-array `features`, conflicting intersecting codes, or another unusable payload | Input missing |
| `changed_schema` | Required field/domain/geometry/CRS expectation changed, a field value is absent, or a point code is unknown | Preserve source evidence; block model use pending review |
| `incomplete` | At least one required hazard is not `available` | Score null; no normal vulnerability category |
| `pending_verification` | Source structure or authority is not yet verified | Do not use as official model evidence |
| `verified` | Current service/layer metadata matches the configured expectation | Endpoint/schema check passed; point availability is still separate |
| `verified_with_changed_metadata` | Endpoint responds but non-fatal expected metadata differs | Display differences and review before relying on changed fields/domains |
| `inaccessible` | Network/host access failed after retries | Input missing |
| `invalid_layer` | HTTP/ArcGIS 404 or layer validation failure | Input missing until configuration is corrected |
| `missing_classification_field` | Metadata lacks the configured class field | Input missing |

Not every status is appropriate at every layer. For example, a point query may
be `no_intersection` even when metadata validation is `verified`.

## 3. ArcGIS and HTTP errors

ArcGIS may return HTTP 200 with an `error` object. The parser checks that object
before treating a response as successful.

| ArcGIS/HTTP condition | Normalized status |
| --- | --- |
| ArcGIS 498 or 499 | `authentication_required` |
| HTTP 401 or 403 | `authentication_required` |
| ArcGIS/HTTP 404 | `invalid_layer` |
| HTTP 429, 500, 502, 503, or 504 | Retryable `service_error` |
| Other ArcGIS error | `service_error` |
| HTTP error without usable ArcGIS object | `service_error` or `invalid_response`, according to parsed response |
| Non-JSON body | `invalid_response`, after retry only when its HTTP status is retryable |
| JSON root that is not an object | `invalid_response` |

The structured error object includes:

```json
{
  "status": "authentication_required",
  "message": "sanitized upstream message",
  "endpoint": "https://approved-host/path/without-query",
  "http_status": 403,
  "arcgis_error_code": 499,
  "details": []
}
```

Query strings are removed from exposed endpoints. Keys named `token`,
`access_token`, `authorization`, `password`, or `key` are recursively redacted
from diagnostic detail.

## 4. Retries and timeouts

Defaults:

```text
ULAP_REQUEST_TIMEOUT_SECONDS=15
ULAP_MAX_RETRIES=2
```

`ULAP_MAX_RETRIES=2` means one initial attempt and at most two retries.
Network errors, socket timeouts, and retryable HTTP/service errors use
exponential delays based on 0.25 seconds:

```text
after attempt 1: 0.25 seconds
after attempt 2: 0.50 seconds
```

Authentication, invalid-layer, schema, coordinate, and ordinary valid
zero-feature outcomes are not made successful through retries. The retry limit
must remain small to avoid amplifying load on the upstream services.

## 5. Cache behavior

Defaults:

```text
ULAP_METADATA_CACHE_SECONDS=86400
ULAP_QUERY_CACHE_SECONDS=3600
```

The current client uses a process-local, thread-safe memory cache. Each object
records:

- sanitized source URL;
- retrieval time;
- expiration time;
- whether returned from cache;
- stale flag; and
- metadata version when the ArcGIS response provides one.

Tokens are excluded from cache keys and source URLs. An unexpired cache hit has
`from_cache = true` and `stale = false`. An expired entry is deleted and a live
request is attempted. The current implementation has no stale-cache fallback;
it does not silently use expired data when the live service fails.

The client provides internal whole-cache clearing and source-specific
invalidation. There is intentionally no browser administration/cache-management
page or public cache-control endpoint.

Changing a TTL affects new requests only. Setting it to zero disables caching
for that class of request.

## 6. URL and token controls

Outbound ArcGIS URLs must:

- use HTTPS;
- use port 443 or the default HTTPS port;
- have no embedded username/password or fragment;
- resolve to `ulap-hazards.georisk.gov.ph` or
  `ulap-nga.georisk.gov.ph`; and
- remain allowlisted after a redirect.

The registry supports only approved relative service paths and the two
configured base-URL environment overrides. An override that resolves outside
the allowlist fails validation.

`ULAP_TOKEN` is optional and server side. It is added as an encoded request
parameter only by the backend. It must never be committed, sent to the browser,
included in cache keys, logged, saved with an assessment, or printed by the
verification script.

## 7. Point-query edge cases

### Zero features

A valid response with zero features is `no_intersection`. It may reflect a
coverage gap, intentionally unmapped area, geometry issue, or true lack of a
polygon. Without separate coverage evidence, the backend does not claim which.

### Multiple features with one code

If intersecting polygons all have the same official code, the provider can
return that code with a multiple-intersection warning and the feature count.

### Multiple features with conflicting codes

If the official codes differ, the result is `invalid_response`; all
intersecting attributes are preserved for diagnosis and no class is selected.
The backend does not silently choose the first, lowest, or highest class.

### Missing or unknown classification

A missing configured field, null code, unknown code, absent live domain, or
live/configured domain mismatch produces `changed_schema`. The raw code and
attributes are retained where present, but the model transformation is blocked.

## 8. Boundary errors

Boundary identification first queries the municipal layer:

- no municipal polygon at the point: `outside_coverage`;
- a municipality other than Basey, Samar: `outside_coverage`;
- multiple Basey polygons: returned with a topology warning;
- inside Basey but no matching barangay: `no_intersection`, with the location
  still identified as inside Basey; and
- network/authentication/schema failure: the corresponding explicit status.

A normal Basey assessment must not run for a point outside the verified Basey
municipal result.

## 9. Logging

Successful client requests currently log:

- sanitized dataset endpoint;
- HTTP status;
- request duration in milliseconds;
- returned feature count when applicable; and
- parsing status.

Typed response/error objects additionally carry request/retrieval times, layer
source, cache state, HTTP status, and ArcGIS error code where available. Logs
must never contain a token or unredacted authorization detail. Technical logs
are for debugging and operations; they are not a user activity log or
application audit-log feature.

## 10. User-facing and report behavior

The interface and PDF should translate statuses into plain language while
retaining the exact machine status. Required examples:

- “No intersecting flood polygon was returned. This is not a Low or Safe
  classification.”
- “Authorized ArcGIS access is required.”
- “The live classification domain changed; the official value is preserved
  but model use is blocked.”
- “A verified ground-shaking source is not configured.”
- “A complete assessment cannot be calculated because required hazard values
  are unavailable.”

Available hazards, sources, incident context, and CLUP context may still be
shown for an incomplete result. The score remains null.
