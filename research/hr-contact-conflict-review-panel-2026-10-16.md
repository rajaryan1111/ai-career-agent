# HR contact conflict review panel (2026-10-16)

**Question.** The application has recorded disagreements between a person's HR contact files and their stored
contacts since schema 7 - and, until now, a person could see only the *count* of them (`3 disagreement(s) kept
for review`). How does a person read what a recorded disagreement actually says, and where each side came from,
without any of it being merged, resolved, dismissed or changed?

**Answer, short.** The **HR contacts** tab now lists every recorded disagreement, oldest first, and describes
the selected one in full: the address, the field, both values under labels that distinguish what this database
keeps from what the file said, the provenance the schema actually holds, when it was recorded, and a closing
sentence that says plainly that nothing here is merged, resolved or dismissible. It is read-only in the strong
sense that the tests measure: opening it, listing it, selecting every row in it and re-reading it after another
connection imports writes **zero rows**, leaves the do-not-contact mark and its reason untouched, and puts no
contact value in a dialog, the status line, the activity log or the count-only note under the list.

---

## 1. What was inspected before any code was written

| Inspected | What it settled |
| --- | --- |
| `planning/arena-task-phase-0-contact-conflict-review-panel-2026-10-16.md` | The scope: read-only review in the existing tab, both sides plus provenance from persisted schema fields only, deterministic order, bounded rendering, refresh after an import and on revisit, synthetic fixtures, zero writes, no migration unless inspection proves the record cannot support the view. |
| `hr_contact_conflict` DDL (`career_agent/store.py`, schema 7) | The record holds exactly: `conflict_id`, `email_key`, `field`, `kept_value`, `other_value`, `origin`, `source_file`, `observed_at`. Nothing else exists, and nothing new was needed. **No migration was added.** |
| `ContactConflict` / `ContactConflictOrigin` | `origin` is `file` (two rows of one file disagree) or `stored` (the file disagrees with what the database holds); `kept_value` is the value this application stores and `other_value` the one it does not. |
| `CareerStore.list_contact_conflicts(email_key=None)` | Read-only, `ORDER BY conflict_id`, no paging and no lookup-by-id parameter. The panel therefore keeps the store's own order (oldest first) and re-reads the list when an id has to be resolved - **no store parameter was added just to avoid one re-read**, and no call in the panel writes. |
| `_contact_disagreements` (`store.py`) | The exact rules the panel describes: two **non-empty** values that differ; within one file the **first non-blank answer in row order** is kept; against the database the **stored value** is kept; one entry per (field, value) pair, so a file repeating the same second value asks one question; a pair already recorded is not recorded twice, so an idempotent re-import adds no row. Values are stripped before they are recorded - which is why the panel's long-value test compares against the stripped value. |
| `hr_contact` (`source_file`, `first_seen_at`, …) | The stored contact *does* record the file it was first seen in - and that is a **different fact** from "the file that supplied the value this database keeps". The panel does not use it as provenance for `kept_value`, and says so on screen instead. |
| `career_agent/desktop.py` (the contacts tab, its builders, every selection handler) | The tab's existing patterns: a scrolling body, `ttk.Treeview` lists with `show="headings"`, `tk.StringVar` notes, a `tk.Text` for read-only multi-line text, per-tab refresh through `_refresh_contacts`, and the rule that a *selection* never writes the status line (the status line is the activity-log channel). |
| `tests/test_desktop_handlers.py` (the stand-in widget module, `ContactTabTestCase`) | How the handlers are tested: real career-agent objects over a disposable synthetic database, a widget stand-in that refuses unknown options and fires the virtual events real Tk fires, per-tab layout policy tests. |
| `.github/workflows/tests.yml` (`for workflow in A B C D E F G H I J K L`) | Workflow **L** had to be extended rather than a workflow **M** added; `tests/test_desktop_acceptance.py` asserts that letter list verbatim. |
| The two HR research notes (import/persistence and the do-not-contact control) | The preflight evidence, and the named gaps this increment closes one of ("disagreements cannot be resolved" becomes "disagreements can be read; resolving them is still deliberately absent"). |
| `scripts/desktop_acceptance.py` (workflow L, the focus walk, `settle_window`, `press`) | What was already asserted about the tab, and what a display-backed check may claim. |

