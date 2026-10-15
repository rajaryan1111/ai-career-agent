"""The email and calendar contract: drafts, previews, refusals, idempotency and the local mock.

Nothing in this module can perform a real operation, which is the property these tests exist to keep
true. They check four things and, just as importantly, what is *not* here:

* a draft or an event is a value that describes what would happen, and constructing one has no side
  effect at all - no ledger entry, no attempt, no write;
* the preview says what a person would need to know, including the facts that are missing, and never
  claims something was sent or created;
* the default integration refuses everything with a reason, and the mock - the only thing that *can*
  perform anything - records operations locally, refuses a repeat, allows a retry after a failure, and
  cannot reach a network;
* the local ``.ics`` export is unchanged apart from the two identity helpers the preview now shares
  with it, so a preview cannot promise a different event from the one the file will hold.

What these tests cannot establish: that a provider behaves as documented, or that a network call would
fail. No provider exists, and the project's local-first scan (``tests/test_local_only.py``) is what
keeps the shipped code from acquiring one by accident.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from datetime import date, datetime, time, timezone
from pathlib import Path

from career_agent import integrations
from career_agent.core import Availability, JobListing
from career_agent.followups import FollowUpReminder, FollowUpState, to_calendar

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def sample_reminder(*, listing_id: str = "j1", day: date = date(2026, 10, 20),
                    note: str | None = "ask about the panel") -> FollowUpReminder:
    """One recorded follow-up, invented: the employer, the role and the note are fixtures."""
    return FollowUpReminder(
        listing_id=listing_id, on=day, state=FollowUpState.UPCOMING, days_away=5,
        employer_name="Sandbox Systems", role_title="Data Engineer", note=note,
    )


def sample_listing(listing_id: str = "j1") -> JobListing:
    return JobListing(
        listing_id=listing_id, source_id="fixture", source_name="Fixture",
        source_listing_url=f"https://jobs.example.invalid/{listing_id}",
        employer_name="Sandbox Systems", role_title="Data Engineer",
        availability_status=Availability.UNKNOWN,
    )


def ready_draft(**overrides) -> integrations.EmailDraft:
    fields = {"subject": "Following up", "body": "Hello,\n\nJust following up.",
              "recipient": "hiring@sandbox.example", "listing_id": "j1"}
    fields.update(overrides)
    return integrations.EmailDraft(**fields)


class RecordingIntegration:
    """A stand-in that counts attempts and answers with whatever it was told to answer."""

    name = "recording"
    is_enabled = True

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.attempts = 0

    def _answer(self, operation_id: str) -> integrations.IntegrationResult:
        self.attempts += 1
        outcome = self.outcomes.pop(0) if self.outcomes else integrations.Outcome.COMPLETED
        return integrations.IntegrationResult(
            outcome=outcome, operation_id=operation_id, message=f"answer {outcome.value}",
            performed=outcome is integrations.Outcome.COMPLETED, integration_name=self.name,
        )

    def send_email(self, draft):
        return self._answer(draft.operation_id)

    def create_event(self, request):
        return self._answer(request.operation_id)


class DraftValidationTests(unittest.TestCase):
    """A draft refuses what a person can see is wrong, and keeps what they wrote."""

    def test_a_draft_without_a_recipient_is_still_a_draft_and_says_what_is_missing(self):
        draft = integrations.EmailDraft(subject="Following up", body="Hello.")

        self.assertFalse(draft.is_ready)
        self.assertEqual([fact.field for fact in draft.missing()], ["recipient"])
        self.assertIn("guessing one from an employer's name", draft.missing()[0].reason)

    def test_a_blank_recipient_means_not_supplied_rather_than_an_empty_address(self):
        draft = integrations.EmailDraft(subject="Following up", body="Hello.", recipient="   ")

        self.assertIsNone(draft.recipient)
        self.assertFalse(draft.is_ready)

    def test_a_ready_draft_needs_nothing(self):
        draft = ready_draft()

        self.assertTrue(draft.is_ready)
        self.assertEqual(draft.missing(), ())

    def test_a_blank_subject_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            integrations.EmailDraft(subject="   ", body="Hello.")

        self.assertIn("subject", str(caught.exception))

    def test_a_blank_body_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            integrations.EmailDraft(subject="Hi", body="\n  \n")

        self.assertIn("message body", str(caught.exception))

    def test_an_over_long_subject_or_body_is_refused_with_the_limit(self):
        with self.assertRaises(ValueError) as subject_error:
            integrations.EmailDraft(subject="s" * (integrations.MAX_SUBJECT_LENGTH + 1), body="Hello.")
        with self.assertRaises(ValueError) as body_error:
            integrations.EmailDraft(subject="Hi", body="b" * (integrations.MAX_BODY_LENGTH + 1))

        self.assertIn(str(integrations.MAX_SUBJECT_LENGTH), str(subject_error.exception))
        self.assertIn(str(integrations.MAX_BODY_LENGTH), str(body_error.exception))

    def test_the_subject_is_normalised_but_the_body_keeps_its_paragraphs(self):
        draft = integrations.EmailDraft(subject="  Following   up  ", body="One\n\nTwo\n")

        self.assertEqual(draft.subject, "Following up")
        self.assertEqual(draft.body, "One\n\nTwo")

    def test_addresses_that_are_visibly_wrong_are_refused_with_the_reason(self):
        for address, expected in (
            ("hiring at sandbox.example", "contains a space"),
            ("hiring", "one '@'"),
            ("hiring@sandbox", "one '@'"),
            ("@sandbox.example", "one '@'"),
            ("hiring@", "one '@'"),
            (" hiring@sandbox.example", "leading or trailing spaces"),
            ("hiring@sandbox.example ", "leading or trailing spaces"),
        ):
            with self.subTest(address=address):
                with self.assertRaises(ValueError) as caught:
                    integrations.EmailDraft(subject="Hi", body="Hello.", recipient=address)
                self.assertIn(expected, str(caught.exception))

    def test_a_plain_address_is_accepted_and_the_check_is_not_deliverability(self):
        draft = ready_draft(recipient="Hiring.Team+roles@sandbox.example")

        self.assertEqual(draft.recipient, "Hiring.Team+roles@sandbox.example")
        self.assertEqual(integrations.validate_email_address("a@b.example"), "a@b.example")

    def test_the_operation_id_is_the_same_for_the_same_content_and_different_for_changed_text(self):
        first = ready_draft()
        second = ready_draft()

        self.assertEqual(first.operation_id, second.operation_id)
        self.assertNotEqual(first.operation_id, ready_draft(body="Different.").operation_id)
        self.assertNotEqual(first.operation_id, ready_draft(subject="Different").operation_id)
        self.assertNotEqual(first.operation_id,
                            ready_draft(recipient="other@sandbox.example").operation_id)

    def test_address_capitalisation_does_not_change_the_operation(self):
        """An address is one address whatever case it is typed in, so a repeat is recognised as one."""

        self.assertEqual(ready_draft(recipient="Hiring@Sandbox.example").operation_id,
                         ready_draft(recipient="hiring@sandbox.example").operation_id)

    def test_a_given_operation_id_is_kept(self):
        draft = ready_draft(operation_id="email-fixed")

        self.assertEqual(draft.operation_id, "email-fixed")

    def test_the_description_never_carries_the_recipient(self):
        """A description ends up in a log or a list; an address is somebody else's private detail."""
        draft = ready_draft(recipient="person@sandbox.example")

        self.assertNotIn("person@sandbox.example", draft.describe())
        self.assertIn(draft.operation_id, draft.describe())


