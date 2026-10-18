# The invalidation surface: a window that refuses a stale document (2026-10-18)

## What this increment is

The last open half of P7's invalidation rule. The store already refused to hand out a document whose
sources had moved (`artifacts.require_current_artifact`, `StaleArtifactError`), but nothing a person
can see used that gate, so in practice a stale document was simply never mentioned. This increment
adds the **Tailored documents** tab, the rebuild path behind it, and the acceptance evidence for
both. Preparing a *new* document for a listing is still not something this window can do — the tab
lists, checks and rebuilds what the artifact layer stored — and that is named as the next step rather
than implied.

## What the tab shows and refuses

* **A row says what the document was built from.** Kind, listing, `strategy id vN`, when it was
  built, the file its facts were read out of (the citation added earlier the same day), and its
  state: `Current`, or `Rebuild before use — ` followed by every line the lineage report gives. A
  state cell never says only "stale": the whole point of the report is that the person is told which
  fact, which history or which strategy version moved.
* **"Check before use" asks the store's own gate.** It calls `require_current_artifact`, so the
  window cannot have a second opinion. A current document is reported as attachable by hand, with the
  standing truth that this application sends nothing. A stale one opens a dialog that lists the
  reasons and offers a rebuild; declining writes nothing and says so.
* **"Rebuild from current facts..." appends, never edits.** `artifacts.rebuild_artifact` captures a
  fresh basis, builds the same kind of document under the strategy's **newest** version and stores it
  as a new append-only row. The stale document stays exactly as it was — it is evidence of what was
  prepared, not a draft — and the status line names both documents and any requirement the person's
  facts do not state, because a gap is reported and never written into the document.
* **Screening answers are refused.** The builders only restate stored facts; answers a person wrote
  are not facts this application can regenerate, so a rebuild of that kind is refused with a message
  saying who writes them. Nothing is written on that path.
* **Nothing on the tab sends anything**, and the document's text never reaches the status line, the
  summary, the detail line or the event log — ids, kinds and counts only.

## The defect this increment found: a revision could delete a hard gate

`store.revise_role_strategy(strategy_id, **content)` built the new version **out of the arguments
alone**. Every caller so far passed the whole content, so the bug was invisible; the first caller that
wanted to change one field (the rebuild path, and any future editor) would have either crashed with a
`TypeError` or — worse, had it passed the two required fields — written a new version with
`excluded_employers`, `excluded_role_titles` and `required_skills` silently emptied. Those three are
*gates* in `matching.assess_for_strategy`: a version that lost them would quietly unblock employers
and titles the person had excluded, permanently, because versions are append-only.

A revision now **states what changes**: named fields replace, unnamed fields are carried forward, a
field can still be cleared by naming it with an empty value, and a field name the model does not have
is refused (`StrategyError`) instead of being dropped on the floor and reported as "nothing changed".
Five regression tests, including the rename-keeps-the-gates case. One existing artifact test had been
relying on the defect to produce a second version and was corrected to make a real change.

## Evidence

* `tests/test_artifacts.py::RebuildArtifactTests` — 8 tests: append-and-keep, newest strategy version,
  gaps reported not invented, cover letters rebuilt as cover letters, screening answers refused with
  zero writes, unknown identifier refused, the rebuild cites the documents the facts now come from,
  and a current document may be rebuilt without pretending it was stale.
* `tests/test_strategies.py` — 5 tests for the revision defect above (32 in the module).
* `tests/test_desktop_handlers.py::TailoredDocumentsTabTests` — 10 tests driving the **real window**
  against stub widgets and a real database: the list's cells, the refusal state naming the fact, the
  controls disabled until a row is selected, a current check that writes nothing and opens no dialog,
  a declined offer that writes nothing, an accepted offer that appends and keeps, the rebuild
  confirmation, screening answers refused, a document deleted elsewhere refused, and the privacy of
  the status line and the log. Two deliberate mutations (a state cell that always says "Current", and
  a gate that never raises) were each caught by two of these tests before the code was restored.
* `tests/test_desktop_logic.py::TailoredDocumentTextTests` — 7 tests for the sentences themselves,
  including that a document citing nothing says so rather than guessing "unknown".
* `scripts/desktop_acceptance.py` — **workflow M** (M1-M5), registered in `WORKFLOWS` and in the CI
  loop over workflow letters (the test that compares the two keeps them from drifting). Under the
  stand-in widget run on this machine the whole file reports `118 checks passed` and then
  `RESULT: BLOCKED — a stand-in Tk is not a desktop, so this run is not evidence`, which is exactly
  what that mode is for. **No display-backed run has executed workflow M yet**, because CI runs only
  on main-targeting heads; that is outstanding, not done.
* `scripts/desktop_smoke_test.py` — `artifacts_tree` with its six columns, `artifact_summary`, and the
  new tab in `EXPECTED_TABS`, so a platform leg fails if the tab or its summary stops being built.
* Manual checklist steps **124-129** added, all **BLOCKED**: no display, no Tkinter and no assistive
  technology here, and nothing about wording, fit, focus order or screen-reader output is established
  by any automated check. The checklist is now 129 steps: 22 PASS, 107 BLOCKED, 0 FAIL.
* Full local suite: **2215 tests OK (skipped=13)**. Gates unchanged: `SOURCE_QUALITY_GATE_PASSED` is
  `False`, `enabled_discovery_sources()` is `()`; no discovery, submission, email or inbox path is
  touched by any of this.

## Known limitation, named rather than implied

Running `tests/test_desktop_acceptance.py` and `tests/test_desktop_handlers.py` **together in one
process** fails, because the two modules install different stand-ins for the same widget module. This
predates this increment (verified by running the same pair at the previous commit) and does not affect
`unittest discover`, which is how the suite runs. It is a test-harness defect worth fixing on its own.
