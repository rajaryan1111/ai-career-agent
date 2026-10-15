# AI Career Agent

AI Career Agent is being built as a local-first desktop assistant for job discovery, eligibility review, explainable matching, application preparation, and application tracking.

## Current implementation

The project now includes a small offline desktop alpha, launched with `python -m career_agent` or the installed `career-agent` command. It uses Python's standard-library Tkinter UI and local SQLite, and it installs with no required third-party dependency. It is not yet a signed packaged desktop release, and GUI smoke testing is still required on supported operating systems.

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
- A dated **activity history** per application, kept beside the tracker status rather than inside it:
  each entry records what the person says happened (applied, employer replied, interview, assessment,
  followed up, note) on the day it happened, plus when this app wrote the row. An entry never changes a
  status, never creates a tracker record, and is never accepted as confirmation evidence, so a note
  cannot become proof. Entries are shown oldest first, are deleted with their listing, and one entry can
  be deleted explicitly.
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

The local alpha supports manual candidate-profile entry, your own employment and education records (the **Work history & study** tab: employer, job title, employment type, start and end dates, an explicit current-role flag, optional notes, and institution, qualification, discipline, start and completion dates with an ongoing-study flag, validated so an impossible period or a current role with an end date is refused rather than stored), manual job entry, eligibility evaluation, shortlisting only on explicit eligibility PASS, tracker status changes guarded by the domain state machine (the dialog offers only the statuses the selected record may actually move to, and a record in a final state such as `withdrawn` is told so instead of being offered a change it cannot take), a dated activity history for each application (written by you, never by the app, and never treated as evidence), local JSON export and import (a file is read, planned and confirmed before anything is written; an existing listing is linked rather than replaced and a stored profile is kept), and explicit delete controls. Lists show the app's own record times (labelled "this app, UTC"); the detail pane states that the source's publication or update date is not provided, because the database stores none and import time is never presented as a source date. Job entry has an explicit mode: **New job** always creates a separate record, while selecting a saved listing switches to **Edit**, keeps that listing's identity, and asks for confirmation when an eligibility-relevant field changes. Local database write failures are reported with an actionable message and never reported as success; a status change that does not actually change the status is not reported as an update. The candidate profile can be filled in by hand or proposed from a résumé you import locally (see [Import a résumé](#import-a-résumé-pdf-or-docx)): the document is read on this device, every proposed value is shown with the text it came from before anything is written, you accept or reject each value, and the unselected and missing values keep what your profile already had. One rule decides the database file for the window, the backup/restore commands and the `--doctor` report, so all three always name the same file (see [Where the app keeps its data](#where-the-app-keeps-its-data)); `--doctor` reports the version, the paths, and whether the database is readable, without a display and without changing anything. Progress reporting adds up the records that already exist (`--analytics`, and the **Progress report** on the Application tracker tab): counts, rates that name their denominator and are withheld below five applications, and an explicit list of what this application cannot measure — an offer, or anything an employer did without telling you — so an unavailable metric is never printed as a zero. Job-source adapters remain disabled until their source-specific permissions and quality checks are resolved. Email and calendar integrations have the same shape: a typed draft and event contract with a preview of exactly what would happen, an operation id that makes a repeat recognisable, and execution that is disabled by default and refuses with a reason — the only thing that can perform anything is an explicitly named local mock that contacts nothing (see [Can it send email or add things to my calendar?](#can-it-send-email-or-add-things-to-my-calendar)).

## Run the desktop app

Python 3.10+ with Tkinter available. The project is not published to any package index, so install it
from the checkout itself if you want a `career-agent` command; the source checkout runs the identical
program with no installation at all.

```bash
python -m pip install .          # from the repository root; adds the `career-agent` command
python -m pip install ".[pdf]"   # the same, plus optional PDF résumé reading
career-agent                     # open the desktop window
career-agent --version           # print the version and database schema version
career-agent --database "/path/to/career-agent.sqlite3"
career-agent --doctor            # where is my data, and can this app read it?
career-agent --analytics         # what the records add up to, with every denominator named
career-agent --integration-status        # whether this app can email or add events, and why not
career-agent --preview-calendar-export   # what the .ics export would contain, without writing it
career-agent --draft-follow-up j1        # a follow-up email draft you can read and copy out; nothing is sent
```

```bash
python -m career_agent --version # the source-checkout form; no metadata needed
```

Both spellings run the same `main()`. `--version` needs no display and no packaging metadata: it reports
`career_agent.__version__`, which is also where the packaged build takes its version from, so the
installed metadata and the app cannot disagree. Installing adds the `career_agent` package only — the
maintenance tools in `scripts/` (the CSV audit and the tracker-record correction tool) stay in the
checkout and are run from there. There is still no installer, no signed desktop bundle, and no bundled
interpreter: see [Packaging status](#packaging-status) for what that means and what is missing.

### Where the app keeps its data

One rule decides the database file, and the window, the database commands and the doctor all follow it,
so they can never disagree about which file is in use:

1. `--database PATH` for one run;
2. otherwise the `CAREER_AGENT_DATABASE` setting, which must be an absolute path;
3. otherwise `<data folder>/career_agent.sqlite3`.

The data folder is `CAREER_AGENT_HOME` followed by the app's folder name (`ai-career-agent` on Linux,
`AI Career Agent` on macOS and Windows) when that setting holds an absolute path, and the platform's
per-user application-data folder otherwise. A *relative* value in either setting is ignored rather than
resolved against the working directory, because the profile and the history would otherwise appear to
move between launches depending on where the app was started from; the doctor prints which setting was
ignored and why. Only the default location is created automatically — a path you name is used exactly
as given, so a mistyped path reports a missing folder instead of quietly becoming a real one.

```bash
career-agent --doctor                 # version, Python, data paths, and whether the database is readable
python -m career_agent --doctor       # the same, from a checkout
```

`--doctor` is read-only: it creates nothing, changes nothing, repairs nothing, and needs no display, so
it is safe to run when the app will not start. It reports the version and the Python it is running on,
the resolved database path *and which rule chose it*, whether the data folder exists and is writable,
and what the database contains (or the exact refusal the app itself would show if the file is damaged,
empty, or written for a newer schema). It does not stop at structure: on a file whose schema is the one
this build writes, it also decodes every stored record — profile, listings, application records, activity,
preparation, interview rounds, employment and education, and the scheduled work — with the same functions
the read paths use, and reports the table and the record it cannot read instead of clearing the file. A
file written by an *older* schema is reported by version and not decoded, because this check never changes
a file and therefore never migrates one. It exits `1` when it finds a problem and `0` when it does not,
which makes it usable from a launcher or a script. Its report lists file locations, so remove them
before sharing it; the start-up note described below is the redacted one.

### Logs and diagnostics

The application writes one line per event to `logs/application.log`, beside the database it describes
(so `--database /somewhere/else.sqlite3` keeps its log in `/somewhere/else/logs/`). The file answers
"what has this app been doing?" without anyone having to remember: the version starting up, a database
being opened and migrated (and which step from which version), the safety copy taken before an existing
database is updated, a migration that failed, profile, job, tracker and activity writes, résumé imports, exports, backups and restores — including each refusal, so a
backup that never happened cannot look like one that did.

