# Deleting one stored HR contact, and the disagreements recorded about it

Date: 2026-10-16 · Task: `planning/arena-task-phase-0-per-contact-deletion-2026-10-16.md` ·
Branch: `arena/351e052d-ai-career-agent` · Scope: local, offline, no schema change, no external action.

**Status:** Implemented, tested and driven through the real window; documented here after verification. The
human half is **not** done: steps 106-111 of the manual checklist are new, all six are **BLOCKED**, and no box
has been ticked. Schema stays **7** — no migration was needed. `SOURCE_QUALITY_GATE_PASSED` is still `False` and
`enabled_discovery_sources()` is still `()`; this increment reaches no network and sends nothing.

## The question this note answers

The HR contacts tab could import a list, mark a contact do-not-contact and read the disagreements an import had
recorded — but a record could never be removed. The only erasure this application offered was
`--forget-local-data`, which takes the whole database with it, so "delete this one person" had no path at all.
This increment adds it: one selected contact, deleted together with the disagreements recorded about it, in one
store transaction, after one confirmation that says what it costs — and with every refusal path deleting
nothing.

The work was specified *before* it was written, in the committed task file, and that first reading changed the
design in two ways worth recording: the deletion belongs in the **store** (the erasure module is file-level
whole-database erasure only, and a screen that issued two deletes itself could leave a contact's evidence
behind), and the confirmation has to identify the record by a **row reference** rather than by who it names —
which is the same rule the mark confirmations already follow.

This note records that increment: the inspected erasure contract, the tables and foreign keys involved, the
transaction and rollback semantics, the files and commits, the exact commands and counts, the CI evidence, the
manual status, and the gaps that remain.

## 1. What the person gets, and what they are told

The **HR contacts** tab already imported a list, marked a contact do-not-contact and listed the disagreements an
import recorded. It could not remove a record: the only erasure this application offered was
`--forget-local-data`, which takes the whole database. This increment adds the missing row-level action.

- **The control.** **Delete selected contact**, on its own row under its own sentence, in the tab's scrolling
  body. It is built `disabled` and enabled by the same `_sync_contact_actions()` that decides the two mark
  controls, for **any** selected stored contact — marked or not. A mark is a reason to be careful about
  contacting somebody, never a reason to keep their record, and this window does not decide which records a
  person may remove from their own database. With nothing selected the line under the controls names deleting
  among the actions a row offers.
- **The sentence.** `app.contact_delete_note` (a `StringVar`, so the words are read back by a test rather than
  only drawn) says that deleting removes one stored contact and every disagreement recorded about it in a single
  step, that no other contact, mark or disagreement is touched, that **there is no undo in this application**,
  that a backup written earlier still holds the record and that restoring that copy brings it back, and that
  nothing is sent to anybody either way.
- **The confirmation.** Titled *Delete this stored contact*. It names the **row** and not the person: its
  position in the stored list (`row N of M in the stored list`), the file the record came from, and the exact
  number of disagreements that go with it — counted from the same query the deletion uses — then the no-undo
  and backup sentences. The address, name, company, the reason a mark carries and every disagreement value are
  absent from it. This is the same reference style the mark confirmations already use, and it is what makes the
  question answerable without printing who it is about.
- **The report.** On success both views are re-read through one `_refresh_contacts()` call (the stored list and
  the disagreement panel), which is what clears the selection and greys the button again, and the status line
  reads `1 stored contact deleted, with N recorded disagreement(s). Nothing was contacted.` The dialog is built
  from the **store's own outcome** rather than the count the question used, because the two are read at
  different moments and what the person is told afterwards has to be what happened.
- **Every refusal.** Nothing selected → a dialog saying to select a row, status *…nothing was deleted*; a row
  the database no longer holds → *That contact is no longer stored*, nothing deleted, list refreshed; a declined
  confirmation → status *Cancelled; nothing was deleted.*; a row that goes **while the question is being
  answered** → the store's own `deleted=False`, reported as *already not stored* rather than as a deletion this
  window performed; an unreadable record (`StoredRecordError`) or any `sqlite3.Error` → the tab's existing
  reporting helpers. None of them writes a row, and none of them claims a success.

## 2. The erasure contract as it already exists (inspected, unchanged)

Read before writing any code, and deliberately not modified:

- `career_agent/erasure.py` implements **file-level, whole-database** erasure only: `plan_erasure` creates
  nothing and opens no database, and `erase` re-checks each path, refuses symbolic links and non-regular files,
  never walks a folder, and re-checks existence so nothing is reported removed that is not. There is no row
  deletion in it, and this increment did not add one.
