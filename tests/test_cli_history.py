"""Tests for the history commands: the report, and the two ways a record can be added without the window.

These commands are the only place the candidate's own records can be seen or written from a terminal, so
the properties tested here are the ones a person would be harmed by if they were wrong: the report changes
nothing and claims no more than the records say, the write commands refuse contradictions rather than
resolving them, a refusal writes nothing at all, and neither command uploads or contacts anybody.
"""
from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from datetime import date
from pathlib import Path

import career_agent.__main__ as cli
from career_agent.core import (
    ActivityKind, ApplicationActivity, ApplicationTracker, Availability, JobListing,
)
from career_agent.store import CareerStore


class HistoryCommandTests(unittest.TestCase):
    """A temporary folder and a disposable database; every record in it is invented."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.database = self.folder / "career_agent.sqlite3"

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main([*arguments, "--database", str(self.database)])
        return code, out.getvalue(), err.getvalue()

    def add_role(self, *arguments: str) -> tuple[int, str, str]:
        return self.run_cli("--add-role", "Sandbox Systems", "--title", "Data Engineer", "--start",
                            "2023-04-01", *arguments)

    def roles(self):
        with CareerStore(self.database) as store:
            return store.list_work_history()

    def study(self):
        with CareerStore(self.database) as store:
            return store.list_education()

    # ------------------------------------------------------------------ the report
    def test_the_report_lists_both_kinds_of_record_and_says_nothing_was_changed(self):
        self.add_role("--current", "--employment-type", "full_time", "--summary", "built the pipeline")
        self.run_cli("--add-study", "IIT Delhi", "--qualification", "B.Tech", "--discipline", "ECE",
                     "--completed", "2019-05-31")

        code, out, err = self.run_cli("--history")

        self.assertEqual(code, 0, err)
        self.assertEqual(err, "")
        self.assertIn("Data Engineer at Sandbox Systems", out)
        self.assertIn("2023-04-01 - present", out)
        self.assertIn("Full time", out)
        self.assertIn("built the pipeline", out)
        self.assertIn("B.Tech - ECE at IIT Delhi", out)
        self.assertIn("2019-05-31", out)
        self.assertIn("nothing was changed, uploaded or sent", out)

    def test_the_report_on_a_fresh_installation_says_there_is_nothing_yet(self):
        code, out, err = self.run_cli("--history")

        self.assertEqual(code, 0, err)
        self.assertIn("No database yet", out)
        self.assertFalse(self.database.exists(), "a report must not create the database it reports on")

    def test_the_report_says_which_records_it_could_not_time_rather_than_summing_them_in(self):
        self.add_role("--current")
        self.run_cli("--add-role", "Old Co", "--title", "Analyst", "--start", "2015-01-06")

        code, out, _err = self.run_cli("--history")

        self.assertEqual(code, 0)
        self.assertIn("end date not recorded", out)
        self.assertIn("no duration is counted for them", out)
        self.assertIn("not a claim about experience", out)

    def test_the_report_counts_months_covered_once_when_two_roles_overlap(self):
        self.run_cli("--add-role", "Sandbox Systems", "--title", "Engineer", "--start", "2020-01-01",
                     "--end", "2021-01-01")
        self.run_cli("--add-role", "Sandbox Systems", "--title", "Analyst", "--start", "2020-07-01",
                     "--end", "2021-07-01")

        code, out, _err = self.run_cli("--history")

        self.assertEqual(code, 0)
        self.assertIn("cover 18 month(s) in total", out)
        self.assertIn("counted once", out)

    def test_the_report_of_an_empty_database_does_not_report_a_zero_duration(self):
        self.run_cli("--add-study", "IIT Delhi", "--qualification", "B.Tech")

        code, out, _err = self.run_cli("--history")

        self.assertEqual(code, 0)
        self.assertNotIn("month(s) in total", out, "no roles means no duration to report, not a zero")
        self.assertIn("None recorded", out)

    # ------------------------------------------------------------------ adding a role
    def test_adding_a_role_writes_it_and_reports_exactly_what_was_saved(self):
        code, out, err = self.add_role("--current", "--employment-type", "contract")

        self.assertEqual(code, 0, err)
        self.assertIn("Added employment record 1", out)
        self.assertIn("Data Engineer at Sandbox Systems (2023-04-01 - present, Contract)", out)
        self.assertIn("Nothing was uploaded and no employer was contacted", out)
        stored = self.roles()
        self.assertEqual(len(stored), 1)
        self.assertTrue(stored[0].is_current)

    def test_adding_a_role_without_a_title_is_refused_and_writes_nothing(self):
        code, out, err = self.run_cli("--add-role", "Sandbox Systems", "--start", "2023-04-01")

        self.assertNotEqual(code, 0)
        self.assertIn("--title", err)
        self.assertIn("Nothing was written", err)
        self.assertEqual(self.roles(), ())

    def test_adding_a_role_without_a_start_date_is_refused_and_writes_nothing(self):
        code, _out, err = self.run_cli("--add-role", "Sandbox Systems", "--title", "Data Engineer")

        self.assertNotEqual(code, 0)
        self.assertIn("--start", err)
        self.assertEqual(self.roles(), ())

    def test_an_impossible_period_is_refused_rather_than_resolved(self):
        code, _out, err = self.add_role("--end", "2019-01-01")

        self.assertNotEqual(code, 0)
        self.assertIn("before the start date", err)
        self.assertIn("Nothing was written", err)
        self.assertEqual(self.roles(), ())

    def test_a_current_role_with_an_end_date_is_refused_even_on_the_command_line(self):
        code, _out, err = self.add_role("--current", "--end", "2025-01-01")

        self.assertNotEqual(code, 0)
        self.assertIn("current role", err)
        self.assertEqual(self.roles(), ())

    def test_a_date_that_is_not_written_as_YYYY_MM_DD_is_refused_with_the_option_named(self):
        code, _out, err = self.add_role("--start", "1 April 2023")

        self.assertNotEqual(code, 0)
        self.assertIn("--start", err)
        self.assertIn("YYYY-MM-DD", err)
        self.assertEqual(self.roles(), ())

    def test_the_same_role_cannot_be_added_twice_by_running_the_command_twice(self):
        self.add_role()

        code, _out, err = self.add_role()

        self.assertNotEqual(code, 0)
        self.assertIn("already have a record", err)
        self.assertEqual(len(self.roles()), 1)

    def test_an_unknown_employment_type_is_refused_by_the_parser(self):
        """``choices`` refuses it before a record exists, so no half-record can be written either."""
        with self.assertRaises(SystemExit):
            self.run_cli("--add-role", "Sandbox Systems", "--title", "Data Engineer", "--start",
                         "2023-04-01", "--employment-type", "side-hustle")

        self.assertEqual(self.roles(), ())

    def test_adding_a_role_creates_the_database_on_a_fresh_machine_rather_than_refusing(self):
        """The same behaviour ``--seed-tasks`` has: the first command on a new machine works."""
        self.assertFalse(self.database.exists())

        code, out, err = self.add_role("--current")

        self.assertEqual(code, 0, err)
        self.assertTrue(self.database.exists())
        self.assertIn("Added employment record", out)

    # ------------------------------------------------------------------ adding a qualification
    def test_adding_a_qualification_writes_optional_fields_as_absent(self):
        code, out, err = self.run_cli("--add-study", "IIT Delhi", "--qualification", "B.Tech")

        self.assertEqual(code, 0, err)
        self.assertIn("B.Tech at IIT Delhi", out)
        stored = self.study()
        self.assertIsNone(stored[0].discipline)
        self.assertIsNone(stored[0].start_date)
        self.assertIsNone(stored[0].completion_date)

    def test_ongoing_study_is_recorded_as_ongoing(self):
        code, out, _err = self.run_cli("--add-study", "Coursera", "--qualification", "Specialisation",
                                       "--ongoing")

        self.assertEqual(code, 0)
        self.assertIn("ongoing", out)
        self.assertTrue(self.study()[0].is_ongoing)

    def test_ongoing_study_with_a_completion_date_is_refused_and_writes_nothing(self):
        code, _out, err = self.run_cli("--add-study", "Coursera", "--qualification", "Specialisation",
                                       "--ongoing", "--completed", "2026-06-01")

        self.assertNotEqual(code, 0)
        self.assertIn("ongoing", err)
        self.assertEqual(self.study(), ())

    def test_a_qualification_without_a_qualification_is_refused(self):
        code, _out, err = self.run_cli("--add-study", "IIT Delhi")

        self.assertNotEqual(code, 0)
        self.assertIn("--qualification", err)
        self.assertEqual(self.study(), ())

    def test_completion_before_start_is_refused_and_writes_nothing(self):
        code, _out, err = self.run_cli("--add-study", "IIT Delhi", "--qualification", "B.Tech",
                                       "--start", "2019-08-01", "--completed", "2015-05-31")

        self.assertNotEqual(code, 0)
        self.assertIn("before the start date", err)
        self.assertEqual(self.study(), ())

    def test_a_history_record_cannot_create_an_application(self):
        """The property that keeps these records notes about a person rather than claims about a job."""
        self.add_role("--current")
        self.run_cli("--add-study", "IIT Delhi", "--qualification", "B.Tech", "--ongoing")

        with CareerStore(self.database) as store:
            self.assertEqual(store.list_jobs(), ())
            self.assertIsNone(store.get_tracker("j1"))

    def test_the_records_survive_and_are_visible_to_both_front_ends(self):
        self.add_role("--current", "--summary", "built the pipeline")
        self.run_cli("--add-study", "IIT Delhi", "--qualification", "B.Tech", "--completed",
                     "2019-05-31")

        code, out, _err = self.run_cli("--history")

        self.assertEqual(code, 0)
        self.assertIn("Data Engineer", out)
        self.assertIn("B.Tech", out)
        self.assertEqual(len(self.roles()), 1)
        self.assertEqual(len(self.study()), 1)


class AnalyticsCommandTests(unittest.TestCase):
    """The progress report on the command line: the same report, and the same refusals to overstate."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.database = self.folder / "career_agent.sqlite3"

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main([*arguments, "--database", str(self.database)])
        return code, out.getvalue(), err.getvalue()

    def record_applications(self, count: int, *, replies: int = 0) -> None:
        """Write ``count`` applications, of which ``replies`` have a recorded reply."""
        with CareerStore(self.database) as store:
            for index in range(count):
                listing_id = f"j{index}"
                store.save_job(JobListing(listing_id, "fixture", "Fixture",
                                          f"https://jobs.example.invalid/{listing_id}", "Sandbox Systems",
                                          "Data Engineer", availability_status=Availability.OPEN))
                store.save_tracker(ApplicationTracker(listing_id))
                store.add_activity(listing_id, ApplicationActivity(
                    ActivityKind.APPLIED, date(2026, 10, 1), f"applied to {listing_id}"))
            for index in range(replies):
                store.add_activity(f"j{index}", ApplicationActivity(
                    ActivityKind.RESPONSE, date(2026, 10, 5), f"reply about j{index}"))

    def test_the_report_prints_the_counts_and_the_rates_with_their_denominators(self):
        self.record_applications(6, replies=2)

        code, out, err = self.run_cli("--analytics")

        self.assertEqual(code, 0, err)
        self.assertEqual(err, "")
        self.assertIn("Applications recorded as sent: 6", out)
        self.assertIn("2 of 6 recorded as sent", out)
        self.assertIn("This report is read-only", out)

    def test_the_report_withholds_a_rate_below_the_floor_rather_than_printing_a_percentage(self):
        self.record_applications(2, replies=1)

        code, out, _err = self.run_cli("--analytics")

        self.assertEqual(code, 0)
        self.assertIn("1 of 2 recorded as sent", out)
        self.assertIn("No rate is shown", out)
        self.assertNotIn("% against", out)

    def test_the_report_says_what_it_cannot_measure_instead_of_printing_a_zero(self):
        self.record_applications(6)

        code, out, _err = self.run_cli("--analytics")

        self.assertEqual(code, 0)
        self.assertIn("Offers", out)
        self.assertIn("missing data, not a zero", out)
        self.assertNotIn("Offers: 0", out)
        self.assertIn("not your ability", out)

    def test_the_report_on_a_fresh_installation_says_nothing_is_recorded_and_creates_no_database(self):
        code, out, err = self.run_cli("--analytics")

        self.assertEqual(code, 0, err)
        self.assertIn("No database yet", out)
        self.assertFalse(self.database.exists(), "a report must not create the database it reports on")

    def test_the_report_changes_nothing(self):
        self.record_applications(6, replies=2)
        with CareerStore(self.database) as store:
            before = [(record.listing_id, record.status) for record in store.list_trackers()]
            activities = len(store.list_activity("j0"))

        code, _out, _err = self.run_cli("--analytics")

        self.assertEqual(code, 0)
        with CareerStore(self.database) as store:
            self.assertEqual([(record.listing_id, record.status) for record in store.list_trackers()],
                             before, "no status was created or changed")
            self.assertEqual(len(store.list_activity("j0")), activities)

    def test_history_and_analytics_cannot_be_asked_for_in_the_same_run(self):
        with self.assertRaises(SystemExit):
            self.run_cli("--history", "--analytics")


if __name__ == "__main__":  # pragma: no cover - convenience for a focused run
    unittest.main()
