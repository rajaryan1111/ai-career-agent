# Source Validation Test Suite — Research Gate

**Date:** 2026-10-13  
**Status:** Research-only acceptance specification; no implementation authorized.  
**Dataset under test:** [job-source-audit-seed-2026-10-13.csv](job-source-audit-seed-2026-10-13.csv)  
**Purpose:** Turn the current research into reproducible go/no-go checks before any source connector or application workflow is implemented.

## 1. Current baseline (observed, not a pass)

A strict CSV parser was rerun over the current seed file on 2026-10-14 after expanding the research sample. This replaces the original 2026-10-13 baseline.

| Check | Observed result |
|---|---:|
| Header columns | 27 |
| Non-empty data rows | 82 |
| Rows with a column count other than 27 | 0 |
| Duplicate listing IDs | 0 |
| Status = open | 15 |
| Status = unknown | 56 |
| Status = expired | 3 |
| Status = closed | 2 |
| Status = not_a_listing | 2 |
| Status = source_review | 4 |
| Distinct canonical URL values | 73 |
| Repeated canonical-URL groups | 8 (7 exact requisition groups + 1 shared general-careers-page ambiguity) |

These are mixed listing/source/control records. **They are not confirmed-open unique vacancies.** The open label in this seed is an audit observation and must not be promoted to a current recommendation without a fresh canonical-page check.

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
| SV-021 | AUD-REMOTEOK-20261013 Remote OK live feed source audit | Treat as source-level evidence, not a vacancy; preserve attribution, location-restriction and zero-pay-placeholder cautions | Counted as a job, a zero salary is interpreted as unpaid, or no intern match in the retrieved response is generalized to the whole feed |
| SV-022 | INT-019 Tether Research Engineer Intern | Enforce MSc/PhD eligibility and honor the employer's explicit instruction not to use AI tools to complete application responses | Recommended to a candidate who does not meet the degree requirement, or AI drafts/autofills prohibited answers |
| SV-023 | AUD-HIMALAYAS-MISMATCH-20261013 One Impression / HexCoded | Keep source-review status; role family is growth/GTM and employer identity is unresolved | Aggregator tags alone cause recommendation as an ML-engineering vacancy |
| SV-024 | INT-020 Origin CVAT Annotation Intern | Keep current status unknown until the specific role is verified on an official source; classify as CV annotation/data QA | Aggregator deadline is treated as canonical proof of open status or annotation is mislabeled as model engineering |
| SV-025 | IN-022 Sprinto AI Implementation Intern | Classify the role as AI implementation/applied engineering from the readable canonical page; because no explicit current-open wording was captured, keep status unknown pending confirmation | Apply control alone is treated as proof of current availability, or the role is promoted to ML research without evidence |
| SV-026 | AUD-HIMALAYAS-API-20261013 | Record direct filtered API retrieval as inaccessible through the web interface; keep coverage unmeasured and do not infer zero results/provider downtime | Failed retrieval is reported as no jobs or provider outage, or guessed counts are entered |
| SV-027 | INT-019 Tether country selector | Keep India-specific eligibility unknown until the accepted-country list is verified; enforce the explicit no-AI-answers instruction | Remote wording or a long country selector is treated as proof of India eligibility, or prohibited answers are AI-generated |
| SV-028 | IN-001 Apple Applied ML Intern | Enforce the official minimum requirement of PhD student in year 2 or beyond; retain unknown listing status until separately verified | Recommended to an undergraduate or marked eligible because the role is in Bengaluru and says intern |
| SV-029 | IN-022 Sprinto application page | Treat hCaptcha as a human-intervention boundary; never solve, bypass, or automate around it. Listing discovery/detail review remains separate from application submission | Automation attempts to bypass the challenge or claims that a visible Apply link authorizes automated submission |

### SV-031 — Himalayas permission conflict fixture

| Test ID | Fixture | Expected result | Failure condition |
|---|---|---|---|
| SV-031 | Himalayas public API documentation versus general Terms of Service | Mark source blocked pending written clarification; do not call/search/crawl/cache it during feasibility sampling. If later cleared, record the written scope and meet attribution/link-back and no-third-party-aggregator conditions | Public API availability or attribution is treated as unconditional permission despite the general terms' automated-gathering restriction, or Himalayas is counted as a cleared source without written clarification |

## 4. Live-source test cases (read-only only)