- Row-level deletion lives in the store and already exists for other record types: `delete_profile` removes the
  profile **and** its history records in one transaction and logs counts, `delete_job` and
  `delete_work_history` delete a single row and log an identifier. Per-contact deletion therefore belongs in
  `CareerStore`, not in the erasure module — a screen that issued two deletes itself could leave the contact
  gone and its disagreements behind, which is exactly the half-deletion this increment must make impossible.
- The threat model's existing limit is unchanged and is not overstated anywhere in the window: erasure reaches
  the files this application derives and names the copies it cannot (backups, exports, calendar files and drafts
  written elsewhere). The new sentence about backups says the same thing for a deleted row.

## 3. The tables, the foreign keys, and why no migration was needed

Read from `career_agent/store.py` (schema 7) rather than assumed:

- `hr_contact(email_key TEXT …, …)` holds one row per email key.
- `hr_contact_conflict(conflict_id …, email_key TEXT …, … REFERENCES hr_contact(email_key) ON DELETE CASCADE)`
  is the **only** object in the schema that references either table, and `email_key` appears in no other module
  of the package. So the dependents of a contact are exactly its conflict rows, and they are reachable by the
  same key.
- `PRAGMA foreign_keys = ON` is issued once when the store opens its connection, so the declared cascade is
  live on every connection this application makes.
- Nothing about the tables changed, so the schema is still **7**, the migration runner was not touched, and the
  JSON export still does not carry the contact tables (`importer.export_payload` was read to confirm it).

## 4. The operation: one transaction, named deletes, and an honest count

`CareerStore.delete_contact(email_key) -> ContactDeletionOutcome(deleted, conflicts)`:

1. The key is normalised with the store's one email normaliser, so any spelling finds the record.
2. `BEGIN IMMEDIATE` opens one transaction by hand — the same pattern `import_contacts`, `claim_run` and the
   other multi-statement writers already use.
3. The contact row is read. **Absent key**: `ROLLBACK`, no write, no event, `deleted=False`. For a delete,
   "already gone" is the requested end state, and the caller is *told* rather than handed an exception —
   deliberately unlike `set_contact_suppression`, which raises in the same situation because a mark that
   silently did not happen would be a false claim about state meant to persist.
4. The conflict rows are counted, then deleted **by name** (`DELETE FROM hr_contact_conflict WHERE email_key =
   ?`), then the contact row (`DELETE FROM hr_contact WHERE email_key = ?`), then `COMMIT`.
5. Any `BaseException` → `_roll_back_quietly()` and re-raise, so the contact and its evidence both survive and
   the database is left usable.
6. Only after the commit: `_record("contacts.deleted", "contacts=1 conflicts=N")` — counts, and no address,
   name, company, note or file name. `ContactDeletionOutcome.describe()` renders the same facts for the status
   line; the dataclass deliberately does **not** carry the address, because an outcome is what a dialog and a
   log line are built from.

**Why the conflicts are deleted explicitly *and* the cascade is kept.** The declared `ON DELETE CASCADE` is
real and stays as a second line of defence for anything that removes a row another way. But a deletion that
quietly stopped removing rows because a pragma changed, or because a connection was opened without it, would
leave orphans behind while reporting a success — and whether a person's data actually went must not depend on a
setting. Both halves are asserted: one test deletes with `PRAGMA foreign_keys = OFF` and requires the evidence
to be gone anyway, and another asserts that the cascade really is declared and enabled (so the belt is not
imagined).

## 5. Files and commits

| File | What changed |
| --- | --- |
| `career_agent/store.py` | `ContactDeletionOutcome` with `describe()`, and `CareerStore.delete_contact` (+74 lines). |
| `career_agent/event_log.py` | `"contacts.deleted"` added to `EVENTS`, with the comment about what an event may carry extended to it. |
| `career_agent/desktop.py` | The button (grid row 14) and its sentence as a `StringVar` (row 15), the conflict panel's widgets renumbered 15→17 through 19→21, `_sync_contact_actions`'s delete branch and the reworded no-selection line, and `_delete_selected_contact`. |
| `tests/test_contacts_store.py` | `ContactDeletionTests` (12 tests). |
| `tests/test_desktop_handlers.py` | `ContactDeletionControlTests` (11 tests), one real-window wording test, the delete button in the double, and the button added to the layout-policy list. |
| `scripts/desktop_acceptance.py` | Workflow L gains **L13-L15**; `SYNTHETIC_OTHER_MARK_REASON` added. |

