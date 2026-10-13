# Open-source AI Job Agent review — QaliAI/ai-job-agent

**Reviewed:** 2026-10-13  
**Scope:** Read-only review of the upstream README, MIT license, public ATS source reference, privacy/architecture docs, ATS dispatcher, source registry, live verifier, preference filter, claim checker and daily workflow. No code was run, imported, copied or executed.

## Executive decision

**Reuse concepts selectively; do not import the repository or its adapters.** The upstream project is directionally relevant: local-first candidate files, direct ATS discovery, a persistent deduplication ledger, explainable scoring and human-reviewed application submission. Its MIT license permits reuse subject to retaining the license notice, but license compatibility does not establish permission to access every job source or guarantee correctness of implementation claims.

The source code contains several concrete behaviors that conflict with this project's quality-first and fail-closed requirements. Treat upstream documentation and sample reports as project claims, not independent proof of production quality.

## Useful ideas to retain as design references

- Keep candidate ground truth, search preferences and verified achievements distinct.
- Use deterministic IDs and a persistent ledger to deduplicate across runs.
- Normalize provider-specific responses into a documented canonical schema.
- Use explainable fit dimensions, show material gaps and apply hard eligibility gates before ranking.
- Verify generated application claims against candidate evidence.
- Keep candidate data and generated artifacts local by default; use fictional fixtures for tests.
- Generate a review brief with direct employer links instead of automatically submitting applications.

These are design references only. No code or dependency is approved by this review.

## Findings from direct source inspection

### 1. High risk — verifier fails open on network and access errors

