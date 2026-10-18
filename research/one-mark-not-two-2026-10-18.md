# One mark, not two: the do-not-contact list in the window

**Date:** 2026-10-18
**Increment:** the HR contacts tab's do-not-contact mark now writes the list the sending gate reads,
and that list is visible in the window for the first time.

## The defect

Two records called the same thing existed side by side:

| Record | Written by | Read by |
| --- | --- | --- |
| `hr_contacts.suppressed` (a column, with a day and a note) | the HR contacts tab | the window, and nothing else |
| `contact_suppression` (schema 14: address, reason, day, note) | `store.suppress_contact`, from Python | `guarded_dispatch`, before any outbound action |

A person who pressed **Mark do not contact** saw the row change, the summary count it, and a dialog
confirm it. The one check that could ever stop a message knew nothing about it. The reverse was just as
bad: an address on the enforced list was invisible in the application, so a person had no way to see
what their own build would refuse.

Nothing in this build sends anything, so no message went anywhere it should not have. That is luck
about the schedule, not a property of the design: the gap would have closed itself the day sending
arrived, in the worst possible way.

## What the window does now

One decision, one confirmation, both records:

- **Marking** reads a reason from a chooser carrying the suppression module's own five labels and no
  sixth, writes the contact column, and records the address with `suppress_contact`. The confirmation
  states that the address goes on the list checked before anything may be sent, that recording an
  address twice keeps the first reason, and - for `asked_to_stop` - that this reason is the permanent
  one.
- **Removing** requires a note of at least four characters whenever the address is on the enforced
  list, and the refusal happens **before** the question is asked. The window never asks something it is
  about to refuse.
- **The panel** lists every suppressed address with its reason, the day, and whether a note exists -
  never the note's text, which stays as private as it was: not in a column, a dialog, an event or the
  log.
- **A legacy mark is reported, not hidden.** A contact marked before this change is counted in the line
  above the list as "not on the list", and the state line under the controls says so for the selected
  row. Marking it again puts it on.

## Decisions worth writing down

- **The note is required exactly when the store requires it.** A mark that exists only as a column -
  the legacy case - can still be cleared without one, because that is the store's rule for a column,
  and inventing a stricter rule in the window would make the two disagree again in a new way.
- **A removal does not offer a reason chooser.** A removal is recorded against whatever reason is
  stored; offering a chooser would imply the earlier reason could be rewritten, which is the one thing
  "the first reason wins" exists to prevent.
- **A reason this build has no member for is drawn, not refused.** `suppression_rows` matches on the
  stored value rather than the enum object, so a database written by a later build still lists the
  address rather than raising - an address somebody must not be written to is the last thing a list
  should hide behind an exception.
- **Two rows changed, deliberately.** The acceptance check that read "marking changed 1 row" now reads
  2 and asserts both halves; the old number was the defect, written down.

## Evidence

- `tests/test_desktop_handlers.py::DoNotContactListPanelTests` - 12 tests: the panel, the note that
  never leaves the record, the offered reasons matching the module's, the first reason surviving a
  second mark, the refusal before the question, the removal clearing both records, the declined
  removal changing nothing, the legacy mark reported as unlisted, an unreadable row and an unavailable
  database.
- `tests/test_desktop_logic.py::DoNotContactTextTests` - 6 tests over the Tk-free text.
- `tests/test_desktop_handlers.py::ContactMarkControlTests` - updated where it described the old
  behaviour: the note box stays usable while a mark is on (a removal needs it), and a mark writes two
  rows.
- `scripts/desktop_acceptance.py` workflow **L9** (two rows, the panel, the note that is not drawn) and
  new **L9b** (the refusal with no note, the removal that clears both, and the mark put back so the
  later steps still check what they were written to check).

## What is still not true

- Nothing sends anything, so the list is still a guard in front of a locked door.
- The list can only be added to **through a stored contact**. An address that is not in the contacts
  list cannot be suppressed from the window, and there is still no CLI flag for it.
- No display-backed run: the stand-in acceptance run is 131 checks, 0 failed, and is not a window.
