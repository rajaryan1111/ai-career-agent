# Batch Research Pass — 2026-10-14

## Decision

**The source-quality gate remains NOT PASSED. Keep the project research-only.** This batch adds one candidate lead and consolidates a fresh public-web review of candidate-relevant pages and source-policy controls. It does not claim the 50-record validation sample is complete.

## Work completed in this batch

- Re-fetched and parsed the audit CSV before edits: 82 records, 27 columns, no malformed-width rows, no duplicate listing IDs, 73 distinct canonical URL values, 8 repeated-URL groups.
- Reconciled the current status counts from the actual CSV: 19 `open`, 52 `unknown`, 3 `expired`, 2 `closed`, 2 `not_a_listing`, 4 `source_review`. These are audit-record labels, not unique eligible vacancies.
- Added one official-employer-page lead, Valura.AI, as `unknown`, not `open`. The official page says it was posted 27 July 2026, gives Chennai/GIFT City/Remote as locations, describes a 3–6 month internship with full-time preferred, and lists Python, LLM APIs, agent orchestration, MCP, RAG, retrieval, evaluations, SQL, FastAPI and Docker. It does not provide sufficiently explicit current-open wording or a fully resolved country/eligibility statement for this audit. Canonical page: https://careers.valura.ai/836918cc-4b0f-4207-b364-e277600fd43f
- Rechecked RadialBrain's official careers page: internships are for current students and are remote across India; the page describes an AI Engineering Intern role around agents, automation and product engineering. It does not explicitly say the intake is currently open, so its status remains `unknown`. https://www.radialbrain.com/careers/
- Rechecked the Unisys AI Engineering Intern page surfaced in current search. It is Bangalore-based and the role asks for current/recent M.Tech candidates; it is not a direct match for the target BTech ECE undergraduate without further evidence. Do not count it as a candidate-ready match. https://unisys.wd5.myworkdayjobs.com/en-US/External/job/AI-Engineering-Intern_REQ574280
- Reviewed a Jobicy Spotify internship listing as an international-remote geography control: it specifies UK, USA and Sweden, and the text says it is a conference-specific expression-of-interest post, not a general vacancy. It must not be shown as India-eligible or as a normal open role for a candidate who did not attend the named conference. https://jobicy.com/jobs/154386-colm-2026-intern
- Excluded a recent LinkedIn result for Flocci from candidate-ready counts because the result says applications close 30 September 2026, before this review date; the search-result recency label does not override the expired deadline.
- Reconfirmed Jobicy's public API policy from its official documentation: normal product integrations are permitted without individual permission if Jobicy attribution and the canonical Jobicy listing URL are preserved; the public feed's listing URL is not guaranteed to be an employer ATS URL. The feed covers listings published in the last seven days, so absence is not proof of closure. The optional commercial direct-link API can incur a per-job fee. https://jobicy.com/jobs-rss-feed
- No live source API endpoint was queried in this batch. No source connector, production code, dependency, candidate-data transfer, autofill or application submission was performed.

## Candidate-facing interpretation

| Lead / control | Evidence observed | Decision for this audit |
|---|---|---|
| Valura.AI — AI Engineering Intern (Python) | Official role page; relevant agent/RAG/evaluation stack; posted 2026-07-27; remote is listed, full-time preferred | Add as `unknown`; verify intake is still open and clarify eligibility before recommending |
| RadialBrain — AI Engineering Intern | Official careers page says remote across India and internship for current students | Keep `unknown`; role is relevant but explicit current-open evidence was not found |
| Unisys — AI Engineering Intern | Official role page; Bangalore; current/recent M.Tech requirement | Not a direct candidate match for BTech ECE undergraduate |
| Spotify CoLM 2026 — Intern (Jobicy listing) | UK/USA/Sweden only; conference-specific expression of interest | Geography and posting-type negative control; not India-eligible |
| Flocci AI Engineering Intern (LinkedIn result) | Search result shows a 2026-09-30 closing date | Exclude pending canonical evidence of reopening |

## Reconciled audit baseline after this batch

The CSV is expected to contain **83 records × 27 columns**, with 0 malformed-width rows, 0 duplicate listing IDs, 74 distinct canonical URL values, and 8 repeated-URL groups. Status labels are expected to be: 19 open, 53 unknown, 3 expired, 2 closed, 2 not-a-listing, and 4 source-review. Permission remains unknown for 78 records. These are mixed audit records, not 19 unique candidate-ready vacancies.

## Gate checklist

| Requirement | Result |
|---|---|
| At least 20 unique relevant, currently available vacancies | **Not demonstrated** |
| 50-record validation sample: 25 India-focused + 25 international remote | **Not complete** |
| ≥90% valid direct-employer application links with a defined response-outcome denominator | **Not measured** |
| Zero unsupported worldwide-eligibility claims | **Not yet demonstrated across the full sample** |
| Source permission resolved for every source selected for integration | **Not passed for all sources; Jobicy is the only leading conditional candidate** |
| Candidate profile stays local; no automated application submission | **Design boundary retained** |

## Next gate decision

Do not start production integration. The next research pass must produce a reproducible, deduplicated 50-record sample, record employer-link outcomes using a defined denominator, audit hard eligibility without converting `unknown` to `pass`, and confirm permissions for each exact source/product flow. Jobicy remains the first candidate for a later explicitly authorized read-only adapter; it has not been integrated or queried.
