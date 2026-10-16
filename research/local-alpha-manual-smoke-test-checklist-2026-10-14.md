# Local Alpha Manual Smoke-Test Checklist

**Status:** Executed on 2026-10-15 on a headless Linux machine: the 22 steps that need no window passed, 76 are blocked for named missing capabilities (see the execution results below and `research/local-alpha-manual-acceptance-run-2026-10-15.md`), and four defects found by the run were fixed. **Still required before calling the desktop alpha verified, and not yet recorded as passed.**

**Update, 2026-10-15 (final increment of the day):** the verdicts are unchanged again — 22 PASS, 76 BLOCKED,
0 FAIL — and **no box has been ticked**. The acceptance run now also drives the Work history & study forms as
workflow G: a current role added through the form, an impossible period and an unparseable date refused with
nothing stored, an ongoing qualification added, a contradictory one refused, a role's title loaded into an
emptied form and saved over the record, and the current-role flag taken off again with an end date saved.
That is **46 checks per leg** on the same five display-backed CI legs, run `38747830528` at `e939260`; six more
steps (68–73) carry coverage lines citing it, and the earlier lines keep the numbers of the run that produced
them. Two of those six are **partial**: the delete button's two answers (71) and the finished-qualification
listing (72) are not driven by the run.

**Update, 2026-10-15 (the last increment of the day):** the verdicts are unchanged once more — 22 PASS,
76 BLOCKED, 0 FAIL — and **no box has been ticked**. Three workflows are new: follow-up reminders and the
combined next-action list (H1–H14), the schedule's pause and resume with nothing started (I1–I8), and
data safety — a verified backup, a validated restore and every refusal in between (J1–J8). That is
**76 checks per leg** on the same five display-backed CI legs, run `38762008724` at `5b291a7a`; the fifteen
numbered steps those workflows drive carry coverage lines citing that run, and every earlier line keeps the
numbers of the run that produced it. Workflow H is also where a real desktop defect was found: the first
follow-up day could not be recorded from any reachable path in the window, because the button that sets it
only ever looked at the reminder list — which is empty precisely when a day is being recorded for the
first time. It is fixed (`480dca1`) with a regression test at the handler level, and H1–H2 are the
display-backed proof.

**Update, 2026-10-15 (later the same day):** the numbered steps' verdicts are unchanged — 22 PASS, 76 BLOCKED, 0 FAIL — and **no box has been ticked**. What is new is 14 steps whose *functional* claim is now checked automatically, through the real window, on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26; CPython 3.10–3.13): each of those steps now carries an "Automated coverage" line naming the checks, the run and the commit. Nothing about layout, wording, focus order, accessibility, mouse-driven use or native feel is covered by those checks, which is what the remaining BLOCKED verdicts are about; see "Automated coverage of numbered steps" below.  
**Update, 2026-10-16 (later the same day: one new check, no verdict changed):** the verdicts are unchanged —
22 PASS, 76 BLOCKED, 0 FAIL, no box ticked — and the harness gained **one check inside an existing workflow**
rather than a new workflow: `scripts/desktop_acceptance.py` now declares **77 checks**, and workflow I gained
I9, which adds a task whose schedule nobody ever ran and requires the **Background tasks** tab's summary to
name what the schedule walked past while nothing was running — while starting no worker, taking no lease and
recording no attempt. Steps 1–I8 keep their numbers and their meaning, so every coverage line below that
names a step still names the same check. The behaviour itself (``worker.missed_occurrences``, surfaced by
``--worker-status`` and the tab's summary) is new in this increment, and it is a *report*: nothing catches up
on a missed occurrence, which is why the numbered step 51's manual half stays BLOCKED.

**Update, 2026-10-16 (coverage gaps closed, no verdict changed):** the verdicts are unchanged — 22 PASS,
76 BLOCKED, 0 FAIL, no box ticked — and **no acceptance workflow was added or extended**: the milestone's
harness stays at ten workflows and 76 checks. What changed is that five claims previously marked *partial* now
carry a verified assertion at the level where they live. Four are at the handler-stub level, in
`tests/test_desktop_handlers.py`, and each was proved to bite by a temporary mutation that the assertion caught:
the application's **activity history is compared before and after a declined and an accepted follow-up
clear** (because the confirmation promises it stays as it is); the scheduler tab's own **cadence and timezone
cells are asserted for all three default tasks** (`00:00, 12:00`, `23:30`, `09:00`, `Asia/Kolkata` — the module
test names the constant, so a literal appears here); the calendar preview's **whole per-event line** is asserted
as the dialog draws it; and the email draft's **complete field set plus the refusal when no reminder is
selected** are asserted. The fifth, next-action row ordering, was already covered and needed no new test:
`tests/test_preparation.py::ActionTests` (most-overdue-first, the kind tie-break, and independence from input
order) and `tests/test_desktop_handlers.py::NextActionsTabTests` (the exact row order across all three kinds).
Each of the five steps' coverage lines now names both levels rather than calling itself partial, and the one
half that remains genuinely unasserted (whether some other control could connect an account, step 86) is stated
as such.

**Date created:** 2026-10-14

This checklist is intentionally separate from unit tests. It requires a real desktop session and should be completed on each operating system that the project advertises as supported. Do not mark a step passed based only on code inspection.

## Preconditions

- [ ] Python 3.10+ is installed.
    → **PASS — python3 -V reported 3.11.2.**
- [ ] Tkinter is available in that Python installation.
    → **BLOCKED — no display and no Tkinter in the acceptance environment: import tkinter raises ModuleNotFoundError and DISPLAY is unset.**
- [ ] From the repository root, run: python -m career_agent --version; it must print the version and the
  schema version and exit with status 0, in a terminal and with no display variables set.
    → **PASS — printed 0.1.0 (database schema version 6) and exited 0 with no display variables set.**
- [ ] From the repository root, run: python -m unittest discover -s tests -v
    → **PASS — Ran 1559 tests, OK (skipped=13).**
- [ ] Run: python -m compileall -q career_agent scripts tests
    → **PASS — exit 0 with no output.**
- [ ] Run: python scripts/audit_job_source_csv.py; it should print a JSON report with an input SHA-256 and no unhandled error.
    → **PASS — JSON, input_sha256 0356b093…, 83 records, exit 0.**
- [ ] Use a throwaway copy of the database for destructive or exploratory steps. The correction tool
  (`scripts/correct_tracker_record.py`) and a GUI restore both write a verified backup first, but the
  other GUI actions (deleting a job or the profile, exporting) do not.
    → **PASS — every destructive step ran on a synthetic copy under /tmp; the application-data folder still does not exist.**

## Desktop workflow

1. [ ] Run python -m career_agent; confirm the window opens without a traceback.
    → **BLOCKED — no display and no Tkinter in the acceptance environment.**
2. [ ] Confirm the displayed database path is in the operating system's per-user application-data directory, not inside the repository.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the path rule itself was printed by the doctor run.**
3. [ ] Enter a profile with country, degree, study status, graduation year, experience, work authorization, and skills. Save, close, reopen, and confirm values persist.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the same profile round-tripped at the storage layer.**
    → **Automated coverage (2026-10-15): A1–A6 (profile fields persisted and read back; a role and a qualification added through the window's own forms and listed after a reopen) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10–3.13), 38 checks per leg, run `38739493727` at `a530029`.
4. [ ] Enter a manual job with a source listing URL and leave the employer application URL blank. Save, restart, and confirm the two URL fields remain separate and the employer URL is still blank.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; both URL fields round-tripped at the storage layer.**
    → **Automated coverage (2026-10-15): B1–B5 (both URL fields kept separate, the blank one still blank after a reopen, nothing submitted, the save confined to the disposable database) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10–3.13), 38 checks per leg, run `38739493727` at `a530029`.
5. [ ] Mark the listing open but leave the availability evidence/note blank. Evaluate: overall eligibility must remain UNKNOWN; shortlisting must be blocked.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the evaluation rule was executed directly and returned UNKNOWN.**
    → **Automated coverage (2026-10-15): C1–C4 (open with no evidence evaluates UNKNOWN, shortlisting is refused, and the status does not move) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10–3.13), 38 checks per leg, run `38739493727` at `a530029`.
6. [ ] Add an availability evidence/note and explicit matching mandatory requirements. Evaluate: eligibility may be PASS only if every applicable hard requirement passes.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the evaluation rule was executed directly and returned PASS.**
    → **Automated coverage (2026-10-15): C5–C6 (with the requirements stated explicitly the same application reaches PASS on every requirement and is shortlisted) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10–3.13), 38 checks per leg, run `38739493727` at `a530029`.
7. [ ] Change the allowed country so it excludes the candidate country. Evaluate: eligibility must be FAIL.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the evaluation rule was executed directly and returned FAIL.**
8. [ ] Add an explicit allowed-work-authorization list. A missing candidate value must be UNKNOWN; an exact matching value may pass that check; a mismatch must fail. Do not accept fuzzy/semantic equivalence.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; UNKNOWN, exact-match PASS and mismatch FAIL all executed directly.**
9. [ ] Remove a mandatory degree/study-status/graduation-year value from either the candidate or listing. Evaluate: eligibility must not pass.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; a missing mandatory value never reached PASS when executed directly.**
10. [ ] Attempt to shortlist a FAIL or UNKNOWN job. The app must block it. Shortlisting an explicit PASS job should update the tracker.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the gate lives in the window handler, and the transition table it consults was verified.**
    → **Automated coverage (2026-10-15): C4 and C6 (blocked while UNKNOWN, allowed once PASS, and the tracker moves to 'shortlisted') drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10–3.13), 38 checks per leg, run `38739493727` at `a530029`.
