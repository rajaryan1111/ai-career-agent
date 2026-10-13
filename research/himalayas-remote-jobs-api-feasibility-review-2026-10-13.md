# Alternative remote-job API evaluation: Himalayas

**Checked:** 2026-10-13  
**Status:** Strong candidate for a bounded read-only pilot; not production-approved.  
**Evidence type:** Official provider documentation and OpenAPI/schema documentation. Live filtered API payloads could not be retrieved through this research environment, so this is a schema/terms assessment, not a coverage or listing-quality measurement.

## Executive finding

Himalayas is a better *schema fit* than AI Dev Jobs for the worldwide-remote internship track because its public API explicitly documents:
- `employment_type=Intern`;
- `seniority=Entry-level`;
- `country=IN` (or country names/slugs);
- `worldwide=true` to limit results to worldwide-friendly jobs;
- `locationRestrictions` and `timezoneRestrictions` on each job;
- `applicationLink`, `pubDate`, `expiryDate`, salary currency and pay period.

The API is documented as free, public, and unauthenticated, with a maximum of 20 records per request and rate limiting. However, the provider requires a visible credit to Himalayas and a link back to the Himalayas listing whenever its data is displayed in our application. This is a real product requirement, not optional polish.

Sources:
- API overview and use terms: https://himalayas.app/api
- Detailed API docs: https://himalayas.app/docs/remote-jobs-api
- Data dictionary: https://himalayas.app/docs/data-dictionary
- OpenAPI/examples: https://github.com/Himalayas-App/remote-jobs-api

## Relevant documented schema

| Need | Himalayas field/filter | Product use / caveat |
|---|---|---|
| Internship classification | `employmentType=Intern` | Better than guessing from title; still verify employer description |
| Entry-level search | `seniority=Entry-level` | Does not prove student/year/degree/experience eligibility |
| India-specific remote roles | `country=IN` | Cross-check `locationRestrictions` and employer terms |
| Worldwide-remote roles | `worldwide=true` | Useful hard gate, but still independently verify candidate eligibility |
| Country restrictions | `locationRestrictions` | Empty array is documented as worldwide; unknown/malformed data must not be interpreted as unrestricted |
| Timezone limits | `timezoneRestrictions` | Candidate timezone is IST (UTC+05:30); interpret provider values carefully |
| Salary | `minSalary`, `maxSalary`, `currency`, `salaryPeriod` | Preserve currency and pay period; do not assume annual or USD |
| Freshness | `pubDate`, `expiryDate`, response `updatedAt` | Provider timestamps are useful signals, not a substitute for checking the employer's canonical vacancy |
| Apply destination | `applicationLink` | Validate target, preserve provenance and verify canonical employer page |
| Stable identity | `guid`, `companySlug` | Deduplicate with canonical employer URL/requisition where possible, not only provider IDs |

## Terms and integration implications

The provider states the API is free to use, including commercially, subject to attribution:
1. Include a visible mention that data is sourced from Himalayas.
2. Link back to the Himalayas listing URL (the docs say to use `applicationLink` or `guid`; verify the exact user-facing destination and preserve the original employer apply destination separately where present).
3. Do not resubmit Himalayas listings to third-party job aggregators such as Jooble, Neuvoo, Google Jobs, or LinkedIn Jobs.

For our downloadable desktop app, a visible source label and source-link on each listing can satisfy the stated attribution intent, but counsel/provider clarification may be needed if our UI or local caching semantics are ambiguous. Do not republish a bulk dataset outside the app or send these listings to another aggregator.

The API documentation says the browser cannot call the endpoint directly due to absent CORS headers. A desktop app can call from its local backend/process, subject to normal network, rate-limit and privacy handling. Do not add a proxy service that creates recurring infrastructure costs; the first test can be a local one-off script once network access is available.

## Proposed bounded experiment (not yet executed)

Run four separate, low-volume queries and capture request URL, timestamp, response status, response `updatedAt`, result count, relevant rate-limit/error metadata if available, and raw response fixture:
1. India + Entry-level + Intern + keyword AI.
2. India + Entry-level + Intern + keyword machine learning.
3. Worldwide + Entry-level + Intern + keyword AI.
4. Worldwide + Entry-level + Intern + keyword machine learning.

Use no more than one page (20 records) per query initially. Do not automatically retry 429 responses; wait according to provider guidance. Deduplicate records across queries before scoring.

For every returned record, manually check:
- canonical employer job page still open;
- actual employment type and degree/year requirements;
- required years of experience;
- India candidate eligibility/work authorization;
- worldwide vs restricted remote status and timezone restrictions;
- direct application link and whether it points to the employer or an intermediary;
- compensation currency and pay period;
- duplicate/repost status.

Compare the resulting set against a small manually collected official-employer-board sample. Report relevant-record precision and false-eligibility rate; do not claim recall without a defensible denominator. Preserve raw source data separately from normalized classifications.

## Known limitations and open questions

- Live filtered JSON responses were inaccessible through the current browser retrieval environment; the local runtime also lacked DNS/network access. Therefore no query was actually executed and no result count, job quality, or coverage metric is claimed.
- The public docs do not establish whether every employer listing is checked against the employer's canonical page at the moment of every response.
- The meaning of an empty `locationRestrictions` array is documented as worldwide; still verify whether timezone limits or employer description impose additional constraints.
- The exact listing URL suitable for attribution may differ from the employer's actual apply URL. Preserve both separately and test with real records before product approval.
- The API is remote-focused; it does not solve the India on-site/hybrid internship track.
- Data availability and terms can change. Re-check official docs and terms before shipping.

## Decision

**Prioritize Himalayas for the next remote-internship source pilot** because its documented schema aligns better with explicit internship and worldwide/country eligibility gates. Keep AI Dev Jobs as a secondary comparison source, not authoritative. Neither source is approved for production yet. No code, dependencies, API keys, accounts, candidate data, or application submissions were added or used in this review.

## Source log checked 2026-10-13

- https://himalayas.app/api
- https://himalayas.app/docs/remote-jobs-api
- https://himalayas.app/docs/data-dictionary
- https://github.com/Himalayas-App/remote-jobs-api
- AI Dev Jobs comparison: https://aidevboard.com/docs