### AI Dev Jobs
- Use only the documented public GET endpoints and documented filters.
- Record whether internship/fresher candidates can be represented despite the documented job-type enum not listing internship.
- Separate junior taxonomy from actual eligibility evidence.
- Validate worldwide eligibility from explicit fields and canonical job wording; never infer it from “remote”.
- Respect the documented hourly anonymous rate limit. On 429, stop and wait; do not retry aggressively or change identities.
- Current evidence is a first-page unfiltered convenience sample, skewed senior. Filtered-query coverage is **not yet measured**.

Official references: https://aidevboard.com/docs and https://aidevboard.com/terms.

### Himalayas — HOLD; do not run the planned query test until permission is clarified
- Official API docs describe public integration use, but general Terms of Service broadly prohibit automated data gathering without prior written approval.
- Obtain written clarification for a local-first desktop client before calling filtered endpoints, crawling, caching, or measuring coverage. See [permission review](himalayas-api-permission-terms-conflict-2026-10-13.md).
- If and only if written clearance is received, test a small, fixed set of documented search filters: India + internship/entry-level; worldwide + internship/entry-level; AI; ML.
- Capture employmentType, seniority, country/worldwide and timezone restrictions, applicationLink, publication/expiry timestamps, salary currency and period, and stable listing ID.
- The documented API has a maximum of 20 results per request, rate limits, and data refreshed every 24 hours. Avoid polling more often than daily.
- If written permission is obtained, show Himalayas as the source with a visible link back to Himalayas and the original listing; do not resubmit its listings to third-party aggregators.
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
- The live source coverage gate is **not passed**: the existing API smoke test is not a fixed filtered sample, the target-relevant unique count is not established, and permissions/attribution remain unresolved for candidate feeds. Himalayas is specifically on hold pending written clarification because its API docs and general terms create a material permission ambiguity.
- **No implementation code, dependencies, credentials, candidate data transfer, or application submissions are authorized by this document.**


### Follow-up retrieval attempt and API contract discrepancy — 2026-10-13

A second direct retrieval pass attempted the three documented Himalayas filtered searches (India+AI+Entry-level+Intern; India+machine learning+Entry-level+Intern; worldwide+AI+Entry-level+Intern) and a documented AI Dev Jobs read-only search (q=intern, location=India, level=junior, limit=10, page=1). All four URLs were inaccessible through the current web retrieval interface; no HTTP status/body/headers were returned. The sample remains not measured, not empty and not evidence of provider downtime.

At the time of the first check, the Himalayas API landing page and its public OpenAPI file appeared inconsistent about browse pagination. A subsequent check of the current landing page resolved the choice: it explicitly deprecates offset and recommends cursor/nextCursor for browse; filtered search uses 1-based page pagination. Treat the older OpenAPI/example as stale. The live filtered response is still unverified and request/response metadata must be captured in the bounded pilot.

References: https://himalayas.app/api ; https://himalayas.app/docs/remote-jobs-api ; https://github.com/Himalayas-App/remote-jobs-api/blob/main/openapi.json ; https://aidevboard.com/docs

### Documentation freshness correction — Himalayas pagination

The current official API landing page explicitly marks offset as deprecated and recommends cursor pagination (nextCursor returned by /jobs/api passed back as cursor). The public OpenAPI artifact and Python example still use offset, so treat them as stale/not synchronized with the current landing-page guidance rather than as an equally current unresolved contract. For the future pilot, browse pagination should follow the current landing page; filtered search uses the documented 1-based page parameter.

Add a documentation-freshness fixture:
| Test ID | Fixture | Expected result | Failure condition |
|---|---|---|---|
| SV-030 | Himalayas current landing page vs older OpenAPI/example pagination guidance | Prefer current explicit guidance: cursor for browse; page for filtered search. Record older offset examples as documentation drift and do not start a full-feed sync merely to test feasibility | Implementing deprecated offset pagination based only on the stale example, or claiming the API is broken because docs disagree |

References: https://himalayas.app/api ; https://github.com/Himalayas-App/remote-jobs-api/blob/main/openapi.json ; https://github.com/Himalayas-App/remote-jobs-api/blob/main/examples/python.py

The pagination choice is now sufficiently documented for a later bounded implementation proof, but live filtered result retrieval and source-quality gates remain unverified.

### SV-032 — Partial source failure and safe resume

