# Versioned role strategies — model and append-only store (2026-10-18)

## What this increment is

The first half of P7: a role strategy is the person's own, versioned statement of intent about the
roles they are pursuing — role family, title synonyms, seniority, locations, work modes, employment
types, compensation bounds with a currency, hard required skills, exclusions (role titles, employers)
and ranking preferences (preferred skills). This increment delivers the domain model
(`career_agent/strategies.py`), the append-only persistence (`schema 9`, one new table), backup/restore
and doctor coverage, and the privacy/event contract. It deliberately does **not** yet wire strategies
into matching, eligibility, artifacts or any UI — those are the next increments, and none of them can
be built until versions mean something, which is what this one establishes.

## The rules the model holds

* **Industry-agnostic by construction.** Every field is free text the person supplies; there is no
  recognised vocabulary of industries, and AI/ML, backend, data and the rest are examples a person
  might type, never a list the code knows.
* **Not a second candidate profile.** Facts about the person stay in `CandidateProfile` with their
  provenance (schema 8's contract). A strategy only says what to do with those facts.
* **Versions are append-only.** One row per `(strategy_id, version)`; `revise_role_strategy` writes a
  new row and never updates an old one. A revision whose content matches the current version
  byte-for-byte writes no row and returns the stored version — a version that changed nothing would
  be a claim that something did. `content_key()` renders content alone (identity excluded, sets
  sorted), so "the same statement" is recognised across identifiers and orderings.
* **Unknown means unknown.** Everything but name and role family is optional; an absent list is
  "nothing stated", not a preference for nothing.
* **Compensation is recorded, not compared.** `JobListing` has no compensation field, so bounds are
  the person's statement, not an eligibility check this build can run; the model refuses an amount
  without a currency, a negative/NaN/Infinite/boolean amount, and an inverted range.
* **The same numeric boundary as the import.** Booleans and non-finite values are refused at the
  constructor, the same values the JSON boundary refuses (see the number-boundary note above).
* **Events carry identity, never content.** `strategy.created` / `strategy.revised` /
  `strategy.deleted` carry the generated identifier and version numbers; the name, places and
  excluded employers are the person's data and are asserted absent from the log.
* **The JSON export stays at version 2.** Strategies are configuration, not candidate facts: the
  whole-database backup carries them (asserted across a backup → delete → restore cycle). A future
  format version that adds them is a deliberate decision, and the test that pins the export shape is
  where it has to be argued for.

## Store integration

Schema **9** adds `role_strategy_version(strategy_id, version, payload, created_at)` through the
existing one-step-at-a-time runner: additive, `IF NOT EXISTS`, re-runnable after an interruption, and
rollback-safe like every earlier step. The payload holds content only (identity is columns), read
back through `strategy_from_payload`, which refuses damaged rows as `StrategyError` →
`StoredRecordError` rather than crashing a table read. The doctor (`unreadable_stored_records`) reads
the new table through the same decoder the read paths use. New store API: `create_role_strategy`,
`revise_role_strategy`, `get_role_strategy(id, version=None)`, `list_role_strategies()` (newest
version of each, name order), `role_strategy_versions(id)`, `delete_role_strategy(id)` (whole-history
deletion in one transaction, 0 and no event when nothing is stored).

## Tests and evidence

`tests/test_strategies.py` — 27 tests over the model's refusals, payload round-trip and damage
reporting, the store's append-only/no-op-revision/refusal/backup-restore/restart/doctor/privacy
contract, and the export pin. Two additions to `SchemaMigrationTests` (the v8→v9 upgrade on a
database full of records, and step re-runnability). `SCHEMA_VERSION == 9` is re-pinned in
`test_store.py` and `test_store_tasks.py`, deliberately, as every bump before this one was.

* Focused: `python -m unittest tests.test_strategies tests.test_store tests.test_backup
  tests.test_event_log tests.test_importer` — 374 tests OK.
* Full local suite: `python -m unittest discover -s tests` — **2119 tests OK (skipped=13)**.
* `python -m compileall -q career_agent scripts tests` — clean; `git diff --check` — clean.
* No external action; `SOURCE_QUALITY_GATE_PASSED` stays `False`, `enabled_discovery_sources()` stays
  `()`; export format stays **2**.

## Deliberately not in this increment

Matching/eligibility consumption of strategies, tailored-artifact lineage (which needs the
`role_strategy_version` reference this table now provides), invalidation of artifacts on strategy
change, any window or CLI for strategies, and any migration of strategies into the JSON format.
Each is the next P7 increment; none is claimed here.
