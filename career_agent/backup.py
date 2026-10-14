"""Verified, local-only database backup and restore.

Why SQLite's backup API instead of a file copy
----------------------------------------------
A plain file copy is not a backup of a live SQLite database. Measured on this project's own store:
for a database in WAL format the committed rows live in the ``-wal`` sidecar, and copying the main
file alone produced a file that failed with ``no such table``; the same copy inherited the process
``umask`` (``0o644``, readable by other local accounts) and silently overwrote a previous backup.
``sqlite3.Connection.backup`` reads through SQLite, so it captures a consistent snapshot of the
committed state even while the application holds the database open.

Guarantees implemented here
---------------------------
* A backup destination is created owner-only (``0600``) *before* any data is written, is never an
  existing file (``O_EXCL``: nothing is overwritten and a symbolic link is not followed), and is
  verified (SQLite ``integrity_check``, schema version, required tables) before success is reported.
  On any failure the partial file this module created is removed, so a failed backup cannot be
  mistaken for a usable one.
* Every backup is normalised to the classic single-file rollback-journal format, so it has no
  ``-wal``/``-shm`` sidecars, opens correctly wherever it is copied, and a restored database never
  silently switches the application to WAL (whose sidecars would be created with ordinary,
  non-owner-only permissions).
* Restore validates the chosen file *before* the live database is touched, copies it into a staged
  file beside the live database, validates that exact staged file, snapshots the current database
  (verified when it is readable, raw but owner-only when it is not), refuses while another
  connection holds the database, replaces the file with an atomic ``os.replace``, and reopens the
  result to verify it. A failure after the swap puts the previous database back.
* Local only, standard library only: no network access, no third-party dependency, no schema
  migration and no silent downgrade. A file whose schema version is not exactly the version this
  build supports is refused rather than guessed at.

Platform limits (stated, not claimed)
-------------------------------------
* The owner-only guarantee is POSIX-only. On Windows ``os.chmod`` cannot express it, so backups are
  written without that protection and this module does not claim otherwise. Windows also refuses
  ``os.replace`` while another program has the destination open: the restore then fails with a
  message and the original database is left untouched.
* While another process is committing to the database, ``Connection.backup`` can wait for it (the
  standard library retries while SQLite reports the source busy, and its ``progress`` callback does
  not break that loop). The exclusive-access check turns the common cases — a second copy of the
  app, an abandoned lock — into a prompt, actionable refusal instead of an apparent freeze; it
  cannot bound the wait in every interleaving.
* ``PRAGMA integrity_check`` detects the damage SQLite can detect. It cannot prove that a backup is
  complete or that a byte-level change to data pages never happened.
"""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .store import (
    SCHEMA_TABLES, SCHEMA_VERSION, PrivateWriteError, create_private_file, require_owner_only,
)

#: Default file name offered when the user chooses where to write a backup.
BACKUP_NAME_PREFIX = "career_agent-backup"
BACKUP_SUFFIX = ".sqlite3"

#: Suffix of the snapshot written beside the database before a restore (the correction tool
#: ``scripts/correct_tracker_record.py`` uses the same convention for the same purpose).
AUTOMATIC_BACKUP_INFIX = ".backup-"

#: How long SQLite waits for a lock before reporting the database as busy. Kept short so a refusal
#: arrives as a message rather than an apparently frozen window.
LOCK_TIMEOUT_SECONDS = 2.0

#: SQLite side files. A stale ``-wal``/``-journal`` left beside a replaced database would be
#: replayed on top of it and silently discard the restored data, so they never survive a restore.
_SIDECAR_SUFFIXES = ("-journal", "-wal", "-shm")
_COPY_CHUNK_BYTES = 1024 * 1024


class BackupError(Exception):
    """A backup or restore was refused or failed. The message is written to be shown to the user."""


