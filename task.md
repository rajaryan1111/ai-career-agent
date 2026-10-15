# AI Career Agent — Product Execution Backlog

**Last updated:** 2026-10-16  
**Purpose:** Actionable task inventory derived from the product vision. Completion must be based on verified implementation and test evidence.

## Product outcome
After resume upload and one-time setup, the agent should autonomously discover relevant jobs twice daily, evaluate fit and eligibility, prepare truthful application materials, submit through permitted supported workflows, send authorized personalized HR outreach, track actual replies/outcomes, prevent duplicates and proactively report progress. Routine actions inside saved global policy should not require per-application approval.

## P0 — Inspect current implementation and finish offline contact import
- [ ] Inspect existing resume/CSV importers, SQLite schema/migration contract, desktop views, activity events, backup/restore and tests before adding abstractions.
- [ ] Complete CSV parse/preview/review with synthetic fixtures; handle BOM, encoding, missing/extra columns, blank rows and row-level validation.
- [ ] Detect normalized-email duplicates, suspicious syntax, missing names, conflicting person/company metadata and repeated records.
- [ ] Keep import read-only until explicit user confirmation; show review summary and rejected-row reasons.
- [ ] Persist only through migration-safe existing store paths; preserve suppression/opt-out history across re-imports.
- [ ] Test cancellation/no-write, duplicate imports, malformed files, conflicts, backup/restore and regression behavior.
- [ ] Never include contact data in public fixtures, logs, screenshots or repository files.

## P1 — Resume intelligence and one-time onboarding
- [ ] Inspect existing resume ingestion and reuse supported PDF/DOCX/text paths.
- [ ] Normalize skills, education, graduation year, projects, experience, links, location and job-relevant facts.
- [ ] Store provenance per extracted fact and distinguish confirmed, uncertain and missing values.
- [ ] Add profile review/edit and ask only for required missing information.
- [ ] Configure target roles (AI/ML Engineer, Applied AI Engineer, AI Engineer, Forward Deployed Engineer and relevant internships), work/location preferences, eligibility, exclusions and limits.
- [ ] Never invent skills, employment, grades, legal eligibility or screening answers.

## P2 — Durable application ledger and deduplication
- [ ] Audit existing job/application/event schema and reuse it where possible.
- [ ] Define stable job/application identity across sources and discovery runs.
- [ ] Track discovered, evaluated, prepared, blocked, submitted, submission-unknown, interview, assessment, rejected, offer, withdrawn and follow-up-due states as applicable.
- [ ] Store timestamps, source URLs, external identifiers, artifact versions, decision reasons and submission evidence.
- [ ] Make side effects idempotent; reconcile uncertain outcomes before retrying.
- [ ] Test duplicates across restarts, migrations, backups and restoration.

## P3 — Source feasibility and twice-daily discovery
- [ ] Create a feasibility/permission matrix for official company career pages, supported ATS/public feeds, LinkedIn, Unstop, Internshala, Naukri.com and other relevant sources.
- [ ] For each source document permitted access, authentication, terms, rate limits, freshness, fields, failure modes and submission capability.
- [ ] Implement timezone-aware morning/evening scheduling with next-run display, run history, bounded retries, cancellation and pause/stop.
- [ ] Record posting freshness, deadline, location, eligibility evidence and canonical application route.
- [ ] Keep each source disabled until its own permission, quality and test gate passes; do not claim universal coverage.

## P4 — Tailoring and permitted autonomous applications
- [ ] Generate role-specific resume/cover letter versions from verified facts; preserve the original and version outputs.
- [ ] Validate required fields, eligibility and policy before executing an application.
- [ ] Implement only source-specific submission routes that are supported, permitted and testable.
- [ ] Allow routine submissions without per-job approval when they fit saved global authorization and require no unresolved fact or human attestation.
- [ ] Stop affected applications for missing information, sensitive/legal attestations, identity verification, CAPTCHA/OTP, platform restrictions or suspicious postings.
- [ ] Mark submitted only with evidence; represent uncertain outcomes distinctly and never blindly retry.
- [ ] Use mocks in tests; never submit real applications from tests.

## P5 — Private HR outreach and inbox reconciliation
- [ ] Connect a supported mail provider with least-privilege permissions; never store plaintext passwords or commit tokens.
- [ ] Keep HR contacts in private local storage; retain provenance and review ambiguous records.
- [ ] Enforce email normalization, duplicate checks, opt-out/suppression, prior-send checks, campaign limits and contact-level idempotency.
- [ ] Generate personalized internship outreach and attach the correct resume version.
- [ ] Enable real sending only after explicit global authorization, permission checks and end-to-end safety tests.
- [ ] With separately authorized mailbox access, track actual replies, bounces and delivery evidence; do not infer replies.
- [ ] Add follow-up intervals/limits and respect opt-outs and prior contact history.

## P6 — Reporting, safety and release
- [ ] Build dashboard for discovery runs, applications, HR outreach, replies, interviews, deadlines, blockers and next actions.
- [ ] Provide configurable run notifications and daily/weekly summaries with truthful, evidence-backed states.
- [ ] Provide pause/resume, stop-all, source revocation, export/delete and privacy controls.
- [ ] Verify backup/restore, recovery, secrets handling, logging redaction, scheduler behavior and migration safety.
- [ ] Run focused and full regression suites; report exact commands/results and limitations.
- [ ] Document only verified capabilities and source coverage.

## Non-negotiable engineering rules
- Inspect and reuse existing implementation before adding modules, schemas or abstractions.
- Keep main unchanged and do not merge/close PR #2 as part of this work.
- Do not enable live discovery, email sending or application submission before relevant gates pass.
- No CAPTCHA/OTP bypass, anti-bot evasion, prohibited scraping, fabricated profile facts or unapproved external data transfer.
- No real external side effects in tests.
- Never claim completion without code and test evidence.
