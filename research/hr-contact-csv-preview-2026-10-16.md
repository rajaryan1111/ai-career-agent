# HR contact CSV preview — Phase 0, offline only (2026-10-16)

**What was asked.** `planning/arena-task-phase-0-hr-contact-csv-import-2026-10-16.md`: add an offline,
local-first HR-contact CSV import review flow that can read the user's private CSV without copying it into
this repository, where a user can preview validated rows and review flags and cancel without anything being
written - and, if persistence or UI integration could not be done safely in one increment, ship only a
tested, clearly scoped parser and preview contract and document the remaining integration rather than
faking a completed workflow.

**What was done: the second of those two.** The parser and the preview contract exist, are tested, and are
reachable from the command line; persistence and the review screen deliberately do not exist yet, and every
document says so. There is no half-built import path: the feature cannot write anything, because it has no
code that writes.

## What exists

`career_agent/contacts.py` (new, ~600 lines with its design notes) reads one file and reports on it:

| Step | Behaviour |
| --- | --- |
| Path | A missing path, a folder, a non-regular file and a 0-byte file are each refused by name. |
| Size | Bounded at 20 MB, checked before and during the read (`_read_bounded`); a file that grows past the limit is refused, never truncated. |
| Rows | Bounded at 50,000; over the limit is a refusal, not a partial report. |
| Encoding | Decoded as UTF-8 with the BOM removed (`utf-8-sig`). A UTF-16 mark is named as UTF-16 - a spreadsheet export is the likely cause and "not UTF-8" alone would not say what to change. Any other invalid byte is refused with its offset. |
| Header | A blank column name and two names differing only in case or spacing are refused; the names are printed so the person can see what the file has. |
| Columns | `Email`, `Email Address`, `E-Mail`, `Mail`, `Contact Email`, `Work Email`, `Email Key`, `Email Id`, `Normalised/Normalized Email`, the name spellings, the company spellings, the source-row spellings and the review-reason spellings are matched; every other header is listed as not used. |
| Ambiguity | Two columns for the email field is a refusal naming both, never a choice. `--contact-email-column` (and the name/company equivalents) pins one. |
| Rows of unequal length | A record with more fields than the header is refused with its line number; a short record is read with empty trailing cells, which is what a spreadsheet writes for a blank row end. |
| Values | Every cell is preserved exactly as the file wrote it. Only the email is normalised, and only by trimming and case-folding, to make the comparison key. |
| Groups | Rows sharing a key are one group; the group keeps every distinct non-empty company label in first-seen order. |
| Flags | `email-missing`, `email-syntax`, `name-missing`, `duplicate-key`, `company-conflict` - each on the row it applies to. |
| Report | Counts, flag tallies, and line numbers. No cell value, ever. |

`--preview-contact-csv PATH` is the command. It opens **no database** (it is dispatched before any database
work and ignores `--database`), writes no file, reaches no network, prints the report to standard output and
exits 0. A refusal is one sentence on standard error with exit status 2 and **nothing at all on standard
output**, which is the rule this project established for every other command (D31, section 21 of
`research/cross-platform-desktop-ci-evidence-2026-10-15.md`).

## What it deliberately does not do

Import into the database; a table, a migration or a store method for contacts; the review screen in the
window; row-by-row selection; exporting rejected rows; suppression/do-not-contact records; matching contacts
to listings; drafts; sending, submitting or contacting anybody. The last group is also gated externally
(`SOURCE_QUALITY_GATE_PASSED = False`, `enabled_discovery_sources() == ()`, both unchanged by this work).

Two reasons the split is the right one, rather than a shortcut:

* **UI integration here is not a small change.** A review screen means a new notebook tab, handlers, a
  scrollable body, keyboard paths and additions to the desktop acceptance harness - and it can only be
  judged on a real display, which this machine does not have; the display-backed CI legs are the only
  evidence, so it belongs in an increment that can be measured there.
