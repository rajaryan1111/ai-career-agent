# AI Career Agent

AI Career Agent is a local-first desktop assistant for job discovery, eligibility review, explainable matching, application preparation, and application tracking.

## Current implementation

The project includes a small offline desktop alpha launched with `python -m career_agent`. It uses Python's standard-library Tkinter UI and local SQLite. It is not yet packaged for end users, and GUI smoke testing is still required on supported operating systems.

The dependency-free Python domain core in `career_agent/` provides:

- Three-valued hard eligibility checks: `pass`, `fail`, and `unknown`.
- Separate country eligibility from optional exact-match work-authorization requirements.
- An `open` status without a recorded availability evidence/note remains `unknown` for eligibility.
- Explicit country/work eligibility handling; worldwide eligibility passes only when explicitly recorded.
- Transparent skill overlap and missing-skill explanations, separate from eligibility.
- Conservative URL/requisition deduplication.
- Separate source-listing and employer-application URLs.
- Guarded application status transitions; confirmation requires evidence.
- Local SQLite persistence for candidate profiles, job listings, application attempts, and event history, including explicit per-record delete operations and a confirmed **Delete all local data** action.
- No network access, resume parsing, candidate-data transfer, form filling, or application submission.

The local alpha supports manual candidate-profile entry, manual job entry, eligibility evaluation, shortlisting only on explicit eligibility PASS, application preparation with a readiness checklist and fact-only draft preview, tracker status changes guarded by the domain state machine, per-attempt history with evidence, re-application after withdrawal, local JSON export, explicit delete controls, and a close confirmation when the profile form has unsaved edits. PDF/DOCX import is available for review only — extracted values are marked for review and nothing is written until the user explicitly saves. Resume parsing covers text-based PDF, DOCX, TXT, and MD files only; scanned PDFs need OCR, which is not provided. Job-source adapters remain disabled until their source-specific permissions and quality checks are resolved.

### Profile provenance

Candidate profiles and application history store provenance metadata in the SQLite database:

- **source** (user_entered/imported/inferred/verified): How the candidate fact was provided.
- **verification_state** (unverified): Current verification status of the fact.
- **Timestamps**: When the fact was last updated or corrected.
- **correction_history**: Immutable log of evidence changes preserving the full history behind confirmations.

Provenance survives saving, closing, and reloading a profile. Existing profiles without provenance remain readable. Updates and corrections preserve history correctly. Missing provenance remains unknown rather than being fabricated. Invalid or corrupted stored data is handled safely with user-facing error messages (no tracebacks). Sensitive information is not unnecessarily duplicated into audit history.

Database schema version 2 adds provenance guarantees: every persisted change appends an immutable row to `application_events`, so the evidence behind a confirmation survives later status changes. Profile schema includes `updated_at` tracking. One application attempt is keyed by `(listing_id, attempt_number)`, so re-application after withdrawal creates a new separate record rather than reviving the old one.

### Release boundaries

This is a **local-first desktop alpha**, not a production release. It is source-research-driven and intentionally gated:

- No live job submissions or applications.
- No real email delivery.
- No always-on background worker.
- No verified external source adapters (source-quality gate stays closed until written permission is recorded).
- GUI requires a display server (Tkinter); headless CI runs tests without a display.
- Editable install (`pip install -e .`) is verified; wheel builds succeed but are not published.
- No external service integrations (Gmail, Slack, Linear, PostHog, etc.) are enabled.

### Install

