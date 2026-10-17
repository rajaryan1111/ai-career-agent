# JSON import: reconcile state for an already-stored listing

Date: 2026-10-17 · Scope: local JSON v2 import, no schema change, no external action.

## Finding

The importer already linked an incoming listing to a local listing by its canonical duplicate key and
deliberately preserved the local listing payload and timestamps. Before this increment, it stopped there:
when the local listing had no tracker, follow-up or activity history, the file's application state was silently
dropped. That contradicted the export/import contract, which says the application record, follow-up plan and
activity history travel with the file.

## Invariant and implementation

For a linked listing:

- the local `listing_id`, payload and record timestamps are never replaced;
- missing tracker state is created at the required initial `discovered` status, never at a later status the
  importing file claims;
- an existing local tracker, status, evidence and confirmation state are preserved;
- a missing follow-up is added; an identical one is idempotent, while a different local follow-up is refused
  in the plan and kept unchanged;
- activity is appended only when `(occurred_on, kind, detail)` is not already present; repeated entries in
  the incoming file and repeated imports do not duplicate it; and
- state is attached to the local listing identity, even when the file used a different listing identifier.

The plan now describes these linked-state writes, so a person sees them before confirming an import. The
application state is reconciled through the existing store methods; no SQL or new schema was added, and the
external-action gates remain closed.

## Verification

Synthetic importer tests cover a linked listing with missing tracker/follow-up/activity state, repeat-import
idempotency, preservation of a local tracker and conflicting follow-up, and a local listing identifier that
differs from the file's identifier. The focused importer/store/export-import subset ran **251 tests, OK**;
the full local suite ran **2079 tests, OK (skipped=1)**; compilation and `tabnanny` were clean.

The related resume-import audit item was subsequently closed by
[the write-verification note](resume-import-write-verification-2026-10-17.md): a committed but unverified write
is no longer reported as nothing saved. No live discovery, email, application submission or candidate-data
transfer was enabled.
