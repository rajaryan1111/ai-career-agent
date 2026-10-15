# Human Desktop Acceptance Handoff (2026-10-16)

**What this document is.** A run-book for the one thing this project has never done: a person opening the
window on a real desktop and judging what a machine cannot. It does **not** replace or duplicate the
[local-alpha manual smoke-test checklist](local-alpha-manual-smoke-test-checklist-2026-10-14.md) — the
98 numbered steps, their expected behaviour and their result lines stay there, and they are the record. This
file says how to get to a state where those steps can be executed, which steps carry which area, what
evidence to capture, and where to write the result.

**Status of every window step today: BLOCKED, and nothing here changes that.** No human has opened this
window. 22 of the 98 steps passed on a headless machine (the ones needing no window), 76 are blocked for the
named missing capability, none failed, and no box has been ticked.

**What automation already established, so a tester does not re-do it by hand.** Ten workflows and **77 checks**
now (76 when the per-leg table below was recorded; one check was added to workflow I on 2026-10-16)
(`scripts/desktop_acceptance.py`) drove the real window's own widgets on five display-backed CI legs — Linux
under Xvfb, Windows 2025 and macOS 26, on CPython 3.10 and 3.13 — every leg reporting
`RESULT: PASS — 76 checks passed` in run `38762008724` at `5b291a7a` for the 76-check state (per-leg table: section 15 of
[cross-platform-desktop-ci-evidence-2026-10-15.md](cross-platform-desktop-ci-evidence-2026-10-15.md)). That is
evidence about **stored records and the window's own status line**, produced by a program pressing widgets on a
virtual or CI display. It is not evidence about layout, wording, focus, assistive technology, a real mouse, or
how any of it feels, and it is not human acceptance. Where a step's checklist line carries an "Automated
coverage" note, that note says exactly which part a machine checked and which part is still yours.

**One command is deliberately not a numbered step: `--forget-local-data`.** It removes the database, its
SQLite sidecars, the snapshots and staged restores beside it, and the two logs this application writes. It
is a terminal command with no window, and asking a tester to erase their own data to prove it works would
be a destructive test of the tester rather than of the program, so the 17 tests in
`tests/test_cli_forget.py` carry it: the preview lists exactly what `--yes` would remove, a folder or a
symbolic link is refused rather than followed, a file the application did not write in the same folder
survives, a removal that completes exits zero, a removal that only partly completes exits non-zero, and a
database that comes back is reported rather than claimed as removed. If you want to read that preview on
your own machine, run `python -m career_agent --forget-local-data` without `--yes`: it changes nothing, and
you can judge whether the list it prints is the list you would expect.

---

## 1. Prerequisites