No runtime dependency beyond the Python standard library and Tk is required. An editable install adds the `career-agent` command:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
career-agent --help
```

The package declares Python 3.10–3.12 in `pyproject.toml`. Editable installs are verified locally; no wheel, installer, updater, or code-signing pipeline exists yet.

Tk is not a pip dependency. If `import tkinter` fails, install the matching system package for your interpreter (for example `brew install python-tk@3.12` on Homebrew, `sudo apt install python3-tk` on Debian/Ubuntu, or the official python.org installer on macOS/Windows).

### Run the desktop app

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

### Troubleshooting

- **`ModuleNotFoundError: No module named 'career_agent'`** — run the command from the repository root, or install the package first with `python -m pip install -e .`.
- **`ModuleNotFoundError: No module named '_tkinter'`** — the interpreter lacks Tk. Install it with your platform's package manager or use the python.org build. Unit tests do not need Tk; scripted GUI tests skip when it is unavailable.
- **`TclError: no display name and no $DISPLAY environment variable`** — the session is headless. Run the app on a desktop session; the test suite still runs.
- **Exit status 2 immediately after launch** — the `--database` parent directory does not exist. Create it, or omit `--database` to use the per-user location. The app never creates parent directories for a supplied path.
- **`sqlite3.OperationalError: database is locked`** — another instance (or a backup tool) holds the file. Close the other instance and retry; the app does not delete or reset the database automatically.
- **`Permission denied` writing the database** — check ownership and mode. On POSIX the app restricts the file to mode `0600`; restore write permission for the owning user rather than widening access.
- **A backup is refused** — check the error text: unsupported `format_version`, files above 10 MiB, non-UTF-8 content, and tampered event histories are rejected deliberately. Restore is replace-only and validates everything before writing.
- **A resume imports nothing** — only text-based PDF, DOCX, TXT, and MD are supported, and extraction relies on labelled lines. Scanned PDFs need OCR, which is not included; image-only files are reported as having no extractable text.
- **Discovery is disabled** — this is intentional. The source-quality gate stays closed until a provider's written permission is recorded; see the [job sources and discovery](#job-sources-and-discovery) section.
- **A backup is refused** — check the error text: unsupported `format_version`, files above 10 MiB, non-UTF-8 content, and tampered event histories are rejected deliberately. Restore is replace-only and validates everything before writing. An empty database is a no-op with zero counts.

For a support report, include the `--diagnostics` output and the exact command and error text. Do not attach your database or resume files.

### Audit research data

To regenerate a reproducible CSV integrity summary (including input SHA-256, row/column counts, duplicate IDs, canonical URL groups, status and permission counts):

```bash
python scripts/audit_job_source_csv.py
```

The tool intentionally does not invent a direct-link validity percentage; the existing route observations do not provide a defensible uniform denominator.

### Run tests

Python 3.10+; no third-party packages are required. The single reproducible command runs the unit suite, the tracker smoke test, `compileall`, and the CSV audit, and exits nonzero if any step fails:

```bash
python scripts/smoke_check.py
```

Run one step alone when iterating:

```bash
python -m unittest discover -s tests -v
```

### Tracker integrity smoke test

```bash
python scripts/tracker_smoke_test.py
```

Runs end-to-end scenarios against temporary databases only: schema version 2, attempt creation, persisted transitions, evidence surviving later status changes, fresh re-application, rejected invalid/stale/duplicate writes, withdrawal history, format-v3 backup contents, backup round-trip into a separate database, a tampered backup being rejected without mutation, consistency after failures, and in-place migration of a schema-v1 database. Exit code 0 means every scenario passed; 1 means at least one failed. Add `--keep` to retain the temporary workspace for inspection. The script never opens the application-data database.

The throwaway database, profile, and listings are synthetic. The smoke test includes a negative control: a backup with a tampered event history must be rejected, and the target database must remain unchanged.

### Resume import

**Candidate profile → Import resume (review)…** reads DOCX (text body), text-based PDF, TXT, and MD files with the standard library only — no extra dependency and no upload. Extraction is deliberately conservative:

- Only explicitly labelled lines become proposals (`Skills:`, `Country:`, `Degree:`, `Graduation year:`, `Experience:`, `Work authorization:`, `Preferred …:`). Unlabelled sentences are never turned into facts.
- Each proposal carries the evidence line it came from and is marked for review.
- Proposals fill the profile form; nothing is written until you click **Save profile locally**, and nothing is sent anywhere.
- Encrypted PDFs, malformed DOCX files, non-UTF-8 text, empty files, unsupported extensions, and files over 5 MiB are refused with an actionable message.
- Scanned or image-only PDFs are reported as needing OCR rather than being treated as an empty resume.

This is not a full parser: contact fields, projects, certifications, tables, multi-column layouts, and unusual fonts are out of scope, and every imported value must be reviewed against the original document.

### Job sources and discovery

Discovery is **disabled** in this build. `career_agent/sources.py` defines the adapter contract — source identity, documented access method, permission evidence, review date, capabilities (discovery and submission are separate), local rate limit, timeout, and support status — plus typed outcomes that keep a valid empty result distinct from blocked, rate-limited, timeout, and transient or schema failures. `run_discovery` enforces a bounded retry policy (at most five attempts, capped exponential backoff, injectable sleep for tests), never retries schema errors, rejects records that are not listings, and suppresses duplicate observations before reporting how many it collapsed.

The registry lists manual entry as the only enabled source. Himalayas and SmartRecruiters remain blocked because their terms conflict with automated gathering or autonomous AI workflows and no written authorization is recorded. `SOURCE_QUALITY_GATE_PASSED` stays false, the **Sources & settings** tab states this, and no adapter performs network access. Enabling a provider requires recorded permission evidence and a completed review; scraping public pages, bypassing access controls, or flipping the gate without evidence is out of scope.

### Backup and restore

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
- Scripted Tk tests exercise the restore dialog (declined restore, cancelled file chooser, preparation, resume import, deletion, and close confirmation) when a display exists; layout, focus order, and visual messaging still depend on the manual checklist.

### Quality gates and test skips

12 tests are skipped when the `pypdf` package is not installed. All 600 unit tests pass (0 failures) on Python 3.10–3.12. The test suite also includes the tracker integrity smoke test, `compileall`, and the CSV audit.

### Safety and product principles

- Keep candidate profile and application history local by default. On POSIX systems the SQLite file is restricted to the owning user (mode 0600) when opened, so a shared machine cannot read it with the process umask default.
- The database is **not** encrypted at rest. File permissions and OS volume encryption are the current boundary; backups are plain JSON. The options, threat model, and the deferred key-recovery decision are recorded in the encryption-at-rest note.
- Missing eligibility evidence is not a pass.
- A visible Apply button is not proof that a job is open or that submission succeeded.
- Never infer worldwide eligibility from the word "remote."
- Do not fabricate candidate facts or screening answers.
- Do not bypass source restrictions or add unapproved connectors.
- A relevance score is not a hiring probability.
- The current alpha does not submit applications. Future automated actions require source/employer permission, reliability evidence, and a scoped, revocable policy; no blanket permission is implied.

### Project status

The local-only desktop alpha is implemented and source research continues in parallel. It is not yet a packaged production release; follow the manual GUI smoke-test checklist before claiming desktop acceptance. Release scope and known limitations are recorded in [CHANGELOG.md](CHANGELOG.md). This does **not** mean the source-quality gate has passed or that live discovery/application workflows are ready.

## Supported Python version and operating-system assumptions

- Python 3.10, 3.11, 3.12 (declared in `pyproject.toml`)
- macOS, Linux, Windows (OS classifiers in `pyproject.toml`)
- Tkinter must be available for the GUI; unit tests run without it

## Development setup and test commands

```bash
# Create a virtual environment
python3 -m venv .venv
. .venv/bin/activate

