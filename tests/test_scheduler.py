"""Tests for the scheduler engine (P3-C).

Covers: cron parsing, timezone-aware next-run computation, DST boundaries,
restart recovery, duplicate/overlapping-run prevention, bounded retries,
cancellation, and malformed schedule data. All time is injected
deterministically by monkeypatching career_agent.scheduler._now; there are
no real-time sleeps.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import career_agent.scheduler as scheduler_module
from career_agent.core import JobListing
from career_agent.scheduler import (
    ScheduleDefinition,
    SchedulerEngine,
    SchedulerStatus,
    compute_next_run,
)
from career_agent.store import CareerStore, StoredRecordError

UTC = timezone.utc


@pytest.fixture
def store(tmp_path: Path) -> CareerStore:
    s = CareerStore(str(tmp_path / "scheduler.db"))
    s.save_job(
        JobListing(
            listing_id="j1",
            source_id="fixture-src",
            source_name="Fixture Source",
            source_listing_url="https://fixture.example/j1",
            employer_name="Fixture Employer",
            role_title="AI Intern",
        )
    )
    return s


class FakeClock:
    """Deterministic clock replacing career_agent.scheduler._now."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime.now(UTC)

    def __call__(self) -> str:
        return self._now.isoformat(timespec="seconds")

    def advance(self, **kwargs) -> None:
        self._now = self._now + timedelta(**kwargs)

    def rewind(self, **kwargs) -> None:
        self._now = self._now - timedelta(**kwargs)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    ck = FakeClock()
    monkeypatch.setattr(scheduler_module, "_now", ck)
    return ck


def make_schedule(
    schedule_id: str = "s1",
    *,
    cron: str = "30 9 * * *",
    tz: str = "America/New_York",
) -> ScheduleDefinition:
    return ScheduleDefinition(
        id=schedule_id,
        name="daily discovery",
        job_listing_id="j1",
        cron_expression=cron,
        timezone=tz,
    )


# ---------------------------------------------------------------- cron parsing


