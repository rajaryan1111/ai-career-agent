# Himalayas Filtered API Retrieval Attempt — 2026-10-13

**Outcome:** The documented endpoint is verified; the live filtered JSON payload is not retrievable through the current web retrieval interface. This is a tooling limitation, not evidence of provider downtime or zero results.

## Official documentation checked

The current official API docs describe a free public JSON search endpoint at:

- https://himalayas.app/jobs/api/search
- https://himalayas.app/docs/remote-jobs-api
- https://himalayas.app/api

The documented filters include `q`, `country`, `worldwide`, `exclude_worldwide`, `seniority`, `employment_type`, `company`, `timezone`, `sort`, and `page`. The current docs describe cursor pagination for the browse endpoint and page-based filtered search. The browse endpoint has a maximum of 20 jobs per request; data is refreshed every 24 hours, and the API is rate-limited. The docs say displayed data must include a visible link back to Himalayas and mention Himalayas as the source; it must not be resubmitted to third-party websites named in the policy.

## Direct query attempts

The following read-only filtered URLs were opened through the web retrieval interface on 2026-10-13:

1. `/jobs/api/search?q=AI&country=India&seniority=Entry-level&employment_type=Intern&sort=recent`
2. `/jobs/api/search?q=machine%20learning&country=India&seniority=Entry-level&employment_type=Intern&sort=recent`
3. `/jobs/api/search?q=AI&worldwide=true&seniority=Entry-level&employment_type=Intern&sort=recent`

All three returned “URL is not accessible via this tool.” No HTTP status, JSON body, result count, pagination metadata, or rate-limit headers were returned. Therefore, this test did **not** establish whether the provider returned data, no matches, a rate limit, or an endpoint error.

## Decision and next action

- Keep Himalayas as the first candidate for the remote internship source pilot because its documented filters and eligibility fields align with product requirements.
- Mark live filtered API coverage as **not measured**. Do not claim the API is down or that matching listings are absent.
- The next reproducible step requires a network-enabled test environment that can make a normal read-only HTTPS GET request to the official endpoint, capture response metadata, and save a minimal auditable sample. Respect the published request limits and 24-hour refresh; no aggressive retries.
- Once accessible, manually review a fixed sample for role family, internship/entry-level status, India/worldwide eligibility, canonical application route, current status, duplicate identity, salary field semantics, and attribution/retention constraints.
- Do not add a connector, dependency, API key, candidate profile, resume, or application workflow until the validation gate passes.

## Related listing-level caution

The current Tether application form renders a country selector beginning with United Kingdom and “75 more” options. The inspected response did not independently establish that India is eligible for that specific role, so the dataset now records India-specific eligibility as unverified rather than treating broad remote language as proof.


## Follow-up retrieval attempt and documentation consistency check — 2026-10-13

A second direct retrieval pass attempted the same three Himalayas filters and one documented AI Dev Jobs search URL:

- Himalayas India + AI + Entry-level + Intern, sorted recent.
- Himalayas India + machine learning + Entry-level + Intern, sorted recent.
- Himalayas worldwide + AI + Entry-level + Intern, sorted recent.
- AI Dev Jobs GET /api/v1/jobs with q=intern, location=India, level=junior, limit=10, page=1.

The web retrieval interface again returned “URL is not accessible via this tool” for all four URLs. It returned no HTTP status, response body, result count, or rate-limit headers. This remains a retrieval-tool limitation; it is not evidence of provider outage, zero matches, or API failure. No coverage metric was added.

### Earlier pagination note (superseded by the follow-up below)

The current Himalayas API landing page says the browse endpoint uses cursor pagination and recommends echoing nextCursor into the next request. The provider's public remote-jobs-api GitHub OpenAPI document describes limit plus offset pagination instead, and its sample uses offset. Both sources describe a 20-record maximum; the official docs also describe daily refresh and rate limiting. At the time of this note, the current landing page and GitHub artifacts appeared inconsistent. The later first-party documentation check below resolves the implementation choice: follow the current landing page's cursor guidance; treat offset examples as stale. Live filtered payloads remain unverified.

Sources checked 2026-10-13:
- https://himalayas.app/api
- https://himalayas.app/docs/remote-jobs-api
- https://github.com/Himalayas-App/remote-jobs-api/blob/main/openapi.json
- https://aidevboard.com/docs

### Decision

- Filtered results for both providers remain not measured.
- No implementation, dependencies, credentials, or candidate data transfer.
- Next valid step is a normal HTTPS GET from a network-enabled environment, capturing status, headers, response shape, query parameters, and a minimal sample; use the current landing-page cursor guidance if a future sync is authorized; do not implement a full-feed sync just to prove feasibility.

## Documentation discrepancy resolved by current first-party reference check — 2026-10-13

**Correction to the preceding note:** the pagination discrepancy is now substantially resolved by the current official API landing page. It explicitly says the browse endpoint uses cursor pagination, that offset is deprecated and will be removed, and that nextCursor should be passed back as cursor. The public GitHub OpenAPI file and its Python example still describe offset pagination, so those artifacts appear stale or not yet synchronized with the current landing-page instructions. Do not describe this as an unresolved provider ambiguity anymore; describe it as a documentation freshness mismatch with an explicit current recommended path.

Recommended interpretation:
- Browse /jobs/api: use limit up to 20 and cursor/nextCursor according to the current landing page.
- Filtered /jobs/api/search: use its documented 1-based page parameter.
- Do not implement or poll a full-feed sync just to prove feasibility; the bounded filtered pilot remains the lower-cost test.
- Continue to respect the daily refresh, rate limits, visible Himalayas attribution and original listing links.

Evidence: current API landing page https://himalayas.app/api explicitly calls offset deprecated and cursor preferred; current OpenAPI artifact https://github.com/Himalayas-App/remote-jobs-api/blob/main/openapi.json and example https://github.com/Himalayas-App/remote-jobs-api/blob/main/examples/python.py still show offset. Sources checked 2026-10-13.

This resolves the pagination-choice question, but **does not** resolve the separate live retrieval limitation: the four filtered/read-only URLs still returned no status/body through this research interface, so target coverage remains unmeasured.