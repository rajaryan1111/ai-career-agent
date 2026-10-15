# Local Alpha Manual Smoke-Test Checklist

**Status:** Executed on 2026-10-15 on a headless Linux machine: the 22 steps that need no window passed, 76 are blocked for named missing capabilities (see the execution results below and `research/local-alpha-manual-acceptance-run-2026-10-15.md`), and four defects found by the run were fixed. **Still required before calling the desktop alpha verified, and not yet recorded as passed.**  
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
4. [ ] Enter a manual job with a source listing URL and leave the employer application URL blank. Save, restart, and confirm the two URL fields remain separate and the employer URL is still blank.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; both URL fields round-tripped at the storage layer.**
5. [ ] Mark the listing open but leave the availability evidence/note blank. Evaluate: overall eligibility must remain UNKNOWN; shortlisting must be blocked.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the evaluation rule was executed directly and returned UNKNOWN.**
6. [ ] Add an availability evidence/note and explicit matching mandatory requirements. Evaluate: eligibility may be PASS only if every applicable hard requirement passes.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the evaluation rule was executed directly and returned PASS.**
7. [ ] Change the allowed country so it excludes the candidate country. Evaluate: eligibility must be FAIL.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the evaluation rule was executed directly and returned FAIL.**
8. [ ] Add an explicit allowed-work-authorization list. A missing candidate value must be UNKNOWN; an exact matching value may pass that check; a mismatch must fail. Do not accept fuzzy/semantic equivalence.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; UNKNOWN, exact-match PASS and mismatch FAIL all executed directly.**
9. [ ] Remove a mandatory degree/study-status/graduation-year value from either the candidate or listing. Evaluate: eligibility must not pass.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; a missing mandatory value never reached PASS when executed directly.**
10. [ ] Attempt to shortlist a FAIL or UNKNOWN job. The app must block it. Shortlisting an explicit PASS job should update the tracker.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the gate lives in the window handler, and the transition table it consults was verified.**
11. [ ] Attempt an invalid tracker transition and confirm the app shows an error without changing the saved status.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; an invalid transition was refused directly and the stored status stayed unchanged.**
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
13. [ ] Export to a user-selected JSON file; verify it parses and contains the profile/jobs/tracker records. Confirm the UI warns that the file may contain personal data.
    → **BLOCKED — no display and no Tkinter in the acceptance environment for the warning line; the export itself ran from the terminal and the file was inspected.**
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
18. [ ] Back up again to the *same* path. The app must refuse and explain, and the earlier file must be
    unchanged (compare the file size and its modification time).
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the second terminal backup was refused with the first file byte-identical.**
19. [ ] Add a job, then restore from the backup made in step 17 and confirm the question is asked first.
    Cancel once: nothing may change. Then confirm: the added job must be gone, the older data must be
    back, and a `<database name>.backup-<timestamp>` file must exist beside the database.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the terminal restore ran and a timestamped copy was kept beside the database.**
20. [ ] Close and reopen the app after that restore; the restored data must still be there, and the
    status line must not claim a success that did not happen.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the restored database was read back from the terminal with only the older records.**
21. [ ] Choose a file that is not a database (for example a text file) and restore from it: the app must
    refuse with a clear message *before* asking to confirm, and the current data must be untouched.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the terminal restore from a text file was refused with the database unchanged.**
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
33. [ ] Shortlist the job (only possible on an explicit eligibility PASS), reopen the dialog, and check the
    list again: it must offer only the statuses the record may move to from `shortlisted`. For a
    `submission_attempted` record the list must include `submitted_unverified`, `confirmed`, `failed` and
    `unknown_status` but not `interview` or `response_received`; those appear only after `confirmed`.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the states offered after a submission attempt were read directly.**
34. [ ] Close a record honestly: move an application to `withdrawn` with a note. Reopen **Update selected
    status** for it. The app must say the record is in a final state and must not offer a list of statuses
    at all. The stored note must still be shown in the tracker list, unchanged.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the states offered from withdrawn were read directly.**
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
44. [ ] Set a day in the past for a second application (for example yesterday). It must sort above the
    future one and read "N day(s) overdue". Confirm the summary line counts overdue and due-today
    separately, and that the **Application tracker** tab still shows the same statuses as before.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the terminal list printed the overdue day above the future one and led with the overdue count.**
