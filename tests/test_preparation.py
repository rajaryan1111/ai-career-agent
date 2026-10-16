import unittest
from datetime import date, timedelta

from career_agent.core import (
    ApplicationTracker, Availability, InterviewMode, InterviewOutcome, InterviewRound, InterviewStage,
    JobListing, PreparationItem, PreparationKind,
)
from career_agent.followups import reminder_for
from career_agent.preparation import (
    Action, ActionKind, Timing, actions, describe_actions, done_items, interview_summary,
    open_items, preparation_summary, rounds_ordered, summary, timing_for,
)

TODAY = date(2026, 10, 15)


def job(listing_id="j1", employer="Sandbox Systems", role="Data Engineer") -> JobListing:
    return JobListing(listing_id, "manual", "Manual entry", f"https://jobs.example.invalid/{listing_id}",
                      employer, role, availability_status=Availability.OPEN)


def item(title="Tailor the résumé", *, days=None, kind=PreparationKind.TAILORING, listing_id="j1",
         done=False) -> PreparationItem:
    return PreparationItem(
        listing_id=listing_id, title=title, kind=kind,
        due_on=None if days is None else TODAY + timedelta(days=days),
        done_at="2026-10-10T00:00:00+00:00" if done else None,
    )


def round_(stage=InterviewStage.TECHNICAL, *, days=1, listing_id="j1", mode=InterviewMode.VIDEO,
           outcome=InterviewOutcome.AWAITING, notes=None) -> InterviewRound:
    return InterviewRound(listing_id=listing_id, stage=stage, scheduled_on=TODAY + timedelta(days=days),
                          mode=mode, outcome=outcome, notes=notes)


def reminder(*, days=-2, listing_id="j1", note=None, tracker_status=None):
    tracker = ApplicationTracker(listing_id)
    if tracker_status is not None:
        tracker = ApplicationTracker(listing_id, tracker_status)
    return reminder_for(tracker.with_follow_up(TODAY + timedelta(days=days), note=note), job(listing_id), TODAY)


class TimingTests(unittest.TestCase):
    """Where a record stands against the day it is looked at - and that "no day" is its own answer."""

    def test_the_five_timings(self):
        self.assertIs(timing_for(TODAY - timedelta(days=1), TODAY), Timing.OVERDUE)
        self.assertIs(timing_for(TODAY, TODAY), Timing.TODAY)
        self.assertIs(timing_for(TODAY + timedelta(days=3), TODAY), Timing.SOON)
        self.assertIs(timing_for(TODAY + timedelta(days=30), TODAY), Timing.LATER)
        self.assertIs(timing_for(None, TODAY), Timing.UNDATED)

    def test_undated_is_not_called_overdue(self):
        """An item nobody scheduled is not late; calling it late would devalue the word."""
        self.assertIsNot(timing_for(None, TODAY), Timing.OVERDUE)

    def test_the_soon_window_is_the_reporting_window_not_a_rule(self):
        day = TODAY + timedelta(days=8)

        self.assertIs(timing_for(day, TODAY, upcoming_days=7), Timing.LATER)
        self.assertIs(timing_for(day, TODAY, upcoming_days=8), Timing.SOON)


class PreparationListTests(unittest.TestCase):
    def test_open_items_come_earliest_first_with_undated_last(self):
        dated_late = item("Later thing", days=5)
        dated_soon = item("Sooner thing", days=1, kind=PreparationKind.RESEARCH)

        ordered = open_items([dated_late, dated_soon, item("No day", kind=PreparationKind.OTHER)])

        self.assertEqual([entry.title for entry in ordered], ["Sooner thing", "Later thing", "No day"])

    def test_a_finished_item_leaves_the_open_list(self):
        done = item("Finished", done=True)

        self.assertEqual(open_items([done]), ())
        self.assertEqual([entry.title for entry in done_items([done])], ["Finished"])

    def test_nothing_recorded_is_not_the_same_as_everything_done(self):
        self.assertIn("No preparation items are recorded", preparation_summary([], TODAY))
        self.assertIn("Every preparation item is done", preparation_summary([item(done=True)], TODAY))

    def test_the_summary_counts_overdue_today_and_undated(self):
        summary_line = preparation_summary(
            [item("A", days=-2), item("B", days=0), item("C"), item("D", done=True)], TODAY)

        self.assertIn("3 item(s) still to do", summary_line)
        self.assertIn("1 overdue", summary_line)
        self.assertIn("1 due today", summary_line)
        self.assertIn("1 with no day set", summary_line)
        self.assertNotIn("1 item(s)", summary_line)


