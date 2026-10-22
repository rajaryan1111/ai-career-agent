# Local Alpha Manual Smoke-Test Checklist

**Status:** Required before calling the desktop alpha verified; not yet recorded as passed  
**Date created:** 2026-10-14  
**Updated:** 2026-10-19 — added fresh-install, CLI, edge-case, and cleanup sections plus a recorded-results table

This checklist is intentionally separate from unit tests. It requires a real desktop session and should be completed on each operating system that the project advertises as supported. Do not mark a step passed based only on code inspection. Scripted Tk tests exercise the same widgets but cannot verify layout, focus order, clipping, or visual messaging.

Record every step as **PASS**, **FAIL**, or **BLOCKED** in the table at the end. A step with no recorded result counts as not executed.

## Preconditions

- [ ] Python 3.10–3.12 is installed and `python --version` reports the intended interpreter.
- [ ] Tkinter is available: `python -c "import tkinter; print(tkinter.TkVersion)"` succeeds.
- [ ] A desktop session is available (not SSH without a display).
- [ ] From the repository root: `python -m unittest discover -s tests -v` exits 0 with no failures.
- [ ] From the repository root: `python -m compileall -q career_agent scripts tests` exits 0.
- [ ] `python scripts/audit_job_source_csv.py` prints a JSON report with an input SHA-256 and no traceback.
- [ ] `python scripts/smoke_check.py` exits 0 and reports every step as passing.
- [ ] All GUI runs use a disposable database under `/tmp` (or `%TEMP%` on Windows). Never point these checks at real candidate data.
- [ ] Note the OS version, desktop environment, Python version, Tk version, and tester in the results section.

Suggested disposable paths:

```bash
python -m career_agent --database /tmp/career-agent-alpha.sqlite3
python -m career_agent --database /tmp/career-agent-restore-a.sqlite3
python -m career_agent --database /tmp/career-agent-restore-b.sqlite3
```

## 0. Installation and command line

0.1. [ ] In a fresh virtual environment (`python3 -m venv /tmp/ca-venv && . /tmp/ca-venv/bin/activate`), run `python -m pip install -e .`. It must complete without dependency downloads beyond packaging essentials. **Expected:** install succeeds; `career-agent --version` prints `career-agent 0.1.0`; `career-agent --help` prints usage and exits 0.

0.2. [ ] Run `career-agent --diagnostics`. **Expected:** one short report with version, Python, platform, Tkinter availability, whether the default database exists and its schema version, the closed source-quality gate, and zero enabled discovery sources. No candidate names, notes, URLs, or other record contents appear.

0.3. [ ] Run `python -m career_agent --database /tmp/missing-dir/db.sqlite3`. **Expected:** a clear error naming the missing parent directory and exit status 2; no file is created and no traceback is shown.

0.4. [ ] Run `python -m career_agent --database /tmp/career-agent-alpha.sqlite3`, quit, and relaunch. **Expected:** the window opens both times without a traceback; the second launch reuses the same database rather than recreating it.

0.5. [ ] With the package installed, run `python -m career_agent` from a directory other than the repository root. **Expected:** the app starts and reports the per-user database location; nothing is written into the repository.

## 1. Candidate profile

1.1. [ ] Launch with the disposable database and confirm the window opens without a traceback. Confirm the status area shows the active database path.

1.2. [ ] With no saved profile, inspect the form and status. **Expected:** the app states that no profile is saved yet; no placeholder values are saved on the user's behalf.

1.3. [ ] Enter a profile with country, degree discipline, study status, graduation year, experience, work authorization, and skills. Save. **Expected:** a success message identifies what was saved; the values match the input exactly, including capitalization and spacing.

1.4. [ ] Close and reopen the app. **Expected:** every saved value persists, and the form shows the saved values rather than blanks.

1.5. [ ] Clear a required field (for example country or degree) and attempt to save. **Expected:** validation names the missing field, nothing is saved, and previously saved values remain intact. Re-enter the value and save successfully.

