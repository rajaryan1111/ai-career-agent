# Release-readiness audit — 2026-10-15

What this document is: the repository half of the release rehearsal named as missing piece 3 in the README,
run on one Linux machine with the **installed wheel**, plus the CI coverage audit behind the matrix in
`.github/workflows/tests.yml`, plus the written version/data-compatibility policy that was missing piece 4
(its user-facing form lives in the README, under
[What a version number promises about your data](../README.md#what-a-version-number-promises-about-your-data)).

Every claim below is a command and its observed result from this run. Nothing here is a plan, a projection,
or a claim about a platform this rehearsal did not run on. It is **not** a statement that the application is
production-ready: there is no installer, no signed bundle, no published package, and the per-operating-system
half of the release checklist (a real desktop, macOS and Windows) still needs machines this project does not
have. `SOURCE_QUALITY_GATE_PASSED` remains `False` and live job discovery remains disabled; nothing in this
rehearsal enabled anything.

## 1. How this was rehearsed

| | |
|---|---|
| Machine | Linux 6.1.158+, non-root user (uid 1001), no display used |
| Interpreter | CPython 3.11.2 (the system interpreter), plus CPython 3.10–3.13 in CI |
| Revision | the working tree that this document was added to (`main` untouched; branch `arena/351e052d-ai-career-agent`, on top of `dc20325`) |
| Artefact | `ai_career_agent-0.1.0-py3-none-any.whl`, sha256 `cf681747d19e47aa5d02dbaf8ae5bb4fd5ac0e4eba8726de5e86fc61735d5c73`, 29 archive members (24 under `career_agent/`, 5 `dist-info` metadata files) — no `tests/`, no `scripts/` |
| Built by | `python -m build --wheel --outdir <outside the checkout>` in a separate virtual environment, then installed into a fresh one: `pip install <wheel>` |
| Data | synthetic only: one invented listing, one invented application record, invented employment and education records, in a disposable folder under `/tmp`. No real database, no real résumé, no candidate data, and the checkout was never the working directory of the rehearsal |
| Reproducibility note | the digest identifies the file this rehearsal used. A rebuild is not expected to produce identical bytes (setuptools records file timestamps in the archive), so treat the revision, not the digest, as the identity |

Installed package, as reported by `pip show ai-career-agent`: `Name: ai-career-agent`, `Version: 0.1.0`,
`Requires:` (empty — there is no required third-party dependency), with the `career-agent` console script
installed beside it. `career-agent --version` → `career-agent 0.1.0 (database schema version 6)`, exit 0.

## 2. Install, start and read back

**`--doctor` with no database at all** (exit 0, and nothing created):

```
Database: <home>/ai-career-agent/career_agent.sqlite3
          chosen by the default location
Data folder: not created yet; the app creates it on first run (<home>/ai-career-agent).
Database: no file yet, so there is nothing saved to check. The app creates it on first run.

No problems found. This report lists file locations, so remove them before sharing it.
```

`ls <home>` afterwards → `No such file or directory`. The read-only promise holds: no database, no folder,
no log file was created by the check.

**A database written by the installed copy, then read back.** The same interpreter that installed the wheel
wrote one listing (`j1`, "Data Engineer at Sandbox Systems"), one tracker with a follow-up day
(`today + 3 days`, note "ask about the panel"), one activity entry, one employment record and one education
record. Then:

| Command | Observed |
|---|---|
| `career-agent --database alpha.sqlite3 --doctor` | `readable, no profile · 1 job · 1 tracker record · 1 activity entry · schema version 6.` + `Every stored record could be decoded by this version.`, exit 0 |
| `--history` | employment and education sections, the "not a claim about experience" caveat, exit 0 |
| `--analytics` | the full progress report; rates withheld with their floor named ("1 recorded as sent"), the "What cannot be measured here" list present, exit 0 |
| `--next-actions` | `Nothing is due yet; 1 item(s) are coming up.` → the follow-up on `2026-10-18 (in 3 day(s))`, exit 0 |

## 3. Backup and restore

```
$ career-agent --database alpha.sqlite3 --backup-to alpha-backup.sqlite3
Backup written and verified: alpha-backup.sqlite3
Contents: no profile · 1 job · 1 tracker record · 1 activity entry · schema version 6
Owner-only where the file system supports POSIX permissions; not encrypted, so keep it private.
                                                                                     (exit 0)

$ career-agent --database alpha.sqlite3 --restore-from alpha-backup.sqlite3 --yes
Restored alpha.sqlite3
from     alpha-backup.sqlite3
Contents: no profile · 1 job · 1 tracker record · 1 activity entry · schema version 6
Previous database kept as a verified copy: alpha.sqlite3.backup-20261015T070454Z
Keep the previous-database copy until you have confirmed everything you need is present.
                                                                                     (exit 0)
```

The previous database was kept rather than deleted, the file exists (`ls` confirms), and a doctor run after
the restore reports the same contents with `Every stored record could be decoded by this version.`

## 4. Export and import

```
$ career-agent --database alpha.sqlite3 --export-to alpha.json
Wrote 1 listing(s) and the profile to alpha.json
This file may hold personal information. It was written owner-only where the file system
supports it, and nothing was sent anywhere.                                    (exit 0)
```

Importing that file into a *separate* database shows the plan before anything is written — the plan run
printed `Listings: 1 would be added.`, `Application records: 1 would be created at 'discovered'`,
`Follow-up days: 1 would be recorded as you set them.`, `Activity history: 1 entr(ies) would be appended`,
`Employment history: 1 record(s)…`, `Education: 1 record(s)…`, followed by
`Nothing was written. Run the same command with --yes to apply this plan.` (exit 0). With `--yes`:

```
Import complete: added 1 listing(s); created 1 application record(s); recorded 1 follow-up day(s);
added 1 employment record(s); added 1 education record(s); appended 1 activity entr(ies).
Nothing was replaced: a listing or profile already stored wins over the file's copy. Nothing was sent anywhere.
```

A doctor run on the target database then reports `1 job · 1 tracker record · 1 activity entry · schema
version 6`, and `--history` shows the imported employment and education records.

## 5. A real schema upgrade (5 → 6)

An earlier attempt at this rehearsal was invalid: the file it copied already recorded `user_version = 6`, so
no migration ran and no snapshot was taken. This run used a **genuine** schema-5 database, built the only
honest way available without an older release: by running this build's real migration steps and stopping at
version 5 (the same mechanism `tests/test_store.py` uses for its older-version fixtures).

```
$ python make_v5_fixture.py old2.sqlite3        # built with the installed package
fixture old2.sqlite3 written by the current build stopped at schema version 5
  jobs=[('j1',)] trackers=[('j1', 'discovered')] activity_entries=1
```

110592 bytes, 10 tables. `--doctor` on it, read-only:

```
Database: readable, no profile · 1 job · 1 tracker record · 1 activity entry · schema version 5.
          It was written by schema version 5; opening the app updates it to version 6 and records
          that step in the file.
          Its records are not decoded here: this check never changes the file, so the version check
          comes first.                                            (exit 0, file unchanged)
```

Then one ordinary read command opened it (`--analytics`, exit 0), and the file was inspected directly:

| Question | Answer |
|---|---|
| Schema version now | `user_version: 6` |
| Snapshot taken first | `old2.sqlite3.backup-20261015T070533Z`, 110592 bytes, `user_version: 5`, 10 tables — the pre-upgrade file, verified and kept |
| Listing survived | `j1 · Data Engineer at Sandbox Systems · open` |
| Tracker survived | `('j1', 'discovered', '2026-10-17', 'chase the reply')` |
| Activity survived | `('applied', '2026-10-15', 'recorded before the previous upgrade')` |
| Tables now | 11 (`application_activity`, `application_preparation`, `application_tracker`, `candidate_education`, `candidate_profile`, `candidate_work_history`, `interview_round`, `job_listings`, `scheduled_task`, `task_run`, `worker_lease`) |

`--doctor` afterwards reports schema version 6 and a clean record check; `--follow-ups` still lists the
follow-up day that the v5 file held.

## 6. Failure paths

All of these ran against the installed copy, with synthetic data. "Nothing was changed" statements were
verified by hashing the database file before and after.

| Situation | Command | Observed |
|---|---|---|
| No database yet | `--analytics --database missing.sqlite3` | exit 0, `No database yet, so nothing is recorded to add up.…`; the file was **not** created |
| Import file that is not JSON | `--import-from broken.json` | exit 2, `REFUSED: broken.json is not valid JSON (line 1, column 33: …). Nothing was read from it.` |
| Import file with no format version | `--import-from wrongshape.json` | exit 2, `REFUSED: … has no format_version, so this app cannot tell what wrote it.` |
| Export target that cannot be written | `--export-to readonly-folder/alpha.json` | exit 2, `REFUSED: … could not be opened for writing: Permission denied.` |
| Export target whose folder does not exist | `--export-to nowhere/alpha.json` | exit 2, `REFUSED: … could not be opened for writing: No such file or directory.` |
| Backup target that cannot be written | `--backup-to readonly-folder/alpha-backup.sqlite3` | exit 2, `REFUSED: … could not be opened for writing: Permission denied.` + `No backup was created.` |
| Backup file that is not a database | `--restore-from damaged-backup.sqlite3 --yes` | exit 2, `REFUSED: … is not a database this app can read (file is not a database). The restore did not complete.`; the live database hash is byte-identical before and after |
| A record this version cannot read | see section 7 | doctor exits 1 and names the record; reports that read it exit 2; reports that do not read it exit 0 |

**Finding, measured again on 2026-10-15: a read-only file *is* a write-refusal path, and it was worded as a
read failure.** With the database file at mode `444`, `--doctor` and `--follow-ups` still run (correct: both
are read-only), and the file's mode is restored to owner-only on open (`_restrict_to_owner`, best-effort,
POSIX-only) — observed again as `-r--r--r--` → `-rw-------`. This section first read that as "writes then
succeed". They do not: the connection was opened while the file was read-only, so a *writing* command fails
with SQLite's `attempt to write a readonly database`. Measured with no `chmod` in between, on the installed
console script: `--seed-tasks` run 1 exits 2 and refuses, leaving the file at `-rw-------`; run 2 exits 0 and
creates the schedule. The same reproduction holds for a database inside a folder the account cannot write
(mode `555`), and on a **read-only filesystem** — the case recorded here as unavailable, because a read-only
bind mount can now be arranged (2026-10-15):

| Situation | Command | Observed |
|---|---|---|
| Database on a read-only filesystem (bind mount, `ro`) | `--doctor` | exit **1**: the database is reported `readable … schema version 6`, and the one problem named is `start-up notes cannot be written to mnt/logs` — accurate, and worth knowing, because a start-up failure could not be recorded there |
| same | `--analytics`, `--follow-ups`, `--history` | exit 0, full reports |
| same | `--backup-to out/backup.sqlite3`, `--export-to out/export.json` | exit 0, `Backup written and verified`; writing *outside* the read-only location is unaffected |
| same | `--seed-tasks`, `--import-from … --yes` (a file with something to add) | exit 2, write refusal, nothing written |
| same | `--restore-from … --yes` | exit 2, `REFUSED: mnt/.career_agent.sqlite3.restore-….partial could not be opened for writing: Read-only file system. The restore did not complete.` |
| all of the above | — | the database file's sha256 is identical before and after every command, no `-journal`/`-wal` side file is left behind, and the mount is unmounted afterwards |

**The defect those runs found.** Every one of those write refusals was worded as a *read* failure:
`REFUSED: this database file could not be read, so nothing was reported: attempt to write a readonly
database`, followed by advice to restore a verified backup *over the file* — a read described for a write,
damage that is not there, and a remedy that would have failed in exactly the same way. Nothing was ever
written by mistake (exit status 2, byte-identical file), so the harm was entirely in the sentence. Fixed in
`career_agent/__main__.py`: `looks_like_a_write_failure()` keeps SQLite's write-side words (`attempt to write
a readonly database`, `unable to open database file`, `database is locked`, `read-only file system`) on their
own sentence — *"this database could not be written to, so nothing was changed"*, naming the read-only
file/folder, missing-folder and lock possibilities — while read failures keep theirs. The refusal helper is
now `_refuse_database_problem`, because it words three cases rather than one. Reproduced before the fix on a
read-only filesystem (four writing commands, transcript in
[`cross-platform-desktop-ci-evidence-2026-10-15.md`](cross-platform-desktop-ci-evidence-2026-10-15.md)) and
covered after it by `tests/test_damaged_records.WriteRefusalTests`: a read-only file, a folder that cannot be
written, the read failures that must not be re-worded, and the write permission coming back as the whole fix.

## 7. The defect this audit found, and the fix

The rehearsal's first failure probe built a database whose stored tracker status was a value no version of
the application knows (`sent-somewhere` — the equivalent of a hand-edited value, or a file from a later
build). The application refuses such a record by design, and it refused it here: but the *reports* handled
it three different ways, and the doctor got it wrong. Before the fix, on the same database:

| Command | Before | After |
|---|---|---|
| `--doctor` | **exit 0**, `No problems found.` — while every read path refused the same file | **exit 1**, `PROBLEM: 1 stored record(s) cannot be read by this version… - The saved status 'sent-somewhere' is not one this version of the application recognises… (in the 'application_tracker' table, record 'j1')` |
| `--analytics` | **exit 3** (unexpected failure), a sanitised start-up note written to `logs/startup-diagnostics.log` | **exit 2** (`EXIT_REFUSED`), `REFUSED: this database holds a record this version cannot read: …` + `Nothing was changed or repaired. --doctor reports which record it is…` |
| `--follow-ups` | **exit 3**, same shape | **exit 2**, same sanitised refusal |
| `--history` | exit 0 (it does not read tracker records) | exit 0, unchanged |

The database file's sha256 was identical before and after every command, including the doctor
(`8c085d0c…` in the probe copy), so nothing was repaired, rewritten or migrated.

Fix, in the same shape the codebase already uses:

- `career_agent/store.py` gains `unreadable_stored_records(path)`: it decodes every stored record through
  the **same decoder functions the read paths use** (profile, listing, tracker, activity, preparation,
  interview, work history, education, tasks, runs, leases), over a `mode=ro` connection, capped at 5000 rows
  per table, and returns one sentence per unreadable record. It creates nothing, migrates nothing, and reuses
  the backup module's read-only URI helper rather than a second implementation of one. The row decoders
  became `@staticmethod`s with a shared `_decode_profile`, so nothing about their rules was copied.
- `career_agent/__main__.py` runs that sweep from `--doctor` once the structural check is clean, and
  `--analytics`, `--follow-ups`, `--next-actions`, `--interviews`, `--history` and `--worker-status` answer a
  refused record with `_refuse_unreadable_records`: one clear sentence, exit `2`, nothing half-printed, and a
  pointer at `--doctor`. A file that records an **older** schema is version-checked first and its records are
  not decoded, deliberately: the doctor never writes, so it cannot migrate the file, and decoding an
  old-layout payload could report a problem that opening the app would resolve. `--doctor` says exactly that
  instead of implying the data is fine.
- Tests: `tests/test_damaged_records.py` (18 tests) pins the before/after behaviour — the scan on a healthy
  database of every record kind, a damaged status, a payload this build cannot use, an unknown activity kind,
  only the damaged record being named, a missing file, byte-for-byte non-modification, an older schema left at
  its own version, the doctor's exit codes and its naming of the record, the refusal status of the read-only
  reports, and that the reports which do not read the record still run. Reverting `career_agent/store.py` and
  `career_agent/__main__.py` to `dc20325` was executed to confirm the new file fails without the fix
  (`ImportError: cannot import name 'unreadable_stored_records'`), and the two exit-code claims above were
  re-measured pre-fix and post-fix on the same database.

Known limit, stated rather than hidden: the doctor decodes records only for a file whose schema version is
the current one. A file that is *both* older and damaged reports as "written by schema version N; opening the
app updates it" with exit 0; the damaged record is reported on the next run, after the app has upgraded it.
The alternative — decoding an older layout — would report problems that the upgrade itself fixes.

Related behaviour confirmed in the same probe: **the export still takes the data out** of a damaged database.
`--export-to` succeeded (exit 0) and marked the value it cannot label:

```json
"application_tracker": {
  "status": "sent-somewhere", "status_evidence": null, "candidate_confirmed": false,
  "updated_at": "2026-10-15T07:04:53+00:00", "follow_up_on": "2026-10-18",
  "follow_up_note": "ask about the panel", "status_recognised": false
}
```

**Found later, by the manual acceptance run.** Executing the checklist on 2026-10-15 turned up four more
defects, three of them in this same neighbourhood: a progress figure that counted a round nobody had attended,
four commands that reported a readable database holding one unreadable record as a start-up that failed (exit
3, with a start-up note), an import that wrote part of the file and then refused while saying nothing had been
written, and a refusal that claimed a draft had been written when nothing was on disk. Each is diagnosed, fixed
and regression-tested in
[`local-alpha-manual-acceptance-run-2026-10-15.md`](local-alpha-manual-acceptance-run-2026-10-15.md) section 5.
The refusal this section describes now reaches *every* command, not only the read-only reports, and the import
sweeps its target read-only before it writes anything.

## 8. CI coverage audit

The workflow runs five jobs across Linux, Windows and macOS. What they cover, and why (the platform legs were
added on 2026-10-15):

| Job | Matrix | What it proves |
|---|---|---|
| `unit-tests` | Ubuntu, Python 3.10, 3.11, 3.12, 3.13 | the suite passes on the floor `pyproject.toml` declares and on the newest interpreter it has been run on; `compileall` over `career_agent/`, `scripts/`, `tests/`; the source-CSV integrity audit |
| `installed-package` | Ubuntu, Python 3.10 and 3.13 | `python -m build --wheel`, `pip install dist/*.whl` into a clean environment, then `career-agent --version`, `--doctor`, `--database` run **from outside the checkout** — the same strings `tests/test_packaging.py` requires, so a wheel, a console script or a build backend that only works on the interpreter that built it fails CI |
| `desktop-smoke-linux` | Ubuntu, system interpreter, `xvfb` + `python3-tk` | the scripted desktop entry point run twice: with no display it must exit 2 and print `RESULT: BLOCKED` (and must not print a pass), and under a real virtual display it must exit 0 — so a runner that cannot show a window can never be counted as covering one. Then it checks that the run left no window, database or temporary folder behind |
| `pdf-extra` | Ubuntu, Python 3.13 | the optional `[pdf]` extra is what unlocks the résumé tests, in both directions: without `pypdf` the PDF cases skip, and with it installed the same module finishes with a bare `OK` |
| `cross-platform` | Windows and macOS, Python 3.10 and 3.13 | the full suite on a real Windows and a real macOS runner; `compileall`; the CSV audit; the résumé tests with the extra installed (no skips); a wheel built and installed into a virtual environment **outside the checkout** with the import path asserted; then the installed command surface — `--version`, `--doctor` on a missing database (exit 0, `no file yet`) and on a file that is not one (exit 1 for the doctor, exit 2 for a read-only report, file byte-identical), schema creation with all eleven tables, cross-process persistence, a backup/restore that really replaces data, a JSON export imported into a second database, the two discovery invariants, a minimal Tk widget lifecycle, and the desktop smoke test |

Decisions behind the matrix:

- The range in `requires-python` stays open-ended (`>=3.10`), while the range *tested* is closed and named.
  A version nobody has run is not described as supported; the README's packaging section says which
  interpreters were actually exercised.
- 3.13 is the newest leg because it is the newest interpreter the suite has been run on. An attempt to obtain
  3.13 (and 3.14) in this environment failed — `uv python install 3.13` and a direct download from the
  `python-build-standalone` releases were both blocked by the sandbox's network policy (`UnknownIssuer` /
  `SSL_ERROR_SYSCALL`) — so the newest leg can only be proven by CI. No 3.14 leg exists, and none is claimed.
- `tests/test_documented_commands.py` reads every `--flag` this README and the manual smoke-test checklist
  tell a person to run and looks it up in the real `--help` output, so a documented command that no longer
  exists fails the suite. Current state: README 30 flags, checklist 21 flags, 0 unknown in either. (This
  line read "checklist 20" when it was written; re-counted on 2026-10-15 while executing the checklist, which
  is 21 either way — the document is what changed, not the count of flags in it.)
- **What CI still does not cover, and therefore does not let this document claim:** pixel rendering, layout,
  dialog wording, accessibility, native look-and-feel, code signing, installers, or a person using the window.
  macOS and Windows *are* now covered for the suite, the installed command surface and a minimal Tk widget
  lifecycle, and a runner without a display session reports BLOCKED for the window itself rather than passing.
  The manual campaign's non-GUI half has been executed and is recorded in
  [`local-alpha-manual-acceptance-run-2026-10-15.md`](local-alpha-manual-acceptance-run-2026-10-15.md); the
  window items are still unrun, and the checklist itself carries the per-step state. The results of the new
  platform legs are recorded in
  [`cross-platform-desktop-ci-evidence-2026-10-15.md`](cross-platform-desktop-ci-evidence-2026-10-15.md).

### 8.1 Phase 3 of the platform work — the Windows-first-failure states, each with its evidence

The Windows legs were not written and then declared working: they were run, and each run exposed a different
state of the same two problems. The sequence is kept because the numbers are the evidence that the fixes
addressed what was actually failing rather than what was expected to.

| Phase | State observed | Evidence | What changed |
|---|---|---|---|
| 3.1 — first exposure | **949 errors**, essentially one cause: every `CareerStore` construction failed, because the owner-only helper looked up `os.fchmod` (absent on Windows) and treated the result as a reason to refuse the write; the open descriptor leaked with it | runs 38706620081 and 38708232458, job annotations for the Windows legs | the helper reports success where there is nothing to apply and still refuses on POSIX (`career_agent/store.py`); `tests/test_store.PlatformWithoutPosixModeBitsTests` holds the writing paths on a platform without mode bits |
| 3.2 — after that fix | the suite ran, and failed in **four** places on both Windows legs, identically: two mode-verification tests, the swap-write test, and the child-suite leak watch cascading from them | run 38711721472 (`b04ad90`), inventory annotation: `4 distinct failures recorded :: FAIL: test_a_write_attempted_during_the_swap…, FAIL: test_the_suite_leaves_no_sqlite_connection_open, FAIL: test_require_owner_only_reports_a_file_that_cannot_be_protected, FAIL: test_a_filesystem_that_ignores_the_mode_leaves_no_readable_export` | the mode-verification tests skip where there are no mode bits to verify, the swap test asserts the platform's stated release window instead of failing on it, and the platform assumptions in the other test families (flags, path spellings, mode bits, folder cleanup) were corrected |
| 3.3 — after those | **green**: 12 jobs, both Windows legs and both macOS legs among them | run 38713190679 (`f38ac49`), every job `success` | — |

A step that is not recorded is a step whose failure cannot be diagnosed from the network this project develops
on, and the third phase's evidence is only readable because the runs before it fixed that: every step now
records its output into one notes file, and `scripts/ci_annotate.py` publishes the failing test names, ten
tracebacks and, on a green run, the suite's counts. See
[`cross-platform-desktop-ci-evidence-2026-10-15.md`](cross-platform-desktop-ci-evidence-2026-10-15.md).

### 8.2 The macOS side, as its own evidence line

Both macOS legs failed step 10 (`Build a wheel and install it into a virtual environment outside the
checkout`) on two consecutive runs while their own suites passed (`Ran 1597 tests … OK`), and the step was the
one step whose output was not recorded — so nothing about it could be read from this side of the network.
Recorded and reproduced on Linux, the cause was the step's working directory: `python -` put the checkout at
the head of the import path, so the checkout satisfied the assertion about the *installed* copy. The wheel is
now built into a temporary directory, installed and inspected from there, and the assertion is unchanged.
Reproduction transcripts and the local dry run of the whole job body (14 steps, no failures, wheel imported
from `…/venv/lib/python3.11/site-packages/…`) are in
[`cross-platform-desktop-ci-evidence-2026-10-15.md`](cross-platform-desktop-ci-evidence-2026-10-15.md).

## 9. Version and data-compatibility policy

Written in user-facing form in the README (section "What a version number promises about your data"), and
summarised here with the evidence this audit produced:

1. **No released build exists**, so `career_agent.__version__` names a development build of the same local
   alpha and promises **no stability**: any version may change the schema.
2. **A newer build opens an older database; an older build refuses a newer one.** The schema version is
   recorded in the file (`PRAGMA user_version`) and printed by `--version` and `--doctor`. Section 5 is the
   measured upgrade; a newer file is refused rather than partially read (covered by `tests/test_store.py`).
3. **An existing file is copied before it is changed**, through the same verified, owner-only backup path,
   with the snapshot's own version in its name (section 5). A copy that cannot be written stops the upgrade.
4. **Steps are additive, one transaction each**, and only ever appended; a failed step leaves the file at the
   version it reached and says so.
5. **Backups are accepted across versions** (validated against the tables their version declared) and are
   upgraded when opened; a newer file is refused.
6. **Export documents carry `format_version`**, an unknown version is refused with that reason, and import
   never overwrites a stored listing or profile — the plan says which status is *not* imported when the file
   holds one this build cannot assume was reached.
7. **An unreadable record is reported, never repaired** — on the read paths, in the export (marked) and now
   in `--doctor` (section 7).
8. **There is no downgrade path and no automatic update mechanism.** Upgrading means installing the newer
   build and opening the file; downgrading means restoring a backup taken before the upgrade.

## 10. What remains missing (the honest list)

1. Per-platform launch artefacts, signing and notarisation (macOS `.app`, Windows installer).
2. A decision on bundling the interpreter versus requiring a system Python with Tkinter.
3. The per-operating-system half of this rehearsal: a backup/restore and doctor pass on a real macOS and
   Windows desktop from a packaged build. Nothing in this document speaks for either.
4. Real GUI coverage: the manual smoke-test checklist's desktop items are still unrun; automated tests use
   widget stubs and are not GUI tests. The checklist's non-GUI half *has* been executed (22 steps passed, 76
   blocked for the missing display, four defects found and fixed) — see the acceptance run linked in section 7.
   A scripted smoke entry point now also builds and drives the real window where a display exists
   (`scripts/desktop_smoke_test.py`, run under Xvfb for Linux in CI); that is window construction and
   programmatic interaction with a real Tk, not a person using it, so no checklist step moved to PASS.
5. **Partly closed (2026-10-15).** Windows and macOS legs run the suite, the installed-command rehearsal and
   a minimal Tk lifecycle, and a display-backed Linux leg runs the scripted desktop smoke test. The matrix is
   green as of run 38713190679 (`f38ac49`, 12 jobs), and the three states the Windows legs passed through on
   the way there are recorded in section 8.1. Still missing: a CI leg for Python 3.14 (no interpreter here has
   been able to run it), the same rehearsal from a *packaged* build on each operating system, and any human GUI
   session. **Corrected the same day (runs 38716978550 and 38719357147):** the widget-lifecycle step's
   BLOCKED was a defect in that check, not a limit of the runners - it had never imported `tkinter.ttk`, and
   its report broke macOS's bash 3.2 - so both windows checks now pass on the Windows and macOS legs
   (`PASS: Tk 8.6 built a root, a frame and a label and updated them`; `RESULT: PASS — 14 checks passed`). The
   two defects are D11 and D12 in
   [`cross-platform-desktop-ci-evidence-2026-10-15.md`](cross-platform-desktop-ci-evidence-2026-10-15.md)
   section 9; what these legs still do not claim is a person using the window, or a packaged build.
6. **Closed (2026-10-15).** A read-only filesystem can now be arranged here with a bind mount, and section 6
   records what it measured — including the write-refusal wording defect that case exposed.
7. Branch protection, a signed tag and a release archive: none exist, and no package has been published.

## 11. Reproducing this rehearsal

Outside the checkout, with a built wheel:

```bash
python -m venv /tmp/rel-build && /tmp/rel-build/bin/pip install --quiet build
/tmp/rel-build/bin/python -m build --wheel --outdir /tmp/rel-dist /path/to/checkout
python -m venv /tmp/rel-venv && /tmp/rel-venv/bin/pip install --quiet /tmp/rel-dist/*.whl
mkdir -p /tmp/rel-work && cd /tmp/rel-work
export CAREER_AGENT_HOME=/tmp/rel-work/home
/tmp/rel-venv/bin/career-agent --version
/tmp/rel-venv/bin/career-agent --doctor
```

The section transcripts above are plain command/output pairs from that setup, with one extra script for the
schema-5 fixture (section 5) and one SQL update to damage a single stored status (sections 6–7). Everything
ran under `/tmp`; the candidate's own database was never opened, and no test in this document touched the
repository's working tree.