Commits (branch `arena/351e052d-ai-career-agent`, PR #2 open and unmerged):

| Commit | What it is |
| --- | --- |
| `c1b2ab1` | `feat(contacts): delete one stored contact and its recorded disagreements` — the implementation and every test above. |
| (this note's commit) | Documentation: this note, the checklist's steps 106-111, and the counts in `design.md`, `phases.md`, `README.md`, `task.md`, `memory.md`, the handoff and the research index. |

## 6. Tests: what is asserted, and what was proved to bite

| Command | Result |
| --- | --- |
| `python3 -m unittest tests.test_contacts_store` | `Ran 52 tests … OK` (12 of them new) |
| `python3 -m unittest tests.test_desktop_handlers` | `Ran 331 tests … OK` (11 of them new) |
| `python3 -m unittest tests.test_desktop_smoke_test` | `Ran 19 tests … OK` |
| `python3 -m unittest discover -s tests` | `Ran 1881 tests … OK (skipped=13)` |
| `python3 scripts/desktop_acceptance.py --stand-in-tk` | `97 checks passed, 0 failed`, `RESULT: BLOCKED` — a stand-in Tk is not a desktop, and the run says so |
| `python3 -c "import sys; sys.path.insert(0,'scripts'); import desktop_acceptance as a; print(a.declared_step_count())"` | `97` (read from the source, so no number elsewhere had to be edited) |

**Store level (12 tests).** Deleting one contact touches exactly **two** rows measured against the connection's
`total_changes` (the contact and its one conflict), and the other contact's conflict is still there — the
fixture gives **both** contacts a disagreement of their own precisely so a deletion that removed *every*
conflict row could not pass. The unrelated contact's `suppressed`, `suppressed_at` and note come back
unchanged. A key the store does not hold writes nothing and records no event. Key normalisation finds a
differently-spelled address. An injected failure on the conflict delete and on the contact delete both roll the
whole thing back, leave both contacts and both disagreements intact, and leave a usable database (the next
deletion succeeds). With `PRAGMA foreign_keys = OFF` the evidence still goes, and the cascade is separately
asserted to be declared and enabled. Afterwards there are no orphans, `PRAGMA foreign_key_check` is empty,
`integrity_check` passes and `user_version` is still 7. A restart and a backup taken **afterwards** agree with
the database, and — the honest limit, asserted rather than papered over — a backup taken **before** the deletion
still holds the record after a restore. The event carries `contacts=1 conflicts=1` and none of the fixture's
values.

**Handler level (11 tests).** The disabled/enabled states and the wording of the sentence on the *real* window's
builder; the confirmation's position/file/count wording with every contact and disagreement value asserted
absent; a declined confirmation (`total_changes` unchanged, both contacts and all three disagreements intact,
no `contacts.deleted` line, status *Cancelled*, no success dialog); nothing selected; a stale row; a row that
vanishes while the question is being answered (asked once, one row removed — the other deletion's — and
*already not stored* reported instead of a false success); the confirmed deletion changing **three** rows (the
contact and its two disagreements) with the other contact's mark, reason and disagreement byte-identical
afterwards, both views re-read, the selection cleared and the button greyed; the privacy of every surface
(the dialog, the status line, the state line, the summary, the panel note and the log) with the file name
*allowed* on screen — it is the reference the question is answerable by — and never in the log; an injected
`sqlite3.OperationalError` deleting nothing and reporting the tab's existing database-unavailable error; the
selection not surviving the deletion; and the report carrying the store's count when the screen's earlier read
was made to disagree with it.

**Proved to bite.** Four temporary mutations were made and reverted: removing the explicit
`DELETE FROM hr_contact_conflict` (2 tests fail), removing the rollback (1 failure, 1 error), ignoring the
answer to the confirmation (1 failure) and dropping the post-deletion refresh (2 failures). No assertion was
weakened to get any of these to pass.

## 7. The acceptance workflow: L13-L15

Three checks were **added inside workflow L** rather than making a thirteenth workflow, so the CI unit job's
loop over workflow letters is unchanged (`declared_step_count()` moves 94 → 97 by reading the source).

- **L13** — with two stored contacts (the second given a mark and a reason of its own, so a mark is left behind
  to protect), clears the selection: the button must be `instate(["disabled"])`, the state line must name
  deleting, the sentence must carry `no undo`, `disagreement`, `backup` and `Nothing is sent to anybody`, and
  then a **marked** row and an unmarked row must each enable it.
- **L14** — sets the dialog policy to answer *No*: the question must name `row N of 2 in the stored list`, the
  source file, `2 recorded disagreement(s)`, `no undo` and the nothing-is-sent sentence; the contact's own
  address, name and company, the other contact's mark reason and the disagreement values must **not** be in it;
  `total_changes` must be unchanged; both contacts and all three disagreements must still be stored; both marks
  and the reason must be intact; the status line must say nothing was deleted; and the log must contain no
  `contacts.deleted`.
- **L15** — confirms: `Contact deleted` must be reported, exactly **three** rows must have changed, the record
  must be gone from the store while the other contact's mark and reason and its own disagreement remain, the
  list must show one row, the summary must count one contact and one mark, the panel must hold one disagreement
  belonging to the surviving contact, the selection must be cleared, the button greyed, the status line must
  carry the counts and *Nothing was contacted*, and the dialogs and the log must contain no contact value (the
  log additionally containing no file name and carrying `detail=contacts=1 conflicts=2`).

## 8. CI evidence

| Run | Commit | What the legs reported |
| --- | --- | --- |
| `38875397574` | `c1b2ab1` | **13/13 jobs green** (`conclusion: success` on the run). Linux display-backed job `116889109924`: `RESULT: PASS — 97 checks passed`, with **L13, L14 and L15 `[ ok ]`** alongside L1-L12, and `RESULT: PASS — 14 checks passed` from the smoke script. macOS 26 legs `116889110326` (3.10) and `116889110329` (3.13): `Ran 1881 tests in 52.658s … OK (skipped=20)` and `RESULT: PASS — 97 checks passed`. Windows 2025 legs `116889110281` (3.13) and `116889110111` (3.10): `Ran 1881 tests in 458.337s / 616.865s … OK (skipped=39 / 46)` and the same `RESULT: PASS — 97 checks passed` on a real Tk 8.6 display. Unit legs 3.10-3.14 `116889110376` / `116889110366` / `116889110285` / `116889110400` / `116889110215`, installed-package legs `116889110343` (3.10) / `116889110251` (3.14), PDF extra `116889110262`. |

Nothing in this increment needed a fix after the run: `--stand-in-tk` reached 97/97 before the push, and the
first matrix on the commit was green, so **no new defect (`D36`) was found** and the cross-platform defect
register is unchanged — the L11/D35 fixes that the previous increment needed were already in place, and the
three new checks passed on Linux and macOS on their first attempt and on Windows too.

The one thing that had to be corrected during the work was in the *tests*, not the feature, and the record is
honest about it: the first version of `ContactDeletionTests` called an undefined `contact_file(...)` helper and
would have failed at collection; the store tests were then run and corrected (both contacts in the fixture given
a disagreement of their own so a deletion that removed every conflict row could not pass, and `foreign_key_check`
compared as the list SQLite returns rather than a tuple), and `python3 -m unittest discover -s tests` was run
again after every change. Nothing was committed before the suite was green.

## 9. Manual status: what a human still has to do

Steps **106-111** of `research/local-alpha-manual-smoke-test-checklist-2026-10-14.md` are new and all six are
**BLOCKED**: no display with Tkinter, no screen reader and no keyboard exists in this environment, and a
stand-in widget module is not a desktop. They ask for exactly the things no harness can judge — what a greyed
destructive button *looks* like, whether the confirmation reads clearly, whether the keyboard and mouse reach it
at the window's own minimum size, what a screen reader announces, and whether the sentence about a backup
written earlier is understood as the limit it is. Every one carries an "Automated coverage" line naming the
checks that do exist, so a tester does not redo what the harness already established. The checklist's head count
moved 105 → **111** steps, 22 PASS / **89 BLOCKED** / 0 FAIL, and no box was ticked.

## 10. What this deliberately does not do

- **No bulk deletion**, no "delete all", no deletion from anywhere but the selected row, and no way to delete a
  contact from the command line.
- **No export** of the contact list, and the JSON export still does not carry the contact tables.
- **No tombstone.** Nothing keeps the erased address, name or company: the event carries counts, and no other
  table references either contact table.
- **No change to the whole-database erasure** (`--forget-local-data`) and no change to backup or restore
  semantics: a backup is a copy, so a deletion before it is not a deletion in it, and the window says so.
- **No reach for the gaps this increment leaves named:** the mark still has one current reason rather than a
  history, disagreements still cannot be dismissed or merged, the panel still stops at 40 rows with no paging,
  and nothing acts on a mark yet.
- **No external action of any kind.** Nothing here opens a socket, and the gate stays closed:
  `SOURCE_QUALITY_GATE_PASSED is False`, `enabled_discovery_sources() == ()`.