# Install the package in editable mode
python -m pip install -e .

# Run the desktop app
python -m career_agent

# Run unit tests
python -m unittest discover -s tests -v

# Run the tracker integrity smoke test
python scripts/tracker_smoke_test.py

# Run the full smoke check (tests + compileall + CSV audit)
python scripts/smoke_check.py

# Run diagnostics
python -m career_agent --diagnostics

# Build a wheel
python -m build
```

## How to build and verify a distributable package

```bash
python -m build
# Inspect the generated dist/ directory
pip install --no-index --find-links dist ai-career-agent
# Verify imports and entry point
python -m career_agent --version
# Verify clean-environment install by installing into a fresh venv
```

## Candidate profile provenance and correction history

See the [Profile provenance](#profile-provenance) section above for details on how provenance is stored and preserved.

## Eligibility decisions: PASS, FAIL, and UNKNOWN

- **PASS**: All eligibility requirements are explicitly met with verified evidence.
- **FAIL**: At least one requirement explicitly fails (wrong country, missing work authorization, closed listing, insufficient experience, etc.).
- **UNKNOWN**: Insufficient evidence to determine eligibility; the decision stays unknown until missing information is provided.

Three-valued logic is fundamental: missing evidence never defaults to a pass. Eligibility scope (restricted vs. worldwide) and exact-match work-authorization requirements are separately enforced.

## Matching strategy, policy gates, reporting, and local notifications

- **Matching strategy** (`matching.py`): `assess_strategy()` produces a `MatchStrategy` with `Recommendation` enum (6 levels: STRONG_PASS → FAIL), `verification_required`, and `confidence` (high/medium/low). Used in UI to determine shortlist enablement and follow-up reminders.
- **Policy gates** (`policy.py`): `check_policy()` enforces PERMITTED/BLOCKED/UNCERTAIN/CONDITIONAL statuses at action boundaries. FAIL eligibility → BLOCKED. UNKNOWN → UNCERTAIN. PASS → CONDITIONAL (requires explicit user authorization) or PERMITTED (if authorized).
- **Reporting** (`reporting.py`): `build_eligibility_insights()` distinguishes confirmed facts, inferred facts, and missing requirements. Provides actionable explanations for unknown or failed requirements without claiming submission or confirmation without evidence.
- **Local notifications** (`notifications.py`): `NotificationManager` with idempotent 24-hour follow-up reminders. Local-only; does not send external notifications, emails, or push notifications unless explicitly configured and authorized.

## Current limitations

The following capabilities are **not** available in this alpha:

- No live job submissions or applications.
- No real email delivery.
- No always-on background worker.
- No verified external source adapters (source-quality gate stays closed).
- GUI visual verification unavailable in headless environments; requires display server (Tkinter).
- Follow-up reminders are in-memory only (not persisted across restarts).
- No production packaging or release pipeline.
- No external service integrations (Gmail, Slack, Linear, PostHog, etc.).
- Resume extraction is conservative: only explicitly labelled lines become proposals; scanned PDFs need OCR.
- No form filling or automated application submission.

## GUI requirements and how to run GUI checks

The desktop UI requires a display server with Tkinter support. To run GUI checks:

1. Ensure Tkinter is available: `python3 -c "import tkinter"` — no error.
2. Launch the app: `python -m career_agent`.
3. Use the manual GUI smoke-test checklist in `research/local-alpha-manual-smoke-test-checklist-2026-10-14.md` to verify:
   - Window construction and tab rendering.
   - Profile import and save.
   - Job listing and eligibility evaluation.
   - Tracker status transitions.
   - Backup and restore flow.
   - Error handling for corrupt records.
   - Close confirmation on unsaved edits.
4. If no display is available, run headless tests: `python -m unittest discover -s tests -v`.

## Privacy considerations for candidate profiles and local SQLite data

- Candidate profiles and application history are stored locally in SQLite.
- On POSIX systems, the database file is restricted to mode `0600` (owner-only read/write) when opened.
- The database is **not** encrypted at rest. File permissions and OS volume encryption are the current boundary.
- Backups are plain JSON; sensitive data should be handled accordingly.
- No candidate data is transmitted over the network.
- No external service integrations are active by default.
- Users can delete all local data via the **Delete all local data** action, which removes profile, listings, attempts, and event history in one transaction.
- Privacy notice: the project does not collect, store, or transmit any candidate or application data.

## Optional dependencies and skipped tests

- `pypdf`: 12 tests are skipped when this package is not installed. It is optional and used for PDF-based resume import features.
- No other third-party dependencies are required. The entire domain core runs on Python standard library only.

---

For support requests and release checks, `--diagnostics` prints environment facts without starting the app, opening a record, or creating anything. See the [troubleshooting](#troubleshooting) section for common issues.

---

**Project status**: The local-only desktop alpha is implemented and source research continues in parallel. It is not yet a packaged production release.