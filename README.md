# AI Career Agent

AI Career Agent is being built as a local-first desktop assistant for job discovery, eligibility review, explainable matching, application preparation, and application tracking.

## Current implementation

The project now includes a small offline desktop alpha launched with `python -m career_agent`. It uses Python's standard-library Tkinter UI and local SQLite. It is not yet packaged for end users, and GUI smoke testing is still required on supported operating systems.

The dependency-free Python domain core in `career_agent/` provides:

- Three-valued hard eligibility checks: `pass`, `fail`, and `unknown`.
- Separate country eligibility from optional exact-match work-authorization requirements.
- An `open` status without a recorded availability evidence/note remains `unknown` for eligibility.
- Explicit country/work eligibility handling; worldwide eligibility passes only when explicitly recorded.
- Transparent skill overlap and missing-skill explanations, separate from eligibility.
- Conservative URL/requisition deduplication.
- Separate source-listing and employer-application URLs.
- Guarded application status transitions; confirmation requires evidence.
- Append-only application history: each persisted status change is recorded, and the evidence behind a confirmation is never erased by a later transition.
- Applications are attempts: a withdrawal is preserved as an immutable record, and re-applying creates a new attempt for the same listing instead of reviving the old one.
- Optimistic concurrency: a stale window cannot silently overwrite a newer application status.
- One active application per identified job; a duplicate source observation cannot be shortlisted twice.
- Local SQLite persistence for profile, job, attempt, and history records, including explicit delete operations.
- No network access, resume parsing, candidate-data transfer, form filling, or application submission.

The local alpha supports manual candidate-profile entry, manual job entry, eligibility evaluation, shortlisting only on explicit eligibility PASS, tracker status changes guarded by the domain state machine, per-attempt history with evidence, re-application after withdrawal, local JSON export, and explicit delete controls. A status change advances the current attempt; only a withdrawal can be followed by a new attempt, and only when the listing is still open and eligible. PDF/DOCX parsing is deferred to a follow-on local-only increment. Job-source adapters remain disabled until their source-specific permissions and quality checks are resolved.

Existing databases are upgraded in place to schema version 2 (one attempt per legacy tracker row, revision 0). History is not invented for records that predate the upgrade.

## Run the desktop app

Python 3.10+ with Tkinter available:

```bash
python -m career_agent
```

Candidate data is stored in the operating system's per-user application-data directory, not inside the repository. To use the core tests in a headless environment, no display is required.

## Audit research data

To regenerate a reproducible CSV integrity summary (including input SHA-256, row/column counts, duplicate IDs, canonical URL groups, status and permission counts):

```bash
python scripts/audit_job_source_csv.py
```

The tool intentionally does not invent a direct-link validity percentage; the existing route observations do not provide a defensible uniform denominator.

## Run tests

Python 3.10+; no third-party packages are required.

```bash
python -m unittest discover -s tests -v
```

## Tracker integrity smoke test

```bash
python scripts/tracker_smoke_test.py
```

Runs end-to-end scenarios against temporary databases only: schema version 2, attempt creation, persisted transitions, evidence surviving later status changes, fresh re-application, rejected invalid/stale/duplicate writes, withdrawal history, format-v2 export with attempts and events, consistency after failures, and in-place migration of a schema-v1 database. Exit code 0 means every scenario passed; 1 means at least one failed. Add `--keep` to retain the temporary workspace for inspection. The script never opens the application-data database.

The throwaway database, profile, and listings are synthetic. There is no import/restore API yet, so the export contract is validated but not round-tripped.

## Safety and product principles

- Keep candidate profile and application history local by default.
- Missing eligibility evidence is not a pass.
- A visible Apply button is not proof that a job is open or that submission succeeded.
- Never infer worldwide eligibility from the word “remote.”
- Do not fabricate candidate facts or screening answers.
- Do not bypass source restrictions or add unapproved connectors.
- A relevance score is not a hiring probability.
- The current alpha does not submit applications. Future automated actions require source/employer permission, reliability evidence, and a scoped, revocable policy; no blanket permission is implied.

## Project status

The local-only desktop alpha is implemented and source research continues in parallel. It is not yet a packaged production release; follow the manual GUI smoke-test checklist before claiming desktop acceptance. This does **not** mean the source-quality gate has passed or that live discovery/application workflows are ready. See [the local-alpha smoke-test checklist](research/local-alpha-manual-smoke-test-checklist-2026-10-14.md) and [the current source-quality gate assessment](research/source-quality-gate-assessment-2026-10-14.md).
