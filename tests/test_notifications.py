"""Tests for notification preferences, and for the controls that must be read back, not assumed.

Two halves. The first is the decision about whether to prepare a report: quiet by default, silent in
quiet hours, once per period, and silent while everything is stopped. The second is the roadmap's
other requirement - that pausing, resuming, stopping and withdrawing are *read back from the records*
rather than believed because a control was pressed.

Nothing here delivers anything anywhere. No email, no push, no system notification: the only channels
this build offers are the window a person opens and a file on their own machine.
"""
from __future__ import annotations

import dataclasses
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from career_agent.notifications import (
    CHANNEL_LIMITS, Cadence, DeliveryChannel, NotificationError, NotificationPreferences,
    notification_due, preferences_from_payload, preferences_payload,
)
from career_agent.policy import ActionKind, GlobalPolicy, evaluate_policy
from career_agent.reporting import build_operations_report
from career_agent.store import CareerStore, StoredRecordError
from career_agent.tasks import RunState, build_task
from career_agent.worker import worker_status

MORNING = datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc)
NIGHT = datetime(2026, 10, 20, 23, 30, tzinfo=timezone.utc)


class PreferenceTests(unittest.TestCase):
    """What a person can ask for, and what this build refuses to pretend it can do."""

    def test_the_default_is_silence(self):
        preferences = NotificationPreferences()
        self.assertIs(preferences.cadence, Cadence.OFF)
        self.assertTrue(preferences.is_off)
        self.assertIn("No notification is prepared", preferences.describe())

    def test_a_cadence_and_a_channel_must_be_ones_this_build_offers(self):
        with self.assertRaises(NotificationError):
            NotificationPreferences(cadence="whenever")  # type: ignore[arg-type]
        with self.assertRaises(NotificationError):
            NotificationPreferences(cadence=Cadence.DAILY, channel="sms")  # type: ignore[arg-type]

    def test_an_hour_outside_the_day_is_refused(self):
        for hour in (-1, 24, 9.5, True):
            with self.subTest(hour=hour), self.assertRaises(NotificationError):
                NotificationPreferences(cadence=Cadence.DAILY, hour=hour)  # type: ignore[arg-type]

    def test_each_channel_states_its_own_limit(self):
        for channel in DeliveryChannel:
            with self.subTest(channel=channel):
                self.assertIn(channel, CHANNEL_LIMITS)
        self.assertIn("nothing is sent anywhere", CHANNEL_LIMITS[DeliveryChannel.IN_APP])
        self.assertIn("nothing is uploaded", CHANNEL_LIMITS[DeliveryChannel.FILE])

    def test_the_description_says_when_and_how_and_under_what_condition(self):
        described = NotificationPreferences(cadence=Cadence.WEEKLY, hour=7,
                                            channel=DeliveryChannel.FILE).describe()
        self.assertIn("once a week", described)
        self.assertIn("07:00", described)
        self.assertIn("written to a file on this machine", described)

    def test_preferences_survive_a_round_trip_and_reject_what_they_do_not_know(self):
        preferences = NotificationPreferences(cadence=Cadence.DAILY, hour=6,
                                              channel=DeliveryChannel.FILE,
                                              only_when_attention=False)
        self.assertEqual(preferences_from_payload(preferences_payload(preferences)), preferences)
        for payload in ('{"cadence": "hourly"}', '{"shout": true}', "not json", "[]"):
            with self.subTest(payload=payload), self.assertRaises(NotificationError):
                preferences_from_payload(payload)


