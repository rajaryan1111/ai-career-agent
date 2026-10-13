# Live Job-Source Smoke Test: AI Dev Jobs and Remote OK

**Checked:** 2026-10-13  
**Method:** Read the public API responses exposed by the official endpoint pages during this research pass. This is a limited smoke test, not a full paginated crawl, not a representative statistical sample, and not a production integration.  
**No credentials, scraping, application submissions, or new dependencies were used.**

## Executive result

The endpoints are reachable and return structured data, but this pass does **not** establish that either source has enough suitable roles for an India-based student/fresher. The visible samples show a mismatch risk: AI Dev Jobs' first visible records skew toward senior roles, while Remote OK's feed is a broad remote-work feed with roles across many functions and seniority levels.

**Decision:** Keep both as coverage-test candidates; do not mark either production-approved. Build a reproducible, bounded, human-reviewed evaluation before implementation.

## Source 1: AI Dev Jobs

- Official API docs: https://aidevboard.com/docs
- Public jobs endpoint: https://aidevboard.com/api/v1/jobs
- Terms: https://aidevboard.com/terms

### What the official API says

The documentation describes public GET search/list endpoints with pagination, a maximum page size of 50, and filters including full-text query, tags, role level, location, workplace, and explicit worldwide remote scope. The documented levels are `junior`, `mid`, `senior`, `lead`, and `principal`; the documented job types are `full-time`, `part-time`, `contract`, and `freelance`. There is no explicit internship job-type value in that list. Anonymous reads have an hourly IP throttle and return rate-limit headers. Source: https://aidevboard.com/docs

### Observed smoke-test evidence

The official unfiltered endpoint returned a structured JSON response with pagination metadata, source/job IDs, descriptions, company names, locations, workplace/remote-scope fields, job type, experience level, publication/update/expiry timestamps, and original apply URLs. The response identified itself as non-degraded and non-estimated. Example records visible in the response included a senior Data Scientist role requiring more than five years of coding and ML experience, senior actuarial roles, and senior/lead engineering roles. Sources:
- https://aidevboard.com/api/v1/jobs
- https://aidevboard.com/docs

This demonstrates schema usefulness, not target-audience coverage. The visible sample is not enough to estimate how many junior roles exist, and query-parameter variants could not be reliably inspected through this web retrieval interface in this pass. No claim is made that India/junior queries are empty.

### Main risks / requirements

- **Internship representation gap:** documented job-type values do not include internship. Internships might be discoverable through text or other fields, but that is unverified.
- **Level is not eligibility:** a role tagged junior can still require work experience or be restricted to a particular country.
- **Remote is not global:** use the explicit global-remote scope when available; restricted/unknown must not be treated as worldwide eligible.
- **Pay normalization:** the API docs describe salary filters in USD/year. Preserve source currency/period and never interpret missing pay as zero.
- **Provider score is not truth:** use our own hard eligibility checks and evidence-backed ranking.
- **Access throttles:** stay within the documented hourly throttles; no retries or alternate identities to evade 429.

**Status:** High-priority candidate for a bounded coverage test; not approved as a production dependency yet.

## Source 2: Remote OK

- Official JSON feed: https://remoteok.com/api
- Official FAQ: https://remoteok.com/faq
- Terms, updated 2026-07-20: https://remoteok.com/legal

### What the official source says

Remote OK offers free unauthenticated JSON and RSS feeds. Its FAQ asks aggregators to credit Remote OK and link every original job post. Its terms require a web or in-app hyperlink back to Remote OK on the page/app screen where API/site data is used. The API's own first response item includes an attribution notice that asks for a followed link and a source mention. Sources:
- https://remoteok.com/faq
- https://remoteok.com/legal
- https://remoteok.com/api

### Observed smoke-test evidence

The feed returned structured JSON with a legal/attribution object followed by job records. The first visible records included a senior sales role and a product-design director role; the feed is not AI/ML-only and may contain roles unrelated to the user's target. A later visible record included a role marked remote in India, but its content was not an internship/fresher example. This is only a few visible records, not a statistical sample or an assertion that the full feed lacks entry-level AI roles. Source: https://remoteok.com/api

### Main risks / requirements

- **Attribution is mandatory for product design:** show “Remote OK” with a followed link on the screen where its data is used and link each role to its original listing.
- **Feed breadth:** remote-only does not mean technical, entry-level, India-eligible or globally eligible.
- **Freshness:** retain posted/updated timestamps; independently verify the original listing before recommending or applying.
- **Eligibility:** location text alone is not enough; detect explicit “US only”, “UK only”, “India only”, sponsorship and work-authorization language.
- **Missing pay:** Remote OK records can use zero-like salary values; do not show these as ₹0 or $0 compensation. Treat absent/zero placeholder values as unknown unless the source explicitly confirms zero pay.
- **Caching/retention:** keep only the minimum fields needed and confirm the current terms before production.

**Status:** Candidate for a bounded coverage test after the attribution UI requirement is designed; not approved for integration yet.

## Recommended coverage-test protocol

Do this before adding adapters:

1. Define a fixed evaluation window and a target set: AI/ML/software internships, fresher/graduate roles, and junior roles suitable for an India-based candidate, plus separately labelled international roles with explicit worldwide eligibility.
2. Query only documented endpoints/feeds, within their published access controls. Record request time, query/filter, response status, rate-limit headers, result count and source schema/version where available.
3. Take a small bounded sample per source and manually label every record: relevant role family, entry-level evidence, internship/fresher evidence, India eligibility, global-remote eligibility, posted age, apply-link validity, duplicate/repost, and missing fields.
4. Keep distinct labels for **not stated**, **unknown**, **not eligible**, **stale**, and **source unavailable**. Never turn missing evidence into a positive eligibility claim.
5. Report precision among surfaced results and the reasons for rejection. Do not claim recall/market coverage without a defensible denominator.
6. Apply an explicit go/no-go threshold before implementation. Proposed initial gate: at least 20 currently valid, target-relevant records across the test window, at least 90% valid direct apply links, zero known false claims of worldwide eligibility, and no unresolved permission/attribution blockers. These are proposed project thresholds, not measured results.
7. Do not count two feeds as “broad coverage” merely because they are two sources; the test must include an independently assembled employer/official-board sample to expose source blind spots.

## Decision

The smoke test confirms that both sources return useful structured data and official docs exist. It does **not** establish adequate coverage for Indian internships/fresher roles. Continue with the bounded, human-reviewed evaluation and retain the no-code/no-dependency gate until results and terms are satisfactory.