1.6. [ ] Enter deliberately long values (for example a 300-character skills string and a long note). Save, reopen, and confirm the values round-trip without truncation or silent coercion.

1.7. [ ] Edit the profile, then close the window without saving. **Expected:** a confirmation asks whether to discard the unsaved changes. Decline: the window stays open and the form keeps the edits. Accept: the window closes and the saved profile is unchanged after relaunch. With no unsaved edits, closing must not prompt.

## 2. Listings and eligibility

2.1. [ ] Enter a manual job with a source listing URL and leave the employer application URL blank. Save, restart, and confirm the two URL fields remain separate and the employer URL is still blank.

2.2. [ ] Enter a second job with the same identifying details (same employer, role, and source/application URL). **Expected:** the app warns that it matches an existing canonical URL/requisition and asks whether to keep the second observation. Declining leaves the list unchanged; accepting keeps both observations separately, and shortlisting both must be blocked with a duplicate reason.

2.3. [ ] Mark a listing open but leave the availability evidence/note blank. Evaluate. **Expected:** overall eligibility is UNKNOWN; shortlisting is blocked and the reason mentions the missing availability evidence.

2.4. [ ] Add availability evidence and explicit matching mandatory requirements. Evaluate. **Expected:** eligibility may be PASS only if every applicable hard requirement passes, and each requirement row is explained.

2.5. [ ] Change the allowed country so it excludes the candidate country. Evaluate. **Expected:** eligibility is FAIL and the failing requirement names the country.

2.6. [ ] Add an explicit allowed-work-authorization list. Test three states: candidate value missing (UNKNOWN), exact match (that check passes), and mismatch (FAIL). **Expected:** no fuzzy or semantic equivalence is accepted.

2.7. [ ] Remove a mandatory degree, study-status, or graduation-year value from either the candidate or the listing. Evaluate. **Expected:** eligibility does not pass and the missing item is named.

2.8. [ ] Mark a listing closed. Evaluate. **Expected:** eligibility is FAIL for the closed listing even when every other requirement matches. A listing with unknown availability stays UNKNOWN.

2.9. [ ] Attempt to shortlist a FAIL or UNKNOWN job. **Expected:** the app blocks the action with a reason and leaves the tracker unchanged. Shortlisting an explicit PASS job updates the tracker.

2.10. [ ] Edit a listing's requirements after it was shortlisted, then re-evaluate. **Expected:** the displayed eligibility reflects the saved requirement values, and any warning about the change is visible rather than silently ignored.

## 3. Preparation, tracking, and history

3.1. [ ] Select a shortlisted, eligible job and choose **Prepare application**. **Expected:** the readiness checklist is explicit (blocked / needs review / ready); the draft preview uses only recorded facts and labels missing fields as not recorded; declining the confirmation changes nothing.

3.2. [ ] Accept the preparation confirmation. **Expected:** `prepared` is recorded with a new history entry, and the visible status matches the persisted status after a restart.

3.3. [ ] Select an ineligible or non-shortlisted job and choose **Prepare application**. **Expected:** the action warns or is unavailable, and the tracker is unchanged.

3.4. [ ] Attempt an invalid tracker transition. **Expected:** the app shows an error without changing the saved status. Confirm the status after restarting.

3.5. [ ] Attempt to mark an application confirmed without evidence. **Expected:** rejection with a clear reason. Confirm with a meaningful evidence note, then move it to response received or interview. **Expected:** the confirmation evidence and timestamp remain visible in history.

3.6. [ ] Withdraw an active attempt, then re-apply while the listing is still open and eligible. **Expected:** a new attempt is created; the earlier attempt and its history are preserved and still viewable.

3.7. [ ] Open **View history** for a job with several transitions. **Expected:** events appear in chronological order with their evidence, and no event is editable or deletable from this view.

3.8. [ ] Force-quit the app (for example `kill -9` on the process) after saving a transition, then relaunch. **Expected:** the database is readable, the transition is present, and no history entry is duplicated or missing.

