# Public GitHub Reuse Audit — 2026-10-14

**Reviewed:** 2026-10-14  
**Repository under review:** `rajaryan1111/ai-career-agent`  
**Stage:** Research only; no implementation authorized.  
**Scope:** Public GitHub repository discovery outside the user's own repositories. This was a broad, relevance-led search, not an exhaustive crawl of all public GitHub repositories.

## Executive decision

**Reuse ideas and references selectively; do not import upstream code, job datasets, workflows, credentials, or dependencies at this stage.** The strongest findings reinforce decisions already made for AI Career Agent: employer/canonical evidence, explicit source-level permission, local-first candidate data, human-controlled submission, careful board identity verification, resumable/partial-run semantics, and evidence-constrained resume claims.

Twelve repository-search themes were queried: job-search agents, job-board APIs, job-listing datasets, resume/career matching, ATS integrations, n8n job-search automation, scraping tools, deduplication, work authorization, LLM evaluation/provenance, public job APIs, and internship datasets. The searches returned 100+ result entries before deduplication. README/license/documentation files were fetched for a bounded set of 14 distinct external repositories; the more relevant candidates below received closer review. Search indexing is incomplete and this is not a claim that every public repository was inspected.

No external code, dependency, workflow, dataset, API key, token, candidate data, or application action was added or executed. No live job-source endpoint was queried. Your own repositories were not used as discovery candidates; the target repository was read only to align the findings with existing project policy.

## Findings worth retaining

### 1. Career-Ops — local-first, human-controlled, evidence-first workflow

- Repository: https://github.com/career-ops-hq/career-ops
- Reviewed: README, MIT license, and budget/model-agnostic documentation.
- Useful design references: evaluate one listing against the candidate's actual record; prefer evidence over keyword stuffing; surface strong reasons not to apply; keep the workflow local; let the candidate make the final submission decision; separate cost/model choices from core workflow.
- Decision: **retain as design references only**. These ideas align with our existing local-first and human-submission principles; they do not justify importing a second job-agent codebase.
- Caution: outcome counts and product performance statements in the upstream README are author-reported and were not independently validated. An MIT license permits code reuse subject to its terms, but it does not resolve job-source access permission or justify bypassing our research gate.

### 2. Job-Radar — board identity, pacing, checkpoints, and explicit local configuration

- Repository: https://github.com/maccydee/job-radar
- Reviewed: README and MIT license.
- Useful design references: discover ATS board identifiers from a company's own careers page rather than guessing; verify that a responding board actually belongs to the intended employer; pace requests per host; make interrupted scans resumable; preserve per-source/platform differences; keep candidate configuration out of version control.
- Decision: **retain the design lessons, not the implementation or bundled employer-board list**. Board identity verification and recoverable partial runs are especially relevant to source-quality requirements already documented in this project.
- Caution: the repository describes a large list of employer boards and 23 ATS platforms, but that is not proof that every board is correctly mapped, currently active, or authorized for our use. Each provider and employer-board pathway still needs an independent permission review. Do not copy the board list into our project.

### 3. ATS Public Job APIs cheatsheet — discovery index only

- Repository: https://github.com/noble-ronin/ats-job-apis
- Reviewed: README; a repository-level LICENSE file was not found at the expected path.
- The cheatsheet lists endpoints for Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee, Breezy HR, BambooHR, Personio, and Workday.
- Decision: **use only as a lead list for official-documentation research**. Do not copy its code or treat its endpoint list as proof of permission. Existing official-source research for Greenhouse, Lever, and Ashby remains the authority for those providers. Any new provider needs its own current official documentation, terms/permission assessment, data-use limits, and validation fixtures before it is considered.
- Caution: a public/keyless JSON/XML endpoint is a technical fact, not blanket authorization to query, cache, republish, autofill, or submit.

### 4. Remotive Remote Jobs API — possible conditional source, not approved

- Repository: https://github.com/remotive-com/remote-jobs-api
- Documentation: https://github.com/remotive-com/remote-jobs-api#readme
- API endpoint documented by the repository: https://remotive.com/api/remote-jobs
- The repository's own terms say that the API is for sharing Remotive jobs further, require a link back to the canonical Remotive listing and attribution, describe a 24-hour delay, advise a maximum of four requests per day, and prohibit submitting Remotive jobs to third-party job websites. It also says displaying jobs to collect signups/email addresses breaches its terms.
- Decision: **conditional research candidate only**. It may be worth a small coverage/freshness evaluation later if the product's exact local-desktop use is confirmed to fit the provider's terms. No API request or integration was made.
- Before any future test: preserve attribution and canonical links; respect the stated rate guidance; do not use the feed for signup/email capture; clarify any ambiguity about the intended application/distribution model; measure target-role coverage and freshness separately from technical availability.

### 5. Evidence-grounded Resume Tailoring Agent — claim provenance and negative tests

