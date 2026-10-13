# AI Dev Jobs live REST API — unfiltered first-page sample

**Checked:** 2026-10-13  
**Method:** Read-only GET of the documented public endpoint `https://aidevboard.com/api/v1/jobs` through browser retrieval. No account registration, candidate profile, application endpoint, or write action was used. Query-filtered URLs were not accessible in this retrieval environment; no filtered-query experiment is claimed.

## Observed response

The endpoint returned a JSON response with:
- `degraded: false`
- `estimated: false`
- `has_next: true`
- `page: 1`, `per_page: 20`
- `total: 9083`, `total_is_exact: true`
- `total_pages: 455`

These are provider-reported API metadata at the time checked, not an independent count of unique/current canonical vacancies.

## First-page relevance observations

- No listing title containing “Intern” appeared in the first 20 records.
- One record had `experience_level: junior`: **Electrical Integration Systems Engineer, Edge Compute and Communications** at Anduril, located in Costa Mesa, California, with `workplace: onsite`. This is a negative control for a candidate looking for India internships/fresher AI roles; the `junior` enum alone is not sufficient to call it a suitable opportunity.
- The other visible records skewed toward senior/lead engineering, data science, actuarial, management, or US onsite/hybrid roles. Several remote entries explicitly identified a restricted country or had `remote_scope: unknown`.
- Some listing records were duplicated or near-duplicated across related roles (e.g., several Anduril research scientist variants), so coverage calculations must deduplicate by canonical employer requisition, not by aggregator record ID.
- Many `expires_at` values clustered around 2026-10-14 while `published_at` values were around 2026-09-11 to 2026-09-14 and `updated_at` values around 2026-09-12 to 2026-09-14. This may reflect a provider refresh/expiry policy rather than the employer's actual closing date. Do not treat it as authoritative vacancy status without clarification and canonical verification.

## What this test can and cannot say

**Can say:** the live unfiltered API endpoint was reachable; its response includes useful provenance and status fields; the first 20 records were poorly aligned with the initial India internship/fresher target and contained useful negative controls.

**Cannot say:** the API has poor overall precision or recall; filtered queries return no relevant jobs; the total represents 9,083 unique canonical vacancies; every `status: active` listing remains open at the employer; or `expires_at` means employer deadline.

This is a convenience sample of page 1, not a random or representative sample. Do not calculate production source precision, recall, or overall coverage from it.

## Next test

1. Run a bounded direct client request for `q=intern`, `level=junior`, `location=India`, and a separate `global_remote=true` query, capturing the exact URL, status code, headers (especially rate-limit headers), response timestamp, page and record count.
2. If filtered API access cannot be executed in the research environment, run the same test from a user-controlled local environment using the documented public GET endpoint; do not evade throttles or retry 429s.
3. Manually compare every sampled result against the canonical employer page: active status, direct apply URL, role type, seniority/experience, India/work authorization eligibility, global-remote scope, compensation, deadline and duplicates.
4. Compare against a manually assembled sample from official employer career boards. Report relevant-record precision and false-eligibility rate; do not claim recall without a defensible denominator.
5. Ask the provider to clarify the semantics of `expires_at`, how duplicate/reposted requisitions are represented, and whether an internship category is planned. Do not send candidate data or use application endpoints.

## Decision

AI Dev Jobs remains a **candidate discovery source only**. It is not approved as an authoritative eligibility/status source or for production integration. The default endpoint works for a small read-only inspection, but filtered coverage and freshness semantics remain unvalidated. No code, dependency, account, API key, or application action was added or used.

## Source log

- Official API docs: https://aidevboard.com/docs
- Read-only default endpoint: https://aidevboard.com/api/v1/jobs
- Example listing page from response: https://aidevboard.com/job/2db5a60c-c3d2-414c-9a51-83571e86d34d