## 4. Resume import

4.1. [ ] On the profile tab, choose **Import resume (review)…** and select a synthetic DOCX file with labelled lines (`Skills:`, `Country:`, `Degree:`). **Expected:** proposals show each extracted value with its quoted evidence line; nothing is saved automatically.

4.2. [ ] Decline the import review. **Expected:** the profile form is unchanged, and no file or value is written to the database.

4.3. [ ] Accept the proposals, then inspect the form before saving. **Expected:** proposed values populate the form for review; the profile is only persisted after **Save profile locally**.

4.4. [ ] Repeat with a plain-text and a Markdown resume, and with a text-based PDF. **Expected:** supported formats extract conservatively; unsupported labels produce no invented values.

4.5. [ ] Try a scanned or image-only PDF. **Expected:** the app states that OCR is unavailable and that no text was found; it does not report a successful import with empty values.

4.6. [ ] Try a corrupt DOCX, an oversized file, a non-UTF-8 text file, and an unsupported extension. **Expected:** one clear error per attempt, the app remains usable, and the profile is unchanged.

4.7. [ ] Check the terminal output after importing a file containing a distinctive synthetic name or email. **Expected:** no resume contents or personal values are printed to logs or error messages.

## 5. Backup, restore, and deletion

5.1. [ ] Export to a user-selected JSON file. **Expected:** the file parses as JSON, contains the profile/jobs/tracker/history records, and the UI warns that it may contain personal data.

5.2. [ ] Against `/tmp/career-agent-restore-a.sqlite3`, enter a synthetic profile, two listings, and one confirmed attempt with evidence; export a backup to a temporary file.

5.3. [ ] Close the app and start it against `/tmp/career-agent-restore-b.sqlite3`. Restore that backup. **Expected:** an empty database restores without a confirmation prompt; compare the profile, listings, attempts, evidence, and **View history** output.

5.4. [ ] Restore the same file again into the now-populated database. **Expected:** the confirmation lists the backup's job/attempt/event counts and warns that replacement cannot be undone. Decline. The status bar reports the cancellation and no record changes.

5.5. [ ] Restore again and accept. **Expected:** records that existed only in the second database disappear; the backup's records are present, and the counts match the confirmation.

5.6. [ ] Open the restore dialog and cancel the file chooser. **Expected:** no confirmation dialog appears and nothing changes.

5.7. [ ] Try a non-JSON file, a backup with an unsupported `format_version`, a file larger than 10 MiB, a non-UTF-8 file, and a backup with a tampered event history. **Expected:** one clear error per attempt, the database is unchanged, and the app remains usable.

5.8. [ ] Restore a backup whose contents are internally inconsistent (for example a tracker row referencing a missing job). **Expected:** the restore is refused and rolled back; the previous database contents remain intact.

5.9. [ ] Delete a job and confirm its tracker record and history are deleted with it. Delete the profile and confirm it is absent after restart.

5.10. [ ] Choose **Delete all local data…**, decline once, then accept. **Expected:** the first decline changes nothing; acceptance empties the profile form, job list, and tracker, the status bar reports deleted counts, and an exported backup file remains intact on disk.

5.11. [ ] After deleting all data, restart and confirm the app opens to an empty but usable state.

## 6. Sources and settings

6.1. [ ] Open **Sources & settings**. **Expected:** the banner says discovery is disabled with manual entry only, the source-quality gate reads **closed**, and blocked providers are listed with their status and reason.

6.2. [ ] Confirm no search, fetch, connect, or network control is present, and no candidate data is sent anywhere during the whole session.

6.3. [ ] Confirm the tab distinguishes blocked, awaiting verification, and disabled states rather than showing a generic "unavailable" message.

## 7. Edge cases and recovery

7.1. [ ] Launch two instances against the same database and perform conflicting edits. **Expected:** stale writes are rejected with a retry message rather than silently overwriting the other instance's change.

