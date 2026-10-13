# Remote OK API: fit and policy comparison for Career Agent

**Checked:** 2026-10-13  
**Status:** Secondary candidate for remote-role discovery only; not production-approved.  
**Evidence type:** Official Remote OK FAQ and Himalayas official API documentation. No live feed payload was successfully retrieved in this environment, so this is a schema/policy comparison, not a listing-quality test.

## Executive finding

Remote OK documents a free, unauthenticated JSON feed at `https://remoteok.com/api` and RSS feed at `https://remoteok.com/remote-jobs.rss`. It supports filtering by tags, including `tag` or `tags`. The official FAQ requires attribution to Remote OK and a link to each original job post when its feed is used to build an aggregator or publicly share listings.

This is useful as a secondary remote-source candidate, but the public documentation reviewed does not show the same explicit filter dimensions documented by Himalayas for internship type, entry-level seniority, country eligibility, worldwide availability and timezone restrictions. Do not assume tag search can safely substitute for those structured fields.

Sources:
- Remote OK official FAQ: https://remoteok.com/faq
- Remote OK API help: https://remoteok.featurebase.app/help/articles/3140840-is-there-an-api-or-rssjson-feed-of-remote-jobs
- Himalayas official API docs: https://himalayas.app/api

## Comparative assessment

| Capability | Remote OK documented feed | Himalayas documented API | Career Agent implication |
|---|---|---|---|
| No-auth public access | Yes | Yes | Both are technically easy to probe |
| Structured internship filter | Not established in reviewed public docs; tag filter documented | Explicit `employment_type=Intern` | Himalayas better documented for internship search |
| Entry-level filter | Not established in reviewed public docs | Explicit `seniority=Entry-level` | Remote OK needs title/description review and more false-positive testing |
| Country eligibility filter | Not established in reviewed public docs | Explicit `country` plus per-listing restrictions | Don't infer candidate eligibility from remote label alone |
| Explicit worldwide filter | Not established in reviewed public docs | `worldwide=true` documented | Himalayas has the clearer hard-gate signal |
| Timezone restrictions | Not established in reviewed public docs | Documented field and filter | Himalayas better suited to explainable IST eligibility |
| Attribution | Credit Remote OK and link original job URL | Mention Himalayas and link back to Himalayas listing | Both require visible source attribution; preserve employer apply URL separately |
| Rate limits | Public FAQ reviewed does not specify a numeric budget | Himalayas says rate-limited; 429 response says wait 60 seconds | Do not assume unlimited requests for either |
| On-site/hybrid India roles | Remote-focused | Remote-focused | Neither covers the whole target market |

“Not established in reviewed public docs” means the cited official material did not document the capability; it is not a claim that the provider can never support it.

## Product constraints if Remote OK is tested

1. Treat feed records as leads, not authoritative vacancy status.
2. Preserve the original Remote OK listing URL for attribution and separately retain the canonical employer/application URL when available.
3. Do not equate remote with worldwide eligibility. Parse any stated country, work authorization, timezone, or location limits from the listing and canonical employer page.
4. Keep source labels visible and make it clear which page is the aggregator listing versus the employer's application destination.
5. Use bounded read-only requests, record status and timestamps, deduplicate reposts, and respect any published rate limits or server errors. Do not evade throttling.
6. Do not resell or republish feed data outside the product without reviewing the provider's current terms.

## Proposed experiment, if added to the sample

- Retrieve one feed page only, after connectivity is available.
- Record request URL, timestamp, HTTP status, response headers, item count and raw response fixture.
- Inspect titles/tags for AI, machine learning, internship, graduate and entry-level signals; this is candidate generation, not eligibility proof.
- For every sampled result, verify canonical employer status, country/work authorization, role type, experience requirements, direct application URL, compensation period/currency and duplicate/repost status.
- Report precision among human-reviewed results and false-eligibility rate. Do not claim recall without a defensible denominator.

## Decision

Keep Remote OK as a **secondary comparison source**, behind Himalayas for the remote internship pilot because Himalayas documents more of the structured fields needed for strict eligibility. No production integration is approved. The live Remote OK feed was not retrieved in this environment; no result count or coverage metric is claimed. No code, dependencies, account, API key, candidate data or application action was added or used.
