"""The handlers this application registers: what a scheduled task actually does.

Two are built in, and both are written so that "nothing happened" can never look like "the work was
done":

* ``backup.snapshot`` writes a verified snapshot of the local database beside it, through the same
  :func:`career_agent.backup.create_backup` the *Data safety* tab and the command line use, so a
  scheduled snapshot guarantees exactly what a manual one guarantees - consistent, owner-only, read
  back and validated. It refuses when the folder already holds more automatic snapshots than
  :data:`MAX_AUTOMATIC_SNAPSHOTS`, because a schedule that fills a disk is a worse failure than a
  missed snapshot. It never deletes an existing file: a scheduled job must not be able to destroy the
  recovery copies it exists to create.

* ``discovery.run`` is the scheduled discovery the product is built around. Live discovery is
  *disabled*: the source-quality gate has not passed and no source is enabled, so this handler refuses
  with that reason attached and touches no network. If the gate ever genuinely passes, the same task
  will run the real discovery through the adapter framework; until then every scheduled run is
  recorded as a refusal naming the gate, which is exactly what the run history should show.

The refusal is not a placeholder. It is the honest record of a product whose network access is gated,
and it is what makes the difference visible between "we did not try" and "we tried and it failed".
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .backup import automatic_backup_snapshots, create_backup, next_automatic_backup_path
from .sources import SOURCE_QUALITY_GATE_PASSED, enabled_discovery_sources
from .tasks import (
    DEFAULT_SCHEDULE_TIMES, DEFAULT_TIMEZONE, HandlerOutcome, HandlerResult, ScheduledTask, build_task,
)
from .worker import HandlerRegistry, TaskContext

#: How many automatic snapshots may sit beside the database before the scheduled backup refuses. The
#: number is deliberately generous (two snapshots a day is a fortnight) and the refusal names the count,
#: so a person who wants more can move the old ones themselves rather than have the application guess.
MAX_AUTOMATIC_SNAPSHOTS = 30

#: Where the product's own cadence comes from: midnight and noon on the person's clock, in the zone the
#: product was specified with. ``build_task`` defaults to these too; they are named here because the
#: seeded tasks are what a person actually sees in their schedule.
DISCOVERY_TASK_ID = "scheduled-discovery"
BACKUP_TASK_ID = "daily-backup"


class BuiltinHandler:
    """A registered handler together with the one line the scheduler shows for its kind."""

    def __init__(self, kind: str, description: str, run) -> None:
        self.kind = kind
        self.description = description
        self._run = run

    def __call__(self, context: TaskContext) -> HandlerResult:
        return self._run(context)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"BuiltinHandler({self.kind!r})"


def backup_snapshot(context: TaskContext) -> HandlerResult:
    """Write one verified snapshot of the database beside it, or refuse and say why."""
    database = Path(context.database_path)
    if not database.is_file():
        return HandlerResult(
            HandlerOutcome.REFUSED,
            "there is no database file to back up yet, so nothing was written")
    existing = automatic_backup_snapshots(database)
    if len(existing) >= MAX_AUTOMATIC_SNAPSHOTS:
        return HandlerResult(
            HandlerOutcome.REFUSED,
            f"{len(existing)} automatic snapshots already sit beside the database, which is the limit "
            f"of {MAX_AUTOMATIC_SNAPSHOTS}; move or delete some of them and this task will run again. "
            "Nothing was deleted: a scheduled backup will not remove the copies it exists to create.")
    # Named from the occurrence, so the same scheduled instant cannot produce two differently-named
    # copies, and an attempt that finds its name taken writes beside it rather than over it.
    target = next_automatic_backup_path(database, context.slot_at)
    # A failure here is not caught: the backup module's message names the cause, and the worker records
    # it as the attempt's error - a failure rather than a refusal, because the work was attempted.
    info = create_backup(database, target)
    # ``create_backup`` verifies what it wrote before returning, so reaching this line means the file
    # exists, opens, and holds this schema's tables.
    return HandlerResult(HandlerOutcome.SUCCEEDED, f"wrote {target.name} and verified it ({info.summary()})")


def discovery_run(context: TaskContext) -> HandlerResult:
    """The scheduled discovery run: refuse while live discovery is gated, and never reach the network.

    Read the reason before assuming a fault: a refusal here is the permission gate working. It is
    recorded, counted as neither a success nor a failure, and never retried, because repeating a
    decision does not change it.
    """
    if not SOURCE_QUALITY_GATE_PASSED:
        return HandlerResult(
            HandlerOutcome.REFUSED,
            "live discovery is disabled: the source-quality gate has not passed, so no source may be "
            "read. This is the product's permission rule, not a failure; nothing was sent or fetched.")
    sources = enabled_discovery_sources()
    if not sources:
        return HandlerResult(
            HandlerOutcome.REFUSED,
            "live discovery is disabled: no source is enabled for collection, so there is nothing to "
            "read. Nothing was sent or fetched.")
    # Even with the gate passed and a source enabled, no live adapter is implemented in this build, and
    # saying so is the only honest answer: claiming a run would be inventing a result.
    return HandlerResult(
        HandlerOutcome.REFUSED,
        "live discovery is disabled in this build: no source adapter is implemented yet, so nothing "
        "was fetched.")


def default_registry() -> HandlerRegistry:
    """The registry this application runs: the two built-in kinds, and nothing else."""
    registry = HandlerRegistry()
    registry.register("backup.snapshot", BuiltinHandler(
        "backup.snapshot",
        "Write a verified snapshot of the database beside it (refuses instead of deleting old ones)",
        backup_snapshot))
    registry.register("discovery.run", BuiltinHandler(
        "discovery.run",
        "Run scheduled discovery (refuses while the source-quality gate is closed; no network access)",
        discovery_run))
    return registry


def describe_default_handlers() -> tuple[str, ...]:
    """One line per built-in kind, for the command line and the window."""
    return default_registry().describe()


def default_tasks(*, now: datetime | None = None) -> tuple[ScheduledTask, ...]:
    """The tasks a fresh installation should have.

    The discovery cadence is the product's (00:00 and 12:00 Asia/Kolkata). The backup runs once a day,
    late, when it is least likely to compete with anything the person is doing; it is a local file
    operation and asks nobody for anything.
    """
    return (
        build_task(
            DISCOVERY_TASK_ID, "Scheduled job discovery", "discovery.run",
            times=DEFAULT_SCHEDULE_TIMES, timezone=DEFAULT_TIMEZONE,
            timeout_seconds=600, max_attempts=2, retry_backoff_seconds=300, now=now),
        build_task(
            BACKUP_TASK_ID, "Daily database backup", "backup.snapshot",
            times=("23:30",), timezone=DEFAULT_TIMEZONE,
            timeout_seconds=300, max_attempts=2, retry_backoff_seconds=600, now=now),
    )


@dataclass(frozen=True)
class SeedOutcome:
    """What seeding did: what was created, what was left alone, and the schedule as it now stands."""

    created: tuple[str, ...]
    kept: tuple[str, ...]
    tasks: tuple[ScheduledTask, ...]

    def describe(self) -> str:
        parts = []
        if self.created:
            parts.append("created " + ", ".join(self.created))
        if self.kept:
            parts.append("left " + ", ".join(self.kept) + " exactly as they were")
        return "; ".join(parts) if parts else "nothing to do"


def seed_default_tasks(store, *, now: datetime | None = None) -> SeedOutcome:
    """Add the default tasks to a store that does not have them yet, and leave the rest untouched.

    A task that already exists is *not* re-saved, on purpose: re-saving would overwrite a person's
    choice of times, or turn a task they disabled back on, and neither is this function's to decide.
    Re-running it is therefore safe and boring, which is what an installation step should be.
    """
    moment = now or datetime.now(timezone.utc)
    created: list[str] = []
    kept: list[str] = []
    for task in default_tasks(now=moment):
        if store.get_scheduled_task(task.task_id) is not None:
            kept.append(task.task_id)
            continue
        store.save_scheduled_task(task, now=moment)
        created.append(task.task_id)
    return SeedOutcome(created=tuple(created), kept=tuple(kept), tasks=store.list_scheduled_tasks())
