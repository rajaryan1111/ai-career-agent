# Changelog

All notable changes to this repository are recorded here. The project is an
internal local alpha; entries describe what has actually been verified.

## [0.1.0] — 2026-10-19

### Added
- Local Tkinter/SQLite desktop workflow: candidate profile, manual job entry with source/model separation, three-valued eligibility, explainable skill overlap, shortlisting on explicit PASS only.
- Attempt-scoped application tracking with an append-only event history, evidence that survives later transitions, guarded status transitions, optimistic concurrency, and re-application after withdrawal as a new attempt.
- Local resume import (DOCX, text-based PDF, TXT, MD) using the standard library only: conservative labelled-line proposals with quoted evidence, applied to the profile form for review and never saved automatically; encrypted, malformed, oversized, non-UTF-8 and image-only files are refused or flagged honestly.
- Application preparation: readiness checklist (blocked / needs review / ready) and a fact-only draft preview that never invents answers or destinations.
- Versioned JSON backups (format 3, schema 2) with full validation, transactional replace-only restore, rollback on failure, and documented format-2 compatibility.
- Partial and complete local data deletion, including a confirmed "delete all local data" action.
- Permission-gated source adapter contract with typed discovery outcomes, rate-limit helper, and a Sources & settings tab that reports the closed source-quality gate. No adapter performs network access.
- `python -m career_agent --database PATH` plus the `career-agent` console command, `--help`, `--version`, and `--diagnostics` (environment and database-location facts with no record contents and no writes).
- Local database files are restricted to the owning user (mode 0600) on POSIX systems when opened, including databases created earlier with a permissive umask.
- `pyproject.toml` (Python 3.10–3.12, zero runtime dependencies), `.gitignore`, and `scripts/smoke_check.py` for one-command verification.
- Test suite: 206 tests plus a 15-scenario tracker smoke test; GitHub Actions runs both on Python 3.10, 3.11, and 3.12.

### Known limitations
- Manual GUI acceptance has not been completed; scripted Tk tests cover the flows where a display exists and skip otherwise.
- Resume import handles labelled text only: no OCR, contact fields, tables, multi-column layouts, or projects/certifications; no live job discovery, no email integration, no automated submission, no scheduler or remote worker.
- Restore is replace-only; format-2 restores are not byte-for-byte faithful.
- No wheel, installer, updater, or code-signing pipeline; only editable installs are verified.
- Only macOS has hosted GUI execution; CI covers tests on Linux but not the desktop UI.