class CalendarRequestValidationTests(unittest.TestCase):
    """An event refuses combinations that would move an appointment, and never invents a time."""

    def test_an_all_day_request_needs_only_a_day_and_a_title(self):
        request = integrations.CalendarEventRequest(title="Follow up: Data Engineer", day=date(2026, 10, 20))

        self.assertTrue(request.is_all_day)
        self.assertTrue(request.is_ready)
        self.assertEqual(request.missing(), ())

    def test_an_all_day_request_reports_that_no_time_is_recorded(self):
        request = integrations.CalendarEventRequest(title="Follow up", day=date(2026, 10, 20))

        imprecisions = request.imprecisions()

        self.assertEqual([fact.field for fact in imprecisions], ["start time"])
        self.assertIn("will not guess", imprecisions[0].reason)

    def test_a_timed_request_has_no_imprecision_and_carries_its_timezone(self):
        request = integrations.CalendarEventRequest(
            title="Interview", day=date(2026, 10, 20), start_time=time(10, 30), duration_minutes=45,
            timezone_name="Asia/Kolkata")

        self.assertFalse(request.is_all_day)
        self.assertEqual(request.imprecisions(), ())
        self.assertEqual(request.timezone_name, "Asia/Kolkata")

    def test_a_time_without_a_duration_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            integrations.CalendarEventRequest(title="Interview", day=date(2026, 10, 20),
                                              start_time=time(10, 30), timezone_name="Asia/Kolkata")

        self.assertIn("how long", str(caught.exception))

    def test_a_duration_without_a_time_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            integrations.CalendarEventRequest(title="Interview", day=date(2026, 10, 20), duration_minutes=45)

        self.assertIn("Leave both out", str(caught.exception))

    def test_a_time_without_a_timezone_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            integrations.CalendarEventRequest(title="Interview", day=date(2026, 10, 20),
                                              start_time=time(10, 30), duration_minutes=45)

        self.assertIn("timezone", str(caught.exception))

    def test_a_timezone_without_a_time_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            integrations.CalendarEventRequest(title="Interview", day=date(2026, 10, 20),
                                              timezone_name="Asia/Kolkata")

        self.assertIn("means nothing", str(caught.exception))

    def test_a_time_that_carries_its_own_zone_is_refused_so_the_two_cannot_disagree(self):
        from datetime import timedelta
        aware = time(10, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))

        with self.assertRaises(ValueError) as caught:
            integrations.CalendarEventRequest(title="Interview", day=date(2026, 10, 20), start_time=aware,
                                              duration_minutes=45, timezone_name="Asia/Kolkata")

        self.assertIn("separately", str(caught.exception))

    def test_durations_outside_the_recorded_range_are_refused(self):
        for minutes, expected in ((0, str(integrations.MIN_DURATION_MINUTES)),
                                  (integrations.MAX_DURATION_MINUTES + 1,
                                   str(integrations.MAX_DURATION_MINUTES))):
            with self.subTest(minutes=minutes):
                with self.assertRaises(ValueError) as caught:
                    integrations.CalendarEventRequest(title="Interview", day=date(2026, 10, 20),
                                                      start_time=time(10, 30), duration_minutes=minutes,
                                                      timezone_name="Asia/Kolkata")
                self.assertIn(expected, str(caught.exception))

    def test_a_boolean_duration_is_refused_rather_than_read_as_one_minute(self):
        with self.assertRaises(ValueError) as caught:
            integrations.CalendarEventRequest(title="Interview", day=date(2026, 10, 20),
                                              start_time=time(10, 30), duration_minutes=True,
                                              timezone_name="Asia/Kolkata")

        self.assertIn("whole number", str(caught.exception))

    def test_a_timezone_name_that_this_machine_does_not_know_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            integrations.validate_timezone("Mars/Olympus")

        self.assertIn("Mars/Olympus", str(caught.exception))
        self.assertIn("all-day", str(caught.exception))

    def test_a_blank_timezone_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            integrations.validate_timezone("  ")

        self.assertIn("Asia/Kolkata", str(caught.exception))

    def test_a_known_timezone_name_is_returned_unchanged(self):
        self.assertEqual(integrations.validate_timezone(" Europe/London "), "Europe/London")

    def test_a_day_outside_the_recorded_years_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            integrations.CalendarEventRequest(title="Interview", day=date(202, 1, 1))

        self.assertIn("202-01-01", str(caught.exception))

    def test_a_moment_in_time_is_not_a_day(self):
        with self.assertRaises(ValueError) as caught:
            integrations.CalendarEventRequest(title="Interview", day=datetime(2026, 10, 20, 9, 0))

        self.assertIn("not a moment in time", str(caught.exception))

    def test_a_blank_title_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            integrations.CalendarEventRequest(title="   ", day=date(2026, 10, 20))

        self.assertIn("event title", str(caught.exception))

    def test_the_operation_identity_follows_the_day_and_the_time(self):
        base = integrations.CalendarEventRequest(title="Follow up", day=date(2026, 10, 20))

        self.assertEqual(base.operation_id,
                         integrations.CalendarEventRequest(title="Follow up",
                                                           day=date(2026, 10, 20)).operation_id)
        self.assertNotEqual(base.operation_id,
                            integrations.CalendarEventRequest(title="Follow up",
                                                              day=date(2026, 10, 21)).operation_id)
        self.assertNotEqual(
            base.operation_id,
            integrations.CalendarEventRequest(title="Follow up", day=date(2026, 10, 20),
                                              start_time=time(10, 30), duration_minutes=30,
                                              timezone_name="Asia/Kolkata").operation_id,
        )


