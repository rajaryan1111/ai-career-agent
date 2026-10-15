"""Tests for follow-up days: what a reminder says, what it must never do, and the calendar file.

The fixtures are invented applications belonging to nobody. The two properties these tests spend the most
effort on are the ones that would be damaging to get wrong: a reminder must never move an application's
status or invent a reply, and the calendar file must be well formed for a real calendar application to
read - a folded line, an escaped comma or a mis-counted multi-byte character turns the export into a file
that silently does nothing.
"""
from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone

from career_agent.core import (
    ApplicationStatus,
    ApplicationTracker,
    Availability,
    JobListing,
    validate_follow_up_date,
    validate_follow_up_note,
)
from career_agent.followups import (
    CALENDAR_PRODUCT_ID,
    FollowUpState,
    calendar_file_name,
    reminder_for,
    reminders,
    state_for,
    summary,
    to_calendar,
)

TODAY = date(2026, 10, 15)
NOW = datetime(2026, 10, 15, 6, 30, tzinfo=timezone.utc)


def job(listing_id: str = "j1", *, employer: str = "Sandbox Systems", role: str = "Data Engineer") -> JobListing:
    """An invented listing: example.invalid is reserved for documentation and reachable by nobody."""
    return JobListing(listing_id, "fixture", "Fixture", f"https://jobs.example.invalid/{listing_id}",
                      employer, role, availability_status=Availability.UNKNOWN)


def tracker(listing_id: str = "j1", *, days: int | None = 2, note: str | None = None,
            status: ApplicationStatus = ApplicationStatus.SUBMITTED_UNVERIFIED) -> ApplicationTracker:
    """An invented application with, by default, a follow-up day two days from the test's today."""
    base = ApplicationTracker(listing_id, status)
    if days is None:
        return base
    return base.with_follow_up(TODAY + timedelta(days=days), note=note)


class StateTests(unittest.TestCase):
    """Which day is which."""

    def test_the_four_states_of_a_recorded_day(self):
        cases = ((-1, FollowUpState.OVERDUE), (0, FollowUpState.DUE_TODAY), (1, FollowUpState.UPCOMING),
                 (7, FollowUpState.UPCOMING), (8, FollowUpState.LATER), (365, FollowUpState.LATER))
        for days, expected in cases:
            with self.subTest(days=days):
                self.assertEqual(state_for(TODAY + timedelta(days=days), TODAY), expected)

    def test_no_day_recorded_is_its_own_state_rather_than_due(self):
        self.assertEqual(state_for(None, TODAY), FollowUpState.NONE)

    def test_the_upcoming_window_is_the_reporting_window_not_a_rule(self):
        """The same day is 'upcoming' in a weekly report and 'later' in a daily one."""
        in_ten_days = TODAY + timedelta(days=10)

        self.assertEqual(state_for(in_ten_days, TODAY), FollowUpState.LATER)
        self.assertEqual(state_for(in_ten_days, TODAY, upcoming_days=14), FollowUpState.UPCOMING)


class ReminderTests(unittest.TestCase):
    """What one reminder says."""

    def test_a_reminder_carries_what_a_person_needs_to_recognise_it(self):
        item = reminder_for(tracker(days=-3, note="ask about the take-home"), job(), TODAY)

        self.assertIsNotNone(item)
        self.assertEqual(item.listing_id, "j1")
        self.assertEqual(item.state, FollowUpState.OVERDUE)
        self.assertEqual(item.days_away, -3)
        self.assertEqual(item.employer_name, "Sandbox Systems")
        self.assertEqual(item.role_title, "Data Engineer")
        self.assertEqual(item.note, "ask about the take-home")
        self.assertEqual(item.status, ApplicationStatus.SUBMITTED_UNVERIFIED)
        self.assertIn("3 day(s) overdue", item.describe())
        self.assertIn("ask about the take-home", item.describe())

    def test_an_application_with_no_day_is_left_out_rather_than_shown_empty(self):
        self.assertIsNone(reminder_for(tracker(days=None), job(), TODAY))

    def test_only_today_and_earlier_are_actionable(self):
        self.assertTrue(reminder_for(tracker(days=0), job(), TODAY).is_actionable)
        self.assertTrue(reminder_for(tracker(days=-1), job(), TODAY).is_actionable)
        self.assertFalse(reminder_for(tracker(days=1), job(), TODAY).is_actionable)

    def test_reading_a_reminder_changes_nothing_about_the_application(self):
        """The whole point of the separation: a reminder is not a status change."""
        before = tracker(days=-5, status=ApplicationStatus.SUBMITTED_UNVERIFIED)

        item = reminder_for(before, job(), TODAY)

        self.assertEqual(item.status, before.status)
        self.assertEqual(before.status, ApplicationStatus.SUBMITTED_UNVERIFIED)
        self.assertIsNone(before.status_evidence)
        self.assertFalse(before.candidate_confirmed)

    def test_a_reminder_does_not_claim_a_reply_arrived(self):
        """Silence from an employer is not evidence of anything, and the text must not imply otherwise."""
        text = reminder_for(tracker(days=3), job(), TODAY).describe().casefold()

        for phrase in ("no response", "has not replied", "no reply", "rejected", "closed"):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, text)