class TestCronComputation:
    def test_daily_utc(self) -> None:
        after = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)
        assert compute_next_run("30 9 * * *", "UTC", after) == datetime(
            2026, 10, 21, 9, 30, tzinfo=UTC
        )

    def test_plain_wildcard_advances_one_minute(self) -> None:
        after = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)
        assert compute_next_run("* * * * *", "UTC", after) == datetime(
            2026, 10, 20, 10, 1, tzinfo=UTC
        )

    def test_step_every_15_minutes(self) -> None:
        after = datetime(2026, 10, 20, 10, 7, tzinfo=UTC)
        assert compute_next_run("*/15 * * * *", "UTC", after) == datetime(
            2026, 10, 20, 10, 15, tzinfo=UTC
        )

    def test_range_with_step(self) -> None:
        after = datetime(2026, 10, 20, 10, 55, tzinfo=UTC)
        assert compute_next_run("10-50/10 * * * *", "UTC", after) == datetime(
            2026, 10, 20, 11, 10, tzinfo=UTC
        )

    def test_weekday_name_next_monday(self) -> None:
        after = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)  # Tuesday
        assert compute_next_run("0 9 * * mon", "UTC", after) == datetime(
            2026, 10, 26, 9, 0, tzinfo=UTC
        )

    def test_month_name(self) -> None:
        after = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)
        assert compute_next_run("0 9 1 jan *", "UTC", after) == datetime(
            2027, 1, 1, 9, 0, tzinfo=UTC
        )

    def test_wrap_weekday_range(self) -> None:
        # 5-7 == Friday-Sunday; after is Tuesday Oct 20 -> next Friday Oct 23
        after = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)
        assert compute_next_run("0 9 * * 5-7", "UTC", after) == datetime(
            2026, 10, 23, 9, 0, tzinfo=UTC
        )

    def test_wrap_reverse_range_7_to_1(self) -> None:
        # 7-1 == Sunday+Monday (7 -> Sunday=0, wrap to Monday=1). The next
        # matching *minute* after the day jump is midnight Sunday, because
        # `* *` matches hour/minute 00:00.
        after = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)
        assert compute_next_run("* * * * 7-1", "UTC", after) == datetime(
            2026, 10, 25, 0, 0, tzinfo=UTC
        )

    def test_cron_dow_numbering_matches_standard_cron(self) -> None:
        # Standard cron: 0/7=Sunday, 1=Monday, 5=Friday, 6=Saturday
        after = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)  # Tuesday
        assert compute_next_run("0 9 * * 0", "UTC", after) == datetime(
            2026, 10, 25, 9, 0, tzinfo=UTC
        )
        assert compute_next_run("0 9 * * 5", "UTC", after) == datetime(
            2026, 10, 23, 9, 0, tzinfo=UTC
        )

    def test_dom_or_dow_semantics(self) -> None:
        # "1st of month OR any Monday": Oct 20 is Tue -> next Monday Oct 26
        after = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)
        assert compute_next_run("0 9 1 * 1", "UTC", after) == datetime(
            2026, 10, 26, 9, 0, tzinfo=UTC
        )

    def test_dst_winter_new_york_is_est(self) -> None:
        after = datetime(2026, 2, 1, 12, 0, tzinfo=UTC)
        assert compute_next_run("30 9 * * *", "America/New_York", after) == datetime(
            2026, 2, 1, 14, 30, tzinfo=UTC
        )

    def test_dst_summer_new_york_is_edt(self) -> None:
        after = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
        assert compute_next_run("30 9 * * *", "America/New_York", after) == datetime(
            2026, 6, 1, 13, 30, tzinfo=UTC
        )

    def test_spring_forward_skipped_local_time(self) -> None:
        # 02:30 local does not exist on 2026-03-08 in America/New_York
        # (spring forward). Policy: the nonexistent occurrence is skipped
        # and the job fires at the next matching local time (next day),
        # 02:30 EDT == 06:30 UTC.
        after = datetime(2026, 3, 7, 12, 0, tzinfo=UTC)
        result = compute_next_run("30 2 * * *", "America/New_York", after)
        assert result == datetime(2026, 3, 9, 6, 30, tzinfo=UTC)

    def test_fall_back_ambiguous_local_time_picks_first_occurrence(self) -> None:
        # 01:30 occurs twice on 2026-11-01; fold=0 semantics pick EDT (05:30Z)
        after = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
        result = compute_next_run("30 1 * * *", "America/New_York", after)
        assert result == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)

    def test_naive_after_treated_as_utc(self) -> None:
        assert compute_next_run("30 9 * * *", "UTC", datetime(2026, 10, 20, 10, 0)) == datetime(
            2026, 10, 21, 9, 30, tzinfo=UTC
        )

    @pytest.mark.parametrize(
        "expr",
        ["61 * * * *", "* * * *", "* * * * * *", "*/0 * * * *", "0 9 * * foo", "* * 31 4 *"],
    )
    def test_invalid_expressions_raise(self, expr: str) -> None:
        after = datetime(2026, 10, 20, tzinfo=UTC)
        with pytest.raises(ValueError):
            compute_next_run(expr, "UTC", after)

    def test_unknown_timezone_raises(self) -> None:
        with pytest.raises(ValueError):
            compute_next_run("* * * * *", "Not/AZone", datetime(2026, 10, 20, tzinfo=UTC))


# ---------------------------------------------------------------- persistence


