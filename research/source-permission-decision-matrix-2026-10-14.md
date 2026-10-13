# Source Permission Decision Matrix — 2026-10-14

## Purpose

Record what the currently reviewed source terms allow before any live integration is implemented. Permission to read or display listings is separate from vacancy accuracy, applicant-country eligibility, and permission to submit candidate data. This matrix is not legal advice; re-check the linked terms before release because terms can change.

## Decision summary

| Source | Current decision | What the reviewed terms support | Restrictions / unresolved points | MVP action |
|---|---|---|---|---|
| Jobicy public Remote Jobs API | **Approved for a limited prototype source, subject to the rules below** | Official documentation says normal product integrations may use listings without individual permission; interfaces, summaries and categories may be added. Public API is available without an API key and returns Jobicy listing URLs. | Must credit Jobicy and retain the canonical Jobicy URL. Public endpoint contains jobs published in the last 7 days; feed absence is not proof of closure. Do not poll more than once per hour; docs recommend a few times/day. The free endpoint's URL is the Jobicy listing, not necessarily the employer's direct ATS URL. Direct ATS URLs through the commercial API require a wallet and can cost $0.01 per eligible job. Each employer's own application page must still be checked for current status and eligibility before making a strong claim. | Candidate for the first read-only adapter. Use the public endpoint only, preserve source attribution and canonical URL, cache conservatively, rate-limit to no more than hourly, and never pay for the commercial endpoint without separate explicit approval. Do not query the endpoint until the source-quality go/no-go decision. |
| Remotive public API | **Conditional; not selected for the first adapter yet** | Official API terms allow sharing jobs onward when linking to the Remotive listing and naming Remotive as a source. | Feed is delayed by 24 hours. Terms prohibit submitting its jobs to specified third-party job sites and prohibit collecting sign-ups/email addresses as a condition of displaying a listing. Need to verify that the planned app's exact distribution, display and monetization model fits current terms. | Keep out of initial integration until the product flow is documented against terms and the exact use is confirmed. Do not gate job details behind account creation/email capture. |
| AI Dev Jobs API | **Conditional / clarification recommended** | Current terms describe anonymous public read endpoints with hourly throttles and say API data may be used in applications. | Must not scrape beyond rate limits; listing content belongs to employers; resale as a standalone dataset is prohibited. Reviewed terms do not clearly settle all attribution, caching, redistribution, freshness and product-display details for this app. | Do not integrate yet. Ask the operator for written clarification on attribution, display, caching and use in a candidate-facing job discovery product. |
| Direct employer career pages found during research | **Research only unless source-specific permission is established** | Pages can provide useful evidence for human review of role existence, current status, requirements and application destination. | A public page, accessible form, or Apply button does not grant permission for automated collection, long-term caching, republication, autofill or submission. Permissions differ by employer and ATS. | Use official pages for manual evidence checks. Do not bulk-scrape, ingest or automate candidate submissions without source-specific approval/terms review. |
| Himalayas API | **Blocked pending clarification** | Public code or documentation alone is not sufficient permission for job-data use. | Prior review identified conflicting terms that require clarification. | No integration or endpoint query until resolved. |
| JobSpy | **Rejected for this project** | No positive source permission decision established. | The reviewed project promotes proxies to bypass blocking, which conflicts with the project's non-evasion constraint. | Do not import or use. |

## Jobicy limited-prototype conditions

Before implementation is enabled, the proposed adapter must satisfy all of the following:

1. Public endpoint only; no paid/commercial direct-link endpoint and no API key/wallet spend without separate approval.
2. Preserve Jobicy as source, visibly attribute it, and retain the canonical Jobicy listing URL.
3. Treat `active`, `closed`, and `unknown` as distinct statuses when using the documented status endpoint; never convert `unknown` to closed.
4. Respect the 7-day feed window. A missing listing is not evidence of closure.
5. Poll no more frequently than once per hour; default to a few scheduled checks per day. Cache responsibly and back off on throttling/errors.
6. Treat all listing text as untrusted input. Sanitize HTML and do not execute embedded markup/scripts.
7. Store provenance and observation time. Re-verify official employer pages for direct application URL, current availability, work location, degree/year restrictions and compensation before presenting a high-confidence recommendation.
8. Keep remote work mode, applicant-country eligibility and legal work authorization separate. “Anywhere” is not a legal guarantee.
9. Do not send candidate resumes, profiles or other personal data to any source API.
10. Candidate remains in control of opening the employer page and submitting an application.

## What this decision does and does not mean

- It identifies one promising source with published reuse terms; it does **not** prove the source alone meets the product's job-coverage or link-validity targets.
- A Jobicy listing URL is a valid source citation but is not necessarily a direct employer application link. Keep separate fields for `source_listing_url` and `employer_apply_url`.
- Permission to display a source listing does not authorize copying an employer's full page or using an employer's application form programmatically.
- Do not claim the source-quality gate has passed until the sample, link-success metric, eligibility checks, and end-to-end user workflow are measured and reviewed.

## Official references reviewed on 2026-10-14

- Jobicy API documentation and Fair Use: https://jobicy.com/jobs-rss-feed
- Jobicy API examples/terms in repository README: https://github.com/Jobicy/remote-jobs-api/blob/main/README.md
- Remotive API terms: https://remotive.com/remote-jobs/api
- AI Dev Jobs terms: https://aidevboard.com/terms
- Himalayas API repository (clarification required): https://github.com/Himalayas-App/remote-jobs-api
- JobSpy repository (rejected): https://github.com/speedyapply/JobSpy

No source endpoint was queried in this review. No connector, production code, dependency, candidate-data transfer, autofill or application submission was performed.
