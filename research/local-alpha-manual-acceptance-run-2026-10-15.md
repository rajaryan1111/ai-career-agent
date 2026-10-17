# Local Alpha Manual Acceptance Run — 2026-10-15

**What this is.** The execution record of the 98-step manual smoke-test checklist
([`local-alpha-manual-smoke-test-checklist-2026-10-14.md`](local-alpha-manual-smoke-test-checklist-2026-10-14.md))
on the one machine this project has: a headless Linux sandbox, CPython 3.11.2.

**What this is not.** It is not desktop acceptance. There is no display and no Tkinter in this environment, so
every step that needs the window is recorded **BLOCKED**, naming the missing capability. No GUI result is
inferred from a unit test, and no macOS or Windows behaviour is claimed. Nothing here says the alpha is
verified: the checklist's own release rule is untouched.

**Revision scope.** Sections 1-8 record the run and its revision as they stood at that time (the suite is
quoted at 1559 tests, and the harness at 38 then 46 checks). Later sections are dated and carry the numbers
of their own runs; the current totals are in `phases.md` and the newest per-leg table is section 15 of the
cross-platform evidence file.

**Tester / date.** An agent-operated acceptance run, 2026-10-15, on branch `arena/351e052d-ai-career-agent`.
Every status below is backed by a command that was run and its observed output; where a status is PASS, the
command and result are in the Evidence column, and where the evidence is a test that the *same* behaviour was
already covered automatically, the status is still BLOCKED unless the step itself was executed.

---

## 1. Environment and revision

| Item | Value |
| --- | --- |
| Operating system | Linux (sandbox container), kernel `6.1.158+` |
| Interpreter | CPython **3.11.2** (`python3 -V`) |
| Display | `DISPLAY` unset |
| Tkinter | **absent** — `import tkinter` → `ModuleNotFoundError: No module named 'tkinter'` |
| X tooling | no `Xvfb`, `xvfb-run`, `xdotool`, `wmctrl` |
| SQLite CLI | absent (`sqlite3`); the checklist's copy-editing steps were done with Python's `sqlite3` module |
| Revision under test | the working tree that became commit `a74b722` on this branch; the four fixes below were made *during* the run, and every step a fix touched was re-run against the corrected build (batch 3) |
| Installed build under test | wheel built from that tree, installed into a throwaway virtual environment |
| Wheel contents | 29 files: 24 `career_agent/*.py`, 5 `dist-info`; **no** `tests/` or `scripts/` |
| Console script | `career-agent 0.1.0 (database schema version 6)` |
| Data folder | `/home/user/.local/share/ai-career-agent` — created by nothing in this run, still absent afterwards |
| Data used | synthetic fixtures only, in throwaway folders under `/tmp`; every database disposable |

**The wheel hash is not stable across builds, and that is measured, not assumed.** Two builds from the same
tree produced `2d872ea6…` and `2f9ebd51…`; every archived entry's *content* was identical, and the only
difference was the timestamp each `dist-info` file was given. A wheel hash identifies one build, not one
source revision.

---

## 2. How the run was executed

Four transcripts were produced, each with the command and its own exit code captured explicitly (a
`command | head` would report `head`'s status, so nothing in this report comes from a pipeline's status):

1. **Batch 1** — preconditions, the network scan, fixture creation, the terminal backup/restore/repo-clean
   steps.
2. **Batch 2** — sources, follow-ups, export/import, history, analytics, integrations, the damaged-database
   steps, and the first pass at the email/calendar refusals.
3. **Batch 3** — the same later steps re-run against the corrected build, plus the damaged-database and import
   cases that produced defects D1–D3.
4. **Behaviour probes** — 48 assertions driving the domain and storage layer directly (the layer the window
   dialogs act on) for the steps whose *data* half is checkable without a display, each printing what it
   observed.
5. **Extra CLI probes** — the restore-from-a-non-database refusal, and backup → change → restore → read back.

Fixtures: two listings in one database, one profile, one application record walked through the real
transition table to `submitted_unverified`, a follow-up day three days out, an `applied` activity, one overdue
and one undated preparation item, one screening round scheduled for tomorrow, one employment and one
education record. Damaged copies were made **only** of those throwaway files, by editing the copy with
`UPDATE application_tracker SET status = 'sent-somewhere'` statements through Python's `sqlite3` module. The real candidate database was never opened: the application-data folder does not exist on this
machine.

---

## 3. Step-by-step results

### Preconditions

