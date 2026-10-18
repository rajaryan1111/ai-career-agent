# The job a document was written for is part of its lineage — schema 16, 2026-10-18

The audit earlier today wrote down one limitation and called it the highest-priority next task:

> `lineage_status` does not notice a listing edited *after* a document is stored — the artifact
> record keeps `listing_id` but not the listing fields it was built from, so detecting that needs a
> new column and a migration (schema is at 15). A stale-by-listing cover letter therefore still
> reads as "Current".

This is that migration, and the lineage change that uses it.

## The shape of the hole

An artifact row has always been able to answer "which facts?", "which strategy version?" and "which
résumé did those facts come from?". It could name its listing — `listing_id`, with a foreign key —
but a listing is an editable record, and "which listing" is not the same question as "what did that
listing say when this letter was addressed to it".

So: build a cover letter for *Example Employer / GenAI Engineer*, then edit the listing because the
employer rebranded. The letter in the database still opens "Dear Example Employer", the row still
reads **Current**, the export button is still enabled, and the file that lands on disk carries a
provenance header saying it was built from stored facts — all true, and all beside the point. The
one thing the lineage exists to prevent is exactly what happens.

Two approaches were rejected before the column was written:

- **Rebuild and compare.** Regenerate the document and call it stale if the text differs. This marks
  stale every artifact whose content was written directly rather than generated — dozens of fixtures
  in the suite, and any document a future build renders differently — so it reports churn, not
  truth.
- **Compare the whole listing record.** A `JobListing` has twenty-two fields. A document reads three
  of them. Treating an edited source URL or an availability flag as drift produces a refusal nobody
  can act on, and teaches people to ignore the state column.

## What was built

**Schema 16** — one nullable column, `tailored_artifact.listing_fingerprint`, added with
`ALTER TABLE ... ADD COLUMN` inside the existing `_MIGRATIONS` table (step 16, appended, never
reordered). No second migration mechanism, no table rewrite, no existing row touched.

`career_agent.artifacts.ListingFingerprint` is what goes in it: `employer`, `role_title`,
`required_skills` (sorted, de-duplicated — the listing stores a set, and a set has no order to
preserve), plus a `digest`: sha256 over the canonical JSON of those three values, using the same
canonicalisation the integration layer's `_operation_id` already uses (`sort_keys=True`,
`ensure_ascii=False`, `separators=(",", ":")`).

Why three values and not more: those are the three a generated document consumes — the employer it
is addressed to, the role it names, and the skills the screen reported as missing. Why a digest
beside the values and not instead of them: a drift has to be *explained* ("the employer is now
'Renamed Corp', not 'Example Employer'"), which needs the old values; and a record meant as evidence
has to be *checkable*, which needs the digest. A row whose stored values no longer match their own
digest is refused by `from_json` as damage rather than believed.

Nothing of the candidate is in the fingerprint. An employer's name, a role title and a job's skill
list are the employer's own words, already in `job_listings`; the résumé text and the facts stay in
the basis, which is what the basis is for. A test asserts the stored JSON holds exactly four keys
and contains neither a candidate fact nor the source document's name.

**One comparison, two callers.** `_listing_changes` — the build-time check that refuses to store a
document when the listing moved between the preview and the confirmation — is now
`ListingFingerprint.changes_against`, which is also what `lineage_status` calls. The rule about what
counts as a change cannot drift between the two because there is only one of it.

**Three states, not two.** `LineageReport` gained `listing_changes`, `listing_recorded`,
`listing_missing` and the derived `listing_verifiable`:

| The row | What it says |
|---|---|
| fingerprint matches the listing now | `Current` |
| fingerprint differs | `Rebuild before use — the listing this was written for changed: the employer is now 'X', not 'Y'` |
| no fingerprint (stored before schema 16) | `Cannot be checked — this document was stored before the listing it was written for was recorded with it…` |
| the listing is gone | `Cannot be checked — the listing this was written for is no longer stored` |

The third row is the one that matters most for honesty. **Existing artifacts get `NULL`**, and the
migration deliberately does not back-fill from the listing as it stands today: that would declare
every old document "written for exactly this listing", which is precisely the false reassurance
being removed. `is_current` is false for all three non-current states, so `require_current_artifact`
refuses them and no stale or unverifiable document can be exported.

**The window says it in words.** `artifact_state_text(..., verifiable=False)` produces
"Cannot be checked — …" rather than "Rebuild before use — …"; the summary counts those documents
separately ("1 of those was stored before the listing was recorded with the document"); the export
refusal is titled *This document cannot be checked* and explains that nobody can tell whether it
still matches, rather than asserting it is out of date. No state is communicated by colour: the tab
has none, and all three readings are sentences in the row's own state cell.

## A migration fault found on the way

`tests/test_route_evidence.py` creates a file with `PRAGMA user_version = 14` and **no tables**, then
opens it. The runner skips steps 1–14 because the file says they ran, so step 16's `ALTER TABLE
tailored_artifact` hit a table that was never created — and a failing step leaves a database that
cannot be opened at all. Step 4 (the follow-up columns) had the same latent hole since schema 4; it
had simply never been hit.

Both now call `_holds_table(connection, name)` first and do nothing when the table is absent: a
column step's job is to add a column to a table that exists, and standing in for the step that was
skipped would hide the inconsistency instead of leaving it visible to
`backup.validate_app_database`. Pinned by
`test_the_listing_step_does_not_break_a_file_whose_version_runs_ahead_of_its_tables`.

## Evidence

- **Migration**: an upgraded v15 file keeps its artifact row byte-for-byte and gains `NULL`
  (`test_the_listing_step_adds_its_column_and_leaves_every_stored_document_alone`); the step run
  twice adds one column and duplicates nothing
  (`test_running_the_listing_step_again_changes_nothing`); a fresh database records 16 with the
  column; a version-ahead-of-its-tables file still opens.
- **Lifecycle** (`ListingLineageTests`, 16 tests): store → current; employer, role title and
  required skills each independently → stale, named; URL, availability and provenance note → no
  drift; stale → not exportable; rebuild → current, addressed to the employer as it stands, old row
  unchanged and still stale; legacy row → never current, not exportable, and a rebuild of it does
  not back-fill the original; a listing that is gone → reported gone; a hand-edited fingerprint →
  `StoredRecordError`; a document filed under a listing it was not written for → refused by the
  store.
- **Window** (`TailoredDocumentsTabTests`, 5 new): drift row text, legacy row text, export button
  disabled, both refusal dialogs, rebuild writing the current listing.
- **Acceptance**: `scripts/desktop_acceptance.py --stand-in-tk` → **158 checks, 0 failed**, with
  M14/M15/M16 covering drift, rebuild and the unverifiable row. The exit verdict is still
  `RESULT: BLOCKED`: a stand-in Tk is not a desktop, and nothing here is GUI acceptance.
- **Suite**: 2733 tests, 0 failures, 0 errors, 13 skipped (12 × "the optional pypdf package is not
  installed", 1 × "ai-career-agent is not installed in this interpreter (source checkout)").

## What this does not do

It does not make an old document trustworthy — it makes the fact that nobody can check it visible,
and offers the rebuild that fixes it. It does not compare anything a document does not read, so a
listing edited in ways that cannot change what was written stays current on purpose. And it says
nothing about whether the employer's *real* advert changed: this is the record as stored on this
machine, and the app still fetches nothing.
