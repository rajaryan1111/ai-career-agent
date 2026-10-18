# Local Alpha Manual Smoke-Test Checklist

**Status:** Required before calling the desktop alpha verified; not yet recorded as passed  
**Date created:** 2026-10-14  
**Updated:** 2026-10-19 — added backup restore, cancellation, and invalid-file steps

This checklist is intentionally separate from unit tests. It requires a real desktop session and should be completed on each operating system that the project advertises as supported. Do not mark a step passed based only on code inspection.

## Preconditions

- [ ] Python 3.10+ is installed.
- [ ] Tkinter is available in that Python installation.
- [ ] From the repository root, run: python -m unittest discover -s tests -v
- [ ] Run: python -m compileall -q career_agent scripts tests
- [ ] Run: python scripts/audit_job_source_csv.py; it should print a JSON report with an input SHA-256 and no unhandled error.
- [ ] For isolated checks, launch with `python -m career_agent --database /tmp/career-agent-alpha.sqlite3`; omit `--database` only when testing the per-user default location. Never point these checks at real candidate data.

## Desktop workflow

1. [ ] Run python -m career_agent; confirm the window opens without a traceback.
2. [ ] Confirm the displayed database path is in the operating system's per-user application-data directory, not inside the repository.
3. [ ] Enter a profile with country, degree, study status, graduation year, experience, work authorization, and skills. Save, close, reopen, and confirm values persist.
4. [ ] Enter a manual job with a source listing URL and leave the employer application URL blank. Save, restart, and confirm the two URL fields remain separate and the employer URL is still blank.
5. [ ] Mark the listing open but leave the availability evidence/note blank. Evaluate: overall eligibility must remain UNKNOWN; shortlisting must be blocked.
6. [ ] Add an availability evidence/note and explicit matching mandatory requirements. Evaluate: eligibility may be PASS only if every applicable hard requirement passes.
7. [ ] Change the allowed country so it excludes the candidate country. Evaluate: eligibility must be FAIL.
8. [ ] Add an explicit allowed-work-authorization list. A missing candidate value must be UNKNOWN; an exact matching value may pass that check; a mismatch must fail. Do not accept fuzzy/semantic equivalence.
9. [ ] Remove a mandatory degree/study-status/graduation-year value from either the candidate or listing. Evaluate: eligibility must not pass.
10. [ ] Attempt to shortlist a FAIL or UNKNOWN job. The app must block it. Shortlisting an explicit PASS job should update the tracker.
11. [ ] Attempt an invalid tracker transition and confirm the app shows an error without changing the saved status.
12. [ ] Attempt to mark an application confirmed without evidence; it must be rejected. Confirm with a meaningful evidence note, then move it to response_received or interview; confirmation state must remain preserved.
13. [ ] Export to a user-selected JSON file; verify it parses and contains the profile/jobs/tracker records. Confirm the UI warns that the file may contain personal data.
14. [ ] Start the app against a disposable database (`--database /tmp/career-agent-restore-a.sqlite3`). Enter a synthetic profile, two listings, and one confirmed attempt with evidence; export a backup to a temporary file.
15. [ ] Close the app, start it against a second disposable database (`/tmp/career-agent-restore-b.sqlite3`), and restore that backup. An empty database must restore without a confirmation prompt; compare profile, listings, attempts, evidence, and the history shown by **View history**.
16. [ ] Restore the same file again into the populated database. The confirmation must list the backup's job/attempt/event counts and warn that replacement cannot be undone. Decline: the status bar must report the cancellation and no record may change.
17. [ ] Restore again and accept. Records that existed only in the second database must disappear, and the backup's records must be present.
18. [ ] Open the restore dialog and cancel the file chooser: no dialog appears and nothing changes.
19. [ ] Try a non-JSON file, a backup with an unsupported `format_version`, a file larger than 10 MiB, and a backup with a tampered event history. Each must show one clear error, leave the database unchanged, and the app must remain usable afterwards.
20. [ ] Delete a job and confirm its tracker record is deleted. Delete the profile and confirm it is absent after restart.
21. [ ] Inspect the application workflow for network access: local alpha operations must not send requests or candidate data to external services.
22. [ ] Close and reopen the app after a forced close or normal exit; confirm the SQLite database remains readable.

## Record results

For each operating system tested, record:

- OS version and Python version.
- Test date and tester.
- Passed / failed / blocked result per numbered step.
- Exact error text and reproduction steps for failures.
- Any remaining known limitations.

**Release rule:** Until this checklist is executed on a real desktop and the results are recorded, call the UI a local alpha and do not claim GUI or cross-platform acceptance. Passing unit tests does not replace this checklist.
