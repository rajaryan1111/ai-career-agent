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

**Finding: a read-only database file is not a write-refusal path.** With the database file at mode `444`,
`--doctor` and `--follow-ups` still run (correct: both are read-only), and the file's mode was observed
changing from `-r--r--r--` to `-rw-------` on open — the store re-applies owner-only permissions to its own
database every time it opens it (`_restrict_to_owner`, best-effort, POSIX-only). Writes then succeed, so a
"read-only file" does not produce a refusal here; the refusal paths that exist are around *targets*
(backup/export destinations, section 6) and around damaged files. This is a deliberate privacy measure with
a documented side effect, not an accident, and it is recorded here because the opposite behaviour was
expected when the probe was written. A filesystem-mounted read-only database, or a directory the process
cannot write, was not available on this machine to exercise the remaining case.

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

The workflow runs three jobs on `ubuntu-latest` only. What it covers, and why:

| Job | Matrix | What it proves |
|---|---|---|
| `unit-tests` | Python 3.10, 3.11, 3.12, 3.13 | the suite passes on the floor `pyproject.toml` declares and on the newest interpreter it has been run on; `compileall` over `career_agent/`, `scripts/`, `tests/`; the source-CSV integrity audit |
| `installed-package` | Python 3.10 and 3.13 | `python -m build --wheel`, `pip install dist/*.whl` into a clean environment, then `career-agent --version`, `--doctor`, `--database` run **from outside the checkout** — the same strings `tests/test_packaging.py` requires, so a wheel, a console script or a build backend that only works on the interpreter that built it fails CI |

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
- Not covered by CI, and therefore not claimed anywhere: real Tk rendering, window behaviour, macOS or
  Windows behaviour, code signing, or anything requiring a display. The manual campaign's non-GUI half has
  since been executed and is recorded in
  [`local-alpha-manual-acceptance-run-2026-10-15.md`](local-alpha-manual-acceptance-run-2026-10-15.md); the
  window items are still unrun, and the checklist itself carries the per-step state.

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
5. A CI leg for Python 3.14, and a macOS/Windows CI leg (this repository runs only on `ubuntu-latest`).
6. The read-only-*filesystem* case from section 6, which needs a machine where a read-only mount can be
   arranged.
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