| Step | Status | Evidence |
| --- | --- | --- |
| Python 3.10+ | **PASS** | `python3 -V` → `Python 3.11.2` |
| Tkinter available | **BLOCKED** | `import tkinter` → `ModuleNotFoundError`; `DISPLAY` unset. This is the capability whose absence blocks every window step below |
| `python -m career_agent --version` | **PASS** | `python -m career_agent 0.1.0 (database schema version 6)`, exit 0, with no display variables set |
| `python -m unittest discover -s tests -v` | **PASS** | `Ran 1559 tests` … `OK (skipped=13)` — 12 PDF tests (optional `pypdf` not installed) and the installed-package test (source checkout) |
| `python -m compileall -q career_agent scripts tests` | **PASS** | exit 0, no output |
| `python scripts/audit_job_source_csv.py` | **PASS** | JSON report, `input_sha256 0356b093…`, 83 records, exit 0 |
| Throwaway copy for destructive steps | **PASS** | all destructive work on synthetic copies under `/tmp`; `/home/user/.local/share/ai-career-agent` still absent at the end |

### Desktop workflow (1–23)

| Step | Status | Evidence |
| --- | --- | --- |
| 1 window opens | **BLOCKED** | no display/Tkinter. The modules the window is built from import and run headlessly (suite, `--doctor`) |
| 2 database path in the per-user folder | **BLOCKED** | window display blocked; the *rule* is observable: `--doctor` prints the resolved path and which rule chose it |
| 3 profile entry and persistence | **BLOCKED** | window blocked; data half PASS — profile saved, store closed, reopened, read back identical |
| 4 two URL fields stay separate | **BLOCKED** | window blocked; data half PASS — source URL kept, employer apply URL still blank after reopen |
| 5 open listing, no evidence → UNKNOWN, shortlisting blocked | **BLOCKED** | window blocked; rule PASS — evaluation returns `unknown`, `can_be_ranked_as_eligible` false |
| 6 PASS only when every hard requirement passes | **BLOCKED** | window blocked; rule PASS — `pass` with evidence and matching requirements |
| 7 allowed country excludes candidate → FAIL | **BLOCKED** | window blocked; rule PASS — `fail`, country requirement fails |
| 8 work authorization UNKNOWN/PASS/FAIL, no fuzzy matching | **BLOCKED** | window blocked; rule PASS — missing → `unknown`, exact match → `pass`, mismatch → `fail` |
| 9 missing mandatory value → never PASS | **BLOCKED** | window blocked; rule PASS — missing discipline and missing cohort both stay out of `pass` |
| 10 shortlist gate | **BLOCKED** | the gate lives in the window's `_shortlist` handler; the transition table and the eligibility answer it consults were both verified (steps 5/7/11) |
| 11 invalid transition refused, status unchanged | **BLOCKED** | window blocked; rule PASS — `discovered → confirmed` refused, stored status unchanged |
| 12 confirmation rules (four cases, assertion, preservation) | **BLOCKED** | window blocked; rules PASS — `None`, the dialog's own guidance text, an instructional sentence and `<placeholder>` are all rejected; a real observation is accepted; `candidate_confirmed` is stored and survives the move to `response_received` |
| 13 export to a user-chosen JSON file | **BLOCKED** | the window's warning is blocked; the CLI half PASS — `--export-to` wrote the file with the privacy sentence, and the file's contents were inspected in step 57/78 |
| 14 delete a job and its tracker; delete the profile | **BLOCKED** | window blocked; data half PASS — deleting a job removes its tracker row; deleting the profile removes employment and education records and leaves the listings |
| 15 no network access | **PASS** | the five `tests/test_local_only.py` checks, including a child interpreter whose `socket` creation is blocked: `--version`, `--doctor`, `--analytics`, `--sources`, `--integration-status` all exit 0; a shipped-code scan finds only `urllib.parse` and the literal-host inspection in `career_agent/urls.py` |
| 16 close and reopen after a forced close | **BLOCKED** | window blocked; data half PASS — the file is readable after a close/reopen cycle and the records are unchanged |
| 17 Data safety back up, owner-only, existing file refused | **BLOCKED** | window blocked; CLI half PASS — "Backup written and verified", and a second backup to the same path is REFUSED with the first file's digest unchanged |
| 18 back up again to the same path | **BLOCKED** | window blocked; CLI half PASS — refusal with the earlier file byte-identical |
| 19 restore with a confirmation, snapshot kept beside the database | **BLOCKED** | window blocked; CLI half PASS — after `--restore-from … --yes` the older data is back and `restore-src.sqlite3.backup-20261015T073808Z` (126976 B, `-rw-------`) was kept |
| 20 close and reopen after the restore | **BLOCKED** | window blocked; CLI half PASS — the restored file reads back with only the pre-backup records (the role added afterwards is gone) |
| 21 restore from a file that is not a database | **BLOCKED** | window blocked; CLI half PASS — `REFUSED: notadb.sqlite3 is not a database this app can read (file is not a database).` exit 2, and the database was unchanged |
| 22 terminal backup/restore | **PASS** | `--backup-to` written and verified; the second refused (exit 2, digest unchanged); `--restore-from … --yes` exit 0 with the timestamped copy kept |
| 23 repository stays clean | **PASS** | `git status --porcelain` → 0 lines after the batch, and again at the end of batch 3 |

