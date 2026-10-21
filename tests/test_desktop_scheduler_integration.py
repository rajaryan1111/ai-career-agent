"""Integration tests: desktop runtime <-> SchedulerEngine <-> store <-> notifications.

Headless: no real Tk root is required. The app object is built via
``CareerAgentApp.__new__`` and wired with a fake UI root that records
``after``/``after_cancel`` calls, exactly the seam the real Tk event loop
occupies. The existing stub-widget desktop tests already exercise the full
``__init__`` path (including scheduler startup) through their fake Tk stack.

All state is authoritative SQLite state in a temporary directory; no email is
sent and no application is submitted anywhere in these tests.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import career_agent.desktop as desktop
from career_agent.core import Availability, JobListing
from career_agent.notifications import NotificationStatus
from career_agent.scheduler import (
    RunRecord,
    ScheduleDefinition,
    SchedulerEngine,
    SchedulerStatus,
)
from career_agent.store import CareerStore


class StatusRecorder:
    """Stands in for the Tk StringVar used by the status bar."""

    def __init__(self):
        self.values = []

    def set(self, value):
        self.values.append(value)


class FakeRoot:
    """Minimal stand-in for the Tk root event-loop surface."""

    def __init__(self, *, supports_after: bool = True):
        self._timers: list[tuple[int, int, object]] = []
        self.destroyed = False
        if not supports_after:
            # Headless roots without an event loop expose no after() at all;
            # the app must detect that via getattr, not by exception.
            self.after = None

    def after(self, ms, callback=None):
        token = len(self._timers) + 1
        self._timers.append((token, ms, callback))
        return token

    def after_cancel(self, token):
        self._timers = [t for t in self._timers if t[0] != token]

    def destroy(self):
        self.destroyed = True

    @property
    def pending_callbacks(self):
        return [cb for (_t, _ms, cb) in self._timers]


def make_listing(store: CareerStore, listing_id: str = "j1") -> None:
    store.save_job(
        JobListing(
            listing_id=listing_id,
            source_id="fixture-source",
            source_name="Fixture Source",
            source_listing_url=f"https://fixture.example/{listing_id}",
            employer_name="Fixture Employer",
            role_title="AI Intern",
            availability_status=Availability.OPEN,
        )
    )


def make_app(store: CareerStore, root: FakeRoot) -> desktop.CareerAgentApp:
    """Build a CareerAgentApp wired for headless integration testing."""
    app = desktop.CareerAgentApp.__new__(desktop.CareerAgentApp)
    app.root = root
    app.store = store
    app.notification_manager = desktop.NotificationManager(store)
    return app


def run_tick(app: desktop.CareerAgentApp) -> None:
    """Consume the armed poll timer, as the real Tk event loop would, then
    execute one scheduler tick. After this returns exactly one timer (the
    freshly re-armed poll) is pending on the fake root."""
    if getattr(app, "_scheduler_after_id", None) is not None:
        app.root.after_cancel(app._scheduler_after_id)
    app._scheduler_tick()


@pytest.fixture
def workspace(tmp_path: Path):
    store = CareerStore(str(tmp_path / "integration.db"))
    make_listing(store)
    yield store
    store.close()


def delete_without_foreign_keys(store: CareerStore, statement: str, params: tuple = ()) -> None:
    """Remove a row the way a legacy restored database (no FK enforcement)
    would leave it: orphaned records remain and surface at runtime. Used
    to reach the defensive branches in the desktop scheduler wiring."""
    store._connection.execute("PRAGMA foreign_keys = OFF")
    store._connection.execute(statement, params)
    store._connection.execute("PRAGMA foreign_keys = ON")
    store._connection.commit()


def make_due_schedule(store: CareerStore, schedule_id: str = "s1") -> RunRecord:
    """Persist a schedule whose next_run_at is in the past, plus a live run."""
    engine = SchedulerEngine(store)
    definition = ScheduleDefinition(
        id=schedule_id,
        name="daily follow-up",
        job_listing_id="j1",
        cron_expression="30 9 * * *",
        timezone="America/New_York",
    )
    engine.schedule_job(definition)
    definition.next_run_at = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    store.save_schedule_definition(definition)
    run = RunRecord(
        id=f"run_{schedule_id}",
        schedule_id=schedule_id,
        status=SchedulerStatus.RUNNING,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    store.save_run_record(run)
    return run


class TestSchedulerRuntime:
    def test_startup_recovers_interrupted_runs_and_starts_polling(
        self, workspace: CareerStore
    ):
        run = make_due_schedule(workspace)
        root = FakeRoot()
        app = make_app(workspace, root)

        app._start_scheduler_runtime()

        finished = workspace.get_run_record(run.id)
        assert finished.status is SchedulerStatus.FAILED
        assert "interrupted by application restart" in finished.error_message
        # Bounded retry: one PENDING retry record exists, still under the limit.
        retries = [
            r
            for r in workspace.list_run_records()
            if r.id.startswith("run_s1_retry")
        ]
        assert len(retries) == 1
        assert retries[0].status is SchedulerStatus.PENDING
        # Exactly one polling timer is armed.
        assert len(root.pending_callbacks) == 1

    def test_due_run_creates_persistent_notification(
        self, workspace: CareerStore
    ):
        original_run = make_due_schedule(workspace)
        root = FakeRoot()
        app = make_app(workspace, root)
        app._start_scheduler_runtime()

        run_tick(app)

        # The original interrupted run was failed by startup recovery ...
        recovered = workspace.get_run_record(original_run.id)
        assert recovered.status is SchedulerStatus.FAILED
        assert "interrupted by application restart" in recovered.error_message
        # ... and the tick executed its own fresh run to completion.
        completed = [
            r
            for r in workspace.list_run_records()
            if r.status is SchedulerStatus.COMPLETED
            and r.output is not None
            and "AI Intern" in r.output
            and "Fixture Employer" in r.output
        ]
        assert len(completed) == 1
        pending = workspace.get_pending_notifications()
        assert len(pending) == 1
        assert pending[0].dedup_key.startswith("schedule:s1:")
        assert pending[0].status is NotificationStatus.PENDING
        # Polling was re-armed after the tick.
        assert len(root.pending_callbacks) == 1

    def test_second_same_day_execution_does_not_duplicate_notification(
        self, workspace: CareerStore
    ):
        make_due_schedule(workspace)
        root = FakeRoot()
        app = make_app(workspace, root)
        app._start_scheduler_runtime()
        run_tick(app)
        assert len(workspace.get_pending_notifications()) == 1

        # A second due run for the same schedule on the same day (as another
        # tick or poll could produce) must hit the dedup key and not add a
        # second reminder.
        second_run = RunRecord(
            id="run_s1_again",
            schedule_id="s1",
            status=SchedulerStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        workspace.save_run_record(second_run)
        app._execute_scheduled_run(second_run)

        pending = workspace.get_pending_notifications()
        assert len(pending) == 1
        finished = workspace.get_run_record("run_s1_again")
        assert finished.status is SchedulerStatus.COMPLETED
        assert "already pending" in finished.output

    def test_restart_recovery_without_notification_storm(
        self, workspace: CareerStore
    ):
        """Simulate close then restart over the same database: pending
        notification state stays authoritative and avoids duplicates."""
        make_due_schedule(workspace)
        app = make_app(workspace, FakeRoot())
        app._start_scheduler_runtime()
        run_tick(app)
        assert len(workspace.get_pending_notifications()) == 1

        # Simulate a restart: a brand-new app runtime over the SAME store.
        restarted_app = make_app(workspace, FakeRoot())
        restarted_app._start_scheduler_runtime()
        # A new due run after restart on the same day must hit the pending
        # dedup key and therefore not duplicate the reminder.
        restart_run = RunRecord(
            id="run_s1_after_restart",
            schedule_id="s1",
            status=SchedulerStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        workspace.save_run_record(restart_run)
        restarted_app._execute_scheduled_run(restart_run)
        finished = workspace.get_run_record("run_s1_after_restart")
        assert finished.status is SchedulerStatus.COMPLETED
        assert "already pending" in finished.output
        assert len(workspace.get_pending_notifications()) == 1

    def test_engine_failure_reported_and_polling_continues(
        self, workspace: CareerStore, monkeypatch: pytest.MonkeyPatch
    ):
        make_due_schedule(workspace)
        root = FakeRoot()
        app = make_app(workspace, root)
        app.status = StatusRecorder()
        app._start_scheduler_runtime()
        timers_before = len(root._timers)

        def explode():
            raise RuntimeError("store locked")

        monkeypatch.setattr(app.scheduler_engine, "check_due_runs", explode)
        run_tick(app)

        assert any("RuntimeError" in value for value in app.status.values)
        # Polling continues beyond the failure: a new timer is queued.
        assert len(root._timers) > timers_before - 1  # no fewer than before the tick minus consumption
        assert root.pending_callbacks

    def test_missing_job_listing_fails_run_with_reason(self, workspace: CareerStore):
        """A restored legacy database can hold a schedule for a job listing
        that is no longer stored. The newest run must fail with an explicit,
        actionable reason instead of crashing the tick."""
        make_due_schedule(workspace)
        delete_without_foreign_keys(
            workspace, "DELETE FROM job_listings WHERE listing_id='j1'"
        )
        root = FakeRoot()
        app = make_app(workspace, root)
        app._start_scheduler_runtime()

        run_tick(app)

        failed = [
            r
            for r in workspace.list_run_records()
            if r.status is SchedulerStatus.FAILED
            and r.error_message == "job listing no longer stored"
        ]
        assert failed, "the tick run for the missing listing must fail with a reason"

    def test_missing_schedule_definition_fails_run(self, workspace: CareerStore):
        """A restored database can hold a run whose schedule row is gone. The
        executor must fail the run with an explicit reason (defensive branch,
        exercised directly because check_due_runs iterates schedules)."""
        make_due_schedule(workspace)
        delete_without_foreign_keys(workspace, "DELETE FROM schedules WHERE id='s1'")
        root = FakeRoot()
        app = make_app(workspace, root)
        app._start_scheduler_runtime()

        orphan_run = RunRecord(
            id="run_orphan",
            schedule_id="s1",
            status=SchedulerStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        workspace.save_run_record(orphan_run)
        app._execute_scheduled_run(orphan_run)

        finished = workspace.get_run_record("run_orphan")
        assert finished.status is SchedulerStatus.FAILED
        assert finished.error_message == "schedule definition missing"

    def test_disabled_schedule_run_is_cancelled(self, workspace: CareerStore):
        make_due_schedule(workspace)
        schedule = workspace.get_schedule_definition("s1")
        schedule.enabled = False
        workspace.save_schedule_definition(schedule)
        root = FakeRoot()
        app = make_app(workspace, root)
        app._start_scheduler_runtime()

        # A due run reaching the executor while the schedule is disabled is
        # cancelled, never executed.
        running = RunRecord(
            id="run_disabled",
            schedule_id="s1",
            status=SchedulerStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        workspace.save_run_record(running)
        app._execute_scheduled_run(running)

        finished = workspace.get_run_record("run_disabled")
        assert finished.status is SchedulerStatus.CANCELLED
        assert finished.error_message == "schedule disabled"
        assert workspace.get_pending_notifications() == ()

    def test_graceful_shutdown_cancels_pending_timer(self, workspace: CareerStore):
        make_due_schedule(workspace)
        root = FakeRoot()
        app = make_app(workspace, root)
        app._start_scheduler_runtime()
        run_tick(app)
        assert len(root.pending_callbacks) == 1

        app.close()

        assert root.pending_callbacks == []  # the pending poll was cancelled
        assert app._scheduler_closing is True
        assert app._scheduler_polling_active is False
        assert root.destroyed is True

    def test_shutdown_snapshot_state_is_safe_without_timers(self, workspace: CareerStore):
        root = FakeRoot(supports_after=False)
        app = make_app(workspace, root)
        app._start_scheduler_runtime()  # headless roots without after() simply do not poll
        app._scheduler_schedule_tick()
        assert root._timers == []
        app.close()
        assert root.destroyed is True

    def test_polling_timer_uses_controlled_interval(self, workspace: CareerStore):
        make_due_schedule(workspace)
        root = FakeRoot()
        app = make_app(workspace, root)
        app._start_scheduler_runtime()
        _token, ms, callback = root._timers[0]
        assert ms == desktop.SCHEDULER_POLL_MS
        assert callback == app._scheduler_tick

    def test_no_duplicate_polling_loop_rearm_only_once_per_tick(
        self, workspace: CareerStore
    ):
        make_due_schedule(workspace)
        root = FakeRoot()
        app = make_app(workspace, root)
        app._start_scheduler_runtime()
        assert len(root.pending_callbacks) == 1
        run_tick(app)
        assert len(root.pending_callbacks) == 1  # consumed one, re-armed exactly one
        run_tick(app)
        assert len(root.pending_callbacks) == 1  # never more than one loop
