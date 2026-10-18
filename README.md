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
- Application preparation: a readiness checklist over the eligibility result, a draft preview assembled only from recorded facts, duplicate-application blocking, and an explicit local `prepared` state recorded in the attempt history.
- Local SQLite persistence for profile, job, attempt, and history records, including explicit delete operations.
- No network access, resume parsing, candidate-data transfer, form filling, or application submission.

The local alpha supports manual candidate-profile entry, manual job entry, eligibility evaluation, shortlisting only on explicit eligibility PASS, application preparation with a readiness checklist and a fact-only draft preview, tracker status changes guarded by the domain state machine, per-attempt history with evidence, re-application after withdrawal, local JSON export, and explicit delete controls. A status change advances the current attempt; only a withdrawal can be followed by a new attempt, and only when the listing is still open and eligible. PDF/DOCX parsing is deferred to a follow-on local-only increment. Job-source adapters remain disabled until their source-specific permissions and quality checks are resolved.

Existing databases are upgraded in place to schema version 2 (one attempt per legacy tracker row, revision 0). History is not invented for records that predate the upgrade.

## Install

No runtime dependency beyond the Python standard library and Tk is required. An editable install adds the `career-agent` command:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
career-agent --help
```

The package declares Python 3.10–3.12 in [pyproject.toml](pyproject.toml). Editable installs are verified locally; no wheel, installer, updater, or code-signing pipeline exists yet.

## Run the desktop app

Python 3.10+ with Tkinter available:

```bash
python -m career_agent
```

Candidate data is stored in the operating system's per-user application-data directory, not inside the repository. To use the core tests in a headless environment, no display is required.

To run against a specific database, for example a disposable one while testing restore:

```bash
python -m career_agent --database /tmp/career-agent-test.sqlite3
```

A supplied path is created when absent, opened and upgraded to the current schema when it already exists, and never replaced. Its parent directory must already exist; otherwise the app prints an error and exits with status 2. Omitting `--database` keeps the per-user default, and `--help` never touches either database.

## Audit research data

To regenerate a reproducible CSV integrity summary (including input SHA-256, row/column counts, duplicate IDs, canonical URL groups, status and permission counts):

```bash
python scripts/audit_job_source_csv.py
```

The tool intentionally does not invent a direct-link validity percentage; the existing route observations do not provide a defensible uniform denominator.

## Run tests

Python 3.10+; no third-party packages are required. The single reproducible command runs the unit suite, the tracker smoke test, `compileall`, and the CSV audit, and exits nonzero if any step fails:

```bash
python scripts/smoke_check.py
```

Run one step alone when iterating:

```bash
python -m unittest discover -s tests -v
```

## Tracker integrity smoke test

```bash
python scripts/tracker_smoke_test.py
```

Runs end-to-end scenarios against temporary databases only: schema version 2, attempt creation, persisted transitions, evidence surviving later status changes, fresh re-application, rejected invalid/stale/duplicate writes, withdrawal history, format-v3 backup contents, backup round-trip into a separate database, a tampered backup being rejected without mutation, consistency after failures, and in-place migration of a schema-v1 database. Exit code 0 means every scenario passed; 1 means at least one failed. Add `--keep` to retain the temporary workspace for inspection. The script never opens the application-data database.

The throwaway database, profile, and listings are synthetic. The smoke test includes a negative control: a backup with a tampered event history must be rejected, and the target database must remain unchanged.

## Job sources and discovery

Discovery is **disabled** in this build. `career_agent/sources.py` defines the adapter contract — source identity, documented access method, permission evidence, review date, capabilities (discovery and submission are separate), local rate limit, timeout, and support status — plus typed outcomes that keep a valid empty result distinct from blocked, rate-limited, timeout, and transient or schema failures.

The registry lists manual entry as the only enabled source. Himalayas and SmartRecruiters remain blocked because their terms conflict with automated gathering or autonomous AI workflows and no written authorization is recorded. `SOURCE_QUALITY_GATE_PASSED` stays false, the **Sources & settings** tab states this, and no adapter performs network access. Enabling a provider requires recorded permission evidence and a completed review; scraping public pages, bypassing access controls, or flipping the gate without evidence is out of scope. See [the source-quality gate assessment](research/source-quality-gate-assessment-2026-10-14.md) and [the permission decision matrix](research/source-permission-decision-matrix-2026-10-14.md).

## Backup and restore

The JSON file written by **Tracker → Export backup (JSON)** is a complete local backup (format version 3), not a report:

- candidate profile;
- every job with its observation timestamps and full eligibility fields;
- every application attempt, including its revision and last-updated time;
- the append-only event history for each attempt.

The research CSV produced by `scripts/audit_job_source_csv.py` is a report over the source-audit seed file. It is **not** a backup and cannot restore the application.

To restore, use **Tracker → Restore from backup…**. The file is parsed, validated, and only then written. Restoring replaces all local profile, job, attempt, and history records, so the app asks for confirmation whenever data already exists; cancelling that prompt writes nothing. The same operations are available in code:

```python
from career_agent import CareerStore, restore_export_file, restore_from_backup, write_export

with CareerStore("backup-target.sqlite3") as store:
    write_export(store, "backup.json")             # create a backup
    restore_export_file(store, "backup.json")       # only into an empty database
    # Replace after an explicit decision; returning False leaves the data untouched.
    restore_from_backup(store, "backup.json", confirm=lambda counts: True)
```

Safety contract:

- Validation covers the format and schema version, required fields and types, status values, duplicate listing/attempt identifiers, confirmation evidence, event ordering, and a replay of each attempt's status chain. Unknown fields, malformed JSON, non-UTF-8 input, empty files, and files over 10 MiB are rejected.
- Restore is replace-only; it never merges. A non-empty database is refused unless replacement is explicitly requested, and `restore_from_backup` always asks `confirm` before replacing (declining returns `None` with nothing written).
- Deleting existing data and writing restored data happen in one SQLite transaction. Any failure rolls the whole operation back, leaving the previous database intact and usable.
- Version 2 exports are still accepted, but they lack job and attempt timestamps and revisions. Those fields default to the import time and revision 0, so a version 2 restore is semantically complete but not byte-for-byte faithful. Unsupported versions are refused.
- There are no automatic or scheduled backups; creating one is a manual action.
- The restore dialog is wired to this contract, but the GUI has not been exercised in an automated or headless session here; desktop acceptance still depends on the manual checklist.

The GitHub Actions workflow runs this smoke test together with the unit suite, `compileall`, and the CSV audit on Python 3.10–3.12 for pushes to `main`, for all pull requests, and on manual dispatch. A failing scenario fails the job. Branch pushes are not built separately: an open pull request already runs the matrix for each pushed commit, so the same commit is not checked twice.

Changes reach `main` only through a pull request, and merging requires the `unit-tests (3.10)`, `unit-tests (3.11)`, and `unit-tests (3.12)` checks from GitHub Actions. Zero approvals are required, so a pull request is a review gate without a mandatory reviewer. Direct pushes are rejected, administrator enforcement is enabled, no bypass actor is configured, and force pushes and branch deletion are disabled.

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
