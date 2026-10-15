# Cross-Platform and Desktop CI Evidence — 2026-10-15

**What this file is.** The automated half of the desktop verification for the local alpha: what actually ran,
on which operating system and interpreter, with the exact command and the observed result. It exists because
this project is developed from a machine that cannot open a window and cannot read a job log, so the evidence
has to be gathered on runners and published where the API can return it.

**What this file is not.** It is not manual GUI acceptance. Every numbered step of
`research/local-alpha-manual-smoke-test-checklist-2026-10-14.md` that needs a person at a keyboard is still
that checklist's business, and the automated runs below do not close any of them. Nothing here supports a
claim of desktop acceptance, packaging, code signing or release readiness.

**Author:** the agent, on the machine and runners named below. **Date:** 2026-10-15.

## 1. The machine this was written from (capability probe, by running commands)

| Probe (exact command) | Observed |
|---|---|
| `uname -a` | `Linux e2b.local 6.1.158+ #1 SMP PREEMPT_DYNAMIC … x86_64 GNU/Linux` |
| `cat /etc/os-release \| head -2` | `Debian GNU/Linux 12 (bookworm)` |
| `python3 -VV` | `Python 3.11.2 (main, Apr 8 2026, 01:58:00) [GCC 12.2.0]` — the only interpreter; `python3.10/3.12/3.13` are not present |
| `python3 -c "import tkinter"` | `ModuleNotFoundError: No module named 'tkinter'` |
| `printf '%s' "${DISPLAY:-<unset>}"` | `<unset>` |
| `command -v Xvfb xvfb-run Xephyr Xorg weston wayland-info` | none present |
| `sudo apt-get install -y python3-tk` | `E: Package 'python3-tk' has no installation candidate` — the sandbox's packages are unreachable; only `github.com`, `codeload.github.com`, `api.github.com`, `registry.npmjs.org`, `pypi.org` and `files.pythonhosted.org` answer |
| `python3 scripts/desktop_smoke_test.py` | `RESULT: BLOCKED — this Python has no tkinter module: ModuleNotFoundError("No module named 'tkinter'")`, exit **2**, no check reported as passed |

So on this machine no real Tk widget can be created, and none was simulated. The window is exercised on the
runners instead, and on all five of them: the Ubuntu legs under Xvfb, and the four Windows and macOS legs,
where Tk needs no display variable at all. This paragraph first said those platform jobs reported the same
BLOCKED status there; that was the window check's own defect, not a limit of the runners - section 9.

## 2. CI matrix, latest commit

Workflow `.github/workflows/tests.yml`, branch `arena/351e052d-ai-career-agent`, pull request #2 (open).

**Run 38713190679 on `f38ac49` — success, all 12 jobs.**

| Job | Runner | Python | Result | What it verifies on that platform |
|---|---|---|---|---|
| `unit-tests (3.10 … 3.13)` | `ubuntu-latest` | 3.10, 3.11, 3.12, 3.13 | success ×4 (jobs 116349415773, 116349415619, 116349415593, 116349416053) | the full suite on each supported interpreter |
| `Installed package (3.10, 3.13)` | `ubuntu-latest` | 3.10, 3.13 | success ×2 (116349415849, 116349415768) | wheel built and installed, console script answers |
| `Optional PDF extra` | `ubuntu-latest` | 3.13 | success (116349415503) | the résumé module skips its PDF cases without `pypdf` and finishes with a bare `OK` with it |
| `Desktop smoke (Linux, display-backed)` | `ubuntu-latest` | system 3.12 + `python3-tk` | success (116349415572) | the smoke test must report BLOCKED with no display and must pass under `xvfb-run`; then no window, database or folder may be left behind |
| `Cross-platform (windows-latest, 3.10)` | `windows-latest` | 3.10 | **success** (116349415475) | suite, wheel, `--version`, `--doctor` (missing database → 0, not-a-database → 1, read-only report → 2), schema creation and cross-process persistence, backup/restore that replaces data, export/import, discovery invariants, Tk availability, widget lifecycle, smoke test |
| `Cross-platform (windows-latest, 3.13)` | `windows-latest` | 3.13 | **success** (116349415748) | the same |
| `Cross-platform (macos-latest, 3.10)` | `macos-latest` | 3.10 | **success** (116349415846) | the same |
| `Cross-platform (macos-latest, 3.13)` | `macos-latest` | 3.13 | **success** (116349415564) | the same |

**Corrected the same day by run 38719357147 (`e803286`): every one of those legs builds and drives the real
window.** That run carried the same 12 jobs to success while the Windows and macOS legs published, in their own
annotations:

    PASS: Tk 8.6 built a root, a frame and a label and updated them
    RESULT: PASS — 14 checks passed. The window was built on a real display, its tabs and lists were read,
    its read-only refresh actions were invoked, and its disposable database was released.

This paragraph first reported those legs as BLOCKED for the window, on the strength of the widget-lifecycle
step's warning. The warning was the defect: the step never imported `tkinter.ttk`, so its first real use raised
`AttributeError`, and the step published that as "could not run on this runner (exit 2, BLOCKED)" - no reason,
and a hard failure wearing a missing capability's words. Section 9 has the two defects and their fixes; the
platform table in section 7 now reads what the runs actually said. The manual checklist steps stay BLOCKED:
none of this is a person using the window.

### 2.1 What each leg says about itself (run 38721856789 at `e70ee1e`, read from the API)

The summary notice now carries the runner's own account of itself, so the platform, the interpreter, the Tk
and the display behind a verdict are checkable without the log:

| Leg | `platform:` | `tkinter:` | `display:` — Tk's own reply | suite | window |
|---|---|---|---|---|---|
| `windows-latest`, 3.10 | `Windows-10-10.0.26100-SP0` | Tk 8.6 / Tcl 8.6 | `1024x768 pixels from Windows 10.0 26100 Win64` | `Ran 1604 tests in 931.783s`, `OK (skipped=44)` | `PASS: Tk 8.6 built a root, a frame and a label and updated them` then `RESULT: PASS — 14 checks passed` |
| `macos-latest`, 3.10 | `macOS-26.6.2-arm64-arm-64bit` | Tk 8.6 / Tcl 8.6 | `1024x768 pixels from CG0.0 Apple AppKit 2685.7 Mac OS X 1a0602` | `Ran 1604 tests in 47.541s`, `OK (skipped=20)` | the same |
| `ubuntu-latest`, system 3.12, under Xvfb | — (job `desktop-smoke-linux`) | `Tk 8.6, from /usr/lib/python3.12/tkinter/__init__.py` | `1280x1024 pixels from X11R0 The X.Org Foundation 12101011` | (not this job's work) | the same |
| `pdf-extra`, 3.13 | — | — | — | without `pypdf`: `Ran 78 tests … OK (skipped=12)`; with it: `OK`, no skips | — |

The `display:` line is Tk answering (`winfo_screenwidth`, `winfo_screenheight`, `winfo_server`), not a
variable this project sets — that is what makes "the window was built on a real display" a measurement rather
than a claim. The Windows notices print `RESULT: PASS �` where the em dash belongs: those legs' Python
writes the notes in the ANSI code page (D11), and the byte is not valid UTF-8 when it is read back. The macOS
legs are Apple Silicon (`arm64`), so *scripted* window behaviour on Apple Silicon is measured now; what stays
unmeasured there is a person using the window, and any packaged build. The `3.13` counterpart of each leg
reports the same verdicts, with `OK (skipped=37)` on Windows and `OK (skipped=13)` on macOS — the difference
between the legs is which platform-specific tests skip, and a skip always carries its reason.

Earlier runs, kept because the fixes below were derived from them:

| Run | Commit | Result | What it showed |
|---|---|---|---|
| 38708232458 | `9167d7d` | failure | macOS 3.10 and 3.13 failed at the wheel-verification step; Windows 3.10 and 3.13 failed inside the suite |
| 38711721472 | `b04ad90` | failure | macOS green; Windows failed with exactly four recorded findings (section 4) |
| 38713190679 | `f38ac49` | **success** | all 12 jobs |

## 3. The macOS failure: the wheel was verified from inside the checkout

**Symptom.** Step 10 (`Build a wheel and install it into a virtual environment outside the checkout`) failed on
both macOS legs while the suite itself passed (`Ran 1597 tests … OK`). The step was the one step whose output
was not recorded in the notes file, so the failure could not be read from this network at all.

**Root cause, reproduced on Linux.** The step ran `python - <<'PY'` with the checkout as its working directory.
`python -` puts the current directory (here: the checkout) at the head of `sys.path`, so the installed copy was
shadowed by the source tree and the step's own assertion failed on a correct installation:

```
$ cd /home/user/ai-career-agent && /tmp/verify-venv/bin/python -c "import career_agent, pathlib; print(pathlib.Path(career_agent.__file__).resolve())"
/home/user/ai-career-agent/career_agent/__init__.py
ASSERTION FAILED: the checkout was imported, not the wheel: /home/user/ai-career-agent/career_agent/__init__.py
$ cd /tmp && /tmp/verify-venv/bin/python -c "…same check…"
has site-packages in parts: True
```

**Fix.** The wheel is built into the temporary directory (`python -m build --wheel --outdir "$work/dist"`), the
step moves there (`cd "$work"`) and installs and inspects it from there, and the checkout is not left with a
`dist/` or an egg-info directory. The assertion itself is unchanged — the checkout must never be able to
satisfy a check about the installed copy.

**Verification (local dry run of the whole job body, Linux, Python 3.11.2).** The step bodies were extracted
from the workflow with PyYAML and executed in sequence with a virtual environment on `PATH`. All 14 steps
before the annotation steps exited 0; the wheel step printed
`installed 0.1.0 from /tmp/tmp.DaxOk67zeY/venv/lib/python3.11/site-packages/career_agent/__init__.py`. The same
run confirms the checkout is left clean (`git status --short` shows no untracked files after it). The two
platform legs then passed this step for real on run 38713190679.

## 4. Windows: what failed, what each failure was, and what was changed

The first Windows run (`9167d7d`) reported **949 errors**, most of them one cause: every `CareerStore`
construction records its own start in the event log, the event log is written through the private-write helper,
and that helper treated "the owner-only mode could not be applied" as a reason to refuse the write while
Windows has no descriptor mode and no `os.fchmod` — the lookup itself raised, leaking the open descriptor.

| Failure (as recorded by the annotations) | Classification | Change |
|---|---|---|
| 949 errors from `CareerStore` construction; four tests patching `career_agent.store.os.fchmod` failed at `__enter__` with `AttributeError` | product defect (`_apply_owner_only_mode` did not honour the documented POSIX-only rule) + test assumption | the helper reports success where there is nothing to apply (`os.name != "posix"` or no `os.fchmod`) and keeps refusing on POSIX; `tests/test_store.PlatformWithoutPosixModeBitsTests` holds the writing paths; the four patch sites are skipped where POSIX mode bits do not exist, with the reason in the skip message |
| `st_mode & 0o077` assertions in `test_integrations` and `test_cli_integrations` | test assumption | the mode is still asserted where it exists, guarded in place |
| `test_config` doctor tests hard-coding `/tmp` and `/srv` | test assumption | sample paths are built from the platform's own anchor |
| `test_diagnostics` redaction test spelling `data/db.sqlite3` with a forward slash | test assumption | the sample path is built with the platform's separator |
| `test_backup` `test_an_idle_connection…` → `WinError 5` from `os.replace` | documented platform limit | the test now asserts the outcome the platform produces (see below) instead of skipping |
| `test_desktop_handlers` `WinError 32` when the temporary folder was removed while the app was still open | test defect | the app is closed inside the `with` block |
| `test_store` symlink test: `mock.patch.object(os, "O_NOFOLLOW", 0)` → `AttributeError` (attribute absent on Windows) | test assumption | `create=True`; reproduced locally by deleting `os.O_NOFOLLOW` in a child interpreter (error before, `OK` after) |
| Four findings recorded on both Windows legs at `b04ad90`: two mode-verification tests, the swap-write test, and the child-suite leak watch (which cascades from any suite failure) | two test assumptions + one documented platform limit | as recorded in section 4.1 |

### 4.1 The four findings at `b04ad90`, exactly as the annotations reported them

```
4 distinct failures recorded :: FAIL: test_a_write_attempted_during_the_swap_is_refused_rather_than_silently_discarded
(test_backup.RestoreTests), FAIL: test_the_suite_leaves_no_sqlite_connection_open
(test_resource_lifecycle.SuiteConnectionLeakTests), FAIL: test_require_owner_only_reports_a_file_that_cannot_be_protected
(test_store.PrivateFileCreationTests), FAIL: test_a_filesystem_that_ignores_the_mode_leaves_no_readable_export
(test_store.PrivateFileWriteTests)
```

* The two mode-verification tests check that a file is owner-only **after** the mode was applied, and one of
  them simulates a mount whose `chmod` silently does not apply. Where there are no mode bits there is nothing
  to apply and nothing to verify, so the refusal they expect cannot happen. They now skip there, with that
  reason in the skip message, and the writing paths are held by `PlatformWithoutPosixModeBitsTests`, which
  patches the module's `os` the way a platform without mode bits looks.
* `test_a_write_attempted_during_the_swap…` relies on the exclusive guard being held across `os.replace`. The
  module cannot hold it where the operating system refuses to replace a file another handle has open
  (`_CAN_REPLACE_AN_OPEN_FILE`); there, the refusal is the operating system's — which has its own test
  (`test_where_the_platform_cannot_replace_an_open_file_the_guard_is_released_before_the_swap`) — and the
  instant between releasing the guard and the swap is a **stated limit of the module**, not a guarantee. That
  branch now asserts the documented outcome instead of failing on it; it was executed locally by forcing the
  constant to the platform's value.
* `test_the_suite_leaves_no_sqlite_connection_open` runs the whole suite in a child process and fails when the
  child fails, so it is a cascade of the three above and needs no change of its own.

## 5. Other evidence gathered on this machine

**Python 3.11.2, source checkout:** `python3 -B -m unittest discover -s tests` → `Ran 1600 tests in 44.0s`,
`OK (skipped=13)`; `python3 -B -m compileall -q career_agent scripts tests` → clean;
`python3 -B -m unittest tests.test_documented_commands` → 5 tests, OK.

**Optional PDF extra, Python 3.11.2, `pypdf 6.20.1`:**
`python -m unittest discover -s tests -p "test_resume*.py"` → `Ran 78 tests … OK`, **no skips**. The PDF cases
skip without the extra, which the `pdf-extra` job proves on every run by running the module both ways.

**A database that is intact but cannot be written** (defect D5, reproduced again today on a folder at mode
`555`):

```
$ python -m career_agent --database /tmp/d5/career_agent.sqlite3 --import-from /tmp/d5b/export.json --yes
… Nothing has been written yet; this is what an import would do.
REFUSED: this database could not be written to, so nothing was changed: attempt to write a readonly database
A read-only file or folder, a folder that is not there, or another program holding the database are the usual
reasons. `python -m career_agent --doctor` reads the same database without writing to it and reports what it finds.
$ echo $?
2
```

The words matter here: the refusal used to say *"this database file could not be read"* and advise restoring a
verified backup over the file — a read described for a write, with a remedy that would fail identically.
`tests/test_damaged_records.WriteRefusalTests` fails on the old wording.

## 6. How a failure is read from here at all

Job logs are served from a host this network cannot reach, and the API answers a failed step with its exit
status alone. So:

* every step of the three jobs that verify the product, from the interpreter report to the smoke test, opens
  with `exec > >(tee -a "${RUNNER_TEMP:-$HOME}/ci-notes.txt") 2>&1`, and a step of its own creates the file
  first, so whichever step fails is the one whose output was recorded;
* `scripts/ci_annotate.py` turns that file into annotations when the job fails: one listing **every** failing
  test by name (`--names 200`, de-duplicated), ten findings with the end of each traceback, and the run's last
  words. A step may carry only ten error and ten warning annotations, which is why the inventory exists — the
  twenty findings the detail slices can carry were not enough to see a 949-error run;
* on a green run the same mechanism publishes the numbers *and* the platform's own account of itself - the
  interpreter, the platform string, the Tk version, the screen Tk reported, the suite's counts, the widget
  check's verdict and the smoke test's `RESULT:` line - because "the job is green" is not evidence of what
  ran, and it was not evidence of which platform had a window either (section 9).

## 7. What is verified where (and what is not)

| Capability | Linux (this machine, 3.11.2) | Linux runner (Xvfb) | Windows runners | macOS runners | Human at a keyboard |
|---|---|---|---|---|---|
| Full suite | yes (1600, OK) | yes ×4 interpreters | yes ×2 | yes ×2 | — |
| Installed wheel and console script | yes | yes ×2 | yes | yes | — |
| `--version`, `--doctor` on a missing/damaged/read-only database | yes | — | yes | yes | — |
| Schema creation, migration, persistence | yes | yes | yes | yes | — |
| Backup/restore, export/import | yes | yes | yes | yes | — |
| Discovery closed (gate + no enabled sources) | yes | yes | yes | yes | — |
| Tk availability | **no Tkinter** | yes | **yes** (Tk 8.6; `PASS: Tk 8.6 built a root, a frame and a label and updated them`) | **yes** (the same, both interpreters) | — |
| Real window built and driven by a script | **BLOCKED** (exit 2, no tkinter) | **yes** (smoke test passes under Xvfb) | **yes** (14 checks: window built, tabs and lists read, refresh commands invoked, database released) | **yes** (14 checks, the same) | — |
| Mouse/keyboard interaction, pixels, layout, dialog wording | no | no | no | no | **not done** |

Remaining, stated plainly: the 76 manual checklist steps are untouched by all of the above - a script that
builds and drives the window on five runners is still not a person reading a dialog, a menu or a layout;
packaging, signed bundles and installers do not exist, so nothing here speaks for a *packaged* build on any
operating system; the support policy stays at CPython 3.10–3.13 because no 3.14 interpreter has been
exercised; live integrations remain disabled behind the source-quality gate.

## 8. Data and invariants (verified in this increment)

```
$ sha256sum research/job-source-audit-seed-2026-10-13.csv
0356b093ded3917c0fa9ba3aa9f12a682caaf81df7c49a6b042950d66a08f414  research/job-source-audit-seed-2026-10-13.csv
$ python3 -c "from career_agent.sources import SOURCE_QUALITY_GATE_PASSED, enabled_discovery_sources; print(SOURCE_QUALITY_GATE_PASSED, enabled_discovery_sources())"
False ()
```

Every database used above is synthetic and disposable, created under `/tmp`; no candidate data, credential or
generated database is committed.

## 9. Two defects in the pipeline that produced this evidence (D11, D12)

### D11 - a reporting step failed the Windows legs of a run whose checks had all passed

Run 38715164487 (`c2ad285`, the first run carrying the summary step) reported both Windows legs red with every
check inside them green: the two red steps were the reporting ones, and the API said only
`Process completed with exit code 1`. The cause, reproduced here: the notes file mixes encodings - the bash
steps write UTF-8, the Python steps write the platform's ANSI code page - so the em dash in a recorded
`RESULT: BLOCKED — …` line reaches the file as a lone `0x97` byte. The tail mode reads the notes as UTF-8 with
`errors="replace"`, which turns that byte into U+FFFD, and printing U+FFFD through a console code page raises
`UnicodeEncodeError`:

    $ PYTHONIOENCODING=cp1252 python3 <the script as it was> /tmp/repro/ci-notes.txt --tail 3 --level notice
    UnicodeEncodeError: 'charmap' codec can't encode character '\ufffd' in position 99   # exit 1

Fixed in `76d0a3c`: the script prints workflow commands as UTF-8, which is what a runner reads; drops control
bytes that would corrupt a command rather than sending them; and publishes everything unexpected as a warning
annotation carrying the error, so a defect in the reporting can neither redden a passing run nor stay silent.
The checks still fail the job through their own exit codes. Four tests in `tests/test_ci_annotate.py` pin it,
one of them writing the notes with the byte a Windows run leaves and driving the tail mode through cp1252 and
cp437. Run 38716978550 (`76d0a3c`) is green, 12 jobs.

### D12 - a window check that had never run anywhere, reported as a platform limit

Once D11 was fixed the platform legs' own annotations became readable, and they contradicted each other. The
widget-lifecycle step, on all four Windows and macOS legs:

    ::warning::the Tk widget lifecycle could not run on this runner (exit 2, BLOCKED)

and the desktop smoke test, one step later on the same runner:

    RESULT: PASS — 14 checks passed. The window was built on a real display, …

One of the two was wrong and the step could not say which, because it classified every exception as a missing
display and published no reason. Made honest in `d56172d` - classifying the way
`scripts/desktop_smoke_test.py` already did, by importing its `looks_like_no_display` instead of keeping a
second copy of the phrase list, and publishing the reason in the warning - the next run answered per platform:

* Windows, both interpreters: `FAILED: a Tk root was created, but its widget lifecycle is broken:
  AttributeError("module 'tkinter' has no attribute 'ttk'")`. `tkinter` does not import its `ttk` submodule on
  demand, so the check's first real use failed on every platform it ever ran on, and the old code called that
  "no display".
* macOS, both interpreters: `unexpected EOF while looking for matching` (bash's own words) - the here-document
  inside a command substitution added by `d56172d` is not parsed by the bash 3.2 macOS ships, so the step died
  before its first command ran.

Both fixed in `e803286`, which is green (run 38719357147, 12 jobs). The step now prints the verdict it reached
- `PASS:`, `BLOCKED:` with Tk's own phrase, or `FAILED:` - and a BLOCKED carries its reason into the warning, so
a check can no longer answer "could not run here" without saying why. Verified by driving the extracted step
body against a tkinter stand-in: a working Tk prints PASS and exits 0; Tk's no-display phrase prints BLOCKED
and exits 2 with the phrase in the warning; a root that raises anything else prints FAILED and exits 1; a root
whose widgets do not honour what they were asked for prints FAILED and exits 1. A real failure now fails the
step, where before it was published as BLOCKED.

## 10. Commits this evidence describes

In the order they were made, oldest first:

| Commit | What it did |
|---|---|
| `9a0a97b` | every cross-platform step records its output into the notes file; the wheel is built and verified outside the checkout |
| `f976c3c` | POSIX-only guarantees are asserted where the platform has them; the window closes before its folder |
| `c10fc72` | rules, README, architecture, design and phases describe the above |
| `c102aff` | the flag patch on a platform that has no such flag; the idle-connection limit asserted per platform |
| `b04ad90` | the whole failure inventory in one annotation (`--names`), and the documents that describe it |
| `f38ac49` | the mode-verification tests skip without mode bits; the swap release window is asserted as a window |
| `d841615` | a green run publishes the numbers it ran, not only the failure it hit |
| `21475ee` | the cross-platform evidence, the platform limits and the checklist's second follow-up |
| `c2ad285` | phase 3 of the platform work (section 8.1 of the release-readiness audit) and the macOS evidence line |
| `76d0a3c` | the reporting steps cannot fail a run whose checks passed, and cannot fail silently (D11) |
| `d56172d` | the window check says which verdict it reached, and why, classifying as the smoke script does |
| `e803286` | the window check imports `tkinter.ttk` and works under macOS's bash 3.2 (D12) |
| `e70ee1e` | every platform leg publishes its interpreter, its Tk, the screen Tk reported and its own verdicts |
| `980e93e` | sections 2.1, 9 and 11 written down: the per-leg values, the two defects and the limits of this file |
| `7517590` | the `unit-tests` and `installed-package` jobs record and publish their evidence too (D13) |

## 12. D13, added while closing this file

Run 38723866093 failed in bare `unit-tests (3.11)` - the one job that still recorded nothing - and the API
could say only `Process completed with exit code 1`. That is the rule in `rules.md` being enforced by a
failure: a failing run must publish its evidence where the project can read it. Both remaining jobs now
record every step's output into the notes file and publish, on failure, the failing test names, ten findings
with the end of each traceback and the run's last words; on a green run they publish the numbers, and the
`unit-tests` job's notice now carries the seed data (`csv: 0356b093… over 83 records`) as well. Verified by
running the extracted step bodies here; that dry run also caught a defect of mine before it reached a runner
(the new CSV line read a key the audit does not print, `records` instead of `record_count`, and exited 1 on
the KeyError). Run 38725527363 at `7517590` is green, 12 jobs, and `unit-tests (3.11)` did not fail again -
whether its single failure was a flake is not known, and it is not claimed either way; what is now true is
that a recurrence will be readable.

Runs 38713190679 (`f38ac49`), 38716978550 (`76d0a3c`) and 38719357147 (`e803286`) are green, 12 jobs each.
`e803286` is the state described here; PR #2 remains open and unmerged, and `main` has not been touched.

## 11. What a reader of this file should not conclude

* Not that a person has used the window on any platform. Five runners build and drive it; the manual
  checklist's window steps are BLOCKED until a human executes them.
* Not that macOS or Windows *packaging* works: no installer, bundle or signature exists, and no leg tests one.
* Not that the runner's Tk is the same as the machine's: the versions are recorded per leg in the annotations
  (`tkinter: Tk 8.6`), and the interpreter and platform strings travel with them.
* Not that a BLOCKED line means a missing capability. It did not on 2026-10-15 (section 9).


## 14. The seven workflows, run through the real window on three platforms

**What was added.** `scripts/desktop_acceptance.py` drives the real `CareerAgentApp` through its own widgets
and commands on a disposable synthetic database: it types into the real entries and choosers, presses the real
buttons with Tk's `invoke`, answers the dialogs a person would answer (recording every one), and then checks the
stored records and the window's own status line. Seven workflows, 46 checks:

| Workflow | The claim it checks | Checks |
| --- | --- | --- |
| A — candidate profile | a synthetic profile, a role and a qualification typed through the window come back after close and reopen | A1–A6 |
| B — the two job URLs | a source listing URL and a blank employer apply URL stay separate fields, the blank one stays blank after a reopen, nothing is submitted and no discovery source is enabled | B1–B5 |
| C — eligibility safety | no availability evidence means UNKNOWN and a refused shortlist; with the requirements stated explicitly the same application reaches PASS and may be shortlisted | C1–C6 |
| D — tracker and analytics | the status dialog offers exactly the statuses the domain permits, a confirmation is refused until the person asserts it, and a recorded interview round is never counted as an application sent or as an outcome | D1–D8 |
| E — export, import and refusal | the export agrees with the database and warns that the file may hold personal data; a malformed file, a damaged record, an unprotected target and a declined plan all write nothing; a repeat import adds nothing | E1–E9 |
| G — work history and study | a current role added through the form, an impossible period and a date in another shape refused with nothing stored, an ongoing qualification added and a contradictory one refused, a role's stored values loaded into an emptied form and its title saved back over the record, and the current-role flag taken off again with an end date saved | G1–G8 |
| F — cleanup and lifecycle | every window and connection released, the disposable folder gone, the person's own database bit-identical, including after a forced failure | F1–F4 |

The exit codes are the project's own: `0` for `RESULT: PASS`, `1` for `RESULT: FAIL`, `2` for BLOCKED — no
`tkinter`, or no display, is never a pass. The run also compares the number of checks it performed against the
number its own source declares, so a check that stops running fails the run instead of shrinking it.

**Where it runs.** The display-backed Linux job runs it under Xvfb and requires `RESULT: PASS`, every workflow
header the script declares and no failure line; a step with `DISPLAY` unset requires BLOCKED; a third step requires that the
stand-in development run (`--stand-in-tk`, which drives the test suite's stand-in widget module) reports a
DEVELOPMENT RUN, prints no pass or failure line and exits 2, so a stand-in result can never be CI evidence. The
Windows and macOS legs run the same workflow script and tolerate only BLOCKED (a runner with no display
session), and the same run of the suite on those legs re-runs it in a child interpreter.

**The evidence: run 38747830528 at `e939260`, all 12 jobs successful, 46/46 checks on every leg below.**

Every row was read from that run's own annotations, figures and all, so no row is carried over from an
earlier run.

| Leg | Interpreter and platform | Tk and screen | Acceptance run | Suite |
| --- | --- | --- | --- | --- |
| Desktop smoke (Linux, display-backed) | CPython 3.12 (system), ubuntu-latest | Tk 8.6, from `/usr/lib/python3.12/tkinter/__init__.py`; `1280x1024 pixels from X11R0 The X.Org Foundation 12101011` | `RESULT: PASS — 46 checks passed` | — |
| Cross-platform (windows-latest, 3.13) | 3.13.15, `C:\hostedtoolcache\windows\Python\3.13.15\x64\python.exe`, `Windows-2025Server-10.0.26100-SP0` | Tk 8.6 Tcl 8.6, from `…\Lib\tkinter\__init__.py`; `1024x768 pixels from Windows 10.0 26100 Win64` | `RESULT: PASS — 46 checks passed` | 1642 tests, OK (37 skipped); 78 tests, OK |
| Cross-platform (windows-latest, 3.10) | 3.10.11, `C:\hostedtoolcache\windows\Python\3.10.11\x64\python.exe`, `Windows-10-10.0.26100-SP0` | Tk 8.6 Tcl 8.6, from `…\lib\tkinter\__init__.py`; `1024x768 pixels from Windows 10.0 26100 Win64` | `RESULT: PASS — 46 checks passed` | 1642 tests, OK (44 skipped); 78 tests, OK |
| Cross-platform (macos-latest, 3.13) | 3.13.16, `/Library/Frameworks/Python.framework/Versions/3.13/bin/python`, `macOS-26.6.2-arm64-arm-64bit-Mach-O` | Tk 8.6 Tcl 8.6, from `…/3.13/lib/python3.13/tkinter/__init__.py`; `1024x768 pixels from CG0.0 Apple AppKit 2685.7 Mac OS X 1a0602` | `RESULT: PASS — 46 checks passed` | 1642 tests, OK (13 skipped); 78 tests, OK |
| Cross-platform (macos-latest, 3.10) | 3.10.11, `/Library/Frameworks/Python.framework/Versions/3.10/bin/python`, `macOS-26.6.2-arm64-arm-64bit` | Tk 8.6 Tcl 8.6, from `…/3.10/lib/python3.10/tkinter/__init__.py`; same screen string | `RESULT: PASS — 46 checks passed` | 1642 tests, OK (20 skipped); 78 tests, OK |

The same workflows also ran green on run 38739493727 at `a530029` (38 checks), run 38737533708 at `dbaa082`
(37 checks) and run 38735309770 at `dfea62d` (36 checks); each number is what the script declared at that
commit, and the count is checked against its own source, not against a number kept in CI. The newest green run at the time of writing - 38752606452 at `90e4b3f`, 12 jobs - reports
`RESULT: PASS — 46 checks passed` on the Linux display leg and on macOS 3.13 alike, with the suite at 1643
tests, `OK (skipped=13)`. The Windows annotation prints the em dash as `�` — the runner's
encoding, as recorded in section 2.1, not a different result.

**Two more that only real Tk could show (D15, D16).** Run 38741309350 at `a7349e8` failed G7 on all five legs
with `expected exactly one the current-role checkbox, found 0` — a lookup that had matched earlier in the same
window, and a failure that said what was missing but not what was there instead. `linked_to` now compares a
widget's binding against both spellings of the variable's name (`str(variable)` and `variable._name`) and reads
a value Tk hands back as its own object through `str()`, and a failed lookup now names the variable it wanted
and lists what every widget of that class is actually bound to (`describe_bindings`), which is what this
write-up would have needed on the first failure. The same commit added G8, which then failed on run 38745335163
at `8f6874d` with `the role was stored as current=True, end=None`: the save in G7 rebuilt the history list, and a
rebuilt list deletes and re-inserts every row, which takes the selection away in a real window — so the step
that pressed a button acting on the selected row, and the check that the form had been loaded, were reading a
selection and a form that were no longer what they seemed. Both G steps now empty the form first, choose the
row again, and check that the window did not have to ask for a selection that was made; the stand-in tree the
unit tests use was corrected too, because it had kept a deleted row selected, which is how its own scheduler
test came to rely on a selection a real refresh removes. Fixed in `e939260`.

**A timing dependence in a unit test, not in the product.** The windows-3.13 leg of run 38741309350 also failed
`test_updating_an_older_database_keeps_a_verified_copy_of_it` with `['kept', 'also-kept'] != ['also-kept', 'kept']`.
`list_jobs` orders by `first_seen_at` and then by id, and `first_seen_at` is written at whole-second resolution,
so two saves either side of a second boundary come back in the order they were saved: the case was asserting the
runner's speed. Reproduced off-CI (`['kept', 'also-kept']` with the saves a second apart) and fixed in `c0314c2`
by saving both rows through the store's own `observed_at` parameter, with the assertion unchanged.

**An earlier defect that only real Tk could show (D14).** The first display-backed run of these workflows (38734920175 at
`115ad2a`) reported 35 of 36 checks passing, and the failure was F4:
`_tkinter.TclError: can't invoke "winfo" command: application has been destroyed`. After the run's root was
destroyed, `winfo_exists` did not answer "gone" — it raised, and the check read that exception as the window
having survived, reporting a defect in a cleanup that had worked. The stand-in could not have produced this: it
has no interpreter to destroy. Fixed in `dfea62d` by reading Tk's refusal to answer as the window being gone
(`widget_exists`), with five regression tests pinning an interpreter that is gone, a widget really destroyed,
and a widget really still there. No other check failed on any leg, before or after.

**What this does not establish.** No person has used this window, on any platform. Layout, clipping at small
sizes, dialog wording and clarity, keyboard-only navigation and focus order, screen-reader behaviour, real
mouse-driven flows and general native feel are not examined, and no check inspects pixels. The checklist's
window steps stay BLOCKED for those reasons; where a step's *functional* claim is now covered by the table
above, the step records that beside its BLOCKED verdict rather than being marked PASS
(section "Automated coverage of numbered steps" in the checklist). Automated, machine-observed behaviour on a
runner is not a substitute for a person using the application, and is not reported as one.

## 15. Ten workflows, 76 checks: follow-ups, the scheduler and data safety on five legs

Section 14 records the seven workflows of `scripts/desktop_acceptance.py` as they stood at `e939260` (46
checks). Three more have been added since, and the script now declares **76 checks**, still in one file, still
against the real `CareerAgentApp`, each workflow in its own disposable database. Workflow I (the scheduler) and
workflow J (data safety) were added after workflow H, and each is counted by CI's own step: the run's source
declares the number of checks, the runner compares it with the number that ran, and a mismatch fails the job.

**Workflow H — follow-up reminders and the combined next-action list (H1–H14).** An application saved in the
window has no follow-up day; with it selected on the **Application tracker** tab its first day is recorded
through the tab's own button, and the row carries the day, the note and "in 2 day(s)" while the stored status
and the confirmation flag are untouched; days computed from fixed offsets read "3 day(s) overdue", "due today"
and "in 20 day(s)"; the list is ordered by day and the summary leads with "1 overdue, 1 due today: 2
application(s) need a look."; a day is moved and cleared from its own row, a declined clear changes nothing and
an accepted one leaves the status alone and empties the fields; the list survives closing and reopening the
window; a preparation item is added through its own dialog (its kind chooser offering the documented kinds) and
appears as a next action with its day, an item with no day lists as "No day set" rather than being hidden, and
ticking one off writes "Done: … The application's status was not changed."; buttons that do not apply to a
reminder explain instead of acting; a reminder whose listing or application record has gone is reported rather
than acted on; and the calendar preview and the email draft are read-only — no file written, nothing sent, no
confirmation event anywhere. **Workflow I — the schedule (I1–I8).** The schedule starts empty, no worker holds
the lease and the tab says so; the default tasks are added through the tab and adding them again creates
nothing and leaves the stored tasks untouched; pausing asks first and a declined confirmation changes nothing;
an accepted pause keeps the task's name, kind, times, timezone and recorded history and its row reads "paused";
that survives closing and reopening the window; resuming schedules the next run ahead of now and replays no
missed occurrence; a task deleted behind the window is reported rather than written back; and using the tab
takes no lease, records no attempt and writes no `task.run_*` or `worker.*` event. **Workflow J — data safety
(J1–J8).** A backup is written through the Data safety tab's own chooser and verified before the window reports
success, its file holds the database's records and is owner-only on POSIX, and the live database's digest does
not move; an existing destination is never overwritten and a destination that cannot be written is refused with
nothing left behind; a cancelled chooser writes nothing and raises no dialog; a text file, another program's
database, a file truncated to its first 4 KiB and a copy marked with a newer schema version are each refused
under "Backup cannot be used" with "The current database was not changed."; declining the restore confirmation
changes not one byte; a confirmed restore undoes a listing saved after the backup, brings the profile back,
leaves the window's list matching the stored records, keeps exactly one `<database>.backup-<timestamp>` copy
holding the pre-restore counts and leaves the database writable; a restore is refused while another connection
holds the database; and nothing temporary is left beside any database on success or failure.

**The evidence: run 38762008724 at `5b291a7a`, all 12 jobs successful, 76/76 checks on every leg below.**

| Leg | Interpreter and platform | Tk and screen | Desktop acceptance | Suite |
| --- | --- | --- | --- | --- |
| Desktop smoke (Linux, display-backed) | CPython 3.12 (system), ubuntu-latest | Tk 8.6, from `/usr/lib/python3.12/tkinter/__init__.py`; `1280x1024 pixels from X11R0 The X.Org Foundation 12101011` | `RESULT: PASS — 76 checks passed` and, separately, `RESULT: PASS — 14 checks passed` for the smoke entry point | no suite in this job; the script asserts its own declared check count |
| Cross-platform (windows-latest, 3.13) | 3.13.15, `C:\hostedtoolcache\windows\Python\3.13.15\x64\python.exe`, `Windows-2025Server-10.0.26100-SP0` | Tk 8.6 Tcl 8.6; `1024x768 pixels from Windows 10.0 26100 Win64` | `RESULT: PASS — 76 checks passed` | 1648 tests, OK (37 skipped); 78 tests, OK |
| Cross-platform (windows-latest, 3.10) | 3.10.11, `C:\hostedtoolcache\windows\Python\3.10.11\x64\python.exe`, `Windows-10-10.0.26100-SP0` | Tk 8.6 Tcl 8.6; same screen string | `RESULT: PASS — 76 checks passed` | 1648 tests, OK (44 skipped); 78 tests, OK |
| Cross-platform (macos-latest, 3.13) | 3.13.16, `/Library/Frameworks/Python.framework/Versions/3.13/bin/python`, `macOS-26.6.2-arm64-arm-64bit-Mach-O` | Tk 8.6 Tcl 8.6; `1024x768 pixels from CG0.0 Apple AppKit 2685.7 Mac OS X 1a0602` | `RESULT: PASS — 76 checks passed` | 1648 tests, OK (13 skipped); 78 tests, OK |
| Cross-platform (macos-latest, 3.10) | 3.10.11, `/Library/Frameworks/Python.framework/Versions/3.10/bin/python`, `macOS-26.6.2-arm64-arm-64bit` | Tk 8.6 Tcl 8.6; same screen string | `RESULT: PASS — 76 checks passed` | 1648 tests, OK (20 skipped); 78 tests, OK |

The Windows annotations replace the em dash with an unreadable replacement character, the runner's encoding as
recorded in section 2.1, not a different result. Workflow I's
first green run was 38761595835 at `d12c2bcb` (68 checks, 12/12 jobs); workflow J's is the run above. The
stand-in development path (`--stand-in-tk`) reports 76 passed with `RESULT: BLOCKED` and exit 2 on the machine
without a display; it is a development aid and is never used as evidence of real-window behaviour, which is why
every number above comes from a display-backed leg.

**A defect workflow H found on a real display (D17, and a second fix at `0215413`).** Two real-window failures
came out of these workflows and each is fixed with a regression test at the handler level:

- **D17 — the first follow-up day could not be recorded anywhere in the window.** The Follow-ups tab lists only
  applications that already hold a day, so its list is empty precisely when a person records the first one; the
  button that sets the day read its subject from that empty list and always refused with "Select an
  application". Workflow H1–H2, which records the first day for an application selected on the tracker tab, is
  the display-backed proof; the fix is in `480dca1` and the handler-level regression test fails before it.
- **A rebuilt list takes the selection away (`0215413`).** Workflow H5 failed on all five legs of run
  38758158210 with `SmokeFailure: the fields still hold a day that was cleared` at the acceptance script: after
  a clear, the list is rebuilt, real Tk fires `<<TreeviewSelect>>` on the rebuilt tree, and the tab's handler
  refilled the fields from the *Jobs-tab* selection. The binding now reads only the reminder list's own row (and
  says so), the acceptance step re-selects the row it acts on exactly as a person does, and the fail-before-fix
  check reproduced with `AssertionError: '2026-10-24' != ''`. The stand-in tree could not produce this: it
  re-inserts rows without firing the event.

**What this does not establish.** Nothing here was judged by a person on any platform. Layout and clipping,
dialog wording, keyboard-only navigation and focus order, screen-reader behaviour, mouse-driven flows and
native feel are outside every check above, no check inspects pixels, and the checklist's window steps stay
BLOCKED for those reasons — with the functional claim recorded beside the verdict where a workflow now covers
it. A backup, a pause and a reminder are also not evidence that a person would find them understandable.

## 16. D18 — a verdict that depended on the hour CI ran at (run 38781575276 at `e69e5836`)

**What the run said.** The twelve-job matrix came back red on exactly two jobs, both Windows
(`Cross-platform (windows-latest, Python 3.10)` and `3.13`), with three failures each: the two
`SchedulerTabTests` below and `SuiteConnectionLeakTests.test_the_suite_leaves_no_sqlite_connection_open`,
which re-runs the whole suite in a child process and therefore reported the same two failures a second time.
Every other job — the four `unit-tests` legs, both macOS legs, the display-backed Linux leg, both
`installed-package` legs and the PDF extra — was green on the same commit. The annotations gave the two
messages verbatim:

```
FAIL: test_a_finished_attempt_appears_with_its_outcome_and_how_long_it_took
  AssertionError: 'follow-up-digest' != 'daily-backup'          (tests/test_desktop_handlers.py:5353)
FAIL: test_pausing_keeps_the_task_its_times_and_its_history
  AssertionError: Lists differ: [] != ['wrote one snapshot']     (tests/test_desktop_handlers.py:5432)
```

**Why only the Windows legs.** The jobs' own timestamps (read from
`repos/rajaryan1111/ai-career-agent/actions/runs/38781575276/jobs`, converted to Asia/Kolkata) show the
whole matrix starting at 23:27 IST and the boundary falling inside the Windows suite:

| job | ran (IST) | crossed 23:30? |
| --- | --- | --- |
| `unit-tests` (3.10–3.13) | 23:27:09 → 23:28:10 | no |
| `Cross-platform (macos-latest, …)` | 23:27:13 → 23:29:51 | no |
| `Cross-platform (windows-latest, …)` | 23:27:09 → 23:37:29 / 23:38:02 | **yes** |

**The cause is the test's own clock dependence, not the product.** A claim takes the earliest due task
(`SELECT … WHERE enabled = 1 AND next_run_at <= ? ORDER BY next_run_at, task_id LIMIT 1`, `store.py:2049`),
and both tests seeded the three default tasks from the real clock and then paused only
`scheduled-discovery`. Seeded before 23:30, the 23:30 backup slot is the earliest due occurrence and the
claim lands on `daily-backup`. Seeded after it, the backup rolls to the next evening while the 09:00
`follow-up-digest` slot is already due, so the earliest due task is the digest — which is what the two
annotations show. The product's behaviour is correct and documented; the test asserted a fact about the
arrangement that only held for part of the day. Classification: **test defect**.

**The smallest correct fix.** The helper these tests share (`disable`, which paused one named task) became
`keep_only(task_id)`, which pauses every *other* default task, so the task under test is the only one left
that can be claimed; the two tests keep every assertion they had, and no product line changed. The
assertion that the other tasks are still listed ("pausing is not deleting") stays in place.

**Regression test.** `SchedulerTabTests.test_the_claim_a_test_makes_is_the_task_it_asked_for_at_any_hour`
seeds the defaults at a fixed `2026-10-16 23:38 Asia/Kolkata` — the window the Windows legs were in —
asserts that the digest is genuinely due before the backup (so the test cannot quietly stop exercising the
ambiguous hour), removes the other tasks from contention, claims at the backup's own slot and requires the
run to belong to `daily-backup`. Fail-before proof: with the old one-competitor pause restored the test
fails with `- follow-up-digest / + daily-backup`, the same shape as the CI annotation; with the fix it
passes, and it passes at any hour because the seed no longer reads the clock. Fix and test are in commit `6e92c9b` on
this branch; the suite total moved 1651 → 1652.

**What this does not establish.** This is a unit-level verdict about a test's own arrangement. It adds no
window coverage: the checklist's window steps remain BLOCKED for the reasons in section 15, and no run in
this file is a human acceptance.

## 17. D19 — a database restored from itself (found by probing the command line, not by CI)

**What was done.** A disposable synthetic database in `/tmp` was opened through the real entry point and
each file-taking command was given a path a person might plausibly paste: an existing directory, a file that
already exists, and — the case that mattered — **the database's own path**. Everything refused cleanly except
that last one:

```
$ python -m career_agent --database /tmp/probe/live.db --restore-from /tmp/probe/live.db --yes
Restored /tmp/probe/live.db
from     /tmp/probe/live.db
Contents: no profile · 0 jobs · 0 tracker records · 0 activity entries · schema version 6
Previous database kept as a verified copy: /tmp/probe/live.db.backup-20261015T185238Z      (exit 0)
```

The recorded digest of the database changed (`f1583463…` → `99e03cfe…`), and a snapshot file that nobody
asked for was left beside it. No data was lost — the file was replaced by a copy of itself — but three
things were wrong: the command reported success for a no-op, it rewrote a file it had no reason to touch,
and it wrote into the folder the database lives in. The most likely way to reach it is to paste back the
path the product's own refusal advice suggests (`--restore-from "<backup file>"`), which is exactly what a
person does after reading a start-up failure message.

**Classification: product defect**, in the data-safety path, found by probing rather than by reading.

**The smallest correct fix.** `career_agent/backup.py` compares the chosen file with the live database
*before* validating or staging anything, and refuses with

```
REFUSED: /tmp/probe/live.db is the live database itself, so there is nothing to restore from it and
nothing was changed. Choose a backup file written by this application.
```

The comparison uses device and inode (`os.path.samefile`), so a hard link and a symlinked folder are caught
as well as the same path spelled twice, and falls back to comparing resolved paths for the cases the
platform will not stat. A real backup whose *contents* happen to match is still restored — the refusal is
about the same file, not about equal data.

**Regression tests (both fail before the fix, both pass after).**
`tests/test_backup.py::RestoreTests::test_a_database_is_never_restored_from_itself` covers the same path, a
differently spelled path and a hard link, and requires the database to be byte-identical, no snapshot beside
it and no staging file left behind; before the fix it fails with `BackupError not raised` (three subtests
behind one `subTest` loop). `tests/test_cli_backup_restore.py::
RestoreCommandTests::test_the_database_is_refused_as_its_own_backup_on_the_command_line` pins the
user-facing half — exit code 2, the refusal on stderr, `Restored` absent from stdout, bytes unchanged — and
fails before the fix with `AssertionError: 0 != 2`. `test_a_restore_from_a_copy_of_the_database_still_works`
is the guard against over-refusing. Fix and tests are in commit `a29d2d4`.

**What this does not establish.** The same-file case is refused, not "handled": a person who really does
want to re-install their own database from a copy of it must point at that copy, which is the intended path.
Nothing here says anything about restores on Windows (the legs run, but no check replaces a file another
handle holds) beyond what section 15 already recorded.

## 18. The missed-occurrence report: what the schedule walked past while nothing ran

**What it is.** `career_agent/worker.py` gains `missed_occurrences(store)`, a read-only report of the
occurrences the schedule has walked past with nothing recorded for them, and `WorkerStatus.describe()` prints
it. Because both surfaces already share those lines, the window's **Background tasks** tab shows the report
without a second implementation, and `--worker-status` prints exactly what the tab shows.

**What counts as missed, precisely.** A due instant that is an occurrence of that task's own schedule
(enumerated with the same `next_run_after` the scheduler books with, so zone gaps and repeats are the
scheduler's answers rather than a second implementation's), has no attempt row for it — a refusal, a failure
and an interruption were all attempts — owes no retry, and is not the instant the next claim will take. The
last exclusion is what makes this different from the `(due now)` marker: `plan_after_run` schedules the run
after a finished attempt from the moment the process finished, so every *other* occurrence between there and
now is one nothing will ever come back to. The window is bounded to seven days, cut off at each task's own
creation, and the report says which window it used. Reading it takes no lease, writes no run row and records
no event — a test asserts each of those.

**It is not a catch-up.** Nothing runs a missed occurrence, and the report says so in the surface that
displays it ("Nothing is catching up on these: a worker that is not running cannot run what it missed"). A
catch-up would start a day-old backup on the next launch; that is a behaviour change nobody asked for and it
stays unimplemented, which is why phase 5's laptop-off exit criterion is still unmet (see `phases.md`).

**Coverage.** Eight module tests in `tests/test_worker.py` (the walked-past occurrence with its exact
instant and count; the attempt-of-any-state exclusion; a retry owed rather than lost; a paused task accused
of nothing; occurrences from before the task existed; the bounded window; the argument check; and the
read-only proof across the lease, the run table and the event log), the tab-level test
`tests/test_desktop_handlers.py::SchedulerTabTests::test_the_tab_reports_what_the_schedule_walked_past_while_nothing_ran`,
the command-line test
`tests/test_cli_worker.py::WorkerStatusCommandTests::test_the_report_says_what_the_schedule_walked_past_while_nothing_ran`,
and one new check inside workflow I of the acceptance harness — **I9**, which adds a task whose schedule
nobody ran and requires the tab's own summary to name what was missed, with no worker started, no lease taken
and no attempt recorded. The harness now declares 77 checks; step numbering inside workflow I was left alone,
so I1–I8 keep their meaning and every earlier citation of them still names the same check.

**What this does not establish.** That a person wants this report, or understands it: that judgement is one
of the human-only items in the acceptance handoff. And it establishes nothing about laptop-off operation
itself — a reported missed occurrence is still a missed occurrence.

## 19. D20 — a non-finite poll interval was accepted, and then misbehaved (found by probing)

**How it was found.** The same probing pass that produced D19 walked the command line's other numeric
options. Every date, time and identifier argument refused a bad value cleanly. Two cases did not:

```
$ python -m career_agent --worker --poll-seconds nan      # (cut off after 6 seconds)
AI Career Agent 0.1.0 · worker e2b.local-cli               … and it kept running
$ python -m career_agent --worker --poll-seconds inf
AI Career Agent 0.1.0 · worker e2b.local-cli
…
exit 3                                                     # COULD NOT START, after the header was printed
```

**Why.** ``WorkerSettings.__post_init__`` validated its three numeric fields with ``value <= 0``, which is
**False for NaN** and for positive infinity, so both passed. Measured on the primitives rather than assumed:
``threading.Event().wait(nan)`` returns immediately, so a NaN interval makes the loop's sleep a no-op and the
worker polls as fast as it can; ``threading.Event().wait(inf)`` raises ``OverflowError: timestamp too large to
convert``, which escaped the worker loop *after* it had started and reached the top level as an "unexpected
failure" (exit 3) with a startup-diagnostics note — for one mis-typed number. The tracker, the matcher and the
form validation already refuse non-finite numbers (``core.py``, ``matching.py``, ``validation.py``); the worker
settings were the one place that did not.

**Classification: product defect**, in the command-line/worker boundary.

**The smallest correct fix.** The check now requires a *finite* positive number
(``math.isfinite(value) and value > 0``), and the refusal says so ("poll_seconds must be a positive, finite
number of seconds."). ``run_worker`` catches ``WorkerConfigurationError`` around the settings it builds and
returns the documented refused status rather than letting it reach the top-level handler, so a bad flag value
is a refusal with a message and no diagnostics note; the option's help text says what is accepted. Everything
else about the worker is untouched, and a merely unusual-but-finite value (``0.5``) still works.

**Regression tests (fail before, pass after).**
``tests/test_worker.py::SettingsTests::test_a_non_finite_interval_is_refused_rather_than_run_with`` covers all
three settings against NaN, infinity and negative infinity, requires the refusal to name the field and to say
"finite", and requires a finite value to still be accepted; before the fix it fails with nine
`WorkerConfigurationError not raised` subtest failures. On the command line,
``tests/test_cli_worker.py::WorkerCommandTests::test_an_interval_the_worker_cannot_run_with_is_refused_before_it_starts``
requires exit 2, a `REFUSED` line naming finiteness, and **no output at all on stdout** — the strong form of
"nothing was started" — for `nan`, `inf`, `0` and `-1`, plus a parser-level refusal for `-inf` (argparse reads
it as an option, which is also a refusal). Fail-before for the command-line half was measured directly rather
than through the test runner, because the unfixed code *starts the worker*: `nan` ran until a six-second cap
killed it (exit 124) and `inf` exited 3.

**What this does not establish.** Nothing about intervals that are finite but absurd in practice
(``--poll-seconds 1e9`` starts a worker that will not poll again in this century, which is the operator's own
choice and is left alone). The refusal is about values the worker cannot run *correctly* with.

## 20. Python 3.14 — the leg the audit listed as missing (2026-10-16)

The release-readiness audit recorded the gap precisely: *"Still missing: a CI leg for Python 3.14"*, because
the metadata accepts `>=3.10` while the tested claim stopped at 3.13, and the development environment cannot
obtain a newer interpreter (`uv python install` and a direct download were both blocked by the sandbox's
network policy). The gap was closed where it can be: in CI.

| Leg | What it runs | Result | Run |
| --- | --- | --- | --- |
| `unit-tests (3.14)` | the whole suite, `compileall` over `career_agent/`, `scripts/`, `tests/`, and the research-CSV integrity audit | **success** — `Ran 1702 tests … OK (skipped=13)`, CSV `0356b093ded3…` | [38804198342](https://github.com/rajaryan1111/ai-career-agent/actions/runs/38804198342) at `709242b` |
| `Installed package (3.14)` | `python -m build --wheel`, the wheel's contents, installation into a clean environment, and the installed `career-agent` command run from **outside** the checkout (`--version`, `--doctor`, a throwaway database, backup/restore) | **success** | [38805511543](https://github.com/rajaryan1111/ai-career-agent/actions/runs/38805511543) at `791f9ed` |

The `unit-tests` matrix now names `3.10, 3.11, 3.12, 3.13, 3.14`, and the `installed-package` matrix moved from
3.13 to 3.14 beside the 3.10 floor, so the interpreter the suite runs on and the interpreter the wheel is
built and installed on agree.

**What this does not establish.** No 3.14 leg exists on Windows or macOS, and the display-backed desktop
harness still runs on 3.10 and 3.13 — so "runs on 3.14" is a statement about the Linux suite and the Linux
build/install rehearsal, not about a 3.14 desktop on every platform. `requires-python` keeps its open upper
bound, and an interpreter no leg names is untested rather than supported.