## 2. What the panel shows

* **A list, oldest first, numbered from 1.** Columns: `#`, `Contact`, `Field`, `Which two sides`, `Recorded
  from`, `Recorded at`. The contact column shows the **stored contact's own address text** (read from
  `list_contacts()` in the same try as the conflict list), falling back to the normalised key only if no stored
  record exists; the panel never spells a person's address differently from the stored list above it.
* **Which two sides disagree**, in words: `two rows of one file` or `your records vs the file`.
* **The file the disagreeing value arrived in**, which is the file *name* the store recorded - provenance that
  cannot export somebody's home directory, because `_source_file_name` reduced it to a name at storage time.
* **The selected row in full**, under `Kept in this database:` and `Recorded from the file:`, followed by
  `Where each side comes from:` with one line per side and the time it was recorded.
* **A sentence that says what the screen will not do**: not merged, not resolved, no way to dismiss a recorded
  disagreement, and editing the source file and importing it again does not rewrite what the records state.
* **Counts only in the note under the list** (`3 disagreement(s) recorded, oldest first. …`), so the note, the
  status line and the event log can never disagree about who was involved - the note names no one.

**Bounded rendering.** The list holds the first **40** recorded disagreements (`_CONFLICT_ROWS_SHOWN`) and the
note states how many are held when the cap bites, in the same sentence, rather than dropping rows silently. Each
list cell is flattened to one line and clipped at **60** characters (`_CONFLICT_CELL_CHARACTERS`). Each value in
the detail panel is capped at **400** characters (`_CONFLICT_VALUE_CHARACTERS`) *with its real length and the
fact that only the beginning is shown* stated underneath - a clipped value never reads as a complete one. A
20 MB contact CSV can carry a field larger than any screen, so "show it all" is not a promise this window can
keep; "say what was cut" is.

**Refresh.** `_refresh_contacts()` ends by refreshing the panel, so a confirmed import updates the list in the
same read as the counts. The tab also binds `<<NotebookTabChanged>>`: when the contacts tab is *shown*, it runs
the same `_refresh_contacts()` - one implementation, no second read path - so a disagreement recorded by another
connection (or a restore from the Data safety tab) is on screen the moment the tab is looked at. Selecting rows
and re-reading never opens a dialog and never writes the status line.

## 3. Provenance: what the record holds, and what it does not

| Origin | What the panel says about the kept side | What it says about the other side |
| --- | --- | --- |
| `file` | "the first answer in that file's own row order. The row is not recorded, so this screen does not claim which one it was." | "'<file>' said something different about the same address." |
| `stored` | "the value this database already held when the file was imported. The row is not recorded, so this screen does not claim which file supplied it." | "'<file>' said something different about the same address." |

Neither side is called correct, current, newer or better; the panel has no wording that picks a winner, and the
research task's rule that it must imply neither is correct is enforced by the text itself (a check rejects
`is correct`, `is right`, `should be`, `has been resolved` anywhere in the detail). The panel also does not
present the stored contact's own first-seen file as the provenance of the kept value, because the schema does
not connect those two facts.

## 4. Read-only, and how that is established

`tests/test_desktop_handlers.py::ContactConflictPanelTests` (9 tests) and `TreeRowReadbackTests` (2 new tests)
assert, over a disposable synthetic database:

| Test | What it establishes |
| --- | --- |
| `test_each_recorded_disagreement_is_listed_with_its_own_provenance` | Three rows for three real disagreements (one file-vs-itself, two file-vs-stored), numbered 1-3, fields `name`, `name`, `company`, origins and file name per row, and the count in the note. |
| `test_both_sides_are_labelled_and_neither_is_called_the_right_one` | Both values, both labels, the provenance wording, and the absence of any "is correct" style claim. |
| `test_a_database_that_never_disagreed_lists_nothing` | The empty state's sentence, and an empty list. |
| `test_a_list_longer_than_the_panel_shows_says_so` | 45 stored disagreements: 40 rows listed, and the note says the rest are still stored and that this build cannot page to them. |
| `test_a_long_value_is_bounded_in_the_detail_and_a_long_file_name_is_clipped_in_the_list` | The 400-character detail cap with its stated real length, the 60-character cell, and that the whole value is not drawn into the panel. |
| `test_reviewing_every_row_writes_nothing_and_leaves_the_mark_alone` | `total_changes` unchanged, the mark and its reason unchanged, and the detail widget left `disabled`. |
| `test_no_contact_value_reaches_a_dialog_the_status_line_or_the_log` | Every contact value absent from the dialogs, the status line and the activity log, with the mark's reason as the control case. |
| `test_a_disagreement_recorded_while_the_tab_was_elsewhere_appears_when_it_is_shown` | A second `CareerStore` connection imports a contradicting file; showing the tab again lists it, with no write from the window. |
| `test_a_selection_that_is_no_longer_recorded_is_reported_rather_than_described` | A selected id the database no longer holds draws the "no longer recorded" sentence instead of describing stale values. |
| `TreeRowReadbackTests::test_the_arrow_keys_navigate_from_the_focus_item_the_way_tk_does` | The stand-in tree navigates from its focus item like Tk 8.6, including the silent case where no item holds it. |
| `TreeRowReadbackTests::test_a_deleted_row_is_no_longer_the_focus_item` | A deleted row loses the focus item, as Tk drops it. |

Two more tests live in `TabLayoutPolicyTests`: the notebook re-reads the contacts tab when it is shown
(`test_the_notebook_rereads_the_contacts_tab_when_it_is_shown`, which also asserts that both trees are bound to
the handlers their selection events post), and the panel's two new widgets sit inside the tab's scrolled
container (`test_the_panel_widgets_sit_inside_the_tabs_scrolled_container`).

## 5. Commands and counts

| What | Command | Result |
| --- | --- | --- |
| The panel's own tests | `python3 -m unittest tests.test_desktop_handlers.ContactConflictPanelTests` | `Ran 9 tests … OK` |
| The contact-tab handler module | `python3 -m unittest tests.test_desktop_handlers` | `Ran 320 tests … OK` |
| The acceptance harness, as far as this machine can go | `python3 scripts/desktop_acceptance.py --stand-in-tk` | `94 checks passed, 0 failed`, `RESULT: BLOCKED` (no display here, no tkinter in this interpreter) |
| The whole suite | `python3 -m unittest discover -s tests -q` | `Ran 1857 tests … OK (skipped=13)` |

The harness declares **94** checks now (`declared_step_count()` reads the source, so no count elsewhere had to
be edited): workflow L's L10, L11 and L12 are new, and L11 is the only check in the harness that presses a real
key and watches what the window does with it. `scripts/desktop_smoke_test.py`'s inventory of the window's lists
gained `contact_conflicts_tree` with its six columns, so the smoke script's structural pass covers the new tree.

## 6. CI evidence, and a failed run

| Run | Commit | Result |
| --- | --- | --- |
| `38861539212` | `7323457` | **Red - the first attempt.** The display-backed legs failed L11 with `SmokeFailure: the down arrow did not move the selection: ('1',)`: Linux smoke job `116844709877`, macOS 3.10 `116844709946`, macOS 3.13 `116844709973`. Everything else in workflow L passed on those legs - L10 and L12 included - and the unit, installed-package and PDF-extra jobs were green. |
| `38861941267` | `3778a39` | **Half fixed: Linux and macOS green, both Windows legs still red.** Linux smoke job `116845978858`: `RESULT: PASS — 94 checks passed` (L1-L12 `[ ok ]`, K4/K5 `[ ok ]`), `RESULT: PASS — 14 checks passed`, focus measurement `focus 'HR contacts' -> 7 stop(s) in the order, 7 of them in this window, 7/12 interactive control(s) reached`. macOS 26 legs `116845978986` (3.13) and `116845979071` (3.10): `Ran 1857 tests … OK (skipped=13 / 20)` and `RESULT: PASS — 94 checks passed` on real displays (Tk 8.6, 1024x768 CG0.0 Apple AppKit 2685.7). Windows 2025 legs `116845979153` (3.10) and `116845979063` (3.13) failed the same check with the same message. |
| `38864632201` | `4b4e752` | **Green - 13/13 jobs.** Linux smoke job: `RESULT: PASS — 94 checks passed` and `RESULT: PASS — 14 checks passed`; both macOS and both Windows legs: `Ran 1857 tests ... OK` with the acceptance run reporting `RESULT: PASS — 94 checks passed`. |