### Résumé import (24–31)

| Step | Status | Evidence |
| --- | --- | --- |
| 24–31 (proposal rows, scrolling, Escape/Cancel, selections, scanned PDF, DOCX table, damaged PDF, file unchanged) | **BLOCKED** | window/Tkinter absent, and the optional `pypdf` extra is not installed in the acceptance environment, so the PDF path could not be executed either (the 12 `tests/test_resume.py` cases skip with "the optional pypdf package is not installed"). No part of this group was simulated |

### Status, record times and diagnostics (32–41)

| Step | Status | Evidence |
| --- | --- | --- |
| 32 a new record offers only its own starting states | **BLOCKED** | window blocked; rule PASS — from `discovered` the chooser offers `discovered`, `shortlisted`, `withdrawn` and nothing later |
| 33 shortlist → prepared and the later choices | **BLOCKED** | window blocked; rule PASS — from `submission_attempted` the chooser offers the sent/confirmed/failed/unknown states only |
| 34 close a record honestly (withdrawn) | **BLOCKED** | window blocked; rule PASS — from `withdrawn` only `withdrawn` is offered |
| 35 Escape and Return on the dialog | **BLOCKED** | window blocked |
| 36 record times in the detail pane | **BLOCKED** | window blocked; data half PASS — `get_record_times` returns first/last and re-saving the listing leaves both unchanged |
| 37 start the app on a damaged database | **BLOCKED** | window blocked; CLI halves PASS — `--doctor` exits 1 with `PROBLEM: 1 stored record(s) cannot be read by this version`, naming `application_tracker` and record `'j1'`; the read-only reports exit 2 |
| 38 the diagnostic note is replaced, not appended | **BLOCKED** | window blocked; the note path was observed in this run: a start-up failure wrote `logs/startup-diagnostics.log`, and after defect D2 was fixed a refusal writes **no** note at all |
| 39 an unknown status in a throwaway copy | **BLOCKED** | window blocked; data half PASS — the record is refused with `TrackerStatusError` rather than crashing a list, the profile and other records still load, and the row is byte-identical in `sqlite3` before and after |
| 40 a damaged payload in a throwaway copy | **BLOCKED** | window blocked; data half PASS — refused with `StoredRecordError`, the profile still loads from the same file, and the file is byte-identical afterwards |
| 41 database inside a folder that does not exist | **BLOCKED** | window blocked; CLI half PASS — `--analytics` says there is no database yet and creates nothing; `--doctor` adds that the folder will be created as well |

### Follow-ups, matching, sources and the worker (42–52)

| Step | Status | Evidence |
| --- | --- | --- |
| 42 Follow-ups tab explains what a follow-up is | **BLOCKED** | the tab is a window; the same wording is what `--follow-ups` and the README print (read in step 50) |
| 43 set a follow-up day | **BLOCKED** | window blocked; data half PASS — the day and note are stored and `--follow-ups` lists them as `2026-10-18 (in 3 day(s)): Data Engineer at Sandbox Systems [discovered] - ask about the panel` |
| 44 a past day sorts above a future one | **BLOCKED** | window blocked; data half PASS — with one follow-up two days overdue and one five days out, the terminal list led with `1 overdue: 1 application(s) need a look.` and printed `2026-10-13 (2 day(s) overdue)` above `2026-10-20 (in 5 day(s))` |
| 45 "next tuesday" refused | **BLOCKED** | window blocked; the same date shape (`ACTIVITY_DATE_PATTERN`, the pattern `_history_day` uses) rejects it with the stored day unchanged |
| 46 clear the follow-up, decline then confirm | **BLOCKED** | window blocked; data half PASS — clearing removes the day and the note and leaves the status and the activity list alone |
| 47 export to a calendar file and import it into a real calendar | **BLOCKED** | the calendar application is not present in this environment; the file half PASS — 637 B, mode `-rw-------`, one `UID`, no `ATTENDEE`/`ORGANIZER`/URL line, and an existing file is never overwritten (`REFUSED: follow-ups.ics already exists.`) |
| 48 the Evaluate report | **BLOCKED** | window blocked; the report's data is assembled from the same calls: 6 factor lines, the disclaimer sentence, an overlap and a coverage figure |
| 49 `--sources` | **PASS** | gate NOT passed, "Sources permitted to run discovery now: none.", each source's state and conditions printed, every source "applying for jobs here: not permitted", "Adapters built into this version: 0" |
| 50 `--follow-ups` and `--calendar-to` | **PASS** | one follow-up listed with its day and note; the `.ics` written owner-only (627 B, `-rw-------`); a second run REFUSED with the first file byte-identical |
| 51 Background tasks tab lists three tasks | **BLOCKED** | window blocked; data half PASS — `daily-backup` 23:30, `follow-up-digest` 09:00, `scheduled-discovery` 00:00 and 12:00, all Asia/Kolkata |
| 52 pause asks first; a paused task does not run; history shows earlier runs | **BLOCKED** | window blocked; data half PASS — a task saved paused reads `enabled=False` with its times and history intact |

