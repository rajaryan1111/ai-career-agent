# GitHub Repository Audit for AI Career Agent

**Audit date:** 2026-10-13
**Purpose:** Screen all repositories visible under the user's `rajaryan1111` GitHub account, the four third-party repositories previously shared for review, and focused additional GitHub sources discovered during the audit. Capture only material that can improve the AI Career Agent without pulling in unnecessary dependencies or starting implementation.
**Project gate:** Research/documentation only. No implementation or dependency adoption is authorized yet.

## Scope and method

- Enumerated 18 repositories accessible under `rajaryan1111` and reviewed their root contents; inspected READMEs and relevant manifests where present.
- Deep-inspected the portions of the user's repositories most relevant to candidate/job matching, ingestion, retrieval, validation, provenance, deduplication, retry/failure handling, and privacy/security.
- Carried forward focused reviews of the four previously shared external repositories: [obra/superpowers](https://github.com/obra/superpowers), [garrytan/gstack](https://github.com/garrytan/gstack), [Shubhamsaboo/awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps), and [ruvnet/ruflo](https://github.com/ruvnet/ruflo).
- Added a focused review of [ATS job board reference](https://github.com/GregoryBolshakov/ats-job-boards-reference) and [ATS jobs API examples](https://github.com/strongboxr/ats-jobs-api-examples) discovered during the audit.
- This is a relevance and architecture audit, not a line-by-line security audit of every file in every repository. Files that may contain personal resume/job-description data were not copied into this project.

## Highest-value findings

### A. Existing code in the user's repositories can reduce future reinvention

#### 1. `graphone-intelligence-pipeline` — strongest ingestion reference
Repository: https://github.com/rajaryan1111/graphone-intelligence-pipeline

Relevant inspected paths include `src/pipeline/jobs.py`, `src/crawlers/http.py`, `src/crawlers/retry.py`, `src/crawlers/remoteok.py`, `src/validation/schemas.py`, `src/validation/freshness.py`, `src/resolution/resolver.py`, and its tests.

Patterns worth reusing conceptually, after a focused code review at implementation time:
- One shared HTTP client with bounded concurrency, timeouts, typed failure categories, and connection pooling.
- Bounded exponential backoff; respect `Retry-After`; do not retry payload-too-large errors without changing/chunking the request; distinguish genuine access blocks from rate-limit responses.
- Per-source adapters and an explicit pipeline result with counts for discovered, fetched, rejected, stale, invalid, blocked, and failed records. Shortfalls should be reported rather than padded with invented records.
- Schema validation before persistence, with explicit null/unknown fields rather than guessed facts.
- Freshness checks, URL normalization, source provenance, idempotent persistence, entity resolution, and offline tests/fixtures.
- Existing job adapters include Remote OK, Working Nomads, Y Combinator/Who Is Hiring, Wellfound, and Built In. Their presence in code is not proof that their current terms permit our intended use; re-check source-by-source before any reuse.

Limitations: this repository's own docs have historical status text that conflicts with later README sections. Treat the exact code/tests and latest live verification as separate evidence, not the README's aggregate completion claims alone. Do not transplant the whole stack or its database schema into the desktop app.

#### 2. `ai-orbit-tools-ingestion` — strongest source-verification and data-quality reference
Repository: https://github.com/rajaryan1111/ai-orbit-tools-ingestion

Relevant inspected paths include `src/core/http_client.py`, `src/discovery/registry.py`, `src/deduplication/deduplicator.py`, `src/verification/verifier.py`, `src/verification/store.py`, `config/sources.yaml`, and deterministic fixture tests.

Patterns worth reusing conceptually:
- Config-driven source registry with explicit access method, roles, trust/rate settings, enabled state, and notes.
- Discovery produces sightings, not verified truth; only evidence from the official site can promote a record to verified.
- If an official URL is missing or a bot challenge/empty/thin page prevents verification, leave it unverified instead of guessing.
- Separate discovery, official-site verification, field extraction, scoring, and persistence/promotion stages.
- Deduplication with explainable MERGE / REVIEW / DISTINCT outcomes, source sightings preserved, and official/high-trust evidence preferred for field-level merges.
- Persisted checkpoints, resumability, source-specific fixtures, and deterministic tests that do not need live sites.

Limitations: it was built for AI-tool directories, not job postings. Its source list, scoring weights, website selectors, and business rules must not be copied as if they apply to job boards.

#### 3. `AI_resume_review` — relevant UX and candidate/JD-analysis prototype
Repository: https://github.com/rajaryan1111/AI_resume_review

The frontend demonstrates resume/JD text or PDF inputs, role hints, skill-gap analysis, and a skill graph. It is a useful prototype to inspect when we later define the candidate fact review and match-explanation experience.

Do not transplant it unchanged: its README describes a separate analysis API, and the inspected frontend bootstraps a fixed demo user and sends resume/JD files to an API endpoint. That conflicts with our local-first default unless the backend, storage, consent, retention, and account model are redesigned and reviewed. Do not copy its `resume.txt` or `jd.txt` fixtures into the Career Agent; candidate/job data should not become shared demo data by default.

#### 4. `indian-standards-procurement-ai` — useful retrieval and explainability reference
Repository: https://github.com/rajaryan1111/indian-standards-procurement-ai

The inspected engine separates extraction, retrieval, reranking, confidence, evidence/explanation, provider interfaces, and repository interfaces. It caps chunks sent for embedding and falls back to lexical retrieval when vector retrieval is unavailable. It also avoids presenting an unrelated result as a primary recommendation when no product-concept match exists.

Transferable lesson: retrieval similarity should generate candidates, not final truth. Combine it with explicit hard requirements, evidence, confidence/unknown states, and a safe fallback. Do not copy standards-specific lexicons, ranking weights, or datasets into job matching.

#### 5. `jarvis-assistant` — useful tool-safety patterns, not a product base
Repository: https://github.com/rajaryan1111/jarvis-assistant

The README describes a bounded tool loop, result checking, explicit confirmation for high-impact actions, separate optional features, and local credential/session handling. These principles support the Career Agent's hybrid automation and exception queue.

Do not import the full assistant: it is macOS-focused, includes unrelated voice/vision/desktop controls, and defaults to optional hosted LLM functionality. Re-evaluate only small, isolated patterns and their tests if needed later.

### B. External engineering repositories: keep process principles, not frameworks

- [Superpowers](https://github.com/obra/superpowers): retain bite-sized plans, test-first deterministic rules, root-cause debugging, and fresh verification before completion claims. Do not install/copy its full skills/toolchain now. See [review](superpowers-review-2026-10-13.md).
- [gstack](https://github.com/garrytan/gstack): retain plan/review/QA and scope-control principles. Do not adopt browser automation/scraping skills as a shortcut around platform permissions. See [review](gstack-review-notes.md).
- [awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps): local hybrid retrieval (keyword + semantic search + reranking) is a benchmark candidate, not an automatic dependency. The repository's recruitment-team example is employer-side and hosted-service-heavy, so it is not a suitable base. See [review](awesome-llm-apps-review-2026-10-13.md).
- [Ruflo](https://github.com/ruvnet/ruflo): retain least-privilege controls, action evidence, PII/secret handling, and explicit cost budgets. Do not install its multi-agent harness, hooks, swarm, or memory stack. See [review](ruflo-review-2026-10-13.md).

### C. New external ATS research lead

[GregoryBolshakov/ats-job-boards-reference](https://github.com/GregoryBolshakov/ats-job-boards-reference) contains a dated (2026-08-29) sample and measured field-coverage analysis for Greenhouse, Lever, Ashby, and SmartRecruiters. The author reports 5,122 live adverts from 16 companies in the main snapshot; a separate larger segments snapshot is also described. The root repository license is MIT, but do not assume that the license automatically grants rights to redistribute the third-party job descriptions/data. We did not copy the snapshot.

High-value lessons from the dated measurements:
- Public job-board APIs are generally per-company board endpoints, not universal global search APIs; board discovery is a separate problem.
- A successful HTTP response with zero rows can mean an empty board or a bad/unknown slug, and this is provider-specific. SmartRecruiters is especially ambiguous in the described snapshot.
- ATS migrations can leave an old board responding while the new board contains the live roles. A 200 response or first successful provider is not enough to choose the canonical board.
- SmartRecruiters pagination and per-posting detail fields require care; list responses can omit descriptions and compensation, which may be exposed on detail endpoints.
- Greenhouse pay requires the correct query parameter and is an array of ranges; pay labels are employer-written and may conflict with the numeric period. Do not silently infer annual pay or combine base and on-target earnings.
- Lever/Ashby payloads may omit company name; populate from a verified board identity, not from guesses.
- Source IDs alone are insufficient for cross-ATS deduplication. A role may be reposted with a new ID, duplicated by location, or migrated between ATS platforms.
- `updatedAt` is not uniformly available, so change detection should use normalized content fingerprints when supported by the product's permission and cost constraints.
- Data age, retrieval time, posted date, first-seen time, and verification time are different fields. A live API can serve an old or evergreen posting.

These are valuable test cases, not universal guarantees: the sample is dated, company/industry-biased, and too small to represent all boards or India fresher roles. Re-test current official endpoints before implementation.

Companion code reference: [strongboxr/ats-jobs-api-examples](https://github.com/strongboxr/ats-jobs-api-examples) documents technical examples for Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee, Personio and Workday and includes change monitoring. Its README says MIT. It is a useful checklist/reference, not a production dependency: technical reachability does not settle platform terms, and its code has provider-specific assumptions that must be independently tested.

A third repository, [mherzog4/job-boards](https://github.com/mherzog4/job-boards), demonstrates large-scale per-company board discovery via Internet Archive/urlscan indexes and direct board APIs. Do not adopt its discovery mechanism or broad crawling now: source terms, rate limits, archive coverage, and commercial/redistribution permissions need separate review. Its own README reports substantial board-discovery lag and acknowledges incomplete coverage.

## Inventory of all 18 account repositories

| Repository | Relevance decision |
|---|---|
| `ai-career-agent` | Primary project; research-first rules retained. |
| `AI_resume_review` | High relevance for future resume/JD analysis UX; redesign for local-first privacy before reuse. |
| `graphone-intelligence-pipeline` | High relevance for ingestion, retry/freshness, schema validation, provenance, dedup and test patterns. |
| `ai-orbit-tools-ingestion` | High relevance for official-site verification, source registries, checkpoints and evidence-based promotion. |
| `indian-standards-procurement-ai` | Medium-high relevance for retrieval/reranking/provider abstractions and evidence-backed explanations; domain logic is unrelated. |
| `sih26108-is-copilot` | Overlapping IS Copilot project lineage; inspect the primary repository above rather than copying duplicate content. |
| `jarvis-assistant` | Medium relevance for bounded tool loops, explicit confirmation, and credential/session boundaries; most functionality is unrelated. |
| `fake-id-screening` | Low/indirect relevance only: upload validation, safe file handling and offline demo principles; identity screening logic is unrelated. |
| `fibonacci-project` | No meaningful domain reuse found; generic asynchronous job status is too small/generic to justify importing. |
| `deep-learning-am-fm-modulation` | No meaningful product-domain reuse found. |
| `spendly` | No meaningful product-domain reuse found. |
| `SIH-H2S-Dosimeter` | No meaningful product-domain reuse found. |
| `apnacollege-demo` | Minimal introductory repository; no relevant material. |
| `parallel-processing` | Empty repository at time of audit. |
| `rajaryan1111` | Profile README only; no implementation artifact to import. |
| `raj-aryan-portfolio` | Portfolio UI; no relevant Career Agent functionality. |
| `sorry` | Personal 3D experience; no relevant domain logic. |
| `tushita-birthday` | Personal 3D experience/assets; no relevant domain logic. |

This table lists all 18 distinct account repositories. The root/README screen found no meaningful Career Agent material in the personal/college/portfolio/demo repositories beyond generic engineering lessons.

## What we should add to the product design (not code yet)

1. A source registry with per-source permissions/review date, capabilities, rate limits, last checked time, and explicit supported/experimental/blocked/unknown status.
2. One canonical job record with raw-source provenance, original URL, source ID, normalized employer identity, retrieved-at, posted-at, first-seen-at, last-seen-at, last-verified-at, and field-level missingness.
3. Separate source discovery, job-detail retrieval, freshness/eligibility, candidate ranking, and application actions; a failure in one stage should not fabricate records or erase previous known state.
4. Provider-specific contract tests for pagination, empty responses, missing fields, timestamp units, pay ranges/periods, duplicate locations, reposts, ATS migration, rate limits, stale records, malformed payloads, and challenge pages.
5. Deterministic offline fixtures for every supported source, plus explicit live smoke tests separated from the regular test suite.
6. Keep lexical/rule-based retrieval as a baseline. Evaluate hybrid retrieval and reranking on a human-reviewed job-matching test set before adopting embeddings/vector databases.
7. Treat external job content and resumes as untrusted data; never let page instructions broaden tool permissions. Apply runtime schema validation, least privilege, redacted logs, bounded retries, and user approval for consequential actions.
8. Do not copy third-party job snapshots into the repository or ship stale job data. Use datasets only after checking content rights, license scope, freshness, representativeness, and privacy.

## Deliberately not added

- No third-party framework, package, MCP server, plugin, browser automation tool, vector database, hosted actor, or scraping dependency.
- No job snapshot CSV/JSON copied from an external repository.
- No synthetic placement dataset adopted as a ranking/training benchmark: synthetic labels could teach false correlations and do not establish real job eligibility or outcomes.
- No resume or job-description fixture copied from the user's other repository.
- No source is considered approved for production merely because a public endpoint or code example exists.
- No application submission automation or code implementation started.

## Next validation priority

Run a source-by-source, terms-aware coverage experiment using a small, human-reviewed set of company career pages and target roles. Start with official employer board endpoints where the company's board slug is known; include SmartRecruiters as a candidate only after official docs/terms are checked. Measure unique eligible India/international internship/fresher roles, false positives, missing critical fields, staleness, duplicates, request volume, and direct apply URL quality. This will answer a more important question than adding more frameworks: whether the product can deliver enough useful, permitted jobs for its initial audience.

## Evidence and limitations

- Own-repo review is grounded in repository metadata, root contents, selected READMEs and the specific source files listed above. Not every file in every repository was audited line-by-line.
- External repo features are described as documented by those projects, not independently proven secure or production-ready.
- ATS field measurements are from a dated third-party snapshot; percentages must not be treated as universal current guarantees.
- This report is design guidance only. All implementation choices remain pending the project's feasibility decision gate.