class OrderingTests(unittest.TestCase):
    """The order is what to act on first, and it is stable."""

    def pairs(self):
        return [
            (tracker("later", days=30), job("later")),
            (tracker("today", days=0), job("today")),
            (tracker("soon", days=3), job("soon")),
            (tracker("old", days=-10), job("old")),
            (tracker("recent", days=-1), job("recent")),
            (tracker("none", days=None), job("none")),
        ]

    def test_overdue_comes_first_most_overdue_first_then_today_then_the_rest(self):
        found = reminders(self.pairs(), TODAY)

        self.assertEqual([item.listing_id for item in found],
                         ["old", "recent", "today", "soon", "later"])

    def test_the_order_does_not_depend_on_the_input_order(self):
        found = reminders(self.pairs(), TODAY)
        reversed_input = reminders(list(reversed(self.pairs())), TODAY)

        self.assertEqual([item.listing_id for item in found],
                         [item.listing_id for item in reversed_input])

    def test_the_far_future_can_be_excluded_from_a_report(self):
        found = reminders(self.pairs(), TODAY, include_later=False)

        self.assertNotIn("later", [item.listing_id for item in found])
        self.assertIn("soon", [item.listing_id for item in found])


class SummaryTests(unittest.TestCase):
    """The one line a person reads first."""

    def test_nothing_recorded_says_so_and_says_what_to_do(self):
        text = summary(())

        self.assertIn("No follow-ups are recorded", text)
        self.assertIn("Set a day", text)

    def test_recorded_but_not_due_yet_is_not_the_same_as_nothing_recorded(self):
        text = summary(reminders([(tracker("soon", days=3), job("soon"))], TODAY))

        self.assertIn("none are due yet", text)
        self.assertNotIn("No follow-ups are recorded", text)

    def test_due_today_and_overdue_are_counted_separately(self):
        found = reminders([(tracker("old", days=-2), job("old")), (tracker("today", days=0), job("today"))],
                          TODAY)

        text = summary(found)

        self.assertIn("1 overdue", text)
        self.assertIn("1 due today", text)
        self.assertIn("2 application(s)", text)

    def test_a_due_reminder_is_never_described_as_a_response(self):
        text = summary(reminders([(tracker("old", days=-2), job("old"))], TODAY)).casefold()

        self.assertNotIn("reply", text)
        self.assertNotIn("response", text)
        self.assertNotIn("interview", text)


