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
- Local SQLite persistence for profile, job, attempt, and history records, including per-record delete operations and a confirmed **Delete all local data** action that removes the profile, listings, attempts and history in one transaction.
- No network access, resume parsing, candidate-data transfer, form filling, or application submission.

The local alpha supports manual candidate-profile entry, local resume import for review, manual job entry, eligibility evaluation with an append-only audit record for every explicit decision (rule version plus versioned input fingerprints), shortlisting only on explicit eligibility PASS, application preparation with a readiness checklist and a fact-only draft preview, tracker status changes guarded by the domain state machine, per-attempt history with evidence, re-application after withdrawal, local JSON export, explicit delete controls, and a close confirmation when the profile form has unsaved edits. A status change advances the current attempt; only a withdrawal can be followed by a new attempt, and only when the listing is still open and eligible. Resume import covers text-based PDF, DOCX, TXT, and MD files and never saves extracted values automatically; scanned PDFs need OCR, which is not provided. Job-source adapters remain disabled until their source-specific permissions and quality checks are resolved.

Existing databases are upgraded in place to schema version 3: a schema-1 database first becomes schema 2 (one attempt per legacy tracker row, revision 0) and then gains the `eligibility_decisions` table, which is created empty. No existing row is rewritten and history is not invented for records that predate an upgrade. A database written by a newer build is refused rather than downgraded.

## Install

No runtime dependency beyond the Python standard library and Tk is required. An editable install adds the `career-agent` command:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
career-agent --help
```

The package declares Python 3.10–3.12 in [pyproject.toml](pyproject.toml). Editable installs are verified locally; no wheel, installer, updater, or code-signing pipeline exists yet.

Tk is not a pip dependency. If `import tkinter` fails, install the matching system package for your interpreter (for example `brew install python-tk@3.12` on Homebrew, `sudo apt install python3-tk` on Debian/Ubuntu, or the official python.org installer on macOS/Windows).

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

For support requests and release checks, `--diagnostics` prints environment facts without starting the app, opening a record, or creating anything:

```bash
python -m career_agent --diagnostics
```

It reports the version, Python and platform, Tkinter availability, whether the default database exists and at which schema version, the source-quality gate state, and the number of enabled discovery sources. It never prints candidate record contents.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'career_agent'`** — run the command from the repository root, or install the package first with `python -m pip install -e .`.
- **`ModuleNotFoundError: No module named '_tkinter'`** — the interpreter lacks Tk. Install it with your platform's package manager or use the python.org build. Unit tests do not need Tk; scripted GUI tests skip when it is unavailable.
- **`TclError: no display name and no $DISPLAY environment variable`** — the session is headless. Run the app on a desktop session; the test suite still runs.
- **Exit status 2 immediately after launch** — the `--database` parent directory does not exist. Create it, or omit `--database` to use the per-user location. The app never creates parent directories for a supplied path.
- **`sqlite3.OperationalError: database is locked`** — another instance (or a backup tool) holds the file. Close the other instance and retry; the app does not delete or reset the database automatically.
- **`Permission denied` writing the database** — check ownership and mode. On POSIX the app restricts the file to mode `0600`; restore write permission for the owning user rather than widening access.
- **A backup is refused** — check the error text: unsupported `format_version`, files above 10 MiB, non-UTF-8 content, and tampered event histories are rejected deliberately. Restore is replace-only and validates everything before writing.
- **A resume imports nothing** — only text-based PDF, DOCX, TXT, and MD are supported, and extraction relies on labelled lines. Scanned PDFs need OCR, which is not included; image-only files are reported as having no extractable text.
- **Discovery is disabled** — this is intentional. The source-quality gate stays closed until a provider's written permission is recorded; see [Job sources and discovery](#job-sources-and-discovery).

For a support report, include the `--diagnostics` output and the exact command and error text. Do not attach your database or resume files.

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

Runs end-to-end scenarios against temporary databases only: schema version 3, attempt creation, persisted transitions, evidence surviving later status changes, fresh re-application, rejected invalid/stale/duplicate writes, withdrawal history, eligibility-decision persistence across reopen, export, restore and deletion, format-v4 backup contents, backup round-trip into a separate database, a tampered backup being rejected without mutation, consistency after failures, and in-place migration of a schema-v1 database. Exit code 0 means every scenario passed; 1 means at least one failed. Add `--keep` to retain the temporary workspace for inspection. The script never opens the application-data database.

The throwaway database, profile, and listings are synthetic. The smoke test includes a negative control: a backup with a tampered event history must be rejected, and the target database must remain unchanged.

## Resume import

**Candidate profile → Import resume (review)…** reads DOCX (text body), text-based PDF, TXT, and MD files with the standard library only — no extra dependency and no upload. Extraction is deliberately conservative:

- Only explicitly labelled lines become proposals (`Skills:`, `Country:`, `Degree:`, `Graduation year:`, `Experience:`, `Work authorization:`, `Preferred …:`). Unlabelled sentences are never turned into facts.
- Each proposal carries the evidence line it came from and is marked for review.
- Proposals fill the profile form; nothing is written until you click **Save profile locally**, and nothing is sent anywhere.
- Encrypted PDFs, malformed DOCX files, non-UTF-8 text, empty files, unsupported extensions, and files over 5 MiB are refused with an actionable message.
- Scanned or image-only PDFs are reported as needing OCR rather than being treated as an empty resume.

This is not a full parser: contact fields, projects, certifications, tables, multi-column layouts, and unusual fonts are out of scope, and every imported value must be reviewed against the original document.

## Job sources and discovery

Discovery is **disabled** in this build. `career_agent/sources.py` defines the adapter contract — source identity, documented access method, permission evidence, review date, capabilities (discovery and submission are separate), local rate limit, timeout, and support status — plus typed outcomes that keep a valid empty result distinct from blocked, rate-limited, timeout, and transient or schema failures. `run_discovery` enforces a bounded retry policy (at most five attempts, capped exponential backoff, injectable sleep for tests), never retries schema errors, rejects records that are not listings, and suppresses duplicate observations before reporting how many it collapsed.

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

- Validation covers the format and schema version, required fields and types, status values, duplicate listing/attempt/decision identifiers, confirmation evidence, event ordering, a replay of each attempt's status chain, and each audit record's rule version, outcome, fingerprints and requirement trail. Unknown fields, malformed JSON, non-UTF-8 input, empty files, and files over 10 MiB are rejected.
- Restore is replace-only; it never merges. A non-empty database is refused unless replacement is explicitly requested, and `restore_from_backup` always asks `confirm` before replacing (declining returns `None` with nothing written).
- Deleting existing data and writing restored data happen in one SQLite transaction. Any failure rolls the whole operation back, leaving the previous database intact and usable.
- Backup format 4 (schema 3) adds the eligibility-decision audit trail. Formats 2 and 3 are still accepted, but they lack job and attempt timestamps, revisions and audit records: version 2 fields default to the import time and revision 0, so a version 2 restore is semantically complete but not byte-for-byte faithful. A format-4 file cannot be read by a build that only supports format 3, and the audit trail is never silently dropped. Unsupported versions are refused.
- There are no automatic or scheduled backups; creating one is a manual action.
- Scripted Tk tests exercise the restore dialog (declined restore, cancelled file chooser, preparation, resume import, eligibility-decision recording, deletion, and close confirmation) when a display exists; layout, focus order, and visual messaging still depend on the manual checklist.

The GitHub Actions workflow runs this smoke test together with the unit suite, `compileall`, and the CSV audit on Python 3.10–3.12 for pushes to `main`, for all pull requests, and on manual dispatch. A failing scenario fails the job. Branch pushes are not built separately: an open pull request already runs the matrix for each pushed commit, so the same commit is not checked twice.

Changes reach `main` only through a pull request, and merging requires the `unit-tests (3.10)`, `unit-tests (3.11)`, and `unit-tests (3.12)` checks from GitHub Actions. Zero approvals are required, so a pull request is a review gate without a mandatory reviewer. Direct pushes are rejected, administrator enforcement is enabled, no bypass actor is configured, and force pushes and branch deletion are disabled.

## Safety and product principles

- Keep candidate profile and application history local by default. On POSIX systems the SQLite file is restricted to the owning user (mode 0600) when opened, so a shared machine cannot read it with the process umask default.
- The database is **not** encrypted at rest. File permissions and OS volume encryption are the current boundary; backups are plain JSON. The options, threat model, and the deferred key-recovery decision are recorded in [the encryption-at-rest note](research/encryption-at-rest-decision-2026-10-19.md).
- Missing eligibility evidence is not a pass.
- A visible Apply button is not proof that a job is open or that submission succeeded.
- Never infer worldwide eligibility from the word “remote.”
- Do not fabricate candidate facts or screening answers.
- Do not bypass source restrictions or add unapproved connectors.
- A relevance score is not a hiring probability.
- The current alpha does not submit applications. Future automated actions require source/employer permission, reliability evidence, and a scoped, revocable policy; no blanket permission is implied.

## Project status

The local-only desktop alpha is implemented and source research continues in parallel. It is not yet a packaged production release; follow the manual GUI smoke-test checklist before claiming desktop acceptance. Release scope and known limitations are recorded in [CHANGELOG.md](CHANGELOG.md). This does **not** mean the source-quality gate has passed or that live discovery/application workflows are ready. See [the local-alpha smoke-test checklist](research/local-alpha-manual-smoke-test-checklist-2026-10-14.md) and [the current source-quality gate assessment](research/source-quality-gate-assessment-2026-10-14.md).
