# Threat model — the local-only alpha, 2026-10-16

**Scope.** The desktop/CLI application in this repository as it exists at the commit this file ships with:
one local SQLite database, one local process, no server, no account, no network call. This is the Phase 2
"threat model" work item. It is written from the code, the tests and measurements made with the shipped
command line on 2026-10-16 (section 8), not from a template.

**What this document is for.** Phase 2's exit criterion is that *privacy and security boundaries are
documented and enforced*. The enforcement half is the tests and the storage boundary cited beside each
control below; this file is the documentation half, and it names the residual risks honestly instead of
implying that local means safe.

## 1. Assets

| Asset | Where it lives | Why it matters |
| --- | --- | --- |
| Candidate profile: name, contact details, education, employment, résumé-derived text and its evidence | table rows in the local database, and in `--doctor` output | Personal data; the résumé text is the most sensitive content the app holds |
| Application history: listings, tracker records with status evidence, activities, interview rounds, preparation items | local database | Says where the person applied and what an employer said |
| Follow-up days and notes | local database; mirrored into `.ics` files the user writes | Reveals job-search activity to anyone who sees the file |
| Backups | `*.sqlite3` files chosen by the user, plus pre-restore snapshots beside the database | Complete copies of everything above |
| JSON export | user-chosen path | Copy of profile, listings and history; carries its own warning |
| Logs: `logs/application.log` and `startup-diagnostics.log` | beside the database | Must not contain paths or personal data (see 4.4) |
| Mock integration ledger, drafts | user-chosen paths | Drafts contain a private message body |
| The database file itself | `--database` or the per-user application-data folder | Everything above in one file |

**There is no secret to store.** The product has no account, no API token, no password and no session
for any service: nothing in this repository asks for a credential and nothing keeps one, so Phase 2's
"secure secret storage" is satisfied by having no secrets rather than by a store — and the standing rule
is that no credential enters a log, a test, a document or a commit. If a future integration needs one,
that is a new threat with its own section to write, not an extension of this one.

Nothing is transmitted, because nothing in the shipped code can open a connection (4.1). That is the single
largest control in the model, and it is also why the model is short: the realistic adversaries are other
local users or processes, accident, and the user's own files travelling further than the user intended.

## 2. Adversaries considered

1. **Another local user account** on a shared machine or a shared home directory.
2. **Another process running as the same user** — including a synchronised folder agent (OneDrive, Dropbox,
   iCloud Drive) pointed at the data folder, which will copy the database and its backups off the machine.
3. **Accident and misuse by the person themselves** — overwriting a backup, restoring the wrong file,
   restoring the live database from itself, deleting the wrong record.
4. **Untrusted input**: a résumé file the person was sent, a listing's text, an export file from elsewhere.
5. **An attacker who can run code as the user, or as root/administrator** — explicitly *out* of scope at this
   layer; see section 5.
6. **The app itself being the adversary** — a bug that silently deletes, overwrites or invents data. This is
   the class the storage invariants are aimed at (4.3).

## 3. Assumptions the model rests on

- The operating system enforces file permissions and protects the user's session.
- The database file, backups, exports and logs are written with owner-only permissions where the platform
  supports them, and a destination's permissions are *tightened*, never trusted (4.2).
- The app is run as the person whose data it is: there is no multi-user mode, no sharing and no server.
- A *packaged, signed* release does not exist yet, so nothing here depends on one. Nothing here claims a
  signed artefact, an installer, or an automatic update path.

## 4. Controls, with the evidence beside them

### 4.1 Nothing can leave the machine

`tests/test_local_only.py::ShippedCodeCannotTransmitTests::test_no_shipped_module_can_transmit_or_resolve`
reads every shipped module and fails if any of them imports a network module or calls a connect/resolve
function; a second test proves the scan reaches the shipped code and would catch a violation, so the scan
cannot pass by matching nothing. Two further tests run the real work in a **child process with socket
creation blocked** — backup and restore, and the draft plus the local mock — so the claim is behavioural, not
only textual. The source-quality gate stays closed (`SOURCE_QUALITY_GATE_PASSED = False`,
`career_agent/sources.py`), `enabled_discovery_sources()` returns nothing, and the curated listing CSV is
pinned by SHA-256 with a known record count, so a change to the data set cannot slip through unnoticed.