class PreviewTests(unittest.TestCase):
    """A preview says what would happen, names what is missing, and does nothing at all."""

    def disabled_preview(self, draft):
        integration = integrations.default_integration()
        return integration, integrations.preview_email(draft, integration=integration,
                                                       listing=sample_listing())

    def test_previewing_a_draft_touches_nothing(self):
        mock = integrations.LocalMockIntegration()

        integrations.preview_email(ready_draft(), integration=mock, listing=sample_listing())

        self.assertEqual(len(mock.ledger), 0)
        self.assertEqual(mock.attempts, {})

    def test_the_draft_preview_carries_the_body_and_the_operation_id(self):
        draft = ready_draft(body="Hello,\n\nFirst line.")

        _integration, preview = self.disabled_preview(draft)

        self.assertEqual(preview.body, "Hello,\n\nFirst line.")
        self.assertIn(draft.operation_id, preview.operation_id)
        self.assertIn(draft.operation_id, preview.render())

    def test_a_missing_recipient_is_shown_as_missing_and_not_as_a_blank(self):
        _integration, preview = self.disabled_preview(integrations.EmailDraft(subject="Hi", body="Hello."))

        rendered = preview.render()

        self.assertFalse(preview.is_ready)
        self.assertIn("not supplied", rendered)
        self.assertIn("Missing, and not guessed:", rendered)
        self.assertIn("not ready to be performed", rendered)

    def test_the_preview_says_nothing_is_sent_by_producing_it(self):
        _integration, preview = self.disabled_preview(ready_draft())

        self.assertIn("Nothing is sent by producing this preview", preview.render())

    def test_an_email_preview_with_no_integration_says_nothing_would_happen(self):
        integration, preview = self.disabled_preview(ready_draft())

        self.assertFalse(preview.enabled)
        self.assertIn("Nothing", preview.would_do)
        self.assertIn(integration.name, preview.would_do)
        self.assertIn("Nothing was sent and nothing was created", preview.would_do)

    def test_an_email_preview_with_an_enabled_integration_still_says_no_message_leaves_the_machine(self):
        mock = integrations.LocalMockIntegration()

        preview = integrations.preview_email(ready_draft(), integration=mock, listing=sample_listing())

        self.assertTrue(preview.enabled)
        self.assertIn("No email leaves this machine", preview.would_do)

    def test_the_preview_names_the_application_and_says_when_it_no_longer_exists(self):
        stored = integrations.preview_email(ready_draft(), integration=integrations.default_integration(),
                                            listing=sample_listing())
        gone = integrations.preview_email(ready_draft(), integration=integrations.default_integration(),
                                          listing=None)
        unlinked = integrations.preview_email(ready_draft(listing_id=None),
                                              integration=integrations.default_integration(), listing=None)

        self.assertIn("Data Engineer at Sandbox Systems [j1]", stored.render())
        self.assertIn("no longer stored", gone.render())
        self.assertIn("not linked to a stored application", unlinked.render())

    def test_an_all_day_event_preview_says_all_day_and_points_at_missing_time(self):
        request = integrations.CalendarEventRequest(title="Follow up: Data Engineer",
                                                    day=date(2026, 10, 20), listing_id="j1")

        preview = integrations.preview_event(request, integration=integrations.default_integration(),
                                             listing=sample_listing())

        rendered = preview.render()
        self.assertIn("2026-10-20 (all day)", rendered)
        self.assertIn("Not recorded, and not invented:", rendered)
        self.assertIn("not applicable - an all-day entry has no time of day", rendered)
        self.assertIn("Nothing is created in any calendar by producing this preview", rendered)

    def test_a_timed_event_preview_names_the_time_the_zone_and_the_duration(self):
        request = integrations.CalendarEventRequest(
            title="Interview: Data Engineer", day=date(2026, 10, 22), listing_id="j1",
            start_time=time(10, 30), duration_minutes=45, timezone_name="Asia/Kolkata",
            notes="Panel interview")

        preview = integrations.preview_event(request, integration=integrations.default_integration(),
                                             listing=sample_listing())

        rendered = preview.render()
        self.assertIn("2026-10-22 10:30 Asia/Kolkata for 45 minute(s)", rendered)
        self.assertIn("Panel interview", rendered)
        self.assertNotIn("Not recorded, and not invented:", rendered)

    def test_the_calendar_preview_states_that_nobody_is_invited(self):
        mock = integrations.LocalMockIntegration()
        request = integrations.CalendarEventRequest(title="Follow up", day=date(2026, 10, 20))

        preview = integrations.preview_event(request, integration=mock, listing=sample_listing())

        self.assertIn("nobody is invited", preview.would_do)