class DueTests(unittest.TestCase):
    """When a report may be prepared. Every refusal is reported, not only the first."""

    DAILY = NotificationPreferences(cadence=Cadence.DAILY, hour=9, only_when_attention=False)

    def test_nothing_is_due_while_the_person_has_not_asked(self):
        decision = notification_due(NotificationPreferences(), now=MORNING,
                                    last_delivered_at=None, attention_count=3)
        self.assertFalse(decision.deliver)
        self.assertIn("you have not asked for one", decision.reasons)

    def test_a_daily_report_is_due_after_its_hour(self):
        self.assertTrue(notification_due(self.DAILY, now=MORNING,
                                         last_delivered_at=None).deliver)
        early = MORNING.replace(hour=7)
        decision = notification_due(self.DAILY, now=early, last_delivered_at=None)
        self.assertFalse(decision.deliver)
        self.assertIn("it is before 09:00", decision.reasons)

    def test_quiet_hours_silence_it_whatever_else_is_true(self):
        nightly = NotificationPreferences(cadence=Cadence.DAILY, hour=0,
                                          only_when_attention=False)
        decision = notification_due(nightly, now=NIGHT, last_delivered_at=None,
                                    quiet_hours=(22, 7), attention_count=5)
        self.assertFalse(decision.deliver)
        self.assertIn("inside your quiet hours (22:00-07:00)", decision.reasons[0])

    def test_quiet_hours_that_say_nothing_are_refused(self):
        with self.assertRaises(NotificationError):
            notification_due(self.DAILY, now=MORNING, last_delivered_at=None, quiet_hours=(9, 9))

    def test_a_period_is_never_prepared_twice(self):
        earlier = MORNING - timedelta(minutes=30)
        decision = notification_due(self.DAILY, now=MORNING, last_delivered_at=earlier)
        self.assertFalse(decision.deliver)
        self.assertIn("already been prepared for this period", decision.reasons[0])
        tomorrow = MORNING + timedelta(days=1)
        self.assertTrue(notification_due(self.DAILY, now=tomorrow,
                                         last_delivered_at=earlier).deliver)

    def test_a_weekly_report_counts_weeks_not_days(self):
        weekly = NotificationPreferences(cadence=Cadence.WEEKLY, hour=9,
                                         only_when_attention=False)
        yesterday = MORNING - timedelta(days=1)
        self.assertFalse(notification_due(weekly, now=MORNING,
                                          last_delivered_at=yesterday).deliver)
        next_week = MORNING + timedelta(days=7)
        self.assertTrue(notification_due(weekly, now=next_week,
                                         last_delivered_at=yesterday).deliver)

    def test_a_quiet_period_is_passed_over_when_the_person_asked_for_that(self):
        preferences = NotificationPreferences(cadence=Cadence.DAILY, hour=9,
                                              only_when_attention=True)
        self.assertFalse(notification_due(preferences, now=MORNING, last_delivered_at=None,
                                          attention_count=0).deliver)
        self.assertTrue(notification_due(preferences, now=MORNING, last_delivered_at=None,
                                         attention_count=1).deliver)

    def test_stopping_everything_stops_the_report_too(self):
        decision = notification_due(self.DAILY, now=MORNING, last_delivered_at=None, stopped=True)
        self.assertFalse(decision.deliver)
        self.assertIn("everything is stopped", decision.reasons)

    def test_every_reason_is_reported_rather_than_the_first(self):
        decision = notification_due(
            NotificationPreferences(cadence=Cadence.DAILY, hour=9, only_when_attention=True),
            now=NIGHT.replace(hour=5), last_delivered_at=None, quiet_hours=(22, 7),
            attention_count=0, stopped=True)
        self.assertFalse(decision.deliver)
        self.assertEqual(len(decision.reasons), 4)
        self.assertIn("No report is due", decision.describe())

    def test_a_naive_moment_is_refused(self):
        with self.assertRaises(NotificationError):
            notification_due(self.DAILY, now=datetime(2026, 10, 20, 9), last_delivered_at=None)
        with self.assertRaises(NotificationError):
            notification_due(self.DAILY, now=MORNING,
                             last_delivered_at=datetime(2026, 10, 19, 9))


class StoredPreferenceTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.database = Path(self._temporary.name) / "settings.sqlite3"
        self.store = CareerStore(str(self.database))
        self.addCleanup(self.store.close)

    def test_a_file_nobody_has_chosen_in_is_silent(self):
        self.assertTrue(self.store.get_notification_preferences().is_off)
        self.assertIsNone(self.store.notification_prepared_at())

    def test_a_choice_is_stored_and_survives_a_restart(self):
        self.store.save_notification_preferences(
            NotificationPreferences(cadence=Cadence.WEEKLY, hour=7, channel=DeliveryChannel.FILE))
        self.store.close()
        reopened = CareerStore(str(self.database))
        self.addCleanup(reopened.close)
        stored = reopened.get_notification_preferences()
        self.assertIs(stored.cadence, Cadence.WEEKLY)
        self.assertEqual(stored.hour, 7)
        self.assertIs(stored.channel, DeliveryChannel.FILE)

    def test_saving_the_same_choice_again_writes_nothing(self):
        preferences = NotificationPreferences(cadence=Cadence.DAILY)
        self.store.save_notification_preferences(preferences)
        before = self.store._connection.total_changes
        self.store.save_notification_preferences(preferences)
        self.assertEqual(self.store._connection.total_changes, before)

    def test_a_damaged_preference_is_reported_rather_than_replaced_by_a_default(self):
        self.store.save_notification_preferences(NotificationPreferences(cadence=Cadence.DAILY))
        with self.store._connection:
            self.store._connection.execute(
                "UPDATE app_preference SET value='{\"cadence\": \"hourly\"}' "
                "WHERE name='notifications'")
        with self.assertRaises(StoredRecordError):
            self.store.get_notification_preferences()

    def test_what_was_prepared_is_recorded_rather_than_assumed(self):
        self.assertIsNone(self.store.notification_prepared_at())
        stamp = self.store.record_notification_prepared(at="2026-10-20T09:30:00+00:00")
        self.assertEqual(self.store.notification_prepared_at(), stamp)

    def test_a_setting_this_build_does_not_know_is_refused(self):
        with self.assertRaises(ValueError):
            self.store._set_preference("send_everything", "yes")