11. [ ] Attempt an invalid tracker transition and confirm the app shows an error without changing the saved status.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; an invalid transition was refused directly and the stored status stayed unchanged.**
    → **Automated coverage (2026-10-15): D4, D5 and D6 (a status the record may not move to is not offered at all; a refused change shows an error dialog and the saved status is unchanged) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10–3.13), 38 checks per leg, run `38739493727` at `a530029`.
12. [ ] Attempt to mark an application confirmed without evidence; it must be rejected. Attempt it
    again with the app's own guidance text pasted in (for example "Evidence / note (required to
    confirm)" or "A confirmed application requires evidence. An attempt or timeout is not proof.");
    it must also be rejected, and nothing may be written. Then select `confirmed` without ticking
    the confirmation assertion: it must be refused. Only a ticked assertion plus a real observation
    (for example "Employer portal shows Application Received on 2026-10-14") may be saved, and the
    stored `candidate_confirmed` value must then be true. Move it on to response_received or
    interview; the confirmation state must remain preserved. Finally, confirm that a record already
    at `confirmed` cannot have its evidence rewritten in place, and that the dialog explains
    `withdrawn` as the honest correction when the confirmation was a mistake or a test.
    **Never use a real employer's confirmation text in a test run, and never store instruction text
    as evidence.** If a test record does end up confirmed in the real database, correct it with
    `scripts/correct_tracker_record.py` (dry run first) instead of editing SQL by hand.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; all four evidence cases, the ticked assertion and its preservation were executed directly.**
    → **Automated coverage (2026-10-15): D6 (confirmed without the assertion is refused with an explanation and nothing is written) — **partial**: the pasted-guidance-text refusal and the in-place evidence rewrite are not driven here. The rest was driven through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10–3.13), 38 checks per leg, run `38739493727` at `a530029`.
13. [ ] Export to a user-selected JSON file; verify it parses and contains the profile/jobs/tracker records. Confirm the UI warns that the file may contain personal data.
    → **BLOCKED — no display and no Tkinter in the acceptance environment for the warning line; the export itself ran from the terminal and the file was inspected.**
    → **Automated coverage (2026-10-15): E2 (the file parses, carries the profile, the listings, the application record that matches the database, the format version and the top-level history arrays, and the window says the file may hold personal data and to keep it private) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10–3.13), 38 checks per leg, run `38739493727` at `a530029`.
14. [ ] Delete a job and confirm its tracker record is deleted. Delete the profile and confirm it is absent after restart.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; both deletions were executed at the storage layer.**
15. [ ] Inspect the application workflow for network access: local alpha operations must not send requests or candidate data to external services.
    → **PASS — shipped-code scan plus a child interpreter whose socket creation is blocked.**
16. [ ] Close and reopen the app after a forced close or normal exit; confirm the SQLite database remains readable.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; close and reopen executed at the storage layer.**
17. [ ] Open the **Data safety** tab. Click *Back up database*, choose a new file, and confirm the app
    reports a verified backup. Check the file: on macOS/Linux `ls -l` must show owner-only permissions
    (`-rw-------`). Never point this at a file you still need: an existing file must be refused, not
    overwritten.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the terminal backup reported 'written and verified'.**
    → **Automated coverage (2026-10-15): J1 (the backup is written from the Data safety tab's own file chooser, is verified before the window reports success, holds the records the database holds and is owner-only on POSIX, and the live database's digest is unchanged afterwards); J2 (a second backup to the same path is refused and the first file's digest does not move) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 76 checks per leg, run `38762008724` at `5b291a7a`.**
18. [ ] Back up again to the *same* path. The app must refuse and explain, and the earlier file must be
    unchanged (compare the file size and its modification time).
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the second terminal backup was refused with the first file byte-identical.**
    → **Automated coverage (2026-10-15): J2 (the refused second backup leaves the first file byte-identical, and a destination inside a folder that does not exist is refused with no file created and the folder still absent) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 76 checks per leg, run `38762008724` at `5b291a7a`.**
19. [ ] Add a job, then restore from the backup made in step 17 and confirm the question is asked first.
    Cancel once: nothing may change. Then confirm: the added job must be gone, the older data must be
    back, and a `<database name>.backup-<timestamp>` file must exist beside the database.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the terminal restore ran and a timestamped copy was kept beside the database.**
    → **Automated coverage (2026-10-15): J5 (the confirmation is answered **No** first and not one byte of the database or of its folder changes); J6 (answered **Yes**, a listing saved after the backup is gone, the profile is back, the window's list matches the stored records, exactly one `<database>.backup-<timestamp>` copy holds the pre-restore counts and is still readable, and the restored database can be written to again) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 76 checks per leg, run `38762008724` at `5b291a7a`.**
20. [ ] Close and reopen the app after that restore; the restored data must still be there, and the
    status line must not claim a success that did not happen.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the restored database was read back from the terminal with only the older records.**
21. [ ] Choose a file that is not a database (for example a text file) and restore from it: the app must
    refuse with a clear message *before* asking to confirm, and the current data must be untouched.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the terminal restore from a text file was refused with the database unchanged.**
    → **Automated coverage (2026-10-15): J4 (a text file, another program's database, a file truncated to its first 4 KiB and a copy marked with a newer schema version are each refused under "Backup cannot be used" with "The current database was not changed.", the live database's digest does not move, and no temporary file is left behind) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 76 checks per leg, run `38762008724` at `5b291a7a`.**
22. [ ] From a terminal in the repository root, run
    `python -m career_agent --database "<path to a throwaway copy of the database>" --backup-to "/tmp/alpha-check.sqlite3"`
    and confirm it prints a verified backup; then run the same command again and confirm it refuses
    rather than overwriting. Finish with
    `python -m career_agent --database "<same throwaway copy>" --restore-from "/tmp/alpha-check.sqlite3" --yes`
    and confirm it restores and reports the previous-database copy.
    → **PASS — both commands ran, with the refusal and the kept copy observed.**
23. [ ] Confirm no file was created inside the repository (`git status` must stay clean) and that nothing
    was uploaded: the backup commands must work with networking switched off.
    → **PASS — git status --porcelain was empty after the batch and again at the end.**

## Résumé import (PDF or DOCX)

24. [ ] In the **Candidate Profile** tab, press **Import resume (PDF/DOCX)** and pick a PDF with a real text
    layer. The file must be read locally; the review window must open without a traceback — this is the
    step that crashed on macOS (Python 3.14, pypdf 6.20.1) with `unknown option "-wraplength"`.
    → **BLOCKED — no display and no Tkinter in the acceptance environment, and the optional pdf extra is not installed, so the PDF path could not run either.**
25. [ ] Confirm every proposal row shows: a checkbox with the field name, a wrapped label with the proposed
    value, and a wrapped line with the confidence and the `from: ...` evidence quote. Nothing may be cut off
    at the right edge, and no row may be missing its wrapping.
    → **BLOCKED — no display and no Tkinter in the acceptance environment, and the optional pdf extra is not installed, so the PDF path could not run either.**
26. [ ] With a résumé long enough to fill the window, scroll the proposal area with the mouse wheel and by
    dragging the scrollbar. The header and the **Save selected values** and **Cancel** buttons must stay in
    place and remain clickable at every scroll position, and resizing the window must keep them visible.
    → **BLOCKED — no display and no Tkinter in the acceptance environment, and the optional pdf extra is not installed, so the PDF path could not run either.**
27. [ ] Press Escape, then reopen and press the window's close button, then reopen and press **Cancel**: each
    must close the window, set a status line saying the profile was not changed, and leave the saved profile
    exactly as it was (check the form and reopen the app).
    → **BLOCKED — no display and no Tkinter in the acceptance environment, and the optional pdf extra is not installed, so the PDF path could not run either.**
28. [ ] Reject one confident value and accept one `needs review` value, then **Save selected values** and
    confirm. The accepted value must be stored, the rejected one must still hold the previous value, fields
    the document did not mention must be unchanged, and the result message must name what was saved and what
    was not selected.
    → **BLOCKED — no display and no Tkinter in the acceptance environment, and the optional pdf extra is not installed, so the PDF path could not run either.**
29. [ ] Import a scanned PDF (an image with no text layer): the app must say it could not read the text and
    suggest typing the values in. It must not claim a successful parse and must not silently save anything.
    → **BLOCKED — no display and no Tkinter in the acceptance environment, and the optional pdf extra is not installed, so the PDF path could not run either.**
30. [ ] Import a DOCX whose skills are in a table: the table text must be read as rows. Import a damaged PDF
    and an encrypted PDF: each must be refused with its own message, no traceback, and no change to the
    profile. If a layout puts two columns on one line (for example a category on the left and prose on the
    right, as in "Python, SQL, Django    Built ETL pipelines"), the skills from that line must be offered as
    read but marked `needs review` and must start **unticked** — the app must not pre-select text it cannot
    tell apart from prose. A category written before a column gap ("Languages | Python, SQL") must be read
    like the colon form, with the category itself not offered as a skill.
    → **BLOCKED — no display and no Tkinter in the acceptance environment, and the optional pdf extra is not installed, so the PDF path could not run either.**
31. [ ] After any import (successful or refused), confirm the chosen file is unchanged, no copy of it was
    left beside the database or in the repository (`git status` stays clean), and the app never asks for a
    network connection or reports one.
    → **BLOCKED — no display and no Tkinter in the acceptance environment, and the optional pdf extra is not installed, so the PDF path could not run either.**

## Status choices, record times, and start-up diagnostics

32. [ ] Save a new job so it has no application record yet. Open **Update selected status**: the *New
    status* list must contain only `discovered`, `shortlisted`, `withdrawn`. Nothing in the list may imply
    a submission, an employer response, or a confirmation that has not happened. Confirm that opening the
    dialog does not by itself create a tracker record (close it, refresh, the job must still show
    `discovered` with no stored record).
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the states offered from a new record were read directly.**
    → **Automated coverage (2026-10-15): D4 (the chooser offers exactly the current status and its permitted moves and nothing else) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10–3.13), 38 checks per leg, run `38739493727` at `a530029`.
33. [ ] Shortlist the job (only possible on an explicit eligibility PASS), reopen the dialog, and check the
    list again: it must offer only the statuses the record may move to from `shortlisted`. For a
    `submission_attempted` record the list must include `submitted_unverified`, `confirmed`, `failed` and
    `unknown_status` but not `interview` or `response_received`; those appear only after `confirmed`.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the states offered after a submission attempt were read directly.**
    → **Automated coverage (2026-10-15): D1 and D4 (shortlisted through its own button, then the dialog reopened and its options read) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10–3.13), 38 checks per leg, run `38739493727` at `a530029`.
