# Canonical Requisition Deduplication — Reconciliation Report

**Audit date:** 2026-10-13  
**Dataset:** `research/job-source-audit-seed-2026-10-13.csv`  
**Scope:** Reconcile records sharing canonical URLs without deleting source provenance or overstating current vacancy counts. Research only; no product implementation.

## Result

The CSV contains 61 records with 27 columns and unique listing IDs. Canonical URL grouping identifies:

- **7 exact requisition/page groups** where multiple records point to the same role URL: Ema, Atlys, CertifyOS, RIVR, Barnes & Thornburg, Formstack, and ATRISI.
- Those groups contain **17 records representing 9 canonical-role observations?** No: they contain **17 records across 7 groups**, which means **10 records beyond one representative per group** remain in these groups for provenance/control purposes. For unique-URL counting, this is 10 excess records across the seven groups.
- **One additional shared-page ambiguity:** Zyora Labs has two advertised role tracks using the same general careers page. URL equality alone cannot establish whether the tracks are separate requisitions or one intake path.
- The dataset has **53 distinct canonical URL values**. This is a URL-bucket count, **not a count of confirmed-open or distinct eligible vacancies**. Some rows are source-review/control records or general feeds, and Zyora's two tracks remain unresolved.
- The eight rows labeled `open` collapse to **seven distinct canonical URL buckets**, because Ema's aggregator observation INT-008 duplicates the Ema Ashby requisition IN-003. That does not mean seven jobs are verified open, suitable, or permitted for automation.

## Reconciliation decisions

| Group | Records | Primary observation | Retained controls / treatment | Counting rule |
|---|---|---|---|---|
| EMA-01 | IN-003, INT-008 | IN-003 — official Ashby listing | INT-008 retained as aggregator/source-agreement control | One canonical requisition |
| ATLYS-01 | IN-005, IN-014, INT-015 | IN-014 — more detailed recorded role evidence | IN-005 retained as lower-confidence prior lead; INT-015 retained as employer-board validation control | One canonical requisition |
| CERTIFYOS-01 | IN-013, INT-014 | IN-013 — existing canonical employer-board observation | INT-014 retained as validation control | One canonical requisition |
| RIVR-01 | INT-011, INT-016 | INT-016 — fuller recorded Zürich and eligibility evidence | INT-011 retained as a duplicate observation | One canonical requisition; preserve geography/work-authorization exclusions |
| BARNES-01 | INT-012, INT-017 | INT-012 — fuller recorded listing evidence | INT-017 retained as source-comparison control | One canonical requisition |
| FORMSTACK-01 | INT-013, INT-018 | INT-013 — primary observation | INT-018 retained as stale-index control | One canonical requisition; stale search evidence is not a second vacancy |
| ATRISI-01 | IN-020, IN-028 | IN-020 — higher-confidence recorded observation | IN-028 retained as duplicate observation with its own provenance | At most one vacancy until separate requisition evidence exists |
| ZYORA-SHARED-CAREERS | IN-016, IN-017 | No primary requisition can yet be selected from URL alone | Keep both role-track descriptions and statuses separate; seek employer confirmation or distinct requisition IDs | Do not assert one or two active vacancies; exclude from confirmed unique-vacancy counts while unresolved |

“Primary observation” means the best current row to use as the representative for review and matching; it does **not** certify live status, eligibility, permission, or employer legitimacy. All duplicate/control rows remain in the CSV so source agreement, stale indexing, and extraction quality can still be evaluated.

## CSV annotations made

The `review_notes` field now explicitly records the dedupe group and whether each row is the primary observation, duplicate observation, source-comparison control, or unresolved shared-page track. No rows were deleted, no listing IDs changed, and no status values were changed as part of reconciliation.

The status distribution remains:

- `open`: 8 rows
- `unknown`: 43 rows
- `expired`: 3 rows
- `closed`: 2 rows
- `not_a_listing`: 1 row
- `source_review`: 4 rows

These labels are preserved exactly; they are not promoted or downgraded by deduplication alone.

## New acceptance test

Added **SV-038 — Canonical requisition deduplication without losing provenance** to the source-validation suite. It requires that exact same-requisition records count once while preserving per-source observations, and that two different tracks sharing a general careers page not be merged without evidence.

## Remaining actions before the source-quality gate

1. Re-fetch and parse the updated CSV; verify 61 rows, 27 columns, unique IDs, and explicit group notes.
2. Use the primary rows for vacancy-level analysis, but retain duplicate controls for source precision/agreement tests.
3. Resolve the Zyora Labs track ambiguity through separate requisition evidence or an authoritative employer clarification; until then, do not claim a precise unique-vacancy count.
4. Recheck current canonical status and eligibility before any role is recommended. A canonical URL and visible application route are not sufficient proof that a role remains open.
5. Independently assess source permission and any required attribution. Deduplication does not clear the permission gate.

**Conclusion:** Canonical duplicates are now explicitly reconciled at the research-data level without losing provenance. This is a data-quality improvement, not evidence that the source portfolio meets coverage thresholds. The research-only implementation gate remains closed.