class InterviewListTests(unittest.TestCase):
    def test_the_next_round_comes_first_and_the_recent_past_follows(self):
        soon = round_(days=2, listing_id="j2")
        nearer = round_(days=1, listing_id="j1")
        last_month = round_(days=-30, listing_id="j3")
        yesterday = round_(days=-1, listing_id="j4")

        ordered = rounds_ordered([last_month, soon, yesterday, nearer], TODAY)

        self.assertEqual([entry.listing_id for entry in ordered], ["j1", "j2", "j4", "j3"])

    def test_no_round_recorded_says_so(self):
        self.assertIn("No interview rounds are recorded yet", interview_summary([], TODAY))

    def test_the_summary_names_the_next_round_and_how_soon(self):
        line = interview_summary([round_(InterviewStage.TECHNICAL, days=1)], TODAY)

        self.assertEqual(line, "Next: Technical interview tomorrow on 2026-10-16.")

    def test_today_reads_as_today(self):
        self.assertIn("Screening call today", interview_summary([round_(InterviewStage.SCREENING, days=0)], TODAY))

    def test_a_finished_round_without_a_note_invites_one_rather_than_guessing(self):
        line = interview_summary([round_(days=-3)], TODAY)

        self.assertIn("No round ahead", line)
        self.assertIn("only you can say", line)
        self.assertNotIn("went well", line)


class ActionTests(unittest.TestCase):
    """The combined list - the one answer to "what should I do today?"."""

    def setUp(self):
        self.jobs = {"j1": job("j1"), "j2": job("j2", employer="Other Ltd", role="Analyst")}

    def test_the_three_kinds_appear_with_their_application(self):
        found = actions([item("Tailor the résumé", days=0)],
                        [round_(days=1, notes="ask about on-call")],
                        [reminder(days=-2, note="chase the reply")],
                        self.jobs, TODAY)

        self.assertEqual([action.kind for action in found],
                         [ActionKind.FOLLOW_UP, ActionKind.PREPARATION, ActionKind.INTERVIEW])
        self.assertEqual(found[0].detail, "chase the reply")
        self.assertEqual(found[2].employer_name, "Sandbox Systems")
        self.assertEqual(found[2].role_title, "Data Engineer")
        self.assertEqual(found[2].detail, "ask about on-call")

    def test_actionable_items_come_first_most_overdue_first(self):
        found = actions([item("Due today", days=0), item("Two days late", days=-2), item("Next week", days=6)],
                        [], [], self.jobs, TODAY)

        self.assertEqual([action.what for action in found], ["Two days late", "Due today", "Next week"])
        self.assertEqual([action.is_actionable for action in found], [True, True, False])

    def test_most_overdue_action_wins_across_kinds(self):
        """Age outranks kind for overdue work; kind priority only breaks same-day ties."""
        found = actions(
            [item("Preparation overdue five days", days=-5)],
            [round_(days=-10)],
            [reminder(days=-1, note="recent follow-up")],
            self.jobs,
            TODAY,
        )

        self.assertEqual(
            [(action.kind, action.days_away) for action in found],
            [
                (ActionKind.INTERVIEW, -10),
                (ActionKind.PREPARATION, -5),
                (ActionKind.FOLLOW_UP, -1),
            ],
        )

    def test_kind_priority_breaks_ties_for_overdue_actions(self):
        found = actions(
            [item("Preparation", days=-2)],
            [round_(days=-2)],
            [reminder(days=-2)],
            self.jobs,
            TODAY,
        )

        self.assertEqual(
            [action.kind for action in found],
            [ActionKind.INTERVIEW, ActionKind.FOLLOW_UP, ActionKind.PREPARATION],
        )

    def test_an_appointment_outranks_a_chase_on_the_same_day(self):
        """See the module docstring: somebody else's clock first, then a promise, then your own list."""
        found = actions([item("Tailor the résumé", days=0)], [round_(days=0)], [reminder(days=0)],
                        self.jobs, TODAY)

        self.assertEqual([action.kind for action in found],
                         [ActionKind.INTERVIEW, ActionKind.FOLLOW_UP, ActionKind.PREPARATION])

    def test_a_round_whose_day_has_passed_stays_on_the_list(self):
        found = actions([], [round_(days=-2, outcome=InterviewOutcome.WENT_WELL)], [], self.jobs, TODAY)

        self.assertEqual(len(found), 1)
        self.assertIs(found[0].timing, Timing.OVERDUE)
        self.assertEqual(found[0].days_away, -2)

    def test_the_list_can_be_limited_to_what_is_actionable(self):
        """A daily reminder asks for the near list: no undated items, and nothing beyond the window.

        "Later" is the outer window, not "not today" - a round in three days is coming up and belongs in a
        list that is about what to prepare for, which is the distinction the window exists to make.
        """
        found = actions([item("Next month", days=30), item("No day")], [round_(days=3)], [], self.jobs, TODAY,
                        include_later=False, include_undated=False)

        self.assertEqual([action.kind for action in found], [ActionKind.INTERVIEW])
        self.assertIs(found[0].timing, Timing.SOON)

    def test_the_order_does_not_depend_on_the_input_order(self):
        first = actions([item("Later", days=6), item("Sooner", days=1)], [], [], self.jobs, TODAY)
        second = actions([item("Sooner", days=1), item("Later", days=6)], [], [], self.jobs, TODAY)

        self.assertEqual([action.describe() for action in first], [action.describe() for action in second])

    def test_a_record_whose_listing_is_gone_is_still_shown(self):
        """The store deletes these rows with their listing; if one survives, hiding it would lose a task."""
        found = actions([item("Tailor the résumé", days=0, listing_id="gone")], [], [],
                        self.jobs, TODAY)

        self.assertEqual(len(found), 1)
        self.assertIn("no longer stored", found[0].employer_name)

    def test_a_follow_up_keeps_the_status_it_had_without_the_action_claiming_anything(self):
        found = actions([], [], [reminder(days=0, tracker_status=None)], self.jobs, TODAY)

        self.assertIn("Follow up on this application", found[0].what)
        self.assertNotIn("replied", found[0].describe())
        self.assertNotIn("interview", found[0].describe().lower().replace("Follow up on this application", ""))


