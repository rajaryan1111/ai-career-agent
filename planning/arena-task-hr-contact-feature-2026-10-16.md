# Arena Task — Plan HR Contact Import + Duplicate-Safe Internship Workflow

You are working in `rajaryan1111/ai-career-agent` on branch `arena/351e052d-ai-career-agent`. This is a planning-first task. Read the current code, `phases.md`, source-gate implementation, tracker/store/schema, tests, and the documents below before proposing changes.

## Read first

- `planning/hr-contact-outreach-and-application-tracking-2026-10-16.md`
- `research/hr-contact-list-audit-2026-10-15.md`
- Existing phase status, source permission model, application tracker, storage/migrations, and threat model.

## Goal

Plan a safe workflow that imports a reviewed HR contact CSV, matches relevant internship/job opportunities, prepares tailored résumé/email drafts, prevents duplicate outreach and duplicate applications, and shows the user exactly where/when they contacted/applied and what happened.

## Non-negotiable current gates and repo constraints

- Preserve `SOURCE_QUALITY_GATE_PASSED = False` and empty `enabled_discovery_sources()` unless separate source-validation evidence is reviewed and explicitly approved.
- No live discovery, external email, or application submission while gates are closed.
- Do not add a hidden send/submit path or auto-apply behavior that can run without explicit per-action approval.
- Do not scrape, evade source terms, bypass CAPTCHA/OTP/access controls, use stealth/proxy/cookie-session tricks, or introduce unapproved adapters.
- Do not commit HR names/emails or either raw contact CSV to this public repository.
- Do not change `main`, force-push, rewrite history, or merge/close PR #2. Work only on the named Arena branch.
- Do not claim tests/manual checks passed unless actually run and evidenced.
- No external service receives résumé/profile/contact data without explicit informed user consent and data minimization.

## Work requested now

1. Inspect the existing architecture and map which parts already satisfy the planning spec. Do not duplicate existing functionality.
2. Produce a gap analysis: current capability, missing capability, data/schema implications, risks, tests, and dependencies.
3. Propose a small, phased implementation plan with acceptance criteria and file-level scope. Separate offline import/draft/tracking from any external integration.
4. Identify the exact gate evidence needed before a source adapter, email provider, or application submission can be enabled.
5. Design idempotency and duplicate checks across contact imports, outreach, job listings, and applications. Cover ambiguous matches and retries after timeouts.
6. Define a truthful application history/event model so a record only says `contacted` or `submitted` after verifiable confirmation; include approval and evidence references.
7. Include suppression/opt-out, bounce handling, privacy/retention, local-first storage, user-visible pause, and audit export.
8. Add the proposed plan to project planning docs only. Do not implement sending/submission in this task. If a small offline-only documentation correction is needed, keep it minimal and testable.
9. Report exact changed files, tests run, test results, remaining gates, and any unresolved risks.

## Required output

Create/update a focused planning document that includes: architecture fit, phases, migration plan, duplicate-key proposal, state machine, approval UX, privacy/security threat model, acceptance tests, and blocked prerequisites. Finish with a concise summary and do not merge the PR.
