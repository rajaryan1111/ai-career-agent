# The do-not-contact control on the HR contacts tab

Date: 2026-10-16 · Task: `planning/arena-task-phase-0-contact-do-not-contact-control-2026-10-16.md` ·
Branch: `arena/351e052d-ai-career-agent` · Scope: local, offline, no schema change, no external action.

## The question this note answers

The stored contact record could already *represent* a do-not-contact mark - a column, a date it was made, a
reason, one method that writes all three - and the stored list showed it. Nothing in the window could *set*
it. So the mark was durable and displayed but not reachable, which is the gap the persistence note recorded
as "the mark has no control that sets it". This increment closes that gap and nothing else: no schema
version moved, no new table, no parser change, no network call, no contact value in a log.

The work was specified *before* it was written, in the committed task file. Reading it first paid off in the
one place that mattered: the task allowed a reason to be recorded with the mark, and the record already had
`suppressed_note`. A new column would have moved the schema for no gain, so none was added.

## What exists now

**The control is the selection.** Two buttons sit under the stored list on the **HR contacts** tab, beside a
reason box and one line of state. Building them is not the interesting part; what they obey is:

- Both are built **disabled** and are driven by one method (`_sync_contact_actions`) that re-reads
  `list_contacts()` and enables **exactly the action that would change the selected contact**: mark when the
  row is not marked, clear when it is, and the reason box only while marking. A control that could only
  refuse is not offered, so there is no path where pressing a button produces "nothing to change".
- Selecting a row is what points them at a contact. The row carries its stored id as its tree id
  (`iid=str(record.contact_id)`), so the panel asks the widget which row is selected and then asks the store
  for that record - the screen does not carry a parallel copy of the list.
- The state line reads where the row sits and what it carries: *Selected contact 1 of 2 in the stored list:
  Marked do not contact, and a reason is recorded with it* (or *…and no reason is recorded with it*, or *Not
  marked do not contact*), and *No stored contact is selected…* with nothing selected.

**What a confirmation is allowed to say.** Both confirmations describe the row by its **position in the list
and the file it came from** - "row 1 of 2 in the stored list", "from synthetic-contacts.csv" - and never by
the address, the name, the company or the reason. That is deliberate: dialog text is the thing a screenshot,
a screen share or a bug report keeps, and the mark is a judgement about a person who is not in the room. The
chosen file's own name *is* shown to the person (they picked it; hiding it would be the surprising choice),
and the test asserts it is shown there and absent from the log.

**Zero writes is a property of the code, not of the message.** A declined confirmation, a stale selection
(the id of a row a restore removed), and an injected `sqlite3.OperationalError` all leave the stored mark
exactly as it was, with `suppressed_at` unmoved, and each is asserted against the database's **own change
counter** (`connection.total_changes`) rather than against what the window said. The failure path calls
`store._record`'s owning method's caller - `set_contact_suppression` - so the write is either complete inside
the store or never began; the panel reports `Local database could not be read` and keeps the reason box
filled, because throwing away a person's typed sentence on a transient failure is a data loss of its own.

**The reason lives on the record and nowhere else.** It is typed into the box, passed to
`set_contact_suppression(email_key, note=…)`, stored on the row, and cleared from the box on success. It
never reaches a dialog, the status line, a message, or the event log. The event is one line,
`contacts.suppressed`, and its detail is a flag: `suppressed=true` or `suppressed=false`. Clearing nulls the
flag, the date and the reason together, so an unmarked contact is not left explaining why it was once
marked - and can be marked again later with a new reason.

**Marking is still not an import's business.** No code was added to `import_contacts`, which is why the mark
continues to survive a re-import, a file that contradicts what is stored, a restart, and a backup that is
restored. Those four are now asserted through the *window* as well as through the store, which is the
difference between "the store keeps the flag" and "the screen shows the flag after the file is read again".

## Evidence