class CalendarTests(unittest.TestCase):
    """The exported file, which a real calendar application has to be able to read."""

    def document(self, items=None, *, product_id=CALENDAR_PRODUCT_ID) -> str:
        found = reminders(items or [(tracker("j1", days=-2, note="ask about the take-home"),
                                     job())], TODAY)
        return to_calendar(found, now=NOW, product_id=product_id)

    def physical_lines(self, text: str) -> list[str]:
        return [line for line in text.split("\r\n") if line != ""]

    def logical_lines(self, text: str) -> list[str]:
        """Unfold: a continuation line starts with a space and belongs to the line before it."""
        logical: list[str] = []
        for line in self.physical_lines(text):
            if line.startswith(" ") and logical:
                logical[-1] += line[1:]
            else:
                logical.append(line)
        return logical

    def test_the_document_wraps_events_in_a_calendar(self):
        lines = self.logical_lines(self.document())

        self.assertEqual(lines[0], "BEGIN:VCALENDAR")
        self.assertEqual(lines[-1], "END:VCALENDAR")
        self.assertIn("VERSION:2.0", lines)
        self.assertEqual(lines.count("BEGIN:VEVENT"), 1)
        self.assertEqual(lines.count("END:VEVENT"), 1)
        self.assertIn(f"PRODID:{CALENDAR_PRODUCT_ID}", lines)

    def test_an_event_is_an_all_day_entry_on_the_follow_up_day(self):
        lines = self.logical_lines(self.document())

        self.assertIn("DTSTART;VALUE=DATE:20261013", lines)
        self.assertIn("DTEND;VALUE=DATE:20261014", lines, "the end of an all-day event is exclusive")
        self.assertIn("DTSTAMP:20261015T063000Z", lines)

    def test_the_event_says_what_it_is_and_that_it_is_not_from_the_employer(self):
        text = self.document()

        self.assertIn("SUMMARY:Follow up: Data Engineer at Sandbox Systems", text)
        self.assertIn("not a statement from the employer", text.replace("\\n", " "))

    def test_the_event_invites_nobody_and_links_nowhere(self):
        """An export must not start telling other people about somebody's job hunt."""
        text = self.document()

        for forbidden in ("ATTENDEE", "ORGANIZER", "MAILTO", "HTTP://", "HTTPS://"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text.upper())

    def test_the_identifier_is_derived_from_the_application_and_the_day(self):
        """So importing twice updates one event, while a new day is a new event."""
        first = self.document()
        second = self.document()

        self.assertIn("UID:follow-up-j1-20261013@ai-career-agent.local", first)
        self.assertEqual(self.logical_lines(first), self.logical_lines(second),
                         "exporting the same data again produces the same file")

        moved = reminders([(tracker("j1", days=4), job())], TODAY)
        moved_text = to_calendar(moved, now=NOW)

        self.assertIn("UID:follow-up-j1-20261019@ai-career-agent.local", moved_text)

    def test_commas_semicolons_and_backslashes_in_a_note_are_escaped(self):
        text = self.document([(tracker("j1", days=1, note="ask Raj; re: pay, and C:\\path"), job())])

        description = next(line for line in self.logical_lines(text) if line.startswith("DESCRIPTION:"))
        self.assertIn("ask Raj\\; re: pay\\, and C:\\\\path", description)

    def test_newlines_from_a_note_cannot_break_the_file(self):
        """A note is single-line once validated, but the escaper must hold even for a forged record.

        ``validate_follow_up_note`` collapses whitespace, so a newline cannot reach storage through the
        app - which is exactly why the escaper is tested with one that was constructed directly: this is
        the line of defence a hand-edited database row meets.
        """
        forged = ApplicationTracker("j1", ApplicationStatus.SUBMITTED_UNVERIFIED,
                                    follow_up_on=TODAY, follow_up_note="first\nsecond")

        text = to_calendar(reminders([(forged, job())], TODAY), now=NOW)

        self.assertIn("first\\nsecond", text)
        self.assertEqual(text.count("BEGIN:VEVENT"), 1)
        self.assertNotIn("first\r\nsecond", text)

    def test_no_physical_line_exceeds_the_fold_width(self):
        text = self.document([(tracker("j1", days=1, note="x" * 280), job(role="Développeur — भारत"))])

        for line in self.physical_lines(text):
            with self.subTest(line=line[:40]):
                self.assertLessEqual(len(line.encode("utf-8")), 75)

    def test_folding_never_splits_a_character_in_half(self):
        text = self.document([(tracker("j1", days=1, note="देवनागरी " * 20), job(role="इंजीनियर"))])

        self.assertNotIn("\ufffd", text)
        self.assertIn("इंजीनियर", "".join(self.logical_lines(text)))

    def test_unfolding_restores_the_text_exactly(self):
        note = "ask about the take-home, and; the panel — plus देवनागरी"
        text = self.document([(tracker("j1", days=1, note=note), job())])

        description = next(line for line in self.logical_lines(text) if line.startswith("DESCRIPTION:"))

        self.assertIn(note.replace(";", "\\;").replace(",", "\\,"), description)

    def test_every_line_ends_with_the_specified_break(self):
        text = self.document()

        self.assertTrue(text.endswith("\r\n"))
        self.assertEqual(text.count("\n"), text.count("\r\n"), "no bare line feed anywhere")

    def test_the_export_needs_the_moment_it_was_produced_with_its_zone(self):
        with self.assertRaises(ValueError):
            to_calendar(reminders([(tracker("j1", days=1), job())], TODAY),
                        now=datetime(2026, 10, 15, 6, 30))

    def test_an_export_with_no_reminders_is_an_empty_but_valid_calendar(self):
        text = to_calendar((), now=NOW)

        self.assertIn("BEGIN:VCALENDAR", text)
        self.assertNotIn("BEGIN:VEVENT", text)
        self.assertTrue(text.endswith("END:VCALENDAR\r\n"))

    def test_the_document_is_text_a_person_can_read(self):
        """No surrogate escapes or raw bytes: the file is plain UTF-8 text all the way through."""
        text = self.document([(tracker("j1", days=1, note="naïve — ₹"), job())])

        text.encode("utf-8")
        self.assertNotIn("\\xff", text)

    def test_the_suggested_file_name_carries_the_export_day(self):
        self.assertEqual(calendar_file_name(TODAY), "career-agent-follow-ups-20261015.ics")