**D35 - the check pressed an arrow key Tk navigates nowhere without, and then did it in a window Tk would
not deliver a key to.** The panel was correct; the *check* was
wrong, and only a display could show it. Tk 8.6's `ttk::treeview::Keynav` (read from `library/ttk/treeview.tcl`
on the `core-8-6-branch`) starts at `set focus [$w focus]` and returns immediately when no item holds the
tree's focus item - the row a *click* draws its rectangle around. The check had set the tree's **selection**
(which the stand-in fires `<<TreeviewSelect>>` from, and which the app's handler follows) and then pressed
`<Down>`; on a real display Tk did what it does and moved nothing. The local stand-in could not have caught it,
because it navigated from the selection. Fix: the check sets the focus item first, exactly as a click does, and
the stand-in now models Tk's behaviour faithfully - focus item, navigation from it, arrow bindings that exist
and silently do nothing without one, and a deleted row losing the focus item - with two tests pinning that
parity. The first fix took it only half the way, and the Windows legs of the very next run said so: setting
the treeview's focus item is not enough, because Tk's `event` manual requires that "the window has focus to
receive the event properly" for key events, and `focus_set` is ignored while the application's window is not
the active one - the ordinary state of a subprocess driving a window in CI on Windows. The harness now calls
`focus_force`, which sets the focus regardless of the application's active state, and its failure message names
both focuses so a future failure says which one was wrong. What a person therefore sees, in every list in this
window and not only this one, is Tk's behaviour: arrow keys move from the row that was last clicked, and a
freshly focused list does not move at all until a row is clicked. That is written into the manual checklist
rather than papered over.

## 7. Manual acceptance status

Seven numbered steps (**99-105**) were added to
`research/local-alpha-manual-smoke-test-checklist-2026-10-14.md` in a new area section, *HR contacts: the
recorded-disagreement panel*. Every one is **BLOCKED** for the named missing capability - no human has a window
on a display in this environment - and **no box is ticked**. Steps 99-105 cover: the empty state; the rows and
their provenance after a contradicting import; the selected row's two sides and the absence of any claim that
either is right; the keyboard (tabbing to the list, clicking a row, Up/Down, and Tk's focus-item behaviour); a
long value and a long file name; the refresh when the tab is shown again with the mark untouched and no value in
the log; and the >40-disagreement note. The tab previously had **no** numbered steps at all - a gap the handoff
named - so this is the first manual material for it.

What a human still has to judge, in this environment's words: whether the two labels read clearly, whether
"Which two sides" is understandable without the sentence below it, whether the detail text's length and wrapping
are comfortable at the window's minimum size, whether the list scrolls under the mouse and the keyboard the way
it should, how the two new widgets look on each platform's native theme, and whether the panel's presence on
the tab makes the tab feel crowded. None of that is established by a machine driving widgets.

## 8. Named gaps (deliberately not in this increment)

* **No paging.** More than 40 disagreements are held and stated, not browsable. The cap is a rendering cap, not
  a data cap, and the note says so.
* **No dismissal, resolution or merge**, and no way to mark a disagreement as reviewed. This is the scope the
  task set.
* **No export of the disagreement list**, no per-contact deletion, no change to the JSON export (contacts stay
  out of it), and no edit of any contact from this screen.
* **No reason history for the do-not-contact mark**, and nothing that acts on a mark yet.
* **No human has used the tab** on any platform, so its wording, layout and keyboard feel are still unverified
  by the only judge that counts.