File: [scripts/verify_postings.py](https://github.com/QaliAI/ai-job-agent/blob/main/scripts/verify_postings.py)

- HTTP 404/410 are treated as not live, and a small set of page text markers is treated as closed.
- Other HTTP errors, including 403, are returned as `is_live=True` with an “Assumed live” note.
- DNS errors, timeouts and other exceptions are also returned as `is_live=True` with a “Verification skipped” note.
- The daily workflow selects records with `is_live` true, so an unverified posting can pass the liveness gate.

**Decision for our product:** a network failure, 403, parse failure or inaccessible canonical page must result in `unknown/unverified`, never “open”. Separate transport outcome from vacancy status. Do not use a verifier's optimistic default as evidence.

### 2. High risk — source errors collapse into an empty result

File: [scripts/ats_engine.py](https://github.com/QaliAI/ai-job-agent/blob/main/scripts/ats_engine.py)

- JSON/XML fetch helpers return `None` after errors.
- Individual parsers commonly return an empty list when data is missing or a fetch fails.
- The dispatcher logs exceptions and continues, returning only a combined list of successful records.
- The daily workflow prints a total posting count without exposing a structured per-source success/empty/error outcome.

This means “source returned zero jobs” can be indistinguishable from “source could not be queried.” It can also make partial source outages invisible in a seemingly successful run.

**Decision for our product:** preserve explicit per-source states such as `success_with_records`, `success_empty`, `rate_limited`, `transport_error`, `schema_error` and `permission_blocked`. A partial run must not mark unseen records closed or overwrite prior state as if the run were complete.

### 3. High risk for this project's source-policy gate — public endpoint is treated as sufficient

Files: [docs/JOB-SOURCES.md](https://github.com/QaliAI/ai-job-agent/blob/main/docs/JOB-SOURCES.md), [scripts/ats_engine.py](https://github.com/QaliAI/ai-job-agent/blob/main/scripts/ats_engine.py), [knowledge/ats_patterns.json](https://github.com/QaliAI/ai-job-agent/blob/main/knowledge/ats_patterns.json)

The code includes SmartRecruiters among its default sources and has a SmartRecruiters parser/registry entries. Our own source research has marked SmartRecruiters as blocked pending written authorization or an applicable SAP-endorsed pathway. Publicly reachable/keyless endpoints do not override the terms/policy review.

**Decision for our product:** do not adopt this adapter, query SmartRecruiters for coverage, or count it as a permitted source until the existing permission gate is resolved. Re-review every provider independently before any adapter is considered.

### 4. Medium/high risk — work-mode inference can confuse a text mention with an actual work arrangement

File: [scripts/ats_engine.py](https://github.com/QaliAI/ai-job-agent/blob/main/scripts/ats_engine.py)

The current inference looks for the word “remote” anywhere in title, location or description and can label the role remote without proving the employer permits the candidate's location. “Remote” can appear in a discussion of remote collaboration, an exception, or a location restriction. The schema lacks a separate verified field for country eligibility and work authorization.

**Decision for our product:** retain raw evidence and source-specific geography restrictions separately from inferred work mode. If location or eligibility is ambiguous, keep it unknown and require clarification; never infer “worldwide” from “remote”.

### 5. Medium risk — salary parsing and filtering do not normalize currency/pay period

Files: [scripts/ats_engine.py](https://github.com/QaliAI/ai-job-agent/blob/main/scripts/ats_engine.py), [scripts/filter_jobs.py](https://github.com/QaliAI/ai-job-agent/blob/main/scripts/filter_jobs.py)

The salary parser extracts a narrow set of currency symbols from description text, while the filter compares numeric `salary_max` to a candidate minimum without checking currency or pay period. Candidate preference parsing is dollar-oriented. A numeric comparison across USD, INR, EUR, hourly and annual amounts is not valid.

**Decision for our product:** only compare salary after currency and pay period are known and normalized. Preserve missing/ambiguous compensation as unknown, not zero, and do not reject or promote a job on an incomparable amount.

### 6. Medium risk — claim checker is a useful guardrail, not proof of zero hallucinations

File: [scripts/claim_check.py](https://github.com/QaliAI/ai-job-agent/blob/main/scripts/claim_check.py)

The checker uses a fixed technology list and substring presence in broad profile text to decide whether a skill is grounded; it extracts numbers with regular expressions. This is a useful deterministic warning layer, but presence anywhere in a profile is not the same as evidence that the candidate has the skill, and an unlisted technology or differently phrased claim can escape the catalog. The source code alone does not substantiate the README's absolute “100% grounded” claim.

**Decision for our product:** use claim-level evidence links/IDs, distinguish demonstrated/proficient/exposure/aspirational skills, and test both false positives and false negatives. Treat an automated pass as “no configured checks fired,” not a factual guarantee.

### 7. Medium risk — candidate-facing role filters are not an eligibility engine

Files: [scripts/filter_jobs.py](https://github.com/QaliAI/ai-job-agent/blob/main/scripts/filter_jobs.py), [scripts/daily_workflow.py](https://github.com/QaliAI/ai-job-agent/blob/main/scripts/daily_workflow.py)

The reviewed hard filter covers selected company/title exclusions, a salary comparison, a narrow remote constraint and a couple of clearance phrases. It does not by itself establish degree eligibility, current student status, India/worldwide work authorization, internship cohort requirements, or employer-specific restrictions on AI use. The workflow also auto-generates tailored materials for top-ranked roles, so these omitted gates matter before materials are produced.

**Decision for our product:** separate listing validity, candidate eligibility, role relevance and permission/application-integrity rules. Hard eligibility and employer AI-use restrictions must run before ranking or drafting.

### 8. Operational note — registry geography is not target coverage

The sample company registry contains many US/global tech employers and several large employers with non-India hiring patterns. The registry is a hand-maintained starting list, not evidence that the product covers India-based undergraduate internships. The repo's example morning brief is illustrative, not a measured quality result.

**Decision for our product:** build a bounded and reproducible India/international target sample and report unknowns honestly; do not inherit this registry or cite its example counts as validation.

## Reuse / reject matrix

| Pattern | Decision | Reason |
|---|---|---|
| Canonical job schema and source adapters as an architectural pattern | Reference only | Adapter behavior and source permissions need independent verification |
| Stable IDs and cross-run ledger | Retain concept | Useful for dedupe and safe resume |
| Per-source structured outcomes | Strengthen beyond upstream | Upstream currently collapses some failures into empty results |
| Fail-closed liveness/status verification | Required; do not copy upstream default | Upstream marks access/network errors live |
| Transparent scoring and hard exclusions | Retain concept, redesign gates | Must not replace explicit eligibility evidence |
| Candidate-grounded claim checking | Retain concept, strengthen evidence model | Regex/substring checks are not a factual guarantee |
| SmartRecruiters adapter | Reject pending permission clearance | Conflicts with our documented source-policy hold |
| Entire repo, registry, scripts or dependency stack | Reject for now | No implementation gate passed; avoid importing unverified behavior |

## Acceptance tests added to our project

- **SV-034:** a fetch/parser error must not be represented as a valid empty result; report per-source outcome and preserve prior state on partial failure.
- **SV-035:** 403, timeout, DNS failure or verifier exception must yield unknown/unverified, not live/open.
- **SV-036:** work-mode, country eligibility and compensation must not be inferred from ambiguous text or compared without currency/pay-period normalization.
- **SV-037:** no source adapter can be used merely because an endpoint is public/keyless; source-specific permission must be cleared first.

These are proposed acceptance tests for our future implementation, not code changes or test runs.

## References

- Upstream repository and MIT license: https://github.com/QaliAI/ai-job-agent
- Upstream source reference: https://github.com/QaliAI/ai-job-agent/blob/main/docs/JOB-SOURCES.md
- Upstream verifier: https://github.com/QaliAI/ai-job-agent/blob/main/scripts/verify_postings.py
- Upstream ATS engine: https://github.com/QaliAI/ai-job-agent/blob/main/scripts/ats_engine.py
- Upstream filter: https://github.com/QaliAI/ai-job-agent/blob/main/scripts/filter_jobs.py
- Upstream claim checker: https://github.com/QaliAI/ai-job-agent/blob/main/scripts/claim_check.py
- Our SmartRecruiters policy review: https://github.com/rajaryan1111/ai-career-agent/blob/main/research/smartrecruiters-api-policy-review-2026-10-13.md
- Our source validation suite: https://github.com/rajaryan1111/ai-career-agent/blob/main/research/source-validation-test-suite-2026-10-13.md

## Final decision

The repo is a strong source of product ideas, but **not a drop-in foundation**. Its fail-open verifier and error/empty conflation are direct counterexamples to the reliability behavior we need. Keep our implementation gate closed until the source feasibility, permission, quality, privacy and zero-cost gates pass. No code, dependencies, credentials, candidate data, live source queries or application actions were used in this review.
