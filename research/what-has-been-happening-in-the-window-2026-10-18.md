# What has been happening, in the window

**Date:** 2026-10-18
**Increment:** a twelfth tab, **What's happening**: the operations report, the attempts nobody settled,
and the notification preference — the three things that existed only behind `--report`, `--weekly` and
`--notifications` until now.

## Why this, and why now

Everything the reporting and notification modules know was already computed, tested and persisted. None of
it was reachable from the application a person actually opens. Three of those things are not reports at
all, which is what made the gap worth closing rather than documenting:

1. **An attempt whose outcome was never established blocks the next attempt** on the same job and action.
   Only a person can clear it, and the only way to clear it was a Python call.
2. **A notification preference the person cannot see is a claim, not a setting.** It was stored, read back
   by the scheduler, and invisible.
3. **A report that only prints to a terminal cannot be acted on.** The list that matters — unsettled work —
   is the one that needs a control beside it.

## What the tab does, and the three rules it keeps

- **The report is the reporting module's own text.** `report.headline()` is shown verbatim, and
  `report.describe()[1:]` is the body. The window writes no sentence of its own about the records.
- **Settling an attempt needs evidence and one explicit yes.** Below four characters is refused before any
  dialog opens; the confirmation quotes the note back and says that recording the outcome lifts the block
  on further attempts. The three outcomes offered are the three the store will accept — *it did happen*,
  *it did not happen*, *it was refused*. "Still unknown" is deliberately not offered: it settles nothing,
  clears nothing, and would only make the list look handled.
- **Nothing on the tab reaches anything.** The confirmation for the notification preference says so in the
  words a person would want: no email, no push, no system notification, nothing while the application is
  closed.

## The bug this increment found, in the window's own first draft

The first version of `report_summary_text` composed its own sentence — "1 thing(s) from the last day need
you." — and then appended the report's headline, which is "1 thing from the last day need you." The
development acceptance run printed both, one after the other, and that is how it was caught:

> the summary says '1 thing(s) from the last day need you. 1 thing from the last day need you.'

Two counts of the same records, in two different voices, is exactly the drift the reporting module exists
to prevent. The function now returns the headline as written, and adds only where to act on it. A test
pins the property rather than the sentence: `busy.count("need you") == 1`.

## Honest boundaries

- **No display-backed run.** Workflow **O** (six checks) runs green under the stand-in widget module, and
  the stand-in is not a window. Seven new manual steps (137-143) are recorded **BLOCKED**, which takes the
  checklist to 143 steps: 22 PASS, 121 BLOCKED, 0 FAIL.
- **Nothing delivers a notification.** The preference is stored and read back. No code path sends one, and
  the window says so rather than implying a channel exists.
- **Quiet hours are shown, not edited here.** The tab reads `policy.quiet_hours` so the preference can be
  described honestly against it; editing them belongs with the rest of the standing authorisation.
- **The tab creates no attempt.** It can only settle one that something else wrote, and in this build the
  only writer of attempts is `guarded_dispatch`, which still has no in-app caller.

## Evidence

- `tests/test_desktop_handlers.py::WhatsHappeningTabTests` — 12 tests: the quiet database, the unsettled
  row and its wording, the refusal with no evidence, the declined confirmation leaving the change counter
  untouched, the settlement storing the evidence and clearing the list, the preference round-trip, the
  stated boundaries, an unreadable record and an unavailable database.
- `tests/test_desktop_logic.py::WhatsHappeningTextTests` — 10 tests over the Tk-free text, including the
  duplicated-count regression and the strict reading of an hour.
- `scripts/desktop_acceptance.py` workflow **O** — six checks; `scripts/desktop_smoke_test.py` now expects
  twelve tabs and the attempt list's columns; CI's workflow-letter list runs `A`-`O`.
