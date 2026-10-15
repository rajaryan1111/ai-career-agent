"""Remove the local data this application wrote, and nothing else.

A local-first product that stores a person's profile, applications and notes has to be able to *unstore*
them. Deleting records one at a time exists in the window; this module answers the other question — "make
this application's data go away" — without turning into a general-purpose file deleter.

**What it removes.** Only files this application wrote, and only where it derives their names from the
database path it was given:

* the database itself, and SQLite's ``-journal``/``-wal``/``-shm`` sidecars;
* the snapshots and staged restores written beside it (``<database>.backup-*``, ``.<database>.restore-…
  .partial``, ``.<database>.rollback.partial``);
* the two log files it writes in the ``logs`` folder beside the database.

**What it never removes.** Anything it cannot derive: backups written to another folder, JSON exports,
calendar files, saved drafts and mock ledgers all live at paths the person chose, and this module does not
go looking for them. It reports that they exist rather than pretending the data is gone, and it never walks
a folder: an unrecognised file beside the database is left where it is and named in the report.

**How it is safe.** Planning is separate from deleting. The plan is a list of concrete paths with sizes,
it is computed without creating anything, and nothing is removed until the caller passes
``confirmed=True``. A destination that exists but is not a regular file (a directory, or anything reached
through a symbolic link) is refused rather than followed. After deleting, existence is re-checked: a
command that did not remove what it listed must not report success.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import backup as backup_module
from .diagnostics import DIAGNOSTIC_FILE_NAME
from .event_log import LOG_FILE_NAME, log_folder

#: The two log files this application writes. Named here rather than globbed, so a log the application
#: does not write cannot be deleted by this module under any circumstances.
_LOG_FILE_NAMES = (LOG_FILE_NAME, DIAGNOSTIC_FILE_NAME)


class ErasureError(Exception):
    """The erasure could not be planned or completed; nothing is hidden behind a success message."""


@dataclass(frozen=True)
class DataFile:
    """One file the application wrote, as it was found."""

    path: Path
    size_bytes: int
    description: str


@dataclass(frozen=True)
class ErasurePlan:
    """What would be removed, and what is deliberately left alone."""

    database: Path
    data_files: tuple[DataFile, ...]
    left_alone: tuple[str, ...]

    @property
    def total_bytes(self) -> int:
        return sum(item.size_bytes for item in self.data_files)

    @property
    def anything_to_remove(self) -> bool:
        return bool(self.data_files)


@dataclass(frozen=True)
class ErasureOutcome:
    """What happened, with the failures named instead of counted away."""

    removed: tuple[Path, ...]
    failed: tuple[tuple[Path, str], ...]

    @property
    def complete(self) -> bool:
        return not self.failed


def _regular_file(path: Path) -> bool:
    """A file this module is willing to delete: real, and not something reached through a link.

    A symbolic link is refused rather than followed. Deleting through one would remove a file somewhere
    else entirely, which is exactly the class of accident this module must not be capable of.
    """
    try:
        if path.is_symlink():
            return False
        return path.is_file()
    except OSError:
        return False


def _size_of(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _candidate_paths(database_path: Path) -> tuple[tuple[Path, str], ...]:
    """Every path this module will consider, each with the reason it belongs to the application."""
    database = Path(database_path)
    folder = database.parent
    candidates: list[tuple[Path, str]] = [(database, "the database")]
    for suffix in backup_module._SIDECAR_SUFFIXES:
        candidates.append((database.with_name(database.name + suffix), f"SQLite {suffix} sidecar"))
    candidates.append((
        database.with_name(f".{database.name}.rollback.partial"), "a staged restore left behind",
    ))
    candidates.extend(
        (path, "a snapshot taken before a restore")
        for path in sorted(folder.glob(f"{database.name}{backup_module.AUTOMATIC_BACKUP_INFIX}*"))
    )
    candidates.extend(
        (path, "a staged restore left behind")
        for path in sorted(folder.glob(f".{database.name}.restore-*.partial"))
    )
    logs = log_folder(database_path=database)
    candidates.extend((logs / name, "a log this application wrote") for name in _LOG_FILE_NAMES)
    return tuple(candidates)


def plan_erasure(database_path: Path) -> ErasurePlan:
    """List what would be removed. Creates nothing, deletes nothing, opens no database."""
    database = Path(database_path)
    if database.exists() and not _regular_file(database):
        # A folder, a symbolic link or anything else that is not the database file: refused outright,
        # because deleting the logs "beside" a path that is not this application's database would remove
        # another database's data - and following a link would remove a file somewhere else entirely.
        raise ErasureError(
            f"{database} is not a regular file, so it is not a database this command may remove. Nothing "
            "was planned and nothing will be deleted."
        )
    data_files = tuple(
        DataFile(path=path, size_bytes=_size_of(path), description=description)
        for path, description in _candidate_paths(database)
        if _regular_file(path)
    )
    refused = [
        path for path, _description in _candidate_paths(database)
        if path.is_symlink() or (path.exists() and not _regular_file(path) and not path.is_dir())
    ]
    left_alone = [
        "A backup, export, calendar file, draft or mock ledger written to a path you chose: this command "
        "cannot find those, so delete them yourself if you want them gone.",
        "Every other file in the folder, including anything this application did not write.",
    ]
    left_alone.extend(f"{path} was left alone: it is not a regular file this command will delete." for path in refused)
    return ErasurePlan(database=database, data_files=data_files, left_alone=tuple(left_alone))


def erase(plan: ErasurePlan) -> ErasureOutcome:
    """Carry out a plan. Each failure is reported with its own reason, and never counted as a success."""
    removed: list[Path] = []
    failed: list[tuple[Path, str]] = []
    for item in plan.data_files:
        # Re-checked immediately before the call: the plan may be acted on later, and a path that changed
        # shape in between (a link, a folder) must not be deleted on the strength of an older look.
        if not _regular_file(item.path):
            failed.append((item.path, "it is no longer a regular file, so it was left alone"))
            continue
        try:
            item.path.unlink()
        except OSError as exc:
            failed.append((item.path, str(exc)))
            continue
        if item.path.exists():
            failed.append((item.path, "the file is still there after the delete, so this is not a success"))
        else:
            removed.append(item.path)
    return ErasureOutcome(removed=tuple(removed), failed=tuple(failed))