class DomainRuleTests(unittest.TestCase):
    """The rules on the fields themselves, which the desktop and the command line both rely on."""

    def test_a_note_without_a_day_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            ApplicationTracker("j1").with_follow_up(None, note="chase them")

        self.assertIn("needs a day", str(caught.exception))

    def test_clearing_the_day_clears_the_note_with_it(self):
        tracker_with_plan = tracker(days=3, note="chase them")

        cleared = tracker_with_plan.with_follow_up(None)

        self.assertIsNone(cleared.follow_up_on)
        self.assertIsNone(cleared.follow_up_note)
        self.assertFalse(cleared.has_follow_up)

    def test_setting_a_day_keeps_the_application_status_untouched(self):
        before = ApplicationTracker("j1", ApplicationStatus.INTERVIEW)

        after = before.with_follow_up(TODAY)

        self.assertEqual(after.status, ApplicationStatus.INTERVIEW)
        self.assertEqual(after.listing_id, before.listing_id)

    def test_a_mistyped_year_is_refused_where_it_is_typed(self):
        for value in (date(202, 1, 1), date(9999, 12, 31)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_follow_up_date(value)

    def test_a_datetime_is_not_a_day(self):
        with self.assertRaises(ValueError):
            validate_follow_up_date(datetime(2026, 10, 15, 9, 0))  # type: ignore[arg-type]

    def test_a_long_note_is_refused_with_its_length(self):
        with self.assertRaises(ValueError) as caught:
            validate_follow_up_note("x" * 301)

        self.assertIn("301", str(caught.exception))

    def test_a_note_is_trimmed_and_a_blank_one_is_no_note(self):
        self.assertEqual(validate_follow_up_note("  chase   them  "), "chase them")
        self.assertIsNone(validate_follow_up_note("   "))
        self.assertIsNone(validate_follow_up_note(None))


if __name__ == "__main__":
    unittest.main()


class PlanSurvivesTheApplicationMovingOnTests(unittest.TestCase):
    """A reminder is a plan, not a status: moving an application on must not cancel it.

    The regression this locks: ``ApplicationTracker.transition`` rebuilt the record from the status and
    the evidence, so the day and the note were dropped on the way, and the store wrote the row from that
    object - a person who set a reminder and then shortlisted the application lost the reminder without a
    word. Reproduced against a file-backed database before the fix (set 2026-10-20, transition to
    shortlisted, re-read: both fields NULL).
    """

    def test_the_transitioned_record_still_carries_the_day_and_the_note(self):
        planned = ApplicationTracker("j1").with_follow_up(TODAY + timedelta(days=5),
                                                         note="chase the reply")

        moved = planned.transition(ApplicationStatus.SHORTLISTED)

        self.assertEqual(moved.status, ApplicationStatus.SHORTLISTED)
        self.assertEqual(moved.follow_up_on, planned.follow_up_on)
        self.assertEqual(moved.follow_up_note, "chase the reply")

    def test_a_record_with_no_plan_stays_without_one_after_a_transition(self):
        moved = ApplicationTracker("j1").transition(ApplicationStatus.SHORTLISTED)

        self.assertFalse(moved.has_follow_up)
        self.assertIsNone(moved.follow_up_note)