* **Persistence is where privacy mistakes get made.** A contacts table is a store of third-party personal
  data with a retention question, a suppression rule that must survive re-import, and a duplicate key that
  must not be normalised differently from the key in this module. Freezing the contract first - what "the
  same contact" means, what is refused, what is never printed - is what keeps the store honest.

## Evidence

Local, this machine (Linux, CPython 3.11.2), from the repository root, on branch
`arena/351e052d-ai-career-agent`:

| Command | Result |
| --- | --- |
| `python3 -m unittest tests.test_contacts` | `Ran 48 tests ... OK` - 48 tests in 6 classes |
| `python3 -m unittest discover -s tests` | `Ran 1775 tests ... OK (skipped=13)` (1727 before this increment) |
| `python3 -m compileall -q career_agent/contacts.py career_agent/__main__.py` | clean |
| `python3 -m career_agent --preview-contact-csv <synthetic file>` | exit 0; counts, flags and line numbers; **no fixture value present in stdout or stderr** (checked with `grep` over both streams) |
| `python3 -m career_agent --database <a text file named .sqlite3> --preview-contact-csv <file>` | exit 0 - proof by construction that no database is opened |
| `python3 -m career_agent --preview-contact-csv <a UTF-16 file>` | exit 2, `REFUSED: ... looks like UTF-16 text ... Nothing was changed.` on stderr, **0 bytes on stdout** |
| `python3 -m career_agent --contact-email-column Email` (without the command) | exit 2, `REFUSED: --contact-email-column only means something with --preview-contact-csv.`, 0 bytes on stdout |
| `python3 -m career_agent --preview-contact-csv <a file whose cell exceeds csv's field limit>` | exit 2, `REFUSED: ... is not well-formed CSV: the parser could not read line 1 (field larger than field limit (131072)) ...` |

What the tests establish, and how: the source file's bytes, `st_mtime_ns` and its folder listing are
compared before and after a read and after refusals; every synthetic address, name and company in the
fixture set is asserted absent from the report, from a refusal message and from a captured root-logger
handler (which must stay empty: reading a contact file writes no log record at all); ambiguous columns are
asserted to refuse rather than pick; the source strings are asserted unchanged while the key is asserted
normalised; and the counts are asserted to add up to the rows read.

**Fixtures are synthetic.** Every address is on a reserved `.invalid` domain and every name is
`Example Person ...`; the audit's aggregate numbers in `research/hr-contact-list-audit-2026-10-15.md` are
the only thing in this repository that describes the real list, and they contain no contact data. No real
CSV, row, name or address was read, copied, committed, logged or printed by this work.

## What is not established

* **The real exports' headers have not been seen.** The column spellings above are a documented contract,
  not a confirmed match for the private files, which are (correctly) not in this repository. The first real
  run of the command against the user's own file is what confirms them, and until then the preview reports
  its mapping for exactly that reason. If the deduplicated export and the review queue have different
  column sets, each is read on its own and the report says which columns each one used.
* **Nothing about the real data is verified** - not the row count, not the duplicate groups, not the flags.
  The audit's numbers came from a different procedure (a pasted export, cleaned outside this application);
  they are a cross-check to make later, not evidence that this parser agrees with it.
* **"Re-import creates no duplicates" is not yet a testable claim**, because there is no import: the module
  computes the key a store must use and reads the same file to an equal result twice, which is all that can
  be shown while nothing is stored.
* **No manual or GUI acceptance.** No window was opened, and this feature has no window presence yet.

## Next smallest step

1. A store migration (schema version 7) holding only what a review needs - the key, the preserved strings,
   a provenance/source reference, the flags, and a `suppressed`/`do_not_contact` state that survives
   re-import - written through the existing migration and backup-before-upgrade rules, with the key taken
   from `contacts.normalise_email_key` so the two cannot drift.
2. The review screen as a new tab built on `_scrollable_body`, with a cancel that writes nothing, plus its
   steps in the desktop acceptance harness so the display-backed CI legs measure it.
3. Only after those: matching to listings (Phase 1 of the planning document), which is where the source gate
   starts to matter.