### JSON export and import (53–60)

| Step | Status | Evidence |
| --- | --- | --- |
| 53 Data safety export on a disposable database | **BLOCKED** | window blocked; CLI half PASS — `--export-to` wrote the profile and both listings |
| 54 import the same file back | **BLOCKED** | window blocked; CLI half PASS — the plan printed and nothing was added ("Nothing would be added: this file holds nothing this database does not already have") |
| 55 import with Yes; no duplicate rows | **BLOCKED** | window blocked; CLI half PASS — the first `--yes` applied and reported what it kept; a second said "Nothing would be added" |
| 56 import a profile-carrying file from another database | **BLOCKED** | window blocked; CLI half PASS — importing into an empty database reported each kind added (2 listings, profile, 2 application records, 1 follow-up day, 3 employment records, 2 education records, 1 activity entry) |
| 57 terminal export/import on two disposable databases | **PASS** | `--export-to`, `--import-from` (plan), `--import-from … --yes`, idempotent second run, and the refusal to overwrite the existing export |
| 58 malformed import, missing path, missing target database | **PASS** | `{}` → "has no format_version" exit 2; a missing path → exit 2; a target database that does not exist yet → exit 2 with "run the app or the commands once first" and no file created |
| 59 a follow-up survives a status change | **BLOCKED** | window blocked; data half PASS — after the status moved to `interview` the reminder day and note were still stored |
| 60 a follow-up survives a listing re-save | **BLOCKED** | window blocked; data half PASS — re-saving the listing left the follow-up day and note in place |

### Next actions, interviews and preparation (61–67)

| Step | Status | Evidence |
| --- | --- | --- |
| 61 the list is in date order with undated items last | **BLOCKED** | window blocked; CLI half PASS — `--next-actions` printed the overdue item, then the dated ones, then the undated item, with the preparation and round counts |
| 62 mark an item done | **BLOCKED** | window blocked; data half PASS — the overdue item can be ticked off and the undated one stays open |
| 63 record an interview round | **BLOCKED** | window blocked; data half PASS — a round saved for tomorrow reads as 1 day away and awaits an outcome; recording "it did not go ahead" changes no application status |
| 64 delete a follow-up record | **BLOCKED** | window blocked; data half PASS — clearing removes the plan only (step 46) |
| 65 delete a round (No, then Yes) | **BLOCKED** | window blocked; data half PASS — the round can be deleted and only that round disappears |
| 66 `--next-actions` and `--interviews` | **PASS** | both exit 0 with the same records; combined they are refused by the parser with status 2 |
| 67 `--next-actions` on a path that does not exist | **PASS** | exit 0, "No database yet…", and no file created |

### Work history and education (68–78)

| Step | Status | Evidence |
| --- | --- | --- |
| 68 add a current role | **BLOCKED** | window blocked; data half PASS — the role reads "2024-06-01 - present" and lists first |
| 69 an end date before the start date is refused | **BLOCKED** | window blocked; data half PASS — refused with the message naming the two dates; an ended role reads "2022-01-10 - 2023-05-31" |
| 70 "1 April 2023" refused by the history form's date shape | **BLOCKED** | window blocked; the form's shape check accepts `2023-04-01` and rejects `1 April 2023` |
| 71 edit and delete a role | **BLOCKED** | window blocked; data halves PASS — the job title change is stored; deleting removes only that role |
| 72 ongoing study with no dates | **BLOCKED** | window blocked; data half PASS — "start not recorded - ongoing", listed before the completed record |
| 73 ongoing study with a completion date | **BLOCKED** | window blocked; data half PASS — refused, naming both facts |
| 74 `--history` | **PASS** | the records in the window order, the months-covered sentence, and the read-only closing line |
| 75 `--add-role` and its duplicate refusal | **PASS** | the role was added; the same role again was REFUSED (exit 2, naming the stored record); the total then reported 57 months |
| 76 `--add-study` and its duplicate refusal | **PASS** | the stored B.Tech at the fixture's institution was refused as a duplicate (exit 2); a genuinely new qualification (M.Tech at the same institution) was added and listed |
| 77 delete the profile | **BLOCKED** | window blocked; data half PASS — the profile, employment and education records are gone and the listings remain |
| 78 export file contents | **PASS** | keys `education`, `format_version`, `jobs`, `privacy_note`, `profile`, `work_history`; `format_version 2`; 3 work-history records and 2 education records |

### Progress (79–85)