34. [ ] Close a record honestly: move an application to `withdrawn` with a note. Reopen **Update selected
    status** for it. The app must say the record is in a final state and must not offer a list of statuses
    at all. The stored note must still be shown in the tracker list, unchanged.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the states offered from withdrawn were read directly.**
    → **Automated coverage (2026-10-15): D8 (a record moved to 'withdrawn', the chooser then offers no change, the dialog explains that it is final and that nothing was changed, and the database is byte-identical afterwards) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10–3.13), 38 checks per leg, run `38739493727` at `a530029`.
35. [ ] Cancel the dialog with Escape and confirm with Return on the *Save status* button; both must work
    without a mouse. Pressing Escape must change nothing.
    → **BLOCKED — no display and no Tkinter in the acceptance environment.**
36. [ ] In the jobs tab, select a job and read the detail pane: it must show the local record times
    labelled as this app's own observations (first noted / last saved, in UTC), and must state that the
    source's publication or update date is not provided. Then save a change to the same job and confirm
    the *last saved* time moves while *first noted* stays the same.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the record times and their stability were read directly.**
37. [ ] Start the app with a damaged database (throwaway copy): `python -m career_agent --database
    "<copy of the database with garbage written over the first bytes>"`. The window must show a plain-language
    explanation naming a next step (restoring a verified backup), not a bare `file is not a database`, and
    must not print a filesystem path, candidate data, or a credential. The same text must appear, timestamped,
    in `logs/startup-diagnostics.log` beside the application data, owner-only on macOS/Linux.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the doctor and the read-only reports were run against the same copy.**
38. [ ] Confirm the diagnostic note is replaced, not appended, by running the failing start-up twice, and
    that its content is safe to share (no name, email, phone, employer, or local path).
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the note file was seen being written on a start-up failure and not written on a refusal.**
39. [ ] Insert an unknown status into a *throwaway copy* (`sqlite3 "<copy>" "UPDATE application_tracker SET
    status='ghost_status' WHERE listing_id='<id>';"`), then start the app against it: both lists must still
    render that row, showing the stored value with a clear "not recognised by this version" marker rather
    than crashing or silently showing a different status. **Update selected status** must refuse with an
    explanation, and the JSON export must still work and contain the stored value unchanged. Confirm the
    row is unchanged afterwards in `sqlite3`.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the record was refused at the storage layer with the row byte-identical afterwards.**
40. [ ] In a *throwaway copy*, damage a stored payload instead of a status:
    `sqlite3 "<copy>" "UPDATE job_listings SET payload='{\"listing_id\": 5}' WHERE listing_id='<id>';"`, then
    start the app against that copy. The jobs and tracker tabs must report "Saved record could not be read"
    with a plain explanation and no traceback, the profile tab must still load, and re-reading the row in
    `sqlite3` must show it byte-identical — a refused read must never repair, rewrite, or delete what is
    stored. Confirm the same holds after a restart, and that the app still starts and exits normally.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the damaged payload was refused at the storage layer with the file byte-identical.**

41. [ ] Start the app with a database inside a folder that does not exist, for example
    `python -m career_agent --database "$HOME/alpha-test/not-created-yet/db.sqlite3"`. The message must say the
    folder does not exist and tell you to create it or choose another path. It must **not** say the database may
    be damaged and must **not** tell you to rename, restore, or delete a file — nothing was created and nothing
    is damaged. Then create the folder and start again: the app must open normally. (The automated tests cover
    this message; this step confirms what the desktop window actually shows.)
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the terminal reports were run against that path and created nothing.**

## Follow-ups, matching, sources and the worker (added 2026-10-15)

These steps cover the surfaces added after the original checklist was written. Each one is listed here
because an automated test cannot confirm what a real window shows: the tests exercise the handlers and
the store behind the widgets, and the checklist is where the widgets themselves are seen.

42. [ ] Open the new **Follow-ups** tab. It must explain that a follow-up is a day you plan to act on, not
    a status, and that nothing there contacts anybody.
    → **BLOCKED — the tab is a window; the same wording is what the terminal follow-up report prints.**
43. [ ] With an application selected in the **Application tracker** tab, set a follow-up: pick a day a few
    days ahead, add a note, press **Set the day for the selected application**. The row must appear in the
    Follow-ups list with the day, the note, and "in N day(s)"; the status shown must be unchanged, and the
    status bar must say the application's status was not changed.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the day and note were stored and listed from the terminal with the note text.**
    → **Automated coverage (2026-10-15): H1–H2 (with an application selected on the **Application tracker** tab its first follow-up day **is** recordable — the refusals that made that impossible from anywhere in the window are what this check found, see D17 — the new row carries the day, the note and "in 2 day(s)", and the stored status and the confirmation flag are untouched) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 76 checks per leg, run `38762008724` at `5b291a7a`.**
44. [ ] Set a day in the past for a second application (for example yesterday). It must sort above the
    future one and read "N day(s) overdue". Confirm the summary line counts overdue and due-today
    separately, and that the **Application tracker** tab still shows the same statuses as before.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the terminal list printed the overdue day above the future one and led with the overdue count.**
    → **Automated coverage (2026-10-15): H3–H4 (days computed from fixed offsets read "3 day(s) overdue", "due today" and "in 20 day(s)", the list is ordered by day, the summary leads with "1 overdue, 1 due today: 2 application(s) need a look.", and every application is still `discovered` and unconfirmed) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 76 checks per leg, run `38762008724` at `5b291a7a`.**
45. [ ] Type something that is not a date ("next tuesday") and press the set button. The app must refuse
    with a message naming the YYYY-MM-DD form, and the stored record must be unchanged (check with
    `python -m career_agent --follow-ups`, or by re-reading the row).
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the same date shape rejects it with the stored day unchanged.**
46. [ ] Press **Clear the selected follow-up** and decline the confirmation: nothing may change. Press it
    again and accept: the day and note must disappear, while the application, its status and its activity
    history stay exactly as they were.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; clearing the follow-up was executed at the storage layer.**
    → **Automated coverage (2026-10-15): H5 (a day is moved from its own row, a declined clear leaves the day and its row in place, and an accepted clear removes the day and the note, leaves the status alone, empties the fields and takes the row out of the list) plus the stored-activity comparison that `tests/test_desktop_handlers.py::FollowUpTabTests::test_clearing_a_follow_up_asks_first_and_keeps_the_application` now makes: two recorded history entries are compared before and after both answers, because the confirmation says the history stays as it is. The workflow drove the window half on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 76 checks per leg, run `38762008724` at `5b291a7a`.**
47. [ ] Press **Export to a calendar file**, choose a name, and open the saved `.ics` in a real calendar
    application on this OS. It must import without an error dialog, show an all-day event on each
    follow-up day, name the employer and role, and contain no attendee and no link. Then export again to
    the same name and decline the replace prompt: the existing file must be untouched.
    → **BLOCKED — no calendar application in this environment; the file half was written and inspected (637 bytes, owner-only, no attendees).**
48. [ ] In **Jobs & eligibility**, press **Evaluate** for a saved listing. The report must show the
    eligibility lines first and then a **MATCHING (explainable, and never a prediction)** section with one
    line per factor, an overlap percentage *with how much was known*, and the sentence that it is not a
    probability of being hired. A listing you do not meet the stated requirements for must say it is
    blocked from the recommendation while still showing the comparison.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the report's factors and disclaimer were assembled directly from the same calls.**
49. [ ] Run `python -m career_agent --sources`. It must print the gate as NOT passed, name each reviewed
    source with its state, evidence and conditions, print "applying for jobs here: not permitted" for
    every one of them, and say that zero adapters are built in. Nothing must be contacted.
    → **PASS — gate NOT passed, no source permitted to run discovery, adapter count 0.**
