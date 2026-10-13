# Source CSV Audit — Open-Status Claims and Canonical Evidence

**Audit date:** 2026-10-13  
**Dataset:** `research/job-source-audit-seed-2026-10-13.csv`  
**Purpose:** Check whether existing `open` labels have current canonical evidence, whether canonical/application URLs are missing, and whether duplicate records could inflate the unique-vacancy count. This is a bounded audit, not a production source-coverage test.

## Executive result

- Parsed the committed CSV with a quoted-field-aware CSV parser: **61 data rows, 27 columns, 0 malformed rows, 0 duplicate listing IDs**.
- Status labels remain **8 open, 43 unknown, 3 expired, 2 closed, 1 not_a_listing, 4 source_review**.
- **No blank `canonical_employer_url` fields** and **no blank `apply_url` fields** were found across the 61 rows. This checks field presence, not whether every URL is authoritative, reachable, or permitted for automation.
- There are **8 repeated-canonical-URL groups** across the dataset. These must not be counted as separate unique vacancies without evidence that the records represent different requisitions.
- The eight `open` rows are not eight suitable jobs for an India-based undergraduate: one is explicitly geographically restricted outside India, one has a material experience/employment-type contradiction, and one is a duplicate of another Ema record. Other eligibility fields remain unknown in places.
- No listing was changed to `closed` or `expired` merely because this research interface could not retrieve full page text. Retrieval failure is not evidence that a vacancy is closed.

## Open-status spot checks

| Listing ID | Employer / role | Current check | Decision |
|---|---|---|---|
| IN-002 | Drivetrain — Engineering Intern, Gen AI for FP&A Platform | Canonical Lever page crawled on audit date. It displays India, Internship, Remote, and an Apply link; qualifications and GenAI/RAG scope are visible. | Retain `open`. This verifies an active-looking canonical listing, not permission for automated form submission. |
| IN-003 | Ema — AI/Data Resident | Canonical Ashby URL is present. The current research fetch returned only the JavaScript app shell, so page status could not be independently re-read in this pass. The CSV's same-day prior review says the official page identified India-remote and a final-year/GPA/cohort condition. | Leave `open` based on the recorded same-day evidence, but flag for a successful canonical recheck before any recommendation. Do not treat this retrieval failure as a closure. |
| IN-004 | Trackmind — Junior AI Engineer | Canonical Lever page crawled on audit date and displays an Apply link. The header says Internship, while Work Details says Full-Time and requires 6 months–2 years of experience. | Retain listing-state `open`, but flag the contradiction. Do not recommend as a fresher/internship match until the employment type and experience gate are resolved. The CSV review note was updated. |
| INT-001 | Cohere — Machine Learning Intern/Co-op (Winter 2027) | Canonical Ashby URL is present, but the current fetch returned only the JavaScript app shell. Existing same-day audit notes list eligible geographies as Canada, Europe, UK, and US, excluding India. | `open` is a vacancy-state label only. Do not mark India-eligible; retain as a negative eligibility control pending a successful canonical recheck. |
| INT-004 | Kinaxis — Intern AI/ML Researcher | Canonical iCIMS URL is present. The current research fetch could not retrieve the page. Existing same-day audit notes record a stated application deadline of 2026-10-18 and Canada/Eastern-time-zone restriction. | No status change based on a tool retrieval failure. Recheck canonical status and deadline before recommending; do not infer India eligibility. |
| INT-008 | Ema — AI/Data Resident (aggregator record) | Canonical URL points to the same Ema Ashby requisition as IN-003. The aggregator record's role/seniority metadata conflicts with the official-page description in the existing notes. | Keep only as a source-comparison/duplicate control. **Do not count it as a second unique vacancy.** |
| IN-022 | Sprinto — AI Implementation Intern | Canonical Lever page crawled on audit date. It displays Bengaluru, Remote, an Apply link, responsibilities for AI infrastructure/model pipelines/document parsing/LLMs, and a currently-pursuing-degree requirement. The CSV notes hCaptcha on the application route. | Retain `open`. Country/work-authorization, deadline, pay, and automated-submission permission remain unknown. Stop for human intervention at hCaptcha; do not bypass it. |
| IN-025 | Airbus — India Innovation Team GenAI Intern | Canonical Workday URL is present. The current research fetch returned no page text; the CSV's same-day prior review recorded a page posted 2026-10-11 with an Apply button and six-month duration. | No status change based only on empty retrieval output. Recheck canonical page before recommending; degree/year eligibility and exact work authorization remain unknown. |

