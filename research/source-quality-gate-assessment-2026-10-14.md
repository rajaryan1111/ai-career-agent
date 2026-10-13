# Source-Quality Gate Assessment — 2026-10-14

**Decision: NOT PASSED — remain research-only.**  
**Scope:** Current audit seed, the completed explicit-geography international-remote comparison, and a small record-level direct-link spot check. This is an acceptance assessment, not a production authorization.

## Executive decision

The sample is structurally clean enough to continue auditing, but the evidence does not support opening the implementation gate. The international-remote comparison target is complete as a geography-control sample; it is not a set of 25 verified-open jobs or 25 jobs eligible to an India-based undergraduate. Current availability, complete candidate eligibility, direct-link validity at the required rate, and source permission have not been established across a sufficiently large relevant set.

## 1. Baseline integrity — PASS for structure only

Re-parsed `research/job-source-audit-seed-2026-10-13.csv` on 2026-10-14.

| Structural check | Observed | Decision |
|---|---:|---|
| Data records | 82 | Informational |
| Columns per record | 27 | Pass |
| Malformed-width rows | 0 | Pass |
| Duplicate listing IDs | 0 | Pass |
| Distinct canonical URL values | 73 | Informational |
| Repeated canonical-URL groups | 8 | Needs record-level handling |
| Status: `open` | 9 | Not equivalent to confirmed-open unique jobs |
| Status: `unknown` | 62 | Must remain unknown until evidence resolves it |
| Status: `expired` | 3 | Suppress unless new requisition/status evidence appears |
| Status: `closed` | 2 | Suppress |
| Status: `not_a_listing` | 2 | Exclude from vacancy counts |
| Status: `source_review` | 4 | Exclude from vacancy counts |

The five status changes described in the follow-up review were made because current canonical inspection showed only an Apply route, a JavaScript shell, or no readable page—not explicit current-availability evidence. The 8 repeated URL groups consist of 7 exact-requisition/source-observation groups and one shared general-careers-page ambiguity. Preserve source provenance; do not count exact duplicate observations as additional vacancies. Do not merge the two Zyora Labs tracks solely because they share a general careers URL. These URL counts are not a current-open vacancy count.

## 2. Required acceptance gates

| Gate | Evidence observed | Decision |
|---|---|---|
| At least 20 valid, relevant listings for the initial candidate segment | Not demonstrated. The 82 rows mix stale/unknown records, geography and seniority negatives, duplicate observations, source-review rows and non-vacancy controls. Under a strict first-pass screen, only a very small subset has both directly readable canonical evidence and explicit current-availability evidence; the count is far below 20. | **FAIL / insufficient evidence** |
| At least 90% valid direct links | A bounded browser spot check opened 13 canonical URLs: 9 pages returned readable role content, 3 returned a JavaScript shell or no readable page content (Ema, CertifyOS, Airbus), and one request returned an internal error (Azul). This is a browser-readability proxy, not a definitive HTTP/link-validity measurement. The required link-validity denominator and status codes have not been measured across the intended sample. | **UNMEASURED; do not claim pass** |
| Zero false worldwide-eligibility claims | The records correctly preserve the Yotta Labs contradictory “Remote (Global)” versus finite location header as a control, and QovaTech applicant-country eligibility remains unknown. However, all records have not been re-audited against a single formal claim-level checklist. | **UNMEASURED; no known contradiction promoted to worldwide eligibility** |
| No unresolved source permission/attribution blockers | Permission field counts: 77 `unknown`; the remaining five are documented-read/feed/third-party statuses whose product approval or terms review is explicitly unresolved. No source is approved for automated collection, caching, autofill, or submission by this audit. | **FAIL** |
| Candidate eligibility and current status are independently verified | 56 records remain `unknown`; the `open` label alone is not a current recommendation. Degree/year, location/work authorization, and status remain missing or ambiguous on many records. | **FAIL / incomplete** |
| Duplicate identity and provenance preserved | Eight repeated-URL groups remain. Most are documented as comparison controls, but exact-requisition groups must continue to count once; the shared Zyora careers page remains unresolved as to separate active requisitions. | **PARTIAL; not a gate pass** |

### Direct-link spot-check details

Checked on 2026-10-14 using the research browser, against these canonical URLs:

- Readable role content: [Drivetrain](https://jobs.lever.co/drivetrain/bc1c17bc-86ac-4f00-a1e3-0eb85aae4fdc), [Sprinto](https://jobs.lever.co/Sprinto/6dfd5f41-57b6-40e8-9eab-ba4083c1a7c4), [RadialBrain](https://www.radialbrain.com/interns), [Inferova](https://inferova.com/careers-ai-ml), [Threxil AI Intern](https://www.threxil.com/careers/apply/ai-intern), [Threxil Frontend + AI Intern](https://www.threxil.com/careers/apply/frontend-ai-intern), [MailerMen](https://www.mailermen.com/jobs/machine-learning-intern-python-scikit-learn-remote-worldwide-280), [QovaTech](https://www.qovatech.com/careers/ai-engineer), [WATER](https://www.water.bio/careers/WR012).
- Canonical page returned only a JavaScript shell: [Ema](https://jobs.ashbyhq.com/ema/e0511c0c-998f-4079-b62c-d2f164bf2c86), [CertifyOS](https://jobs.ashbyhq.com/certifyos/4bcdec99-9f2e-416c-8e26-498c94c5898a).
- No readable lines returned: [Airbus](https://ag.wd3.myworkdayjobs.com/en-US/Airbus/job/Internship---India-Innovation-Team---GenAI-Intern_JR10446597).
- Research-browser internal error: [Azul](https://jobs.lever.co/azul/f94d4087-2dee-4d69-8596-883ff17efde2).

A JavaScript shell, unreadable page, or tool error does not prove that the URL is dead; it means the role's canonical content could not be independently verified through this check. Conversely, a readable page or visible Apply control is not proof the vacancy is open.

## 3. International remote comparison — SAMPLE TARGET MET, NOT JOB-QUALITY GATE

The pilot report records 67 unique role-like canonical URLs: 38 India-focused records including negative controls, 26 non-India remote comparison records including geography/freshness controls, and 3 other location/work-mode cases. Of the 26 remote-comparison records, 25 have explicit listed country/region evidence; the Yotta Labs contradiction control is excluded from the 25-record target.

This meets the planned comparison-sample target only. It does **not** establish 25 currently open vacancies, 25 roles suitable for an India-based undergraduate, or permission to use the underlying source programmatically.

## 4. What can and cannot be concluded

**Supported now**
- CSV structure and identifier uniqueness pass.
- The comparison sample has enough explicit-geography examples to test restricted-remote handling.
- The dataset contains concrete negative controls for expired/closed roles, PhD-only roles, US/Canada-only remote roles, source/role category pages, and duplicate observations.
- The reviewed records preserve several important unknowns rather than converting them to positive claims.

**Not supported yet**
- A claim that 20 valid, relevant, currently available listings have been verified.
- A measured direct-link validity rate of at least 90%.
- A complete audit proving zero false worldwide-eligibility claims.
- Approval of any source for automated collection, caching, autofill, or application submission.
- Claims of representative coverage, recall, precision, or that the sample reflects the whole internship market.

## 5. Next bounded work

1. Re-review only the candidate-relevant India/explicit-worldwide subset, one record at a time. Capture canonical page evidence, current status wording/date, exact location/work authorization, degree/year/experience, role-family fit, direct apply route, and source terms.
2. Reclassify status from evidence, not from an old CSV label or a visible form alone. Keep `unknown` when a page is unreadable or evidence conflicts.
3. Measure direct-link validity using an explicit denominator and actual response outcomes; keep browser readability as a separate field.
4. Resolve source terms for the intended product use before any live feed/API query, cache, connector, or automated collection.
5. Recompute unique, candidate-relevant records after exact-requisition deduplication. Keep comparison controls outside the eligible-job numerator.
6. Reassess all gate criteria with evidence and dated results. Do not implement until every hard gate passes.

## 6. Safety and implementation boundary

No source API endpoint was queried for this assessment. No code, dependencies, connector, workflow, credentials, dataset import, candidate-data transfer, autofill, or application submission was added or performed. The source-quality and implementation gates remain closed.


## 7. Follow-up candidate-relevant record review — 2026-10-14

See [Candidate-Relevant Record Review](candidate-relevant-record-review-2026-10-14.md). The current canonical pages were rechecked for India-focused Trackmind, RadialBrain, Inferova and WATER records, plus explicit-worldwide/remote controls Threxil (two roles), MailerMen and QovaTech. Trackmind was downgraded to `unknown` because its page contradicts itself (Internship heading vs Full-Time work details and a 6-month-to-2-year experience requirement). RadialBrain, Inferova and WATER remain `unknown`: their pages describe the internships and show application forms, but this check did not find explicit current-open wording. Threxil's careers page explicitly lists two roles open and work from anywhere; MailerMen explicitly says actively hiring and open to applicants anywhere; QovaTech explicitly says “Open internship” but does not establish applicant-country eligibility.

Post-review CSV baseline: 82 records, 27 columns, 0 malformed rows, 0 duplicate IDs; `open` 9, `unknown` 62, `expired` 3, `closed` 2, `not_a_listing` 2, `source_review` 4. Permission field remains `unknown` for 77 rows. This bounded review does not close the ≥20 valid/relevant listings gate, the ≥90% direct-link validity metric, full worldwide-eligibility audit, or source-permission gate. Decision remains **NOT PASSED / research-only**.


## 8. Second India-focused candidate-record recheck — 2026-10-14

See [Candidate-Relevant Record Review](candidate-relevant-record-review-2026-10-14.md). ATRISI's official careers index explicitly labels its ML / AI Intern role “Open”; Zyora Labs' official page labels its student internship section “Open internships”. Their CSV status labels were updated accordingly, with conservative caveats: ATRISI IN-028 is a duplicate observation of IN-020; Zyora's two advertised tracks share one careers page and are not confirmed as distinct requisitions. The candidate should review Zyora's broad confidentiality/work-product ownership terms before agreeing. Hajana remains unknown because the careers index does not explicitly label current availability and its stated cohort eligibility is restrictive. CertifyOS and Walmart remain unknown because an Apply route / recent search result is not equivalent to explicit current-open evidence. Onelogica remains unknown because the stored CSV role title conflates two different entries on the current employer page.

Latest verified audit CSV baseline after this pass: 82 rows, 27 columns, 0 malformed rows, 0 duplicate IDs, 73 distinct canonical URLs, 8 repeated-URL groups; status labels: 13 open, 58 unknown, 3 expired, 2 closed, 2 not_a_listing, 4 source_review. Permission field remains unknown on 77 rows. These labels are mixed audit observations, not 13 unique eligible vacancies; duplicate/shared-page rows must be excluded or resolved before the candidate-relevant unique count is calculated.

**Decision remains NOT PASSED / research-only.** The ≥20 unique relevant currently available listings threshold is not demonstrated; ≥90% direct-link validity remains unmeasured using a proper response-outcome denominator; worldwide/applicant-country claims are not fully audited; source terms/permission remain unresolved. No API endpoint was queried, no code or dependencies were added, no candidate data was transferred, and no application was submitted.


## 9. Third bounded India-focused recheck — 2026-10-14

See [Candidate-Relevant Record Review](candidate-relevant-record-review-2026-10-14.md) for the evidence table covering General Motors, Meraki Labs, Sarvam, vINe AI, AtkinsRéalis, Needl.ai and Concentric AI. The CSV now records explicit employer careers-page “Open Positions” evidence for vINe AI (IN-027) and Needl.ai (IN-031). GM, Meraki, Sarvam, AtkinsRéalis and Concentric remain unknown because current-open evidence is not sufficient or role-type/eligibility ambiguities remain. In particular, the GM posting states no immigration-related sponsorship and ECE is not explicitly in the listed degree fields; Meraki and AtkinsRéalis have full-time employment metadata despite intern titles; Concentric has an internship/full-time metadata tension; Sarvam's indexed page is stale.

Latest CSV integrity: 82 rows, 27 columns, 0 malformed rows, 0 duplicate IDs, 73 distinct canonical URL values, 8 repeated-URL groups. Statuses: 15 open, 56 unknown, 3 expired, 2 closed, 2 not_a_listing, 4 source_review. Permission field remains unknown for 77 rows. These are mixed audit observations, not unique candidate-ready jobs.

**Decision: NOT PASSED / research-only.** The ≥20 unique, relevant, currently available vacancy threshold remains unproven; ≥90% direct-link validity is unmeasured with a valid response-outcome denominator; full applicant-country/worldwide eligibility audit and source permission remain unresolved. No source API was queried and no code, dependencies, connectors, candidate-data transfer, autofill or application submission was performed.


## 10. Fourth candidate-focused status check — 2026-10-14

The current official Humans Care Foundation careers index says it is accepting applications for five open roles, including J01 AI / Machine Learning Engineer; the role page describes a paid, one-month initial internship remote anywhere in India. The employer separately describes a ₹500 two-week traineeship as training rather than a job, so those offers must remain distinct. The official AICTE portal still lists EduRankAI Deep Learning Engineering Intern with an apply-by date of 2027-03-02, three-month duration and ₹0/month stipend. CSV records IN-008 and IN-009 were updated to open based on explicit current evidence; eligibility, compensation details, privacy and source permission remain unresolved.

Latest CSV baseline: 82 rows, 27 columns, 0 malformed rows, 0 duplicate IDs, 73 distinct canonical URLs, 8 repeated-URL groups. Statuses: 17 open, 54 unknown, 3 expired, 2 closed, 2 not_a_listing, 4 source_review. Permission remains unknown for 77 rows. These are mixed audit observations, not unique candidate-ready jobs.

**Decision remains NOT PASSED / research-only.** The 20 unique relevant current-vacancy threshold, measured direct-link validity, full applicant-country audit and source terms remain unresolved. No source API was queried and no production integration was added.


## 11. Fifth candidate-focused status check — 2026-10-14

The current official Sprinto Lever careers board lists AI Implementation Intern under AI Office with Remote workplace and an Apply route. The canonical role page gives AI infrastructure, evaluation pipelines, document parsing, search and LLM integration responsibilities, and asks for a currently pursuing degree in CS, Engineering, Data Science or related technical field. CSV record IN-022 is updated to open; Bengaluru/Remote is not proof of worldwide eligibility, and duration, compensation and source/product permission remain unknown.

The Drivetrain employer board also currently lists its India-based remote GenAI internship. IN-002 was updated to open. This brings the audit to 18 open-labelled rows. This is still not a candidate-ready count: candidate eligibility and role-level terms differ, duplicates remain, and permission is unknown for most rows. Unisys AI Engineering Intern explicitly targets current/recent M.Tech candidates, so it should not be treated as a direct fit for the BTech ECE target. Concentric AI and AtkinsRéalis both have title/employment-type or degree-eligibility ambiguities and remain unknown.

**Gate remains NOT PASSED / research-only.** No source APIs queried, no production integration or dependency added, no candidate data sent, and no application submitted.


### Count reconciliation after CSV re-fetch — 2026-10-14

The just-re-fetched CSV confirms **19 open-labelled records**, not 18: the earlier baseline was 17 and IN-002 plus IN-022 were subsequently updated to open. Current status counts are open 19, unknown 52, expired 3, closed 2, not_a_listing 2, source_review 4. CSV remains 82 rows × 27 columns, 0 malformed rows, 0 duplicate IDs, 73 distinct canonical URLs, and 77 rows with unknown permission. This is a correction to the count above; it does not change the NOT PASSED / research-only decision.


## 12. Sixth candidate-focused recheck — 2026-10-14

The current official Needl.ai careers index lists AI Engineering Intern under open positions. The role is Bengaluru hybrid (three days/week in office), mentions a monthly stipend without an amount, and targets recent graduates with B.Tech/M.Tech or equivalent in CSE/EE/related or candidates with 1–2 years of experience. Existing IN-031 remains `open`; the current BTech ECE student's cohort/degree eligibility is not confirmed. No email was sent.

Threxil's current official careers page states “2 roles open”, “Fully remote”, “Work from anywhere”, and lists AI Intern and Frontend + AI Intern; the page welcomes freshers/self-taught candidates. Existing INT-021/INT-022 remain `open`. The phrase “work from anywhere” is not conclusive evidence of legal hiring, payroll, tax or work-authorization eligibility in every country. Applicant-data privacy and source/product permissions remain unresolved.

For candidate triage, Threxil AI Intern and Sprinto AI Implementation Intern merit careful manual review; HCF is a potential India-remote paid internship lead but exact stipend and eligibility remain unclear. Drivetrain and Needl.ai require explicit confirmation of ECE/current-student eligibility. EduRankAI remains materially unattractive as a paid opportunity (listed ₹0/month, full-time, three months) and still requires legitimacy/workload checks. These judgments are lead-prioritization only, not eligibility determinations.

**Gate remains NOT PASSED / research-only.** 77 records still have permission unknown; current page availability does not authorize crawling, caching, republication or automation. No candidate data was sent and no applications were submitted.


## 13. Source-permission decision matrix — 2026-10-14

Added [Source Permission Decision Matrix](source-permission-decision-matrix-2026-10-14.md) after reviewing current official terms for Jobicy, Remotive and AI Dev Jobs. Jobicy's public Remote Jobs API is the strongest first-adapter candidate because its current documentation explicitly permits normal product integrations without individual permission, provided Jobicy attribution and the canonical Jobicy URL are retained. The free endpoint is read-only and does not guarantee a direct employer ATS URL; the commercial direct-link endpoint can incur $0.01 per eligible job and requires a wallet, so it is excluded from the no-mandatory-cost MVP unless separately approved. The feed is limited to listings published in the last seven days; absence from the feed is not proof a job closed. Automated polling must not exceed once per hour; a few checks/day are recommended.

Remotive remains conditional because its feed is delayed 24 hours, attribution/linking are required, and its terms prohibit gating displayed listings behind sign-up/email capture. AI Dev Jobs remains conditional pending clarification of attribution, caching and product-display details. Himalayas remains blocked pending terms clarification; JobSpy remains rejected due to proxy-based anti-blocking guidance. Public employer pages continue to be used for manual evidence only unless source-specific terms permit intended collection/use.

This is a meaningful source-permission improvement but **does not pass the overall source-quality gate**. No endpoint was queried, no connector or production code was added, and no candidate data or applications were submitted. Next step is to finalize the proposed candidate-facing flow and data fields, then decide whether to authorize a read-only Jobicy adapter under the matrix conditions.


## 14. MVP scope and data contract drafted — 2026-10-14

Added [MVP Scope and Data Contract](mvp-scope-and-data-contract-2026-10-14.md) to define the candidate-facing flow, local-only candidate profile/tracker, listing provenance, separate source/employer URLs, three-valued eligibility (`pass`/`fail`/`unknown`), status semantics, privacy/security boundaries, and measurable acceptance tests. This is a design artifact only, not production implementation. It deliberately excludes resume upload, cloud sync, paid APIs, scraping, browser automation, autofill and application submission.

The current path toward programming is now specific: (1) approve the MVP flow and data contract, (2) complete the 50-record validation sample (25 India-focused and 25 international-remote), (3) measure direct employer link outcomes and audit eligibility claims, (4) confirm source permissions for each exact adapter, then (5) explicitly authorize a single read-only Jobicy public API adapter and test it end-to-end. Jobicy remains the leading candidate, not an already-integrated source; no API endpoint was queried. The overall gate remains **NOT PASSED / research-only** until those checks are evidenced.


## 15. Consolidated batch research pass — 2026-10-14

A fresh public-web pass added Valura.AI's AI Engineering Intern (Python) as IN-036 with status `unknown`: the official page shows a 2026-07-27 post date, Chennai/GIFT City/Remote, 3–6 months (full-time preferred), 0–3 years, and a technically relevant agent/RAG/evaluation stack, but this pass did not capture explicit current-open wording or complete degree/applicant-country eligibility. RadialBrain's official page confirms an India-remote internship track for current students but still does not explicitly establish current intake availability. Unisys's current role asks for current/recent M.Tech candidates and is not a direct fit for the BTech ECE undergraduate target. A Jobicy-hosted Spotify CoLM listing restricts remote locations to the UK, USA and Sweden and is conference-specific, so it is a negative control rather than an India-eligible vacancy. A Flocci search result showed an application close date before this review date and was excluded absent canonical reopening evidence.

Re-fetched CSV baseline after adding IN-036: 83 records, 27 columns, 0 malformed-width rows, 0 duplicate listing IDs, 74 distinct canonical URL values, 8 repeated-URL groups; status counts 19 open, 53 unknown, 3 expired, 2 closed, 2 not_a_listing, 4 source_review; permission unknown for 78 records. The open count remains an audit label count, not a unique eligible vacancy count.

Jobicy's official API documentation continues to support a possible limited read-only integration with source attribution and canonical Jobicy URL preservation. It does not guarantee a direct employer ATS URL; the feed's last-seven-days scope means absence is not proof of closure, and the optional commercial direct-link API can incur per-job cost. **No source API endpoint was queried**, no production code/dependency/connector was added, and no candidate data was transferred.

The 50-record sample (25 India-focused + 25 international remote) remains incomplete; direct-link validity is not measured with a valid response-outcome denominator; the ≥20 unique relevant currently available vacancy threshold is not demonstrated; and the full eligibility/permission audits remain open. Decision: **NOT PASSED — research-only; do not begin production integration.**


## 16. Fixed 50-record QA roster and direct-link probes — 2026-10-14

Added [50-Record Candidate-Validation Roster](50-record-candidate-validation-roster-2026-10-14.md): 25 India-focused plus 25 international-remote rows, one per canonical URL and with explicit negative controls retained. The same GM requisition appears in IN-006/IN-026 locale/parameter variants; only IN-006 is sampled. This completes roster construction, not full validation.

A 2026-10-14 browser probe was attempted for each of the 50 canonical URLs. Three unavailable destinations were observed: Apple IN-001 explicitly says the role does not exist/no longer available; Matrice AI IN-007 returns 404 / Job Not Found (already expired); Bruker IN-033 returned HTTP 410 Gone. IN-030 AtkinsRéalis redirects to the generic jobs search page rather than the stored role. Azul INT-032 returned a browser fetch error without HTTP status and therefore remains unknown. Several JS-rendered Ashby/Workday pages produced a shell/title or no readable body; do not classify these as dead. Apple and Bruker statuses were changed to closed; Matrice remains expired; AtkinsRéalis and Azul remain unknown.

Probe results are not a valid direct-employer application-link success rate. They do not establish that each Apply action works, and some sampled URLs are careers indexes rather than role-deep-links. The ≥90% direct-link target remains **unmeasured** until each actual application destination receives a documented success/failure/unknown outcome and a denominator fixed before calculation.

CSV after re-fetch: 83 records × 27 columns, 0 malformed rows, 0 duplicate IDs, 74 distinct canonical URLs, 8 repeated URL groups; statuses 19 open, 51 unknown, 3 expired, 4 closed, 2 not_a_listing, 4 source_review; 78 rows still have unknown permission. The 50-row roster does not prove 20 unique relevant currently available vacancies, and no source permission has been inferred from a reachable page.

No source API was queried, no production code/dependency/connector was added, no candidate data was transferred, and no autofill/application submission occurred. **Decision remains NOT PASSED — research-only.**


## 2026-10-14 focused application-route spot check

The application-route check is partial and non-representative. Ten routes were examined: four rendered application forms (Drivetrain, Trackmind, Sprinto, CertiK); HCF reached a sign-in gate; Zyora showed an embedded form; Needl.ai published an email route that was not tested; RadialBrain, Valura.AI, and MailerMen remain unknown due to browser/tool limitations. This is not a 50-record success/failure/unknown audit, so no direct-employer-link percentage is reported and the ≥90% criterion remains unproven.

The CSV now records the observed route separately from the canonical listing. No candidate data was entered, no form was submitted, and no email was sent. Source permission remains independent and unresolved for the candidate source set. **Decision remains NOT PASSED — research-only.**


## Latest structural baseline after route instrumentation — 2026-10-14

The re-fetched audit CSV now has **83 rows × 30 columns**, zero malformed-width rows, zero duplicate listing IDs, 74 distinct canonical URL values, and 8 repeated-URL groups. Current status labels are 19 open, 51 unknown, 3 expired, 4 closed, 2 not_a_listing, and 4 source_review; source permission remains unknown for 78 rows. Route outcomes exist for 10 rows, with 73 blank/not checked. This corrects the 27-column snapshots in older dated notes; those lines are historical snapshots, not the current schema. The link-validity percentage is still unmeasured because this was a focused convenience sample, not the fixed 50-record test with a predefined denominator. Gate remains **NOT PASSED — research-only**.
