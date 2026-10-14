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
- Guarded application status transitions; confirmation requires a deliberate user assertion plus
  substantive evidence (the app's own instruction text and bare placeholders are refused). The status
  chooser offers only the moves the record may actually take, and a stored status this version does not
  recognise is shown as it is and left untouched rather than repaired, hidden, or carried forward.
- Local record times shown as such — when this device first wrote a listing and when it last saved it —
  with a clear statement that the source's publication or update date is not available, because none is
  stored.
- A version string that works from a source checkout (`python -m career_agent --version`) and a
  non-sensitive start-up failure report that names a next step without exposing paths, credentials or
  candidate data.
- Local SQLite persistence for profile, job, and tracker records, including explicit delete operations.
- Validation of manually entered links as public http(s) addresses only (no credentials, no
  localhost/private/internal targets) and display-time redaction of credentials in older rows.
- A fail-closed source permission gate: no source runs without recorded permission evidence and a
  passed source-quality gate, and a legitimate empty result is never confused with a blocked,
  partial, challenged, or failed run.
- No network access, resume parsing, candidate-data transfer, form filling, or application submission.

The local alpha supports manual candidate-profile entry, manual job entry, eligibility evaluation, shortlisting only on explicit eligibility PASS, tracker status changes guarded by the domain state machine (the dialog offers only the statuses the selected record may actually move to, and a record in a final state such as `withdrawn` is told so instead of being offered a change it cannot take), local JSON export, and explicit delete controls. Lists show the app's own record times (labelled "this app, UTC"); the detail pane states that the source's publication or update date is not provided, because the database stores none and import time is never presented as a source date. Job entry has an explicit mode: **New job** always creates a separate record, while selecting a saved listing switches to **Edit**, keeps that listing's identity, and asks for confirmation when an eligibility-relevant field changes. Local database write failures are reported with an actionable message and never reported as success; a status change that does not actually change the status is not reported as an update. PDF/DOCX parsing is deferred to a follow-on local-only increment. Job-source adapters remain disabled until their source-specific permissions and quality checks are resolved.

## Run the desktop app

Python 3.10+ with Tkinter available:

```bash
python -m career_agent            # open the desktop window
python -m career_agent --version  # print the version and schema version of this checkout
```

`--version` needs no display and no packaging metadata: it reports the version recorded in the source.
The app has no installer yet — see [Packaging status](#packaging-status) for the exact missing pieces.

If the window cannot open, the message says what happened and what to do next instead of showing a raw
traceback. A short, sanitised note is kept as `logs/startup-diagnostics.log` in the application-data
folder; it holds no candidate data, credentials, or filesystem locations, and a copy can be sent to
whoever is helping you without revealing personal information. The database commands above work without
the window, which is what you need when the database itself is the problem.

Candidate data is stored in the operating system's per-user application-data directory, not inside the repository.
If a tracker record is wrong — for example a smoke-test record left `confirmed` when nothing was ever
submitted — correct it with the backed-up, dry-run-by-default tool rather than editing SQL by hand:

```bash
python scripts/correct_tracker_record.py --database "<your database path>" --listing-id <id> \
    --to withdrawn --reason "<what actually happened>" --clear-confirmation          # dry run
```

See [the smoke-test diagnosis](research/tracker-confirmation-smoke-test-diagnosis-2026-10-14.md) for
the full explanation and the exact recovery steps. Its `--apply` snapshot goes through the same
verified, owner-only backup path described below. To use the core tests in a headless environment, no display is required.

The JSON export is written owner-only (`0600`) on systems that support POSIX permissions, tightened
even when the chosen file already existed, and it refuses to write through a symbolic link so a link
cannot redirect candidate data into another file. If the permissions cannot be applied, the export is
not kept and the app says so instead of writing readable data. A synced or shared destination folder
can still expose the file, so export to a folder only you can access.

## Back up and restore your data

The database holds the candidate profile, every saved listing and the whole application history. The app
can write a verified backup of it and restore from one, entirely on the local machine.

In the app, open the **Data safety** tab: *Back up database* writes a timestamped file to a location you
choose, and *Restore from backup* validates the file you pick, copies the current database aside,
replaces the database, then reopens and verifies it.

The same two operations work without opening the window, which is what you need when the database is
damaged enough that the app cannot start:

```bash
python -m career_agent --backup-to "$HOME/Documents/career-agent-backup.sqlite3"
python -m career_agent --restore-from "$HOME/Documents/career-agent-backup.sqlite3" --yes
```

Add `--database PATH` to either command to work on a database outside the per-user application-data
folder. Restoring replaces candidate data, so it asks you to confirm: interactively it requires typing
`restore`, and in a script it requires `--yes`. Refusals exit with status `2` and say what to do next.

**What a backup guarantees**

- It is taken through SQLite's own backup API, so it is a consistent snapshot even while the app is
  running, and rows committed into a `-wal` file are included rather than skipped (a plain file copy
  loses them — measured, not assumed).
- It is created owner-only (`0600`) on POSIX filesystems, before any data is written, and a symbolic
  link is never followed, so a link cannot redirect a backup into another file.
- An existing file is never overwritten: choose another name, or move the old file first.
- Success is reported only after the new file has been read back and verified (SQLite integrity check,
  schema version, required tables). A failed backup removes its own partial file and reports the
  failure; it never reports success for something unverified.
- Every backup is one self-contained file in the classic rollback-journal format, with no `-wal`/`-shm`
  side files, so it stays usable wherever it is copied or archived.

**What a restore guarantees**

- The chosen file is validated *before* anything local is touched. A file that is unreadable, damaged,
  written for a different schema version, or missing an expected table is refused with a message, and
  the current database is left exactly as it was.
- It is copied into a staging file beside the database and validated again, so the file that is
  installed is the file that was checked. The backup you chose is never modified or consumed.
- The current database is preserved first: a verified snapshot when it is readable, and a raw
  owner-only copy (reported honestly as unverified) when it is not — that unreadable case is often why
  a restore is needed at all. If it cannot be preserved at all, the restore is refused.
- The restore refuses while another connection holds the database open, replaces the file in one atomic
  step, removes stale SQLite side files (a stale `-wal` left beside a replaced database silently
  discards the restored data), and reopens and verifies the result. If that final check fails, the
  previous database is put back.
- A newer or older schema version is refused rather than migrated or downgraded.

**Limitations**

- Backups are **not encrypted**. Owner-only permissions keep other local accounts out, not someone using
  your unlocked account or a copy of the file; a synced or shared folder can still expose it. Store
  backups somewhere only you can reach.
- Owner-only permissions are a POSIX capability. On Windows the file is written without that protection
  and the app does not claim otherwise; Windows also refuses to replace a database another program has
  open, in which case the restore fails with a message and the original is untouched.
- `PRAGMA integrity_check` detects the damage SQLite can detect. It cannot prove a backup is complete or
  untouched by every byte-level change, so keep more than one backup if the data matters.
- An exclusive-access check turns "another copy of the app has the database open" into a refusal with a
  message instead of an apparently frozen window. A writer that takes the database between that check
  and the copy itself can still make a backup wait, because the standard library retries while SQLite
  reports the source busy; nothing is written until the copy succeeds.
- Old backups are never pruned automatically, and nothing is uploaded anywhere: backups are files you
  place yourself.


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

The suite covers the domain rules, SQLite persistence, the CSV audit tool, untrusted-URL validation,
the source permission gates and run-outcome rules, the Tk-free desktop logic (form mapping, save
planning, database-path resolution, stored-timestamp rendering), the status chooser's option set against
the state machine, unrecognised stored statuses and the refusal paths they trigger, version reporting and
start-up diagnostics (including path redaction), verified backup and restore (including corruption,
schema-version and permission failures, WAL and side-file handling, and the command-line front end), and
the desktop handlers exercised through widget stubs. It
requires no display and no GUI packages. Automated tests do **not** cover widget rendering, window
behavior, or operating-system integration: GUI smoke testing on a real desktop, including macOS,
remains outstanding and is tracked in
[the local-alpha smoke-test checklist](research/local-alpha-manual-smoke-test-checklist-2026-10-14.md).

## Packaging status

There is no installer and no packaged build, and nothing in this repository claims one. What exists today:

- The app runs from a source checkout with `python -m career_agent` and needs the standard library plus
  Tkinter, nothing else.
- `career_agent.__version__` is the single source of truth the checkout reports.
  `python -m career_agent --version` prints it with the database schema version and works with no
  packaging metadata, no display, and no third-party tools.
- `career_agent.diagnostics` explains a start-up failure in plain language, redacts local paths, and keeps
  one bounded owner-only note. The failure classes it distinguishes are covered by tests.

Missing pieces, in the order they are needed, for a packaged desktop alpha:

1. Distribution metadata (`pyproject.toml` with PEP 621 project metadata, `requires-python`, and a
   `console_scripts` entry point) plus a build verified in CI, so the version comes from one source
   instead of a literal that could drift from a packaged build.
2. Per-platform launch artefacts, code signing and notarisation (macOS `.app`, Windows installer), with
   the icon, identity, and update story that implies.
3. A decision on bundling the interpreter (PyInstaller/Briefcase-style) versus requiring a system Python
   with Tkinter — including the size, update, and Tk-availability consequences of each choice.
4. A release checklist that runs this repository's suite, the manual desktop checklist, and a
   backup/restore rehearsal on each supported operating system from the packaged build.

Until those exist, "local alpha from a source checkout" is the accurate description.

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