### 4.2 Files are owner-only

`career_agent/store.py` defines `_OWNER_ONLY_MODE = 0o600` and applies it when a file is created, falling
back to `os.chmod` where `os.fchmod` does not exist (Windows). Destinations are tightened rather than trusted,
because a umask can only remove bits and never add them. Asserted for each writer:
backups and pre-restore snapshots (`tests/test_backup.py`), JSON exports
(`tests/test_cli_export_import.py`), calendar files (`tests/test_cli_follow_ups.py`), and the integration
draft and mock ledger (`tests/test_cli_integrations.py`, where the draft assertion is `& 0o077 == 0`, "a draft
holds a private message"). Measured again today on Linux: every file written by the probe commands was
`600` — database, backup, export, `.ics`, ledger and draft alike (section 8.1).

### 4.3 The storage boundary refuses records that would lie

Invariants are enforced where the data is written rather than in the interface: a new application record must
start at `discovered`; a new record cannot claim candidate confirmation; `CONFIRMED` requires evidence text; a
job's eligibility normalises under the documented rules and unknown never passes; a saved job or tracker
record is compared against what was stored so a record is not silently overwritten. Two of these were
measured directly today on a synthetic database and refused with a named reason and *nothing saved* — the
"start at discovered" rule and the "confirmation needs a recorded transition" rule (section 8.2). Jobs are
never dropped silently either: the reports count what they skip and say why.

### 4.4 Logs are redacted by construction

Every logged line goes through one formatter: control characters are flattened, filesystem paths are
redacted, the detail is capped, and the line is kept to one line (`career_agent/event_log.py`,
`_clean_detail`). A test asserts that a local location inside a detail is redacted
(`tests/test_event_log.py`). The start-up diagnostics note is the redacted form; `--doctor` is the verbose
one and its own help text says to remove file locations before sharing its output.

### 4.5 Untrusted documents are bounded before they are parsed

`career_agent/resume.py` caps the file at 10 MB, the total uncompressed size of the DOCX parts at 32 MB
(with a comment recording that a ZIP can *declare* far more than it contains), the PDF at 40 pages and the
extracted text at 400 000 characters; it accepts only the compression methods the standard library can
decompress and refuses entries marked encrypted. Tests cover an over-large declared DOCX, an oversized
input, the page cap, a damaged ZIP, a missing document part, and encrypted PDF/DOCX files — each refused with
its own message rather than a traceback. Before `ElementTree` sees `word/document.xml`, an encoding-aware
Expat preflight now refuses any DTD, including one after a long prolog or encoded as UTF-16; this closes
the old bounded ASCII-prefix bypass and prevents internal entity expansion from becoming résumé text. The
late-prolog and UTF-16 cases are regression-tested. This is a parser boundary, not a general malware scan.
Extraction never promotes a guess to a fact: proposals carry their evidence and confidence, and the person
confirms them.

### 4.6 Destructive operations are refused rather than performed

Backups and drafts and calendar files are never overwritten (each refuses an existing path with a non-zero
exit and says what to do); a restore validates its input, keeps a verified copy of the database it replaces,
reopens the result to verify it, and refuses outright when the chosen file *is* the live database (defect
D19, fixed 2026-10-16); an import without confirmation writes nothing, and importing into a directory with no
database yet is refused rather than creating one. A restore that is interrupted leaves a
`.{database}.restore-{stamp}.partial` file rather than a half-replaced database. Every one of these was
re-measured today (section 8.3).

### 4.7 Repeats do not duplicate side effects

The local mock gives an operation a deterministic id, and performing the same operation twice reports that
it *was already performed*, with nothing written again — measured today, with the ledger left at one
operation. Re-running the default-task seeding leaves the three tasks exactly as they were; re-importing the
same export adds nothing and lets the stored record win; a duplicate employment record is refused by name.
One worker per database is enforced by a lease, so two copies of the worker cannot both claim the same
occurrence.

### 4.8a Removal is planned before it is performed

`career_agent/erasure.py` separates the plan from the deletion: the plan is a list of concrete paths with
sizes, computed without creating anything and without opening the database; nothing is removed until the
command line passes `--yes`. Candidates that are directories or symbolic links are refused rather than
followed, each failure is reported with its reason instead of being counted as a success, and the report
always states what was left alone. Measured on a disposable folder: the preview left every file in place
(exit 0), `--yes` removed exactly the four derived files and left a foreign file beside them, and a second
run reported nothing to remove without creating anything. The `logs` folder is the one directory the module
derives rather than receives, so it is checked as well: when it is a symbolic link, the logs inside it are
left alone and the report says why (D26 below), while the database named on the command line is still
removed — that path is the one the person chose.

### 4.8 Execution and submission are off

No email is sent, no calendar event is created in any account, no application is submitted: the execution
paths refuse unless a *local mock* is named, and the refusal is measured (`REFUSED: no calendar event was
recorded (disabled)`, exit 2). Typed previews are separate from execution, and a preview says so in its own
words. The mock cannot do real network work even in principle, because the child-process tests run it with
sockets blocked.

## 5. Out of scope, and why

- **An attacker running code as the person, or as root/administrator.** File permissions cannot stop this,
  and no local application can. Not defended.
- **Full-disk or file-level encryption.** Not implemented: the database is plain text on disk. The honest
  guidance is to keep it on an encrypted volume and to understand that a synchronised folder will copy it.
- **A compromised interpreter, Tk, or an optional third-party package.** The runtime dependency set is the
  standard library plus the optional `pypdf` for PDF import.
- **Physical access, backups of the whole machine, forensic recovery of deleted rows.** Deleting a record
  from SQLite does not scrub the pages it occupied; `VACUUM` is not run for this reason, and this document
  does not pretend otherwise.
- **Multi-user or server deployments.** There are none.

## 6. Residual risks to name

1. **No encryption at rest.** Files are 0600, which answers "another user account" but not "a copied file".
   This is the largest residual risk and remains open in `phases.md` Phase 2.
2. **Deletion is complete only where the names are derivable — narrowed 2026-10-16, not eliminated.**
   Records can each be deleted from the window, and `--forget-local-data --yes` now removes the database,
   its `-journal`/`-wal`/`-shm` sidecars, the snapshots and staged restores beside it, and the two logs it
   writes. What it still cannot remove is everything at a path the *person* chose: a backup written to
   another folder, a JSON export, an `.ics` file, a saved draft, a mock ledger. It reports that limit
   rather than implying the machine is clean, refuses to follow a symbolic link or a folder, and never
   walks a directory — so "everything is gone" is a statement about this application's own files, and the
   user's copies elsewhere remain their own to delete. `tests/test_cli_forget.py` asserts each of those
   refusals and that a foreign file in the same folder survives.
3. **Synchronised or shared folders.** Pointing `--database` at a synced folder hands the file to another
   service; the app cannot detect this and does not try to prevent it.
4. **Backup and export files travel.** An export warns about itself in its own contents
   (`Export may contain personal information; store securely.`) and holds no credentials — but it is a
   complete copy of the profile, listings and history, and it goes wherever the person sends it.
5. **Windows permission semantics.** Owner-only mode is applied where the platform supports it; on Windows
   the file inherits the ACL of its folder, and this project has no evidence about Windows ACL behaviour. Not
   claimed.
6. **No release/upgrade policy.** There is no published artefact, no signing and no update channel, so there
   is nothing to authenticate and nothing to keep up to date. Open in `phases.md` Phase 2.

## 7. Standing rules this model assumes

Keep discovery disabled until the source-quality gate passes with real permission evidence. Never store
credentials, tokens or personal data in logs, fixtures, tests or commits. Never transmit candidate data
anywhere as part of a test. Never weaken a refusal to make a check pass. If any of those change, this document
is out of date and the phase verdict with it.

## 8. What was measured while writing this (2026-10-16, Linux, CPython 3.11, synthetic data only)

All commands below ran against disposable synthetic databases in `/tmp`, with no network and no real personal
data. Exit codes are the process's own.

### 8.1 File modes

```
$ stat -c '%a %n' /tmp/probe3/*.sqlite3 /tmp/probe3/*.json /tmp/probe3/*.ics /tmp/probe3/draft.txt
600 …/b1.sqlite3   600 …/db3.sqlite3   600 …/exp.json   600 …/exp2.json
600 …/ledger.json  600 …/one.ics       600 …/two.ics    600 …/draft.txt
```

### 8.2 The storage boundary refusing to lie

```
$ python -m career_agent --database …/ics.db --follow-ups      # after a synthetic record was built
… 2026-10-13 (2 day(s) overdue): Probe Engineer at Example Instruments (synthetic) [discovered] …

# a new tracker record claiming a later status, through the same store the app uses:
ValueError: A new application record must start at discovered, not submitted_unverified; advance it with
ApplicationTracker.transition. Nothing was saved.
# …and one claiming confirmation without a transition:
ValueError: A new application record cannot claim candidate confirmation; confirmation requires a recorded
transition with evidence. Nothing was saved.
```

### 8.3 Destructive operations and repeats (each command run twice unless stated)

| What was run twice | Result |
| --- | --- |
| `--backup-to <new path>` | first: "Backup written and verified", exit 0; second: `REFUSED: A file already exists … Backups are never overwritten`, exit 2 |
| `--restore-from <same backup> --yes` | both exit 0; the kept copies are named `….backup-<stamp>` and `….backup-<stamp>-2`, so the second snapshot does not collide |
| `--seed-tasks` | both exit 0, "left scheduled-discovery, daily-backup, follow-up-digest exactly as they were"; `scheduled_task` stayed at 3 rows |
| `--import-from <same export> --yes` | first added 1 listing and created 1 record; second: "Nothing would be added … the stored record wins"; listings stayed at 1 |
| `--import-from` without `--yes` | preview only, listing count unchanged, nothing written |
| `--import-from` into a folder with no database yet | `REFUSED`-style explanation, exit 2, nothing created |
| `--calendar-to <same path>` | first wrote 1 VEVENT; second `REFUSED: … already exists. Choose another name`, exit 2 (two files written under different names differ only in `DTSTAMP`) |
| `--save-draft <same path>` | second `REFUSED: … already exists, so the draft was not written over it`, exit 2 |
| `--record-follow-up <id> --mock-ledger <same ledger>` | second: `[duplicate] This exact calendar operation was already performed at … Nothing was performed again`; ledger stayed at 1 operation |
| `--record-follow-up <id>` with no mock | `REFUSED: no calendar event was recorded (disabled)`, exit 2 |
| `--add-role` with identical arguments | second `REFUSED: You already have a record for … starting …`, exit 2; one row |

### 8.4 Five defects this pass fixed

D19 (restoring the database from itself was accepted) and D20 (a non-finite `--poll-seconds` was accepted and
made the worker poll with no delay, or die after starting). Both are written up with their regression tests in
[the cross-platform CI evidence register](cross-platform-desktop-ci-evidence-2026-10-15.md) sections 17 and 19.

D26 was found by probing `--forget-local-data` after it was written, and is the reason the paragraph above
names the derived folder. The module promises to refuse anything "reached through a symbolic link", and it
did refuse a candidate that *was* a link — but the `logs` folder it derives from the database path was not
checked, so a `logs` folder that was itself a link meant `<logs>/application.log` was deleted *through* the
link. The probe replaced the real `logs` folder with a link to another folder holding a file of that name:
the file was removed, and it had never been written by this application. The regression test
(`tests/test_cli_forget.py::ErasurePlanTests::test_a_logs_folder_that_is_itself_a_link_is_not_deleted_through`)
fails before the fix and passes after it; the fix excludes log candidates when that folder is a link, names
the folder in the report, and keeps removing the database the command was pointed at. The asymmetry is
deliberate and now stated in the module: the database's own folder is *not* checked this way, because the
person named that path and on some platforms an ordinary folder (`/tmp`, a home directory) is reached through
a link.

D27 and D28 are the same class of defect one step further out: the database's *name* was interpolated into a
glob pattern unescaped. A person may call their database `my[1].sqlite3`, and `[1]` is a character class to
`fnmatch`, so the pattern for the pre-restore snapshots matched `my1.sqlite3.backup-…` — a different
database's file, which `--forget-local-data` then listed **and deleted** — while failing to match this
database's own `my[1].sqlite3.backup-…`. That is both D27 (removal reaching a file it should not) and D28
(the counting half): `backup.automatic_backup_snapshots` used the same pattern, so it reported zero snapshots
however many were really there, and the `MAX_AUTOMATIC_SNAPSHOTS` refusal in `backup_snapshot` — the thing
that stops a schedule filling the disk — would never have been reached for such a name. Both are fixed by
escaping the name before it reaches the glob and keeping the literal prefix check beside it:
`tests/test_cli_forget.py::ErasurePlanTests::test_a_database_name_with_glob_characters_does_not_capture_another_files_snapshot`
and `...::test_a_snapshot_of_the_named_database_is_still_found`, plus
`tests/test_handlers.py::BackupSnapshotTests::test_a_database_name_with_glob_characters_still_finds_its_own_snapshots`
and `...::test_the_cap_refusal_also_holds_for_a_name_with_glob_characters`. Each fails before the fix and
passes after it — the second handler test fails by walking past the cap and trying to back up a file that is
not a database. The other glob in the tree belongs to the desktop harness and interpolates names the harness
wrote itself.

D29 was found by importing one export into a second database whose listing happened to use the same
identifier for different content - a hand-edited file, or two machines, is enough. Linking is decided by
`core.duplicate_key` (here, the listing URL), while the row is keyed by `listing_id` and `store.save_job` is
an upsert by that id, so a record that matched no stored identity but reused a stored identifier was planned
as new and then **replaced the stored listing's payload** - employer, URL and availability included - while
the command printed "Nothing was replaced: a listing or profile already stored wins over the file's copy."
Two records inside one file could do the same to each other, with the count claiming two listings had been
added when one was left. `plan_import` now refuses any record whose identifier is already stored under a
different identity, and any repeat of an identifier inside the file, naming the record and the reason;
`tests/test_importer.py::ImportTestCase::test_a_file_record_that_reuses_a_stored_identifier_is_refused_rather_than_written_over`
(before the fix the stored row came back as the file's copy) and
`...::test_two_records_in_one_file_with_the_same_identifier_do_not_overwrite_each_other` (before: the second
record won) are the regression tests. The refusal wording also changed from "Records that cannot be read" to
"Records that cannot be imported", because a refused identifier is readable - it simply cannot be used
without replacing something.

D30 was found by pointing each read-only command at a zero-byte file and comparing the file's digest before
and after. `--follow-ups`, `--worker-status`, `--next-actions`, `--interviews`, `--analytics`, `--history`,
`--export-to`, `--preview-calendar-export` and `--calendar-to` all checked `database.exists()`, and an empty
file exists: SQLite reads it as a valid empty database and **creates the schema inside it**, so each command
wrote 124 KB and an `application.log` beside a file the person named - and then printed its own line saying
that nothing had changed ("This report is read-only; nothing was changed, uploaded or sent to anybody").
`--doctor` already had the right answer for this file (exit 1, "empty (0 bytes)"), so the reports now use
the same rule: a missing path and a zero-byte file both mean there is no database to read, both are left
exactly as they are, and the sentence names the empty file. `tests/test_config.py::
ReadOnlyCommandsLeaveAnEmptyFileAloneTests` is the regression test - it fails before the fix because the
file grows from 0 bytes to a schema and no message mentions the empty file - and it also pins the other side
of the line, that `--seed-tasks` still creates the database it is asked for.

## 9. Verdict

The Phase 2 exit criterion "privacy/security boundaries are documented and enforced" is now documented on both
halves: enforcement is cited above test by test, and the residual risks are named rather than hidden. Phase 2
stays **Partially complete**: encryption at rest and a release/upgrade policy remain open, and this document
claims nothing about either.
