# Tailored artifacts and lineage (2026-10-18)

## What this increment is

The second half of P7's storage layer: a **tailored artifact** is a document prepared for one listing
under one role-strategy version, stored beside the exact basis it was built from. Schema **10** adds
`tailored_artifact(artifact_id, listing_id → job_listings ON DELETE CASCADE, strategy_id,
strategy_version, artifact_kind, content, fact_basis, created_at)`; `career_agent/artifacts.py` owns
what the content may claim and what the lineage says. Matching/eligibility consumption, a window or
CLI for artifacts, and application-time attachment selection are deliberately **not** here.

## The rules the artifact layer holds

* **Builders only restate stored facts.** The résumé builder arranges stated skills (strategy-relevant
  first), work history and education; the cover letter names the listing's employer and role and
  states only stated skills/experience/history. A required skill the profile does not state becomes a
  **gap** in the build result — reported to the person, never written into the document, never
  hidden. No name or contact section exists because the profile has no such fact to draw from, and
  inventing one is the exact failure this layer exists to prevent.
* **The basis is the checkable lineage.** `capture_basis` snapshots the rendered profile facts, which
  of them were unconfirmed, and the work/education records — **without row bookkeeping**
  (`entry_id`/`created_at`/`updated_at`): a row number is not a fact, and a delete-and-retype of the
  same record must not read as a changed history. `lineage_status` compares the stored basis with
  what the store holds now and reports, by name: facts changed, facts *confirmed since* (a
  confirmation changes no value but the document was built while the fact was unconfirmed — worth
  saying), work changed, education changed, and whether a newer strategy version exists.
  `is_current` is true only when nothing moved.
* **Rows are append-only and their lineage resolves at write time.** `save_tailored_artifact` refuses
  an artifact whose listing is not stored or whose strategy version is not stored — a document that
  cannot explain itself is not evidence — and refuses a duplicate identifier instead of upserting.
  Deleting a strategy that artifacts still reference is **refused** (delete the artifacts first), so
  the lineage chain is never broken by a cascade; deleting a listing cascades its artifacts, the same
  per-listing rule every table in this schema declares.
* **Privacy: events and exports carry no artifact content.** `artifact.saved`/`artifact.deleted`
  carry the generated identifier, the kind and the strategy version; the person's writing, the
  listing's employer/role and every fact value are asserted absent from the log. The JSON export
  stays at version 2 and carries no strategies, no artifacts, no basis — the whole-database backup is
  what copies them (asserted across a backup → delete → restore cycle, and for restarts).
* **Damaged rows are reported as themselves** through the doctor's decoder, like every other table.

## Defects found and fixed while building this

* **Resume/letter repetition:** "Other skills" originally repeated the strategy-relevant skills (a
  case-folded set difference let a skill appear twice). Fixed to a case-insensitive subtraction, with
  a regression test.
* **Basis round-trip inequality:** captured history records carried row identifiers, so a saved
  artifact never equaled its own read-back. Fixed by normalizing at capture (facts, not row numbers),
  with the round-trip test asserting dates and enums come back as records.
* **Same-second ordering:** artifacts written within the same second now tie-break by insertion
  order (`rowid`), so "newest first" is total.

## Tests and evidence

`tests/test_artifacts.py` — 30 tests: basis validation and round-trip, builders' no-invention and
gap reporting (including case-insensitivity and silence-about-experience), capture without a profile,
store refusals (no listing, no strategy version, duplicate id), append-only reads, filters and
ordering, delete, restart/backup/restore, listing cascade, doctor reporting, and the privacy pins.
`tests/test_store.py` — the v9→v10 migration on a full database, step re-runnability, and the
strategy-deletion refusal. `tests/test_strategies.py` — the export pin extended to artifacts.
`SCHEMA_VERSION == 10` re-pinned in both pinning tests.

* Focused: artifacts+strategies+store+tasks+importer+resume+backup+event_log+provenance — **605 tests OK**.
* Full local suite: **2151 tests OK (skipped=13)**. `compileall` clean; `git diff --check` clean.
* Desktop smoke test: **BLOCKED by construction** here (no tkinter in this sandbox; nothing verified
  about a window, as its own output states).
* No external action; `SOURCE_QUALITY_GATE_PASSED` stays `False`, `enabled_discovery_sources()` stays
  `()`; export format stays **2**.

## Follow-up the same day: the use gate

`artifacts.require_current_artifact(store, artifact_id)` is the enforcement point of the rule above:
it returns the artifact only while `lineage_status` is current, and raises `StaleArtifactError`
(carrying the structured `LineageReport` and a message that names what moved) otherwise. A missing
identifier is refused as missing. The gate refuses *use*, not history — the row still reads back —
so any future caller (a window, a submission route) has one canonical place to ask before an
artifact is attached, sent or built on. 5 tests in `RequireCurrentArtifactTests`; suite **2175 OK
(skipped=13)**.