class SummaryAndReportTests(unittest.TestCase):
    def test_nothing_recorded_reads_as_nothing_waiting(self):
        line = summary((), TODAY)

        self.assertIn("Nothing is waiting on you", line)

    def test_nothing_due_is_not_the_same_as_nothing_recorded(self):
        found = actions([item("Next week", days=6)], [], [], {"j1": job()}, TODAY)

        line = summary(found, TODAY)

        self.assertIn("Nothing is due yet", line)
        self.assertIn("1 item(s) are coming up", line)
        self.assertNotIn("overdue", line)

    def test_the_summary_counts_overdue_and_today_separately(self):
        found = actions([item("Late", days=-1), item("Today", days=0)], [], [], {"j1": job()}, TODAY)

        line = summary(found, TODAY)

        self.assertIn("2 item(s) need you now", line)
        self.assertIn("1 overdue", line)
        self.assertIn("1 due today", line)

    def test_a_report_line_carries_the_day_the_application_and_the_reason(self):
        found = actions([item("Tailor the résumé", days=-1)], [], [], {"j1": job()}, TODAY)

        line = found[0].describe()

        self.assertIn("2026-10-14", line)
        self.assertIn("1 day(s) overdue", line)
        self.assertIn("Tailor the résumé", line)
        self.assertIn("Data Engineer at Sandbox Systems", line)

    def test_an_undated_item_says_so_rather_than_inventing_a_day(self):
        found = actions([item("No day")], [], [], {"j1": job()}, TODAY)

        self.assertIn("no day set", found[0].describe())
        self.assertNotIn("2026", found[0].describe())

    def test_a_limited_report_states_how_many_it_left_out(self):
        found = actions([item(f"Task {number}", days=number) for number in range(5)], [], [], {"j1": job()},
                        TODAY)

        lines = describe_actions(found, limit=2)

        self.assertEqual(len(lines), 3)
        self.assertIn("and 3 more, not listed here", lines[-1])

    def test_an_unlimited_report_leaves_nothing_out(self):
        found = actions([item(f"Task {number}", days=number) for number in range(3)], [], [], {"j1": job()},
                        TODAY)

        self.assertEqual(len(describe_actions(found)), 3)


class ClaimTests(unittest.TestCase):
    """The vocabulary this module can put in front of a person: no employer decisions, ever."""

    def test_no_interview_outcome_sounds_like_an_employer_decision(self):
        for outcome in InterviewOutcome:
            with self.subTest(outcome=outcome):
                label = InterviewRound("j1", InterviewStage.TECHNICAL, TODAY, outcome=outcome).outcome_label
                self.assertNotIn("passed", label.lower())
                self.assertNotIn("failed", label.lower())
                self.assertNotIn("offer", label.lower())
                self.assertNotIn("rejected", label.lower())
                self.assertNotIn("accepted", label.lower())

    def test_a_round_today_is_still_ahead_rather_than_past(self):
        """The case a summary must not bury: the interview is this morning, not history."""
        self.assertTrue(round_(days=0).is_ahead(TODAY))
        self.assertFalse(round_(days=0).is_past(TODAY))
        self.assertTrue(round_(days=3).is_ahead(TODAY))
        self.assertTrue(round_(days=-1).is_past(TODAY))
        self.assertFalse(round_(days=-1).is_ahead(TODAY))

    def test_each_action_names_the_record_it_came_from(self):
        """A caller acts on the record a line names, so the id travels with the line."""
        from career_agent.core import PreparationItem as Item

        prepared = Item(listing_id="j1", title="Tailor the résumé", preparation_id=7, due_on=TODAY)
        recorded = InterviewRound(listing_id="j1", stage=InterviewStage.TECHNICAL, scheduled_on=TODAY,
                                  round_id=9)

        found = actions([prepared], [recorded], [reminder(days=0)], {"j1": job()}, TODAY)

        by_kind = {action.kind: action for action in found}
        self.assertEqual(by_kind[ActionKind.PREPARATION].record_id, 7)
        self.assertEqual(by_kind[ActionKind.INTERVIEW].record_id, 9)
        self.assertIsNone(by_kind[ActionKind.FOLLOW_UP].record_id,
                          "a follow-up belongs to the application record, not to a row of its own")

    def test_an_action_never_carries_a_status(self):
        """The action list has no field that could assert an application's state."""
        fields = set(Action.__dataclass_fields__)

        self.assertNotIn("status", fields)
        self.assertNotIn("candidate_confirmed", fields)
