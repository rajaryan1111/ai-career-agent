# Continuation handoff — 2026-10-21

Written for the next agent or engineer picking this repository up. Everything below was measured on
this machine on 2026-10-21; nothing in it is inherited from an earlier report. **Verify the live Git
state before you edit anything — this document can be out of date the moment it is committed.**

---

## 1. Repository and selected branch

| | |
|---|---|
| Repository | <https://github.com/rajaryan1111/ai-career-agent> |
| **Selected branch** | **`arena/53b00d6c-ai-career-agent`** |
| Latest pushed commit | the commit that adds this file — read it with `git log -1 --format=%H`; the code it documents is `e624b4a` (see §3) |
| Branch URL | <https://github.com/rajaryan1111/ai-career-agent/tree/arena/53b00d6c-ai-career-agent> |
| Open PR carrying it | #4 → base `arena/351e052d-ai-career-agent` |
| Working tree at time of writing | clean, local HEAD == remote head |

### Why this branch and not the one the brief described

The brief described a local checkout on `feature/complete-alpha-implementation` at
`f465b524e4218a39f192c0b5f5307107289015ea` with schema 2 and notification/scheduler failures. That
commit is **not present in this repository** (it is unpushed work on the author's own machine). The
branch of that name does exist on the remote at `d94ea79`, and it belongs to a different, older
track — see §2.

---

## 2. The repository contains three unrelated Git histories

This is the single most important fact on the page, and it was verified with
`git rev-list --max-parents=0` and `git merge-base`:

| Branch | Root commit | Commits | Schema | Test files | Family |
|---|---|---|---|---|---|
| `main` | `127244b5f79e` | 1 | 1 | 4 | **A** |
| `arena/941d963f-...` (PR #3) | `127244b5f79e` | 192 | 8 | 49 | **A** |
| `fix/tracker-integrity-c1-c7` (PR #5) | `127244b5f79e` | 19 | 2 | 13 | **A** |
| `fix/notification-store` | `127244b5f79e` | 5 | 2 | 17 | **A** |
| `feature/complete-alpha-implementation` | `127244b5f79e` | 3 | 1 | 15 | **A** |
| `arena/351e052d-...` (PR #2) | `359ccdbeb90f` | 2 | 8 | 50 | **B** |
| **`arena/53b00d6c-...` (PR #4, selected)** | `359ccdbeb90f` | **35** | **16** | **66** | **B** |
| `verify/local-alpha-ci` (PR #1, merged) | `61eee0b07b28` | 392 | — | — | **C** |

`git merge-base origin/main HEAD` returns **nothing**: family B shares no ancestor with `main`.
Consequences the next session must not learn the hard way:

- **You cannot rebase family B onto family A, or vice versa.** There is no common base to rebase
  against. GitHub still reports PR #2 and PR #4 as `MERGEABLE` because its merge machinery accepts
  unrelated histories (`refs/pull/2/merge` and `refs/pull/4/merge` both exist), but a local
  `git merge` of those branches needs `--allow-unrelated-histories` and will conflict broadly.
- **PR #5 (family A, schema 2) and PR #4 (family B, schema 16) are two different implementations of
  the same product**, not two increments of one. Of the 34 files PR #5 changes against `main`,
  **none** is a file this track also changes relative to its own root — the trees are structured
  differently.
- The author's local Mac work (`f465b52`, schema 2, notification/scheduler failures) sits in
  **family A**. The most advanced implementation is **family B**. They are not interchangeable.

**No merge, rebase or cross-track transplant was attempted in this session.** Doing it correctly is
a product decision, not a mechanical one — see §9 P0.

---

## 3. Pull requests (live at the time of writing)

| PR | State | Head | Base | Note |
|---|---|---|---|---|
| [#5](https://github.com/rajaryan1111/ai-career-agent/pull/5) | OPEN | `fix/tracker-integrity-c1-c7` (`3869c15`) | `main` | family A, schema 2 |
| [#4](https://github.com/rajaryan1111/ai-career-agent/pull/4) | OPEN | `arena/53b00d6c-ai-career-agent` (`e624b4a` → now this doc's commit) | `arena/351e052d-ai-career-agent` | **this track**, stacked |
| [#3](https://github.com/rajaryan1111/ai-career-agent/pull/3) | OPEN | `arena/941d963f-ai-career-agent` (`fbe19a9`) | `main` | family A, schema 8 |
| [#2](https://github.com/rajaryan1111/ai-career-agent/pull/2) | OPEN | `arena/351e052d-ai-career-agent` (`9b34c4a`) | `main` | family B base of PR #4 |
| [#1](https://github.com/rajaryan1111/ai-career-agent/pull/1) | MERGED | `verify/local-alpha-ci` | `main` | family C |

**Nothing was merged or closed.** PR #2's head advanced to `9b34c4a`
(`fix(import): make JSON imports atomic`) since this branch was cut; `359ccdb` is still an ancestor
of it, so PR #4 remains cleanly stacked and GitHub still reports it `MERGEABLE`.

### Commits pushed from this branch (most recent last)

| SHA | What |
|---|---|
| [`75af6b6`](https://github.com/rajaryan1111/ai-career-agent/commit/75af6b6) | Audit of the build-a-document path: 2 defects fixed, 4 blind spots pinned |
| [`269c250`](https://github.com/rajaryan1111/ai-career-agent/commit/269c250) | **Schema 16** — the listing each tailored document was written for |
| [`761fdb6`](https://github.com/rajaryan1111/ai-career-agent/commit/761fdb6) | README / `task.md` / research note for schema 16 |
| [`e624b4a`](https://github.com/rajaryan1111/ai-career-agent/commit/e624b4a) | Read-only doctor reads a schema-15 artifact row; migration helper renamed |
| *the HEAD commit* | This handoff and `docs/COMPLETION_LEDGER.md` — documentation only, no code change |

---

## 4. What happened to local work in this session

The sandbox was restored between sessions with **HEAD rewound to `359ccdb`** while the working tree
still held the schema-16 files, so Git reported 20 modified + 47 untracked files. Handling:

1. A backup was taken **before any Git operation**, to `/home/user/handoff-backup-2026-10-21/`:
   `git-status.txt`, `unstaged.diff` (694 KB, 11 323 lines), `staged.diff` (empty), `local-log.txt`,
   `remote-refs.txt`, and `worktree-20261021-002829.tar.gz` (230 files, verified readable with
   `tar -tzf`). Excluded: `.git`, `*.sqlite3`, `.env`, caches. No secrets or databases were present
   among the untracked files (checked).
2. `git fetch origin arena/53b00d6c-ai-career-agent` confirmed the remote still held every commit
   (`e624b4a`), i.e. **nothing was lost** — only the local object store had been rewound.
3. `git reset e624b4a…` (**mixed**, not `--hard`) moved HEAD and the index to the pushed commit
   without touching a single file on disk. `git status` then reported a clean tree, proving the
   working tree was byte-identical to `e624b4a`.

No `git reset --hard`, no `git clean`, no force-push, no branch deletion was used at any point.

---

## 5. The six canonical documents

All present on this branch and treated as the product contract:

| Document | Lines | Status against the code on this branch |
|---|---|---|
| `prd.md` | 318 | consistent; the product promises (local-only, nothing sent, truthful provenance) hold |
| `architecture.md` | 308 | consistent with `career_agent/` module layout |
| `design.md` | 242 | consistent |
| `rules.md` | 252 | consistent — the safety rules are the ones the code actually enforces |
| `phases.md` | 570 | consistent; later phases remain unstarted rather than mis-marked |
| `memory.md` | 4 214 | the engineering journal; appended to, never rewritten |

`task.md` (359 lines) is this track's **ledger of record**: 45 `[x]`, 39 `[ ]`.
**No contradiction was found between the six documents and the code in the areas inspected this
session** (dispatch gates, artifact lineage, schema version, acceptance claims). Areas not
inspected are listed in §7 as unverified rather than silently blessed.

`docs/COMPLETION_LEDGER.md` **did not exist on any branch** before this session (there was no
`docs/` directory anywhere in the repository). The file created alongside this one is explicitly
*derived* from `task.md` and from measurements taken today; `task.md` stays the ledger of record.

---

## 6. What this branch actually implements (verified)

Schema **16** (`career_agent/store.py`, `_SCHEMA_VERSION = 16`), 22 tables, 16 ordered migration
steps in one `_MIGRATIONS` table, forward-only and additive.

Working, with tests: candidate profile + fact provenance and confirmation; work history and
education; job listings with cross-source identity; eligibility with explicit `UNKNOWN`; role
strategies (append-only versions); **tailored documents with full lineage** (facts, citations,
strategy version and — since `269c250` — the listing they were written for); export with a
provenance header, owner-only file mode and refusal to overwrite; backup/restore with validation and
rollback; the write-ahead attempt ledger with `UNKNOWN`-blocks-retry semantics; the standing
authorisation (per-pair permission, daily limit from durable rows, quiet hours, stop switch);
do-not-contact suppression; the scheduler/worker (`career_agent/tasks.py`, `career_agent/worker.py`)
with leases and run records; a Tk desktop application (16 tabs) and a CLI.

**Not implemented and not claimed:** live discovery, application submission, outbound email
delivery, inbox reading, laptop-off operation.

---

## 7. Tests run in this session, with exact commands

| Command | Result |
|---|---|
| `python -m unittest discover -s tests -q` | **exit 0 — `Ran 2734 tests … OK (skipped=13)`**, 146 s |
| `python scripts/desktop_acceptance.py --stand-in-tk` | **158 checks passed, 0 failed**; exit verdict `RESULT: BLOCKED` |
| Live probe of dispatch gates (ad-hoc, not committed) | all three invariants held — see below |

The 13 skips, enumerated programmatically: **12 × “the optional pypdf package is not installed”**,
**1 × “ai-career-agent is not installed in this interpreter (source checkout)”**. Nothing else is
skipped.

**Dispatch probe (local, no network, no provider).** With `SOURCE_QUALITY_GATE_PASSED = False` and
`enabled_discovery_sources() == ()`:

1. `policy=None` → `disabled`, `performed=False`, attempt row settles **`refused`** (a refusal does
   not poison the job identity);
2. recipient on the do-not-contact list, written with different case and a trailing space →
   `disabled`, `performed=False`, **no attempt row written**, message names the do-not-contact list;
3. `done_today=None` (nobody counted today's actions) → `disabled`, `performed=False`, even with
   `source_gate_allows=True`.

**Checks that could not run, and are therefore not claimed:**

- **Static typing: not run.** `mypy` is not installed in this interpreter and no network install was
  made (the brief forbids casual dependency changes, and no verified blocker required it).
- **`pytest`: not installed.** The suite is `unittest`; do not assume the two are interchangeable.
- **GUI acceptance: BLOCKED.** This Python has no `tkinter`
  (`ModuleNotFoundError: No module named 'tkinter'`) and there is no display. The stand-in-widget
  run is *not* GUI acceptance and the script says so itself in its exit verdict.
- **CI: none for this head.** `gh api …/commits/<head>/check-runs` → `total_count = 0`;
  `.github/workflows/tests.yml` triggers on `push`/`pull_request` to **`main` only**, so no workflow
  has ever run on this branch. PR #2's and PR #5's green runs are **not** evidence for this head.

---

## 8. Issues fixed, with evidence

Fixed earlier in this session's branch (already pushed, all with regression tests):

| Issue | Commit | Regression tests |
|---|---|---|
| A cover letter reported no gaps, so the preview claimed “nothing the strategy asks for is missing” while the strategy asked for Docker | `75af6b6` | `test_a_cover_letter_reports_the_requirements_it_could_not_claim`, `test_a_cover_letter_preview_names_what_it_could_not_claim` |
| A listing edited between preview and confirmation stored the document anyway | `75af6b6` | `test_a_listing_edited_while_the_document_was_read_is_refused`, acceptance **M13** |
| A listing edited **after** storage left the document reading “Current” and exportable | `269c250` | `ListingLineageTests` (16 tests), acceptance **M14–M16** |
| A column migration step on a file whose recorded version ran ahead of its tables raised, leaving an unopenable database (latent since schema 4) | `269c250` | `test_the_listing_step_does_not_break_a_file_whose_version_runs_ahead_of_its_tables` |
| The read-only doctor would raise `IndexError` on a schema-15 artifact row | `e624b4a` | `test_the_doctor_reads_a_version_15_document_without_opening_the_file` |

**In this 2026-10-21 window specifically, no new code defect was found or fixed.** The dispatch,
suppression and attempt-ledger invariants were probed and held; the notification/scheduler defects
named in the brief belong to family A and do not exist on this branch (see §9 P1). Saying so is the
honest outcome; no change was invented to fill the slot.

---

## 9. Remaining work, in priority order

### P0 — Decide what to do about the three histories
Nothing else on this list is safe to plan until this is settled. Options, in the order a reviewer
would probably weigh them: (a) adopt family B (schema 16, 2 734 tests) as the product and retire
family A's branches after porting anything unique from PR #5 and `fix/notification-store`; (b) keep
family A and port family B's features forward (far more work); (c) keep both temporarily and accept
that `main` represents neither. Whatever is chosen, record it in `task.md` and in the PR
descriptions before any merge. **Do not merge PR #4 into `main` as a shortcut** — it would land an
unrelated history over the one `main` has.

### P1 — Notification/store work named in the brief (family A only)
`CareerStore.list_notifications`, `clear_notifications`, `clear_notifications_by_ids` exist on
`fix/notification-store` at `career_agent/store.py:707/749/806`. On **this** branch
`career_agent/notifications.py` is a decision-only module (no persistence, no status enum updates,
no `tests/test_scheduler.py`), so those defects are **not applicable here** and
`tests/test_notifications.py` passes as part of the 2 734. If the P0 decision keeps family A, do
that work there; if it keeps family B, port only the behaviour that is genuinely missing.

### P2 — Typing and scheduler verification on this branch
Install `mypy` deliberately (it is absent), run it on `career_agent/`, and fix real type defects —
not by widening to `Any`. Scheduler/worker behaviour is exercised by `tests/test_tasks.py`,
`tests/test_worker.py`, `tests/test_store_tasks.py`, `tests/test_cli_worker.py`, all currently
passing; a focused review of lease recovery and duplicate prevention under concurrency is still
worth doing.

### P3 — Product work already scoped in `task.md`
39 unchecked items remain. The next in this area, now that listing lineage is closed: multi-résumé
selection (needs a data model — one `candidate_profile` today) and richer export formats, both
recorded as *enhancements, not requirements*. Human GUI acceptance remains outstanding and blocked
on a display.

---

## 10. Security boundaries — all still closed

- `career_agent/sources.py`: `SOURCE_QUALITY_GATE_PASSED = False`; `enabled_discovery_sources()`
  returns `()`. Verified live today.
- No discovery, no submission, no outbound email, no inbox reading. The only integration is the
  local stand-in, which opens no connection.
- No CAPTCHA or OTP circumvention anywhere; no fabricated candidate facts — a missing fact is a
  reported gap, never invented text.
- Events carry identifiers, counts and sizes only: no candidate text, no employer names, no file
  paths.
- Exported files are written owner-only (`0o600`) through `create_private_file`, and an existing
  file is never overwritten.
- Nothing in this session enabled, weakened or bypassed any of the above.

---

## 11. The exact next task recommended for the next session

**Settle P0, then — if family B is kept — close the “documents cannot be checked” backlog for real
users upgrading from schema 15.**

Concretely, the first codeable task:

> A person upgrading a long-lived database lands on a Tailored documents list where several rows say
> *“Cannot be checked”*. There is no one-press way to deal with them. Add a reviewed, confirmed
> **“rebuild the documents that cannot be checked”** action: it must preview exactly which documents
> it would rebuild and for which listings, write nothing until confirmed, append new documents
> (never touch the originals), and refuse anything whose listing or strategy is gone.

Files: `career_agent/desktop.py` (artifacts tab, `_build_artifacts` ≈ line 2390 and the six
`_*_artifact` handlers), `career_agent/desktop_logic.py` (text helpers near
`artifact_state_text`), `career_agent/artifacts.py` (`rebuild_artifact`, `lineage_status`).

Tests to write/run:

```bash
python -m unittest tests.test_artifacts tests.test_artifact_build -q
python -m unittest tests.test_desktop_handlers.TailoredDocumentsTabTests -v
python scripts/desktop_acceptance.py --stand-in-tk          # expect 158+ checks, verdict BLOCKED
python -m unittest discover -s tests -q                     # expect 2734+ tests, 13 skips
```

---

## 12. Instructions for the next agent

1. **Inspect Git before editing.** Run `git status`, `git log --oneline -5`,
   `git rev-parse HEAD`, `git ls-remote origin`. If local HEAD is behind the remote head of
   `arena/53b00d6c-ai-career-agent`, the sandbox was restored: fetch and use a **mixed**
   `git reset <remote-sha>` (never `--hard`) so files are preserved, then confirm a clean tree.
2. **Never assume this document is newer than the code.** It records 2026-10-21; the branch may have
   moved. The ledger of record is `task.md`, and the tests are the only evidence that matters.
3. Re-run the baseline before claiming anything is “pre-existing”:
   `python -m unittest discover -s tests -q` (expect 2 734 / 13 skipped at `e624b4a`).
4. Keep `main` untouched, keep PRs #2, #3, #4 and #5 open, never force-push, and keep every external
   gate closed.
5. Follow the repository's conventions: a research note per increment in `research/`, a `memory.md`
   journal entry, schema-version literals re-pinned deliberately in tests, event names registered in
   `event_log.EVENTS`, and no candidate data in logs or events.