- Repository: https://github.com/JosieCen/Evidence-grounded_Resume_Tailoring_Agent
- Reviewed: README and MIT license.
- Useful design references: a verified evidence registry; claim-level provenance; explicit `do_not_claim` boundaries; semantic retrieval that proposes evidence but cannot override hard constraints; deterministic post-generation audit; change logs; positive cases and hard-negative cases in the benchmark.
- Decision: **retain as design/test ideas only**. These concepts are relevant to future local application-material preparation, but implementation remains gated.
- Caution: the upstream benchmark is specific to its own fictional fixtures and model setup. Its reported scores are not transferable accuracy claims for AI Career Agent and must not be presented as hiring outcomes.

### 6. Open Jobs — useful historical freshness idea, not a live source

- Repository: https://github.com/elliottdehn/open-jobs
- Reviewed: README and CC0 license text.
- The README states that the crawler, nightly build, and search service stopped on 2026-10-10; the last snapshot was built on 2026-10-05. The repository describes labels such as fresh, stale, re-stamped, and ghost.
- Decision: **do not treat it as a live source or import the snapshot into the current audit seed**. The status labels are a useful research idea for freshness evaluation, but the data is historical and its source-level provenance/collection permission would need separate review before reuse in a product dataset.
- Caution: a repository-level data license does not by itself establish permission for every upstream source or remove freshness limitations.

## Explicitly rejected for this project at this stage

### JobSpy — MIT-licensed scraper with proxy/bypass functionality

- Repository: https://github.com/speedyapply/JobSpy
- The README advertises aggregation from multiple job boards and proxy support to bypass blocking.
- Decision: **do not integrate or run it**. Its bypass-oriented collection path conflicts with our source-permission gate. License compatibility does not override platform terms or authorize collection.

### n8n job-search workflow

- Repository: https://github.com/yixuan116/n8n-ai-agent-job-search
- The README describes reading LinkedIn job-alert email through Gmail, parsing it, and writing records to Notion.
- Decision: **do not import the workflow**. It depends on external account credentials and sends job-alert data into a hosted Notion database, which is not the current local-first default. Email alerts could be considered later only as a user-authorized, narrowly scoped import pathway after privacy, provider, and data-retention review.

### Public job-listing datasets and aggregator snapshots

- Search results included datasets described as Naukri/Glassdoor/data-science listings and other scraped job collections.
- Decision: **do not copy them into the seed CSV or ship them as a bundled dataset**. For each dataset, we would need a verifiable license, upstream provenance, collection-method review, timestamp/freshness information, deduplication quality, and a clear distinction between historical examples and current vacancies. A GitHub repository being public is not enough.

### Repository credentials and API keys

- No credentials were imported or added. Do not copy keys, tokens, cookies, proxy credentials, or secrets from public commits, READMEs, workflow examples, or issue posts. If a future integration requires credentials, use the provider's authorized credential flow and keep secrets outside Git and logs.

## Project implications

1. Keep the current source-quality gate closed. None of these findings clears it.
2. Continue to prefer official employer/ATS documentation over third-party endpoint lists.
3. Record source permission, terms, attribution, rate limits, caching/redistribution limits, freshness, candidate-country eligibility, and application route as separate fields/questions.
4. Treat transport errors, blocked requests, parse errors, and valid empty responses as different outcomes; a partial scan must not make unseen roles appear closed.
5. Verify company-to-ATS-board identity before accepting records from a public endpoint.
6. Keep candidate documents and profile data local by default; use fictional fixtures for evaluation.
7. Keep final application submission under user control.
8. Do not add production code, dependencies, external account integrations, or live connectors based on this repository review.

## Review log and source links

| Candidate | Decision | Main reason |
|---|---|---|
| Career-Ops | Design reference only | Local-first, evidence-first, candidate-controlled submission; no code import |
| Job-Radar | Design reference only | Board identity verification, pacing, checkpoints; no board-list import |
| ATS Public Job APIs cheatsheet | Discovery pointer only | Endpoint claims require official verification; expected-path license not found |
| Remotive API | Conditional research candidate | Explicit terms/attribution/rate limits; fit with intended use not yet confirmed |
| Evidence-grounded Resume Tailoring Agent | Design/test reference only | Claim provenance and hard-negative evaluation; no implementation yet |
| Open Jobs | Historical idea only | Service stopped 2026-10-10; last snapshot 2026-10-05 |
| JobSpy | Rejected for current stage | Proxy/bypass collection conflicts with source-permission policy |
| n8n LinkedIn-alert workflow | Rejected for current stage | External account credentials and hosted Notion data flow conflict with local-first default |
| Scraped job datasets | Not imported | Provenance, license, freshness, and collection permission are not sufficiently established |

**Bottom line:** this search produced useful architecture and evaluation ideas, plus one conditional API lead. It did not identify anything that should be blindly copied into the running project. No code, dependencies, credentials, or datasets were added, and the source-quality and implementation gates remain closed.