| Step | Status | Evidence |
| --- | --- | --- |
| 79 tracker summary line, no rate below five | **BLOCKED** | window blocked; the same lines are what `--analytics` prints (steps 83/84) |
| 80 the progress dialog's contents and its close keys | **BLOCKED** | window blocked |
| 81 resizing and scrolling keeps the button visible | **BLOCKED** | window blocked |
| 82 "What cannot be measured here" and no bare "0 offers" | **BLOCKED** | window blocked; the same section is in the terminal report, which says an offer cannot be stored anywhere in this application |
| 83 below the floor, "No rate is shown" with the reason | **BLOCKED** | window blocked; the terminal report says "No rate is shown: the floor of 5 application(s) is not reached (the denominator is 1)" |
| 84 `--analytics` matches the dialog | **PASS** | counts, named denominators, the timing section, the period comparison, the five caveats and the read-only ending; re-run after defect D1 was fixed |
| 85 `--analytics` on a path with no database; `--history --analytics` | **PASS** | "No database yet…" exit 0 and no file created; the two flags together are refused by the parser with status 2 |

### Email and calendar interfaces (86–94)

| Step | Status | Evidence |
| --- | --- | --- |
| 86 the two read-only actions exist and nothing connects an account | **BLOCKED** | the tab is a window; the CLI equivalents were run, and the shipped-code scan finds no account or socket use (step 15) |
| 87 the calendar preview dialog | **BLOCKED** | window blocked; CLI half PASS — `--preview-calendar-export` listed one event as `<day>: Follow up: Data Engineer at Sandbox Systems  [follow-up-j1-20261018@ai-career-agent.local]`, said nothing was written, and no `.ics` file appeared |
| 88 the draft dialog | **BLOCKED** | window blocked; CLI half PASS — a listing with no row selected is refused; with one, the draft shows `To: not supplied`, `Status: DRAFT ONLY … nothing has been sent`, an operation id, and the "Missing, and not guessed" recipient line |
| 89 nothing changes while the dialog is open | **BLOCKED** | window blocked; the read-only property of the preview/plan is what the CLI checks assert |
| 90 a real mail client shows nothing | **BLOCKED** | there is no mail client on this machine, and this is a real-desktop check |
| 91 `--integration-status` | **PASS** | prints that nothing is enabled, the seven conditions a real provider would need, ends by saying nothing was sent or created, exit 0, no database created |
| 92 preview compared with the written file | **PASS** | the file's UID and summary are the ones the preview listed; 637 B, `-rw-------`, no `ATTENDEE`, no `ORGANIZER`, no URL line |
| 93 the five refusals | **PASS** | an unknown listing id, `--recipient` on its own, `--at 10:30` without a zone, `--minutes 30` without `--at`, and `--mock-ledger` on its own — each printed a reason, said nothing was written or created, exited 2, and wrote no file |
| 94 disabled, then the mock twice | **PASS** | `[disabled]` with "nothing was sent and nothing was created" and exit 2; then `[completed]` recording exactly one operation, and a second run reporting `[duplicate]` and adding nothing. The "watch the machine's network and calendar" half is **BLOCKED** (no graphical session); the no-socket property is what `tests/test_local_only.py` runs in a socket-blocked interpreter |

### Reporting on a database the app cannot fully read (95–98)

| Step | Status | Evidence |
| --- | --- | --- |
| 95 the window on the damaged copy | **BLOCKED** | window blocked; the refusal sentence itself was observed on the command line (analytics and follow-ups) and the dialog's use of it is pinned by the desktop handler tests |
| 96 `--doctor` on the copy | **PASS** | exit 1, `PROBLEM: 1 stored record(s) cannot be read by this version`, `application_tracker`, record `'j1'`, ending "Nothing was changed or repaired by this check."; SHA-256 identical before and after |
| 97 the reports on the copy | **PASS** (Linux) | `--analytics` and `--follow-ups` each exit 2 with the sanitised refusal and a pointer to `--doctor`; `--history` still runs and exits 0. The "no crash dialog on macOS and Windows" clause is **BLOCKED** — those machines are not available |
| 98 healthy database, then a copy recording version 5 | **PASS** | healthy: "Every stored record could be decoded by this version.", exit 0; the version-5 copy: reported as written by version 5, records not decoded, exit 0, `user_version` still 5 afterwards |

### Beyond the checklist: what this run also exercised

- `--preview-calendar-export`, `--calendar-to`, `--draft-follow-up` and `--record-follow-up` on a database
  holding an unreadable record now refuse in the same sentence as the read-only reports, with status 2 and no
  start-up note (defect D2).
- `--import-from … --yes` into such a database is refused **before** anything is written; row counts and the
  damaged row are unchanged (defect D3).
- A file that is not a database at all is described as a file problem (`could not be read … file is not a
  database`) rather than as a database holding a bad record, by the reports and by `--doctor`.
- `--backup-to` on such a file refuses and creates nothing.

---

## 4. Blocked checks and what is missing

