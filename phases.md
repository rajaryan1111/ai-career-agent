# Research and Delivery Phases

**Status:** Production-oriented implementation and evidence-gated source research in parallel  
**Last updated:** 2026-10-14

## Product north star

Deliver a downloadable, maintainable career-automation product that real candidates can use—not a demo-only prototype. It should serve candidates across industries and experience levels through a shared core plus extensible occupation-specific intelligence. It should search on a configurable schedule (default 00:00 and 12:00 Asia/Kolkata), and laptop-independent operation requires a separately verified always-on worker. Selection is an employer decision and is never guaranteed.

## Phase 0 — Product contract and risk controls

**Goal:** Keep the product promise, user control, safety boundaries, and measurable quality criteria consistent across all six canonical documents.

Tasks: maintain the cross-industry scope; distinguish implemented, gated, experimental, and production-supported capabilities; preserve candidate truth, privacy, source permission, and evidence-backed application state.

Exit criteria: PRD, architecture, rules, design, and memory agree; no stale statement says implementation is unauthorized or that the product is research-only.

## Phase 1 — Usable local desktop workflow

**Goal:** Turn the existing offline core into a usable end-to-end local application.

Tasks: implement the chosen Python/Tkinter local shell; candidate profile editing; manual job entry; hard eligibility and explainable matching; shortlist; application ledger/status evidence; persistent SQLite storage; export/delete; and clear unsupported-source states. Resume parsing is deliberately deferred to a follow-on local-only increment so it does not block a complete, testable first workflow.

Exit criteria: a user can configure a profile, add and evaluate a job, shortlist only an explicitly eligible job, track application state with evidence for confirmation, export/delete local data, restart the app, and find saved state intact without a network connection or paid API. Automated tests and manual GUI smoke tests cover critical workflows and invalid inputs. This is an internal local alpha, not the final product. The manual test protocol is recorded in [the local-alpha smoke-test checklist](research/local-alpha-manual-smoke-test-checklist-2026-10-14.md); it must be executed before GUI acceptance is claimed.

### Phase 1B — Local resume import and profile review

Add PDF/DOCX parsing only after the profile/job workflow is stable. Parsing must run locally, retain source text/field provenance where practical, mark uncertain fields for user review, and never silently promote extracted guesses to verified facts. OCR remains optional and must not become a mandatory paid dependency.

## Phase 2 — Product reliability and security foundation

**Goal:** Make the application recoverable, maintainable, and safe before external actions are enabled.

Tasks: schema migrations; backup/restore; secure secret storage; redacted logs; data export/deletion; packaging/install/update strategy; threat model; test fixtures; crash recovery; adapter capability/status UI; and regression tests.

Exit criteria: repeatable installation and recovery tests pass; privacy/security boundaries are documented and enforced; no secrets or real candidate data enter source control or test fixtures.

## Phase 3 — Source permission and job-quality validation

**Goal:** Prove that source integrations are permitted and useful, not merely technically reachable.

Tasks: finish the 50-record validation sample; measure direct employer application-link outcomes using a defined denominator; validate source terms and attribution/caching/rate limits; prove source-level error semantics; and identify a minimum set of useful permitted sources. Keep discovery and submission permissions separate.

Exit criteria: documented evidence for each enabled source; quality thresholds met or explicitly revised with rationale; unresolved providers remain disabled. The current source-quality gate remains NOT PASSED until the research record says otherwise.

## Phase 4 — Cross-industry matching validation

**Goal:** Ensure the product is not effectively an AI/ML-only tool.

Tasks: create privacy-safe, human-reviewed resume/job-description test sets across representative domains (for example design, VLSI/embedded, mechanical, civil, software/data, and business); define occupation-aware skill and credential schemas; evaluate extraction and top-ranked relevance separately from hard eligibility.

Proposed initial thresholds (not yet achieved):
- At least 95% exact extraction accuracy on selected critical fields for parseable resumes.
- At least 80% precision in the top 10 recommendations against a predefined human-reviewed relevance standard.
- Zero known hard-eligibility violations among recommendations marked eligible.
- No duplicate submissions caused by retries.
- No confirmed status without reliable evidence.

Exit criteria: reproducible evaluation results and explicit coverage gaps by occupation group.

## Phase 5 — Background execution and scheduled discovery

**Goal:** Deliver reliable 00:00/12:00 IST runs, including when the user's laptop is off.

Tasks: design a durable queue and worker boundary; compare free/low-cost always-on deployment options; implement health status, missed-run catch-up, idempotent processing, bounded retries, rate limits, and per-source outcome reporting; clearly disclose any remote data transfer and provider limits.

Exit criteria: observed scheduled runs, laptop-off behavior, restart recovery, duplicate prevention, and outage reporting are tested in the chosen deployment. Do not claim this capability until verified.

## Phase 6 — Permitted platform adapters and application automation

**Goal:** Expand from manual/local workflow to real, validated application flows.

Tasks: begin with read-only discovery adapters only after each source's permission gate passes; validate listing freshness and direct application routes; implement platform-specific preparation/submission adapters only when permitted; configure standing user policies; record all actions and evidence; pause only the affected workflow on uncertainty and continue independent safe work.

Exit criteria: each advertised source/workflow has current permission evidence, deterministic fixtures, integration tests, failure recovery, duplicate protection, and real-world pilot validation. CAPTCHA/OTP, access-control, anti-bot, and employer restrictions are never bypassed.

## Phase 7 — Email, interview lifecycle, and career intelligence

**Goal:** Support the journey beyond initial application without expanding permissions silently.

Tasks: optional least-privilege email integration; confirmation and interview detection; follow-up drafts/reminders; job-specific truthful resume/cover-letter versions; company research with evidence; and career analytics that separate activity metrics from outcomes.

Exit criteria: integrations are revocable, external data boundaries are explicit, and all generated claims are traceable to verified candidate facts or cited sources.

## Phase 8 — Pilot, release, and continuous maintenance

**Goal:** Prove the product useful in real life and keep it working as sources change.

Tasks: pilot with consenting users from more than one occupation group; measure time saved, matching quality, form/adapter failure rates, application integrity, user trust, and response/interview outcomes without promising selection; establish release notes, versioning, support/error reporting, and periodic platform-policy reviews.

Exit criteria: installation, upgrades, recovery, privacy/security checks, and pilot acceptance criteria pass; release claims match tested coverage; unsupported roles/sources are labeled honestly.

## Current implementation status

The offline domain core, the SQLite persistence layer, and the Tkinter local desktop alpha (`python -m career_agent`) are implemented, with 192 standard-library tests passing locally and a Python 3.10–3.12 CI workflow running the suite, compilation checks, and the research-CSV audit. The tests cover the domain rules, persistence (including file-backed restart durability), untrusted-URL validation, the fail-closed source permission gate and run-outcome rules, the tracker confirmation-evidence
floor and the backed-up record-correction tool, the Tk-free desktop logic, and the desktop handlers through widget stubs; they do not cover widget rendering, a real Tk session, or any operating-system integration, so the manual GUI smoke test — including macOS/Apple Silicon — remains outstanding.

A local resume parser, remote scheduler, live source connectors, email integration, and real application adapters are not yet implemented/verified. The source-quality gate remains NOT PASSED; no live integration or application automation should be represented as production-ready. Safe local product implementation is authorized and should proceed now.