| Test ID | Fixture | Expected result | Failure condition |
|---|---|---|---|
| SV-032 | A scheduled run has one source return valid records while another source times out, is rate-limited, or fails schema validation; some previously seen listings are absent from the partial result | Record each source outcome separately; retain prior listing state unless a fresh canonical check proves a status change; retry only within source limits; resume idempotently without duplicate records or notifications | Partial results are treated as a complete snapshot, omitted listings are marked closed, an error is reported as a valid empty result, or a retry duplicates records/side effects |

This test is derived from the selective n8n workflow review: batching, ID-cache and error-handler patterns are useful concepts, but the product must not let a partial run corrupt vacancy state. It is a future acceptance test only; no implementation is authorized.

### SV-033 — Current application form does not prove vacancy is open

| Test ID | Fixture | Expected result | Failure condition |
|---|---|---|---|
| SV-033 | Official employer listing has a current-looking application form but only an older posting date and no explicit current-open statement or deadline | Preserve status as unknown; record the page timestamp, route evidence and unresolved fields separately. A visible form can support “application route observed,” not “vacancy confirmed open.” | Promoting the listing to open solely because the page or form still renders, or fabricating a deadline, compensation, eligibility or permission status |

This fixture is grounded in the WATER ML Intern page checked 2026-10-13: the page is dated 2026-08-24 and displays an application form, but the retrieved content does not explicitly confirm current open status. It is a future acceptance test; no application was submitted and no candidate data was sent.

### SV-034 — Source error is not a valid empty result

| Test ID | Fixture | Expected result | Failure condition |
|---|---|---|---|
| SV-034 | A source fetch fails, returns an invalid payload, or throws while another source returns records | Emit a distinct per-source error outcome; distinguish transport, rate-limit, schema and permission errors from a successful empty response; preserve prior listing state unless canonical evidence changes it | Logging the error but returning an indistinguishable empty list, reporting a complete successful run, or closing/overwriting records based on missing partial results |

### SV-035 — Verification uncertainty must not become live status

| Test ID | Fixture | Expected result | Failure condition |
|---|---|---|---|
| SV-035 | Canonical job URL returns 403, times out, has DNS failure, or raises an unexpected verification exception | Set status to unknown/unverified with the exact verification outcome; exclude it from verified-open counts until a successful canonical check or authoritative status evidence exists | Treating access/network failure as live/open or suppressing the uncertainty note |

### SV-036 — Ambiguous work mode and incomparable compensation

| Test ID | Fixture | Expected result | Failure condition |
|---|---|---|---|
| SV-036 | “Remote” appears in prose without a clear work arrangement; country restrictions are missing; salary is given in a different currency or pay period from candidate preferences | Preserve the original text and separate evidence fields; keep country eligibility unknown where unproven; compare compensation only after currency and period are known/normalized | Inferring worldwide eligibility from the word remote, or comparing raw salary numbers across currencies/hourly/monthly/annual periods |

### SV-037 — Public endpoint is not source permission

| Test ID | Fixture | Expected result | Failure condition |
|---|---|---|---|
| SV-037 | An open-source adapter targets a public/keyless provider endpoint whose terms/policy review is blocked or unresolved | Keep the adapter disabled and exclude the source from coverage counts until the source-specific permission gate is cleared | Treating endpoint accessibility, a public API, or an upstream repository's use as authorization |



### SV-038 — Canonical requisition deduplication without losing provenance

| Test ID | Fixture | Expected result | Failure condition |
|---|---|---|---|
| SV-038 | Multiple discovery records from employer boards/aggregators share an exact canonical requisition URL; a separate case has two role tracks sharing only a general careers page | Collapse exact same-requisition observations to one vacancy for counts and ranking, retain each source observation and provenance for source-agreement/quality metrics, and avoid merging different requisitions merely because they share a general careers URL. If distinctness cannot be established, keep the vacancy count unresolved and surface the ambiguity. | Counting exact canonical duplicates as separate vacancies; deleting provenance/control rows; merging distinct role tracks solely because they share a careers page; or promoting unknown status because one duplicate record says open |
  
This fixture is grounded in the 2026-10-13 CSV audit: seven groups share the same role/requisition URL (Ema, Atlys, CertifyOS, RIVR, Barnes & Thornburg, Formstack, and ATRISI), while two Zyora Labs role-track records share a general careers page and cannot safely be classified as one or two active vacancies from URL equality alone. It is an acceptance requirement only; no implementation is authorized.


