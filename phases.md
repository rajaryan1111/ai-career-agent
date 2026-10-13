# Research and Delivery Phases

**Status:** Research and safe-core implementation in parallel  
**Last updated:** 2026-10-13

## Phase 0 — Product framing (current)

**Goal:** Establish the problem, user promise, boundaries, and decision criteria.

Tasks: maintain product vision/open questions; confirm local-first, quality-first, hybrid automation and zero mandatory recurring cost; separate discovery from submission; define confirmed application; identify initial validation segments.

Exit criteria: product principles agreed, critical assumptions ranked, and no unresolved ambiguity about truthful applications or platform compliance.

## Phase 1 — Competitor and market research

**Goal:** Understand existing products and identify a real gap.

Tasks: research job aggregators, application autofill/auto-apply products, resume tools, and trackers; verify features, limitations, pricing, and user feedback; identify unmet needs; record sources and research dates.

Exit criteria: sourced competitor matrix and specific gaps identified—or evidence-based conclusion that differentiation is weak.

## Phase 2 — Job-source and platform feasibility

**Goal:** Establish realistic discovery and submission coverage.

Tasks: audit LinkedIn, Internshala, Naukri, Indeed, Wellfound, and company career pages; verify official APIs, permitted feeds, terms, rate limits and submission workflows; assess discovery and submission separately; identify at least three useful discovery sources with documented permitted access and at least one legitimate, testable application workflow; explicitly mark unsupported/unknown paths.

Exit criteria: evidence-backed source capability matrix, no required workflow depends on bypassing restrictions, and practical zero-cost baseline identified or rejected with evidence.

## Phase 3 — Quality and privacy validation plan

**Goal:** Define objective tests before building.

Tasks: design representative resume and human-reviewed job matching sets; define hard eligibility and false-positive metrics; define duplicate detection and application status integrity tests; define local data and external-processing threat model.

Proposed initial thresholds (not achieved):
- At least 95% exact extraction accuracy on selected critical fields for parseable resumes.
- At least 80% precision in the top 10 recommendations against a predefined human-reviewed relevance standard.
- Zero known hard-eligibility violations among recommended jobs.
- No duplicate submissions caused by retries.
- No confirmed status without reliable evidence.

Exit criteria: repeatable test protocol and documented thresholds.

## Phase 4 — Product requirements and UX specification

Finalize the user journey, application states, profile/preferences, source status, application history, company research reports/citations, exception UX, offline scheduling/recovery, and data export/deletion/privacy disclosures.

Exit criteria: PRD/design reviewed and MVP scope excludes unsupported/unverified capabilities.

## Phase 5 — Architecture and implementation decision gate

Compare desktop frameworks and local storage, decide local parsing/matching, packaging/update strategy, and realistic maintenance cost. Create implementation plan only after the gate passes.

Exit criteria: architecture justified by evidence; budget/platform scope explicit; go/no-go decision recorded.

## Phase 6 — MVP implementation (safe offline core started)

Implementation is authorized for dependency-free, offline domain logic and tests while research continues. The first increment covers eligibility, transparent relevance indicators, conservative deduplication, URL/provenance separation, and guarded application-state transitions. Do not add live source connectors, resume ingestion, candidate-data transfer, autofill, or submission until their specific gates pass.

## Phase 7 — Controlled pilot and expansion (future)

Pilot with consenting users, measure matching quality/time saved/failure rates/application integrity, expand candidate segments and source coverage only after quality targets are met, and re-check platform policies regularly.

## Current phase status

Safe offline-core implementation has started; source-permission and job-quality research continues in parallel. The source-quality gate remains NOT PASSED, so no live source integration or application automation is authorized.