50. [ ] Run `python -m career_agent --follow-ups` and `--calendar-to <a new path>`. The report must list
    the recorded days with an explicit "no status was changed and nothing was sent"; the export must
    write a file (owner-only on POSIX: `ls -l` shows `-rw-------`) and must refuse a second export to the
    same path with a message suggesting a dated name.
    → **PASS — the follow-up was listed and the .ics written owner-only, with the second run refused.**
51. [ ] Open the **Background tasks** tab and confirm three tasks are listed: `daily-backup` (23:30),
    `scheduled-discovery` (00:00, 12:00) and `follow-up-digest` (09:00), all Asia/Kolkata. Run
    `python -m career_agent --worker` in a terminal, wait for the digest's turn (or start it after 09:00
    with a stored follow-up that day), and confirm the attempt's detail in **Recent attempts** names the
    due application and does not change any application's status.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the three tasks were seeded and read back with their times and zones.**
    → **Automated coverage (2026-10-15): I1–I2 and I8 (the schedule starts empty with the tab saying nothing is scheduled and no worker holds the lease; the defaults are added through the tab, created, enabled, with a next run, and adding them again creates nothing and leaves the stored tasks untouched; using the tab takes no lease, records no attempt and writes no `task.run_*` or `worker.*` event). The three tasks' names, times and timezone are asserted at two other levels: `tests/test_handlers.py::DefaultTaskTests::test_the_defaults_are_the_product_cadence_and_a_daily_backup` (all three ids in order, `00:00, 12:00`, `23:30`, the digest cadence, and every task in `Asia/Kolkata`) and `tests/test_desktop_handlers.py::SchedulerTabTests::test_the_tab_lists_the_tasks_and_says_no_worker_holds_the_lease` (the cells the tab itself shows: `00:00, 12:00`, `23:30`, `09:00` and the zone for every row). The workflow drove its half on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 76 checks per leg, run `38762008724` at `5b291a7a`.**
    → **Automated coverage (2026-10-16): I9 (a task whose schedule nobody ran is added with a three-day-old clock, the tab is refreshed through its own button, and the summary is required to report the occurrences the schedule walked past while nothing was running, with the count the schedule holds, the sentence that nothing is catching up on them, and no lease, attempt or event recorded by the read) drove this through the real window on the five display-backed CI legs; the same read is asserted at the worker level (`tests/test_worker.py::StatusTests`, eight tests) and on the command line (`tests/test_cli_worker.py::WorkerStatusCommandTests::test_the_report_says_what_the_schedule_walked_past_while_nothing_ran`). The harness now declares 77 checks per leg; this line was added after the run that produced it is cited in the update above.**