class DatabaseInUse(BackupError):
    """Another connection holds the database, so it must not be read as a snapshot or replaced.

    A distinct type because the two callers must behave differently: a file that cannot be read as a
    database is preserved as a raw copy so a restore can still recover from it, while a database that
    is simply *busy* must refuse the operation instead of being copied in a torn state and replaced
    underneath whoever is using it.
    """


@dataclass(frozen=True)
class DatabaseInfo:
    """What a verified database file contains."""

    path: Path
    schema_version: int
    profile_present: bool
    job_count: int
    tracker_count: int
    foreign_key_violations: int
    size_bytes: int

    def summary(self) -> str:
        """One factual line about the contents, used by the dialogs and the command line."""
        profile = "profile saved" if self.profile_present else "no profile"
        jobs = f"{self.job_count} job" + ("" if self.job_count == 1 else "s")
        trackers = f"{self.tracker_count} tracker record" + ("" if self.tracker_count == 1 else "s")
        return f"{profile} · {jobs} · {trackers} · schema version {self.schema_version}"


@dataclass(frozen=True)
class RestoreResult:
    """What a completed restore did, for reporting to the user."""

    database_path: Path
    restored_from: Path
    pre_restore_backup: Path | None
    pre_restore_verified: bool
    removed_sidecars: tuple[Path, ...]
    info: DatabaseInfo


def _utc_stamp(timestamp: datetime | None = None) -> str:
    """A sortable UTC file-name stamp; injectable so tests do not depend on the clock."""
    moment = timestamp or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def suggested_backup_name(timestamp: datetime | None = None) -> str:
    """Default file name offered for a user-chosen backup destination (timestamps are UTC)."""
    return f"{BACKUP_NAME_PREFIX}-{_utc_stamp(timestamp)}{BACKUP_SUFFIX}"


def automatic_backup_path(database_path: str | Path, timestamp: datetime | None = None) -> Path:
    """Where the pre-restore snapshot of ``database_path`` is written: same folder, timestamped."""
    database = Path(database_path)
    return database.with_name(f"{database.name}{AUTOMATIC_BACKUP_INFIX}{_utc_stamp(timestamp)}")


def _staged_path(database_path: Path, timestamp: datetime | None) -> Path:
    """Staging file for a restore: same folder as the database, so ``os.replace`` stays atomic."""
    return database_path.with_name(f".{database_path.name}.restore-{_utc_stamp(timestamp)}.partial")


def _sidecar_paths(database_path: Path) -> tuple[Path, ...]:
    return tuple(database_path.with_name(database_path.name + suffix) for suffix in _SIDECAR_SUFFIXES)


def _read_only_uri(path: Path) -> str:
    """A ``file:`` URI in read-only mode; ``as_uri`` escapes spaces and other special characters."""
    return f"{Path(os.path.abspath(os.fspath(path))).as_uri()}?mode=ro"


def _discard(path: Path) -> str:
    """Remove a file this module created and describe the outcome for a user-facing message."""
    try:
        os.unlink(path)
    except FileNotFoundError:
        return f"Nothing was kept at {path}"
    except OSError as exc:
        return f"{path} could not be removed ({exc.strerror or exc}); delete it manually"
    return f"Nothing was kept at {path}"


def _is_locking_failure(exc: BaseException) -> bool:
    """Whether a SQLite error is a lock/busy condition rather than an unreadable file."""
    message = str(exc).lower()
    return "locked" in message or "busy" in message


