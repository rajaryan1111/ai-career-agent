"""Tests for the progress report: the arithmetic, and the sentences that keep it honest.

Two kinds of property are checked here. The first is arithmetic over records the test wrote itself, so every
number in the report can be traced to a row. The second is the honesty rules, which are the reason the module
exists: a rate names its denominator, a denominator too small produces no rate, something this application
cannot measure is reported as unavailable rather than as zero, a real zero stays a zero, and nothing in the
report claims that anything caused anything. Those rules are asserted as the text a person would read,
because that is where they can be broken without any count changing.
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from career_agent import analytics
from career_agent.analytics import (
    MIN_MEDIAN_SAMPLES, MIN_RATE_DENOMINATOR, TREND_WINDOW_DAYS, build_report, report_from_store,
)
from career_agent.core import (
    ActivityKind, ApplicationActivity, ApplicationStatus, ApplicationTracker, Availability, InterviewRound,
    InterviewStage, JobListing,
)
from career_agent.store import CareerStore

TODAY = date(2026, 10, 15)


def job(listing_id: str) -> JobListing:
    """An invented listing on a reserved example host, so nothing here can point at a real posting."""
    return JobListing(listing_id, "fixture", "Fixture", f"https://jobs.example.invalid/{listing_id}",
                      "Sandbox Systems", "Data Engineer", availability_status=Availability.OPEN)


def tracker(listing_id: str, status: ApplicationStatus = ApplicationStatus.DISCOVERED) -> ApplicationTracker:
    """A stored application record at one status, built through the domain's own transition table.

    Walking the real path (shortlisted, prepared, awaiting user, attempted, submitted) means a fixture cannot
    describe a record this application would refuse to store. The later statuses require a confirmed employer
    response and evidence, which is what the window demands before it will save one either.
    """
    evidence = "employer wrote back on 2026-10-01"
    if status in (ApplicationStatus.CONFIRMED, ApplicationStatus.RESPONSE_RECEIVED,
                  ApplicationStatus.INTERVIEW, ApplicationStatus.REJECTED_BY_EMPLOYER):
        return ApplicationTracker(listing_id, status=status, status_evidence=evidence,
                                  candidate_confirmed=True)
    if status is ApplicationStatus.WITHDRAWN:
        return ApplicationTracker(listing_id, status=ApplicationStatus.WITHDRAWN)
    record = ApplicationTracker(listing_id)
    for step in (ApplicationStatus.SHORTLISTED, ApplicationStatus.PREPARED, ApplicationStatus.AWAITING_USER,
                 ApplicationStatus.SUBMISSION_ATTEMPTED, ApplicationStatus.SUBMITTED_UNVERIFIED):
        if step is status:
            return record.transition(step)
        record = record.transition(step)
    return record


def applied(listing_id: str, days_ago: int) -> ApplicationActivity:
    return ApplicationActivity(ActivityKind.APPLIED, TODAY - timedelta(days=days_ago),
                               f"applied to {listing_id}")


def replied(listing_id: str, days_ago: int) -> ApplicationActivity:
    return ApplicationActivity(ActivityKind.RESPONSE, TODAY - timedelta(days=days_ago),
                               f"reply about {listing_id}")


def round_record(listing_id: str, stage: InterviewStage, days_from_today: int) -> InterviewRound:
    return InterviewRound(listing_id, stage, TODAY + timedelta(days=days_from_today))


class AnalyticsTestCase(unittest.TestCase):
    """Builds a report from explicitly written records, with no database in the way."""

    def report(self, *, jobs=(), trackers=None, activities=None, rounds=(), today=TODAY):
        return build_report(jobs=list(jobs), trackers=dict(trackers or {}),
                            activities=dict(activities or {}), rounds=list(rounds), today=today)

    def text(self, report) -> str:
        """The whole report as one string, which is how a person reads it."""
        return "\n".join(report.describe())

    def rate_line(self, report, needle: str) -> str:
        """The *rate* line for a label, not the count line: both carry the same wording."""
        lines = [line.strip() for line in report.describe()
                 if needle in line and " of " in line and " recorded as sent" in line]
        self.assertTrue(lines, f"no rate line in the report mentions {needle!r}")
        return lines[0]

    def line_containing(self, report, needle: str) -> str:
        """The single line mentioning ``needle``, whatever kind of line it is."""
        lines = [line.strip() for line in report.describe() if needle in line]
        self.assertTrue(lines, f"no line in the report mentions {needle!r}")
        return lines[0]

    def count_line(self, report, needle: str) -> str:
        lines = [line.strip() for line in report.describe() if needle in line and " (" in line]
        self.assertTrue(lines, f"no count line in the report mentions {needle!r}")
        return lines[0]


class CountingTests(AnalyticsTestCase):
    """What each number is counted from."""

    def test_an_application_with_an_applied_entry_is_counted_as_sent(self):
        report = self.report(jobs=[job("j1")], activities={"j1": [applied("j1", 10)]})

        self.assertEqual(report.applications_recorded, 1)
        self.assertIn("Applications recorded as sent: 1", self.text(report))

    def test_an_application_whose_status_says_it_was_sent_is_counted_even_without_an_entry(self):
        report = self.report(jobs=[job("j1")],
                             trackers={"j1": tracker("j1", ApplicationStatus.SUBMITTED_UNVERIFIED)})

        self.assertEqual(report.applications_recorded, 1)

    def test_a_shortlisted_application_is_not_counted_as_sent(self):
        """Planning is not applying, and counting it would inflate every rate built on this count."""
        report = self.report(jobs=[job("j1")], trackers={"j1": tracker("j1", ApplicationStatus.SHORTLISTED)})

        self.assertEqual(report.applications_recorded, 0)
        self.assertIn("Applications still being planned: 1",
                      self.count_line(report, "Applications still being planned"))

    def test_a_listing_with_both_an_entry_and_a_status_is_counted_once(self):
        report = self.report(jobs=[job("j1")],
                             trackers={"j1": tracker("j1", ApplicationStatus.SUBMITTED_UNVERIFIED)},
                             activities={"j1": [applied("j1", 20)]})

        self.assertEqual(report.applications_recorded, 1)

    def test_activity_of_every_kind_is_counted(self):
        report = self.report(jobs=[job("j1")], activities={"j1": [
            applied("j1", 30), replied("j1", 20),
            ApplicationActivity(ActivityKind.FOLLOW_UP, TODAY - timedelta(days=10), "chased"),
            ApplicationActivity(ActivityKind.NOTE, TODAY - timedelta(days=5), "note"),
            ApplicationActivity(ActivityKind.INTERVIEW, TODAY - timedelta(days=3), "round one"),
            ApplicationActivity(ActivityKind.ASSESSMENT, TODAY - timedelta(days=2), "test"),
        ]})

        self.assertIn("Follow-up entries you wrote: 1", self.text(report))
        self.assertIn("Notes you wrote: 1", self.text(report))

    def test_a_round_whose_day_has_arrived_is_not_reported_as_having_taken_place(self):
        """The distinction the report turns on: a planned day is a plan, not a fact."""
        report = self.report(jobs=[job("j1")], activities={"j1": [applied("j1", 30)]},
                             rounds=[round_record("j1", InterviewStage.SCREENING, -2),
                                     round_record("j1", InterviewStage.TECHNICAL, 3)])

        line = self.count_line(report, "Rounds whose day is today or earlier")
        self.assertIn(": 1", line)
        self.assertIn("nothing here claims the interview took place", line)
        self.assertIn("Interview rounds recorded: 2", self.text(report))

    def test_a_reply_recorded_as_a_status_counts_even_with_no_response_entry(self):
        report = self.report(jobs=[job("j1")],
                             trackers={"j1": tracker("j1", ApplicationStatus.RESPONSE_RECEIVED)})

        self.assertEqual(report.applications_recorded, 1)
        self.assertIn("Applications with a recorded reply: 1", self.text(report))

    def test_a_reply_on_an_application_never_recorded_as_sent_is_not_counted(self):
        """A stray entry must not enter the numerator by way of a denominator it never belonged to."""
        report = self.report(jobs=[job("j1")], activities={"j1": [replied("j1", 5)]})

        self.assertEqual(report.applications_recorded, 0)
        self.assertIn("Applications with a recorded reply: 0", self.text(report))

    def test_the_counts_and_the_rates_are_computed_from_the_same_records(self):
        report = self.report(jobs=[job(f"j{i}") for i in range(6)],
                             activities={**{f"j{i}": [applied(f"j{i}", 30 + i)] for i in range(6)},
                                         "j0": [applied("j0", 31), replied("j0", 10)],
                                         "j1": [applied("j1", 32), replied("j1", 11)]})

        self.assertEqual(report.applications_recorded, 6)
        self.assertIn("Applications with a recorded reply: 2", self.text(report))
        self.assertIn("2 of 6 recorded as sent", self.rate_line(report, "Applications with a recorded reply"))


class RateTests(AnalyticsTestCase):
    """Denominators that are named, rates that are withheld, and zeros that stay zeros."""

    def test_a_rate_names_the_denominator_it_was_computed_over(self):
        report = self.report(jobs=[job(f"j{i}") for i in range(6)],
                             activities={**{f"j{i}": [applied(f"j{i}", 30)] for i in range(6)},
                                         "j0": [applied("j0", 30), replied("j0", 20)],
                                         "j1": [applied("j1", 30), replied("j1", 21)]})

        line = self.rate_line(report, "Applications with a recorded reply")
        self.assertIn("2 of 6 recorded as sent", line)
        self.assertIn("33%", line)

    def test_a_denominator_below_the_floor_produces_no_rate_and_says_why(self):
        report = self.report(jobs=[job("j1"), job("j2")],
                             activities={"j1": [applied("j1", 30), replied("j1", 20)],
                                         "j2": [applied("j2", 40)]})

        line = self.rate_line(report, "Applications with a recorded reply")
        self.assertIn("1 of 2 recorded as sent", line)
        self.assertIn("No rate is shown", line)
        self.assertIn(f"floor of {MIN_RATE_DENOMINATOR}", line)
        self.assertNotIn("%", line)

    def test_the_floor_boundary_is_where_the_constant_says_it_is(self):
        """Pinned on both sides, so moving MIN_RATE_DENOMINATOR cannot happen quietly."""
        def report_with(count: int):
            return self.report(jobs=[job(f"j{i}") for i in range(count)],
                               activities={f"j{i}": [applied(f"j{i}", 30), replied(f"j{i}", 20)]
                                           for i in range(count)})

        below = self.rate_line(report_with(MIN_RATE_DENOMINATOR - 1),
                              "Applications with a recorded reply")
        self.assertIn("No rate is shown", below)
        at_floor = self.rate_line(report_with(MIN_RATE_DENOMINATOR), "Applications with a recorded reply")
        self.assertIn("100%", at_floor)

    def test_no_applications_at_all_reports_no_rate_rather_than_zero_percent(self):
        report = self.report()

        line = self.rate_line(report, "Applications with a recorded reply") \
            if any(" of " in line for line in report.describe()) else None
        rate_line = [line for line in report.describe()
                     if "Applications with a recorded reply" in line and " of " in line][0]
        self.assertIn("0 of 0", rate_line)
        self.assertIn("nothing has been measured yet", rate_line)
        self.assertNotIn("%", rate_line)
        self.assertIsNone(report.rates[0].percent, "a zero denominator is not a rate of zero")

    def test_a_real_zero_is_reported_as_zero_and_not_withheld(self):
        """Twenty applications and no reply is a fact, and the most important one here."""
        report = self.report(jobs=[job(f"j{i}") for i in range(20)],
                             activities={f"j{i}": [applied(f"j{i}", 30 + i)] for i in range(20)})

        self.assertIn("0 of 20 recorded as sent (0%)",
                      self.rate_line(report, "Applications with a recorded reply"))

    def test_a_rate_and_its_counts_cannot_disagree(self):
        """The numerator and denominator printed are the ones the percentage came from."""
        report = self.report(jobs=[job(f"j{i}") for i in range(8)],
                             activities={**{f"j{i}": [applied(f"j{i}", 30)] for i in range(8)},
                                         **{f"j{i}": [applied(f"j{i}", 30), replied(f"j{i}", 20)]
                                            for i in range(3)}})
        rate = next(entry for entry in report.rates if entry.label == "Applications with a recorded reply")

        self.assertEqual((rate.numerator, rate.denominator), (3, 8))
        self.assertAlmostEqual(rate.percent, 3 * 100 / 8)
        self.assertIn(f"{rate.percent:.0f}%", rate.describe())

    def test_every_rate_carries_the_same_named_denominator(self):
        report = self.report(jobs=[job("j1")], activities={"j1": [applied("j1", 9)]})

        self.assertEqual([rate.denominator_label for rate in report.rates],
                         ["recorded as sent"] * len(report.rates))
        self.assertEqual({rate.denominator for rate in report.rates}, {1})


class AvailabilityTests(AnalyticsTestCase):
    """Things this application cannot measure, and the difference between those and a zero."""

    def test_an_offer_is_reported_as_unmeasurable_and_never_as_zero(self):
        text = self.text(self.report())

        self.assertIn("Offers", text)
        self.assertIn("missing data, not a zero", text)
        self.assertNotIn("Offers: 0", text)

    def test_the_report_says_that_what_an_employer_never_told_you_cannot_be_counted(self):
        text = self.text(self.report())

        self.assertIn("screened or rejected without a reply", text)
        self.assertIn("silence is not a record", text)

    def test_the_unavailable_section_is_present_even_when_nothing_is_recorded(self):
        report = self.report()

        self.assertIn("What cannot be measured here", report.describe())
        self.assertEqual(report.unavailable, analytics.UNAVAILABLE_METRICS)

    def test_no_outcome_is_defined_as_success_anywhere_in_the_report(self):
        text = self.text(self.report()).lower()

        self.assertNotIn("success rate", text)
        self.assertIn("no outcome is defined here as success", text)

    def test_every_caveat_is_printed_with_every_report(self):
        """They are part of the report, not documentation: an edit that dropped one fails here."""
        text = self.text(self.report())

        for caveat in analytics._CAVEATS:
            self.assertIn(caveat, text)

    def test_the_report_denies_causation_in_the_period_comparison(self):
        report = self.report(jobs=[job(f"j{i}") for i in range(12)],
                             activities={**{f"j{i}": [applied(f"j{i}", 10 + i)] for i in range(6)},
                                         **{f"j{i}": [applied(f"j{i}", TREND_WINDOW_DAYS + 10 + i)]
                                            for i in range(6, 12)}})

        self.assertIn("not evidence that anything you changed caused the difference", self.text(report))

    def test_the_report_does_not_describe_the_person_apart_from_denying_it_does(self):
        text = self.text(self.report(jobs=[job("j1")], activities={"j1": [applied("j1", 9)]}))
        stripped = text.replace("A rate is not your ability and not your worth.", "")

        for phrase in ("you are doing", "your chances", "you should", "better than"):
            self.assertNotIn(phrase, stripped.lower())


class MedianTests(AnalyticsTestCase):
    """The one timing the stored dates can support, and the reasons it is refused."""

    def report_with_pairs(self, pairs):
        return self.report(jobs=[job(f"j{i}") for i in range(len(pairs))],
                           activities={f"j{i}": [applied(f"j{i}", applied_days),
                                                 replied(f"j{i}", reply_days)]
                                       for i, (applied_days, reply_days) in enumerate(pairs)})

    def test_a_median_of_the_recorded_pairs_is_reported_with_its_sample_size(self):
        report = self.report_with_pairs([(30, 20), (40, 30), (50, 45)])

        line = self.line_containing(report, "Days from application to first recorded reply")
        self.assertIn("10 day(s)", line)
        self.assertIn("middle of 3 pair(s)", line)

    def test_no_pair_at_all_is_reported_as_nothing_to_measure(self):
        report = self.report(jobs=[job("j1")], activities={"j1": [applied("j1", 9)]})

        line = self.line_containing(report, "Days from application to first recorded reply")
        self.assertIn("no application has both an application date and a reply date", line)

    def test_a_median_is_withheld_below_the_sample_floor_and_says_how_many_it_has(self):
        report = self.report_with_pairs([(30, 20), (40, 30)])

        line = self.line_containing(report, "Days from application to first recorded reply")
        self.assertIn("not reported", line)
        self.assertIn("only 2 application(s)", line)
        self.assertIn(f"{MIN_MEDIAN_SAMPLES} are needed", line)

    def test_a_reply_dated_before_the_application_is_excluded_not_counted_as_negative(self):
        """A response dated before the application is a typing mistake, not a negative gap."""
        report = self.report_with_pairs([(30, 20), (40, 30), (50, 45), (20, 90)])

        line = self.line_containing(report, "Days from application to first recorded reply")
        self.assertIn("middle of 3 pair(s)", line)
        self.assertIn("10 day(s)", line)

    def test_a_reply_with_no_date_is_reported_rather_than_silently_dropped(self):
        """A status change records when the row was saved, not the day the employer wrote - so it cannot be
        used as a date, and the report says so rather than quietly shrinking its sample."""
        report = self.report(jobs=[job("j1")],
                             trackers={"j1": tracker("j1", ApplicationStatus.RESPONSE_RECEIVED)},
                             activities={"j1": [applied("j1", 40)]})

        line = self.line_containing(report, "Days from application to first recorded reply")
        self.assertIn("no reply date", line)
        self.assertIn("status change records when it was saved here", line)

    def test_the_timing_that_is_never_available_says_why(self):
        report = self.report(jobs=[job("j1")], activities={"j1": [applied("j1", 9)]})

        line = self.line_containing(report, "Interview rounds between the day")
        self.assertIn("not reported", line)
        self.assertIn("nothing here tracks how long a round lasted", line)
        self.assertIn("a meeting, not a state", line)

    def test_a_median_uses_the_first_recorded_reply_not_the_latest(self):
        report = self.report(jobs=[job("j1")], activities={"j1": [
            applied("j1", 40), replied("j1", 35), replied("j1", 2)]})
        report = self.report(jobs=[job("j1"), job("j2"), job("j3")],
                             activities={"j1": [applied("j1", 40), replied("j1", 35), replied("j1", 2)],
                                         "j2": [applied("j2", 40), replied("j2", 30)],
                                         "j3": [applied("j3", 50), replied("j3", 45)]})

        line = self.line_containing(report, "Days from application to first recorded reply")
        self.assertIn("5 day(s)", line, "the earliest reply is 5 days after the application for j1")


class PeriodComparisonTests(AnalyticsTestCase):
    """Two windows, compared only when both can carry a comparison."""

    def report_with(self, recent: int, earlier: int, *, replies_recent: int = 0):
        jobs, activities = [], {}
        for index in range(recent):
            listing_id = f"r{index}"
            jobs.append(job(listing_id))
            activities[listing_id] = [applied(listing_id, 10 + index)]
            if index < replies_recent:
                activities[listing_id].append(replied(listing_id, 5 + index))
        for index in range(earlier):
            listing_id = f"e{index}"
            jobs.append(job(listing_id))
            activities[listing_id] = [applied(listing_id, TREND_WINDOW_DAYS + 10 + index)]
        return self.report(jobs=jobs, activities=activities)

    def test_both_windows_are_reported_and_compared_when_both_are_large_enough(self):
        report = self.report_with(recent=6, earlier=5, replies_recent=3)

        text = self.text(report)
        self.assertIn(f"the last {TREND_WINDOW_DAYS} days hold 3 of 6", text)
        self.assertIn("50% against 0%", text)
        self.assertIn("not evidence that anything you changed caused the difference", text)

    def test_one_thin_window_withholds_the_comparison_and_names_both_counts(self):
        report = self.report_with(recent=6, earlier=2)

        text = self.text(report)
        self.assertIn("0 of 6", text)
        self.assertIn("0 of 2", text)
        self.assertIn("The two periods are not compared", text)
        self.assertIn("has 6 in the recent one and 2 in the one before", text)
        self.assertNotIn("% against", text)

    def test_an_application_with_no_date_is_left_out_of_both_windows_and_counted_as_left_out(self):
        report = self.report(jobs=[job("j1")], trackers={"j1": tracker("j1", ApplicationStatus.SUBMITTED_UNVERIFIED)},
                             rounds=[])

        self.assertIn("1 application(s) have no application date recorded", self.text(report))

    def test_the_most_recent_day_of_the_window_is_inside_it(self):
        """The window is the last N days *including* today, and its earliest day is inside it too."""
        report = self.report(jobs=[job("j1")], activities={"j1": [
            ApplicationActivity(ActivityKind.APPLIED, TODAY - timedelta(days=TREND_WINDOW_DAYS - 1),
                                "the first day of the window")]})

        text = self.text(report)
        self.assertIn(f"the last {TREND_WINDOW_DAYS} days hold 0 of 1", text,
                      "the application is in the recent window; none of the zero replies are")
        self.assertIn("before that hold 0 of 0", text)

    def test_an_application_exactly_one_window_old_belongs_to_the_earlier_window(self):
        report = self.report(jobs=[job("j1")], activities={"j1": [
            ApplicationActivity(ActivityKind.APPLIED, TODAY - timedelta(days=TREND_WINDOW_DAYS),
                                "just outside the recent window")]})

        text = self.text(report)
        self.assertIn(f"the last {TREND_WINDOW_DAYS} days hold 0 of 0", text)
        self.assertIn("before that hold 0 of 1", text)

    def test_nothing_recorded_means_nothing_to_compare(self):
        report = self.report()

        self.assertEqual(report.periods, ())
        self.assertIn("Nothing to compare", self.text(report))


class ReportShapeTests(AnalyticsTestCase):
    """The whole report: its sections, its determinism, and its one-line summary."""

    def test_the_report_has_every_section_in_reading_order(self):
        report = self.report(jobs=[job("j1")], activities={"j1": [applied("j1", 9)]})

        self.assertEqual(report.describe(), tuple(report.describe()), "describe() is deterministic")
        text = self.text(report)
        positions = [text.index(heading) for heading in (
            "Progress from the records", "What the records hold",
            "How often, against a named denominator", "Timing", "This period against the one before",
            "What cannot be measured here", "How to read this")]
        self.assertEqual(positions, sorted(positions), "the sections read in a fixed order")

    def test_the_report_says_which_day_it_was_computed_for_from_the_caller(self):
        report = self.report(today=date(2026, 3, 1))

        self.assertEqual(report.generated_on, date(2026, 3, 1))
        self.assertIn("2026-03-01", self.text(report))

    def test_the_headline_withholds_a_rate_below_the_floor_and_shows_one_above_it(self):
        small = self.report(jobs=[job("j1")], activities={"j1": [applied("j1", 9)]})
        large = self.report(jobs=[job(f"j{i}") for i in range(10)],
                            activities={f"j{i}": [applied(f"j{i}", 20), replied(f"j{i}", 10)]
                                        for i in range(10)})

        self.assertIn("too few to report a rate", small.headline())
        self.assertIn("10 application(s) recorded as sent", large.headline())
        self.assertIn("10 with a recorded reply (100%)", large.headline())

    def test_an_empty_database_headline_reports_no_percentage(self):
        headline = self.report().headline()

        self.assertIn("No application has been recorded as sent", headline)
        self.assertNotIn("%", headline)

    def test_an_empty_report_still_says_where_the_numbers_would_start_from(self):
        text = self.text(self.report())

        self.assertIn("Nothing is recorded as sent yet", text)
        self.assertIn("start as soon as you write down an application", text)


class StoreBackedReportTests(unittest.TestCase):
    """The same report read through a real database, so the gathering path is exercised too."""

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.store = CareerStore(str(Path(self._directory.name) / "analytics.sqlite3"))
        self.addCleanup(self.store.close)

    def test_the_report_reads_the_records_a_person_actually_stored(self):
        for index in range(6):
            listing_id = f"j{index}"
            self.store.save_job(job(listing_id))
            self.store.save_tracker(ApplicationTracker(listing_id))
            self.store.add_activity(listing_id, applied(listing_id, 30 + index))
        self.store.add_activity("j0", replied("j0", 12))
        self.store.add_activity("j1", replied("j1", 13))

        report = report_from_store(self.store, today=TODAY)

        self.assertEqual(report.applications_recorded, 6)
        rate_line = [line for line in report.describe()
                     if "Applications with a recorded reply" in line and " of " in line][0]
        self.assertIn("2 of 6 recorded as sent", rate_line)

    def test_an_application_with_no_tracker_record_is_still_counted_if_an_entry_says_it_was_sent(self):
        """The activity log is a record in its own right; requiring a tracker row would hide it."""
        self.store.save_job(job("j1"))
        self.store.add_activity("j1", applied("j1", 15))

        self.assertEqual(report_from_store(self.store, today=TODAY).applications_recorded, 1)

    def test_the_report_reads_the_whole_tracker_table_rather_than_the_reminders_only(self):
        for index in range(3):
            listing_id = f"j{index}"
            self.store.save_job(job(listing_id))
            self.store.save_tracker(ApplicationTracker(listing_id))
        self.store.set_follow_up("j1", TODAY + timedelta(days=1), note="chase")

        self.assertEqual([record.listing_id for record in self.store.list_trackers()], ["j0", "j1", "j2"])
        self.assertEqual([record.listing_id for record in self.store.list_follow_up_trackers()], ["j1"])

    def test_the_report_is_read_only(self):
        self.store.save_job(job("j1"))
        self.store.add_activity("j1", applied("j1", 15))
        before = self.store.get_tracker("j1")

        report_from_store(self.store, today=TODAY)

        self.assertEqual(self.store.get_tracker("j1"), before, "no status was created or changed")

    def test_a_round_stored_against_an_application_is_counted_by_the_report(self):
        self.store.save_job(job("j1"))
        self.store.add_activity("j1", applied("j1", 20))
        self.store.record_interview("j1", InterviewStage.SCREENING, TODAY - timedelta(days=2))

        report = report_from_store(self.store, today=TODAY)

        self.assertIn("Interview rounds recorded: 1", "\n".join(report.describe()))
        self.assertIn("Applications with an interview round recorded: 1", "\n".join(report.describe()))


if __name__ == "__main__":  # pragma: no cover - convenience for a focused run
    unittest.main()