7.2. [ ] Make the database file read-only, then attempt a write. **Expected:** a clear permission error, no partial record, and no crash; the app remains usable after restoring write permission.

7.3. [ ] Replace the database with a corrupt file and launch. **Expected:** a clear startup error, no traceback dump of personal data, and exit without destroying the file.

7.4. [ ] Resize the window to its minimum size, maximize it, and tab through the form. **Expected:** no clipped buttons or overlapping labels; focus order is logical; long values remain readable through scrolling or wrapping.

7.5. [ ] Trigger every dialog with the keyboard only (open, confirm, cancel). **Expected:** Escape cancels and Enter confirms only where it is safe to do so; destructive confirmations default to the safe choice.

7.6. [ ] Leave the app idle for several minutes, then continue editing. **Expected:** no stale-state error and no loss of unsaved input beyond documented behavior.

## Record results

Copy this table per tested platform and fill in every row.

| Step | Result (PASS / FAIL / BLOCKED) | Observed behaviour or error text | Tester / date |
| --- | --- | --- | --- |
| 0.1 |  |  |  |
| 0.2 |  |  |  |
| 0.3 |  |  |  |
| 0.4 |  |  |  |
| 0.5 |  |  |  |
| 1.1 |  |  |  |
| 1.2 |  |  |  |
| 1.3 |  |  |  |
| 1.4 |  |  |  |
| 1.5 |  |  |  |
| 1.6 |  |  |  |
| 1.7 |  |  |  |
| 2.1 |  |  |  |
| 2.2 |  |  |  |
| 2.3 |  |  |  |
| 2.4 |  |  |  |
| 2.5 |  |  |  |
| 2.6 |  |  |  |
| 2.7 |  |  |  |
| 2.8 |  |  |  |
| 2.9 |  |  |  |
| 2.10 |  |  |  |
| 3.1 |  |  |  |
| 3.2 |  |  |  |
| 3.3 |  |  |  |
| 3.4 |  |  |  |
| 3.5 |  |  |  |
| 3.6 |  |  |  |
| 3.7 |  |  |  |
| 3.8 |  |  |  |
| 4.1 |  |  |  |
| 4.2 |  |  |  |
| 4.3 |  |  |  |
| 4.4 |  |  |  |
| 4.5 |  |  |  |
| 4.6 |  |  |  |
| 4.7 |  |  |  |
| 5.1 |  |  |  |
| 5.2 |  |  |  |
| 5.3 |  |  |  |
| 5.4 |  |  |  |
| 5.5 |  |  |  |
| 5.6 |  |  |  |
| 5.7 |  |  |  |
| 5.8 |  |  |  |
| 5.9 |  |  |  |
| 5.10 |  |  |  |
| 5.11 |  |  |  |
| 6.1 |  |  |  |
| 6.2 |  |  |  |
| 6.3 |  |  |  |
| 7.1 |  |  |  |
| 7.2 |  |  |  |
| 7.3 |  |  |  |
| 7.4 |  |  |  |
| 7.5 |  |  |  |
| 7.6 |  |  |  |

Platform summary:

- OS version:
- Python version:
- Tk version:
- Desktop environment:
- Test date and tester:
- Overall result:
- Blocking failures:
- Known limitations observed:

## Cleanup

- [ ] Close every application instance.
- [ ] Delete disposable databases and backups: `rm -f /tmp/career-agent-alpha.sqlite3 /tmp/career-agent-restore-*.sqlite3 /tmp/career-agent-restore-*.json` (adjust for your temporary directory).
- [ ] Remove the test virtual environment: `rm -rf /tmp/ca-venv`.
- [ ] Confirm no synthetic resume files remain in the repository: `git status --porcelain` should be clean apart from intentional changes.
- [ ] If any check touched the default per-user database, confirm no real records were altered before closing this checklist.

## Release rule

Until this checklist is executed on a real desktop and the results are recorded, call the UI a local alpha and do not claim GUI or cross-platform acceptance. Passing unit tests, widget-level tests, and green CI do not replace this checklist.