def validate_app_database(path: str | Path) -> DatabaseInfo:
    """Verify that ``path`` is a readable database with the schema this build supports.

    Read-only and side-effect free: the file is never modified, so this can be used on a candidate
    backup before anything local changes. Raises :class:`BackupError` with a user-facing message
    when the file is missing, empty, unreadable, damaged, missing a required table, or written for a
    different schema version.

    A schema version newer than this build's is refused rather than opened, which preserves the
    application's own "newer than supported" refusal: no downgrade and no migration is attempted.
    """
    target = Path(path)
    if target.is_symlink():
        raise BackupError(f"{target} is a symbolic link. Choose the real file rather than a link to it.")
    if not target.is_file():
        raise BackupError(f"No file found at {target}.")
    if target.stat().st_size == 0:
        raise BackupError(f"{target} is empty (0 bytes), so it is not a database this app can read.")

    connection = None
    try:
        connection = sqlite3.connect(_read_only_uri(target), uri=True, timeout=LOCK_TIMEOUT_SECONDS)
        verdict = connection.execute("PRAGMA integrity_check").fetchone()
        result = verdict[0] if verdict else "no result"
        if result != "ok":
            raise BackupError(
                f"{target} failed SQLite's integrity check ({result}), so it is damaged and cannot be "
                "used as a backup."
            )
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version > SCHEMA_VERSION:
            raise BackupError(
                f"{target} uses schema version {version}, which is newer than this app supports "
                f"(version {SCHEMA_VERSION}). Update the app, or use a backup written by this version. "
                "Nothing was changed and no downgrade was attempted."
            )
        if version != SCHEMA_VERSION:
            raise BackupError(
                f"{target} uses schema version {version}, but this app supports exactly version "
                f"{SCHEMA_VERSION}. Refusing to guess at or migrate a different schema."
            )
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        missing = [name for name in SCHEMA_TABLES if name not in tables]
        if missing:
            raise BackupError(
                f"{target} is missing the expected table(s) {', '.join(sorted(missing))}, so it was not "
                "written by this app."
            )
        rows = {name: int(connection.execute(f"SELECT count(*) FROM {name}").fetchone()[0]) for name in SCHEMA_TABLES}
        violations = len(connection.execute("PRAGMA foreign_key_check").fetchall())
    except sqlite3.DatabaseError as exc:
        if _is_locking_failure(exc):
            raise DatabaseInUse(
                f"{target} is in use by another program right now ({exc}). Close other copies of the "
                "app and try again."
            ) from exc
        raise BackupError(f"{target} is not a database this app can read ({exc}).") from exc
    finally:
        if connection is not None:
            connection.close()

    return DatabaseInfo(
        path=target, schema_version=version, profile_present=rows["candidate_profile"] > 0,
        job_count=rows["job_listings"], tracker_count=rows["application_tracker"],
        foreign_key_violations=violations, size_bytes=target.stat().st_size,
    )


def _copy_through_sqlite(source: Path, destination: Path, *, source_read_only: bool = True) -> None:
    """Copy ``source`` into the already-existing file ``destination`` through SQLite's backup API.

    ``destination`` must exist and be owner-only: SQLite writes into the existing file, so its
    permissions are never widened, and ``journal_mode = MEMORY`` keeps this copy's rollback journal
    in memory instead of creating an ordinary-permission sidecar beside it.

    ``source_read_only`` keeps a user-chosen backup file strictly read-only during a restore. The
    application's own database is opened read-write so SQLite can recover a database another tool
    left in WAL format; reading through SQLite is also what makes a ``-wal`` file part of the copied
    state instead of being silently skipped, which is exactly what a plain file copy does.
    """
    source_connection = sqlite3.connect(
        _read_only_uri(source) if source_read_only else str(source), uri=source_read_only,
        timeout=LOCK_TIMEOUT_SECONDS,
    )
    destination_connection = sqlite3.connect(str(destination), timeout=LOCK_TIMEOUT_SECONDS)
    try:
        destination_connection.execute("PRAGMA journal_mode = MEMORY")
        source_connection.backup(destination_connection)
        # A source stored in WAL format would leave the copy marked as WAL. Opening such a file later
        # creates -wal/-shm sidecars with ordinary permissions, so every copy is normalised back to
        # the classic single-file rollback-journal format.
        destination_connection.execute("PRAGMA journal_mode = DELETE")
    finally:
        destination_connection.close()
        source_connection.close()