```bash
career-agent --doctor             # prints the log's path and the most recent event
```

A line holds an event name plus an identifier, a count or a category. It never holds profile values,
résumé text, evidence text or a URL, so the file can be shared with whoever is helping you; any local
location inside a detail is replaced with a placeholder by the same function that sanitises the start-up
note. The file is owner-only on systems that support POSIX permissions, capped at 256 KiB with one
previous file kept (`application.log.1`), and a line that cannot be written is dropped rather than
failing the action it was describing — a full disk never costs you a saved job. There is no viewer inside
the window yet; read the file with any text editor, or ask `--doctor` for the last line.

If the window cannot open, the message says what happened and what to do next instead of showing a raw
traceback. A short, sanitised note is kept as `logs/startup-diagnostics.log` in the application-data
folder; it holds no candidate data, credentials, or filesystem locations (the database path, its folder,
your home folder, and any file named on the command line are replaced with placeholders), and a copy can
be sent to whoever is helping you without revealing personal information. The database commands above work without
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
cannot redirect candidate data into another file. Reading one back is documented in
[Move your data to another computer](#move-your-data-to-another-computer-json-export-and-import). If the permissions cannot be applied, the export is
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

The review window is resizable and its proposal list scrolls, while the header and the **Save selected
values** / **Cancel** buttons stay where they are, so a long résumé cannot push the actions out of reach.
Closing the window, pressing Escape and pressing **Cancel** all do the same thing: nothing is written and
the status line says the profile was not changed.

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
- **Categories and merged columns:** a category name before a skills list is a label, not a skill, whether
  it is written `Languages: Python, SQL` or `Languages | Python, SQL`, and its values are read without it.
  When an extractor reports two columns (or two table cells) on one line and no such label explains them,
  the text on that line is still offered exactly as read but marked `needs review` instead of ticked,
  because which column holds the skills cannot be known from the text alone.
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
  reported and ignored — embedded content is never executed. A DOCX whose document part is stored
  encrypted (a password-protected re-save) is refused with the same plain message as an encrypted Word
  file, and one written with a compression method this build cannot read is refused naming that method;
  neither can reach the window as a raw error. The document is treated as untrusted input: this is text
  extraction, **not** a malware scanner, and no parsing is risk-free.
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
replaces the database, then reopens and verifies it. If the replaced file cannot be reopened, the window
says exactly that and stops reading and writing candidate data instead of reporting a completed restore.

The same two operations work without opening the window, which is what you need when the database is
damaged enough that the app cannot start:

```bash
python -m career_agent --backup-to "$HOME/Documents/career-agent-backup.sqlite3"
python -m career_agent --restore-from "$HOME/Documents/career-agent-backup.sqlite3" --yes
```

If you installed the package, drop the `python -m career_agent` prefix and use `career-agent` with the
same options.

Add `--database PATH` to either command to work on a database outside the per-user application-data
folder, or point `CAREER_AGENT_DATABASE` at an absolute path to make that choice once; both commands
resolve the path by the same rule as the window (see [Where the app keeps its data](#where-the-app-keeps-its-data)),
so a backup always names the file the app itself would open. Restoring replaces candidate data, so it asks you to confirm: interactively it requires typing
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
  written by a newer schema version than this build understands, or missing the tables its own recorded
  version should hold, is refused with a message; the current database is left exactly as it was.
- It is copied into a staging file beside the database and validated again, so the file that is
  installed is the file that was checked. The backup you chose is never modified or consumed.
- The current database is preserved first: a verified snapshot when it is readable, and a raw
  owner-only copy (reported honestly as unverified) when it is not — that unreadable case is often why
  a restore is needed at all. If it cannot be preserved at all, the restore is refused.
- The restore refuses while another connection is active in a transaction, replaces the file in one
  atomic step, removes stale SQLite side files (side files left beside the replaced database belong to the
  previous one, and whether SQLite applies them is SQLite's decision rather than the app's), and reopens
  and verifies the result. If that final check fails, the previous database is put back.
- While the file is being replaced the app holds the database's exclusive lock, so a competing write is
  refused ("database is busy") instead of being accepted and then thrown away by the replacement. This
  applies on macOS and Linux. On Windows the lock cannot be held across the replacement, because SQLite
  opens its database files in a way that makes the operating system refuse to replace them while the app's
  own handle is open: the lock is released immediately before the swap there, and the operating system's
  refusal to replace a file another program is holding open is what protects it. On Windows a restore
  therefore refuses with a message, and leaves the current database untouched, while another program holds
  the file open. (This platform's behaviour is reasoned from the operating system's documented file-sharing
  rules and SQLite's open flags; it is not covered by the tests here, which run on Linux.)
- A backup written by an **older** schema version is accepted: it is validated against the tables its
  own version holds and installed as it is, never rewritten by the restore. Opening the app then updates
  it with the same recorded schema step used for the live database, and both the window and the command
  line say so. A file written by a **newer** version is refused rather than downgraded.

**What an update to the database schema guarantees**

- An existing database at an older version is copied first: a verified, owner-only snapshot is written
  beside it *before* the first step runs, and the log records the copy immediately before the migration
  it precedes. A new database and one already at the current version are not copied. If that copy cannot
  be written, the update does not start at all, and the message names the version on disk and the version
  it was going to become.
- Each copy describes the state the attempt started from, so an existing file is never reused for a later
  attempt, and snapshots are never overwritten. This is the recovery path for the case a rollback cannot
  reach: a step that succeeded, was committed, and only afterwards turned out to be wrong.
- A scheduled task's own history is kept: every attempt, with its outcome (succeeded, refused, failed,
  timed out, or interrupted), how long it took, and the one-line reason - and a refused run is recorded
  as a refusal rather than as a failure, because a rule that says no is not a malfunction.
- The schema is updated one recorded step at a time, each in a single transaction that ends by writing
  the version it reached, so a database can never claim a version whose tables are missing or hold
  tables at a version it does not claim.
- A step that fails is rolled back and reported with the version the database is actually at, re-read
  from the file rather than assumed: "nothing changed" is only said when the file says so. The message
  names the recovery path (a verified backup), and nothing in the database is deleted or rewritten to
  work around a failure.
- A database that records a *newer* schema version is refused, and so is a file that holds tables but
  records no schema version at all — that file was not written by this application, and nothing is
  added to it. Neither refusal modifies the file.

**Limitations**

- Backups are **not encrypted**. Owner-only permissions keep other local accounts out, not someone using
  your unlocked account or a copy of the file; a synced or shared folder can still expose it. Store
  backups somewhere only you can reach.
- Owner-only permissions are a POSIX capability. On Windows the file is written without that protection
  and the app does not claim otherwise (the restore and the lock it can hold there are described above).
  Where the platform has no mode bits to apply, the writer reports success without applying anything rather
  than refusing: refusing there is what stopped the application creating its own database on Windows, since
  every store records its start in the event log and the event log is written through the same helper.
- **Scheduling on Windows needs a timezone database.** A Windows installation has no system copy of the
  IANA zones, so a task cannot be scheduled until `pip install tzdata` is run - the app says exactly that and
  refuses rather than falling back to UTC, because a reminder at the wrong hour is worse than a clear refusal.
  The Windows CI legs install that package, so the scheduling paths run there instead of the refusal.
- `PRAGMA integrity_check` detects the damage SQLite can detect. It cannot prove a backup is complete or
  untouched by every byte-level change, so keep more than one backup if the data matters.
- An exclusive-access check turns "another copy of the app is writing the database" into a refusal with a
  message instead of an apparently frozen window. A writer that takes the database between that check
  and the copy itself can still make a backup wait, because the standard library retries while SQLite
  reports the source busy; nothing is written until the copy succeeds.
- An **idle** connection cannot be detected: a program that has the database open without being in a
  transaction holds no SQLite lock at all, so the restore neither refuses nor waits for it. That
  connection may keep reading the rows it had before the replacement, and its next write fails with
  SQLite's own "attempt to write a readonly database" once SQLite notices the file has moved. The
  replacement itself cannot be coordinated with it on any platform, which is why the app closes its
  connection for the swap and why restoring is safest with other copies of the app closed.
- Old backups are never pruned automatically, and nothing is uploaded anywhere: backups are files you
  place yourself.


## Remove the data this app wrote

Everything the app stores is local, and it can all be removed from the command line:

```bash
python -m career_agent --forget-local-data          # shows what would be removed; removes nothing
python -m career_agent --forget-local-data --yes    # removes those files
```

The first form is the default on purpose: deleting is irreversible, so the command lists every file with
its size and its reason, and reports what it is deliberately **not** touching. The second form removes
them and says so file by file.

**What it removes** — only files this app wrote, and only where their names are derived from the database
it was pointed at: the database itself, SQLite's `-journal`/`-wal`/`-shm` sidecars, the snapshots and
staged restores written beside it (`<database>.backup-*`, `.<database>.restore-….partial`,
`.<database>.rollback.partial`), and the two logs it writes in the `logs` folder beside the database.

**What it never removes** — anything it cannot derive: a backup, JSON export, `.ics` file, saved draft or
mock ledger you wrote to a path of your choosing. It names that limit instead of implying the machine is
clean, so delete those yourself if you want them gone. It also never walks a folder: a file beside the
database that this app did not write is reported and left alone, and a path that is a folder or a symbolic
link is refused rather than followed. Nothing is created — no database, no folder, no log — and running it
again after a successful removal reports that there is nothing left to remove.

## Move your data to another computer (JSON export and import)

A backup is a copy of the whole database in SQLite's own format, so it is the right thing for keeping
your own data — and the wrong thing for handing someone a file to read. The **JSON export** is the
portable, readable format: the candidate profile, your employment and education records, every saved
listing, the application records, the follow-up days and the activity history in an ordinary text file,
with no code and no credentials in it.
Reading one back is the import, which is also how you move your data to a second computer.

In the window, the **Data safety** tab has **Export data to a JSON file** and, beside it,
**Import an exported file (JSON)**. The import always shows you what it would do and asks before it
writes anything. The import of a file this app did not write is refused: the format carries a version,
and a missing or different version is an error, not a guess. A file larger than 64 MB is refused before
it is read at all — this app's exports are kilobytes, so a file that big is not one of them, and reading
a mistyped path whole is how a command runs out of memory instead of saying no.

Without the window:

```bash
python -m career_agent --export-to "$HOME/Documents/career-agent-export.json"
python -m career_agent --import-from "$HOME/Documents/career-agent-export.json"        # shows the plan
python -m career_agent --import-from "$HOME/Documents/career-agent-export.json" --yes  # applies it
```

`--export-to` refuses to replace a file that already exists, so a second export cannot destroy the first
by accident: choose another name. `--import-from` is a **dry run** until you add `--yes`, and it prints
the same plan the window shows. Refusals exit with status `2`.

**What the import does with your existing data**

- The profile is imported only when you have none stored. If your database already has a profile, it is
  kept and the plan says so — an import never silently replaces the profile you filled in.
- A listing that is already stored is **linked, never replaced**: identity is the same duplicate key the
  rest of the app uses (source and listing id), the stored copy stays as it is, and the time it was first
  seen here is not touched. An export therefore cannot overwrite a listing you edited or hide work you
  did after it was written.
- Every application record in the file becomes a record here at `discovered`, the status a new record
  must start at. A later status in the file (say `shortlisted`) is **reported as not imported** rather
  than used: a confirmation you did not make in this app is exactly the evidence the tracker refuses to
  invent. The listing, its facts, the follow-up day and the history still come across.
- Follow-up days travel as data. A day that cannot be read as a date is reported as a refusal — the
  listing itself still imports — rather than being dropped or guessed, and the same is true of a history
  entry that cannot be read.
- Activity history is appended, and an entry already present (same day, same kind, same text) is not
  duplicated, so importing the same file twice does not double your timeline.
- Employment and education records **either all come across or none do**: if you already have any record
  of your own stored here, the plan says how many it is keeping and imports none of the file's, because
  two half-CVs mixed into one list is a record of nobody. Delete the stored records first if you want the
  file's copies. A file written before this feature existed (format version 1) still imports its profile,
  listings and history — it simply carries no records, and none are invented for it.
- What was refused is listed in full when there are few of them, and with a count when there are many.
  Importing the same file a second time is safe and says so: `left N already-stored listing(s) as they
  were`.

The window writes `import.written`, `import.refused` or `import.failed` to the activity log, so an import
that changed your data is visible in the same place as every other write. Nothing about an import leaves
the machine, and the file you read is the file you chose.


## Where listings would come from (and why nothing is fetched yet)

`python -m career_agent --sources` prints what this version could fetch, from where, and under what
permission — and it is the honest answer to "why are there no jobs in here?":

- the **source-quality gate**, which has not passed: while it is closed, no source may run whatever its
  own permission says;
- every **reviewed source** with its state (`approved`, `conditional`, `blocked`, `rejected`), its
  evidence, the conditions attached to it, and whether it is selected for use;
- whether **applying for jobs** at that source would be permitted (today: not at any of them);
- how many **adapters** are built in (**zero**, deliberately — an adapter is only written for a source
  whose permission review *and* the quality gate have both passed).

The report is read-only: it contacts nothing, changes nothing and does not even create a database. To see
the adapter layer's own state, the same command prints one health line per registered adapter, keeping
*success*, *empty*, *partial*, *failed* and *disabled* apart — because "the source is down" and "the
source has nothing today" lead to opposite decisions.

**The framework an adapter will run under** is written and tested (`career_agent/adapters.py`), and it is
where the rules live rather than in a wiki: a declared capability model (submission is `False` for every
adapter, by construction), a hard request cap and a minimum interval between requests, retries bounded to
transient failures only — a refusal is never retried — normalisation that keeps provenance and reports
every rejected record with its reason, deduplication through the same canonical-identity rule the rest of
the app uses, and a run outcome that is one of success/empty/partial/failure rather than a boolean. There
is deliberately **no flag anywhere that opens the gate**: measured today, forcing it open would enable
exactly one source, and the whole "nothing runs" property rests on that one constant being honest.

## How matching works (and what it will not claim)

When you evaluate a saved listing, the app shows two things: whether you appear **eligible**, and how the
listing compares with what you have recorded — the **matching** view. Matching looks at six factors and
says what it found for each one:

| Factor | Compared against |
| --- | --- |
| Required skills | the skills the listing states, against the skills you recorded |
| Experience | the listing's stated range, against the years you recorded |
| Qualification | any degree/study-status/graduation-year the listing names |
| Location | the listing's location text, against your preferred places |
| Work mode | remote / hybrid / onsite, when the listing states one |
| Role type | internship / full-time / contract / …, when the listing states one |

Each factor is reported as **pass**, **partial**, **fail**, **unknown** or **not applicable**, with the
reason ("3 of 4 required skill(s) are recorded for you; missing: Kubernetes"), so you can disagree with
the app and see exactly which fact to change.

**What it will not do.** It does not invent facts: if a listing states no required skills, that factor is
*not applicable* — not a zero and not a perfect score — and if you have not recorded your experience, the
experience factor is *unknown* rather than assumed. The score is always shown with **how much of the
picture was actually known** (the coverage): below half, the reading is *not enough information* whatever
the known factors said, and a *strong* reading is only possible once two thirds of the applicable weight
is known. The order listings appear in is a **review order**: it puts listings that could actually be
compared first, then the better overlap, so a listing you happen to know almost nothing about cannot jump
to the top.

**It is never a probability.** The number is the share of your recorded preferences that the listing
satisfies — nothing about the employer, their other applicants, or their decision. It is not a chance of
being hired, no employer ever sees it, and a script in the test suite fails the build if any wording that
reads like a forecast appears in the output. A listing whose stated requirements you do not meet is
**blocked** from the recommendation while its comparison stays on screen: blocking is not hiding.

**Not compared yet:** pay. The record has no compensation field, so the app says nothing about it rather
than guessing from the listing's free text. Also, differently-spelled skill names are only treated as the
same when you supply that equivalence yourself — "Postgres" and "PostgreSQL" are separate until you say
otherwise, because guessing which names are interchangeable is how a matching tool starts lying.

## Keep your own employment and education record

The profile is a summary you hold in your head — a country, a discipline, a skills list, a years-of-work
figure. The **Work history & study** tab is the record underneath it: each role you have held, and each
qualification you have. It is the CV-shaped list, in the order a CV reads, and it is written by you,
stored on this machine, and used for nothing else.

**Employment.** Employer, job title, employment type (full time, part time, contract, internship,
apprenticeship, self-employed, unknown), a start date, an end date *if you know it*, an explicit **current
role** flag, and an optional note about what you did.

**Education.** Institution, qualification, optional discipline, optional start date, completion date if
you have finished, and an **ongoing study** flag.

**What is refused rather than stored, because it cannot be true:** an end date before the start date (both
dates are named in the message), a current role that also has an end date, an ongoing qualification that
also has a completion date, a role or qualification with a blank employer, title, institution or
qualification, and the same role or qualification twice (employer, title and start date, or institution,
qualification and start date — capitalisation and spacing do not make it a different record). Dates must
be written `YYYY-MM-DD`; a field that promises that shape does not quietly accept four other spellings.

**What is left unknown rather than guessed:** an end date you have not recorded. A role that has ended
but whose end date you do not know stays that way — it is shown as `end date not recorded`, and it
contributes **no** duration, because nothing states that it continued. The same applies to a missing start
date or completion date in education: the list says `start not recorded` rather than inventing one.

**The duration line is about periods, not about experience.** The tab reports how many months are
*covered* by the roles that are current or fully dated — months covered by two roles at once are counted
once, a gap between roles is not counted, and a role with no recorded end counts nothing. It says which
records it could not time, and it is never written back into your profile, which keeps its own
years-of-experience figure that you control. A single confident "years of experience" number derived
from these records would be a claim the records do not support.

```bash
python -m career_agent --history                       # both lists, and the months-covered line (read-only)
python -m career_agent --add-role "Sandbox Systems" --title "Data Engineer" \
    --start 2023-04-01 --current --employment-type full_time --summary "built the ingestion pipeline"
python -m career_agent --add-role "Old Co" --title "Analyst" --start 2020-01-06 --end 2023-03-31
python -m career_agent --add-study "IIT Delhi" --qualification "B.Tech" --discipline ECE \
    --completed 2019-05-31
python -m career_agent --add-study "Coursera" --qualification "Specialisation" --ongoing
```

`--history` is read-only. `--add-role` and `--add-study` add one record each and never edit or delete one;
a refusal exits with status `2` and writes nothing at all. `--employment-type` defaults to `unknown`,
which claims nothing, and an unrecognised type in an imported file becomes `unknown` rather than costing
you the record's employer and dates.

**Deleting.** A record can be deleted from the tab, after a confirmation that says what is being removed
and that your profile, listings and other records are not. Deleting your **saved profile** also deletes
these records, in one transaction, because they are the detail behind it — and the confirmation names how
many of each before you agree, rather than the word "profile" standing in for eleven rows.

**Where these records live and where they travel.** They are two tables in the schema (version 6 added
`candidate_work_history` and `candidate_education`); an existing database is upgraded to it additively,
with every existing row preserved and the new tables empty and immediately usable. They are included in
SQLite backups and restores, in the JSON export (format version 2, top-level `work_history` and
`education` arrays) and in the import rules described under
[Move your data to another computer](#move-your-data-to-another-computer-json-export-and-import). Nothing
here is uploaded, and no employer or institution is contacted about any of it.

**Not implemented:** attaching a document to a role, importing roles from a résumé into this list (résumé
import proposes the flat profile fields only), any verification of a record against an employer, and any
use of these records in eligibility or matching. They are your notes.

## See how the search is going (and what the numbers do not mean)

`python -m career_agent --analytics` prints what the records in this database add up to. The same report is
in the window: a one-line summary under the **Application tracker** list and a **Progress report** button
that opens it in full. Nothing in it is fetched, estimated or modelled — every figure is a count of rows you
wrote, and the module that computes it (`career_agent/analytics.py`) is pure, so the window and the command
line cannot disagree about your own numbers.

```bash
python -m career_agent --analytics     # counts, rates with their denominators, and what cannot be measured
```

**What it reports.** Applications recorded as sent; applications with a recorded reply; applications with an
interview round; rounds recorded, rounds whose day has arrived, rounds where you recorded how it went;
rejections recorded with evidence; applications you withdrew; applications still being planned; follow-up
entries and notes you wrote. Then four rates and two timings.

**Four rules it will not break:**

1. **A rate always names its denominator.** "2 of 6 recorded as sent (33%)" — never a bare percentage. The
   denominator is *applications recorded as sent in this database*, which is a fact about your records and
   not a claim about every application you have ever made.
2. **A denominator below five applications produces no rate at all.** The counts are still printed, with the
   reason: over three applications, one email moves a percentage by thirty points and reads as a trend.
3. **Something this application cannot measure is reported as unmeasurable, never as zero.** An **offer** is
   the clearest case: no field, status or record here can hold one, so no offer count or offer rate appears
   at all, and the report says why. A printed `0 offers` would read as "you received none". The same applies
   to whatever an employer did without telling you.
4. **A real zero is reported as a zero.** Twenty applications with no reply is `0 of 20` — a genuine and
   important fact, and the one the report exists to show.

**Timings.** The median days from application to first recorded reply, over the pairs where you recorded
both dates, with the sample size stated; below three pairs it is withheld and says how many it has. A reply
dated before the application is treated as a typing mistake and excluded from the median rather than counted
as a negative gap. A reply recorded only as a status change cannot be used for timing at all — a status
records when the row was saved here, not the day the employer wrote — and the report says so instead of
quietly shrinking its sample.

**Periods.** The last 90 days against the 90 before it, for replies recorded. Both windows need at least
five recorded applications before they are compared at all; otherwise the two counts are printed and the
comparison is withheld with the reason. Applications with no recorded application date are left out of both
windows, and the report says how many that was.

**What it refuses to say.** No sentence in the report claims that anything caused anything: a rate that
changed did not change *because* you changed your résumé. It is not a measure of your ability or your worth.
It never calls an outcome a "success", because no outcome is defined as one here. The caveats travel inside
the report — in the window as well as on the command line — so they cannot be separated from the numbers they
qualify.

**What it is not.** Not a projection, not a benchmark against other people, and not a model of how a search
"usually" goes: this application has no data about anyone else's search, and it will not invent any.

## What needs doing next (preparation, interviews and follow-ups in one list)

A job hunt is not a list of jobs, it is a list of things to do. The **Next actions** tab answers that one
question across every application: the **preparation items** you have written down (tailor the résumé,
read the engineering blog, get a reference letter ready), the **interview rounds** you have been invited to
and recorded, and the **follow-up days** that have arrived. Overdue first, then today, then what is coming;
within the overdue group the oldest promise comes first whatever its kind, and the kind breaks ties on the same
day - an appointment on somebody else's calendar ahead of a chase, ahead of your own checklist.

```bash
python -m career_agent --next-actions     # what is due, what is coming, and what is recorded
python -m career_agent --interviews       # the rounds you have recorded, next one first
```

**A preparation item is a plan.** You write the title, pick a kind (tailoring, research, practice,
documents, other) and optionally a day. Ticking it off records that *you* said you did it; it never moves
the application, never writes an activity entry, and is not evidence that anything was sent. A title that is
already open cannot be added twice - two identical rows in a checklist are almost always a double click -
but the same title can come back after it is finished, because repeating a step is a real thing people do.

**An interview round is your note, not an employer's decision.** Which round it is, the day it is planned
for, how it is being held, and afterwards *your own* reading of how it went. The vocabulary has no value
for "passed" or "rejected" and never will: the application cannot know an employer's decision, so an offer
or a rejection stays what it is - an activity entry you write and a status change you make yourself, with
your evidence. A round planned for today is still ahead of you, and the list says so.

Everything on the tab can be deleted, and each deletion asks first. Deleting a follow-up *day* is not the
same operation: that belongs to the application record, so the tab sends you to **Follow-ups**, which
clears the day and leaves the application, its status and its history untouched.

**What none of this does.** No status changes, no network, no calendar invite, no email, nothing sent to an
employer. The list is computed from your own records against *your* local day, and the command line says
the same thing in one line, `--next-actions`, which is read-only.


## Follow up on an application (and put it in your own calendar)

An application you sent and never heard about is the state most job hunts die in, so each application can
carry **a day you plan to act on** and a short note. The **Follow-ups** tab lists them: overdue first,
then due today, then what is coming.

**A follow-up is a plan, not a status.** Setting one never moves the application, never writes an activity
entry and never records that an employer replied — silence is not a reply, and neither is your own
reminder. The row shows the application's real status beside your note so you can see both. Clearing a
follow-up asks first and keeps the application, its status and its history exactly as they were. A note
without a day is refused rather than stored, because a reminder with no day is never shown at the right
time. The day also survives everything else you do to the application: moving a status forward, adding
evidence or confirming a submission all leave the reminder where it was, and the only way it disappears is
that you clear it. (This was a real defect until 2026-10-15: a status change wrote the reminder out of the
database without a word. The storage boundary now treats the plan as its own field that an ordinary save
cannot touch, and both the fix and the defect are pinned by tests.)

Three ways to meet your own reminders:

- the **daily reminder task** (`follow-up-digest`, 09:00 Asia/Kolkata) reads the days you recorded, reports
  the ones that are due or overdue in the run history, and changes nothing;
- `career-agent --follow-ups` prints the same list in a terminal, read-only, with the local day it used;
- **Export to a calendar file** (or `career-agent --calendar-to PATH`) writes an `.ics` file for your own
  calendar application — all-day entries, no attendees, no links, and on POSIX the file is owner-only
  (`-rw-------`). It is written on this machine and sent nowhere; an existing file is never replaced
  without asking.

For the record: the project has no email, calendar-account or notification integration, and none is
mocked into looking present — a reminder that needs somebody's credentials is documented as unavailable,
not faked. What it does have is the *interface* for one, with every path to a real side effect switched
off: see [Can it send email or add things to my calendar?](#can-it-send-email-or-add-things-to-my-calendar).

## Can it send email or add things to my calendar?

Short answer: no, and it will not pretend otherwise. What exists is the interface a real integration would
need, built so that nothing can happen by accident:

```bash
python -m career_agent --integration-status                    # what exists, and why none is enabled
python -m career_agent --preview-calendar-export               # the events the .ics export would hold
python -m career_agent --draft-follow-up j1                    # a draft, printed in full; nothing is sent
python -m career_agent --draft-follow-up j1 --recipient you@example.invalid \
    --save-draft ~/follow-up.txt                               # the same draft as a local text file
```

**A draft is not an action, and a preview is not an action either.** A draft is a value: a subject, a body,
the application it belongs to, and — only if you type it — a recipient. The preview says what a person
would need to know before anything happened, including the facts that are *missing*. Nothing here guesses:
no address is derived from an employer's name, no interview time is inferred from a date, and an event with
no recorded time is an all-day entry with the gap stated rather than a made-up appointment. The **Follow-ups**
tab has the same two read-only actions, **Preview the calendar export** and **Draft a follow-up email**.

**Execution is disabled, and the refusal names the reason.** Every email or calendar operation goes through
an integration object, and the one this build returns refuses everything with an
`unsupported`/`disabled` result that says nothing was sent or created and points at what does work — the
local `.ics` export you import yourself. There is no setting, environment variable or stored value that
enables one instead; a real provider would need the seven things `--integration-status` lists (an approved
provider and scope, credentials in the operating system's keyring, provider-side idempotency, a
data-minimization statement, an off-by-default switch, failure handling that cannot lie, and a provider-level
test path).

**Doing it twice must not mean doing it twice.** Every draft and every event carries an operation id derived
from its own content, so asking again produces the same id, and an integration that has already performed
that operation reports it as a duplicate instead of performing it again. A *failed* attempt is not recorded
as done, so a retry with the same id is allowed and still performs the operation once. Proving this without
an account is what `--mock-ledger PATH` is for: it runs the whole sequence against a local mock that records
operations in a file you choose, contacts nothing, and needs no socket at all (a test runs the full
draft-and-record path in an interpreter where creating a socket raises). What the mock cannot do is prove
that a request the network dropped never arrived — that is provider-side idempotency, and it is why a real
integration is a decision with evidence behind it rather than a flag.

## Run scheduled tasks (local worker)

The app can keep a schedule of its own work. Three tasks are created for you, and all of them run on
your computer while the worker process is running — nothing is sent anywhere, and nothing runs while the
computer is off or asleep.

| Task | Runs at | What it does |
| --- | --- | --- |
| `follow-up-digest` | 09:00 Asia/Kolkata | Reports the follow-up days that are due or overdue (writes nothing) |
| `daily-backup` | 23:30 Asia/Kolkata | Writes a verified snapshot of your database beside it |
| `scheduled-discovery` | 00:00 and 12:00 Asia/Kolkata | Scheduled job discovery — **refused** while the source-quality gate is closed |

```bash
career-agent --seed-tasks        # add the default schedule to this database (leaves your edits alone)
career-agent --worker-status     # what is scheduled, what is running, how the recent attempts ended
career-agent --worker            # run the schedule in the foreground until you press Ctrl-C
```

`--worker-status` writes nothing at all — it does not take the worker's lease and does not mark
anything as running — so it is safe to run whenever you are wondering what the scheduler is doing.

**What the worker guarantees.** A run is identified by the instant the schedule named, not by when it
happened, and the database holds one attempt per scheduled occurrence: a restart, a retry after a
failure, or a second copy of the app cannot turn one occurrence into two runs, and cannot lose one
either. A failure is retried with a bounded, doubling delay up to the task's attempt limit, and the
retry serves the occurrence it still owes. An attempt whose worker stopped is closed as *interrupted*
— not as failed and not as successful, because nobody saw it finish — and the occurrence is re-planned.
While a worker is running it holds a lease, so a second worker started by mistake stops with a message
instead of running the same tasks twice; a lease whose heartbeat has gone stale is taken over, because
the alternative is a schedule that can never run again.

**What it does not guarantee.** Background work happens while the worker process runs. This is a local
worker, not a service: close the terminal, shut the laptop, or sleep the machine, and nothing runs until
you start it again. Operating while the computer is off needs a separately deployed and verified
worker, which does not exist yet — so that capability is not claimed anywhere in this project. A handler
is asked to check its deadline and stop flag, and a long-running handler that ignores them keeps
running; the *record* still tells the truth (an attempt that finished after its deadline is recorded as
timed out rather than successful), but the worker cannot force a Python function to return.

**Discovery stays refused.** `--worker` reports the gate's state at startup, and every scheduled
discovery run is recorded as a refusal with the reason. That is the permission rule working, not a
fault: no source has passed the quality gate, so nothing is read.

## Audit research data

To regenerate a reproducible CSV integrity summary (including input SHA-256, row/column counts, duplicate IDs, canonical URL groups, status and permission counts):

```bash
python scripts/audit_job_source_csv.py
```

To measure the matching engine and the résumé importer across industries — design, VLSI/embedded,
mechanical, civil, software/data, business and laboratory work — against a reviewed, entirely synthetic
evaluation set (7 occupation groups, 21 listings with a stated review order, 7 résumé texts):

```bash
python scripts/evaluate_cross_industry.py
```

It reports the engine's agreement with the reviewed order, the number of hard-eligibility violations
(which must be zero, and makes the command exit non-zero), how many stated résumé values were extracted,
and the extraction rules it checks in both directions. It also lists what it does **not** claim: the corpus
is synthetic and small, so its numbers measure agreement with a written standard rather than with real
documents or hiring outcomes. Running it is how the five extractor defects described in
[the evaluation run](research/cross-industry-evaluation-run-2026-10-16.md) were found — an unrecognised
heading for a field this app proposes leaking into the skills list, design/architecture/medical/law and
arts degrees not recognised at all, a trailing full stop hiding the discipline, a `LABORATORY SKILLS`
heading not counting as a skills heading, and `GD&T` being dropped as a skill.

The tool intentionally does not invent a direct-link validity percentage; the existing route observations do not provide a defensible uniform denominator.

## Run tests

Python 3.10+; no third-party packages are required to run the suite. (The PDF import path uses the
optional `pypdf` library when it is installed; the tests that need it skip themselves with a reason when
it is absent, and everything else — including DOCX import — still runs.)

```bash
python -m unittest discover -s tests -v
```

The suite covers the activity history (domain validation, storage order and boundaries, the append-only
write path, deletion, cascade with its listing, unreadable rows refused by name on the read path while
the export still carries them, the status never being touched by an entry, and the desktop panel: adding
through the real dialog, refusals that write nothing, delete confirmation and its cancelled and
already-gone paths, and a cleared panel when no application is selected), the distribution metadata and entry point (the version literal setuptools reads, the
declared dependency surface, the console-script target, and the declared Python floor matching the CI
matrix — the wheel itself is built and installed by the `installed-package` CI job, not by these tests), the domain rules, SQLite persistence, the CSV audit tool, untrusted-URL validation,
the source permission gates and run-outcome rules, the Tk-free desktop logic (form mapping, save
planning, database-path resolution, stored-timestamp rendering, profile read-back comparison), local
résumé import (PDF and DOCX text extraction including DOCX tables, encrypted, damaged, empty, oversized
and textless files, the refusal to invent values, and the socket-blocked local-only guarantee), the status
chooser's option set against
the state machine, unrecognised stored statuses and the refusal paths they trigger, version reporting and
start-up diagnostics (including path redaction), verified backup and restore (including corruption,
schema-version and permission failures, version-aware acceptance of an older backup, the migration
framework (a version-1 database updated in place with its rows intact, a step that fails leaving the
version and structure untouched, a partly applied step reported honestly rather than as "nothing
changed", a verified copy taken before an existing database is updated - not for a new one, not for a
current one, and not an existing copy reused - with a refused copy leaving the update unstarted and the
file byte-identical, refusals by type for a newer or unrecognised file), WAL and side-file handling, and the
command-line front end —
its exit codes, its refusals, the confirmation it requires before replacing a database, and the
fact that it never imports the GUI toolkit), and
the desktop handlers exercised through widget stubs — including the résumé review screen: proposals shown
with evidence before anything is saved, per-value accept and reject, cancellation and declined
confirmation writing nothing, validation and database failures never reported as success, and no document
text reaching a message, the status line or the database. The stubs refuse the options real Tk refuses
(a wrapping option on `ttk.Checkbutton` — which has none — crashed the review window on macOS while the
suite stayed green), and the whole window with every tab is built against those stubs, so a widget
option Tk would reject fails here instead of on someone's desktop. The résumé fixtures are synthetic documents
built in the test process; no real candidate data and no network access are involved. It also checks the
SQLite resource
lifecycle: no test may leave a connection open (the whole suite is re-run in a child process that
counts them, because Python 3.10/3.11 never emit the `ResourceWarning: unclosed database` that
macOS reported), `with sqlite3.connect(...)` — which manages the transaction, not the
connection — is refused by a source scan, and a test may not resolve the machine's own database path,
so the suite cannot open the candidate's real database. Closing the window is covered too: the
registered `WM_DELETE_WINDOW` handler closes the store, destroys the window, and writes none of the
form's unsaved values. It
requires no display and no GUI packages.

A window can also be built and driven without a person, on a machine that has one:

```bash
python scripts/desktop_smoke_test.py
```

It constructs the real `CareerAgentApp` against a disposable synthetic database in a temporary folder,
checks the window's title, minimum size, eight tabs in their documented order, that every tab was built,
and that the main lists carry the columns they are read from, switches to every tab with a real rendering
pass, presses the affected tabs' read-only **Refresh** buttons through Tk's own command dispatch, then
closes the window, releases the database and deletes the folder it created — and checks that the default
per-user database was neither created nor modified. It exits `0` for `RESULT: PASS`, `1` for
`RESULT: FAIL` and `2` for `RESULT: BLOCKED`: a machine with no display, or no `tkinter`, is a BLOCKED run
and never a pass, and the script asserts nothing about pixels, layout or dialog wording. CI runs it under
Xvfb on Linux, where it must pass, and on the Windows and macOS legs, where a runner without a display
session reports BLOCKED instead of being counted as a pass or failing the build.

The workflows themselves are driven the same way, in more depth:

```bash
python scripts/desktop_acceptance.py
```

Ten workflows run against the real window and disposable synthetic databases: a profile (with a role and a
qualification) typed, saved, closed and read back; a listing whose source URL and blank apply URL stay separate
fields and whose blank stays blank; a listing with no availability evidence evaluating to UNKNOWN and refusing
to be shortlisted, then reaching PASS and being shortlisted once the evidence and requirements are stated; an
application moved through its permitted statuses with a confirmation refused until the person asserts it, and a
recorded interview round never counted as an application sent or as an outcome; an export that agrees with the
database and says the file may hold personal data, imported into a second database, plus refusals (a malformed
file, a damaged record, an unprotected target, a declined plan, a repeat import) that each write nothing; the
work history and study forms, where a current role is added, an impossible period and a date written in another
shape are refused with nothing stored, an ongoing qualification is added, a contradictory one is refused, a
role's stored values are loaded into an emptied form and its title saved back over the record, and the
current-role flag is taken off again with an end date saved; follow-up reminders and the combined next-action
list, where the first day for an application is recorded from the window, overdue, due-today and later days
read as words computed from fixed offsets, the list survives a close and reopen, a day is moved and cleared
from its own row with a refused clear changing nothing, a staged day is ticked off without touching any status,
and the calendar preview and the email draft write nothing and send nothing; the schedule's own tab, where the
default tasks are added and adding them again keeps them, pausing asks first and keeps the task's times and
history, a paused task is still paused after a restart, resuming schedules the next occurrence from now and
replays nothing, a task whose record has gone is reported rather than written back, and no worker is started,
no lease taken and no attempt recorded; data safety, where a backup is written through the window and verified
before success is reported, an existing file is never overwritten, a cancelled chooser writes nothing, a
malformed, foreign, truncated or too-new file is refused with the live database unchanged, a declined restore
changes nothing, a confirmed restore brings the backed-up records back while keeping the previous database as a
readable copy, and nothing temporary is left behind on success or failure; what the schedule walked past while
nothing was running, reported from the same status lines the tab already shows, with the overdue occurrence named
separately as the one a worker will still claim; and cleanup that releases every
window and connection, deletes its own folder and leaves the person's database byte-identical, including after
a forced failure. It exits `0`, `1` or `2` for PASS, FAIL and BLOCKED, reports 77 checks, and compares that
number against the checks its own source declares so a check that stops running fails the run. The dialogs a person would answer are answered by the run - a file chooser, the import plan and
the confirmation - and every one of them is recorded and reported. On a machine with no display,
`--stand-in-tk` runs the same workflows against the test suite's stand-in widget module for development: it
prints DEVELOPMENT RUN, never prints a pass or a failure, and exits 2, and CI has a step that requires exactly
that. CI runs the real thing on the display-backed Linux job (where it must pass) and on the Windows and macOS
legs (where BLOCKED is tolerated and reported, and a failure is a failure).

A failing step is readable without a browser. Job logs are served from a storage host that a restricted
network cannot reach, and the API's answer for a failed step is its exit status alone, so every step of the new
jobs, from the interpreter report to the smoke test, records its output into one notes file - the step opens
with `tee -a` into it, and the file is created by a step of its own first. When the job fails,
`scripts/ci_annotate.py` turns the recorded failures into annotations: one listing every failing test by name,
ten findings with the smoke test's failed check and the end of each traceback, and the run's last words. The
inventory of names is the part that makes a red leg on a platform this checkout cannot run readable past its
first ten failures. That is how the first runs of these legs were diagnosed,
and it is why the defects they found (see below) are in this repository's history rather than in a log nobody
could open. A step that is not recorded is a step that cannot be diagnosed from a restricted network; the
macOS wheel-verification step was the one such step left, and it stayed unexplained until it was covered.

Automated tests, including that script, do **not** cover what a person sees: pixel rendering, layout,
dialog wording, and operating-system integration are still checked by hand on a real desktop. Those checks
remain outstanding, and every one of their statuses is in
[the local-alpha smoke-test checklist](research/local-alpha-manual-smoke-test-checklist-2026-10-14.md) - which
is the record, with one line per step and its result. How to get to a state where those steps can be run, what
to capture for each area, and where to write the result is
[the human desktop acceptance handoff](research/human-desktop-acceptance-handoff-2026-10-16.md); the status of
each delivery phase, with the evidence beside it, is the table in [phases.md](phases.md). Which of the ~50
research artefacts answers what, and which of them are current guidance rather than dated evidence, is
[the research index](research/README.md).

## Packaging status

There is no installer, no signed desktop bundle, and no bundled interpreter, and nothing in this
repository claims one. What exists today:

- **An installable package.** `pyproject.toml` carries the PEP 621 metadata: name `ai-career-agent`,
  `requires-python = ">=3.10"`, **no required third-party dependency**, the optional `pdf` extra
  (`pypdf>=4.3`) for PDF résumé reading, and a `career-agent` console script that points at the same
  `career_agent.__main__:main` the module form runs. Only `career_agent/` is packaged: `tests/` and
  `scripts/` stay in the checkout and are not importable from an installed environment.
- **One version, one source.** `career_agent.__version__` is a plain literal and `pyproject.toml` reads it
  with `version = {attr = "career_agent.__version__"}`, so the installed metadata and what `--version`
  prints cannot drift apart. A test pins that the assignment stays statically readable: if it ever became
  computed, the build would fail rather than quietly record a different version.
- **A build and install exercised in CI.** The `installed-package` job builds the wheel, checks that it
  contains the application package and nothing else, installs it into a clean environment, and runs the
  installed command from *outside* the checkout — version report, `--help`, a throwaway database, backup,
  restore. Its assertions mirror the ones `tests/test_packaging.py` makes from the source tree, so the
  behaviour is proven by one run; it is executed on two interpreters anyway, the floor the metadata
  declares (3.10) and the newest one the suite is run on (3.13), because a wheel or a console script that
  only works on the version used to build it is exactly the defect that installing from a checkout hides.
  The same build-and-install-from-a-wheel rehearsal is repeated on Windows and macOS by the
  `cross-platform` job, and the `pdf-extra` job proves the optional library is what unlocks the résumé
  tests rather than a skip being mistaken for coverage: without `pypdf` the PDF cases skip, and with it
  installed the same module has to finish with a bare `OK`.
- **Which interpreters are tested, and which are not.** CI runs the full suite, `compileall` and the CSV
  audit on **3.10, 3.11, 3.12 and 3.13** on Linux, and the same suite on **3.10 and 3.13** on Windows and
  macOS, where it also exercises the installed command surface from a built wheel: `--version`,
  `--doctor` against a missing database and against a file that is not one, schema creation and
  cross-process persistence, a backup and a restore that really replace data, a JSON export imported into
  a second database, and the two invariants that keep discovery closed. `requires-python = ">=3.10"` has
  no upper bound — a newer interpreter is not forbidden — but nothing here claims one: 3.14 has not been
  run, so it is untested rather than supported, and the same is true of every interpreter the workflow
  does not name. The window is exercised on three levels, and they are not interchangeable: handler tests
  with stubbed widgets on Linux, the scripted smoke test above under a real display (Xvfb) on Linux where
  it must pass, and — the only level that can say a person can use it — [the manual
  checklist](research/local-alpha-manual-smoke-test-checklist-2026-10-14.md), which CI cannot run and
  whose GUI steps are still unrun. There is also no lint, formatter or type-check step configured, so none
  is claimed.
- **The documented commands are checked against the program.** `tests/test_documented_commands.py` reads
  every `--flag` this README and the manual checklist tell a person to run and looks it up in the real
  `--help` output, so a documented command that no longer exists fails the suite instead of failing in
  somebody's terminal.
- The app runs from a source checkout with `python -m career_agent` and needs the standard library plus
  Tkinter. Reading PDF résumés additionally needs the optional `pypdf` library; every other feature,
  including DOCX résumé import, works without it. A packaged build would need a decision on whether to
  bundle that library (see below).
- `career_agent.__version__` is the single source of truth the checkout reports.
  `python -m career_agent --version` prints it with the database schema version and works with no
  packaging metadata, no display, and no third-party tools.
- `career_agent.diagnostics` explains a start-up failure in plain language, redacts the local paths it
  knows about (the database file and folder, the home folder, and any path named on the command line,
  while never substituting a value that could match ordinary prose), replaces any remaining *absolute*
  location found in the failure text itself (an external volume, a network share, a Windows drive path)
  with a placeholder, leaves relative words and public URLs untouched, and keeps one bounded owner-only
  note. The failure classes it distinguishes and the redaction rules are covered by tests. Text it cannot
  classify — ordinary prose inside an exception message — is kept as it is: the note is local, and the
  message is what makes it useful.

Missing pieces, in the order they are needed, for a packaged desktop alpha:

1. Per-platform launch artefacts, code signing and notarisation (macOS `.app`, Windows installer), with
   the icon, identity, and update story that implies.
2. A decision on bundling the interpreter (PyInstaller/Briefcase-style) versus requiring a system Python
   with Tkinter — including the size, update, and Tk-availability consequences of each choice.
3. A release checklist that runs this repository's suite, the manual desktop checklist, and a
   backup/restore rehearsal on each supported operating system from the packaged build. What exists today
   is the repository half of that rehearsal, run on this machine and recorded in [the release-readiness
   audit](research/release-readiness-audit-2026-10-15.md): install from the built wheel, `--doctor`,
   backup, restore, export, import, a real schema upgrade, and the failure paths — each with the exact
   command and its observed result. The per-operating-system half is only partly covered: CI runs the
   suite, a real Tk widget lifecycle where the runner has one, and the installed-command rehearsal on real
   Windows and macOS runners, but never from a packaged build and never with a person at the keyboard,
   which is what that checklist asks for.

Nothing is published to a package index and no release archive is attached anywhere, so "install from
this checkout into your own Python environment, or run it from the checkout directly" is the accurate
description — not a downloadable product, and not a packaged desktop app.

### What a version number promises about your data

There is no released build yet, so `career_agent.__version__` names a development build of the same local
alpha and carries **no stability promise**: any version may change the database schema. What it does
promise is narrower and enforced by the code, so a newer build never has to guess at your data:

- **A newer build opens an older database, an older build refuses a newer one.** The file records the
  schema version it holds (`PRAGMA user_version`); a build that finds a *higher* number refuses to open it
  and says which version wrote it. Nothing is read partially and nothing is downgraded — install the newer
  build, or restore a backup from before the upgrade.
- **An existing file is copied before it is changed.** Before the first step updates a database in place,
  a verified copy is taken beside it (`<name>.backup-<timestamp>.sqlite3`) and the step is recorded. A
  copy that cannot be written stops the upgrade instead of changing a file that has no second copy.
- **Steps are additive and run one at a time.** Each recorded step runs in its own transaction, and a step
  that fails leaves the file at the version it reached, with the failure reported rather than swallowed.
  Opening an older file is the only upgrade path; there is no separate migration command.
- **Backups are accepted across versions.** A backup written by an older schema version is validated
  against the tables *its* version declared and is updated when it is opened; a file written for a newer
  schema is refused rather than half-read (see "What a restore guarantees").
- **Export documents carry their format version.** A file whose `format_version` this build does not know
  is refused with that reason, and an export always writes a version. Importing never overwrites a stored
  listing or profile — an existing record wins over the file's copy.
- **An unreadable record is reported, never repaired.** A status, activity kind or payload this build
  cannot interpret is refused by name, on the read paths and in `--doctor`, without being rewritten or
  deleted; the export still takes the data out, marking the value it could not label; and an import into
  that database is refused before it writes anything, rather than applied in part.

Before upgrading, run `career-agent --backup-to <somewhere-private>`; after upgrading, run
`career-agent --doctor`, which reports the schema version the file now records. The rehearsal behind these
claims — including a real schema-5 file opened by an installed wheel — is recorded with commands and
observed output in the [release-readiness audit](research/release-readiness-audit-2026-10-15.md).

## Safety and product principles

- Keep candidate profile and application history local by default.
- Missing eligibility evidence is not a pass.
- A visible Apply button is not proof that a job is open or that submission succeeded.
- Never infer worldwide eligibility from the word “remote.”
- Do not fabricate candidate facts or screening answers.
- Do not bypass source restrictions or add unapproved connectors.
- A relevance score is not a hiring probability.
- The current alpha does not submit applications. Future automated actions require source/employer permission, reliability evidence, and a scoped, revocable policy; no blanket permission is implied.
- What the alpha defends against — and what it does not — is set out in [the threat model](research/threat-model-2026-10-16.md): no network path in the shipped code, owner-only files, refusals instead of destructive overwrites, and the residual risks named honestly (no encryption at rest, and no single erase-everything command).

## Project status

The local-only desktop alpha is implemented, installable from this checkout, and source research continues in parallel. It is not yet a packaged or signed production release; follow the manual GUI smoke-test checklist before claiming desktop acceptance. This does **not** mean the source-quality gate has passed or that live discovery/application workflows are ready. See [the local-alpha smoke-test checklist](research/local-alpha-manual-smoke-test-checklist-2026-10-14.md) and [the current source-quality gate assessment](research/source-quality-gate-assessment-2026-10-14.md).
