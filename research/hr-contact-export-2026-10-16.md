# Exporting the stored HR contact list, and what the file deliberately is not

Date: 2026-10-16 · Task: `planning/arena-task-phase-0-hr-contact-export-2026-10-16.md` ·
Branch: `arena/351e052d-ai-career-agent` · Scope: local, offline, read-only, no schema change, no external action.

**Status:** Implemented, tested, and driven through the real window on five display-backed CI legs across three
platforms; documented here after verification. The human half is **not** done: steps **112-117** of the manual
checklist are new, all six are **BLOCKED**, and no box has been ticked. Schema stays **7** — no migration was
needed and none was written. `EXPORT_FORMAT_VERSION` is still **2** and the JSON export is asserted byte-identical
across a contact export; the contact list is still absent from it. `SOURCE_QUALITY_GATE_PASSED` is still `False`
and `enabled_discovery_sources()` is still `()`; this increment opens no socket and sends nothing.

Two defects were found **by the CI legs and by verification, not by reading**: **D36** in the path redaction the
activity log goes through, and a partial-write leak in the writer. Both are fixed, both have regression tests
that fail without the fix, and both are written up in section 7.

## The question this note answers

The HR contacts tab could read a contact CSV, store it, mark a contact do-not-contact, read the disagreements an
import recorded, and delete one record with its evidence — but the list itself could not leave the database.
The only export this application had was the version-2 JSON document, which deliberately does not carry the
contact tables, so "take a copy of my list to another machine" had no path at all.

This increment adds one: a **separate, explicitly user-initiated** CSV export with its own format, command,
control and sentence about what it is not. The two things the task required to be settled *before* code — which
fields belong in a portable list, and how the do-not-contact state travels — were decided from the code:

- **What goes in the file** came from what the shipped parser can read back (`career_agent/contacts.py` maps
  `Email`, `Name`, `Company Label`, `Source Rows`, `Review Reason`), what the store holds (`ContactRecord`), and
  what the existing export contract is (`importer.py`, `EXPORT_FORMAT_VERSION = 2`). The result is the smallest
  set that makes the file a usable list: address, name, company label, the mark as readable text, and a version
  cell. Section 2 lists what is out and why.
- **Suppression** is the safety-critical part, and the task allowed two honest outcomes: a portable suppression
  field with a compatible import path, or no claim of a lossless backup plus a documented limitation. This
  increment takes the second, for reasons that are in the code: the mark's only writer in the whole application
  is `CareerStore.set_contact_suppression`, and no import statement mentions that column — a file that could set
  a mark could also set one for an address it had no business deciding about. So the mark travels as **text a
  person reads**, the file is never described as safety-preserving, and the thing that does preserve it (the
  whole-database backup) is named in the window, in the command's output and here.

## 1. What the person gets, and what they are told

- **The control.** **Export the stored list...** on the HR contacts tab, under its own heading and its own
  sentence, in the tab's scrolling body. It is never greyed out: a database with no contacts still has a list,
  and an empty list writes an empty list. It opens a **Save as** dialog whose file type is the contact CSV.
- **The sentence beside it** (a `StringVar`, so a test reads what the window says and not what the source draws)
  says what the file holds, that the mark column travels as text, that an existing file is only replaced after a
  confirmation, that it is "a list to move between machines or read, **not a backup of this application**", and
  ends with *Nothing is sent anywhere, and exporting changes nothing in this database.* The part about the mark
  column is **the format module's own sentence** (`contact_export.MARK_COLUMN_LIMITATION`), so the window, the
  command and this note cannot describe the limitation three different ways. Its claims are asserted twice over:
  that each screen carries the module's sentence, and what that sentence actually says (`"Do Not Contact"`
  named, an import `cannot set or clear` it, `read the column` as what to do instead) — the second kind of
  assertion exists because a mutation proved the first kind alone could be satisfied by a sentence that said
  nothing (section 6).
- **The write itself.** One CSV file at the path the person named, through the store's own private write path,
  never through a symbolic link, owner-only from the first byte where the platform has POSIX permissions.