def _require_no_other_connection(database_path: Path) -> None:
    """Refuse while another connection holds the database open.

    Replacing a database file cannot be coordinated with a connection that stays open: SQLite keeps
    the old file, so later writes land in a file nobody can see again. Taking an exclusive lock for
    an instant proves no other connection is active, and turns the common cause (a second copy of the
    app) into a clear refusal. A file that cannot be used as a database at all is not a locking
    problem and is left to the caller, which is already handling an unreadable database.
    """
    connection = None
    try:
        connection = sqlite3.connect(str(database_path), timeout=LOCK_TIMEOUT_SECONDS, isolation_level=None)
        connection.execute("BEGIN EXCLUSIVE")
        connection.execute("ROLLBACK")
    except sqlite3.DatabaseError as exc:
        if _is_locking_failure(exc):
            raise DatabaseInUse(
                f"{database_path} is in use by another connection ({exc}). Close other copies of the "
                "app, then try again."
            ) from exc
    finally:
        if connection is not None:
            connection.close()


def _copy_bytes(source: Path, destination: Path) -> None:
    """Copy a file byte for byte into an already-created, owner-only ``destination``."""
    with open(source, "rb") as reader, open(destination, "wb") as writer:
        while True:
            chunk = reader.read(_COPY_CHUNK_BYTES)
            if not chunk:
                break
            writer.write(chunk)


def _preserve_current_database(database_path: Path, timestamp: datetime | None) -> tuple[Path | None, bool]:
    """Snapshot the current database before it is replaced.

    Returns ``(path, verified)``. A readable database produces a verified, owner-only snapshot
    through :func:`create_backup`. A database that cannot be read as SQLite — the situation a
    restore is usually needed for — is preserved as a raw byte copy plus its side files, and is
    reported as *not verified* so nothing claims it is readable. If it cannot be preserved at all,
    the whole restore is refused rather than replacing data that would then be unrecoverable.
    """
    if not database_path.exists():
        return None, False
    snapshot = automatic_backup_path(database_path, timestamp)
    try:
        validate_app_database(database_path)
    except DatabaseInUse as busy:
        # Busy is not the same as unreadable: a raw copy of a database somebody is writing could be
        # torn, and replacing the file under that writer would break the coordination guarantee.
        raise BackupError(f"The restore was refused because {busy}") from busy
    except BackupError:
        # The current database cannot be read as SQLite — the situation a restore is usually needed
        # for. Preserve its bytes (and any side files) owner-only rather than refusing to recover,
        # and report it to the user as an unverified copy so nothing claims it is readable.
        pass
    else:
        # A readable database always gets a verified snapshot. Any failure here (another connection
        # holding it, an unwritable folder) refuses the restore instead of falling back to a copy
        # that could not be verified.
        try:
            create_backup(database_path, snapshot, timestamp=timestamp)
        except BackupError as exc:
            raise BackupError(
                f"The current database could not be preserved before restoring ({exc}), so the "
                "restore was refused. Nothing was changed."
            ) from exc
        return snapshot, True
    to_preserve = [(database_path, snapshot)]
    for sidecar in _existing_sidecars(database_path):
        to_preserve.append((sidecar, snapshot.with_name(snapshot.name + sidecar.name[len(database_path.name):])))
    for origin, copy in to_preserve:
        try:
            descriptor = create_private_file(copy, exclusive=True)
            os.close(descriptor)
            _copy_bytes(origin, copy)
            require_owner_only(copy, noun="backup")
        except (PrivateWriteError, OSError) as exc:
            raise BackupError(
                f"The current database could not be preserved before restoring ({origin} -> {copy}: "
                f"{exc}), so the restore was refused. Nothing was changed."
            ) from exc
    return snapshot, False


def _existing_sidecars(database_path: Path) -> tuple[Path, ...]:
    """Side files that actually exist next to ``database_path``."""
    return tuple(path for path in _sidecar_paths(database_path) if path.exists())