### Evidence links from the current recheck

- Drivetrain canonical listing: https://jobs.lever.co/drivetrain/bc1c17bc-86ac-4f00-a1e3-0eb85aae4fdc
- Trackmind canonical listing: https://jobs.lever.co/trackmind/ad66c0ec-1ae9-47cb-9d5d-83ae1cb6d200
- Sprinto canonical listing: https://jobs.lever.co/Sprinto/6dfd5f41-57b6-40e8-9eab-ba4083c1a7c4
- Ema canonical listing: https://jobs.ashbyhq.com/ema/e0511c0c-998f-4079-b62c-d2f164bf2c86
- Cohere canonical listing: https://jobs.ashbyhq.com/cohere/36d1f52f-8270-4652-adf5-5303a0ff341b
- Kinaxis canonical listing: https://careers-kinaxis.icims.com/jobs/35465/job?mobile=true&needsRedirect=false
- Airbus canonical listing: https://ag.wd3.myworkdayjobs.com/en-US/Airbus/job/Internship---India-Innovation-Team---GenAI-Intern_JR10446597

A page that renders or displays Apply is supporting evidence for an application route, but is not, by itself, conclusive proof of an active vacancy. Preserve the evidence source, timestamp, and unresolved fields.

## Canonical URL and duplicate audit

### URL fields

- Missing `canonical_employer_url`: **0/61**.
- Missing `apply_url`: **0/61**.
- `official_page_agreement = yes`: 53 records.
- Other records explicitly remain unknown or source-review cases; a populated URL must not be mistaken for proof of employer-page agreement.

### Repeated canonical URLs

| Canonical requisition / page | Listing IDs | Treatment |
|---|---|---|
| Ema AI/Data Resident | IN-003, INT-008 | One vacancy; retain aggregator row only as source-comparison evidence. |
| Atlys AI Intern | IN-005, IN-014, INT-015 | Resolve as one requisition unless evidence proves otherwise. |
| CertifyOS AI Intern | IN-013, INT-014 | Resolve as one requisition unless evidence proves otherwise. |
| Rivr AI Intern — VLA/Data | INT-011, INT-016 | Resolve as one requisition unless evidence proves otherwise. |
| Barnes 2027 BT RISE AI Intern | INT-012, INT-017 | Resolve as one requisition unless evidence proves otherwise. |
| Formstack AI Intern | INT-013, INT-018 | Resolve as one requisition unless evidence proves otherwise. |
| Zyora Labs careers page | IN-016, IN-017 | Same general careers URL is not sufficient to establish two distinct vacancies; verify separate requisition evidence. |
| Atrisi ML/AI Intern | IN-020, IN-028 | Resolve as one requisition unless evidence proves otherwise. |

These repeated URLs are not duplicate listing IDs, so the original CSV's ID uniqueness check does not detect them. Canonical-URL/requisition-level deduplication is a separate requirement.

## Corrections and remaining work

1. Added an evidence-based note to IN-004 documenting the contradictory internship/full-time and experience information while preserving its observed listing-state label.
2. No other status changes were justified by the available evidence. In particular, incomplete page retrieval for Ema, Cohere, Kinaxis, and Airbus was not treated as proof of closure.
3. Before any source-quality gate is evaluated, deduplicate by canonical requisition and resolve the eight repeated-URL groups; keep explicit source-comparison controls but exclude them from unique-vacancy counts.
4. Recheck canonical status and eligibility for records whose page could not be fully retrieved. Preserve `unknown` where evidence is insufficient.
5. Continue to treat source permission as a separate gate from URL validity and vacancy status. No source was queried through the product, no candidate data was sent, and no application was submitted.

**Conclusion:** The CSV has no blank canonical/apply URL fields, but URL presence alone is not enough. The main data-quality risk found in this pass is requisition-level duplication and the tendency to conflate a live listing with a candidate-eligible opportunity. The implementation gate remains closed.