- **Success is claimed last.** The file is read back and compared **byte for byte** with what was written; only
  then is anything said. A file that does not hold exactly that is removed where possible and the call raises
  instead of returning.
- **A completed export says**: the counts and the size ("Wrote 2 contact(s) - 1 marked do not contact - to the
  file you chose (237 bytes)."), the fields the file holds and the ones it deliberately does not, the mark
  column's limitation in the format's own words, and *Nothing was sent to anybody, and the database was not
  changed.* The **path is deliberately not in that report**: a dialog is the part of this program that ends up in
  a screenshot, and a folder name is an account name as often as it is anything else. The command line prints the
  path instead, because that is the person's own terminal.
- **A cancelled or closed dialog** is not a failure and not a success: nothing is written, nothing is said, no
  status line changes and no event is recorded.
- **The command.** `python -m career_agent --export-contacts-to PATH` writes the same file with the same
  guarantees and **refuses a path that already exists** (`REFUSED: … already exists. Choose another name so the
  existing file is not replaced.`, exit status 2), so a scripted export never clobbers a file. It refuses, with
  nothing created, when there is no database, when the database file is empty or is not a database, when the
  folder does not exist, when the list is over the format's own limit, and when the store cannot read a record.
- **The activity log** gains `contacts.exported` with `contacts=N marked=M` after a write, and
  `contacts.export.failed` with a reason on a refusal. An event never carries an address, a name, a company, a
  mark's note, a disagreement value or the name of the file somebody chose — the same rule the import's events
  follow, and the rule D36 turned out not to hold on Windows (section 7).

## 2. The format: `hr-contact-export/1`

One comma-separated file, **UTF-8 with a byte-order mark**, records separated by **`\r\n`** (RFC 4180), one header
row and one row per stored contact, in the order the contacts were first stored (the store's own `contact_id`
order).

| Column | What it holds |
| --- | --- |
| `Email` | The address as stored — not the normalised key. The key (`hr_contact.email_key`) is trimmed and case-folded for matching and never appears in the file. |
| `Name` | The person's name as stored, empty when the record has none. |
| `Company` | The company label as stored, empty when the record has none. |
| `Do Not Contact` | `yes` when the record carries the mark, `no` when it does not. Two literals, never an empty cell — see section 3. |
| `Export Format` | `hr-contact-export/1` on **every** row, so a file that is renamed, trimmed or handed on can still say what it is. |

**Excluded on purpose**, each read out of the code rather than assumed: the internal identifiers (`contact_id`,
`email_key`), `first_seen_at`/`last_seen_at`, the import count, the source **file name** and source **row**
(filesystem provenance, and a folder is somebody's account name), the review flags and the review reason (a note
the *source file* carried), every `hr_contact_conflict` value (the other side of a disagreement is exactly the
material the conflict panel exists to show in full rather than in a file), the mark's `suppressed_at` and
`suppressed_note`, and every activity record. The whole-database backup on the Data safety tab copies those — it
copies the database itself.

**Encoding, escaping and line endings, to the byte.** UTF-8 with a byte-order mark, because UTF-8 is what the
format is and a byte-order mark is a stronger statement of it than a filename. Cells holding a comma, a quote or
a line ending are quoted with their quotes doubled by `csv.writer` (`QUOTE_MINIMAL`), which is what
`career_agent.contacts.read_contact_csv` reads back. CRLF record separators are written **as bytes** rather than
through the text writer, because a text write translates `\n` to the platform's own separator and a documented
format that is one file on Linux and another on Windows is not a format. The two line-ending claims are kept
apart and both are asserted: every *record* separator is CRLF (a fixture with no line endings in its values holds
no bare `\n` anywhere), while a line ending that is part of a *value* stays inside the quotes the writer put
around it (a fixture whose one value holds a newline is asserted to hold exactly that one extra `\n`, counted).

**Spreadsheet formula injection.** A cell whose first character is `=`, `+`, `-` or `@` is written with a
**leading apostrophe**, which every spreadsheet understands as "treat this as text". Only those four characters
and only in that position: an ordinary address, name or company is written exactly as it is stored, and the
apostrophe is documented as part of the cell text for anything that reads the file — including this
application's own parser. It is needed because the *sources* of these strings are files the person imported,
which may have come from anywhere.

**Bounds, decided by the reader rather than by a new constant.** The export refuses **before any path is created**
when the list holds more than `contacts.MAX_CONTACT_ROWS` (50,000) contacts or when the file would be larger than
`contacts.MAX_CONTACT_CSV_BYTES` (20 MiB) — the two limits the shipped parser enforces on read. A file this
program could not read again would not be an export of the person's list, so it is not written, and the refusal
names the Data safety backup instead. An **empty list** is not refused: it is a list with nothing in it, and the
file gets its header row and no data rows, which the parser reads back as zero rows.

**Duplicate keys cannot occur**: the schema stores one row per `email_key`, so the export writes one row per
stored contact, and a test asserts the file's keys are unique however many times an address was imported.

## 3. Suppression safety: the decision, and both directions of it

The mark is the one field in this list that is a **safety** fact rather than a contact detail, so the decision is
written down here rather than inferred from the column list.

**The decision: the mark travels as readable text, an import cannot apply it, and no file from this export is
ever called a safety-preserving backup.** The alternative the task allowed — a portable suppression field with a
compatible import path — was not taken, and the reason is in the code: `CareerStore.set_contact_suppression` is
the **only** writer of `hr_contact.suppressed` in the application, `import_contacts`'s `INSERT` never names the
column and deliberately does not, and the shipped suite asserts that an import leaves the mark exactly as it was.
Teaching an import to trust a column would mean a file — one somebody else could have edited, or generated —
could decide that a person is safe to contact. Marking every contact "do not contact" is a nuisance; unmarking
one is the harm, and the format has no way to know which file it is holding.

So the safety is stated where a person looks, and asserted where a test can:

1. The column exists and is explicit (`yes`/`no`, never empty), so the state is not **silently discarded**: it is
   in the person's own file, readable after a move or a restore.
2. The sentence beside the control, the completion dialog and the command's output all repeat
   `MARK_COLUMN_LIMITATION` — an import of this file cannot set or clear the mark, and the column is there to be
   read.
3. The window's own sentence and the command's output say the file is **a list rather than a backup**, and name
   the whole-database backup on the Data safety tab as the thing that copies everything, marks included.
4. The `--export-contacts-to` help text says the same in one line, and the format's module docstring says a file
   this module writes "must never be described as a safety-preserving backup".

**Both directions are asserted** in `tests/test_contact_export.py::ImportReadBackTests` and
`tests/test_contacts_store.py::ContactExportReadBackTests`: a file whose mark column says `yes` for every row
imports into a fresh database and marks **nobody**, and a file edited to say `no` for a marked contact imports
into the database that holds it and **unmarks nobody** (`suppressed`, `suppressed_at` and the note unchanged).
Re-importing the export into its own database adds nothing, updates both records and creates no disagreement —
`(added, updated, conflicts, skipped_without_key) == (0, 2, 0, 0)`.

**And the honest consequence, said plainly**: a person who moves their list to a new machine imports the contacts
and then has to re-apply the marks in the window that has always made them. Nothing acts on a mark yet in this
build — there is no matching, no draft and no sending — so the limitation is a gap rather than an active hazard,
and the whole-database backup is the path that carries the marks themselves. Both facts are in this note, in the
README and in the dialog.

## 4. Read-only, atomic, and refusing before it writes

- **Read-only.** The export calls the store's list method and a file write, and nothing else. `export_document`
  issues no statement that changes a row and records no event. Tests assert it against the **connection's own
  change counter** (`total_changes`), against the stored rows, marks, mark notes and dates, and against the
  conflict rows; one test closes the store and reopens it to check the same thing from a fresh process state.
- **One writer, one format.** `career_agent/contact_export.py` is the only code that writes this format, so the
  file cannot drift from the columns documented in the module that writes it. `importer.py` was not edited at
  all by this increment.
- **Bytes, not text.** `store.write_private_bytes_file` was added beside `write_private_text_file`, because the
  text writer translates `\n` to the platform's separator. It creates the file through the same
  `create_private_file` (mode applied through the descriptor *before* the first byte, `O_EXCL`/`O_TRUNC` as
  appropriate, `O_NOFOLLOW`, an explicit symlink refusal), and returns the path only after the mode has been
  verified.
- **Verified after writing, and nothing left behind on a failure.** The export reads the file back and compares
  it with the payload; a mismatch, an unreadable file or an unwritable one claims nothing, and the file is
  removed where removal is possible. A write that fails **part way** — the case no read-back can cover — is
  handled in the writer itself (section 7).
- **A symbolic link is refused by the writer**, not by the window: the window has no pre-check for a link, a
  database-adjacent path or anything else, so the refusal has exactly one owner, and a test proves that the link
  and its target are untouched.
- **Restrictive permissions where the platform has them**: `0o600` on POSIX, asserted on the export path; the
  same write path without the permission guarantee elsewhere, which is not claimed there.

## 5. Files and commits

| File | What changed |
| --- | --- |
| `career_agent/contact_export.py` | New (253 lines): the `hr-contact-export/1` contract, `spreadsheet_safe`, `export_row`, `export_document`, `write_export`, `MARK_COLUMN_LIMITATION`, and `ContactExport` / `ContactExportOutcome` / `ContactExportRefused`. |
| `career_agent/store.py` | `write_private_bytes_file` (+36) beside the text writer, and (in the fix commit) `_discard_after_failed_write` so a failed write leaves nothing behind. |
| `career_agent/__main__.py` | `--export-contacts-to PATH`, `run_export_contacts`, the dispatch branch, and the module docstring's paragraph about the two directions of the contact CSV. |
| `career_agent/desktop.py` | The heading, the control (`self.export_contacts_button`, so the window's own attribute can be found and driven) and the sentence (grid rows 22-24), plus `_export_contacts`. |
| `career_agent/event_log.py` | `contacts.exported` and `contacts.export.failed` declared, with the contact block's comment extended to what an event may carry. |
| `career_agent/diagnostics.py` | (fix commit) a third redaction pattern for a location continuing past a placeholder — **D36**. |
| `tests/test_contact_export.py` | New: 37 tests over the format, the values, privacy, read-only, file safety, the bounds, the import read-back, and the untouched version-2 JSON contract. |
| `tests/test_cli_export_contacts.py` | New: 11 tests over the command. |
| `tests/test_store.py` | `PrivateBytesWriteTests` (6 tests) and the writer in the import list. |
| `tests/test_contacts_store.py` | `ContactExportReadBackTests` (3 tests): the import into a second database, the mark column in both directions, no event and no row change. |
| `tests/test_desktop_handlers.py` | `ContactsExportHandlerTests` (10 tests), the control added to the layout-policy widget list, and a real-window assertion on the sentence the tab carries. |
| `tests/test_diagnostics.py` | (fix commit) `PathRedactionTests::test_a_path_that_follows_a_placeholder_is_still_hidden` — D36's regression test, both shapes. |
| `scripts/desktop_acceptance.py` | Workflow L gains **L16-L20**; `declared_step_count()` moves 97 → **102** by reading the source, so no number elsewhere had to be edited. |

Commits (branch `arena/351e052d-ai-career-agent`, PR #2 open and unmerged):

| Commit | What it is |
| --- | --- |
| `bdf443b` | `feat(contacts): export the stored HR contact list to a CSV a person chooses` — the implementation and the tests for it. Its CI run found D36 (section 7). |
| `546d065` | `fix(diagnostics): hide a location that continues past a redaction placeholder` — D36's fix, the partial-write fix, the independent JSON-version assertions, and the line-ending claim split in two. |
| (this note's commit) | Documentation: this note, the checklist's steps 112-117, the defect register's D36 entry, and the counts in `design.md`, `phases.md`, `README.md`, `task.md`, `memory.md`, the handoff and the research index. |

## 6. Commands, tests and counts

| Command | Result |
| --- | --- |
| `python3 -m unittest tests.test_contact_export` | `Ran 37 tests … OK` |
| `python3 -m unittest tests.test_cli_export_contacts` | `Ran 11 tests … OK` |
| `python3 -m unittest tests.test_store` | `Ran 193 tests … OK` (`PrivateBytesWriteTests`: 6) |
| `python3 -m unittest tests.test_contacts_store` | `Ran 55 tests … OK` (`ContactExportReadBackTests`: 3) |
| `python3 -m unittest tests.test_desktop_handlers` | `Ran 343 tests … OK` (`ContactsExportHandlerTests`: 10) |
| `python3 -m unittest tests.test_diagnostics` | `Ran 47 tests … OK` (`PathRedactionTests`: 12) |
| `python3 -m unittest discover -s tests` | `Ran 1950 tests … OK (skipped=13)` |
| `python3 -m compileall -q career_agent scripts tests` | clean |
| `python3 scripts/desktop_acceptance.py --stand-in-tk` | `102 checks passed, 0 failed`, `RESULT: BLOCKED` — a stand-in Tk is not a desktop, and the run says so |
| `scripts/desktop_acceptance.py`'s `declared_step_count()` | `102` (read from the source) |

**64 tests were added by the feature commit and 5 more by the fix commit** (`git show … -- tests/` counts 64 and
5 new `def test_` lines; the suite moves 1890 → 1945 → **1950**, and the counts above are the per-module totals
after the fix). Every one of them is green locally and on all thirteen CI jobs of run `38891340290`: the fix
commit's five are the D36 regression test, the partial-write test in the writer, the export module's
partial-write test (the two levels a fragment could have survived at) and the two version-2-contract tests.

**What the file-level tests hold.** The header row as **literal bytes** plus the byte-order mark, CRLF-only record
separators, and the exact number of newlines a value of the fixture contributes; one row per stored contact with
the address as stored (case and all) and the mark column read from the database in both states; a name holding a
comma, a quote, a line ending and non-ASCII text surviving the round trip byte for byte; an empty list writing
the header and reading back as zero rows; one row per key however many times it was imported; the two limits
refusing before a path exists; a 2,000-row list written and read back; the four formula leaders prefixed and
ordinary values untouched; a contact with no name or company writing empty cells; the privacy sweep (no mark note,
no disagreement value, no source file name, no internal column name anywhere in the file, and no activity-log
line from the module itself); and the version-2 JSON contract pinned to the literal **2**, to a document with no
contact key, and to the document being byte-identical before and after a contact export.

**What the file-safety tests hold.** Owner-only mode on POSIX, and an existing file with wider permissions
tightened rather than trusted; a symbolic link refused with its target untouched; a missing folder refused with
nothing created; an injected short read, an injected mid-write failure and a refusal to apply the mode all
reporting failure instead of success and leaving no fragment behind; and the same checks through the command,
which additionally refuses an existing path, a 0-byte database, a file that is not a database and a database that
does not exist.

**What the desktop tests hold.** The real handler with the stubbed save dialog: the documented header, the
byte-order mark, the mark column as the database holds it, the counts in the status line and in
`contacts.exported`, `total_changes` unchanged, the completion report's counts and its limitation sentence with
**no path** in it, an empty list still writing the documented file and saying it is empty, a closed dialog writing
nothing and saying nothing, a declined overwrite leaving the person's file byte-identical, a confirmed one
replacing it, an unwritable folder reported as a refusal rather than a success, a list over the format's limit
refused through the **real** module constant (patched to 100 bytes, not mocked at the handler), an injected
`sqlite3.OperationalError` claiming nothing, an unreadable stored record reported through the shared explanation,
and owner-only mode. The layout-policy test carries the new control in its list of widgets that must sit inside a
scrolling body, and the sentence the tab carries is asserted on the **real** window rather than on a double.

## 6a. The mutation checks: 20 defects removed, 20 caught

A test that passes with *and* without the behaviour it names is not evidence, so each claim about the tests was
checked by removing the behaviour and requiring the named tests to fail. Three properties make the verdicts
worth quoting, and the first two are corrections of an earlier version of this harness:

1. **The checkout is never modified.** An earlier run mutated the working tree and restored from a backup taken
   the first time it ran; a reused backup then restored an *older* revision over a newer edit, which silently
   undid a change — the tests correctly reported the resulting failure, but the harness had caused it. Every
   mutation now runs in a temporary copy of the worktree, removed in a `finally`, with the copy verified byte for
   byte against the checkout afterwards ("copy differs from the checkout after restores: nothing") and the
   focused tests verified green on the unmutated copy **first**, so a failure can be attributed to the mutation.
2. **The expectation is fixed, not read from the code under test.** "These named tests must fail" is decided
   before anything is mutated, each mutation is verified to have actually changed the file and to still compile,
   and the failing test must be in the module the entry names — so a mutation that matched nothing, broke the
   import, or caused a cascade somewhere else is reported `INVALID` rather than counted as a catch.
3. **The failing test is named**, which is the evidence; the list below is what the run printed.

| Mutation (the smallest edit that removes the behaviour) | Verdict |
| --- | --- |
| The formula guard removed from `export_row` | CAUGHT — `ValueEncodingTests` |
| `spreadsheet_safe` reduced to returning its input | CAUGHT — `ValueEncodingTests` |
| The read-back comparison removed (`if False`) | CAUGHT — `FileSafetyTests` |
| The byte-order mark dropped | CAUGHT — 2 tests in `FormatContractTests` |
| The line terminator changed to `\n` | CAUGHT — 3 tests |
| The format version cell no longer names the format | CAUGHT — 4 tests |
| The mark column written as a constant | CAUGHT — 2 tests |
| The mark's own note written beside the mark | CAUGHT — 3 tests |
| The row limit removed | CAUGHT — `BoundedListTests` |
| The byte limit removed | CAUGHT — `BoundedListTests` |
| `MARK_COLUMN_LIMITATION` weakened to "Read the column to see which contacts were marked." | CAUGHT — the module, command and handler tests |
| The partial-write discard removed | CAUGHT — `PrivateBytesWriteTests`/`FileSafetyTests` |
| The D36 redaction pattern removed | CAUGHT — 2 tests in `PathRedactionTests` |
| The window claiming success for a file that could not be written | CAUGHT — `ContactsExportHandlerTests` |
| The overwrite question skipped | CAUGHT — `ContactsExportHandlerTests` |
| The completion report naming the chosen path | CAUGHT — `ContactsExportHandlerTests` |
| The event carrying the chosen path instead of counts | CAUGHT — `ContactsExportHandlerTests` |
| The command no longer refusing an existing path | CAUGHT — `ExportContactsCommandTests` |
| The command reporting an export it did not write | CAUGHT — `ExportContactsCommandTests` |
| The JSON export contract moved past version 2 | CAUGHT — `TheJsonExportIsUntouchedTests` |

**One mutation found a test defect, not a behaviour defect, and it is the reason two kinds of assertion now
exist.** Replacing `MARK_COLUMN_LIMITATION` with a one-sentence version that says nothing useful passed every
test in the first draft, because those tests asserted that each screen carried *the module's own sentence* — an
identity, not a claim. Three tests now also assert the claim's substance (`"Do Not Contact"` named, `cannot set
or clear` an import, `read the column` as what to do instead) in the module's test class, in the command's report
and in the window's note, and that mutation is now caught. No shipped behaviour was wrong, so this is recorded as
a test defect rather than a numbered one.

## 7. The two defects the verification found (D36, and the partial write)

Neither was found by reading the code. Both are in `research/cross-platform-desktop-ci-evidence-2026-10-15.md`
(section 26) and both have regression tests that fail without the fix.

**D36 — a location that continued past a redaction placeholder (found by the Windows legs of run `38883986337`).**
That run was 11/13: both Windows legs failed the new `L20` check with
`SmokeFailure: the path the person chose reached the activity log`, while Linux and macOS passed it and every
other job was green. The check reads the activity log after a refused export, and the log is written to be safe
to share: `diagnostics.redact_paths` hides declared paths and then any remaining absolute location, so a path
that appears only inside an exception's message is still hidden. On the Windows runners the run's temporary
folder sits under the *parent* of `Path.home()` (`C:\Users\RUNNER~1\AppData\Local\Temp\...`), so the home-folder
replacement shortened the message to `<home folder>\RUNNER~1\AppData\Local\Temp\<run folder>\no-such-folder` —
and the sweep could not match what followed, because both of its patterns carry a guard that refuses to match
after the `>` that every placeholder ends with, and its Windows branch needs a drive letter or a share prefix,
neither of which survives the replacement. POSIX never showed it: `/tmp/...` is not under the home folder's
parent, so nothing was left over to hide.

The fix is a third pattern rather than a wider guard — a location continuing past a placeholder into **two or
more** further segments, while one trailing segment stays visible because that shape is
`<application data folder>/career_agent.sqlite3`, the product's own file name. Widening the shared guard was
written and measured first precisely because it is the obvious fix, and it broke
`test_the_database_location_is_replaced_without_leaking_its_folder` — which is how the two-segment rule was
arrived at. The regression test covers both shapes, and while writing it the POSIX half turned out to fail on
the shipped code too (a path under the home folder's *parent*: `/home/other/matter-notes/...` kept its folder
name on Linux), so the defect was **not** Windows-only in principle — Windows was simply where a real log line
ran into it.

**The partial write (found while verifying the check's own claims).** `write_private_bytes_file` promised "the
bytes it was given, or nothing", but a write that failed part way — a full device, a quota, an I/O error — left
the fragment it had already written at the destination: the reproduction left ten bytes of byte-order mark and
header at the person's chosen path while the error said the export was not completed. A file that looks like an
export and is not is worse than no file, so the writer now removes what it started and says in the message
whether the removal succeeded. `tests/test_store.py::PrivateBytesWriteTests` and the export module's
`FileSafetyTests` both fail without it (verified by mutation), and the message the window shows —
"Nothing was saved; the database was not changed." — is now literally true of the disk as well as the database.

## 8. The acceptance workflow: L16-L20

Five checks were **added inside workflow L** rather than making a thirteenth workflow, so the CI unit job's loop
over workflow letters is unchanged (`declared_step_count()` moves 97 → 102 by reading the source). All five run
on every display-backed leg; what follows is the Linux display job's report, and the Windows and macOS legs
report all five `[ ok ]` too.

- **L16** — finds the control by its own text in the tab's scrolling body, requires it **not** disabled, and reads
  the sentence from the window: it must carry the format module's `MARK_COLUMN_LIMITATION` and the four things a
  person needs before they rely on the file ("one CSV row per stored contact", "not a backup", "replaced",
  "Nothing is sent anywhere").
- **L17** — with two stored contacts (one of them marked), closes the save dialog: the folder must be exactly as
  it was, **no dialog** may have been shown, `total_changes` must be unchanged, the status line must not claim an
  export, and the activity log must be **byte-identical**.
- **L18** — names a destination and presses the control: the report must appear and must not contain the path, the
  file must be there with the byte-order mark, CRLF-only record separators and the documented five-column header,
  one row per stored contact with the mark column matching the database, every row carrying
  `hr-contact-export/1`, the file must be **read back through the application's own parser** to the same
  addresses, `total_changes` and every stored row and conflict must be unchanged, the status line must carry the
  counts and *Nothing was contacted*, and the log must carry `detail=contacts=2 marked=1`.
- **L19** — sweeps what the file and the report may not contain: the reason stored beside a mark, the other side of
  a recorded disagreement, the source file's name, and the internal column names (`Source Rows`, `Review Reason`,
  `contact_id`, `seen_count`, `suppressed_note`); exactly five columns; and none of the fixture's contact values,
  nor the exported file's own name, in the report or the log.
- **L20** — points the control at a folder that does not exist: the refusal must be reported as a failure, nothing
  may be created, the database must not change, the status line must not claim an export, and the log must carry
  `contacts.export.failed` **without either the chosen folder's name or the whole path** — the assertion that
  found D36.

## 9. CI evidence

| Run | Commit | What the legs reported |
| --- | --- | --- |
| `38883986337` | `bdf443b` | **11/13 — failed.** Both Windows legs failed `L20` with `the path the person chose reached the activity log`, which is **D36**. Linux display job `116917171547` reported `RESULT: PASS — 102 checks passed` with L16-L20 `[ ok ]`; both macOS legs and the unit, installed-package and PDF-extra jobs were green, `Ran 1945 tests … OK`. |
| `38891340290` | `546d065` | **13/13 jobs green** with the fix. Linux display job `116941315130`: `RESULT: PASS — 102 checks passed` (L16-L20 `[ ok ]` beside L1-L15) and `RESULT: PASS — 14 checks passed` from the smoke entry point. macOS 26 legs `116941315236` (3.10) and `116941315378` (3.13): `Ran 1950 tests … OK (skipped=20 / 13)` and `RESULT: PASS — 102 checks passed`. Windows 2025 legs `116941315386` (3.10) and `116941315319` (3.13): `Ran 1950 tests in 678.9 s / 568.8 s … OK (skipped=52 / 45)` and `RESULT: PASS — 102 checks passed`. Unit legs 3.10-3.14, installed-package legs (3.10, 3.14) and the optional-PDF-extra leg all green. |

The first run is kept in the record rather than replaced by the green one: it is the only evidence that the D36
check is capable of failing, and the run that closed the defect says so in the register. **`D36` is closed**;
`D35` and everything before it stay as they were.

## 10. Manual status: what a human still has to do

Steps **112-117** of `research/local-alpha-manual-smoke-test-checklist-2026-10-14.md` are new and all six are
**BLOCKED**: no display with Tkinter, no spreadsheet, no screen reader and no keyboard exists in this
environment, and a stand-in widget module is not a desktop. They ask for the things no harness can judge — where
the export sits on the tab and whether its sentence reads clearly, whether the save dialog is reachable and
answerable by keyboard and mouse at the window's own minimum size, whether the file opens where a person expects
to open it, what their spreadsheet does with the apostrophe the format writes, whether non-ASCII names look right
in their tools rather than like mojibake, and whether the sentence about the mark column is understood as the
limitation it is. Every one carries an "Automated coverage" line naming the checks that exist, so a tester does
not redo what the harness established. The checklist's head count moves 111 → **117** steps, 22 PASS /
**95 BLOCKED** / 0 FAIL, and **no box was ticked**.

## 11. What this deliberately does not do

- **No change to the JSON export.** `EXPORT_FORMAT_VERSION` is still `2`, `importer.py` was not edited, the
  contact tables are still **not** in that document, and a test pins the number to the literal 2.
- **No import path for the mark.** The column is text to read, as section 3 records; a person re-applies the
  marks in the window, and no file can set or clear one.
- **No row-level selection export**, no "export only the rows I chose", no per-contact or per-file JSON, vCard or
  XLSX format.
- **No schema change** (still 7), no migration, no new table, no tombstone.
- **No change to `--forget-local-data`, backup or restore semantics**, and no change to the parser
  (`career_agent/contacts.py` is untouched by this increment).
- **No external action of any kind.** Nothing here opens a socket, nothing sends, and the gate stays closed:
  `SOURCE_QUALITY_GATE_PASSED is False`, `enabled_discovery_sources() == ()`.
- **No claim that the export is a backup.** The sentence beside the control, the completion dialog, the command
  line and this note all say the opposite, in the format module's own words.
