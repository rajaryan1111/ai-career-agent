# Conditions you can actually set

**Date:** 2026-10-18
**Increment:** role terms, places, attachment rules, the follow-up limit and the quiet window are
editable on the Permissions & limits tab.

## The gap

The standing authorisation has carried all five since they were added. They are validated by
`GlobalPolicy`, folded once at the value's own edge, part of `content_key()`, round-tripped through
the store, enforced by `evaluate_policy`, reported together when several fail, and carried untouched
through every change the window makes (`dataclasses.replace`, after this tab once lost them by
rebuilding the value field by field). Every one of those properties is tested. None of them could be
*set* without opening a Python prompt, which means that for a person using the application they did
not exist.

## What the tab does now

One panel under the permissions it narrows, one button, one confirmation.

- **Reading what was typed is its own module.** `parse_condition_terms`, `parse_attachment_kinds`,
  `parse_follow_up_limit` and `parse_quiet_hours` live in `desktop_logic.py` with no Tk and no
  database, and they refuse rather than guess: `my resume.pdf` is not a file ending, `a few` is not a
  number of follow-ups, the same term twice is refused instead of quietly folded, and half a quiet
  window is refused because "quiet from 22" with no end is either one hour or ten.
- **Terms are not folded here.** The policy value folds them once at its own edge; a window that
  folded them too would be a second place deciding what two terms are the same.
- **The confirmation says what changes, in both directions.** `roles must mention: data → nothing` is
  as important as the other direction - clearing a condition is a change a person should see
  described, not an empty box that silently stops protecting them.
- **An unchanged save writes nothing.** The boxes are rewritten from the stored value after every
  refresh, so saving again reports "nothing to change" rather than writing a version that records
  nothing.
- **`dataclasses.replace`, not a rebuilt value.** The same discipline the other handlers on this tab
  were corrected to use: a field added to `GlobalPolicy` and forgotten here would be a silent
  loosening of somebody's own rule.

## What this does not change

- A condition **narrows**: it can refuse something otherwise allowed and can never permit anything.
  Nothing on this tab can open a source's gate, and every source is still closed.
- Quiet hours are read by the notification preference on the *What's happening* tab, which still
  delivers nothing anywhere.
- No display-backed run: the stand-in acceptance run is 134 checks, 0 failed, and is not a window.

## Evidence

- `tests/test_desktop_handlers.py::PolicyConditionsTabTests` - 12 tests: the empty state and what it
  means, the declined question writing nothing, every condition stored in one version, the read-back
  and the no-op save, the refusals (half a quiet window, equal hours, a non-ending, a non-number, a
  repeated term), the permissions left alone, and the clearing described.
- `tests/test_desktop_logic.py::PolicyConditionTextTests` - 8 tests over the parsing and the wording.
- `scripts/desktop_acceptance.py` workflow **N7-N9**: the declined question, the refusal before the
  question, and the stored-then-read-back round trip with the no-op save.
