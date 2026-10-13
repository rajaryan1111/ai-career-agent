# Source Validation Test Suite — Research Gate

**Date:** 2026-10-13  
**Status:** Research-only acceptance specification; no implementation authorized.  
**Dataset under test:** [job-source-audit-seed-2026-10-13.csv](job-source-audit-seed-2026-10-13.csv)  
**Purpose:** Turn the current research into reproducible go/no-go checks before any source connector or application workflow is implemented.

## 1. Current baseline (observed, not a pass)

A strict CSV parser was run over the current seed file on 2026-10-13.

| Check | Observed result |
|---|---:|
| Header columns | 27 |
| Non-empty data rows | 56 |
| Rows with a column count other than 27 | 0 |
| Duplicate listing IDs | 0 |
| Status = open | 7 |
| Status = unknown | 41 |
| Status = expired | 3 |
| Status = closed | 2 |
| Status = not_a_listing | 1 |
| Status = source_review | 2 |

These are mixed listing/source/control records. **They are not 56 confirmed-open unique vacancies.** The open label in this seed is an audit observation and must not be promoted to a current recommendation without a fresh canonical-page check.

## 2. Test method and evidence rules

1. Use documented official APIs/feeds only, within their stated access limits. Do not test blocked or unauthorized sources.
2. Record request time, exact query/filter, HTTP/provider status, pagination metadata, result count, source timestamps, and any rate-limit headers actually returned.
3. Preserve the raw source value and canonical URL for each sampled record. Store only the minimum listing metadata needed for evaluation.
4. Label each record independently for role relevance, candidate eligibility, freshness, canonical status, direct apply route, duplicate identity, and source permission. A single quality score cannot hide a hard failure.
5. Keep **unknown**, **not stated**, **not eligible**, **stale**, **closed**, **expired**, **not a listing**, **source unavailable**, **rate limited**, and **parse failure** distinct.
6. An HTTP 200 response is not proof that valid jobs were returned, that jobs are open, or that an empty filtered result means the market has no jobs.
7. For each finding, retain the official source URL and check date. Provider documentation supports API mechanics, not listing truth or target-audience coverage.
8. Human-review all test labels. Do not send resumes, candidate profile data, emails, or applications during this research test.

## 3. Deterministic fixture tests

These tests can be evaluated against existing seed records before any live connector is considered.

| Test ID | Fixture | Expected result | Failure condition |
|---|---|---|---|
| SV-001 | Entire CSV | Every non-empty row has exactly 27 columns; IDs are unique | Any malformed row, missing header field, or duplicate ID |
| SV-002 | NC-001 Semark | Preserve closed status; suppress from open recommendations | Shown as open because page still exists |
| SV-003 | NC-002 BNP Paribas | Preserve filled/closed status; suppress from open recommendations | Shown as open because the canonical page remains reachable |
| SV-004 | NC-003 GE Aerospace | Past 2026-09-24 deadline is an expiry blocker unless a new requisition is evidenced | Recommended as open based only on an indexed page |
| SV-005 | IN-007 Matrice AI | Deadline 2026-08-31 is past; retain expired label absent new evidence | Reopened from page existence alone |
| SV-006 | IN-003 Ema official board + INT-008 aggregator record | Resolve as one underlying vacancy with source-agreement evidence; count once | Counted as two unique jobs or aggregator seniority silently overrides canonical detail |
| SV-007 | INT-009 Remote OK category page | Treat as source/category evidence, not a vacancy | Counted toward number of available jobs |
| SV-008 | INT-010 AI Dev Jobs source review | Treat as source assessment, not a vacancy | Counted as a job listing |
| SV-009 | IN-010 Atlan People Ops | Exclude from AI/ML engineering target set unless user explicitly includes People Ops | Ranked as AI/ML engineering because title includes “AI” |
| SV-010 | INT-006 Azul Marketing AI Intern | Apply role-family policy; AI-enabled marketing alone is not automatically AI/ML engineering | Passed as a technical ML role without evidence |
| SV-011 | IN-011 Apple PhD ML Intern | Reject for candidate profiles that do not satisfy the explicit PhD requirement | Recommended to an undergraduate as eligible |
| SV-012 | IN-012 Apple experienced ML Engineer | Classify as experienced/full-time, not internship | Recommended as an internship |
| SV-013 | INT-005 Parspec | US-based degree-program / US hybrid constraints must be evaluated; do not assume India eligibility | India-based candidate marked eligible without evidence |
| SV-014 | IN-004 Trackmind | Experience requirement of 6 months to 2 years must be compared with candidate profile | “Junior” title bypasses hard experience eligibility |
| SV-015 | IN-025 Airbus GenAI internship | Preserve promising lead but verify live status and complete eligibility before recommendation | Lead status is treated as proof of current eligibility/open state |
| SV-016 | IN-031 Needl.ai | Email application is a human-approved boundary; prepare a draft only | Email/CV sent without explicit approval |
| SV-017 | Any record with blank compensation | Keep compensation unknown; never coerce blank to zero | UI or ranking shows ₹0/$0 or treats missing pay as unpaid |
| SV-018 | Any row with permission_status=unknown | Source integration remains unapproved pending policy/permission review | Unknown permission silently becomes allowed |
| SV-019 | Any duplicate/repost candidate | Compare canonical employer, normalized role, location, requisition ID and evidence; keep provenance from each source | Duplicate counts inflate coverage or source conflict is silently discarded |
| SV-020 | Any stale-index result without live status | Use unknown until canonical status is freshly verified | Search result freshness or an accessible page is treated as proof of open status |
| SV-021 | INT-017 Remote OK live feed source audit | Treat as source-level evidence, not a vacancy; preserve attribution, location-restriction and zero-pay-placeholder cautions | Counted as a job, a zero salary is interpreted as unpaid, or no intern match in the retrieved response is generalized to the whole feed |

