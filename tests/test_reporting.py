"""Tests for the operational report: durable records only, and queued work is never an outcome.

Every database here is a disposable file. The report reads; it never schedules, fetches or sends.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from career_agent.attempts import AttemptState
from career_agent.core import (
    ApplicationStatus, ApplicationTracker, Availability, CandidateProfile, FactSource, JobListing,
)
from career_agent.policy import ActionKind, GlobalPolicy
from career_agent.reporting import (
    OperationsReport, ReportError, build_operations_report, daily_report, weekly_report,
)
from career_agent.store import CareerStore
from career_agent.tasks import RunState, build_task

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def tracked(store, listing_id="j1", status=ApplicationStatus.DISCOVERED):
    """Save a listing and walk its tracker to one status through the domain's own transitions.

    Walking the real path means a fixture cannot describe a record this application would refuse to
    store, which is the same reason the analytics tests do it this way.
    """
    store.save_job(listing(listing_id))
    record = ApplicationTracker(listing_id)
    store.save_tracker(record)
    for step in (ApplicationStatus.SHORTLISTED, ApplicationStatus.PREPARED,
                 ApplicationStatus.AWAITING_USER, ApplicationStatus.SUBMISSION_ATTEMPTED,
                 ApplicationStatus.SUBMITTED_UNVERIFIED):
        record = record.transition(step)
        store.save_tracker(record)
        if step is status:
            return record
    return record


def listing(listing_id="j1") -> JobListing:
    return JobListing(
        listing_id=listing_id, source_id="manual", source_name="Manual entry",
        source_listing_url=f"https://jobs.example.invalid/listing/{listing_id}",
        employer_name="Example Employer", role_title="GenAI Engineer",
        availability_status=Availability.OPEN, location_text="Delhi, India")


class ReportShapeTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.database = Path(self._temporary.name) / "report.sqlite3"
        self.store = CareerStore(str(self.database))
        self.addCleanup(self.store.close)

    def report(self, **overrides) -> OperationsReport:
        return build_operations_report(self.store, now=NOW, **overrides)

    def text(self, **overrides) -> str:
        return "\n".join(self.report(**overrides).describe())

    def test_an_empty_database_reports_that_nothing_ran_rather_than_nothing_at_all(self):
        report = self.report()
        self.assertFalse(report.needs_attention)
        self.assertIn("nothing ran", report.headline())
        self.assertIn("No attempt at an outside action has been recorded", self.text())

    def test_every_report_says_what_it_cannot_say(self):
        report = self.report()
        joined = " ".join(report.caveats)
        self.assertIn("switched off in this build", joined)
        self.assertIn("plans, not outcomes", joined)
        self.assertIn("time does not settle one", joined)

    def test_the_sources_section_quotes_each_gate_rather_than_summarising_it(self):
        text = self.text()
        self.assertIn("0 enabled for discovery", text)
        self.assertIn("jobicy: closed", text)
        self.assertIn("No listing in this database came from a live run", text)

    def test_a_window_must_be_at_least_a_day_and_a_horizon_cannot_be_negative(self):
        with self.assertRaises(ReportError):
            self.report(window_days=0)
        with self.assertRaises(ReportError):
            self.report(horizon_days=-1)

    def test_a_moment_without_a_timezone_is_refused(self):
        with self.assertRaises(ReportError):
            build_operations_report(self.store, now=datetime(2026, 10, 20, 12))

    def test_the_daily_and_weekly_reports_differ_only_in_how_far_they_look(self):
        self.assertEqual(daily_report(self.store, now=NOW).window_days, 1)
        self.assertEqual(weekly_report(self.store, now=NOW).window_days, 7)


class QueuedWorkIsNotAnOutcomeTests(unittest.TestCase):
    """The rule the report exists for, asserted four ways."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.store = CareerStore(str(Path(self._temporary.name) / "queued.sqlite3"))
        self.addCleanup(self.store.close)

    def text(self) -> str:
        return "\n".join(build_operations_report(self.store, now=NOW).describe())

    def test_a_prepared_application_is_reported_as_waiting_on_the_person(self):
        tracked(self.store, status=ApplicationStatus.SHORTLISTED)
        text = self.text()
        self.assertIn("waiting on you", text)
        self.assertIn("prepared or shortlisted is not sent", text)

    def test_an_unverified_submission_is_reported_as_unestablished_and_needs_attention(self):
        tracked(self.store, status=ApplicationStatus.SUBMISSION_ATTEMPTED)
        report = build_operations_report(self.store, now=NOW)
        self.assertTrue(report.needs_attention)
        joined = "\n".join(report.describe())
        self.assertIn("what the employer received is not established", joined)

    def test_a_scheduled_task_is_reported_as_scheduled_not_as_done(self):
        task = build_task("backup.snapshot", "Nightly backup", "backup.snapshot",
                          times=("07:00",), timezone="UTC", now=NOW)
        self.store.save_scheduled_task(task)
        text = self.text()
        self.assertIn("1 task(s) scheduled", text)
        self.assertIn("Scheduled is not done", text)

    def test_an_unresolved_attempt_leads_the_report_and_counts_as_attention(self):
        self.store.begin_attempt(operation_id="op-1", identity_key="requisition:example:req-1",
                                 action=ActionKind.EMAIL_SEND.value)
        report = build_operations_report(self.store, now=NOW)
        self.assertTrue(report.needs_attention)
        self.assertEqual(report.sections[0].heading, "Attempts at outside actions")
        self.assertTrue(report.sections[0].needs_attention)
        joined = "\n".join(report.describe())
        self.assertIn("blocks any further attempt", joined)

    def test_a_reconciled_attempt_stops_needing_attention(self):
        self.store.begin_attempt(operation_id="op-1", identity_key="requisition:example:req-1",
                                 action=ActionKind.EMAIL_SEND.value)
        self.store.reconcile_attempt("op-1", state=AttemptState.FAILED,
                                     evidence="the provider has no record of it")
        self.assertFalse(build_operations_report(self.store, now=NOW).needs_attention)

    def test_a_refusal_is_not_counted_as_a_failure(self):
        stored = self.store.save_scheduled_task(build_task(
            "discovery.run", "Look for jobs", "discovery.run", times=("07:00",), timezone="UTC",
            now=NOW - timedelta(days=1)))
        run = self.store.claim_due_run(worker_id="worker-1", now=stored.next_run_at)
        self.store.finish_run(run.run_id, RunState.REFUSED, detail="the source gate is closed",
                              now=NOW - timedelta(hours=2))
        report = build_operations_report(self.store, now=NOW)
        joined = "\n".join(report.describe())
        self.assertIn("refusal(s) are the permission rules working, not errors", joined)
        self.assertFalse(report.needs_attention,
                         "a refusal must not teach a person to ignore the report")

    def test_a_run_that_timed_out_is_reported_as_unresolved_not_as_a_success(self):
        stored = self.store.save_scheduled_task(build_task(
            "backup.snapshot", "Nightly backup", "backup.snapshot", times=("07:00",),
            timezone="UTC", now=NOW - timedelta(days=1)))
        run = self.store.claim_due_run(worker_id="worker-1", now=stored.next_run_at)
        self.store.finish_run(run.run_id, RunState.TIMED_OUT, detail="no answer",
                              now=NOW - timedelta(hours=2))
        report = build_operations_report(self.store, now=NOW)
        self.assertTrue(report.needs_attention)
        self.assertIn("cannot be read as successes", "\n".join(report.describe()))


class AuthorisationAndDatesTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.store = CareerStore(str(Path(self._temporary.name) / "dates.sqlite3"))
        self.addCleanup(self.store.close)

    def text(self, **overrides) -> str:
        return "\n".join(build_operations_report(self.store, now=NOW, **overrides).describe())

    def test_with_nothing_authorised_the_report_says_so(self):
        self.assertIn("Nothing is authorised", self.text())

    def test_an_authorisation_is_reported_with_the_caveat_that_it_runs_nothing(self):
        self.store.save_global_policy(GlobalPolicy(
            allowed=frozenset({("jobicy", ActionKind.DISCOVERY)}),
            daily_limits={ActionKind.DISCOVERY: 2}))
        text = self.text()
        self.assertIn("Authorisation version 1", text)
        self.assertIn("jobicy — look for jobs", text)
        self.assertIn("still switched off in this build", text)

    def test_a_withdrawn_authorisation_is_reported_as_permitting_nothing(self):
        self.store.save_global_policy(GlobalPolicy(
            allowed=frozenset({("jobicy", ActionKind.DISCOVERY)}),
            daily_limits={ActionKind.DISCOVERY: 2}))
        self.store.revoke_global_policy()
        self.assertIn("withdrawn; nothing may be attempted", self.text())

    def test_an_overdue_follow_up_needs_attention_and_a_future_one_does_not(self):
        tracked(self.store)
        self.store.set_follow_up("j1", date(2026, 10, 18), note="check in")
        report = build_operations_report(self.store, now=NOW)
        self.assertTrue(report.needs_attention)
        self.assertIn("already past", "\n".join(report.describe()))
        self.store.set_follow_up("j1", date(2026, 12, 1), note="check in")
        later = build_operations_report(self.store, now=NOW, horizon_days=7)
        self.assertIn("Nothing is dated in the next 7 day(s)", "\n".join(later.describe()))

    def test_nothing_in_the_report_names_a_person_or_an_address(self):
        self.store.save_profile(CandidateProfile(
            candidate_country="India", degree_discipline="ECE", graduation_year=2027,
            experience_years=1.0, work_authorization="citizen",
            skills=frozenset({"Python"}), preferred_locations=frozenset({"Delhi"})),
            source=FactSource.USER_ENTERED)
        self.store.begin_attempt(operation_id="op-1", identity_key="requisition:example:req-1",
                                 action=ActionKind.EMAIL_SEND.value)
        text = self.text()
        self.assertNotIn("@", text)
        self.assertNotIn("Python", text)


class ReportCommandTests(unittest.TestCase):
    """The command line surface, run as a subprocess the way a person would run it."""

    def run_cli(self, *arguments, database):
        return subprocess.run(
            [sys.executable, "-m", "career_agent", "--database", str(database), *arguments],
            cwd=REPOSITORY_ROOT, capture_output=True, text=True, timeout=120)

    def test_the_command_reports_an_absent_database_without_creating_one(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "missing.sqlite3"
            result = self.run_cli("--report", database=database)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("nothing to report", result.stdout)
            self.assertFalse(database.exists(), "a read-only command created a database")

    def test_the_command_prints_the_report_and_says_it_changed_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "report.sqlite3"
            store = CareerStore(str(database))
            store.begin_attempt(operation_id="op-1", identity_key="requisition:example:req-1",
                                action=ActionKind.EMAIL_SEND.value)
            store.close()
            result = self.run_cli("--report", database=database)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Attempts at outside actions", result.stdout)
            self.assertIn("needs you", result.stdout)
            self.assertIn("nothing was fetched, sent, submitted or changed", result.stdout)

    def test_the_weekly_flag_widens_the_window(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "weekly.sqlite3"
            CareerStore(str(database)).close()
            result = self.run_cli("--report", "--weekly", database=database)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("last 7 days", result.stdout)
            self.assertIn("next 14 day(s)", result.stdout,
                          "the weekly report also widens how far forward it looks")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