class DisabledByDefaultTests(unittest.TestCase):
    """The integration this application uses is the one that does nothing."""

    def test_the_default_is_the_disabled_integration(self):
        integration = integrations.default_integration()

        self.assertFalse(integration.is_enabled)
        self.assertEqual(integration.name, "disabled")

    def test_a_disabled_integration_refuses_both_kinds_of_operation_with_a_reason(self):
        integration = integrations.default_integration()
        draft = ready_draft()
        request = integrations.CalendarEventRequest(title="Follow up", day=date(2026, 10, 20))

        for result in (integration.send_email(draft), integration.create_event(request)):
            with self.subTest(kind=result.operation_id.split("-")[0]):
                self.assertIs(result.outcome, integrations.Outcome.DISABLED)
                self.assertFalse(result.performed)
                self.assertFalse(result.succeeded)
                self.assertIn("Nothing was sent and nothing was created", result.message)
                self.assertIn(".ics file", result.message)

    def test_the_refusal_names_what_can_be_done_instead(self):
        message = integrations.DEFAULT_DISABLED_REASON

        self.assertIn(".ics", message)
        self.assertIn("by hand", message)

    def test_a_disabled_integration_is_not_retried(self):
        integration = RecordingIntegration([integrations.Outcome.DISABLED])

        result = integrations.dispatch_with_retry(integration, ready_draft(), attempts=3)

        self.assertEqual(integration.attempts, 1)
        self.assertIs(result.outcome, integrations.Outcome.DISABLED)

    def test_the_status_lines_list_every_condition_for_enabling_a_provider(self):
        lines = integrations.describe_integrations()
        text = "\n".join(lines)

        self.assertIn("Integration state: nothing is enabled", text)
        for name, reason in integrations.ENABLEMENT_REQUIREMENTS:
            with self.subTest(requirement=name):
                self.assertGreater(len(reason), 40)
                self.assertIn(name, text)
        self.assertIn("provider-side idempotency".lower(), text.lower())
        self.assertIn("OS keyring", text)