| Requirement | Why | How to confirm |
| --- | --- | --- |
| Python 3.10–3.14 with `tkinter` | the window is Tk; the suite runs up to 3.14 in CI (no 3.14 display leg exists, so a person's own interpreter is what matters here) | `python3 -c "import tkinter; print(tkinter.TkVersion)"` prints `8.6` |
| A real desktop session | Xvfb and a CI runner are not a person's desktop | the window really appears and can be moved, resized and clicked |
| A disposable data folder | **never point a manual run at a real database** | `export CAREER_AGENT_HOME="$(mktemp -d)"` before starting the app in that shell |
| The optional `pdf` extra, for steps 24–31 | PDF import reads text through `pypdf`; DOCX needs nothing extra | `python3 -m pip install "pypdf>=4.3"` into the interpreter running the app |
| A calendar application, for step 47 | the `.ics` must be imported somewhere real | any calendar that imports `.ics` files |
| A mail client, for step 90 | the claim is that this app cannot reach one | any configured mail client |
| A clean checkout, for step 23 | the run must create no file in the repository | `git status --porcelain` is empty before and after |
| A second terminal | steps 22, 49–50, 57–58, 66–67, 74–76, 84–85, 91–94, 96–98 are terminal-only | — |
| A screen reader, for area K | only a real assistive technology can judge this | VoiceOver (macOS, `Cmd-F5`), NVDA or Narrator (Windows), Orca (Linux) |

**Fixture discipline.** Type only synthetic values. Every listing, employer, role, résumé and note you enter
must be obviously invented; the résumé files for steps 24–31 should be synthesised for the purpose. The
application writes an event log and a database inside the folder you point it at; when you are done, delete
that folder. Do not use a database you care about, and do not test restore, deletion or "damaged database"
steps (14, 19–21, 37–41, 77, 95–97) on anything but a throwaway copy.

**Run the automated entry points once, before you start, so you know what they already say.** None of these
establishes human acceptance; they are how you avoid re-checking the machine's half by hand.

```bash
python scripts/desktop_smoke_test.py      # 14 checks: the window is built, eight tabs, lists have their columns
python scripts/desktop_acceptance.py      # 77 checks: ten workflows on disposable synthetic databases
python scripts/desktop_acceptance.py --stand-in-tk   # development only: prints DEVELOPMENT RUN and exits 2
```

All of them exit `0` for PASS, `1` for FAIL and `2` for BLOCKED, and a machine with no display reports BLOCKED —
never a pass. The third is a development aid and is never evidence of window behaviour.

---

## 2. The areas, and which numbered steps carry them

Execute the steps in the checklist in numeric order; the areas below are a guide to what each is judging and
what to capture. "Human-only judgement" is the part no automated run covers for that area.

### A. Launch, normal and abnormal shutdown, database location — steps 1, 2, 16, 23, 37–41, 98

- **Setup:** a disposable `CAREER_AGENT_HOME`; for 37–41, a throwaway copy of a database.
- **Do:** start with `python -m career_agent`; confirm no traceback; read the status line's database path; close
  and reopen; then run the damaged/unknown-status/missing-folder start-ups the steps describe.
- **Expected:** as written in each step — the window opens, the path is under the per-user data folder, the
  database is readable after reopening, and each damaged case is answered with a plain sentence rather than a
  traceback.
- **Evidence to capture:** the exact status-line text, the full text of any diagnostic, whether a crash-report
  window appeared, and `git status --porcelain` for step 23.
- **Human-only judgement:** whether the first screen tells you what you are looking at; whether the diagnostic
  note is readable at a glance; whether you would know what to do next.

### B. Window layout, resizing, clipping, readability — steps 1, 26, 36, 79–83

- **Setup:** the window opens at `1120x760` and refuses to shrink below `900x600`.
- **Do:** view every tab at the default size; resize to the minimum and to a maximised window; scroll each list
  and the progress report (79–83) with the mouse wheel and the scrollbar; check the **Close** button on the
  report dialog stays visible (81).
- **Expected:** no control, label or column is clipped or overlaps; long text wraps rather than being cut;
  every button stays reachable at the minimum size and at a maximised/zoomed size.
- **Evidence to capture:** a screenshot of each tab at default size and at the minimum size, plus one of the
  progress report scrolled to its end; note any clipped label by its text.
- **Human-only judgement:** everything here — no automated check inspects pixels, and this handoff does not
  claim otherwise.

### C. Profile, job entry, eligibility, shortlist, tracker transitions — steps 3–12, 32–35

- **Setup:** the disposable database from area A.
- **Do:** fill the profile; add a listing with a source URL and a blank employer URL; evaluate with no evidence
  (5), with evidence and requirements (6–8), then remove a requirement (9); try to shortlist UNKNOWN/FAIL (10);
  make an invalid transition (11); try to confirm without evidence and then with it (12); walk the status dialog
  for a new, a shortlisted and a withdrawn record (32–34); operate the dialog with Escape and Return (35).
- **Expected:** as written in the steps — UNKNOWN and FAIL cannot be shortlisted; the dialog offers only the
  current status and its permitted moves; a confirmation needs the person's own evidence; the status line never
  claims a write that did not happen.
- **Evidence to capture:** which options the status chooser offered at each state, the exact refusal text, and
  the status line afterwards.
- **Human-only judgement:** whether the eligibility report is understandable; whether the move you cannot make
  is explained well enough to know why.

### D. First follow-up, moving and clearing a reminder, persistence — steps 42–47, 59, 60

- **Setup:** an application selected on the **Application tracker** tab (this is where a follow-up day is set
  for the first time — a defect fixed on 2026-10-15 meant no reachable path could record the first one).
- **Do:** read what the tab says a follow-up is (42); record the first day with a note (43); record a past day
  on a second application and read the ordering and the summary (44); type `next tuesday` (45); decline and then
  accept the clear confirmation (46); export the `.ics` and import it into a real calendar (47); change a
  status and re-save a listing while a reminder is recorded (59, 60).
- **Expected:** the row shows the day, the note and `in N day(s)` or `N day(s) overdue`; the application's
  status and history never move; an unparseable day is refused naming `YYYY-MM-DD`; clearing removes the day and
  the note and nothing else; the calendar imports with an all-day event, no attendee and no link.
- **Evidence to capture:** the reminder rows before and after each action, the refusal text, and — for step 47 —
  what your calendar application showed when importing the file.
- **Human-only judgement:** whether "a day you plan to act on, not a status" is clear from the tab; whether the
  calendar entry is what you would expect to see.

### E. Next-action list: ordering and accuracy — steps 61–67

- **Setup:** at least one listing; one preparation item dated yesterday and one with no day.
- **Do:** add both (61); tick one off (62); record an interview round for tomorrow and its outcome (63); try
  **Delete the selected record** on a follow-up row and on a round (64, 65); compare with the terminal reports
  (66, 67).
- **Expected:** the overdue item sorts above the undated one, the undated one is listed rather than hidden, an
  interview due tomorrow reads as upcoming rather than as something that happened, a follow-up row refuses
  deletion by explaining where it is cleared, and the status line says the application's status did not move.
- **Evidence to capture:** the row order you saw (read the whole list), the wording that places each row in
  time, and the terminal output you compared it against.
- **Human-only judgement:** whether the list's order and its words make sense to a person in a hurry.

### F. Scheduler pause and resume, and truthful worker status — steps 51, 52

- **Setup:** the **Background tasks** tab; a terminal for `python -m career_agent --worker` if you want to watch
  an occurrence (the tab itself never runs anything).
- **Do:** confirm three tasks are listed with their times and zone (51); pause `follow-up-digest`, declining the
  confirmation first (52); close and reopen the window and confirm it is still paused; resume it.
- **Expected:** `daily-backup` 23:30, `scheduled-discovery` 00:00 and 12:00, `follow-up-digest` 09:00, all
  `Asia/Kolkata`; pausing asks first, keeps the task's times and history and shows `paused`; a declined
  confirmation changes nothing; resuming schedules the next run from now; the tab never takes the worker's lease
  and never claims a run happened. The summary also names, separately, the overdue occurrence a worker will
  still claim and what the schedule walked past while nothing ran ("Missed while nothing was running …"),
  which is a report and never a catch-up.
- **Evidence to capture:** the three rows as displayed, the confirmation wording, the row before and after the
  pause and after the resume, and the summary line about who holds the lease.
- **Human-only judgement:** whether "no worker holds the lease" means something a person can act on, and
  whether the difference between the tab and the foreground `--worker` is discoverable from the screen.

### G. Backup creation, refusals, restore — steps 17–22

- **Setup:** the **Data safety** tab; a disposable database; never a file you still need.
- **Do:** back up to a new file (17); back up again to the same path (18); add a job and restore from the first
  backup, declining the question first and then accepting it (19); reopen after the restore (20); restore from a
  text file (21); repeat the same operations from the terminal (22).
- **Expected:** the app reports a verified backup; on macOS/Linux `ls -l` shows `-rw-------`; an existing file is
  refused, not overwritten; the confirmation is asked before anything is replaced; the added job is gone, the
  older data is back, and a `<database name>.backup-<timestamp>` file sits beside the database; a non-database is
  refused with the current data untouched.
- **Evidence to capture:** the file listing with permissions and timestamps, the refusal text, the confirmation
  wording, and the data you saw before and after the restore.
- **Human-only judgement:** whether you would trust the backup after reading what the window said.

### H. Résumé import review, and cancelling without saving — steps 24–31

- **Setup:** a synthetic PDF with a real text layer, a synthetic DOCX whose skills are in a table, a damaged
  DOCX, and a scanned PDF with no text layer; `pypdf` installed.
- **Do:** press **Import resume (PDF/DOCX)** and work through the review dialog: read every proposal and its
  evidence (25), scroll a long list with the mouse wheel (26), close by Escape, by the window's close button and
  by **Cancel** (27), reject one confident value and accept one `needs review` value (28), then the scanned,
  table and damaged documents (29, 30), and confirm the chosen file is unchanged afterwards (31).
- **Expected:** every proposal shows its field, its value, its evidence and its confidence; nothing is written
  until **Save selected values**; cancelling saves nothing; a file with no text layer is refused rather than
  guessed at; a damaged file is refused by name; the source file is never modified or copied into the database.
- **Evidence to capture:** the review dialog's rows (screenshot), what the profile holds after saving only the
  accepted values, the refusal text for each bad document, and a checksum of the source file before and after.
- **Human-only judgement:** whether a proposal's evidence is enough for you to decide; whether "needs review"
  reads as a recommendation or as a warning — and whether the dialog's wording would ever let you approve
  something you did not mean to.

### I. File chooser and confirmation wording — steps 17, 19, 21, 27, 46, 47, 53–55, 64, 65

- **Do:** perform every action that opens a native file chooser or a confirmation, and read the sentences
  instead of clicking through them.
- **Expected:** each chooser opens in a sensible folder, filters to the right file type, and cancelling it leaves
  the app in the state it was in; each confirmation states what will be replaced or removed, and the safe answer
  is the one that does not act.
- **Evidence to capture:** the exact wording of every dialog you were shown, and the state of the data after you
  declined one.
- **Human-only judgement:** all of it. Automated runs answer these dialogs themselves and only check that a
  refusal was explained; they cannot read them as prose.

### J. Keyboard-only navigation, tab order, focus — steps 27, 35, 64, 65, 81

- **Do:** without touching the mouse, reach every control on every tab: `Tab`/`Shift-Tab` through each form, the
  arrow keys and `Enter` in each list, `Space` on the checkbuttons, `Escape` and `Return` in every dialog. Note
  where focus goes when a tab is opened, when a list is refreshed, and when a dialog closes.
- **Expected:** every control is reachable, the order follows the visual layout, the focused control is visibly
  obvious, `Enter`/`Return` performs the default action and `Escape` cancels, and focus returns somewhere
  sensible after a dialog.
- **Evidence to capture:** the tab order you observed per tab, any control you could not reach, and any place
  where you could not tell what had focus.
- **Human-only judgement:** all of it — no automated check presses `Tab`.

### K. Screen reader and assistive technology — no numbered step; run this pass explicitly

This area has **no coverage anywhere** in this project and is unrun. It is included so that its absence is
visible. No automated check can judge it.

- **Setup:** VoiceOver on macOS (`Cmd-F5`), NVDA or Narrator on Windows, Orca on Linux; one platform each is enough
  to start, and the result must state which one you used.
- **Do:** with the screen reader running, start the app and navigate one full pass: read the profile form, the
  jobs list, the follow-ups list and the next-action list; open the status dialog and the progress report; add an
  activity entry; trigger a refusal.
- **Expected:** each control announces a name and a role that match what is on screen; list rows announce their
  columns and not only their first value; a refusal is announced rather than only displayed; an image-free,
  text-only interface like this one should be navigable without a mouse.
- **Evidence to capture:** the spoken output for one representative control of each kind (quote it), plus any
  control that announces nothing or announces the wrong thing.
- **Human-only judgement:** all of it.

### L. Real mouse usability and native feel — steps 26, 81, and the whole run

- **Do:** perform the run with a mouse: click every button, drag the window, resize it by its edges, scroll with
  the wheel, use the lists' scrollbars, and try the app's own closing button.
- **Expected:** nothing needs a second attempt because a target is too small or too close to its neighbour;
  resizing does not hide a control; double-clicks and single clicks behave as they look like they should.
- **Evidence to capture:** anything you had to try twice, and the size the window was at when it happened.
- **Human-only judgement:** all of it, including whether it "feels like" a native application on your platform.

### M. Operating-system specifics

Run the checklist once per operating system you intend to claim support for, and record the environment facts
with the results. This project has automated CI evidence on Linux (Xvfb), Windows 2025 and macOS 26 (see
section 15 of the cross-platform evidence file), and **no human has run it on any of them**.

| Platform | Holds today | What a person must still do |
| --- | --- | --- |
| Linux (the development platform) | system Tk 8.6, X11; automated legs pass | the whole checklist; window-manager behaviour is untested |
| Windows 10/11 | Tk 8.6 on CI; POSIX permission checks are skipped there by design | the whole checklist, including whether the "owner-only" wording is honest on a platform without POSIX modes |
| macOS (Apple Silicon) | Tk 8.6 on CI (AppKit 2685.7) | the whole checklist — this is the platform the one earlier manual check was performed on (résumé import review, cancelled without saving) |

---

## 3. What to write down, and where

Write results **into the checklist**, at the step, in its existing style — one line per answer, never deleting
the lines already there:

```
→ **PASS — <what you actually saw>.** (tester, OS + version, Python + Tk version, 2026-10-__)
→ **FAIL — <what happened instead, with the exact text and the shortest steps to repeat it>.**
→ **BLOCKED — <the capability that is missing>.**
```

Then fill in the checklist's "Record results" section: OS and Python versions, test date and tester,
passed/failed/blocked per step, exact error text and reproduction steps for failures, and remaining known
limitations. **Do not tick a box for a step you did not execute**, and do not tick a box because an automated
check covers the functional half of it — the two are recorded beside each other, not instead of each other.

**What to hand back.** The completed checklist entry, the screenshots named in area B, the dialog wording from
area I, the keyboard and screen-reader notes from areas J and K, and a one-line verdict per area. Anything you
could not execute is `BLOCKED` with the missing capability named — that is a useful result, and it is the
result this project has recorded for every window step so far.

---

## 4. Where the rest of the evidence lives

| Document | What it holds |
| --- | --- |
| [local-alpha manual smoke-test checklist](local-alpha-manual-smoke-test-checklist-2026-10-14.md) | the 98 numbered steps, their expected behaviour, and the per-step result lines (the record of truth) |
| [research index](README.md) | what every research artefact answers, and which are current guidance rather than dated evidence |
| [local-alpha manual acceptance run](local-alpha-manual-acceptance-run-2026-10-15.md) | what a headless machine could execute (22 PASS, 76 BLOCKED, 0 FAIL), the four defects that run found, and how the window half was later driven automatically |
| [cross-platform desktop CI evidence](cross-platform-desktop-ci-evidence-2026-10-15.md) | the ten workflows, their per-leg check counts (76 when the table was recorded, 77 after workflow I gained a check), per-leg platform/Tk/screen strings, and the defects only a real display could show |
| [release-readiness audit](release-readiness-audit-2026-10-15.md) | what is implemented, tested, packaged and verified — and what is none of those |

**The distinction this handoff keeps.** Implemented is not automated-tested; automated-tested is not
human-accepted; human-accepted is not release-ready. This project has the first two for most of its local
workflow, the third for none of it, and no packaged, signed release on any platform.
