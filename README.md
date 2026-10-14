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
- Local résumé import: a PDF or DOCX you pick is read on this device and offered as proposals for you
  to review; nothing reaches the profile until you select values and confirm. The extracted text is
  discarded, never stored and never sent anywhere. See
  [Import a résumé](#import-a-résumé-pdf-or-docx) for the limits and the optional PDF library.
- No network access, candidate-data transfer, form filling, or application submission.

The local alpha supports manual candidate-profile entry, manual job entry, eligibility evaluation, shortlisting only on explicit eligibility PASS, tracker status changes guarded by the domain state machine (the dialog offers only the statuses the selected record may actually move to, and a record in a final state such as `withdrawn` is told so instead of being offered a change it cannot take), local JSON export, and explicit delete controls. Lists show the app's own record times (labelled "this app, UTC"); the detail pane states that the source's publication or update date is not provided, because the database stores none and import time is never presented as a source date. Job entry has an explicit mode: **New job** always creates a separate record, while selecting a saved listing switches to **Edit**, keeps that listing's identity, and asks for confirmation when an eligibility-relevant field changes. Local database write failures are reported with an actionable message and never reported as success; a status change that does not actually change the status is not reported as an update. The candidate profile can be filled in by hand or proposed from a résumé you import locally (see [Import a résumé](#import-a-résumé-pdf-or-docx)): the document is read on this device, every proposed value is shown with the text it came from before anything is written, you accept or reject each value, and the unselected and missing values keep what your profile already had. Job-source adapters remain disabled until their source-specific permissions and quality checks are resolved.

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

## Import a résumé (PDF or DOCX)

Open the **Candidate Profile** tab and press **Import resume (PDF/DOCX)**. The file is read on this
device — no upload, no cloud OCR, no external parser, no network request — and the import itself writes
nothing to your profile. A review window then shows, for every proposed value:

- the profile field and the value that was found;
- a short quotation of the document text it came from, so you can judge it yourself;
- a confidence label (`confident` or `needs review`), where only `confident` values start ticked;
- what the document did **not** mention, and what it contained that the profile has no field for (a name,
  an email address or a phone number, for example — shown as information, never stored).

Tick or untick each value, then press **Save selected values** and confirm. A value you did not tick
keeps the value already in the form (and in your saved profile), so an import cannot silently overwrite
what you entered. Saving goes through exactly the same validation as the Save button, and the app
re-reads the stored profile and compares it field by field before it reports that the save succeeded.

What is parsed, and what is deliberately not:

- **Supported today:** skills, degree/discipline, graduation year, study status, country, work
  authorization, and years of experience when the document states a figure.
- **Never guessed:** a keyword is not a qualification, a bare year is not treated as a graduation year,
  and nothing is inferred about eligibility, work authorization, location or study status. Study status
  and work authorization are always `needs review`; a field the document is silent about is reported as
  missing, never as a confirmed "no".
- Values with no matching profile field (name, contact details, institutions, employers, employment
  dates) are listed as "present in the document but not stored" — the database schema is not extended to
  hold them.

Limits and failure handling — oversized or unreadable files are refused with an explanation, never
silently truncated:

- At most 10 MB per file, at most 40 PDF pages, and a cap on how much text is accepted; a DOCX's
  declared uncompressed size is checked before it is read.
- Encrypted, damaged, empty and textless/scanned PDFs each get their own message. **A scanned PDF with no
  text layer cannot be read by this feature and is not pretended to be readable:** the app says so and
  asks you to type the values in. OCR is **not** implemented.
- A legacy `.doc`, an unsupported format, or a DOCX carrying macros is refused, or has the macro part
  reported and ignored — embedded content is never executed. The document is treated as untrusted input:
  this is text extraction, **not** a malware scanner, and no parsing is risk-free.
- The file you selected is read in place; no copy of it is kept anywhere.

**PDF support is an optional third-party library.** DOCX import uses the standard library alone. For PDF
text extraction, install [pypdf](https://pypi.org/project/pypdf/) (BSD-3-Clause, no mandatory
dependencies, Python 3.9+):

```bash
python -m pip install pypdf
```

Without it, everything else in the app — including DOCX import — works unchanged, and choosing a PDF
produces a clear "PDF support is not installed" message instead of a crash. The library is imported only
when a PDF is actually read.

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

Python 3.10+; no third-party packages are required to run the suite. (The PDF import path uses the
optional `pypdf` library when it is installed; the tests that need it skip themselves with a reason when
it is absent, and everything else — including DOCX import — still runs.)

```bash
python -m unittest discover -s tests -v
```

The suite covers the domain rules, SQLite persistence, the CSV audit tool, untrusted-URL validation,
the source permission gates and run-outcome rules, the Tk-free desktop logic (form mapping, save
planning, database-path resolution, stored-timestamp rendering, profile read-back comparison), local
résumé import (PDF and DOCX text extraction including DOCX tables, encrypted, damaged, empty, oversized
and textless files, the refusal to invent values, and the socket-blocked local-only guarantee), the status
chooser's option set against
the state machine, unrecognised stored statuses and the refusal paths they trigger, version reporting and
start-up diagnostics (including path redaction), verified backup and restore (including corruption,
schema-version and permission failures, WAL and side-file handling, and the command-line front end), and
the desktop handlers exercised through widget stubs — including the résumé review screen: proposals shown
with evidence before anything is saved, per-value accept and reject, cancellation and declined
confirmation writing nothing, validation and database failures never reported as success, and no document
text reaching a message, the status line or the database. The résumé fixtures are synthetic documents
built in the test process; no real candidate data and no network access are involved. It also checks the
SQLite resource
lifecycle: no test may leave a connection open (the whole suite is re-run in a child process that
counts them, because Python 3.10/3.11 never emit the `ResourceWarning: unclosed database` that
macOS reported), and `with sqlite3.connect(...)` — which manages the transaction, not the
connection — is refused by a source scan. It
requires no display and no GUI packages. Automated tests do **not** cover widget rendering, window
behavior, or operating-system integration: GUI smoke testing on a real desktop, including macOS,
remains outstanding and is tracked in
[the local-alpha smoke-test checklist](research/local-alpha-manual-smoke-test-checklist-2026-10-14.md).

## Packaging status

There is no installer and no packaged build, and nothing in this repository claims one. What exists today:

- The app runs from a source checkout with `python -m career_agent` and needs the standard library plus
  Tkinter. Reading PDF résumés additionally needs the optional `pypdf` library; every other feature,
  including DOCX résumé import, works without it. A packaged build would need a decision on whether to
  bundle that library (see below).
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