### SV-039 — Recent search snippet with unreadable canonical page

| Test ID | Fixture | Expected result | Failure condition |
|---|---|---|---|
| SV-039 | Official-employer search result shows a recent posting and Apply link, but opening the canonical page through the available retrieval interface yields no readable content | Store the snippet as provisional discovery evidence; retain `unknown` status and unresolved eligibility fields until canonical evidence is available. Keep the exact URL, observation date and retrieval limitation. | Promoting to verified-open/eligible based only on the search snippet, inventing missing requirements, or treating a tool retrieval limitation as proof the employer page is unavailable/closed |

This case is grounded in the Walmart and Unisys Workday recheck on 2026-10-13. It is a source-evidence quality test, not proof that either employer page is actually broken. See [independent employer sample pilot](independent-employer-sample-pilot-2026-10-13.md).


### SV-039 follow-up — explicit global-remote language still does not clear permission

The Threxil Systems pages checked on 2026-10-13 explicitly state “work from anywhere,” identify two open roles, and welcome freshers/self-taught developers on the individual role pages. That is stronger work-location and role-status evidence than a bare “remote” label or a form alone. It still does not establish every jurisdiction's legal/work-authorization eligibility, compensation/duration, employer legitimacy, or permission for automated collection, caching, autofill, or submission. Keep those dimensions independent; retain human review and do not infer source permission from public visibility.

References: https://www.threxil.com/careers ; https://www.threxil.com/careers/apply/ai-intern ; https://www.threxil.com/careers/apply/frontend-ai-intern


### International-remote sample expansion — evidence tiers

Add the following records to the next human-labelled source-quality evaluation:

- **INT-023 MailerMen:** official employer-hosted listing says Remote (Worldwide), Actively hiring, freshers only, and was updated on 2026-10-13. Record as explicit worldwide eligibility evidence while keeping source permission unresolved.
- **INT-024 QovaTech:** official career page says open internship and remote-friendly; applicant-country eligibility is not stated. Do not infer worldwide eligibility from the company serving clients worldwide.
- **INT-025 DataRobot:** official Workday result lists Remote Canada-Ontario and US offices; direct page retrieval was unreadable. Preserve unknown status and treat geography as a negative control.

These three rows extend the international remote comparison but do not close the 25-listing segment or the overall source-quality gate. A public employer page, an active form, and permission to automate remain three separate questions.


### SV-040 — Remote label with a restricted employment-country list

| Test ID | Fixture | Expected result | Failure condition |
|---|---|---|---|
| SV-040 | A role is labelled remote but the employer lists a finite set of employment locations that excludes the candidate's country, or requires work authorization in the country of employment | Preserve `remote` as work mode while independently recording the explicit country/location whitelist and work-authorization rule; classify the candidate as ineligible or eligibility-unconfirmed based on evidence. Do not infer global eligibility from remote work. | Treating remote as worldwide, ignoring a listed-country restriction, or recommending the role to a candidate outside the supported locations without an explicit exception. |

Grounded in the Cohere Research Internship (Winter 2027) page (remote; Canada/Europe/UK/US locations; PhD-level research eligibility and work authorization required) and Zolve's 2026 program page (US-based degree eligibility; applications closed). This is an acceptance test only; no implementation is authorized.


### SV-041 — Public API terms, attribution, and rate limits are independent acceptance checks

| Test ID | Fixture | Expected result | Failure condition |
|---|---|---|---|
| SV-041 | A public GitHub repository documents a job API and describes sharing/attribution conditions, request limits, delays, or restrictions on redistribution | Record the provider's current official terms and allowed use separately from endpoint mechanics; preserve required canonical links/attribution; respect rate limits and delay; keep the source unapproved until intended product use is confirmed to fit the terms | Treating public/keyless access as permission; omitting required attribution; exceeding stated rate guidance; redistributing where prohibited; or approving a source before its intended use is reviewed |

Grounded in the Remotive Remote Jobs API repository, checked 2026-10-14. Its README documents a 24-hour delay, recommends at most four requests per day, requires a canonical Remotive link and source attribution, and prohibits submitting its listings to third-party job websites. This test is a research acceptance requirement only; no API request or connector is authorized.

### SV-042 — Dataset license, source provenance, and freshness are separate

