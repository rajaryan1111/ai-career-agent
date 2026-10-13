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
| Status: `open` | 10 | Not equivalent to confirmed-open unique jobs |
| Status: `unknown` | 61 | Must remain unknown until evidence resolves it |
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