45. [ ] Type something that is not a date ("next tuesday") and press the set button. The app must refuse
    with a message naming the YYYY-MM-DD form, and the stored record must be unchanged (check with
    `python -m career_agent --follow-ups`, or by re-reading the row).
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the same date shape rejects it with the stored day unchanged.**
46. [ ] Press **Clear the selected follow-up** and decline the confirmation: nothing may change. Press it
    again and accept: the day and note must disappear, while the application, its status and its activity
    history stay exactly as they were.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; clearing the follow-up was executed at the storage layer.**
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
52. [ ] With the app open, pause `follow-up-digest` in the Background tasks tab, confirm it asks first and
    that pausing keeps its times and its history, then resume it and confirm the next run is scheduled.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; a task saved as paused read back paused with its times intact.**

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
62. [ ] Select the item and press **Mark the selected item done**. The row must leave the list, the status
    line must say the application's status was not changed, and the tracker row on the **Application
    tracker** tab must be exactly as it was.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; completing an item was executed at the storage layer.**
63. [ ] Press **Record an interview round**, choose a stage, a day (tomorrow) and a mode, and save. The round
    must appear in the list above the preparation items and must read "in 1 day(s)"/"tomorrow" rather than
    as something that has already happened. Then select it, press **Record the selected round's outcome**,
    pick "You felt it went well", save, and confirm the outcome text appears in the row and that no status
    changed.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the round's day, its awaiting state, the recorded outcome and the unchanged status were all verified.**
64. [ ] Select a **follow-up** row and press **Delete the selected record**. It must explain that a follow-up
    day is cleared on the Follow-ups tab rather than deleted here, and nothing may change.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; clearing the plan was executed at the storage layer.**
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
69. [ ] Add an ended role with an end date before its start date. It must be refused with a dialog naming
    both dates, the list must not change, and the employment count must not move. Then add a role that has
    ended but whose end date you do not know: it must be accepted, list as `end date not recorded`, and the
    summary line must say that no duration is counted for it.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the refusal and the ended role's period were verified directly.**
70. [ ] Add a role with a start date written as `1 April 2023`. It must be refused with a message naming the
    `YYYY-MM-DD` shape, and nothing may be written.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the form's date shape was checked directly (accepts YYYY-MM-DD, rejects '1 April 2023').**
71. [ ] Select the role you added, change its job title, press **Save changes to the selected role**, and
    confirm the list shows the new title. Then press **Delete the selected role**, answering **No** first
    (nothing may change) and then **Yes** (only that role may disappear, and the status line must say what
    was deleted).
    → **BLOCKED — no display and no Tkinter in the acceptance environment; editing and deleting a role were executed at the storage layer.**
72. [ ] Add an education record ticking **Still studying** with no dates, and confirm it lists as
    `start not recorded - ongoing`. Then add one with a completion date and no start date, and confirm it
    lists `start not recorded - <date>` after the ongoing one.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the ongoing record's text and its place in the list were verified directly.**
73. [ ] Add an education record with a completion date while **Still studying** is ticked. It must be
    refused, and the list must not change.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the refusal was verified directly.**
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
87. [ ] Press **Preview the calendar export** with at least one follow-up recorded. A read-only dialog must
    list each event as `<day>: Follow up: <role> at <employer>  [follow-up-<id>-<day>@ai-career-agent.local]`,
    state that nothing has been written yet and that every event is an all-day entry with no attendee, and
    close with **Close**, Escape and Return. Before and after, the folder holding the database must contain
    no new `.ics` file.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the terminal preview listed the same event and wrote no file.**
88. [ ] Press **Draft a follow-up email** with no row selected: it must ask you to select a reminder, and
    open nothing. With a reminder selected, the dialog must show the subject, the full body, `To: NOT
    SUPPLIED`, `Status: DRAFT ONLY`, an `Operation id: email-...`, the "Missing, and not guessed" line for
    the recipient, and a line saying nothing was sent and nothing was created.
    → **BLOCKED — no display and no Tkinter in the acceptance environment; the terminal refusals and the full draft text were observed.**
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

For each operating system tested, record:

- OS version and Python version.
- Test date and tester.
- Passed / failed / blocked result per numbered step.
- Exact error text and reproduction steps for failures.
- Any remaining known limitations.

**Release rule:** Until this checklist is executed on a real desktop and the results are recorded, call the UI a local alpha and do not claim GUI or cross-platform acceptance. Passing unit tests does not replace this checklist.