| Test ID | Fixture | Expected result | Failure condition |
|---|---|---|---|
| SV-042 | A public repository offers a job dataset/snapshot with a repository-level license, but the collection method, upstream source permissions, timestamps, or currentness are incomplete | Keep the dataset out of the production/seed corpus until license, provenance, collection permissions, timestamps, and intended use are reviewed. Historical snapshots may be used only as clearly labeled research fixtures after review; never count them as currently open jobs | Assuming a public repository or CC0/MIT label resolves upstream source rights; treating a stale snapshot as live; or adding unreviewed records to vacancy/coverage counts |

Grounded in the Open Jobs repository, whose README says the live service stopped on 2026-10-10 and its last snapshot was built on 2026-10-05. Its freshness categories are useful research ideas, but this audit did not import or query its dataset. This is an acceptance requirement only; no dataset or implementation is authorized.


### SV-043 — Cursor traversal, canonical URL validation, and partial export integrity

| Test ID | Fixture | Expected result | Failure condition |
|---|---|---|---|
| SV-043 | A future authorized API adapter paginates with cursors; a cursor repeats/expires, a record has an invalid/non-canonical source URL, or a page request fails mid-export | Bound page sizes; preserve filters across pages; detect repeated/expired cursors; validate source URLs against the provider's documented canonical URL pattern; deduplicate by provider ID without losing source sightings; surface a failed/partial run explicitly and never present it as a complete snapshot. A new traversal is required after cursor expiry. | Infinite/repeated-page loops, accepting arbitrary or malformed links as canonical, silently returning partial results as complete, deleting provenance during deduplication, or treating missing records as closed |

