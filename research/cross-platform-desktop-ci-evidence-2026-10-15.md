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

Runs 38713190679 (`f38ac49`), 38716978550 (`76d0a3c`) and 38719357147 (`e803286`) are green, 12 jobs each.
`e803286` is the state described here; PR #2 remains open and unmerged, and `main` has not been touched.

## 11. What a reader of this file should not conclude

* Not that a person has used the window on any platform. Five runners build and drive it; the manual
  checklist's window steps are BLOCKED until a human executes them.
* Not that macOS or Windows *packaging* works: no installer, bundle or signature exists, and no leg tests one.
* Not that the runner's Tk is the same as the machine's: the versions are recorded per leg in the annotations
  (`tkinter: Tk 8.6`), and the interpreter and platform strings travel with them.
* Not that a BLOCKED line means a missing capability. It did not on 2026-10-15 (section 9).