class LocalMockTests(unittest.TestCase):
    """The mock performs locally, refuses repeats, and reports failures as failures."""

    def test_a_ready_draft_is_recorded_once_with_the_target_and_the_subject(self):
        mock = integrations.LocalMockIntegration(
            clock=lambda: datetime(2026, 10, 15, 6, 0, tzinfo=timezone.utc))

        result = mock.send_email(ready_draft())

        self.assertIs(result.outcome, integrations.Outcome.COMPLETED)
        self.assertTrue(result.performed)
        self.assertTrue(result.succeeded)
        self.assertIn("No email was sent", result.message)
        self.assertIn("sandbox.example", result.detail)
        records = mock.ledger.records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].target, "hiring@sandbox.example")
        self.assertEqual(records[0].completed_at, "2026-10-15T06:00:00+00:00")

    def test_the_same_request_twice_is_performed_once(self):
        mock = integrations.LocalMockIntegration()

        first = mock.send_email(ready_draft())
        second = mock.send_email(ready_draft())

        self.assertIs(first.outcome, integrations.Outcome.COMPLETED)
        self.assertIs(second.outcome, integrations.Outcome.DUPLICATE)
        self.assertFalse(second.performed)
        self.assertTrue(second.succeeded, "an operation already done satisfies the request")
        self.assertEqual(len(mock.ledger), 1)
        self.assertIn("nothing was sent or created twice", second.message)
        self.assertIn(mock.ledger.records()[0].completed_at, second.message)

    def test_an_edited_draft_is_a_new_operation(self):
        mock = integrations.LocalMockIntegration()

        mock.send_email(ready_draft())
        result = mock.send_email(ready_draft(body="A different message."))

        self.assertIs(result.outcome, integrations.Outcome.COMPLETED)
        self.assertEqual(len(mock.ledger), 2)

    def test_a_draft_without_a_recipient_is_refused_and_not_recorded(self):
        mock = integrations.LocalMockIntegration()

        result = mock.send_email(integrations.EmailDraft(subject="Hi", body="Hello."))

        self.assertIs(result.outcome, integrations.Outcome.INVALID)
        self.assertFalse(result.performed)
        self.assertIn("recipient", result.message)
        self.assertEqual(len(mock.ledger), 0)

    def test_an_event_is_recorded_with_its_day_and_no_account_is_touched(self):
        mock = integrations.LocalMockIntegration()

        result = mock.create_event(integrations.CalendarEventRequest(title="Follow up: Data Engineer",
                                                                    day=date(2026, 10, 20), listing_id="j1"))

        self.assertIs(result.outcome, integrations.Outcome.COMPLETED)
        self.assertIn("No calendar account was contacted", result.message)
        self.assertIn("no invitation", result.message)
        self.assertEqual(mock.ledger.count_of(integrations.OperationKind.CALENDAR), 1)
        self.assertEqual(mock.ledger.records()[0].target, "2026-10-20")

    def test_a_failure_is_not_recorded_as_done_and_a_retry_performs_it_once(self):
        draft = ready_draft()
        mock = integrations.LocalMockIntegration(fail_operation_ids={draft.operation_id: 1})

        first = mock.send_email(draft)

        self.assertIs(first.outcome, integrations.Outcome.FAILED)
        self.assertFalse(first.performed)
        self.assertEqual(len(mock.ledger), 0)
        self.assertIn("retry", first.message)

        retried = integrations.dispatch_with_retry(mock, draft)

        self.assertIs(retried.outcome, integrations.Outcome.COMPLETED)
        self.assertTrue(retried.performed)
        self.assertEqual(retried.attempts, 2)
        self.assertEqual(len(mock.ledger), 1, "the retry must not perform the operation twice")

        again = integrations.dispatch_with_retry(mock, draft)

        self.assertIs(again.outcome, integrations.Outcome.DUPLICATE)
        self.assertEqual(len(mock.ledger), 1)

    def test_retrying_stops_after_the_configured_attempts_and_reports_how_many_it_made(self):
        draft = ready_draft()
        mock = integrations.LocalMockIntegration(fail_operation_ids={draft.operation_id: 5})

        result = integrations.dispatch_with_retry(mock, draft, attempts=3)

        self.assertIs(result.outcome, integrations.Outcome.FAILED)
        self.assertEqual(result.attempts, 3)
        self.assertEqual(mock.attempts[draft.operation_id], 3)
        self.assertEqual(len(mock.ledger), 0)

    def test_an_invalid_request_is_not_retried(self):
        draft = integrations.EmailDraft(subject="Hi", body="Hello.")
        mock = integrations.LocalMockIntegration()

        result = integrations.dispatch_with_retry(mock, draft, attempts=3)

        self.assertIs(result.outcome, integrations.Outcome.INVALID)
        self.assertEqual(mock.attempts[draft.operation_id], 1)

    def test_a_dispatch_without_attempts_is_refused(self):
        with self.assertRaises(ValueError):
            integrations.dispatch_with_retry(integrations.LocalMockIntegration(), ready_draft(), attempts=0)

    def test_a_key_already_used_for_another_kind_of_operation_is_refused_rather_than_repeated(self):
        """One key means one operation: the mock will not guess which of the two was meant."""
        mock = integrations.LocalMockIntegration()
        request = integrations.CalendarEventRequest(title="Follow up", day=date(2026, 10, 20))
        mock.create_event(request)

        result = integrations.dispatch_with_retry(
            mock, ready_draft(operation_id=request.operation_id), attempts=3)

        self.assertIs(result.outcome, integrations.Outcome.INVALID)
        self.assertFalse(result.performed)
        self.assertIn("calendar operation", result.message)
        self.assertEqual(len(mock.ledger), 1)
        self.assertEqual(mock.attempts[request.operation_id], 2, "one calendar attempt plus the refused one")

    def test_an_unknown_integration_shape_is_still_usable_through_the_protocol(self):
        """Anything with the two methods and the two attributes can stand in, which is what a test does."""
        integration = RecordingIntegration([integrations.Outcome.COMPLETED])

        self.assertIsInstance(integration, integrations.Integration)