def _remove_sidecars(database_path: Path) -> tuple[Path, ...]:
    """Remove leftover side files and report which were removed.

    Called only after the current database has been snapshotted and the file has been replaced, so
    nothing that is still needed is deleted. A stale ``-wal`` replayed onto a replaced database
    silently discards the restored data; a stale hot ``-journal`` can roll back the new file.
    """
    removed = []
    for sidecar in _existing_sidecars(database_path):
        try:
            sidecar.unlink()
            removed.append(sidecar)
        except OSError:
            raise BackupError(
                f"{sidecar} could not be removed after restoring. Delete it before opening the app, "
                "because SQLite would otherwise apply it to the restored database."
            ) from None
    return tuple(removed)


def create_backup(database_path: str | Path, destination: str | Path, *,
                  timestamp: datetime | None = None) -> DatabaseInfo:
    """Write a verified, owner-only snapshot of the local database to ``destination``.

    Refuses an existing destination (backups are never overwritten, and a symbolic link is never
    followed), refuses while another connection is committing to the database, and removes its own
    partial file on any failure. Nothing is reported as successful until the new file has been read
    back and verified.
    """
    source = Path(database_path)
    target = Path(destination)
    if source.is_symlink() or not source.is_file():
        raise BackupError(f"There is no database at {source} to back up.")
    if source.stat().st_size == 0:
        raise BackupError(f"{source} is empty (0 bytes), so there is nothing to back up yet.")
    if target.is_symlink():
        raise BackupError(
            f"{target} is a symbolic link. Refusing to write a backup through it; choose a regular "
            "file name."
        )
    if target.is_dir():
        raise BackupError(f"{target} is a folder. Choose a file name for the backup.")
    if target.exists():
        raise BackupError(
            f"A file already exists at {target}. Backups are never overwritten: choose another name, "
            "or move the existing file first."
        )
    if not target.parent.is_dir():
        raise BackupError(f"The folder {target.parent} does not exist. Choose an existing folder.")

    validate_app_database(source)  # refuse early, before creating anything, when the source is unusable
    _require_no_other_connection(source)

    try:
        descriptor = create_private_file(target, exclusive=True)
    except PrivateWriteError as exc:
        raise BackupError(str(exc)) from exc
    try:
        os.close(descriptor)
        _copy_through_sqlite(source, target, source_read_only=False)
    except (sqlite3.Error, OSError) as exc:
        raise BackupError(f"The backup could not be created ({exc}). {_discard(target)}.") from exc
    try:
        info = validate_app_database(target)
        require_owner_only(target, noun="backup")
    except (BackupError, PrivateWriteError) as exc:
        raise BackupError(
            f"The backup did not verify, so it was not kept ({exc}). {_discard(target)}."
        ) from exc
    return info


