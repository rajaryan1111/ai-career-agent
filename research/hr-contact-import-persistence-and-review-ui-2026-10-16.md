# HR contact import: persistence, review UI and what a re-import may not do (2026-10-16)

**Increment:** Phase 0's second half - the list the parser could only report on can now be reviewed in the
window and stored locally, once, deliberately. Branch `arena/351e052d-ai-career-agent`; source commit
`168ac313c26679e99eaa1c6808e355e9f6cfaeef`; the documentation you are reading is the commit after it.
**Scope:** offline, local, single-user. Nothing here contacts a person, sends a message, matches a contact to
a listing, reaches a network, or opens a source. `SOURCE_QUALITY_GATE_PASSED` is still `False` and
`enabled_discovery_sources()` is still `()`, both asserted by the CI legs that run the suite.
**Companion documents:** [the parser/preview evidence](hr-contact-csv-preview-2026-10-16.md) (the shipped
`062a88c`), [the contact-list audit](hr-contact-list-audit-2026-10-15.md) (what a real export looks like,
counted without its values), the [handoff](../research/human-desktop-acceptance-handoff-2026-10-16.md) (what
a person still has to try by hand), and the register of
[cross-platform desktop CI evidence](cross-platform-desktop-ci-evidence-2026-10-15.md) (the matrix this
increment's run belongs to).

---

## 1. What changed, and the rule behind each piece

Three layers, one feature: parse (already shipped), decide, and store only on an explicit confirmation.

| Layer | Where | The rule it exists to enforce |
| --- | --- | --- |
| Parser | `career_agent/contacts.py` (unchanged) | Every original string survives; ambiguity is a refusal, not a guess |
| Decision | `CareerStore.plan_contact_import`, `_contact_decisions` | What a person confirms and what is written are one calculation, not two |
| Storage | schema 7: `hr_contact`, `hr_contact_conflict` | One key is one record; a re-import cannot rewrite the address, the company or a do-not-contact mark |
| Window | `career_agent/desktop.py`, the **HR contacts** tab | Reading a file stores nothing; storing it needs the plan shown first |

Nothing in this increment adds an abstraction of its own: the migration goes through `_MIGRATIONS` and the
existing runner, the entity follows the shape the other tables already use (a small dataclass, `_decode_*`
raising `StoredRecordError`, `_record` for the event, `_select_*` for the read), and the tab reuses
`_scrollable_body`, `_clear_tree` and the two shared failure reporters the other tabs use.

## 2. Schema 7

```sql
hr_contact(contact_id PK, email_key TEXT NOT NULL UNIQUE, email TEXT NOT NULL, name, company,
           review_flags TEXT NOT NULL DEFAULT '', review_reason, source_row,
           source_file TEXT NOT NULL, first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
           seen_count INTEGER NOT NULL DEFAULT 1,
           suppressed INTEGER NOT NULL DEFAULT 0, suppressed_at, suppressed_note)
  idx_hr_contact_company(company, email_key)
  idx_hr_contact_review(suppressed, last_seen_at, email_key)

hr_contact_conflict(conflict_id PK,
                    email_key TEXT NOT NULL REFERENCES hr_contact(email_key) ON DELETE CASCADE,
                    field TEXT NOT NULL, kept_value TEXT NOT NULL, other_value TEXT NOT NULL,
                    origin TEXT NOT NULL, source_file TEXT NOT NULL, observed_at TEXT NOT NULL)
  idx_hr_contact_conflict_contact(email_key, field, conflict_id)
```

Why each piece is there rather than a simpler alternative:

* **`email_key` is `UNIQUE`.** Deduplication is a database constraint, not a convention: however many rows of
  however many files name one address, a second record for that key is impossible. The key is always produced
  by `career_agent.contacts.normalise_email_key` - the address trimmed and case-folded and nothing else - so
  the review panel and the storage layer cannot disagree about what "the same contact" means.
* **`email`, `name`, `company` are the person's own strings.** A comparison key is not a display value: a
  `.invalid` address written as `First.Contact@Example.invalid` in somebody's export is shown back to them
  exactly as their file wrote it. Nothing normalises, trims or re-cases a value a person can read.
* **`source_file` is a name, never a path.** A database is backed up, restored and handed to someone else; a
  folder name in it is somebody's home directory. `Path(file_name).name`, falling back to `"contact list"`.
* **`first_seen_at`/`last_seen_at`/`seen_count` are import bookkeeping, not claims about a person.** They say
  when *this* application last read a key and how many imports have seen it. `seen_count` starts at 1 and only
  ever moves up, so a re-import is visible in the record it changed.
* **`suppressed`/`suppressed_at`/`suppressed_note` are the opt-out.** One method in the whole codebase writes
  them (`set_contact_suppression`); no import statement mentions the column at all, which is why the mark
  survives a re-import, a file that contradicts what is stored, a backup and a restore.
* **`hr_contact_conflict` is evidence, not a merge.** One row per pair of disagreeing non-empty values, with
  which field, which value was kept, which was not, and whether the disagreement is between two rows of one
  file (`file`) or between the file and the database (`stored`). `ON DELETE CASCADE` keeps the evidence from
  outliving the record it is about.

Two tables rather than one because they have different lifetimes: a contact is current state, a disagreement is
a dated observation about it.

## 3. Migration, upgrade and rollback

`_migration_to_v7` is appended to `_MIGRATIONS` as step 7 with the description *"add the imported HR contact
list and the disagreements found in it"*, and every statement in it is `IF NOT EXISTS`, so a step interrupted
after its first statement is completed by re-running it rather than leaving a database that cannot be opened.
The step is purely additive: a file that never imports a contact list differs from version 6 by two empty
tables, which is what makes it safe to run on real data. Nothing in the step reads or writes an existing table.

The behaviour a person actually gets comes from the existing runner, unchanged: opening an older file takes a
**verified snapshot first** (`_snapshot_before_upgrade`, beside the database, refused rather than ignored if it
cannot be written), runs each pending step inside one `BEGIN IMMEDIATE` per step, writes `PRAGMA user_version`
inside that transaction, records `database.migrated from=6 to=7`, and on a failure records
`database.migration_failed`, rolls the step back and raises `SchemaMigrationError` naming the step - so the
file is left at the version and with the rows it started from. `_initialize` still refuses a version above
`_SCHEMA_VERSION` and a version-0 file that already holds tables.

Evidence, all in `tests/test_store.py::SchemaMigrationTests`:

| Test | What it establishes |
| --- | --- |
| `test_the_contact_step_adds_its_tables_to_a_database_full_of_records` | A version-6 file holding a profile, a job, a tracker row with a follow-up, a preparation item, an interview round, a role and a qualification upgrades with every row intact; the new tables arrive empty; a synthetic list is then imported into the *upgraded* file with a do-not-contact mark and read back after a restart; the one pre-upgrade copy is still at **version 6** with its job row, and the log holds `database.migrated from=6 to=7` |
| `test_the_contact_step_can_run_again_on_a_database_that_already_has_its_tables` | Running the step twice changes no version and no row (the interrupted-step case) |
| `test_a_failed_contact_step_leaves_the_version_and_the_data_untouched` | A step 7 that half-applies and then raises leaves `SchemaMigrationError(target=7, from=6)` and a file whose job and tracker rows are still readable and whose contact list is still empty |

The version bump moves three pins, and they are the ones to check next time:
`SCHEMA_TABLES_BY_VERSION[7]` and `PRAGMA user_version` in `tests/test_store.py` (whose `tables == set(...)`
assertion fails loudly), `tests/test_backup.py`'s table-drift walk (unchanged, and green), and
`tests/test_store_tasks.py::SchemaTests`'s literal. `_MIGRATIONS` versions are asserted to be
`range(1, SCHEMA_VERSION + 1)`, so a missing step cannot pass.

## 4. The store API, and what a re-import may not do

| Method | Writes? | What it is for |
| --- | --- | --- |
| `plan_contact_import(parsed) -> ContactImportPlan` | no | The counts and the disagreements an import *would* produce, computed from the database and shown before anything is asked |
| `import_contacts(parsed, *, observed_at=None) -> ContactImportOutcome` | yes, once | One transaction: every record and every disagreement, or none |
| `list_contacts(*, suppressed=None)` | no | The stored records, filterable by the do-not-contact mark |
| `get_contact(email_key)` | no | One record by normalised key |
| `list_contact_conflicts(*, email_key=None)` | no | The stored disagreements |
| `contact_record_counts()` | no | `contacts`, `do_not_contact`, `with_review_flags`, `conflicts` |
| `set_contact_suppression(email_key, suppressed=True, *, note=None)` | yes | The only writer of the mark; refuses an address no import has stored |

The rules a re-import obeys, each asserted in `tests/test_contacts_store.py`:

1. **One key, one record.** The parser groups rows by key and the import writes one row per group, so a file
   that lists the same address three times stores one contact - and importing the same file again finds it
   stored and updates it.
2. **Identity text is never rewritten.** The `UPDATE` does not mention `email`, and it writes `name`/`company`
   only to the value the decision computed - which for a stored non-empty field *is* the stored value. A
   stored address with different case than the incoming one is therefore unchanged after the import.
3. **A disagreement is kept, never merged.** A later file naming a different non-empty name or company leaves
   the stored value in place and records the other one as a `stored`-origin conflict; two rows inside one file
   that disagree are recorded as `file`-origin, with the first value in file order kept, so which value wins
   depends on nothing but the order of the person's own file. An empty cell never disagrees with anything.
   Conflicts that are already stored for the same key, field, kept value, other value and origin are not
   recorded twice, which is what makes importing the same file again ask the same question once.
4. **Nothing is written before a confirmation.** `plan_contact_import` selects and computes and never writes;
   the zero-write assertion is the connection's own `total_changes`, not the message a person sees.
5. **A failure writes nothing at all.** `import_contacts` runs inside `BEGIN IMMEDIATE ... COMMIT` and calls
   `_roll_back_quietly()` on any exception before re-raising. An injected `sqlite3.OperationalError` (a
   connection wrapper, because `sqlite3.Connection.execute` cannot be patched) leaves the counts, the records
   and the disagreements exactly as they were.
6. **Rows with no email key are counted, not stored.** They have no identity, so there is nothing to key a
   record by; the plan reports them and the outcome says they were not stored.

The event is one line, after the commit, and carries counts only:

```
contacts.imported added=2 updated=0 conflicts=1 skipped=0 suppressed_untouched=0
```

## 5. The window: the HR contacts tab

The ninth tab, built inside a scrolling body for the same reason `Work history & study` and
`Background tasks` are: the preview, the review rows and the stored list together are taller than the smallest
page this window can be given at its own declared minimum (900x600), and content below the fold cannot be
reached unless something scrolls it. No address is drawn in a label: the values a person reads are in two
`Treeview`s (rows), and text drawn across the tab is the tab-wide wrap width, which CI measures on three
platforms at three sizes.

* **Choose a contact CSV...** opens the file chooser and calls `contacts.read_contact_csv` - the shipped
  parser, not a second one. A refusal shows the parser's own sentence plus "The database was not changed",
  records `import.refused`, clears the preview and leaves the stored list untouched; an unreadable *file*
  (the chooser returning nothing) sets the status line and returns.
* What is shown is the same report the command line prints (`describe()`: counts, columns used, flags) plus the
  flagged rows in the file's own order, each with the parser's reasons.
* **Import these contacts** computes the plan from the database (added, updated, disagreements to keep, keys
  already marked do-not-contact, rows with no key) and puts those counts *inside* the confirmation
  ("Import these contacts?"), so the decision is made with the consequences visible. Declining writes nothing.
* On confirm, `import_contacts` runs and the window reports the outcome in the status line and one dialog -
  opened only after the transaction returned.
* **Clear the preview** forgets the file; nothing was ever stored for it, so there is nothing to undo.
* **Refresh** re-reads the stored list and the counts line beneath it.

The tab does not offer anything this increment does not implement: there is no button that contacts anybody, no
matching, no draft, and the confirmation says in its own words that nothing is contacted and no address leaves
the machine.

## 6. Privacy boundaries

* **No fixture, screenshot or log in this repository holds a real contact.** Every address used in tests and in
  the acceptance run is on a reserved `.invalid` domain, and the values are synthetic (`Sample Person One`).
  No private CSV has ever been read by this work.
* **The command line and the event log carry no contact value**: `contacts.imported` is counts and an outcome;
  `ContactsImportPlan.describe()` is counts, field names and reasons; the parser's refusals quote no cell.
* **The window shows values, locally, to the person whose file it is** - that is the review screen's job, and
  it is why the values live in a tree rather than in a label (an acceptance measurement prints label text).
* **Provenance is a file name, never a path**, so a database handed to somebody else does not carry a folder
  structure.
* **Backups and restores carry the list, the disagreements and the marks** - they are rows in the same
  database - and the restore path's existing validation applies unchanged.
* **The JSON export does not carry the list.** `career_agent.importer.export_document` builds explicit
  sections (`profile`, `jobs`, `work_history`, `education`); the contact tables are not among them, so a
  contact list cannot leave through the export feature. Moving a contact list between machines is therefore
  **not** supported yet, and that is a gap rather than a claim.
* **Erasure** (`career_agent.erasure`) removes the database and its side files by the paths it already derives,
  so the two new tables are covered by the existing whole-database removal; there is no per-contact deletion,
  which is a named gap.

## 7. Test evidence (exact commands, actual output)

Run on Linux, CPython 3.11.2 (no display in this checkout, so the display-backed workflows are BLOCKED here by
construction and are exercised by the CI legs):

| Command | Output |
| --- | --- |
| `python3 -m unittest tests.test_contacts_store` | `Ran 39 tests ... OK` |
| `python3 -m unittest tests.test_store` | `Ran 187 tests ... OK` |
| `python3 -m unittest tests.test_store_tasks` | `Ran 39 tests ... OK` |
| `python3 -m unittest tests.test_desktop_handlers` | `Ran 296 tests ... OK` |
| `python3 -m unittest tests.test_desktop_smoke_test tests.test_desktop_acceptance tests.test_desktop_logic` | `Ran 111 tests ... OK` |
| `python3 -m unittest tests.test_contacts` | `Ran 48 tests ... OK` |
| `python3 -m unittest tests.test_backup tests.test_cli_forget tests.test_event_log tests.test_damaged_records tests.test_documented_commands tests.test_local_only` | `Ran 159 tests in 5.9s ... OK` |
| `python3 -m unittest discover -s tests` | **`Ran 1832 tests in 64.5s ... OK (skipped=13)`** |
| `python3 -m compileall -q career_agent scripts tests` | no output (clean) |
| `python3 scripts/desktop_acceptance.py --stand-in-tk` | `DEVELOPMENT RESULT: 87 checks passed, 0 failed, against the test suite's stand-in widget module`, exit 2 - a development run against stubs, **not** desktop evidence |

The nine families the increment was specified to cover, and where each lives:

| Family | Where |
| --- | --- |
| Migration 6->7 on a populated database, backup-before-upgrade, idempotent step, rollback, older paths | `tests/test_store.py::SchemaMigrationTests` (3 new tests) + the existing v1/v4/v5/v6 upgrade tests |
| New import, repeat import, duplicate rows in one file, re-import after a name/company change, deterministic conflicts | `tests/test_contacts_store.py::StoredContactTests`, `ContactPlanTests` |
| Suppression across re-import, a conflicting file, backup/restore and restart | `tests/test_contacts_store.py::SuppressionTests` |
| Cancel, close, parse refusal and a declined confirmation = zero writes | `NothingIsWrittenBeforeAConfirmationTests` (change counter), `tests/test_desktop_handlers.py::ContactImportTabTests` |
| Confirm writes exactly once; injected storage failure rolls back and shows no success | `WriteExactlyOnceTests`, `ContactImportTabTests.test_a_storage_failure_is_reported_and_no_success_is_shown` |
| Malformed input: bad address, missing name, ambiguous columns, malformed CSV, caps, extra columns, BOM, UTF-16 | `tests/test_contacts.py` (the shipped parser's own 48 tests) plus the refusal paths through the tab |
| Privacy: fixture values absent from logs and CLI output; no contact value in an event | `ContactPrivacyTests`, `tests/test_event_log.py`, the CLI tests in `tests/test_contacts.py` |
| Display-backed GUI patterns: focus, scrolling, cancel, confirm | workflow **L** in `scripts/desktop_acceptance.py` (5 checks) on the five display-backed CI legs; `tests/test_desktop_handlers.py::TabLayoutPolicyTests` for what the tab asks for without a display |
| Regression, compile/lint, existing backup/restore | the full suite above, `compileall`, `tests/test_backup.py`, `tests/test_erasure.py` |

**CI.** The run for the commit that carries this note is recorded in the session report and in `phases.md`
(run id, conclusion, per-leg `RESULT:` lines). The last fully green matrix on this branch was run
`38823626117` at `3a88e6e` (13/13 jobs, 82 checks per display-backed leg, 1778 tests per leg); this increment
adds workflow L and 54 tests, so its own run is the evidence that matters, not that one.

## 8. Known gaps and the next smallest task

Named gaps, in the order a person would meet them:

1. **No human has used the tab.** Every automated check above is a machine's; the checklist's window steps stay
   BLOCKED (see the handoff), and this note claims nothing about wording, focus feel, assistive technology or
   a real mouse.
2. **The do-not-contact mark cannot be set from the window or the command line.** It is durable, displayed and
   tested, but only `CareerStore.set_contact_suppression` writes it. A screen for it is the natural next step
   *if* it is wanted before matching, since a mark nobody can set is a promise without a control.
3. **Recorded disagreements cannot be resolved or dismissed.** They accumulate with their dates; a person can
   read the counts and the keys but cannot say "I have seen this one".
4. **Row-by-row accept/reject and exporting the refused rows are not implemented** - the file is imported as a
   whole, or not at all.
5. **A contact list cannot be exported or moved between machines** (the JSON export does not carry it) and
   there is no per-contact deletion.
6. **Nothing is matched, drafted or sent**, and no source is enabled. That is the closed gate, not an
   oversight.

**Next smallest task:** either (a) a small, local **do-not-contact control** in the same tab (select a stored
contact, mark or unmark with a note, confirmed, zero writes on cancel) with the store API it already has - or
(b) the **conflict review panel** that lists the recorded disagreements for a key so the evidence is readable
without a database browser. Both are local, both are testable with the same harness and fixtures, and neither
touches a source, a network or an external action.