class TestSchedulePersistence:
    def test_schedule_roundtrip(self, store: CareerStore, clock: FakeClock) -> None:
        engine = SchedulerEngine(store)
        definition = make_schedule()
        engine.schedule_job(definition)
        reloaded = engine.get_schedule("s1")
        assert reloaded is not None
        assert reloaded.cron_expression == "30 9 * * *"
        assert reloaded.timezone == "America/New_York"
        assert reloaded.created_at is not None
        # Next run respects the cron: 09:30 America/New_York on the next day
        expected_next = compute_next_run("30 9 * * *", "America/New_York", clock._now)
        assert reloaded.next_run_at == expected_next.isoformat()

    def test_next_run_not_clobbered_by_polling(self, store: CareerStore, clock: FakeClock) -> None:
        """Repeated check_due_runs calls before the due time must not push
        the schedule forever into the future."""
        engine = SchedulerEngine(store)
        definition = make_schedule("s2", cron="* * * * *")
        engine.schedule_job(definition)
        reloaded = engine.get_schedule("s2")
        assert reloaded.next_run_at is not None
        first_next = reloaded.next_run_at
        boundary = datetime.fromisoformat(first_next)
        # Anchor the injected clock 30 seconds before the due boundary
        clock._now = boundary - timedelta(seconds=30)
        # Poll every "second"; polling must never move the due time and
        # must not fire early.
        for _ in range(29):
            clock.advance(seconds=1)
            assert engine.check_due_runs() == ()
            got = engine.get_schedule("s2")
            assert got.next_run_at is not None
            assert got.next_run_at == first_next
        # At the boundary the run fires exactly once
        clock.advance(seconds=1)
        runs = engine.check_due_runs()
        assert len(runs) == 1
        assert runs[0].status is SchedulerStatus.RUNNING


# ---------------------------------------------------------------- execution


class TestRunExecution:
    def test_due_run_and_restart_recovery(self, store: CareerStore, clock: FakeClock) -> None:
        engine = SchedulerEngine(store)
        definition = make_schedule("s3")
        engine.schedule_job(definition)
        assert engine.check_due_runs() == ()

        # Simulate application close + restart: a brand new engine over the
        # same store sees the same persisted schedule.
        clock.advance(days=2)
        engine = SchedulerEngine(store)
        runs = engine.check_due_runs()
        assert len(runs) == 1
        assert runs[0].schedule_id == "s3"
        assert runs[0].status is SchedulerStatus.RUNNING
        # Missed-run policy: run once on resume, then compute the next
        # occurrence; no storm of catch-up runs.
        further = engine.check_due_runs()
        assert further == ()

    def test_overlapping_duplicate_prevention(
        self, store: CareerStore, clock: FakeClock
    ) -> None:
        engine = SchedulerEngine(store)
        definition = make_schedule("s4", cron="* * * * *")
        clock.rewind(seconds=30)
        engine.schedule_job(definition)
        clock.advance(minutes=2)  # past the first due minute
        first_next = engine.get_schedule("s4").next_run_at
        (first_run,) = engine.check_due_runs()
        # While the run is open, re-polling must not create duplicates even
        # if enough time passed for the next occurrence.
        clock.advance(minutes=5)
        assert engine.check_due_runs() == ()
        # Completing the run releases the schedule.
        ck_statuses = list(store.list_run_records())
        assert len(ck_statuses) == 1
        engine.complete_run(first_run.id, SchedulerStatus.COMPLETED)
        record = store.get_run_record(first_run.id)
        assert record.status is SchedulerStatus.COMPLETED
        assert record.completed_at is not None
        assert first_next is not None

    def test_failed_run_creates_bounded_retry(
        self, store: CareerStore, clock: FakeClock
    ) -> None:
        engine = SchedulerEngine(store)
        definition = make_schedule("s5", cron="* * * * *")
        definition.max_retries = 2
        clock.rewind(seconds=30)
        engine.schedule_job(definition)
        clock.advance(minutes=2)
        (run,) = engine.check_due_runs()
        engine.complete_run(run.id, SchedulerStatus.FAILED, error_message="boom")
        pending = engine.get_pending_runs()
        retries = [r for r in pending if r.id.startswith("run_s5_retry")]
        assert len(retries) == 1
        assert retries[0].status is SchedulerStatus.PENDING
        # Retry is scheduled in the future (exponential backoff, never
        # embedded in the past).
        assert engine.get_pending_runs()
        assert store.get_schedule_definition("s5") is not None

    def test_retry_not_created_beyond_max(
        self, store: CareerStore, clock: FakeClock
    ) -> None:
        engine = SchedulerEngine(store)
        definition = make_schedule("s6", cron="* * * * *")
        definition.max_retries = 1
        clock.rewind(seconds=30)
        engine.schedule_job(definition)
        clock.advance(minutes=2)
        (run,) = engine.check_due_runs()
        # Simulate a repeatedly failing run whose retry budget is exhausted.
        run.retry_count = 1
        store.save_run_record(run)
        engine.complete_run(run.id, SchedulerStatus.FAILED, error_message="again")
        pending = [
            r
            for r in store.list_run_records()
            if r.id.startswith("run_s6_retry")
        ]
        assert pending == []

    def test_cancel_running_run(self, store: CareerStore, clock: FakeClock) -> None:
        engine = SchedulerEngine(store)
        definition = make_schedule("s7", cron="* * * * *")
        clock.rewind(seconds=30)
        engine.schedule_job(definition)
        clock.advance(minutes=2)
        (run,) = engine.check_due_runs()
        engine.cancel_run(run.id)
        record = store.get_run_record(run.id)
        assert record.status is SchedulerStatus.CANCELLED
        assert record.completed_at is not None

    def test_interrupted_runs_surface_after_restart(
        self, store: CareerStore, clock: FakeClock
    ) -> None:
        """A run still marked RUNNING after the process died is reported as
        needing attention instead of vanishing silently."""
        engine = SchedulerEngine(store)
        definition = make_schedule("s8", cron="* * * * *")
        clock.rewind(seconds=30)
        engine.schedule_job(definition)
        clock.advance(minutes=2)
        (run,) = engine.check_due_runs()
        # Process dies without complete_run ever being called; new engine
        engine = SchedulerEngine(store)
        pending = engine.get_pending_runs()
        assert any(r.id == run.id and r.status is SchedulerStatus.RUNNING for r in pending)


