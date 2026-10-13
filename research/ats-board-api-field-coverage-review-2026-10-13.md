# ATS Public Job-Board API Field-Coverage Review

**Reviewed:** 2026-10-13  
**Purpose:** Add implementation-relevant schema and failure-mode findings from public GitHub references to the existing official ATS feasibility research.  
**Status:** Research only; no connector implementation or provider approval.

## Decision

Add SmartRecruiters to the **candidate list for further official documentation/terms review**, not to the approved source list. Use the dated ATS field-coverage repository as a test-case catalogue; do not copy its job data or rely on its percentages as current universal facts.

## Sources

- [ATS job board reference — README](https://github.com/GregoryBolshakov/ats-job-boards-reference/blob/master/README.md) — MIT-licensed repository, measured snapshot from 2026-08-29; reports 5,122 adverts from 16 companies in the primary snapshot and a separate segments snapshot.
- [ATS job board reference — dated snapshot files](https://github.com/GregoryBolshakov/ats-job-boards-reference/tree/master/data) — snapshot data was inspected at the file listing level, not copied or adopted.
- [ATS jobs API examples](https://github.com/strongboxr/ats-jobs-api-examples) — MIT-licensed example code for Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee, Personio and Workday. Code is a secondary reference, not official permission evidence.
- [Greenhouse official Job Board API docs](https://docs.greenhouse.io/job-board.html) — official docs state public job-board GET data does not require authentication; application submission requires Basic Auth.
- [Greenhouse API overview](https://support.greenhouse.io/hc/en-us/articles/10568627186203-Greenhouse-API-overview) — official overview updated 2026-08-26.

## Dated field observations from the third-party snapshot

The reference's primary snapshot reports these non-empty-field rates for its sampled company boards. These are **not** universal API guarantees and must be remeasured on our actual target companies.

| Field | Greenhouse | Lever | Ashby | SmartRecruiters |
|---|---:|---:|---:|---:|
| Title | 100% | 100% | 100% | 100% |
| Location | 100% | 93% | 100% | 100% |
| Department | 100% | 94% | 100% | 100% |
| Employment type | 0% | 76% | 100% | 100% |
| Posted date | 100% | 100% | 100% | 100% |
| Updated date | 100% | 0% | 0% | 0% |
| Apply URL | 100% | 100% | 100% | 100% |
| Declared salary minimum | 47% | 1% | 72% | 13% |

Interpretation: these percentages describe a narrow dated sample (mostly a selected set of tech-company boards), not coverage in India, internships, or all employers. The low salary disclosure rates and absent updated timestamps are reasons to model unknown fields explicitly and use content-diffing, not to infer pay or freshness.

## Failure modes that should become future fixture tests

1. **Empty response semantics:** provider-specific behavior must distinguish 404/unknown slug, known board with zero openings, API error, and parse failure. The reference reports that SmartRecruiters can return HTTP 200 with zero results for both unknown and empty boards; do not infer 'board exists' or 'company is not hiring' from that alone.
2. **ATS migration:** one company may have an old board and a new board both returning valid responses. Detect likely migration using company identity and posting sets; do not select the first successful endpoint and declare it canonical.
3. **Pagination:** SmartRecruiters list endpoints are paginated; the reference reports a 100-item cap and ignored higher `limit` values. Validate `totalFound`/offset and stop conditions against current official docs.
4. **Detail vs list:** the reference reports that SmartRecruiters' detail endpoint can contain job description and compensation fields absent from the list response. Fetch details only for jobs that survive initial filtering if current terms/quotas allow.
5. **Greenhouse content flags:** the reference reports `content=true` also affects department/office fields, and `pay_transparency=true` enables pay ranges in the sampled endpoint. Verify the current official contract before relying on these flags.
6. **Salary ranges are typed, not just numeric:** preserve raw range arrays, currency, unit/period, employer-written labels, base-vs-bonus/OTE distinctions, and provenance. Zero/invalid ranges and contradictory units must become unknown/review-required, not a confident zero or normalized annual salary.
7. **Missing company identity:** if the provider payload omits company, attach a verified board/company identity from the source configuration. Do not infer from role text.
8. **Timestamp differences:** validate units (e.g. milliseconds vs seconds), timezone, absent timestamps, and impossible/future values. Keep `posted_at`, `retrieved_at`, `first_seen_at`, `last_seen_at`, and `last_verified_at` distinct.
9. **Dedup beyond source ID:** include normalized employer identity, canonical URL, normalized title/location, and content fingerprint; retain source sightings and explain merges. Reposts and location-specific rows can be duplicates; ATS migration can look like mass closures/new jobs.
10. **Stale listings:** a successful live endpoint may still contain evergreen or old listings. Do not equate live retrieval with recently posted or actively hiring.
11. **Source failure accounting:** don't silently turn a blocked/challenge/malformed response into an empty job list. Record source-level status and continue safely with other sources.
12. **Bandwidth and request budget:** large HTML descriptions and per-job detail calls can increase data volume and request count. Use two-stage fetch and bounded concurrency only after checking each provider's rules.

## Source posture

| Source | Current posture | Next action |
|---|---|---|
| Greenhouse | Technical public GET API documented officially; this does not itself authorize every product use or application action. | Continue terms/usage review and target-company coverage audit. |
| Lever | Per-company public postings API described in official docs already recorded in `job-platform-feasibility-matrix-2026-10-13.md`. | Continue terms/usage review and test missing fields/timestamps on target boards. |
| Ashby | Per-company public job board API described in official docs already recorded in the feasibility matrix. | Continue terms/usage review; test listing flags, salary, and migration cases. |
| SmartRecruiters | Technical endpoints and pitfalls surfaced by third-party code/snapshot; official usage permission for our desktop product remains unverified in this review. | Check current official docs, terms, rate limits, and intended-use permission before any connector. |
| Recruitee / Personio / Workday | Example repo lists technical endpoints, including Workday POST search calls. That is not sufficient evidence of permission, stability, or fit. | Lower priority; verify official docs and access terms before testing. |

## Dataset decision

Do not copy the 2–8 MB snapshots from the reference repo into our repository and do not use them as a production data source. Reasons:
- Snapshot date is 2026-08-29; it is stale for current job discovery.
- Company sample is narrow and does not establish Indian fresher/internship coverage.
- Root MIT license covers the repository code/documents according to the repository metadata and LICENSE; it does not automatically establish the right to redistribute all employer-authored job descriptions or third-party listing content.
- Shipping the data would add bulk and false freshness risk without helping the live source-coverage gate.

Keep the external links and field-level test ideas only. For matching evaluation, build a small reviewed fixture set from permitted sources and redact or synthesize any candidate profile data. Label synthetic examples clearly and never train or claim accuracy from them as if they were real outcomes.

## Required pre-implementation checks

- [ ] Official documentation and terms for SmartRecruiters and any additional ATS source.
- [ ] Current endpoint response shapes and pagination semantics against several known boards.
- [ ] Target-audience coverage: India and global-remote internships/fresher roles, not just senior tech jobs.
- [ ] Legal/data-use review for storing, displaying, caching, and refreshing listing content.
- [ ] Offline fixtures for all failure modes above.
- [ ] No scraping or submission automation inferred from a public GET endpoint.
- [ ] Record source review date, permissions, rate limits, attribution, retention, and direct apply URL behavior.

## Limitations

This is a research note based on the named third-party repositories and official Greenhouse documentation. It is not a legal opinion, comprehensive ATS audit, or current production test of every endpoint. Field rates are explicitly historical sample measurements.