## 4. Live-source test cases (read-only only)

### AI Dev Jobs
- Use only the documented public GET endpoints and documented filters.
- Record whether internship/fresher candidates can be represented despite the documented job-type enum not listing internship.
- Separate junior taxonomy from actual eligibility evidence.
- Validate worldwide eligibility from explicit fields and canonical job wording; never infer it from “remote”.
- Respect the documented hourly anonymous rate limit. On 429, stop and wait; do not retry aggressively or change identities.
- Current evidence is a first-page unfiltered convenience sample, skewed senior. Filtered-query coverage is **not yet measured**.

Official references: https://aidevboard.com/docs and https://aidevboard.com/terms.

### Himalayas
- Test a small, fixed set of documented search filters: India + internship/entry-level; worldwide + internship/entry-level; AI; ML.
- Capture employmentType, seniority, country/worldwide and timezone restrictions, applicationLink, publication/expiry timestamps, salary currency and period, and stable listing ID.
- The documented API has a maximum of 20 results per request, rate limits, and data refreshed every 24 hours. Avoid polling more often than daily.
- If used in a product, show Himalayas as the source with a visible link back to Himalayas and the original listing; do not resubmit its listings to third-party aggregators.
- Filtered API payloads and target coverage have not yet been verified in this environment.

Official references: https://himalayas.app/api and https://himalayas.app/docs/remote-jobs-api.

### Remote OK
- Read only the documented public JSON/RSS feed; preserve source and original-job links.
- Measure relevant role family, internship/entry-level evidence, location eligibility, freshness, duplicates, and apply-link quality.
- Design visible attribution and a link back to Remote OK on any screen using its data; link each job to the original post.
- Treat zero-like pay placeholders as unknown unless the listing explicitly confirms zero compensation.
- Do not infer broad candidate eligibility from “remote”.

Official references: https://remoteok.com/api, https://remoteok.com/faq, https://remoteok.com/legal.

### Official employer boards
- Use direct employer listings as the canonical comparison set, not as a blanket permission to scrape.
- Public board API mechanics differ by provider. For example, Greenhouse documents public GET access for job-board data, while its application POST requires an API key. Discovery permission must not be conflated with submission authorization.
- Do not use LinkedIn, Indeed, Workday, Wellfound, or SmartRecruiters automation contrary to the restrictions recorded in the source feasibility matrix. SmartRecruiters remains blocked pending explicit authorization/endorsed pathway.

Official Greenhouse reference: https://docs.greenhouse.io/job-board.html.

## 5. Sampling plan

**First bounded pilot:** 30 unique records total, selected by a pre-registered rule rather than cherry-picking:

- 10 from AI Dev Jobs using documented queries/filters (if the query results are retrievable and permitted);
- 10 from Himalayas using the documented remote filters;
- 10 from independently found official employer boards, including India on-site/hybrid and international remote roles.

If a source cannot return the sample through the documented interface, record source_unavailable or query_not_testable and do not silently replace it with a different source. Keep source-level and vacancy-level records separate. Deduplicate before counting the 30 unique vacancies; retain source duplicates as provenance evidence.

For every record, two human reviewers should independently label:
- Target role family: yes / no / unknown.
- Student/fresher/entry-level evidence: yes / no / unknown.
- India eligibility: yes / no / unknown.
- International remote eligibility: yes / no / unknown / not applicable.
- Canonical status: open / closed / expired / unknown.
- Apply route: valid direct employer route / valid third-party route / email / broken / unknown.
- Freshness: current evidence / stale / unknown.
- Duplicate: unique / duplicate / possible duplicate.
- Permission/attribution: cleared / blocked / unresolved.
- Final recommendation eligibility: eligible / ineligible / needs user clarification.

Resolve reviewer disagreements with evidence, not model confidence. If a field cannot be verified, retain unknown.

## 6. Go/no-go gate (proposed thresholds; not yet measured)

A source or source combination may proceed to a limited implementation proof only if all hard gates pass:

1. **Coverage:** at least 20 unique, currently valid, target-relevant vacancies in the fixed test window across the proposed source set.
2. **Direct route:** at least 90% of recommended records have a valid canonical employer application route or a clearly disclosed valid application route.
3. **Eligibility safety:** zero known false claims of India or worldwide eligibility in the reviewed sample.
4. **Freshness:** closed/expired records are never recommended as open; stale or unknown status is visibly labelled and excluded from any “verified open” count.
5. **Deduplication:** duplicate source records do not inflate unique-vacancy counts; unresolved likely duplicates are not counted twice.
6. **Permission:** no unresolved material API/terms/attribution/retention blocker for each source selected for the pilot.
7. **Privacy and cost:** no candidate data is sent during discovery validation; no required paid service or recurring cost is introduced.
8. **Reproducibility:** query definitions, sample selection, timestamps, labels and evidence links are saved so the same evaluation can be repeated.

These are proposed internal gates, not results. Report precision among sampled surfaced records. Do not claim recall or broad market coverage without a defensible denominator. A source that fails a gate may remain a manual research lead but must not be called production-ready.

## 7. Decision after this pass

- CSV structure passes the initial 27-column/unique-ID check.
- Several useful negative controls already exist for closed, expired, duplicate, non-listing, role-family and geography cases.
- The live source coverage gate is **not passed**: the existing API smoke test is not a fixed filtered sample, the target-relevant unique count is not established, and permissions/attribution remain unresolved for candidate feeds.
- **No implementation code, dependencies, credentials, candidate data transfer, or application submissions are authorized by this document.**