class LedgerTests(unittest.TestCase):
    """The record of what has been done survives a restart, and a damaged one stops everything."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.ledger_path = self.folder / "integration-ledger.json"

    def test_a_first_run_with_no_file_is_not_an_error(self):
        mock = integrations.LocalMockIntegration(ledger_path=self.ledger_path)

        result = mock.send_email(ready_draft())

        self.assertIs(result.outcome, integrations.Outcome.COMPLETED)
        self.assertTrue(self.ledger_path.exists())
        self.assertEqual((self.ledger_path.stat().st_mode & 0o077), 0, "the ledger must be owner-only")

    def test_an_operation_recorded_by_one_run_is_a_duplicate_in_the_next(self):
        first = integrations.LocalMockIntegration(ledger_path=self.ledger_path)
        first.send_email(ready_draft())

        second = integrations.LocalMockIntegration(ledger_path=self.ledger_path)
        result = second.send_email(ready_draft())

        self.assertIs(result.outcome, integrations.Outcome.DUPLICATE)
        self.assertEqual(len(second.ledger), 1)

    def test_a_ledger_that_cannot_be_read_stops_the_operation_instead_of_being_treated_as_empty(self):
        self.ledger_path.write_text("{ not json", encoding="utf-8")

        with self.assertRaises(integrations.IntegrationLedgerError) as caught:
            integrations.LocalMockIntegration(ledger_path=self.ledger_path)

        self.assertIn("cannot establish what it has already done", str(caught.exception))
        self.assertIn("Nothing was performed", str(caught.exception))

    def test_a_ledger_from_a_later_format_is_refused_rather_than_half_read(self):
        self.ledger_path.write_text('{"ledger_version": 99, "operations": []}', encoding="utf-8")

        with self.assertRaises(integrations.IntegrationLedgerError) as caught:
            integrations.IntegrationLedger.load(self.ledger_path)

        self.assertIn("99", str(caught.exception))

    def test_a_ledger_without_operations_is_refused(self):
        self.ledger_path.write_text('{"ledger_version": 1, "operations": "nope"}', encoding="utf-8")

        with self.assertRaises(integrations.IntegrationLedgerError):
            integrations.IntegrationLedger.load(self.ledger_path)

    def test_a_ledger_entry_this_build_cannot_read_is_refused(self):
        self.ledger_path.write_text(
            '{"ledger_version": 1, "operations": [{"operation_id": "email-1", "kind": "telepathy"}]}',
            encoding="utf-8")

        with self.assertRaises(integrations.IntegrationLedgerError) as caught:
            integrations.IntegrationLedger.load(self.ledger_path)

        self.assertIn("could not be read", str(caught.exception))

    def test_a_ledger_that_cannot_be_written_is_reported_as_a_failure_not_a_success(self):
        mock = integrations.LocalMockIntegration(ledger_path=self.ledger_path)
        with unittest.mock.patch.object(integrations, "write_private_text_file",
                                        side_effect=OSError("no room left on the device")):
            result = mock.send_email(ready_draft())

        self.assertIs(result.outcome, integrations.Outcome.FAILED)
        self.assertFalse(result.performed)
        self.assertIn("not being reported as completed", result.message)
        self.assertIn("no room left on the device", result.message)

    def test_a_ledger_location_that_is_not_a_file_is_refused_before_anything_is_performed(self):
        blocked = self.folder / "not-a-file"
        blocked.mkdir()

        with self.assertRaises(integrations.IntegrationLedgerError) as caught:
            integrations.LocalMockIntegration(ledger_path=blocked)

        self.assertIn("Nothing was performed", str(caught.exception))

    def test_a_saved_ledger_round_trips_its_entries(self):
        ledger = integrations.IntegrationLedger()
        ledger.record(integrations.LedgerRecord(
            operation_id="email-1", kind=integrations.OperationKind.EMAIL, listing_id="j1",
            target="hiring@sandbox.example", summary="Following up",
            completed_at="2026-10-15T06:00:00+00:00", attempts=2))
        written = ledger.save(self.ledger_path)

        loaded = integrations.IntegrationLedger.load(written)

        self.assertEqual(len(loaded), 1)
        entry = loaded.record_for("email-1")
        self.assertEqual(entry.listing_id, "j1")
        self.assertEqual(entry.attempts, 2)
        self.assertIs(entry.kind, integrations.OperationKind.EMAIL)


class DraftFromContextTests(unittest.TestCase):
    """A draft written from an application uses what is recorded, and nothing that is not."""

    def test_a_follow_up_draft_is_built_from_the_stored_employer_role_and_note(self):
        draft = integrations.draft_for_follow_up(sample_reminder())

        self.assertIn("Data Engineer", draft.subject)
        self.assertIn("Sandbox Systems", draft.subject)
        self.assertIn("Data Engineer", draft.body)
        self.assertIn("Sandbox Systems", draft.body)
        self.assertIn("ask about the panel", draft.body)
        self.assertEqual(draft.listing_id, "j1")
        self.assertEqual(draft.purpose, integrations.PURPOSE_FOLLOW_UP)

    def test_a_draft_without_a_given_address_has_none_and_cannot_be_performed(self):
        draft = integrations.draft_for_follow_up(sample_reminder())

        self.assertIsNone(draft.recipient)
        self.assertFalse(draft.is_ready)

    def test_a_given_address_is_kept_and_checked(self):
        draft = integrations.draft_for_follow_up(sample_reminder(), recipient="hiring@sandbox.example")

        self.assertTrue(draft.is_ready)
        with self.assertRaises(ValueError):
            integrations.draft_for_follow_up(sample_reminder(), recipient="not an address")

    def test_a_reminder_without_a_note_produces_no_note_paragraph(self):
        draft = integrations.draft_for_follow_up(sample_reminder(note=None))

        self.assertNotIn("My own note", draft.body)
        self.assertIn("Thank you for your time.", draft.body)

    def test_a_supplied_body_is_used_unchanged(self):
        draft = integrations.draft_for_follow_up(sample_reminder(), body="Custom text.\n\nThanks.")

        self.assertEqual(draft.body, "Custom text.\n\nThanks.")

    def test_the_listing_can_be_named_explicitly(self):
        draft = integrations.draft_for_follow_up(sample_reminder(), listing_id="j9")

        self.assertEqual(draft.listing_id, "j9")

    def test_the_draft_text_states_that_it_is_a_draft_and_marks_the_missing_address(self):
        text = integrations.draft_as_text(integrations.draft_for_follow_up(sample_reminder()))

        self.assertIn("To: NOT SUPPLIED", text)
        self.assertIn("Status: DRAFT ONLY", text)
        self.assertIn("nothing has been sent", text)
        self.assertIn("Operation id: email-", text)
        self.assertTrue(text.endswith("\n"))
        self.assertNotIn("attached", text)

    def test_the_draft_text_of_a_ready_draft_shows_the_address_and_the_body(self):
        draft = ready_draft(body="Hello,\n\nBody line.")

        text = integrations.draft_as_text(draft)

        self.assertIn("To: hiring@sandbox.example", text)
        self.assertIn("Body line.", text)

    def test_an_event_described_from_a_reminder_matches_the_exported_summary(self):
        reminder = sample_reminder()
        request = integrations.event_from_reminder(reminder)

        self.assertEqual(request.title, integrations.preview_event(
            request, integration=integrations.default_integration()).fields[0][1])
        self.assertEqual(request.day, reminder.on)
        self.assertEqual(request.notes, reminder.note)
        self.assertTrue(request.is_all_day)

    def test_an_event_described_from_a_reminder_keeps_a_supplied_time(self):
        request = integrations.event_from_reminder(sample_reminder(), start_time=time(9, 0),
                                                   duration_minutes=30, timezone_name="Asia/Kolkata")

        self.assertFalse(request.is_all_day)
        self.assertEqual(request.duration_minutes, 30)


class CalendarExportPreviewTests(unittest.TestCase):
    """The working calendar path is a local file, and the preview describes that exact file."""

    def test_the_plan_lists_the_day_the_summary_and_the_uid_of_every_event(self):
        plan = integrations.calendar_export_plan([sample_reminder(), sample_reminder(listing_id="j2")])

        self.assertEqual(len(plan.events), 2)
        self.assertEqual(plan.events[0][0], "2026-10-20")
        self.assertIn("Follow up: Data Engineer at Sandbox Systems", plan.events[0][1])
        self.assertEqual(plan.events[0][2], "follow-up-j1-20261020@ai-career-agent.local")
        rendered = plan.render()
        self.assertIn("2 event(s) would be written", rendered)
        self.assertIn("Nothing has been written yet", rendered)
        self.assertIn("no attendee is invited", rendered)

    def test_the_preview_promises_exactly_the_events_the_export_writes(self):
        reminder = sample_reminder()
        plan = integrations.calendar_export_plan([reminder])

        document = to_calendar([reminder], now=datetime(2026, 10, 15, 6, 0, tzinfo=timezone.utc))

        day, summary, uid = plan.events[0]
        self.assertIn(f"UID:{uid}", document)
        self.assertIn(f"SUMMARY:{summary}", document)
        self.assertIn(f"DTSTART;VALUE=DATE:{day.replace('-', '')}", document)

    def test_the_export_stays_local_attendee_free_and_uninvited(self):
        document = to_calendar([sample_reminder()], now=datetime(2026, 10, 15, 6, 0, tzinfo=timezone.utc))

        self.assertTrue(document.startswith("BEGIN:VCALENDAR"))
        for forbidden in ("ATTENDEE", "ORGANIZER", "METHOD:REQUEST", "http://", "https://"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, document)

    def test_no_reminders_means_an_empty_plan_rather_than_a_failure(self):
        plan = integrations.calendar_export_plan([])

        self.assertEqual(plan.events, ())
        self.assertIn("0 event(s)", plan.render())

    def test_a_named_target_is_shown_in_the_plan(self):
        plan = integrations.calendar_export_plan([sample_reminder()], target="reminders.ics")

        self.assertIn("reminders.ics", plan.render())


class OperationIdStabilityTests(unittest.TestCase):
    """A key that changes between processes would make duplicate detection impossible."""

    def test_the_same_draft_produces_the_same_identifier_in_a_fresh_interpreter(self):
        code = (
            "import sys; sys.path.insert(0, '.')\n"
            "from career_agent import integrations\n"
            "draft = integrations.EmailDraft(subject='Following up', body='Hello.',"
            " recipient='hiring@sandbox.example', listing_id='j1')\n"
            "print(draft.operation_id)\n"
        )
        readings = []
        for seed in ("0", "1", "12345"):
            completed = subprocess.run(
                [sys.executable, "-c", code], capture_output=True, text=True, cwd=str(REPOSITORY_ROOT),
                env=dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1"), timeout=120,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            readings.append(completed.stdout.strip())

        self.assertEqual(len(set(readings)), 1, f"the identifier depends on the interpreter: {readings}")
        self.assertTrue(readings[0].startswith("email-"))

    def test_the_identifier_is_derived_from_content_and_carries_no_timestamp(self):
        before = integrations.EmailDraft(subject="Hi", body="Hello.", recipient="a@b.example",
                                         listing_id="j1").operation_id
        after = integrations.EmailDraft(subject="Hi", body="Hello.", recipient="a@b.example",
                                        listing_id="j1").operation_id

        self.assertEqual(before, after)
        expected = hashlib.sha256(
            '{"kind":"email","payload":{"body":"Hello.","listing_id":"j1","recipient":"a@b.example",'
            '"subject":"Hi"}}'.encode("utf-8")).hexdigest()[:20]
        self.assertEqual(before, f"email-{expected}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
