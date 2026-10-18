# Remaining-work matrix, read off the repository

**Date:** 2026-10-18
**Read from:** `task.md` (the ledger), `career_agent/*.py` (the implementation and its real callers),
`tests/`, `scripts/desktop_acceptance.py`, `README.md`, `phases.md`, `rules.md`, `memory.md`.
**Rule applied throughout:** a row is *complete* only when something in the application calls the
code and a test or acceptance check asserts the behaviour. A module with no caller is **incomplete**,
not complete, however well it is tested.

## Ledger arithmetic, not an estimate

`task.md` holds **29 `[x]` and 39 `[ ]`** boxes. The unticked ones are not all "work not done": many
are phase goals whose *verification* depends on an external permission that does not exist (a mailbox,
a partner agreement, a display-backed CI leg). The matrix separates those two cases, because calling
them both "remaining" is how a project talks itself into claiming the wrong thing.

| # | Task (ledger line) | Implementation and its real callers | Missing integration / UI | Tests & acceptance | External dependency | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | P8-6 acceptance evidence per route | `acceptance_evidence.py`: 6 routes × 9 kinds, `held_evidence()` hard-coded `()`. Caller: `--acceptance-evidence` only | No storage: evidence cannot be *recorded*, only described. No window surface | `tests/test_acceptance_evidence.py` (16) | None for the mechanism; real evidence needs the outside world | **incomplete → doing now** |
| 2 | P8-7 mailbox authorisation, delivery/reply evidence | Nothing. `integrations.py` has `DisabledIntegration` and a `LocalMockIntegration` test double | Everything | — | **An authorised mailbox.** Cannot be built here | **blocked (external)** |
| 3 | `guarded_dispatch` has no in-app caller | `integrations.guarded_dispatch` implements the whole chain: suppression → duplicate/unknown block → write-ahead attempt → authorised dispatch → settle | No window control reaches it; the follow-up tab stops at a read-only draft | `tests/test_integrations.py` covers the function | None — the disabled integration is the honest terminal state | **incomplete → doing now** |
| 4 | P3 source status and blocked reasons in the UI | `sources.py`: 6 `SOURCE_DECISIONS`, `discovery_gate`, `submission_gate`, `SOURCE_QUALITY_GATE_PASSED = False`. Callers: `--sources`, the report, the worker | No tab shows a source or why it is closed | `tests/test_sources.py` | None | **incomplete → doing now** |
| 5 | P3 twice-daily discovery operational | `tasks.py`/`worker.py` schedule and refuse; every run is recorded as a refusal | n/a | `tests/test_worker.py`, `tests/test_tasks.py` | **A permitted source.** None exists | **blocked (external)** — and must not be claimed |
| 6 | P4 permitted autonomous applications | `policy.py` + `artifacts.py` + `require_current_artifact` | No submission adapter exists for any route | — | **A permitted submission route** with written terms | **blocked (external)** |
| 7 | P5 outreach sending | `guarded_dispatch` + suppression (schema 14) | see row 3 | `tests/test_suppression.py` (20) | **A mailbox** | **blocked (external)** |
| 8 | P6 dashboard / reports | `reporting.py`, `analytics.py`; window: *What's happening* tab (`52a8e95`) | — | handler + logic tests, acceptance O | None | **complete** |
| 9 | P6 notification preferences | `notifications.py` (schema 13); window: *What's happening* tab | Delivery itself: nothing sends | logic + handler tests, acceptance O6 | A delivery channel nobody has authorised | **complete as a preference; delivery blocked** |
| 10 | P6 pause/resume, stop-all, revocation | `policy.py`, `tasks.py`; window: scheduler tab + Permissions & limits | — | acceptance I3-I6, N4-N6 | None | **complete** |
| 11 | P7 strategies, artifacts, lineage | `strategies.py`, `artifacts.py`; window: *Tailored documents* tab | ~~Nothing in the window *creates* a first artifact~~ **done 2026-10-18** (`a51fa5d`, `f8995b3`): choose, preview in full, store exactly that, save a copy; duplicate, moved-strategy, moved-facts and stale-export all refused | acceptance M1-M12 | None | **done (a display-backed run is still owed, like every other tab)** |
| 12 | P8 conditions + quiet hours editable | `policy.py`; window: Permissions & limits (`56e5755`) | — | `PolicyConditionsTabTests`, acceptance N7-N9 | None | **complete** |
| 13 | Do-not-contact enforcement + UI | `suppression.py` (schema 14) + `guarded_dispatch`; window: HR contacts (`e173b40`) | Suppressing an address that is **not** a stored contact | `DoNotContactListPanelTests`, acceptance L9/L9b | None | **complete for stored contacts** |
| 14 | Cross-platform + human desktop acceptance | `scripts/desktop_acceptance.py` (134 checks), `scripts/desktop_smoke_test.py` | — | Stand-in run only | **A display and a human.** No `tkinter` in this sandbox | **blocked (environment)** |
| 15 | CI on this PR head | `.github/workflows/tests.yml` triggers on `main` only | — | — | A maintainer enabling branch triggers | **blocked (repository settings)** |

## What this sprint actually finished (added at the end of the sprint)

| Row | Was | Now | Commit |
| --- | --- | --- | --- |
| 1 — acceptance evidence | requirements only, `held_evidence()` hard `()` | schema 15 `route_evidence`, six routes recordable and withdrawable, on the new **Sources & evidence** tab | `e21c2ad` |
| 4 — source status in the UI | `--sources` only | the same tab shows every reviewed source with the gate's own reason | `e21c2ad` |
| 3 — the dispatch gap | `guarded_dispatch` had no in-app caller | **Follow-ups → Try to send this follow-up...**, plus one defect found and fixed in the guard | `31b4c93` |
| 13 — do-not-contact | stored contacts only | any address, with one confirmation and no invented contact row | `0e5771f` |

Rows 2, 5, 6, 7, 14 and 15 are unchanged and stay **blocked**: a mailbox, a permitted source, a
permitted submission route, a display with a human, and a CI trigger for this branch are all outside
this repository. Row 11 (nothing in the window builds a *first* tailored document) was the largest
remaining piece of work that is not blocked on anybody else; it was finished on 2026-10-18 - see
`research/the-first-tailored-document-2026-10-18.md`. What is left unblocked after it is smaller:
there is no way to choose *between* several imported résumés (the store holds one profile, with each
fact's source file recorded beside it), and the exported format is plain text only.

## What this sprint could actually finish

Rows **1, 3, 4** are the only ones whose blocker is "nobody has written it yet". Everything else is
either done or waiting on something that cannot be conjured: a mailbox, a partner agreement, a
display, or a CI trigger. Those three are what this sprint implements; the rest are reported as
blocked with the exact missing dependency, which is the honest answer rather than a smaller one.
