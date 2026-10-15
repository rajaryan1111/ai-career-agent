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

So on this machine no real Tk widget can be created, and none was simulated. The window is therefore exercised
where a display actually exists: the display-backed Linux runner, and the two platform jobs, which report the
same BLOCKED status there rather than a pass.

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

On the Windows and macOS runners the Tk widget-lifecycle step exits 2 and publishes
`::warning::the Tk widget lifecycle could not run on this runner (exit 2, BLOCKED)` — those hosted runners have
no display session, and the step records that instead of failing the build or pretending the window was
checked. The Linux display-backed job has no such warning: its widget lifecycle and its smoke test both
passed under Xvfb, which is the only place in this pipeline where a real Tk window was built and driven.

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
* on a green run the same mechanism publishes the numbers (a notice annotation with the `Ran N tests`, `OK`
  and `RESULT:` lines), because "the job is green" is not evidence of what ran.

## 7. What is verified where (and what is not)

| Capability | Linux (this machine, 3.11.2) | Linux runner (Xvfb) | Windows runners | macOS runners | Human at a keyboard |
|---|---|---|---|---|---|
| Full suite | yes (1600, OK) | yes ×4 interpreters | yes ×2 | yes ×2 | — |
| Installed wheel and console script | yes | yes ×2 | yes | yes | — |
| `--version`, `--doctor` on a missing/damaged/read-only database | yes | — | yes | yes | — |
| Schema creation, migration, persistence | yes | yes | yes | yes | — |
| Backup/restore, export/import | yes | yes | yes | yes | — |
| Discovery closed (gate + no enabled sources) | yes | yes | yes | yes | — |
| Tk availability | **no Tkinter** | yes | Tk present; widget lifecycle **BLOCKED** (no display session) | Tk present; widget lifecycle **BLOCKED** (no display session) | — |
| Real window built and driven by a script | **BLOCKED** (exit 2) | **yes** (smoke test passes under Xvfb) | **BLOCKED**, reported as such | **BLOCKED**, reported as such | — |
| Mouse/keyboard interaction, pixels, layout, dialog wording | no | no | no | no | **not done** |

Remaining, stated plainly: the 76 manual checklist steps are untouched by all of the above; macOS/Apple
Silicon GUI behaviour is not verified (the runner reports BLOCKED); packaging, signed bundles and installers do
not exist; the support policy stays at CPython 3.10–3.13 because no 3.14 interpreter has been exercised; live
integrations remain disabled behind the source-quality gate.

## 8. Data and invariants (verified in this increment)

```
$ sha256sum research/job-source-audit-seed-2026-10-13.csv
0356b093ded3917c0fa9ba3aa9f12a682caaf81df7c49a6b042950d66a08f414  research/job-source-audit-seed-2026-10-13.csv
$ python3 -c "from career_agent.sources import SOURCE_QUALITY_GATE_PASSED, enabled_discovery_sources; print(SOURCE_QUALITY_GATE_PASSED, enabled_discovery_sources())"
False ()
```

Every database used above is synthetic and disposable, created under `/tmp`; no candidate data, credential or
generated database is committed.

## 9. Commits this evidence describes

| Commit | What it did |
|---|---|
| `9a0a97b` | every cross-platform step records its output into the notes file; the wheel is built and verified outside the checkout |
| `f976c3c` | POSIX-only guarantees are asserted where the platform has them; the window closes before its folder |
| `c10fc72` | rules, README, architecture, design and phases describe the above |
| `c102aff` | the flag patch on a platform that has no such flag; the idle-connection limit asserted per platform |
| `b04ad90` | the whole failure inventory in one annotation (`--names`), and the documents that describe it |
| `f38ac49` | the mode-verification tests skip without mode bits; the swap release window is asserted as a window |

Run 38713190679 was triggered by `f38ac49` and is green; the final state of the branch is on GitHub and PR #2
remains open and unmerged.
