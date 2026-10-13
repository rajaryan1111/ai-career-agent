# Deep Code Audit: Reuse Candidates from Existing Repositories

**Checked:** 2026-10-13  
**Scope:** Targeted code review of the strongest internal reuse candidates after the broader repository inventory. This is not a line-by-line audit of every file in every repository.  
**Status:** Research only. No code or datasets copied; no dependency or source connector approved.

## Executive decision

Reuse **design patterns and selected tests**, not whole applications. The strongest useful patterns are:
1. Shared bounded HTTP transport with typed failures and explicit handling of 401/403/429/5xx.
2. Deterministic source adapters with provenance and missing-field handling.
3. Content-fingerprint pagination guards and resumable checkpoints.
4. Official-source verification that refuses to promote a listing when the page is blocked, thin, malformed, or identity cannot be confirmed.
5. Explicit source registry and per-source status rather than silently treating failures as empty results.

These are candidates for a later implementation review after source permissions and the product decision gate. The existing projects have different domains and contain source-specific assumptions that must not be copied wholesale.

## 1. `graphone-intelligence-pipeline`

Repository: https://github.com/rajaryan1111/graphone-intelligence-pipeline  
Reviewed code paths:
- [HTTP wrapper](https://github.com/rajaryan1111/graphone-intelligence-pipeline/blob/main/src/crawlers/http.py)
- [bounded retry](https://github.com/rajaryan1111/graphone-intelligence-pipeline/blob/main/src/crawlers/retry.py)
- [Remote OK adapter](https://github.com/rajaryan1111/graphone-intelligence-pipeline/blob/main/src/crawlers/remoteok.py)
- [Working Nomads adapter](https://github.com/rajaryan1111/graphone-intelligence-pipeline/blob/main/src/crawlers/workingnomads.py)
- [Hacker News “Who is hiring?” adapter](https://github.com/rajaryan1111/graphone-intelligence-pipeline/blob/main/src/crawlers/ycombinator_jobs.py)
- [Wellfound adapter](https://github.com/rajaryan1111/graphone-intelligence-pipeline/blob/main/src/crawlers/wellfound.py)
- [job-ingestion requirements](https://github.com/rajaryan1111/graphone-intelligence-pipeline/blob/main/.kiro/specs/phase-7-jobs-ingestion/requirements.md)
- [source registry](https://github.com/rajaryan1111/graphone-intelligence-pipeline/blob/main/src/config/sources.py)

### What is worth retaining as a design reference

- A single shared HTTP client centralizes timeouts, connection pooling, bounded concurrency, status handling and typed failures.
- Retries are bounded, use jitter, and respect `Retry-After`; 401/403 blocks are not treated as a challenge to bypass.
- Adapters parse deterministic fields and preserve source URL/source identity rather than asking an LLM to invent missing required fields.
- The source registry documents discovery method, date strategy, rate-limit notes and known limitations.
- The job-ingestion spec separates listing discovery, parsing, freshness, validation and persistence.

### Important limitations / warnings

- **Do not copy source adapters as an approved list.** The repository includes a Wellfound sitemap crawler, but this project's own official-terms review says Wellfound terms restrict harvesting/scraping. Technical code existing in another repository is not permission evidence.
- Remote OK and Working Nomads adapters currently emit a small common schema (title, company, URL, posted date and a remote flag). That is insufficient on its own for our strict eligibility rules: region/country restrictions, internship/fresher level, employment type, work authorization, compensation period, and application-route reliability need separate evidence and unknown states.
- The Hacker News adapter selects the newest matching “Who is hiring?” thread and heuristically extracts the first link and the first pipe-separated text line. Community posts can be malformed, edited, stale, or contain several links; this source requires quality evaluation and explicit human-review/low-confidence handling, not blind promotion to verified vacancies.
- The current adapter code does not itself establish the usage permission, attribution, retention and refresh conditions required for the Career Agent. Those belong in a source-policy registry/gate.
- Historical project requirements and README status can conflict; verify tests and current code, not prose alone.

**Disposition:** Reuse patterns for transport, typed failure handling, normalization and test fixtures only after reviewing the exact implementation and license/compatibility. Re-evaluate each source independently; no adapter is approved merely because it exists here.

## 2. `ai-orbit-tools-ingestion`

Repository: https://github.com/rajaryan1111/ai-orbit-tools-ingestion  
Reviewed code paths:
- [HTTP client and response cache](https://github.com/rajaryan1111/ai-orbit-tools-ingestion/blob/main/src/core/http_client.py)
- [robots rules parser](https://github.com/rajaryan1111/ai-orbit-tools-ingestion/blob/main/src/core/robots.py)
- [pagination guards](https://github.com/rajaryan1111/ai-orbit-tools-ingestion/blob/main/src/discovery/pagination.py)
- [source registry](https://github.com/rajaryan1111/ai-orbit-tools-ingestion/blob/main/src/discovery/registry.py)
- [resumable discovery runner](https://github.com/rajaryan1111/ai-orbit-tools-ingestion/blob/main/src/discovery/runner.py)
- [official-site verifier](https://github.com/rajaryan1111/ai-orbit-tools-ingestion/blob/main/src/verification/verifier.py)
- [project README](https://github.com/rajaryan1111/ai-orbit-tools-ingestion/blob/main/README.md)

### What is worth retaining as a design reference

- Source records preserve where a candidate was found; discovery sightings are kept distinct from verification.
- The verifier fetches only the resolved official URL and does not treat a directory listing as proof that the target is real or that its claims are true.
- Challenge pages, empty/thin pages, non-HTML responses and uncertain identity remain unverified rather than being marked successful.
- Pagination has hard page/candidate caps, repeat-content detection, empty-page stop conditions, consecutive-failure budgets and recorded stop reasons.
- Checkpoints and accumulated outputs support resumability without deleting earlier source contributions.
- Offline HTTP mode and deterministic fixtures reduce accidental live traffic and make parser tests reproducible.

### Important limitations / warnings

- This is an AI-tool directory pipeline, not a job-posting model. Product identity resolution, tool scoring, product lifecycle signals and its large stored datasets do not transfer directly.
- The HTTP client's cache and live-fetch behavior must be reviewed against each job provider's caching, retention and attribution terms before reuse.
- Its robots handling is a technical courtesy mechanism, **not a legal authorization engine**. The code documents a fail-open outcome when robots.txt cannot be retrieved or parsed; the Career Agent must not interpret that as permission. Source-specific terms/API policy still govern, and ambiguous access must stop or remain unsupported.
- The repo contains multi-megabyte scraped candidate datasets and logs. Do not copy these into the Career Agent; they add bulk, stale data and unrelated third-party content without helping job-source feasibility.
- A source being configured or marked enabled in YAML does not prove it is currently accessible, permitted, high quality, or fit for the target audience.

**Disposition:** Strongest internal reference for provenance, verification states, safe pagination, checkpointing and offline tests. Reuse must be selective and adapted to job-specific schemas and provider policies.

## 3. `AI_resume_review` and `indian-standards-procurement-ai`

- `AI_resume_review` remains a UX/analysis reference for resume-to-job comparison and skill gaps. Do not reuse its fixed demo-user behavior, external analysis request flow, or sample resume/JD fixtures unchanged; they conflict with local-first defaults or can mislead quality evaluation.
- `indian-standards-procurement-ai` remains a pattern reference for evidence-backed retrieval, lexical fallback, reranking and confidence explanations. Do not copy its standards corpus, procurement-specific terms, giant bundled API file or domain lexicons into the Career Agent.

## 4. Requirements for any future reuse

Before moving any module into the Career Agent:
1. Verify license compatibility and preserve required notices.
2. Review the exact file and its tests at a pinned commit SHA; do not import a repository wholesale.
3. Remove unrelated domain assumptions and all bundled real/scraped datasets.
4. Add source-policy gating before any network access, including permission status, documented method, rate limits, attribution and cache/retention rules.
5. Test empty-but-valid results separately from errors, access blocks, challenges, schema changes, stale records, duplicate/reposted jobs and missing critical eligibility fields.
6. Keep source failure visible in run reports; never convert “blocked or not checked” into “no jobs exist.”
7. Measure target-audience coverage and human-reviewed relevance before calling the source useful.

## Conclusion

The existing repositories contain meaningful engineering patterns, but **none removes the main product risk: discovering enough relevant jobs through permitted, reliable sources**. Do not add code or dependencies yet. First finish source authorization and target-audience coverage validation; then select the smallest useful patterns and tests.