52. [ ] With the app open, pause `follow-up-digest` in the Background tasks tab, confirm it asks first and
    that pausing keeps its times and its history, then resume it and confirm the next run is scheduled.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; a task saved as paused read back paused with its times intact.**
    → **Automated coverage (2026-10-15): I3–I7 (pausing asks first and a declined confirmation changes nothing; an accepted pause keeps the task's name, kind, times and timezone and its recorded history, and its row reads "paused"; the paused task is still paused after the window is closed and opened again; resuming schedules the next run ahead of now and replays no missed occurrence; and a task whose record was deleted behind the window is reported rather than written back) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 76 checks per leg, run `38762008724` at `5b291a7a`.**

## Moving data with the JSON export and import (added 2026-10-15)

53. [ ] On a disposable copy of the app (`CAREER_AGENT_HOME` pointed at a temporary folder), open **Data
    safety** and press **Export data to a JSON file**. Choose a new name. The status line must report what
    was written, and on POSIX `ls -l` must show `-rw-------`. If the platform's save dialog offers to
    replace that name on a second press, decline it and confirm the first file is unchanged. (Refusing an
    existing file outright is the *command line* rule — see step 57 — because the save dialog asks on the
    window's behalf, differently on each platform.)
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the export ran from the terminal.**
54. [ ] Add nothing, then press **Import an exported file (JSON)** and choose that same file. A dialog must
    appear describing the plan (listings that would be linked, the profile, the application record) and
    must not have written anything yet. Press **No**: nothing may change and the status line must say the
    import was cancelled.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the plan printed from the terminal with nothing added.**
    → **Automated coverage (2026-10-15): E8 and E9 (the plan is shown naming what is already stored before anything is written; declining it leaves the database byte-identical and the status line reports the cancellation) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10–3.13), 38 checks per leg, run `38739493727` at `a530029`.
55. [ ] Press **Import an exported file (JSON)** again, choose the same file and press **Yes**. The status
    line must report the result including `left 1 already-stored listing(s) as they were`, the Jobs tab
    must still show exactly one listing with its original first-seen time, and the Tracker tab must show
    the record at `discovered` with its follow-up day and its activity entry.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the terminal import applied once and reported nothing to add on a repeat.**
56. [ ] Without editing anything, export the profile-carrying file from a *different* disposable database
    (`--export-to`), import it into the database that already has a profile, and confirm the dialog says
    your stored profile is kept and that the profile is unchanged afterwards.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the terminal import into an empty database reported every kind it added.**
57. [ ] In a terminal, on two disposable databases: `python -m career_agent --database a.sqlite3
    --export-to out.json`, then `--database b.sqlite3 --import-from out.json` (plan only — nothing must be
    created) and finally the same command with `--yes`. Then run `--import-from out.json --yes` again and
    confirm the second apply reports the listing was left as it was rather than adding a duplicate. Run
    `--export-to out.json` a second time and confirm it refuses with status `2` and leaves the file alone.
    → **PASS — export, plan, apply, idempotent repeat and the refusal to overwrite were all observed.**
58. [ ] Point `--import-from` at a text file that is not an export (for example `{}`), at a path that does
    not exist, and at a database path that does not exist. Each must refuse with status `2`, name the
    reason in plain language, and create no file.
    → **PASS — each malformed or missing input was refused with status 2 and no file created.**

59. [ ] Set a follow-up on an application (say three days from today), then change that application's
    status through **Update status** and confirm afterwards, in the **Follow-ups** tab, that the day and
    the note are still listed — and that the row still shows the new status beside them. Then clear the
    follow-up and confirm the application, its status and its history are untouched.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the reminder survived a status change at the storage layer.**
60. [ ] While a follow-up is recorded, edit the listing (save it again from the Jobs tab) and confirm the
    reminder survives that too, then confirm the **Follow-ups** tab is what changes, not the application.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the reminder survived a listing re-save at the storage layer.**

61. [ ] Open the **Next actions** tab with at least one saved listing. Select its row on the Jobs tab, press
    **Add a preparation item**, and add one item with a day of yesterday and one with no day at all. Both
    must appear at the top of the list (the overdue one first, the undated one after the dated items), and
    the application's status must be unchanged everywhere in the window.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the terminal list printed the order and the preparation and round counts.**
    → **Automated coverage (2026-10-15): H8–H9 (a preparation item with yesterday's day is added through its own dialog, whose kind chooser offers the documented kinds, and lists as "<day> (1 day(s) overdue)" naming the item and the application; an item with no day lists as "No day set" rather than being hidden, and the reminder recorded earlier appears in the same list). The ordering the step states is asserted elsewhere, on the list standing alone: `tests/test_preparation.py::ActionTests` (most-overdue-first; the oldest promise first across kinds for overdue work, with the kind breaking same-day ties; an appointment outranking a chase on the same day; and the order not depending on the order things were passed in) and `tests/test_desktop_handlers.py::NextActionsTabTests::test_the_list_shows_the_three_kinds_with_the_record_each_row_names` (the exact row order across all three kinds). The workflow drove its half on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 76 checks per leg, run `38762008724` at `5b291a7a`.**
62. [ ] Select the item and press **Mark the selected item done**. The row must leave the list, the status
    line must say the application's status was not changed, and the tracker row on the **Application
    tracker** tab must be exactly as it was.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; completing an item was executed at the storage layer.**
    → **Automated coverage (2026-10-15): H10 (the row leaves the list, the window says "Done: <title>. The application's status was not changed." and the application is still `discovered` afterwards) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 76 checks per leg, run `38762008724` at `5b291a7a`.**
63. [ ] Press **Record an interview round**, choose a stage, a day (tomorrow) and a mode, and save. The round
    must appear in the list above the preparation items and must read "in 1 day(s)"/"tomorrow" rather than
    as something that has already happened. Then select it, press **Record the selected round's outcome**,
    pick "You felt it went well", save, and confirm the outcome text appears in the row and that no status
    changed.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the round's day, its awaiting state, the recorded outcome and the unchanged status were all verified.**
    → **Automated coverage (2026-10-15): D2–D3 (stage, day and mode chosen through the dialog; the round is stored as awaiting and the application's status is left alone) — **partial**: whether the round also appears in the other list views is not checked here. The rest was driven through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10–3.13), 38 checks per leg, run `38739493727` at `a530029`.
64. [ ] Select a **follow-up** row and press **Delete the selected record**. It must explain that a follow-up
    day is cleared on the Follow-ups tab rather than deleted here, and nothing may change.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; clearing the plan was executed at the storage layer.**
    → **Automated coverage (2026-10-15): H11 (selecting a reminder row and pressing **Delete the selected record** raises "Follow-up days are cleared, not deleted", completes no preparation item, and leaves the reminder, its status and the list exactly as they were) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 76 checks per leg, run `38762008724` at `5b291a7a`.**
65. [ ] Select an interview round and press **Delete the selected record**, answering **No** first and then
    **Yes**. Nothing may be removed on the first answer; the second must remove only the round and say so.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; deleting a round was executed at the storage layer.**
66. [ ] In a terminal with the app closed: `python -m career_agent --next-actions` and
    `python -m career_agent --interviews`. Both must print the same records the window shows, say the report
    is read-only, and name the number of records; running `--next-actions --interviews` together must be
    refused by the argument parser with status 2.
    → **PASS — both reports ran, and the parser refused the two flags together with status 2.**
67. [ ] Point `--next-actions` at a path that does not exist (`--database /tmp/nothing.sqlite3`): it must say
    there is no database yet and create no file.
    → **PASS — exit 0, no database yet, and no file created.**

## Work history and education (added 2026-10-15)

The records behind the profile's summary fields, on their own tab and on the command line. Everything here
is a plan the person wrote and nothing contacts an employer.

68. [ ] Open the **Work history & study** tab. Add a current role (employer, job title, start date, tick
    **This is my current role**, type *Full time*) and confirm it appears at the top of the employment list
    reading `start - present`, that the summary line under the forms counts it, and that the status line
    names what was saved.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the current role was stored and read back.**
    → **Automated coverage (2026-10-15): G4 (the role typed into the form, **This is my current role** pressed through the checkbox's own widget, stored as current with no end date, and the status line naming what was saved) and G8 (the row the list shows stops marking it current once the flag is unticked) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 46 checks per leg, run `38747830528` at `e939260`. What was not checked here: whether the row's own text reads `start - present`, and whether the summary line counts the role as a person reads it.**
69. [ ] Add an ended role with an end date before its start date. It must be refused with a dialog naming
    both dates, the list must not change, and the employment count must not move. Then add a role that has
    ended but whose end date you do not know: it must be accepted, list as `end date not recorded`, and the
    summary line must say that no duration is counted for it.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the refusal and the ended role's period were verified directly.**
    → **Automated coverage (2026-10-15): G2 (an end date before its start is refused, the dialog names both dates, and the database does not move) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 46 checks per leg, run `38747830528` at `e939260`. The ended-role-with-no-known-end-date half was verified directly at the storage layer, not in this run.**
70. [ ] Add a role with a start date written as `1 April 2023`. It must be refused with a message naming the
    `YYYY-MM-DD` shape, and nothing may be written.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the form's date shape was checked directly (accepts YYYY-MM-DD, rejects '1 April 2023').**
    → **Automated coverage (2026-10-15): G3 (`1 April 2023` is refused naming the `YYYY-MM-DD` shape and nothing is stored) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 46 checks per leg, run `38747830528` at `e939260`.**
71. [ ] Select the role you added, change its job title, press **Save changes to the selected role**, and
    confirm the list shows the new title. Then press **Delete the selected role**, answering **No** first
    (nothing may change) and then **Yes** (only that role may disappear, and the status line must say what
    was deleted).
    → **BLOCKED — no display and no Tkinter in the acceptance environment; editing and deleting a role were executed at the storage layer.**
    → **Automated coverage (2026-10-15): G7 (the role is loaded into a form emptied first, so the values read back can only have come from the record, its title is changed and saved over it, and the record count does not move) and G8 (the current-role flag is unticked and an end date saved) drove the edit half of this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 46 checks per leg, run `38747830528` at `e939260`. **partial**: the delete button and both answers to its confirmation are not driven by the acceptance run.**
72. [ ] Add an education record ticking **Still studying** with no dates, and confirm it lists as
    `start not recorded - ongoing`. Then add one with a completion date and no start date, and confirm it
    lists `start not recorded - <date>` after the ongoing one.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the ongoing record's text and its place in the list were verified directly.**
    → **Automated coverage (2026-10-15): G5 (a qualification with **Still studying** ticked and no dates is stored as ongoing with both dates unset and is listed as ongoing) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 46 checks per leg, run `38747830528` at `e939260`. **partial**: the record with a completion date and no start date, and its place after the ongoing one, were verified directly rather than in this run.**
73. [ ] Add an education record with a completion date while **Still studying** is ticked. It must be
    refused, and the list must not change.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the refusal was verified directly.**
    → **Automated coverage (2026-10-15): G6 (a completion date with **Still studying** still ticked is refused, the window explains the contradiction, and nothing is stored) drove this through the real window on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 46 checks per leg, run `38747830528` at `e939260`.**
74. [ ] Without the window open, run `python -m career_agent --history`. It must print the same records in
    the same order, state the months covered without calling them years of experience, and say the report
    is read-only.
    → **PASS — the records, the months sentence and the read-only closing line all observed.**
75. [ ] Run `python -m career_agent --add-role "Sandbox Systems" --title "Data Engineer" --start 2023-04-01
    --current`. It must add the record and report what was saved. Then run the same command again: it must
    refuse the duplicate, write nothing, and exit with status 2 (`echo $?` on macOS/Linux).
    → **PASS — the role was added and the duplicate refused with status 2.**
76. [ ] Run `python -m career_agent --add-study "IIT Delhi" --qualification "B.Tech" --completed 2019-05-31`
    and confirm it appears in the window after pressing the tab's refresh path (switch tabs or reopen the
    window).
    → **PASS — the duplicate was refused and a genuinely new qualification was added.**
77. [ ] Save a profile, add at least one role and one qualification, then press **Delete profile** and read
    the confirmation before answering. It must name how many employment and education records will be
    deleted with the profile, and answering **Yes** must remove all of them, leave the job listings and
    applications untouched, and empty the Work history & study tab.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the deletion was executed at the storage layer.**
78. [ ] Export to JSON (Data safety tab) and open the file in a text editor: it must contain
    `"format_version": 2` and top-level `work_history` and `education` arrays holding the records you
    entered. Import it into a second, empty database with `--import-from ... --yes` and confirm the records
    arrive with the same dates. Import it into the *first* database (which still holds its records) and
    confirm the plan says the stored records are kept and nothing is duplicated.
    → **PASS — the keys, the format version and the record counts were read from the file.**
    → **Automated coverage (2026-10-15), added to the PASS above:** E2 (the format version and the top-level `work_history`/`education` arrays match the stored records) and E5, E8 (import into an empty database, then a repeat import that says the stored records are kept and adds nothing), run `38739493727` at `a530029`.
## Progress reporting (added 2026-10-15)

The report adds up records that already exist. Nothing here fetches, estimates or projects, and every manual
check below is about what the window and the terminal *say*, which unit tests cannot confirm.

79. [ ] Open the **Application tracker** tab on a database with several applications recorded. Under the
    activity list there must be a summary line naming how many applications are recorded as sent and how
    many have a recorded reply - and, below five applications, it must not show a percentage at all; it must
    say there are too few to report a rate.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the terminal report prints the same lines.**
80. [ ] Press **Progress report**. A read-only dialog must open with the counts, the rates, the timing, the
    period comparison, a section listing what this app cannot measure, and the "How to read this" caveats.
    It must close with **Close**, with Escape, and with Return, and nothing in the window may change while it
    is open.
    → **BLOCKED — no display and no Tkinter in the acceptance environment.**
81. [ ] Resize the report dialog and scroll it: the **Close** button must stay visible at the bottom no
    matter how long the report is.
    → **BLOCKED — no display and no Tkinter in the acceptance environment.**
82. [ ] Read the "What cannot be measured here" section and confirm it says an offer cannot be stored
    anywhere in this app. Confirm no line anywhere in the dialog reads "0 offers" or "0%" for something the
    app cannot observe.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the same section is printed by the terminal report, with no '0 offers' line.**
83. [ ] With fewer than five applications recorded, confirm every rate line says "No rate is shown" and gives
    the floor as the reason, and that the counts above them are still correct.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the terminal report prints 'No rate is shown' with the floor as the reason.**
84. [ ] Close the window, then run `python -m career_agent --analytics`. The terminal report must contain the
    same numbers the dialog showed, must name its denominators, must print the five caveats, and must end by
    saying the report is read-only.
    → **PASS — counts, denominators, caveats and the read-only ending, re-run after defect D1 was fixed.**
85. [ ] Run `python -m career_agent --analytics --database /tmp/nothing-here.sqlite3`: it must say there is no
    database yet, create no file, and exit with status 0. Then confirm `--history --analytics` together are
    refused by the argument parser with status 2.
    → **PASS — no database yet with status 0 and no file created; the combined flags refused with status 2.**

## Email and calendar interfaces (added 2026-10-15)

There is no email account and no calendar account, and none can be enabled. These checks are about what the
window and the terminal *say* and about what does **not** happen: that a draft stays text, that a preview
writes nothing, and that the only thing able to perform an operation is a named local mock that contacts
nothing. Only a real machine with real mail/calendar clients open can show that nothing was sent and no
account was touched, which is why they are here and not in the suite.

86. [ ] Open the **Follow-ups** tab. It must offer **Preview the calendar export** and **Draft a follow-up
    email** beside the existing controls, and there must be no button, menu item or setting anywhere in the
    window that connects an account, sends a message, or invites anybody.
    → **BLOCKED — the tab is a window; the terminal equivalents ran and the shipped code was scanned for account and socket use.**
    → **Automated coverage (2026-10-15): H7 — **partial**: both buttons are pressed on the tab, the preview and the draft are the read-only dialogs they claim to be ("no invitation", "no attendee is invited", "No email account is connected", "nothing here can send anything"), no file is written while they are open and both status lines say nothing was sent. **Still open here:** whether some other control in the window could connect an account; the shipped-code scan in step 15 covers the code, not the widgets. That half ran on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 76 checks per leg, run `38762008724` at `5b291a7a`.**
87. [ ] Press **Preview the calendar export** with at least one follow-up recorded. A read-only dialog must
    list each event as `<day>: Follow up: <role> at <employer>  [follow-up-<id>-<day>@ai-career-agent.local]`,
    state that nothing has been written yet and that every event is an all-day entry with no attendee, and
    close with **Close**, Escape and Return. Before and after, the folder holding the database must contain
    no new `.ics` file.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the terminal preview listed the same event and wrote no file.**
    → **Automated coverage (2026-10-15): H7 and the window's own dialog at the stub level: the preview counts the reminders the tab lists, states that nothing has been written yet and that no attendee is invited, and the folder holding the database gains no file; `tests/test_desktop_handlers.py::IntegrationSurfaceTests::test_the_preview_lists_the_events_and_writes_nothing` now asserts the whole per-event line the dialog draws (`2026-10-17: Follow up: AI Intern at Example Inc  [follow-up-j1-20261017@ai-career-agent.local]`), and `tests/test_cli_integrations.py` asserts the same day-prefixed line on the terminal preview. Still not asserted anywhere: whether the dialog closes on Escape and Return. The workflow drove its half on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 76 checks per leg, run `38762008724` at `5b291a7a`.**
88. [ ] Press **Draft a follow-up email** with no row selected: it must ask you to select a reminder, and
    open nothing. With a reminder selected, the dialog must show the subject, the full body, `To: NOT
    SUPPLIED`, `Status: DRAFT ONLY`, an `Operation id: email-...`, the "Missing, and not guessed" line for
    the recipient, and a line saying nothing was sent and nothing was created.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the terminal refusals and the full draft text were observed.**
    → **Automated coverage (2026-10-15): H7 and the same surface at the stub level, where the complete field set is asserted: `tests/test_desktop_handlers.py::IntegrationSurfaceTests::test_the_draft_carries_the_stored_context_and_states_that_nothing_was_sent` checks the subject, a line of the body, `To: NOT SUPPLIED`, `Status: DRAFT ONLY`, `Missing, and not guessed:`, the operation id and the "Nothing was sent and nothing was created" line, and `...::test_the_draft_refuses_with_nothing_selected_and_opens_nothing` checks that the button with no row selected explains itself and opens nothing. The workflow drove its half - both dialogs opened on the real window, no file written, both status lines saying nothing was sent - on five display-backed CI legs (Linux under Xvfb, Windows 2025 and macOS 26, CPython 3.10 and 3.13), 76 checks per leg, run `38762008724` at `5b291a7a`.**
89. [ ] While that draft dialog is open, check the application's status, its follow-up day and its note, and
    the reminders list: none may change. Select and copy the draft text out of the dialog by hand; nothing
    must be written to disk by copying.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the read-only property of the preview and the plan was asserted by the commands themselves.**
90. [ ] With a mail client configured on this machine, draft a follow-up and watch for any mail window,
    toast, outbox entry or "draft saved" notice. There must be none: this app cannot reach a mail client.
    → **BLOCKED — there is no mail client on this machine; this is a real-desktop check.**
91. [ ] Run `python -m career_agent --integration-status` (add `--database /tmp/nothing-here.sqlite3` to be
    sure). It must print that nothing is enabled, list the seven conditions a real provider would need, end
    by saying nothing was sent or created, exit with status 0, and create no database file.
    → **PASS — nothing enabled, the seven conditions listed, exit 0, and no database created.**
92. [ ] Run `--preview-calendar-export`, then `--calendar-to <file>.ics`, and compare: every UID and summary
    in the written file must be one the preview listed. Open the `.ics` in a text editor and confirm it
    contains no `ATTENDEE`, no `ORGANIZER` and no URL, and that the file is owner-only on this platform.
    → **PASS — the written file's UID and summary match the preview; owner-only, no attendee, organizer or URL line.**
93. [ ] Try the refusals: `--draft-follow-up <unknown id>`, `--recipient a@b.example` on its own, `--at 10:30`
    without `--timezone`, `--minutes 30` without `--at`, and `--mock-ledger <path>` on its own. Each must
    print a reason, say nothing was written (or created), exit with status 2, and write no file.
    → **PASS — all five refusals printed their reason, wrote nothing and exited 2.**
94. [ ] Run `--record-follow-up <listing id>` with no mock named: it must print `[disabled]`, say nothing was
    sent or created, and exit 2. Then run it with `--mock-ledger <file>` twice: the first run must print
    `[completed]` and record exactly one operation in the file, the second must print `[duplicate]` and add
    nothing. While both runs happen, watch the machine's network activity and any calendar client: there must
    be no connection to a mail or calendar provider and no new event in any calendar.
    → **PASS for the disabled refusal, the recorded operation and the duplicate; BLOCKED for watching the machine's own network and calendar (no graphical session here).**

## Reporting on a database the app cannot fully read (added 2026-10-15)

Make a **copy** of a database for these steps and edit the copy with `sqlite3` or DB Browser; never edit the
file the app is using. Set one tracker row's `status` to a value no version of this app knows (for example
`UPDATE application_tracker SET status = 'sent-somewhere';`). Then:

95. [ ] Open the window on that copy and use **Progress report**: the dialog must show the app's own refusal
    sentence ("The saved status '…' is not one this version of the application recognises…"), not a raw
    traceback, not an empty report and not a crash. The window must stay open, and the status line must not
    claim anything was repaired.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the same refusal sentence was observed in the terminal reports.**
96. [ ] Run `career-agent --doctor --database <copy>`: it must exit `1`, print
    `PROBLEM: 1 stored record(s) cannot be read by this version`, name the table (`application_tracker`) and
    the record (`j1`), and end with `Nothing was changed or repaired by this check.` Compare the file's
    SHA-256 before and after: it must be identical.
    → **PASS — exit 1, the problem line, the table, the record and the unchanged SHA-256.**
97. [ ] Run `--analytics` and `--follow-ups` against the copy: each must exit `2` with the sanitised refusal
    and a pointer to `--doctor`. Run `--history`: it must still run and exit `0`, because it does not read
    that record. On macOS and Windows, confirm no crash report dialog appears for any of the four.
    → **PASS on Linux (both reports refused with status 2, the history report still ran); the macOS and Windows clause is BLOCKED — those machines are not available.**
98. [ ] Open a *healthy* database and run `--doctor`: it must print
    `Every stored record could be decoded by this version.` and exit `0` — the check must not turn a normal
    file into a warning. Then run `--doctor` on a copy whose `PRAGMA user_version` is set to `5`: it must
    report version 5, say its records are not decoded here, exit `0`, and leave the recorded version at 5.
    → **PASS — the healthy file reports no problems and exits 0; the version-5 copy is reported by version, not decoded, and left at 5.**

## Record results

### 2026-10-15 — headless Linux execution (CPython 3.11.2, no display, no Tkinter)

- **Executed:** every step that does not need a window, plus the data half of the steps whose rule can be
  driven directly. Full record, with the command and the observed result for each step, in
  `research/local-alpha-manual-acceptance-run-2026-10-15.md`.
- **Result:** 22 of the 98 numbered steps passed here (15, 22, 23, 49, 50, 57, 58, 66, 67, 74, 75, 76, 78,
  84, 85, 91, 92, 93, 96, 97, 98, and 94 with one half blocked); **76 are BLOCKED**, all of them for a named
  missing capability, overwhelmingly the absent display and Tkinter build; none failed. Six of the seven
  preconditions passed; the Tkinter precondition is the blocked one.
- **Defects found and fixed by this run:** D1 the progress report counted a round that has not happened as one
  whose outcome was recorded; D2 four commands reported a readable database with one unreadable record as
  "the application stopped while starting up", exit 3, with a start-up note; D3 an import into such a database
  wrote part of the file and then refused, saying nothing had been written; D4 a refusal claimed a draft had
  been written when nothing was on disk. Each has a regression test that fails on the behaviour it replaced.
- **Still to do before the checklist can be called passed:** execute it on a real desktop (Linux first, then
  macOS and Windows), install the optional pdf extra and run the résumé steps, and repeat the whole checklist
  from a packaged build.

### 2026-10-15 — follow-up: capability probe again, scripted desktop smoke test, cross-platform CI

**No numbered step changed status.** The 98 steps above are exactly as the previous entry left them: 22 PASS,
76 BLOCKED, 0 FAIL. Everything in this subsection is *automated* evidence, gathered on GitHub-hosted runners
and on this machine, and none of it closes a step that needs a person at a keyboard.

**Capability probe, executed again on 2026-10-15 (commands, not assumptions).**

| Probe | Result |
|---|---|
| `sudo -n true` | **succeeds** — the earlier entry's "not root" is superseded, so the environment was re-probed with install privileges available |
| `apt-get update` after switching the sources to `https://` (`sed` on `/etc/apt/sources.list.d/debian.sources`), then `apt-get install -y xvfb python3-tk x11-utils xauth` | **impossible**: port 80 is refused and the HTTPS handshake to `deb.debian.org` is terminated by the sandbox's network policy (`E: Unable to locate package xvfb`, `E: Package 'python3-tk' has no installation candidate`). Only `github.com`, `codeload.github.com`, `api.github.com`, `registry.npmjs.org`, `pypi.org` and `files.pythonhosted.org` are reachable |
| `python3 -c "import tkinter"` | `ModuleNotFoundError: No module named 'tkinter'` (unchanged) |
| Full PyPI project index scanned (914,223 names) for a distribution shipping an X server or a Tk-enabled interpreter, and `registry.npmjs.org` searched for a prebuilt `Xvfb` | none: every hit is a wrapper that downloads a binary from a host this environment cannot reach (`pytest-xvfb`, `@cypress/xvfb`, `@wdio/xvfb`, `portable-python`, …) |
| GitHub release assets (`objects.githubusercontent.com`) | TLS-blocked, so a prebuilt `Xvfb` (for example `shkolnik/xvfb-static`, whose binaries exist only as release assets) cannot be downloaded |
| `sudo mount -o bind,ro SRC DST` | **works** — a genuinely read-only filesystem can now be arranged here, which is used below |

**Conclusion:** no real Tk widget can be created or interacted with on *this* machine, so every GUI step above
stays **BLOCKED** here. The window is instead exercised on runners that have a display, by the scripted entry
point below.

**New automated evidence (not manual GUI acceptance).**

| Platform / Python | Exact command | Observed | Status | Kind |
|---|---|---|---|---|
| Linux (Debian 12), CPython 3.11.2 | `python scripts/desktop_smoke_test.py` (this machine: no `tkinter`, no display) | `RESULT: BLOCKED — this Python has no tkinter module: ModuleNotFoundError("No module named 'tkinter'")`, exit **2**, no check reported as passed | **BLOCKED** | automated smoke test |
| Ubuntu runner, system CPython, `xvfb` + `python3-tk` | `env -u DISPLAY python scripts/desktop_smoke_test.py`, then `xvfb-run -a python scripts/desktop_smoke_test.py` | first run must exit 2 with `RESULT: BLOCKED`; second must exit 0 with `RESULT: PASS` | see `research/cross-platform-desktop-ci-evidence-2026-10-15.md` | automated smoke test |
| Windows / macOS runners, CPython 3.10 and 3.13 | full suite, wheel install outside the checkout, `--version`, `--doctor` (missing database → 0, file that is not a database → 1, read-only report → 2), schema creation and cross-process persistence, backup/restore that replaces data, export/import into a second database, discovery invariants, minimal Tk widget lifecycle, `python scripts/desktop_smoke_test.py` | recorded per job in the same report; a runner without a display session reports the window as BLOCKED and is annotated rather than counted as covering it | see the report | automated, per operating system |
| Ubuntu runner, CPython 3.13 | `pip install ".[pdf]"`, then the résumé module with the extra (`OK`, no skips) and without it (12 PDF cases skip) | recorded in the same report | see the report | automated |

**What the scripted smoke test does and does not prove.** It builds the real window against a disposable
synthetic database, checks the title, the minimum size, the nine tabs in order, that every tab was built, the
main lists' columns, that the status line names the disposable database, that the created file holds the
current schema, that every tab can be selected with a rendering pass, that each affected tab's read-only
**Refresh** button can be pressed through Tk's own command dispatch, that the summaries fill, that the event
log is written beside the disposable database, that closing releases it and the folder can be deleted, and
that the person's own database was neither created nor modified. The tab added on 2026-10-16 (**HR contacts**) is
covered by the tab list, the refresh press and the focus walk, but has no numbered steps of its own here: a
person reading this checklist should treat it as NOT TESTED by hand. The script asserts nothing about pixels,
layout or dialog wording, and it does not press anything with a mouse — every numbered step above that needs a human at
the window therefore stays **BLOCKED**, and passing it must never be recorded as a passed step.

**PDF steps 24–31 (unchanged).** They are window steps: the import dialog is where a file is chosen and where
each proposed value is accepted or rejected. The optional extra is now installed and exercised on three
operating systems in CI (the résumé module finishes with a bare `OK` there, and skips all twelve PDF cases
without it), so the *reader* half is continuously covered — but steps 24–31 need the window and stay
**BLOCKED**.

**Defect found by this follow-up, and fixed.** D5: a database that is intact but cannot be *written* (a
read-only file, a read-only folder, a read-only filesystem, a lock) was refused as
`this database file could not be read`, with advice to restore a verified backup over it — a read described
for a write, on a file nothing had written to, with a remedy that would fail identically. Reproduced on a
read-only file, a folder at mode `555` and a read-only bind mount; the refusal now says the database could
not be written to and still exits 2 having changed nothing. `tests/test_damaged_records.WriteRefusalTests`
fails on the old wording; before/after transcripts are in
`research/cross-platform-desktop-ci-evidence-2026-10-15.md`.

**Read-only filesystem case, now executed** (the release audit previously recorded it as unavailable): a
database on a `bind,ro` mount is read normally by `--doctor`, `--analytics`, `--follow-ups` and `--history`
(exit 0, doctor exit 1 solely because start-up notes cannot be written there), a backup and an export *out* of
that location succeed, every write *into* it is refused with exit 2, and the file's sha256 is identical before
and after every command.

### 2026-10-15 — second follow-up: the platform legs run green, and what they cost

**No numbered step changed status.** The 98 steps are exactly as the two entries above left them: 22 PASS,
76 BLOCKED, 0 FAIL. Everything below is automated evidence from GitHub-hosted runners plus commands re-run on
this machine; none of it is a person at a window, and none of it closes a step that needs one. The full record,
with the commands, the annotations and the transcripts, is in
`research/cross-platform-desktop-ci-evidence-2026-10-15.md`.

**Capability probe, re-run (commands, not assumptions).** `uname -a` → Debian GNU/Linux 12, kernel 6.1.158+;
`python3 -VV` → 3.11.2, and no 3.10/3.12/3.13 interpreter exists here; `python3 -c "import tkinter"` →
`ModuleNotFoundError`; `DISPLAY` unset; `command -v Xvfb xvfb-run Xephyr Xorg weston` → none;
`sudo apt-get install -y python3-tk` → *no installation candidate* (only GitHub, PyPI and npm hosts answer from
this sandbox); `python3 scripts/desktop_smoke_test.py` → **BLOCKED**, exit 2, no check reported as passed. The
conclusion is unchanged: no window on this machine, and none was simulated.

**The matrix, green.** Run 38713190679 at `f38ac49`, all 12 jobs successful: the suite on CPython 3.10, 3.11,
3.12 and 3.13; the installed-package jobs on 3.10 and 3.13; the optional-PDF job; the display-backed desktop
smoke test on Linux; and the four cross-platform legs (`windows-latest` and `macos-latest` × 3.10 and 3.13),
which verify installation, `--version`, `--doctor` against a missing database (0), a file that is not a database
(1) and a read-only report (2), schema creation and cross-process persistence, backup/restore that really
replaces data, export/import into a second database, the discovery invariants, Tk availability plus a minimal
widget lifecycle, and the smoke test. **Corrected the same day (run 38719357147 at `e803286`): all five legs
build and drive the real window.** The Linux runner's smoke test passes under Xvfb, and so do the Windows and
macOS legs' window checks, which publish `PASS: Tk 8.6 built a root, a frame and a label and updated them` and
`RESULT: PASS — 14 checks passed. The window was built on a real display, its tabs and lists were read, its
read-only refresh actions were invoked, and its disposable database was released.` They were first read here as
reporting BLOCKED for the window; that was a defect in the widget-lifecycle check (D12), not a limit of those
runners. Each leg's annotation also carries what that runner says about itself — the interpreter, the platform
string, the Tk version and the screen Tk answered with, e.g. `display: 1024x768 pixels from CG0.0 Apple AppKit
2685.7 Mac OS X 1a0602` on macOS (Apple Silicon), `display: 1024x768 pixels from Windows 10.0 26100 Win64` on
Windows and `display: 1280x1024 pixels from X11R0 The X.Org Foundation 12101011` under Xvfb on Linux; the
values are tabulated in the evidence report, section 2.1. **No numbered step moved.** A scripted window on five
runners is not a person using it, and this entry still closes none of the 76 BLOCKED steps.

**Defects found by those runs, and fixed (each with a regression test that fails on the old behaviour).**

- **D6 — the wheel-verification step measured the checkout, not the wheel.** Step 10 of the macOS legs ran
  `python -` from the checkout, so the checkout satisfied an assertion about the installed copy and both macOS
  legs failed on a correct installation. Reproduced on Linux from the repository root (the checkout's
  `career_agent/__init__.py` was imported) and from `/tmp` (site-packages, as required). The wheel is now built
  into the temporary directory, installed and inspected from there, and the assertion is unchanged.
- **D7 — every private write was refused on Windows.** `_apply_owner_only_mode` applied the owner-only mode
  through the descriptor and treated any failure as a reason to refuse, while Windows has neither a descriptor
  mode nor `os.fchmod`: the lookup raised, the descriptor leaked, and the first Windows run reported 949 errors
  because every `CareerStore` construction writes the event log through that helper. The helper now reports
  success where there is nothing to apply, keeps refusing on POSIX, and
  `tests/test_store.PlatformWithoutPosixModeBitsTests` holds the writing paths on a platform without mode bits.
- **D8 — platform assumptions inside tests.** Four tests patched `os.fchmod` and one patched `os.O_NOFOLLOW`,
  neither of which exists on Windows (`mock.patch` raised at `__enter__`, so the assertions never ran); doctor
  tests hard-coded `/tmp` and `/srv`; a redaction test spelled a path with a forward slash; three assertions
  read POSIX mode bits. The flag patch is now created where the attribute is absent (reproduced by deleting
  `os.O_NOFOLLOW` in a child interpreter), the paths are built from the platform's own anchor and separator,
  and the mode assertions run where mode bits exist. The POSIX assertions themselves are unchanged.
- **D9 — a temporary folder was removed while the application still held it open**, which Windows refuses
  (`WinError 32`); the app is now closed inside the block that owns the folder.
- **D10 — a failure could only be read ten findings deep.** The first Windows run failed 949 times and the
  annotations could carry ten of them, so most of the inventory could only be guessed at.
  `scripts/ci_annotate.py --names` now publishes one annotation listing every failing test by name, and a green
  run publishes its `Ran N tests` / `RESULT:` lines as a notice.

- **D11 — two reporting steps turned a green Windows leg red.** Run 38715164487 (`c2ad285`) reported both
  Windows legs red with every check inside them green; the API said only `Process completed with exit code 1`.
  The notes file mixes encodings (bash steps write UTF-8, Python steps write the platform's ANSI code page), so
  an em dash arrived as a lone `0x97` byte, was read back as U+FFFD, and could not be printed through the
  console code page: `UnicodeEncodeError`, exit 1. Reproduced with those exact bytes under cp1252 and cp437
  (exit 1 before, exit 0 after). Fixed in `76d0a3c`: print workflow commands as UTF-8, drop control bytes that
  would corrupt a command, and publish anything unexpected as a warning annotation rather than failing the
  step. Run 38716978550 is green.
- **D12 — a window check that had never run anywhere, published as a platform limit.** The widget-lifecycle
  step reported `exit 2, BLOCKED` on all four Windows and macOS legs while the next step on the same runner
  reported `RESULT: PASS — 14 checks passed` for the real window. Made honest in `d56172d` (classify as
  `scripts/desktop_smoke_test.looks_like_no_display` does, and publish the reason), the next run named two
  defects: the step never imported `tkinter.ttk`
  (`AttributeError("module 'tkinter' has no attribute 'ttk'")`) and its report used a here-document inside a
  command substitution, which macOS's bash 3.2 does not parse. Both fixed in `e803286`; the step now prints
  `PASS:`/`BLOCKED:` (with Tk's own phrase) or `FAILED:` and a real failure fails the step. Verified against a
  tkinter stand-in: working Tk → 0; no-display phrase → 2 with the reason; any other root failure → 1; widgets
  that do not honour what they were asked for → 1.

- **D13 — one job's failure was unreadable.** Run 38723866093 failed in `unit-tests (3.11)` with nothing but
  `Process completed with exit code 1` in the API, because that job (and `installed-package`) recorded no
  output for `scripts/ci_annotate.py` to publish. Both jobs now record every step into the notes file and
  publish the failing test names, the first findings and the run's last words; a green `unit-tests` run also
  publishes the seed data's hash and record count. Verified by running the extracted step bodies here, which
  caught a defect in the new step before it reached a runner (it read `records`, the audit prints
  `record_count`). Run 38725527363 is green and the failure did not recur; whether it was a flake is unknown
  and is not claimed.

**Platform limits, stated and asserted rather than skipped.** The restore's guard cannot be held across
`os.replace` where the operating system refuses to replace a file another handle has open (Windows), so the
instant between releasing the guard and the swap is a limit of the module and that branch asserts the limit
instead of failing on it; the operating system's own refusal keeps its own test. An idle SQLite connection is
invisible to the coordination on every platform, and each platform's outcome is asserted. A filesystem whose
mode silently does not apply cannot be verified where there are no mode bits, so those two tests skip there
with the reason stated.

**PDF steps 24–31 (unchanged, still BLOCKED).** They are window steps. The optional extra is exercised on real
Windows, macOS and Linux runners (the `pdf-extra` job runs the module with and without `pypdf`), and on this
machine the résumé module runs `Ran 78 tests … OK` with `pypdf 6.20.1` and **no skips** — but steps 24–31 need
the import dialog and a person deciding on each proposed value.

**Support policy unchanged.** CPython 3.10–3.13 on Linux, macOS and Windows are the versions these runners
exercised. 3.14 is deliberately not added: no compatible interpreter has been exercised anywhere in this
pipeline, and adding it to the policy on the strength of the others would be a claim without evidence.

For each operating system tested, record:

- OS version and Python version.
- Test date and tester.
- Passed / failed / blocked result per numbered step.
- Exact error text and reproduction steps for failures.
- Any remaining known limitations.

**Release rule:** Until this checklist is executed on a real desktop and the results are recorded, call the UI a local alpha and do not claim GUI or cross-platform acceptance. Passing unit tests does not replace this checklist.

### 2026-10-15 — third follow-up: 14 steps' functional claims are now checked on real displays

**This subsection is a historical record of the 38-check state of the harness at that moment.** Later
subsections in this file record the same workflows after more were added (46 and then 76 checks); the numbers
below are what those runs reported at the commits named in them. **No numbered step changed verdict and no box
was ticked.** The 98 steps remain 22 PASS, 76 BLOCKED, 0 FAIL.
What follows is automated, machine-observed evidence from the project's own acceptance workflows; a person has
still not used this window, and every judgement a person has to make is still outstanding.

**What was added.** `scripts/desktop_acceptance.py` drives the real `CareerAgentApp` through its own widgets and
commands on a disposable synthetic database: entries typed into, choosers set, buttons pressed through Tk's
`invoke`, dialogs answered and recorded, and then the stored records and the window's own status line read back.
Six workflows (A–F), 38 checks, exit `0`/`1`/`2` for PASS/FAIL/BLOCKED as the smoke test uses them.

**Where it ran, and what it reported.** Run `38739493727` at `a530029`, all 12 jobs successful. Five legs ran the
workflows against real Tk on a real display and reported `RESULT: PASS — 38 checks passed`:

| Leg | Interpreter, platform | Tk and screen |
| --- | --- | --- |
| Desktop smoke (Linux, display-backed) | CPython 3.12 (system), ubuntu-latest | Tk 8.6; `1280x1024 pixels from X11R0 The X.Org Foundation 12101011` |
| Cross-platform (windows-latest, 3.13) | 3.13.16, `Windows-2025Server-10.0.26100-SP0` | Tk 8.6; `1024x768 pixels from Windows 10.0 26100 Win64` |
| Cross-platform (windows-latest, 3.10) | 3.10.11, `Windows-10-10.0.26100-SP0` | Tk 8.6; same screen string |
| Cross-platform (macos-latest, 3.13) | 3.13.15, `macOS-26.6.2-arm64-arm-64bit-Mach-O` | Tk 8.6; `1024x768 pixels from CG0.0 Apple AppKit 2685.7 Mac OS X 1a0602` |
| Cross-platform (macos-latest, 3.10) | 3.10.11, `macOS-26.6.2-arm64-arm-64bit` | Tk 8.6; same screen string |

The suite on those legs ran `1634 tests … OK` (37–44 skipped, the number differing by interpreter), and the
window smoke test reported its own `RESULT: PASS — 14 checks passed`. On the Linux job two further steps require
that the workflows report BLOCKED with no display and that the stand-in development run can never report a pass;
both passed. The full record, including the defect below and the per-leg annotations, is section 14 of
`research/cross-platform-desktop-ci-evidence-2026-10-15.md`.

**Automated coverage of numbered steps.** 35 steps carry an "Automated coverage" line: **3, 4, 5, 6, 10,
11, 13, 17, 18, 19, 21, 32, 33, 34, 43, 44, 46, 51, 52, 54, 61, 62, 64, 68, 69, 70, 73, 78, 87 and 88** are
covered for the functional claim the step states, and **12, 63, 71, 72 and 86 are covered in part** — step 12's
pasted-guidance-text refusal and in-place evidence rewrite are not driven, step 63's appearance in the other list
views is not checked, step 71's delete button and both answers to its confirmation are not driven, step 72's
record with a completion date and no start date, and its place after the ongoing one, were verified at the storage
layer rather than in this run, and step 86's remaining half is whether some other control in the window could
connect an account (the shipped-code scan in step 15 covers the code, not the widgets). Each line names the level
it was established at: a workflow step on a display-backed runner and/or a named test at the module or
handler-stub level. **A stub test is not a GUI test** — it drives the handler behind the widgets and says so in
its own docstring — and no line here moves a step's verdict. Step 78 already passed by file inspection; its
second half (the plan for an already-populated database, and the repeat import) is now checked automatically as
well.

**A defect that only a real display could show (D14).** The first display-backed run of these workflows
(38734920175 at `115ad2a`) passed 35 of 36 checks; the failure was F4 reporting a cleanup that had worked,
because `winfo_exists` *raises* once the Tk interpreter is destroyed rather than answering "gone". Fixed in
`dfea62d` with five regression tests. The stand-in widget module the unit tests use could not have produced it.

**What remains for a person.** Every one of the 76 BLOCKED verdicts is still exactly that, and the reasons are
unchanged: a person has to open the window on a machine with a display and judge what a machine cannot — layout
and clipping at normal and smaller sizes, the wording and clarity of each dialog, keyboard-only navigation and
focus order, screen-reader behaviour, actual mouse-driven flows, and whether the whole thing feels like a native
application. Steps 24–31 additionally need the `pdf` extra installed.
