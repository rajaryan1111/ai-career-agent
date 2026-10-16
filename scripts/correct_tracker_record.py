#!/usr/bin/env python3
"""Safely correct one local application-tracker record; dry-run by default.

Why this exists: the desktop app can move a record forward through the permitted statuses, but it
deliberately never clears a stored ``candidate_confirmed`` flag on its own, and it cannot revise
the evidence of a status already recorded (re-applying a status is a no-op). A record that reached
``confirmed`` by mistake — for example during a smoke test where nothing was ever submitted — can
therefore only be made truthful by an explicit, auditable correction. This tool performs exactly
one such correction on exactly one record, using the real :class:`~career_agent.store.CareerStore`
so every domain and storage invariant still applies. It cannot create, delete, or bulk-edit data.

Safety properties:
  * Dry run by default: nothing is written unless ``--apply`` is given. The dry run validates the
    intended change on a throwaway copy of the database so it cannot touch the original.
  * ``--apply`` first writes a timestamped backup next to the database through
    :func:`career_agent.backup.create_backup`, so the snapshot is consistent, owner-only where the
    file system supports POSIX permissions, verified before the change is attempted, and never
    overwrites an existing file. Its path is printed.
  * The change goes through ``CareerStore``, so an invalid or impermissible transition is refused
    with the same error the application would give. There is no direct SQL write path here.
  * ``--reason`` is mandatory and becomes the new evidence text: the corrected record must say why
    it is being corrected. The reason is never fabricated by this tool.
  * Only the named record is touched, and the result is re-read and verified field by field - status,
    evidence, confirmation flag and listing id - before success is reported. A verification failure
    exits non-zero and leaves the backup in place.
  * The write is conditional on the row this run read (``save_tracker(..., expected=...)``): if the
    record changed in the meantime, the tool refuses and nothing is written, rather than overwriting
    evidence or a confirmation it never saw. Comparing transition rules alone cannot catch that, since
    a forward move usually leaves the intended transition permitted.

Usage (single correction):
    python scripts/correct_tracker_record.py --database "<path>/career_agent.sqlite3" \
        --listing-id <listing-id> --to withdrawn \
        --reason "Fictional smoke-test record: no application was ever submitted ..." \
        --clear-confirmation --apply

Run it without ``--apply`` first to see the intended change.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from career_agent.core import (  # noqa: E402  (imports need the repository root on sys.path)
    ApplicationStatus,
    ApplicationTracker,
    is_allowed_tracker_transition,
    is_substantive_confirmation_evidence,
)
from career_agent.backup import BackupError, automatic_backup_path, create_backup  # noqa: E402
from career_agent.store import CareerStore  # noqa: E402

EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_UNEXPECTED = 3
_TRACKER_COLUMNS = "listing_id, status, status_evidence, candidate_confirmed, updated_at"


class Refused(Exception):
    """The correction was refused for a reason the user can act on. Nothing was written."""


def read_row(database_path: Path, listing_id: str) -> dict | None:
    """Read one tracker row through a short-lived read-only connection."""
    if not database_path.is_file():
        raise Refused(f"Database not found: {database_path}")
    uri = f"file:{database_path}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise Refused(f"Could not open the database read-only: {exc}") from exc
    try:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            f"SELECT {_TRACKER_COLUMNS} FROM application_tracker WHERE listing_id = ?", (listing_id,)
        ).fetchone()
    except sqlite3.Error as exc:
        raise Refused(f"Could not read the tracker table: {exc}") from exc
    finally:
        connection.close()
    return dict(row) if row is not None else None


def describe(row: dict | None) -> str:
    if row is None:
        return "  (no tracker row)"
    return (
        f"  status={row['status']}  candidate_confirmed={row['candidate_confirmed']}\n"
        f"  evidence={row['status_evidence']!r}\n"
        f"  updated_at={row['updated_at']}"
    )


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Correct exactly one local tracker record through the app's own invariants.",
        epilog="Nothing is written without --apply. A backup is written before any change.",
    )
    parser.add_argument("--database", required=True, help="path to the local SQLite database file")
    parser.add_argument("--listing-id", required=True, help="the listing id of the record to correct")
    parser.add_argument(
        "--to", required=True, choices=[status.value for status in ApplicationStatus],
        help="the status the record should truthfully hold",
    )
    parser.add_argument(
        "--reason", required=True,
        help="truthful note recorded as the new evidence; must explain the correction",
    )
    parser.add_argument(
        "--clear-confirmation", action="store_true",
        help="also drop a confirmation flag that was never genuinely earned or is no longer claimed",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="actually write the change (default is a dry run that writes nothing)",
    )
    return parser.parse_args(argv)


def validate_request(args: argparse.Namespace, row: dict, target: ApplicationStatus) -> bool:
    """Check the request against the domain rules; return whether the confirmation flag is cleared."""
    if not is_substantive_confirmation_evidence(args.reason):
        raise Refused(
            "The --reason text is empty or looks like a placeholder/instruction. Record what actually "
            "happened, for example: 'Fictional smoke-test record: no application was ever submitted.'"
        )
    current = ApplicationStatus(row["status"])
    if target is current:
        raise Refused(
            f"The record is already '{current.value}', so there is nothing to correct. This tool never "
            "rewrites evidence in place; move the status forward in the app instead."
        )
    if target is ApplicationStatus.CONFIRMED:
        raise Refused(
            "Refusing to move a record to 'confirmed': a confirmation is a claim about an employer and "
            "must be recorded in the app, where the confirmation assertion is made deliberately."
        )
    if not is_allowed_tracker_transition(current, target):
        raise Refused(
            f"The state machine does not permit {current.value} -> {target.value}. This tool cannot "
            "bypass the app's transitions."
        )
    return bool(args.clear_confirmation)


def corrected_tracker(row: dict, target: ApplicationStatus, reason: str, clear_confirmation: bool) -> ApplicationTracker:
    """Build the corrected tracker value exactly as the domain would."""
    current = ApplicationTracker(
        listing_id=row["listing_id"], status=ApplicationStatus(row["status"]),
        status_evidence=row["status_evidence"], candidate_confirmed=bool(row["candidate_confirmed"]),
    )
    return current.transition(
        target, evidence=reason, candidate_confirmed=False if clear_confirmation else None
    )


def expected_fields(row: dict) -> dict:
    """The fields a correction was decided from, for the conditional write in :meth:`save_tracker`.

    Read paths in this module are deliberately short-lived, so the row is read once, validated, and
    then written minutes later when ``--apply`` follows a review. Passing these fields makes the write
    compare-and-set: a record another writer moved on - even to a status this transition also permits,
    with evidence or a confirmation this run never saw - matches no row and is refused instead of
    being overwritten by a stale decision.
    """
    return {
        "status": row["status"],
        "status_evidence": row["status_evidence"],
        "candidate_confirmed": bool(row["candidate_confirmed"]),
    }


def describe_mismatch(verified: dict | None, intended: ApplicationTracker, listing_id: str) -> str | None:
    """Compare a written row with the intended correction, field by field; ``None`` means it matches.

    Every field the tool set is checked, not only the status: a write that reached the intended status
    while dropping the evidence, the confirmation flag, or the identity of the record would still be a
    lost correction, and reporting it as success would be wrong. ``updated_at`` is checked by its
    documented meaning - when the app last wrote this record locally - so it must be a parseable
    ISO-8601 instant; no particular value is ever expected.
    """
    if verified is None:
        return f"no tracker row exists for {listing_id!r} after the write"
    checks = (
        ("listing_id", verified.get("listing_id"), intended.listing_id),
        ("status", verified.get("status"), intended.status.value),
        ("status_evidence", verified.get("status_evidence"), intended.status_evidence),
        ("candidate_confirmed", bool(verified.get("candidate_confirmed")), intended.candidate_confirmed),
    )
    for name, found, wanted in checks:
        if found != wanted:
            return f"{name} is {found!r}, expected {wanted!r}"
    try:
        datetime.fromisoformat(str(verified.get("updated_at")))
    except (TypeError, ValueError):
        return f"updated_at is {verified.get('updated_at')!r}, which is not an ISO-8601 timestamp"
    return None


def apply_to_copy(database_path: Path, listing_id: str, target: ApplicationStatus, reason: str,
                  clear_confirmation: bool) -> tuple[bool, str]:
    """Validate the intended change on a throwaway copy so the original is never touched."""
    with tempfile.TemporaryDirectory() as directory:
        copy_path = Path(directory) / "validation-copy.sqlite3"
        shutil.copy2(database_path, copy_path)
        with CareerStore(str(copy_path)) as store:
            row = read_row(copy_path, listing_id)
            if row is None:
                raise Refused("The record disappeared from the validation copy.")
            intended = corrected_tracker(row, target, reason, clear_confirmation)
            store.save_tracker(intended, expected=expected_fields(row))
            verified = read_row(copy_path, listing_id)
        mismatch = describe_mismatch(verified, intended, listing_id)
        if mismatch is not None:
            return False, f"the validation copy did not hold the correction ({mismatch})"
        return True, "the change is permitted and was reproduced on a throwaway copy"


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv)
    database_path = Path(args.database).expanduser()
    target = ApplicationStatus(args.to)
    try:
        row = read_row(database_path, args.listing_id)
        if row is None:
            raise Refused(f"No tracker row exists for listing id {args.listing_id!r}; nothing to correct.")
        clear_confirmation = validate_request(args, row, target)
        corrected = corrected_tracker(row, target, args.reason, clear_confirmation)

        print(f"Database: {database_path}")
        print(f"Listing:  {args.listing_id}")
        print("Current record:")
        print(describe(row))
        print("Corrected record (intended):")
        print(describe({
            "status": corrected.status.value,
            "status_evidence": corrected.status_evidence,
            "candidate_confirmed": int(corrected.candidate_confirmed),
            "updated_at": "(updated on write)",
        }))

        if not args.apply:
            ok, detail = apply_to_copy(database_path, args.listing_id, target, args.reason, clear_confirmation)
            print(f"\nDRY RUN: {detail}." if ok else f"\nDRY RUN FAILED: {detail}.")
            print("Nothing was written. Re-run with --apply to make this change.")
            return EXIT_OK if ok else EXIT_REFUSED

        # One shared implementation: verified, owner-only, never overwrites an existing snapshot.
        backup_path = automatic_backup_path(database_path)
        try:
            snapshot = create_backup(database_path, backup_path)
        except BackupError as exc:
            print(f"REFUSED: the database could not be backed up before the change ({exc})", file=sys.stderr)
            print("Nothing was written.", file=sys.stderr)
            return EXIT_REFUSED
        print(f"\nBackup written and verified: {backup_path}")
        print(f"Contents: {snapshot.summary()}")

        with CareerStore(str(database_path)) as store:
            # Conditional on the row this run read and validated: see ``expected_fields``.
            store.save_tracker(corrected, expected=expected_fields(row))

        verified = read_row(database_path, args.listing_id)
        mismatch = describe_mismatch(verified, corrected, args.listing_id)
        if mismatch is not None:
            print(f"VERIFICATION FAILED: the written record does not match the intended change "
                  f"({mismatch}).", file=sys.stderr)
            print(f"The backup is still intact at {backup_path}", file=sys.stderr)
            return EXIT_UNEXPECTED
        print("Corrected record:")
        print(describe(verified))
        print(f"\nCorrection applied and verified. Original state is preserved in {backup_path}")
        return EXIT_OK
    except Refused as refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        print("Nothing was written.", file=sys.stderr)
        return EXIT_REFUSED
    except (ValueError, sqlite3.Error) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        print("Nothing was written.", file=sys.stderr)
        return EXIT_REFUSED
    except Exception as exc:  # unexpected: report honestly, do not pretend success
        print(f"UNEXPECTED ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("Nothing was written unless a backup message was printed above.", file=sys.stderr)
        return EXIT_UNEXPECTED


if __name__ == "__main__":
    raise SystemExit(main())