| What | Command | Result |
| --- | --- | --- |
| The control, its states and its refusals | `python3 -m unittest tests.test_desktop_handlers` | `Ran 308 tests … OK` |
| Store behaviour unchanged, plus the one new privacy test | `python3 -m unittest tests.test_contacts_store tests.test_contacts tests.test_event_log` | `Ran 119 tests … OK` |
| The whole suite | `python3 -m unittest discover -s tests` | `Ran 1845 tests … OK (skipped=13)` |
| The acceptance harness, as far as this machine can go | `python3 scripts/desktop_acceptance.py --stand-in-tk` | `91 checks passed, 0 failed`, `RESULT: BLOCKED` (no display) |
| Syntax of every touched file | `python3 -m compileall -q career_agent scripts tests` | clean |

`ContactMarkControlTests` (12 tests) covers: the enablement of each control in each state; marking through
the handler with one change counted, the note stored, the summary, state line, row cell and selection all
read back; a declined mark writing nothing; clearing through the handler with the date and reason gone; a
declined clear keeping both; no selection; a stale id refreshing the list (four inserts) and writing
nothing; an already-marked row offering "Nothing to change" without a confirmation; an injected
`sqlite3.OperationalError` showing no success and keeping the note; survival across a re-import (`seen_count
2`) and a contradicting later file (2 disagreements, stored name kept); a restart and a backup restore read
back through the panel; and the privacy assertions - no fixture value or note in any dialog or the status
line, and the log holding `event=contacts.suppressed` with a flag and no file name.

The acceptance workflow grew from five checks to nine (**L6-L9**): the controls are off until a row is
selected and are reachable by the same keyboard walk workflow K measures; a declined removal leaves the mark
and its date exactly as they were; a confirmed removal clears them and says so; and a mark made from the
window with a reason typed into the real entry stores that reason, shows it in no dialog, no status line and
no log line, and counts as one row changed.

## Decisions, and the ones that were rejected

- **No schema change.** The record already had `suppressed`, `suppressed_at`, `suppressed_note`. Version 7
  stands; no migration, no rollout question, nothing to roll back.
- **One reason, cleared with the mark.** The task permitted a reason; a reason *history* is a different
  feature with its own retention question. Rejected here and named as a gap.
- **The reason box is disabled while clearing.** Typing a reason into a control that will ignore it is a
  small lie in the interface.
- **The button is disabled rather than offering an action that will refuse.** "Nothing to change" exists as
  a guard in the handler for a programmatic call, but the window never offers it.
- **Confirmation text names the row position and the file, not the contact.** Recorded above; it is the
  reason this note calls the boundary explicit rather than incidental.
- **The event carries a flag only.** Counts are already the import's shape; a mark has nothing to count.
  Prose would be an unbounded channel into a log file.

## Named gaps (not claimed, not implied)

- **No human has used this control.** Every check above is automated or stand-in. The window has not been
  run on a display by a person, the wording has not been read aloud by a screen reader, and the keyboard
  feel of the two buttons is unmeasured. The manual checklist has **no numbered steps for the HR contacts
  tab**, so nothing there is even marked BLOCKED - the tab needs its own steps written before it can be
  ticked.
- **`set_contact_suppression` is still the only writer**, and the mark is still not exportable: the JSON
  export does not carry the contact tables, so a person cannot yet take their do-not-contact list with them
  or move it to another install.
- **No per-contact deletion.** Clearing the mark is not erasing the record; a contact whose data must go
  cannot be removed from the window at all today.
- **Recorded disagreements still cannot be read in the window**, let alone resolved. A key's history of
  contradictions is stored, counted, and invisible.
- **No history of marks.** The record holds the current mark, its date and its one reason; a person cannot
  see that a contact was marked, unmarked and marked again.
- **Nothing acts on the mark yet**, because nothing contacts anybody: no matching, no drafts, no sending, no
  reply or bounce handling. The gate (`SOURCE_QUALITY_GATE_PASSED = False`) and the empty
  `enabled_discovery_sources()` are unchanged by this increment, and no contact value is transferred off the
  machine - there is no code path here that could.