Grounded in the Jobicy API examples repository (https://github.com/Jobicy/jobicy-api-examples), whose Python client documents provider-ID deduplication, Jobicy URL validation, repeated-cursor rejection, cursor expiry, and stopping exports on HTTP failures. This is a future acceptance test only; no adapter, dependency, or live endpoint call is authorized.


## 2026-10-14 baseline refresh note

The source-audit CSV now contains 82 records. The 25-record international-remote explicit-geography comparison target is met for research purposes, with one additional Yotta Labs record retained as a contradictory-geography control and excluded from that target count. This does not establish 25 current open vacancies, candidate eligibility from India, or permission to automate any source. The source-quality gate remains unpassed; the next gate work is record-level freshness/status/eligibility review, source permission confirmation, and measured acceptance metrics.


### SV-044 — Acceptance-gate denominators and evidence tiers

| Test ID | Fixture | Expected result | Failure condition |
|---|---|---|---|
| SV-044 | A source-quality report aggregates a mixed audit CSV containing vacancies, duplicate source observations, negative controls, category/feed rows, stale records, and unresolved statuses | State the denominator and inclusion rules for each metric; count exact requisitions once; exclude non-listings and comparison controls from the eligible-vacancy numerator; report `unknown` separately; distinguish canonical-page readability from HTTP/link validity; provide dated evidence for status, eligibility, role relevance, and source permission. Mark a criterion unmeasured when evidence does not support a numeric result. | Counting mixed rows as vacancies, using page visibility as proof a role is open, treating a JS shell as a dead link or a readable page as a valid application route without evidence, hiding unresolved permission blockers, or declaring the gate passed from sample size alone. |

Assessment record: [Source-Quality Gate Assessment — 2026-10-14](source-quality-gate-assessment-2026-10-14.md). The current decision is **NOT PASSED**: structural CSV checks pass, but the valid/relevant listing threshold and permission gate fail or lack sufficient evidence; the direct-link rate and full worldwide-eligibility audit remain unmeasured. This test is a research acceptance requirement only; no implementation is authorized.


### 2026-10-14 — conservative status correction after canonical recheck

Rechecked five records against canonical URLs: Drivetrain (IN-002), Ema (IN-003), Ema aggregator comparison (INT-008), Sprinto (IN-022), and Airbus (IN-025). Drivetrain and Sprinto returned readable job descriptions and Apply routes but no explicit current-open wording; Ema returned only a JavaScript shell; Airbus returned no readable lines. Because an Apply route or a search snippet alone is not proof of current availability, all five records were changed to `unknown` and their `last_checked_at` dates updated to 2026-10-14. INT-008 remains a duplicate/source-comparison observation for IN-003, not a second vacancy.

Post-correction baseline: 82 records, 27 columns, 0 malformed rows, 0 duplicate IDs; `open` 10, `unknown` 61, `expired` 3, `closed` 2, `not_a_listing` 2, `source_review` 4. The source-quality gate remains NOT PASSED.


### SV-045 — Current status and applicant geography must be explicit evidence fields

| Test ID | Fixture | Expected result | Failure condition |
|---|---|---|---|
| SV-045 | A canonical employer page is readable and has an Apply form, but no explicit current availability wording; or a page says “remote-friendly/serving clients worldwide” without an explicit applicant-country policy | Keep availability `unknown` unless the employer explicitly lists the role as open/actively hiring or gives equivalent current evidence. Keep applicant-country eligibility `unknown` unless the employer explicitly states eligible countries/regions or worldwide applicants. Keep legal/work authorization separate from work mode. | Treating an Apply button as proof of open status, or “remote”, “remote-friendly”, “work from anywhere” without jurisdictional context, or “serving clients worldwide” as proof of legal applicant eligibility in every country. |

Applied in the 2026-10-14 follow-up review: Trackmind was downgraded to unknown due to contradictory employment-type/experience text; RadialBrain, Inferova and WATER remain unknown despite visible application forms; Threxil has explicit open-role evidence; MailerMen explicitly states actively hiring and worldwide applicants; QovaTech says “Open internship” but does not establish applicant-country eligibility. See [Candidate-Relevant Record Review](candidate-relevant-record-review-2026-10-14.md). This is a research acceptance requirement only; no implementation is authorized.


### SV-046 — Shared careers pages, duplicate observations, and track ambiguity

| Test ID | Fixture | Expected result | Failure condition |
|---|---|---|---|
| SV-046 | Two advertised internship tracks share one general careers/application page; or a stored role title does not match the current employer page's internship/full-time entries | Preserve both track observations and provenance, but do not count separate unique vacancies until evidence distinguishes requisitions. Keep status "unknown" when the stored title cannot be mapped reliably to a current canonical role. An explicit employer-index “Open” label may support an "open" status for the advertised role, but does not resolve unique requisition count or source permission. | Counting shared-page tracks as distinct confirmed vacancies without evidence; conflating internship and full-time roles; treating an open role page as permission for product ingestion or applicant-data collection. |

Applied 2026-10-14: ATRISI's index explicitly marks ML / AI Intern Open, while IN-028 remains a duplicate observation of IN-020; Zyora's two tracks are explicitly advertised as open but share a general careers page, so distinct requisition count is unresolved; Onelogica's current page separates an AI Engineer internship from a full-time Data & AI Engineer GenAI Platforms role, so the CSV title mapping remains unknown. Current CSV baseline: 82 records, 27 columns, 0 malformed rows, 0 duplicate IDs; statuses "open" 13, "unknown" 58, "expired" 3, "closed" 2, "not_a_listing" 2, "source_review" 4; permission "unknown" 77. The source-quality gate remains NOT PASSED and no implementation is authorized.


### SV-047 — Role title must agree with employment-type metadata

| Test ID | Fixture | Expected result | Failure condition |
|---|---|---|---|
| SV-047 | Canonical employer page title includes “Intern” but Employment Type / Job Type says “Full time”; or eligibility fields omit the candidate's degree discipline | Preserve the exact contradiction, keep current status unknown unless there is explicit current-open evidence, and do not infer degree equivalence or internship terms. Ask employer for clarification before recommendation when the mismatch affects eligibility or candidate expectations. | Automatically treating “Intern” in the title as an internship contract, or treating an Apply button as evidence that the vacancy is currently open. |

Applied 2026-10-14: Meraki Labs AI Engineer Intern and AtkinsRéalis Robotics & AI Engineering Intern both display Full time employment metadata despite internship titles; Concentric AI lists an ML Intern role but labels Job Type Full-time. GM's listed eligible degree fields do not explicitly name ECE and its page states no immigration-related sponsorship for the role. Needl.ai and vINe AI have explicit employer careers-page open-position evidence; neither has product/source permission approval. Latest CSV baseline: 82 records, 27 columns, 0 malformed rows, 0 duplicate IDs; statuses open 15, unknown 56, expired 3, closed 2, not_a_listing 2, source_review 4; permission unknown 77. Gate remains NOT PASSED / research-only.