# ---------------------------------------------------------------- schedule data


class TestScheduleDataSafety:
    def test_invalid_cron_disables_schedule_with_reason(
        self, store: CareerStore, clock: FakeClock
    ) -> None:
        engine = SchedulerEngine(store)
        definition = make_schedule("s9", cron="not-a-cron")
        engine.schedule_job(definition)
        reloaded = engine.get_schedule("s9")
        assert reloaded.enabled is False
        assert reloaded.description is not None
        assert "invalid schedule" in reloaded.description

    def test_unknown_timezone_disables_schedule(
        self, store: CareerStore, clock: FakeClock
    ) -> None:
        engine = SchedulerEngine(store)
        definition = make_schedule("s10", tz="Bad/Zone")
        engine.schedule_job(definition)
        reloaded = engine.get_schedule("s10")
        assert reloaded.enabled is False

    def test_malformed_stored_schedule_raises_structured_error(
        self, store: CareerStore
    ) -> None:
        """Corrupted persisted payloads surface a typed store error, not a
        raw KeyError/TypeError out of the dataclass constructor."""
        store._connection.execute(
            "INSERT INTO schedules(id, name, job_listing_id, cron_expression, timezone,"
            " enabled, created_at, last_run_at, next_run_at, max_retries, description, payload)"
            " VALUES ('bad', 'x', 'j1', '* * * * *', 'UTC', 1, NULL, NULL, NULL, 3, NULL, '{}')"
        )
        with pytest.raises(StoredRecordError):
            store.list_schedule_definitions()

    def test_list_schedules_empty(self, store: CareerStore) -> None:
        assert SchedulerEngine(store).list_schedules() == ()