| Missing capability | Blocks |
| --- | --- |
| A display and a Tkinter build (`DISPLAY` unset, `import tkinter` fails; no `Xvfb`/`xvfb-run`) | every window step: 1–14, 16–21, 24–36, 38–48, 51–56, 59–65, 68–73, 77, 79–83, 86–90, and the window halves of 37, 95 |
| A real calendar application | 47 |
| A configured mail client | 90 |
| macOS and Windows machines | the per-operating-system wording in 97, and any cross-platform claim |
| The optional `pypdf` extra | the PDF half of 24–31 (the 12 PDF tests skip for the same reason) |

Not one of these was simulated, and no step is marked PASS on the strength of a related automated test.

---

## 5. Defects found in this run

Each was reproduced first, then diagnosed, fixed minimally, covered by a regression test that fails on the old
behaviour, and re-run. `SOURCE_QUALITY_GATE_PASSED` stays `False` and `enabled_discovery_sources()` stays
empty throughout; the job-source CSV was not touched
(`input_sha256 0356b093ded3917c0fa9ba3aa9f12a682caaf81df7c49a6b042950d66a08f414`, 83 records).

### D1 — the progress report counted a round that has not happened as one whose outcome was recorded

- **Seen at:** step 84. The only stored round was `('j1', 'screening', '2026-10-16', 'video', 'awaiting')`, and
  `--interviews` said "Waiting - it has not happened yet", yet the report printed
  `Rounds where you recorded how it went: 1`, labelled "your own reading of the round, saved after it
  happened".
- **Cause:** the count was `record.outcome is not None`; `awaiting` is a stored outcome, so an invitation
  nobody has attended counted as a reading.
- **Fix:** the count excludes `awaiting` (`career_agent/analytics.py`).
- **After:** the same database prints `Rounds where you recorded how it went: 0`; recording "it did not go
  ahead" prints `1`.
- **Test:** `tests/test_analytics.py::…::test_a_round_that_has_not_happened_is_not_counted_as_one_whose_outcome_was_recorded`
  (failed before the fix with `3` where the label promises `2`).

### D2 — a readable database holding one unreadable record was reported as a start-up that failed

- **Seen at:** steps 93/94 on a damaged copy. `--preview-calendar-export`, `--calendar-to`,
  `--draft-follow-up` and `--record-follow-up` printed
  `COULD NOT START: The application stopped while starting up.` with `TrackerStatusError`, exited **3**, and
  wrote a `startup-diagnostics.log` beside the data — for a command that never started a window and for a
  database that had been read successfully apart from one row.
- **Cause:** the six read-only reports handled the failure themselves; these commands let it reach the
  top-level handler, which describes a *start-up* failure and keeps a note.
- **Fix:** the handler refuses a database it cannot read for every command, in the same sentence and with the
  same status (2) the reports use, and only describes a start-up when the window is what was asked for
  (`career_agent/__main__.py`).
- **After:** all four commands print `REFUSED: this database holds a record this version cannot read: …`, exit
  2, write no note, and create no output file. A file that is not a database at all gets the file-level
  sentence instead.
- **Test:** `tests/test_damaged_records.py::EveryCommandThatReadsTheRecordTests` (fails `6 != 2`-style against
  the old handler).

### D3 — an import into that database wrote part of the file and then refused

- **Seen at:** the import half of step 97. Row counts before a refused
  `--import-from … --yes`: `(profile 0, employment 0, education 0, listings 1, trackers 1, activity 0)`; after
  the refusal, exit 2: `(1, 3, 2, 1, 1, 0)` and the stored listing's payload rewritten. The refusal said
  "Nothing was changed or repaired".
- **Cause:** the import applies record by record, and the failure on the damaged tracker row happened after
  the profile, employment and education records were written.
- **Fix:** the command sweeps the target with the same read-only decoder sweep `--doctor` uses, and refuses
  before it plans or applies anything.
