# Changelog

All notable changes to this repository are recorded here. The project is an
internal local alpha; entries describe what has actually been verified.

## [Unreleased]

### Added
- Eligibility-decision audit trail (database schema 3): every explicit **Evaluate** and **Shortlist** action appends an immutable record with its outcome, timestamp, the `ELIGIBILITY_RULE_VERSION` that produced it, the per-requirement explanation/evidence trail, and versioned `fp1:` SHA-256 fingerprints of the eligibility-relevant profile and listing inputs. Raw candidate values are not duplicated in audit rows or backups.
- Backup format 4 carries the audit trail per job. Formats 2 and 3 remain readable; older builds refuse format 4 instead of dropping records. The audit table is created empty by the v2→v3 migration and by v1→v3 upgrades, without rewriting existing rows.
- The desktop report and status bar state whether a decision was recorded. A failed audit write is reported as `Decision NOT recorded: …` and is never presented as saved.

### Changed
- Schema version is 3 and backup format is 4. Databases written by a newer build are still refused rather than downgraded.
- Tests and the tracker smoke test now cover migration from v1 and v2, decision persistence, cascade/delete counts, fingerprint sensitivity, and backup/restore validation of audit records.

### Known limitations
- Fingerprints are change detectors, not a security boundary; they can be brute-forced by someone who already holds the database. No encryption at rest is added.
- A decision records that an evaluation happened; it does not re-verify the listing or prove an external submission.

## [0.1.0] — 2026-10-19

### Added
- Local Tkinter/SQLite desktop workflow: candidate profile, manual job entry with source/model separation, three-valued eligibility, explainable skill overlap, shortlisting on explicit PASS only.
- Attempt-scoped application tracking with an append-only event history, evidence that survives later transitions, guarded status transitions, optimistic concurrency, and re-application after withdrawal as a new attempt.
- Local resume import (DOCX, text-based PDF, TXT, MD) using the standard library only: conservative labelled-line proposals with quoted evidence, applied to the profile form for review and never saved automatically; encrypted, malformed, oversized, non-UTF-8 and image-only files are refused or flagged honestly.
- Application preparation: readiness checklist (blocked / needs review / ready) and a fact-only draft preview that never invents answers or destinations.
- Versioned JSON backups (format 3, schema 2) with full validation, transactional replace-only restore, rollback on failure, and documented format-2 compatibility.
- Partial and complete local data deletion, including a confirmed "delete all local data" action.
- Closing the window with unsaved profile-form edits asks before discarding them; a clean form closes without a prompt.
- Permission-gated source adapter contract with typed discovery outcomes, rate-limit helper, bounded retry policy with capped exponential backoff, duplicate-observation suppression, schema-error detection, and a Sources & settings tab that reports the closed source-quality gate. No adapter performs network access.
- `python -m career_agent --database PATH` plus the `career-agent` console command, `--help`, `--version`, and `--diagnostics` (environment and database-location facts with no record contents and no writes).
- Local database files are restricted to the owning user (mode 0600) on POSIX systems when opened, including databases created earlier with a permissive umask.
- README troubleshooting for missing Tk, headless displays, database path/locking/permission errors, refused backups, and unsupported resume imports; the manual checklist now covers installation, CLI, edge cases, per-step results, and cleanup.
- `pyproject.toml` (Python 3.10–3.12, zero runtime dependencies), `.gitignore`, and `scripts/smoke_check.py` for one-command verification.
- Test suite: 214 tests plus a 15-scenario tracker smoke test; GitHub Actions runs both on Python 3.10, 3.11, and 3.12.

### Known limitations
- Manual GUI acceptance has not been completed; scripted Tk tests cover the flows where a display exists and skip otherwise.
- Resume import handles labelled text only: no OCR, contact fields, tables, multi-column layouts, or projects/certifications; no live job discovery, no email integration, no automated submission, no scheduler or remote worker.
- Restore is replace-only; format-2 restores are not byte-for-byte faithful.
- No wheel, installer, updater, or code-signing pipeline; only editable installs are verified.
- No encryption at rest: the database relies on `0600` permissions plus OS volume encryption, and backups are plain JSON. Key management and recovery are unresolved; see [the encryption note](research/encryption-at-rest-decision-2026-10-19.md).
- Only macOS has hosted GUI execution; CI covers tests on Linux but not the desktop UI.
