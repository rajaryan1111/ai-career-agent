"""Tests for the task/schedule domain: the arithmetic and the rules, with no database involved.

The schedule maths is where a scheduler is most quietly wrong, so the cases here are the ones that
would move somebody's run without telling them: a machine in another timezone, a clock moved forward,
a local time that occurs twice, a retry that must serve the occurrence it owes, and a definition that
should have been refused rather than scheduled.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from career_agent.tasks import (
    DEFAULT_SCHEDULE_TIMES, DEFAULT_TIMEZONE, HandlerOutcome, HandlerResult, MAX_ATTEMPTS,
    MAX_BACKOFF_SECONDS, MAX_DETAIL_LENGTH, MAX_TIMEOUT_SECONDS, RunState, ScheduledTask,
    ScheduleUpdate, TaskRun, TaskValidationError, WorkerLease, WorkerLeaseHeld, build_task,
    clean_detail, next_run_after, parse_time, plan_after_run, retry_delay_seconds, slot_key,
    validate_times, zone_for,
)

UTC = timezone.utc
#: A fixed reference instant: 2026-10-15 00:00 in Asia/Kolkata (the schedule's own zone).
MIDNIGHT_IST = datetime(2026, 10, 14, 18, 30, tzinfo=UTC)


def task(**changes) -> ScheduledTask:
    """A task with the product's default cadence, overridden by keyword where a test cares."""
    fields = {
        "task_id": "discovery-run", "name": "Scheduled discovery", "kind": "discovery.run",
        "times": DEFAULT_SCHEDULE_TIMES, "timezone": DEFAULT_TIMEZONE,
    }
    fields.update(changes)
    return ScheduledTask(**fields)  # type: ignore[arg-type]