- **After:** the same command refuses with the record named, and the same before/after counts are identical.
- **Test:** `tests/test_damaged_records.py::EveryCommandThatReadsTheRecordTests::test_an_import_into_a_database_with_an_unreadable_record_writes_nothing`
  (compares every row of every table and the file's bytes; fails against the old code).

### D4 — a refusal claimed a draft had been written when nothing was on disk

- **Seen at:** step 93, `--draft-follow-up j1 --mock-ledger ledger.json` with no recipient: the command
  printed `REFUSED: the draft was written but not performed (invalid).` and exit 2 — with no file anywhere.
- **Cause:** one sentence served two different states (a draft saved to a file and then refused, and a request
  that was never written because it was missing a fact).
- **Fix:** the message names what happened: no file written, or the path that was written.
- **Test:** the assertions in `tests/test_cli_integrations.py` on both states
  (`…recorded_nowhere` now asserts "no file was written"; the new `…says_which_file_was_written` asserts the
  path is named and the file exists); both fail against the old message.

---

## 6. What the automated checks cover, and what they do not

- Full suite on this revision: **1559 tests, `OK (skipped=13)`**; `compileall` clean; the CSV audit reports the
  unchanged digest. CI runs the same suite on 3.10, 3.11, 3.12 and 3.13 plus the installed-package job on 3.10
  and 3.13, and the commit carrying this report (`a74b722`, run `38700616471`) passed all six jobs — so the
  suite result above is reproduced on four interpreters, not only on the 3.11 this machine has. There is **no
  3.14 leg** and no macOS or Windows leg, so no support is claimed for them.
- The suite is not a substitute for this run: every window interaction above is still unverified, and the
  defects above were found by executing the checklist, not by the suite — D1 had no assertion on that count,
  D2/D3 were only reachable through a real command sequence, and D4's message was pinned by a test that could
  not see the missing file.
- The temporary fixtures, transcripts and virtual environments live outside the repository (`/tmp`) and are
  not committed; nothing in this run wrote into the checkout, the application-data folder or any real
  database.

---

## 7. Remaining blockers and the recommendation

**Blocked, in the order they matter:** a real desktop session (every window step, and the "watch the machine"
half of the integration checks); macOS and Windows runs of this checklist; the optional `pypdf` extra for the
PDF résumé steps; a release checklist that repeats this run from a *packaged* build on each supported system.

**Not blocked and now verified on Linux, headlessly:** install from the built wheel, version reporting, the
doctor (healthy, damaged-record, damaged-file, older-schema and missing-database cases), profile and record
persistence, eligibility and transition rules, follow-ups, next actions, interviews, preparation, work history
and education, analytics, JSON export and import, backup and restore, the email/calendar interface including
its refusals and the local mock, and the operational safety properties (no sockets, gate closed, discovery
disabled, owner-only files, nothing written into the repository).

**Recommendation: continue remediation, and schedule the cross-platform GUI run before any release review.**
Specifically:

1. Run this checklist on a machine with a display and Tkinter (Linux desktop first, then macOS and Windows),
   recording results in the same format — the window steps are the only part of the product with no execution
   evidence at all.
2. Install the `pdf` extra there and exercise the résumé steps 24–31, including the scanned-PDF and DOCX-table
   cases.
3. Then decide on packaging (artefacts, signing, interpreter bundling) — until a packaged build has been
   rehearsed on each supported system, the accurate description remains "a local alpha you install into your
   own Python environment".

A limited release review is **not** justified yet: two thirds of the checklist cannot be executed here, and
the four defects above were each found within the first execution of the steps that could be.

---

## 8. Later the same day: the window steps' functional claims, driven automatically

Nothing in sections 1-7 changed. What changed is that the *functional* claim behind a number of the window
steps is now executed on machines that do have a display, by the second entry point this project had to be
added for the purpose (`scripts/desktop_acceptance.py`, section 14 of
`research/cross-platform-desktop-ci-evidence-2026-10-15.md`).

- **Seven workflows, 46 checks, on five display-backed CI legs** — Linux under Xvfb, Windows 2025 (3.10 and
  3.13) and macOS 26 (3.10 and 3.13) — every leg `RESULT: PASS — 46 checks passed`, in run `38747830528` at
  `e939260`, all 12 jobs successful. The whole suite is green on the same legs: 1642 tests,
  `OK` (37, 44, 13 and 20 skipped by interpreter and platform).
- **What the workflows drove**: a profile typed, saved, closed and read back; the two job URL fields kept
  apart with the blank one still blank; a listing with no availability evidence staying UNKNOWN and refusing
  shortlisting, then reaching PASS once the evidence and requirements were stated; an application moved
  through its permitted statuses with a confirmation refused until the person asserted it and an interview
  round never counted as an outcome; an export that agrees with the database and warns that the file may hold
  personal data, imported into a second database, with three refusals writing nothing; the work history and
  study forms, including their refusals and a role's stored values loaded back into an emptied form for
  editing; and cleanup that releases every window and connection, deletes its own folder and leaves the
  person's own database byte-identical, including after a forced failure.
- **What this is still not.** No human has opened the window. Layout and clipping at normal and smaller
  sizes, dialog wording, keyboard-only navigation and focus order, screen-reader behaviour, mouse-driven
  flows and native feel are exactly as unverified as they were in section 7 — a machine driving widgets
  through Tk's own dispatch cannot judge any of them. The checklist verdicts are unchanged: **22 PASS,
  76 BLOCKED, 0 FAIL**, with no box ticked and 20 steps now carrying an "Automated coverage" line (four of
  them in part).
- **One more flake, in a unit test rather than the product**: the macOS 3.13 leg of run `38750225851` failed a
  case comparing the whole stored tracker row after an idempotent re-save, because the row's `updated_at` is
  the store's own write clock at whole-second resolution and the two writes need not land inside one second.
  The record's own columns are what must not move, and that is what the case now compares (`90e4b3f`), with a
  second case pinning the clock behaviour deterministically; no store behaviour was changed to make it pass.
  The last run, `38752606452` at `90e4b3f`, is green on all 12 jobs with 1643 tests `OK (skipped=13)` on
  macOS 3.13 and `RESULT: PASS — 46 checks passed` on the Linux display leg.
- **Three defects only a real display could show came out of this**, each fixed with regression tests:
  D14 (a cleanup check read Tk's refusal to answer for a destroyed interpreter as the window having
  survived, fixed in `dfea62d`), D15 (a widget lookup that could not read the name Tk answers a binding
  with, and a failure that did not say what the widget was bound to instead, fixed in `8f6874d`), and D16
  (two steps acting on a selection that a list refresh had taken away, and a stand-in tree that kept a
  deleted row selected so the same mistake passed headlessly, fixed in `e939260`). A fourth finding was in a
  unit test rather than the product: a pre-upgrade case asserted a listing order that depended on two saves
  landing in the same second, fixed in `c0314c2` by pinning the observation time through the store's own
  parameter.

---

## 9. The last increment of 2026-10-15: follow-ups, the scheduler and data safety

Sections 1-8 stand as they were written. Three more workflows have since been added to
`scripts/desktop_acceptance.py`, and the script now declares **76 checks** (section 15 of
`research/cross-platform-desktop-ci-evidence-2026-10-15.md` has the full account and the per-leg table).

- **Ten workflows, 76 checks, on five display-backed CI legs** — Linux under Xvfb, Windows 2025 (3.10 and
  3.13) and macOS 26 (3.10 and 3.13) — every leg `RESULT: PASS — 76 checks passed`, in run `38762008724` at
  `5b291a7a`, all 12 jobs successful. The whole suite is green on the same legs: 1648 tests, `OK` (13, 20, 37
  and 44 skipped by interpreter and platform). Workflow I's first green run was `38761595835` at `d12c2bcb`
  (68 checks, 12/12 jobs).
- **What the new workflows drove**: a follow-up day recorded for an application selected in the window — its
  first day, which no reachable path could record before — with overdue, due-today and later days computed
  from fixed offsets and read as words, the list ordered by day with its summary line, a day moved and cleared
  from its own row with a declined clear changing nothing, the list across a close and reopen, preparation
  items added through their own dialog (one with a day, one with none, listed rather than hidden), ticking one
  off without touching any status, a reminder whose listing or record has gone reported rather than acted on,
  and a calendar preview and an email draft that write nothing and send nothing; the scheduler tab's own
  buttons — the default tasks added and adding them again creating nothing, pausing asking first, a declined
  pause changing nothing, a real pause keeping the task's definition and history and reading "paused", that
  pause surviving a restart, resume scheduling the next occurrence from now and replaying nothing, a deleted
  task reported rather than written back, and no worker started, no lease taken and no attempt recorded; and
  data safety — a backup written through the tab's own chooser and verified before success is reported and
  owner-only on POSIX, an existing destination never overwritten, a cancelled chooser writing nothing, a
  malformed, foreign, truncated and too-new file each refused with the live database's digest unchanged, a
  declined restore changing not one byte, a confirmed restore undoing what came after the backup while keeping
  the previous database as a readable copy, a restore refused while another connection holds the database, and
  no temporary file left behind on success or failure.
- **Two defects only a real display could show came out of these workflows.** D17: the first follow-up day
  could not be recorded from any path in the window, because the Follow-ups tab lists only applications that
  already hold a day and the button that sets it read its subject from that empty list; fixed in `480dca1`
  with a handler-level regression test that fails before the fix and with H1–H2 as the display-backed proof.
  The second: run `38758158210` failed workflow H5 on all five legs with `SmokeFailure: the fields still hold
  a day that was cleared`, because a cleared day rebuilds the list, real Tk fires `<<TreeviewSelect>>` on the
  rebuilt tree, and the handler refilled the fields from another tab's selection; the binding now reads only
  the reminder list's own row, the acceptance step re-selects the row it acts on, and the fail-before-fix
  check reproduced as `AssertionError: '2026-10-24' != ''` (`0215413`).
- **What this is still not.** No human has opened the window, on any platform. Layout and clipping, dialog
  wording, keyboard-only navigation and focus order, screen-reader behaviour, real mouse-driven flows and
  native feel are exactly as unverified as in section 7. The checklist verdicts are unchanged — **22 PASS,
  76 BLOCKED, 0 FAIL**, no box ticked — with 35 steps now carrying an "Automated coverage" line, ten of them
  in part. The stand-in development run (`--stand-in-tk`, 76 passed, `RESULT: BLOCKED`, exit 2) is a
  development aid on a machine with no display and is not evidence of real-window behaviour.