def restore_backup(backup_path: str | Path, database_path: str | Path, *,
                   timestamp: datetime | None = None) -> RestoreResult:
    """Replace the local database with a validated copy of ``backup_path``.

    Each step refuses rather than guesses, and the live database is only touched after the chosen
    file has been validated, a staged copy of it has been validated, and the current database has
    been preserved:

    1. validate the chosen backup (never modified: it is opened read-only and copied from there);
    2. write and validate a staged file beside the live database, so the file that is installed is
       exactly the file that was checked;
    3. preserve the current database (verified snapshot when readable, raw owner-only copy when it
       is not) and refuse the restore if it cannot be preserved;
    4. refuse while another connection holds the database open;
    5. replace the file with an atomic ``os.replace`` and remove any stale SQLite side files;
    6. reopen and verify the installed database, putting the previous database back if that fails.
    """
    source = Path(backup_path)
    database = Path(database_path)
    source_info = validate_app_database(source)
    if database.is_symlink():
        raise BackupError(f"{database} is a symbolic link. Refusing to replace it; use the real path.")
    if not database.parent.is_dir():
        raise BackupError(f"The folder {database.parent} does not exist.")
    if database.is_dir():
        # Checked here, before any staging file is created: a folder is a common mistake when a file
        # dialog is pointed at the application's data folder, and the later preservation step would
        # otherwise report it as a database that "could not be preserved" - true of nothing.
        raise BackupError(
            f"{database} is a folder, not a database file. Choose the database file itself."
        )
    staged = _staged_path(database, timestamp)
    try:
        descriptor = create_private_file(staged, exclusive=True)
    except PrivateWriteError as exc:
        raise BackupError(str(exc)) from exc
    try:
        os.close(descriptor)
        _copy_through_sqlite(source, staged, source_read_only=True)
        staged_info = validate_app_database(staged)
    except BackupError:
        raise BackupError(f"The restore was not started. {_discard(staged)}.") from None
    except (sqlite3.Error, OSError) as exc:
        raise BackupError(
            f"The restore was not started: the backup could not be copied ({exc}). {_discard(staged)}."
        ) from exc
    if staged_info.schema_version != source_info.schema_version:  # defensive: same file, same contract
        raise BackupError(
            f"The restore was not started: the staged copy reports schema version "
            f"{staged_info.schema_version}, not {source_info.schema_version}. {_discard(staged)}."
        )

    try:
        # Coordinate with other connections here: preserving the current database refuses while
        # another connection holds it (see ``create_backup``), so this runs immediately before the
        # swap and again as the last step before anything is replaced. It is also taken after the
        # snapshot rather than before, because opening a database can make SQLite remove leftover
        # side files, and those must already be preserved rather than destroyed by a readiness check.
        pre_backup, pre_verified = _preserve_current_database(database, timestamp)
    except BackupError:
        _discard(staged)  # its own staging file must not outlive a refused restore
        raise

    try:
        os.replace(staged, database)
    except OSError as exc:
        preserved = f"it is preserved at {pre_backup}" if pre_backup is not None else "there was nothing to preserve"
        raise BackupError(
            f"The database could not be replaced ({exc.strerror or exc}). The current database is "
            f"unchanged, and {preserved}. {_discard(staged)}."
        ) from exc

    removed_sidecars = _remove_sidecars(database)
    try:
        require_owner_only(database, noun="database")
        info = validate_app_database(database)
    except (BackupError, PrivateWriteError) as exc:
        raise BackupError(_describe_failed_install(database, pre_backup, pre_verified, exc)) from exc

    return RestoreResult(
        database_path=database, restored_from=source, pre_restore_backup=pre_backup,
        pre_restore_verified=pre_verified, removed_sidecars=removed_sidecars, info=info,
    )


def _describe_failed_install(database_path: Path, pre_backup: Path | None, pre_verified: bool,
                             reason: Exception) -> str:
    """Report a failed post-install check, putting the previous database back when that is possible.

    Reached after the swap, when the restored file is in place but cannot be confirmed usable. The
    original database is never simply left destroyed: a verified snapshot is copied back through the
    same staged-and-replace path (leaving the snapshot itself intact for the user).
    """
    note = f"The restored database could not be confirmed usable ({reason})."
    if pre_backup is None:
        return f"{note} There was no previous database to put back."
    if not pre_verified:
        return (
            f"{note} The previous database could not be read before the restore, so it was kept as a "
            f"raw copy at {pre_backup} rather than being verified; the app may need help to recover."
        )
    staged = database_path.with_name(f".{database_path.name}.rollback.partial")
    try:
        descriptor = create_private_file(staged, exclusive=True)
        os.close(descriptor)
        _copy_through_sqlite(pre_backup, staged, source_read_only=True)
        os.replace(staged, database_path)
        _remove_sidecars(database_path)
        validate_app_database(database_path)
    except Exception as exc:  # noqa: BLE001 - the rollback path must report, never raise
        return (
            f"{note} Putting the previous database back also failed ({exc}); it is preserved at "
            f"{pre_backup}. {_discard(staged)}."
        )
    return f"{note} The previous database was put back from {pre_backup}."