class ReadBackTests(unittest.TestCase):
    """Pause, resume, stop and withdraw: believed only when the records say so."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.store = CareerStore(str(Path(self._temporary.name) / "controls.sqlite3"))
        self.addCleanup(self.store.close)
        self.task = self.store.save_scheduled_task(build_task(
            "daily-backup", "Nightly backup", "backup.snapshot", times=("07:00",),
            timezone="UTC", now=MORNING - timedelta(days=1)))

    def _pause(self, *, enabled: bool, now: datetime):
        """Pause or resume the way the window does it: write the task, then read it back."""
        self.store.save_scheduled_task(
            dataclasses.replace(self.task, enabled=enabled, next_run_at=None), now=now)
        return self.store.get_scheduled_task("daily-backup")

    def test_pausing_is_read_back_from_the_stored_task_not_from_the_call(self):
        paused = self._pause(enabled=False, now=MORNING)
        self.assertFalse(paused.enabled, "the database is what decides whether a task is paused")
        self.assertIsNone(paused.next_run_at, "a paused task has no next run")

    def test_a_paused_task_is_not_claimed_by_a_worker(self):
        self._pause(enabled=False, now=MORNING)
        self.assertIsNone(self.store.claim_due_run(worker_id="w1", now=MORNING + timedelta(days=1)),
                          "a worker reads the schedule, so a pause is obeyed without telling it")

    def test_resuming_schedules_the_next_occurrence_and_replays_nothing(self):
        self._pause(enabled=False, now=MORNING)
        later = MORNING + timedelta(days=3)
        resumed = self._pause(enabled=True, now=later)
        self.assertTrue(resumed.enabled)
        self.assertIsNotNone(resumed.next_run_at)
        self.assertGreater(resumed.next_run_at, later,
                           "resuming must not replay the occurrences a pause walked past")
        self.assertEqual(self.store.list_task_runs(task_id="daily-backup"), (),
                         "nothing ran because of a resume")

    def test_the_worker_status_is_read_from_the_records(self):
        status = worker_status(self.store, now=MORNING)
        self.assertIsNone(status.lease, "no worker is running, and the status says so")
        self.assertEqual(status.running, ())
        self.assertEqual(status.next_task.task_id, "daily-backup")

    def test_a_run_that_was_refused_is_reported_as_refused_not_as_done(self):
        run = self.store.claim_due_run(worker_id="w1", now=self.task.next_run_at)
        finished = self.store.finish_run(run.run_id, RunState.REFUSED,
                                         detail="the source gate is closed")
        self.assertIs(finished.state, RunState.REFUSED)
        self.assertIs(self.store.get_task_run(run.run_id).state, RunState.REFUSED)

    def test_stop_all_is_read_back_from_the_stored_authorisation_and_refuses_everything(self):
        self.store.save_global_policy(GlobalPolicy(
            allowed=frozenset({("jobicy", ActionKind.DISCOVERY)}),
            daily_limits={ActionKind.DISCOVERY: 2}))
        self.store.save_global_policy(GlobalPolicy(
            allowed=frozenset({("jobicy", ActionKind.DISCOVERY)}),
            daily_limits={ActionKind.DISCOVERY: 2}, stop_all=True))
        stored = self.store.get_global_policy()
        self.assertTrue(stored.stop_all)
        decision = evaluate_policy(stored, source_id="jobicy", action=ActionKind.DISCOVERY,
                                   now=MORNING, done_today=0, source_gate_allows=True)
        self.assertFalse(decision.allowed)
        self.assertIn("stopped", decision.describe())
        self.assertIn("Everything is stopped",
                      "\n".join(build_operations_report(self.store, now=MORNING).describe()),
                      "a report that does not mention the stop invites somebody to wait forever")

    def test_a_withdrawal_is_read_back_and_silences_notifications_too(self):
        self.store.save_global_policy(GlobalPolicy(
            allowed=frozenset({("jobicy", ActionKind.DISCOVERY)}),
            daily_limits={ActionKind.DISCOVERY: 2}))
        self.store.revoke_global_policy()
        stored = self.store.get_global_policy()
        self.assertIsNotNone(stored.revoked_at)
        decision = evaluate_policy(stored, source_id="jobicy", action=ActionKind.DISCOVERY,
                                   now=MORNING, done_today=0, source_gate_allows=True)
        self.assertFalse(decision.allowed)
        self.store.save_notification_preferences(
            NotificationPreferences(cadence=Cadence.DAILY, hour=0, only_when_attention=False))
        report = build_operations_report(self.store, now=MORNING)
        self.assertFalse(notification_due(
            self.store.get_notification_preferences(), now=MORNING,
            last_delivered_at=None, quiet_hours=stored.quiet_hours,
            attention_count=report.attention_count, stopped=bool(stored.revoked_at)).deliver)


class NotificationCommandTests(unittest.TestCase):
    """The command itself, run as a person runs it."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.database = Path(self._temporary.name) / "cli.sqlite3"

    def run_command(self, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "career_agent", *arguments, "--database", str(self.database)],
            capture_output=True, text=True, timeout=120,
            cwd=str(Path(__file__).resolve().parents[1]))

    def test_a_file_that_does_not_exist_is_answered_without_creating_one(self):
        result = self.run_command("--notifications")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No notification is prepared", result.stdout)
        self.assertFalse(self.database.exists(), "asking a question must not create a database")

    def test_setting_a_cadence_is_stored_and_read_back(self):
        CareerStore(str(self.database)).close()
        stored = self.run_command("--notifications", "weekly")
        self.assertEqual(stored.returncode, 0, stored.stderr)
        self.assertIn("once a week", stored.stdout)
        shown = self.run_command("--notifications")
        self.assertIn("once a week", shown.stdout,
                      "the preference is read back from the database, not from the last command")

    def test_the_command_says_what_it_cannot_do(self):
        CareerStore(str(self.database)).close()
        result = self.run_command("--notifications", "daily")
        for promise in ("no email", "no push", "no system notification"):
            with self.subTest(promise=promise):
                self.assertIn(promise, result.stdout)

    def test_a_cadence_this_build_does_not_offer_is_refused_by_the_parser(self):
        result = self.run_command("--notifications", "hourly")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