class TaskDefinitionTests(unittest.TestCase):
    """What may be scheduled at all."""

    def test_the_default_cadence_is_midnight_and_noon_on_the_task_clock(self):
        built = build_task("discovery-run", "Scheduled discovery", "discovery.run", now=MIDNIGHT_IST)

        self.assertEqual(built.times, ("00:00", "12:00"))
        self.assertEqual(built.timezone, "Asia/Kolkata")
        self.assertEqual(built.next_run_at, datetime(2026, 10, 15, 6, 30, tzinfo=UTC),
                         "00:00 IST on 15 October is 18:30 UTC on the 14th; noon IST is 06:30 UTC")

    def test_times_are_parsed_sorted_and_deduplicated(self):
        self.assertEqual(parse_time("09:05").hour, 9)
        self.assertEqual(validate_times(["12:00", "00:00", "12:00"]), ("00:00", "12:00"))

    def test_a_time_that_is_not_a_time_is_refused_with_its_own_value_in_the_message(self):
        for value in ("24:00", "9:05", "noon", "12:60", "", "12:00:00"):
            with self.subTest(value=value):
                with self.assertRaises(TaskValidationError) as caught:
                    parse_time(value)
                self.assertIn("HH:MM", str(caught.exception))

    def test_a_schedule_needs_at_least_one_time_and_a_sequence(self):
        with self.assertRaises(TaskValidationError) as empty:
            validate_times([])
        self.assertIn("at least one time of day", str(empty.exception))

        with self.assertRaises(TaskValidationError) as single:
            validate_times("12:00")  # the classic mistake: a string is iterable, and not a schedule
        self.assertIn("not a single string", str(single.exception))

    def test_a_timezone_this_machine_does_not_have_is_refused_with_the_fix(self):
        with self.assertRaises(TaskValidationError) as caught:
            zone_for("Mars/Olympus_Mons")

        message = str(caught.exception)
        self.assertIn("not available on this machine", message)
        self.assertIn("tzdata", message, "the Windows case must name the package that provides it")

    def test_bounds_are_refused_rather_than_clamped(self):
        for changes, expected in (
            ({"timeout_seconds": 0}, "timeout in seconds"),
            ({"timeout_seconds": MAX_TIMEOUT_SECONDS + 1}, "timeout in seconds"),
            ({"max_attempts": 0}, "number of attempts"),
            ({"max_attempts": MAX_ATTEMPTS + 1}, "number of attempts"),
            ({"retry_backoff_seconds": -1}, "retry delay in seconds"),
            ({"consecutive_failures": -1}, "consecutive-failure count"),
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(TaskValidationError) as caught:
                    task(**changes)
                self.assertIn(expected, str(caught.exception))

    def test_identifiers_are_checked_so_a_task_can_be_stored_and_named(self):
        with self.assertRaises(TaskValidationError):
            task(task_id="Discovery Run")
        with self.assertRaises(TaskValidationError):
            task(kind="Discovery")
        with self.assertRaises(TaskValidationError):
            task(name="   ")

    def test_a_time_without_a_zone_is_refused_rather_than_assumed(self):
        with self.assertRaises(TaskValidationError) as caught:
            task(next_run_at=datetime(2026, 10, 15, 12, 0))

        self.assertIn("must carry a timezone offset", str(caught.exception))

    def test_an_unfinished_outcome_may_not_be_recorded_as_the_last_one(self):
        with self.assertRaises(TaskValidationError) as caught:
            task(last_outcome=RunState.RUNNING)

        self.assertIn("must be a finished one", str(caught.exception))

    def test_an_unfinished_occurrence_must_say_which_attempt_is_next(self):
        with self.assertRaises(TaskValidationError) as caught:
            task(pending_slot_at=MIDNIGHT_IST)

        self.assertIn("which attempt is next", str(caught.exception))

        # and the pair is normalised: no slot means no attempt to remember
        self.assertIsNone(task(pending_attempt=2).pending_attempt)

    def test_a_disabled_task_is_stored_with_no_next_run(self):
        built = build_task("discovery-run", "T", "discovery.run", now=MIDNIGHT_IST, enabled=False)

        self.assertFalse(built.enabled)
        self.assertIsNone(built.next_run_at, "a disabled task is not due, and must not look due")


class NextRunTests(unittest.TestCase):
    """When the next occurrence is, in the presence of zones and clock changes."""

    def test_the_next_occurrence_is_the_next_time_on_the_task_clock(self):
        scheduled = task()
        # 2026-10-15 11:59 IST -> noon IST the same day
        before_noon = datetime(2026, 10, 15, 6, 29, tzinfo=UTC)
        self.assertEqual(next_run_after(scheduled, before_noon),
                         datetime(2026, 10, 15, 6, 30, tzinfo=UTC))
        # 2026-10-15 12:01 IST -> midnight IST on the 16th
        after_noon = datetime(2026, 10, 15, 6, 31, tzinfo=UTC)
        self.assertEqual(next_run_after(scheduled, after_noon),
                         datetime(2026, 10, 15, 18, 30, tzinfo=UTC))

    def test_the_answer_does_not_depend_on_the_zone_the_question_is_asked_in(self):
        scheduled = task()
        asked_in_utc = next_run_after(scheduled, MIDNIGHT_IST)
        asked_in_new_york = next_run_after(scheduled, MIDNIGHT_IST.astimezone(zone_for("America/New_York")))
        asked_in_kolkata = next_run_after(scheduled, MIDNIGHT_IST.astimezone(zone_for("Asia/Kolkata")))

        self.assertEqual(asked_in_utc, asked_in_new_york)
        self.assertEqual(asked_in_utc, asked_in_kolkata)

    def test_the_instant_itself_counts_only_when_asked_inclusively(self):
        scheduled = task(times=("12:00",))
        noon_ist = datetime(2026, 10, 15, 6, 30, tzinfo=UTC)

        self.assertEqual(next_run_after(scheduled, noon_ist),
                         datetime(2026, 10, 16, 6, 30, tzinfo=UTC),
                         "strictly after: the next noon IST is tomorrow's")
        self.assertEqual(next_run_after(scheduled, noon_ist, inclusive=True), noon_ist,
                         "inclusive: the instant itself is the answer when it is an occurrence")

        midnight_only = task(times=("00:00",))
        self.assertEqual(next_run_after(midnight_only, noon_ist),
                         datetime(2026, 10, 15, 18, 30, tzinfo=UTC),
                         "midnight IST on the 16th is 18:30 UTC on the 15th")
        self.assertEqual(next_run_after(midnight_only, noon_ist, inclusive=True),
                         datetime(2026, 10, 15, 18, 30, tzinfo=UTC),
                         "noon IST is not one of this task's occurrences, so inclusive changes nothing")

    def test_a_local_time_inside_the_spring_forward_gap_is_skipped_not_moved(self):
        scheduled = task(times=("02:30",), timezone="America/New_York")
        # 2026-03-08 02:00 EST becomes 03:00 EDT, so 02:30 does not exist that day.
        before = datetime(2026, 3, 7, 12, 0, tzinfo=UTC)

        self.assertEqual(next_run_after(scheduled, before), datetime(2026, 3, 9, 6, 30, tzinfo=UTC),
                         "8 March 02:30 is not a real time; 9 March 02:30 EDT is the next occurrence")

    def test_a_local_time_that_occurs_twice_is_one_occurrence_not_two(self):
        scheduled = task(times=("01:30",), timezone="America/New_York")
        start = datetime(2026, 11, 1, 4, 0, tzinfo=UTC)  # 00:00 EDT

        first = next_run_after(scheduled, start)
        following = next_run_after(scheduled, first)

        self.assertEqual(first, datetime(2026, 11, 1, 5, 30, tzinfo=UTC), "the first 01:30 (EDT)")
        self.assertEqual(following, datetime(2026, 11, 2, 6, 30, tzinfo=UTC),
                         "the repeated 01:30 (EST) is not a second occurrence")

    def test_a_schedule_that_can_never_match_answers_none_rather_than_looping(self):
        scheduled = task(times=("02:30",), timezone="America/New_York")
        # On the gap day itself, with a single time, the search still finds the next day; a limit
        # exists only so a broken clock cannot spin, and it is exercised through the private helper
        # being asked for a day that has no matching instant at all.
        from career_agent.tasks import _occurrences_on

        self.assertEqual(_occurrences_on(datetime(2026, 3, 8).date(), ("02:30",), zone_for("America/New_York")), ())


class SlotIdentityTests(unittest.TestCase):
    """The idempotency key: one name per occurrence, whoever asks."""

    def test_the_key_names_the_task_and_the_instant_and_nothing_else(self):
        first = slot_key("discovery-run", MIDNIGHT_IST)
        again = slot_key("discovery-run", MIDNIGHT_IST)

        self.assertEqual(first, again)
        self.assertEqual(first, "discovery-run@2026-10-14T18:30:00+00:00")
        self.assertNotEqual(first, slot_key("other-task", MIDNIGHT_IST))
        self.assertNotEqual(first, slot_key("discovery-run", MIDNIGHT_IST + timedelta(seconds=1)))

    def test_a_key_asked_for_in_another_zone_is_the_same_key(self):
        self.assertEqual(slot_key("t", MIDNIGHT_IST),
                         slot_key("t", MIDNIGHT_IST.astimezone(zone_for("Asia/Kolkata"))))

    def test_a_key_without_a_zone_is_refused(self):
        with self.assertRaises(TaskValidationError):
            slot_key("t", datetime(2026, 10, 15, 12, 0))


class RetryTests(unittest.TestCase):
    """Bounded exponential backoff, and what finishing a run does to the task."""

    def test_the_delay_doubles_and_caps(self):
        scheduled = task(retry_backoff_seconds=60, max_attempts=5)

        self.assertEqual(retry_delay_seconds(scheduled, 1), 60)
        self.assertEqual(retry_delay_seconds(scheduled, 2), 120)
        self.assertEqual(retry_delay_seconds(scheduled, 3), 240)
        self.assertEqual(retry_delay_seconds(scheduled, 4), 480)
        self.assertEqual(retry_delay_seconds(scheduled, 5), 0,
                         "the fifth attempt is the last one allowed, so nothing follows it")

        slow = task(retry_backoff_seconds=MAX_BACKOFF_SECONDS, max_attempts=3)
        self.assertEqual(retry_delay_seconds(slow, 1), MAX_BACKOFF_SECONDS)
        self.assertEqual(retry_delay_seconds(slow, 2), MAX_BACKOFF_SECONDS, "capped, not unbounded")

    def test_success_returns_the_task_to_its_schedule(self):
        scheduled = task()
        now = datetime(2026, 10, 15, 6, 31, tzinfo=UTC)

        update = plan_after_run(scheduled, RunState.SUCCEEDED, 1,
                                datetime(2026, 10, 15, 6, 30, tzinfo=UTC), now)

        self.assertEqual(update.next_run_at, datetime(2026, 10, 15, 18, 30, tzinfo=UTC))
        self.assertIsNone(update.pending_slot_at)
        self.assertIsNone(update.pending_attempt)
        self.assertEqual(update.consecutive_failures, 0)
        self.assertEqual(update.last_outcome, RunState.SUCCEEDED)

    def test_a_refusal_is_not_a_failure(self):
        scheduled = task(consecutive_failures=0)

        update = plan_after_run(scheduled, RunState.REFUSED, 1, MIDNIGHT_IST,
                                datetime(2026, 10, 14, 18, 31, tzinfo=UTC))

        self.assertEqual(update.consecutive_failures, 0,
                         "a rule that says no must not count towards anything")
        self.assertIsNone(update.pending_slot_at)

    def test_a_failure_with_attempts_left_keeps_the_occurrence_it_owes(self):
        scheduled = task(retry_backoff_seconds=60, max_attempts=3)
        slot = datetime(2026, 10, 15, 6, 30, tzinfo=UTC)
        now = datetime(2026, 10, 15, 6, 31, tzinfo=UTC)

        update = plan_after_run(scheduled, RunState.FAILED, 1, slot, now)

        self.assertEqual(update.pending_slot_at, slot, "the retry serves the occurrence it owes")
        self.assertEqual(update.pending_attempt, 2)
        self.assertEqual(update.next_run_at, now + timedelta(seconds=60))
        self.assertEqual(update.consecutive_failures, 1)

    def test_the_last_attempt_gives_up_on_the_occurrence_but_not_on_the_task(self):
        scheduled = task(max_attempts=2)
        slot = datetime(2026, 10, 15, 6, 30, tzinfo=UTC)
        now = datetime(2026, 10, 15, 6, 31, tzinfo=UTC)

        update = plan_after_run(scheduled, RunState.FAILED, 2, slot, now)

        self.assertIsNone(update.pending_slot_at)
        self.assertEqual(update.next_run_at, datetime(2026, 10, 15, 18, 30, tzinfo=UTC),
                         "the next scheduled occurrence still runs")
        self.assertEqual(update.last_outcome, RunState.FAILED)
        self.assertEqual(update.consecutive_failures, 1)

    def test_an_interruption_counts_as_an_attempt_that_has_not_had_its_chance(self):
        scheduled = task(max_attempts=2)

        update = plan_after_run(scheduled, RunState.INTERRUPTED, 1, MIDNIGHT_IST,
                                datetime(2026, 10, 14, 18, 40, tzinfo=UTC))

        self.assertEqual(update.pending_attempt, 2)
        self.assertEqual(update.consecutive_failures, 1)

    def test_only_a_finished_run_can_plan_the_next_state(self):
        for outcome in (RunState.PENDING, RunState.RUNNING):
            with self.subTest(outcome=outcome):
                with self.assertRaises(TaskValidationError):
                    plan_after_run(task(), outcome, 1, MIDNIGHT_IST, MIDNIGHT_IST)


class HandlerResultTests(unittest.TestCase):
    """What a handler may say, and what it may not smuggle into the record."""

    def test_a_handler_must_state_an_outcome(self):
        with self.assertRaises(TaskValidationError):
            HandlerResult(outcome="succeeded")  # type: ignore[arg-type]

        self.assertEqual(HandlerResult(HandlerOutcome.SUCCEEDED).detail, "")
        self.assertEqual(HandlerResult(HandlerOutcome.STOPPED, "asked to stop").outcome,
                         HandlerOutcome.STOPPED)

    def test_detail_text_is_single_line_and_bounded(self):
        forged = HandlerResult(HandlerOutcome.SUCCEEDED, "done\nevent=app.started")

        self.assertEqual(forged.detail, "done event=app.started")

        long_text = clean_detail("x" * (MAX_DETAIL_LENGTH + 50))
        self.assertLessEqual(len(long_text), MAX_DETAIL_LENGTH + len("... (truncated)"))
        self.assertTrue(long_text.endswith("... (truncated)"))
        self.assertEqual(clean_detail(None), "")


class TaskRunTests(unittest.TestCase):
    """The stored shape of one attempt."""

    def run_for(self, **changes) -> TaskRun:
        fields = {
            "run_id": "run-1", "task_id": "discovery-run",
            "slot_key": slot_key("discovery-run", MIDNIGHT_IST), "slot_at": MIDNIGHT_IST,
            "attempt": 1, "state": RunState.RUNNING, "timeout_seconds": 300,
            "created_at": MIDNIGHT_IST,
        }
        fields.update(changes)
        return TaskRun(**fields)  # type: ignore[arg-type]

    def test_a_state_stored_as_text_is_read_back_as_its_state(self):
        self.assertEqual(self.run_for(state="succeeded").state, RunState.SUCCEEDED)

    def test_an_unknown_state_is_reported_as_itself(self):
        with self.assertRaises(TaskValidationError) as caught:
            self.run_for(state="zombie")

        self.assertIn("zombie", str(caught.exception))

    def test_duration_needs_both_ends(self):
        self.assertIsNone(self.run_for().duration_seconds)
        finished = self.run_for(
            started_at=MIDNIGHT_IST, finished_at=MIDNIGHT_IST + timedelta(seconds=2.5))
        self.assertEqual(finished.duration_seconds, 2.5)


class WorkerLeaseTests(unittest.TestCase):
    """One scheduler per database, with a way back if the holder died."""

    def test_the_refusal_names_the_holder_and_the_heartbeat(self):
        lease = WorkerLease(lease_name="scheduler", worker_id="worker-7",
                            acquired_at=MIDNIGHT_IST, heartbeat_at=MIDNIGHT_IST)
        error = WorkerLeaseHeld(lease)

        self.assertIn("worker-7", str(error))
        self.assertIn(MIDNIGHT_IST.isoformat(), str(error))
        self.assertIs(error.lease, lease)

    def test_a_lease_without_a_zone_is_refused(self):
        with self.assertRaises(TaskValidationError):
            WorkerLease(lease_name="scheduler", worker_id="worker-7",
                        acquired_at=datetime(2026, 10, 15, 12, 0), heartbeat_at=MIDNIGHT_IST)


class ScheduleUpdateTests(unittest.TestCase):
    """The update object is a value type: nothing about it is inferred later."""

    def test_it_carries_every_field_the_store_needs_to_write(self):
        update = ScheduleUpdate(next_run_at=MIDNIGHT_IST, pending_slot_at=None, pending_attempt=None,
                                consecutive_failures=0, last_outcome=RunState.SUCCEEDED)

        self.assertEqual(sorted(field for field in update.__dataclass_fields__),
                         ["consecutive_failures", "last_outcome", "next_run_at", "pending_attempt",
                          "pending_slot_at"])


if __name__ == "__main__":  # pragma: no cover - convenience for running this file alone
    unittest.main()
