# Acceptance evidence you can actually record, and sources that say why they are closed

**Date:** 2026-10-18
**Increment:** schema 15 (`route_evidence`), the `Sources & evidence` tab, acceptance workflow **P**.

## The gap

Two of the project's clearest statements lived where nobody could see them.

`career_agent/acceptance_evidence.py` has said since P8 item 6 exactly what each of the six application
routes would have to prove before anybody could sensibly open it: nine written requirements per route,
from a permission basis to a tested withdrawal path. But `held_evidence(route_id)` returned `()` for
every route **by construction** - there was no table, no API, no way to write down that one of the nine
had been met. The requirements were a document pretending to be a workflow.

`career_agent/sources.py` has an equally clear answer to "why are there no jobs in here?" - six reviewed
sources, a permission state each, and a closed quality gate that holds even the approved one shut. That
answer was in `--sources` and in nothing a person using the window would ever open.

## What this increment adds

**Schema 15, `route_evidence(route_id, kind, recorded_at, reference, note)`, primary key
`(route_id, kind)`.** One row per requirement per route, because "we reviewed the terms" and "we have
their rate limit in writing" are different claims and a single approved flag would let either stand in
for the other.

Store API, all of it refusing before it writes:

| Call | Refuses when |
| --- | --- |
| `record_route_evidence(route, kind, *, reference, note, now=None)` | the route is unknown; the kind is unknown; the route does not list that kind; the reference is under 4 characters; the note is under 8; **that requirement is already recorded** |
| `withdraw_route_evidence(route, kind, *, note)` | the reason is under 4 characters |
| `route_evidence_for`, `list_route_evidence`, `held_evidence_kinds`, `evidence_held_by_route` | read-only; a stored kind this build cannot read raises from `list_route_evidence` and **counts for nothing** in `held_evidence_kinds` |

Two refusals are the interesting ones. **Already-recorded is never overwritten**: withdraw it, with a
reason, and record it again, so the history shows somebody changed their mind rather than that the
record always said this. And a **kind this build does not know never counts as held** - fail closed, or
a row somebody inserted by hand could make a route look ready.

`acceptance_evidence.outstanding`, `route_is_ready`, `describe_route` and `describe_all` learned an
optional `held=` / `held_by_route=` argument. Left out, they still answer about what *this project*
holds in its code, which is nothing - so every existing caller and every pinned test is unchanged.

**The window.** A new tab, `Sources & evidence`, with the source decisions and their gate reasons above,
and the routes, their requirements and what is recorded below. One `askyesno` before any write, the two
refusals shown before the question is asked, and the detail pane that says what a requirement means
whether or not it is held.

## What it deliberately does not do

Recording evidence **enables nothing**. `SOURCE_QUALITY_GATE_PASSED` is a constant in code;
`enabled_discovery_sources()` returns `()`; `discovery_gate` and `submission_gate` read neither the
database nor this table. A test and an acceptance step both record every requirement for a route and
then assert the gates have not moved - which is the whole point of writing the evidence down somewhere
auditable rather than in a commit message.

Nor does the tab fetch, send or submit. The source list is read from the reviewed decisions; the only
writes on the tab are the evidence row and its withdrawal.

## Evidence

- `python -m unittest tests.test_route_evidence` → **23 tests, OK**, covering recording, per-route
  isolation, the event-log redaction (route and kind only - no reference, no note), every refusal,
  withdrawal with and without a reason, re-recording after a withdrawal, readiness with and without the
  held set, the unreadable stored kind, and a schema-14 file migrated in place.
- `python -m unittest tests.test_desktop_handlers.SourcesAndEvidenceTabTests` → **15 tests, OK**,
  driving the tab's real handlers over a real store: closed gates listed, the reason shown, refusals
  before the question, a declined confirmation writing nothing, a confirmed record read back, the
  withdrawal path, and nine recorded requirements leaving every gate closed.
- `python -m unittest tests.test_desktop_logic` → **105 tests, OK** (9 new: the source and evidence
  prose, including that a complete route reads "every requirement recorded" and never "permitted").
- `python scripts/desktop_acceptance.py --stand-in-tk` → **140 checks, 0 failed** (workflow **P**,
  steps P1-P6). A stand-in is not a display: this run is reported as BLOCKED, as it always is.
- Full suite: `python -m unittest discover -s tests` → **Ran 2611 tests, OK (skipped=13)**.

Four files outside the feature changed with it, each a deliberate re-pin: the schema version in
`tests/test_store.py` (twice) and `tests/test_store_tasks.py`, the documented workflow letters in
`tests/test_desktop_acceptance.py` and `.github/workflows/tests.yml`, and the expected tabs, trees and
summary variables in `scripts/desktop_smoke_test.py`.
