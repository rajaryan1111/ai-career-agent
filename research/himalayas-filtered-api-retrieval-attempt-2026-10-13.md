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
