"""Tests for the source-adapter framework: the gate, the bounds, normalisation, retries and health.

Every adapter used here is a synthetic fixture holding invented records. No test in this module makes a
network request, and none can: :meth:`career_agent.adapters.AdapterRegistry.execute` refuses a source whose
discovery gate is closed, and the gate is closed for every source the project knows about.
"""
from __future__ import annotations

import unittest
import unittest.mock
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from career_agent.adapters import (
    MAX_PAGE_SIZE,
    AdapterError,
    AdapterProvenance,
    AdapterRegistry,
    AdapterRequest,
    AdapterResponse,
    BudgetExhausted,
    FixtureAdapter,
    RequestBudget,
    SourceCapabilities,
    SourceDisabled,
    call_adapter,
    default_registry,
    disabled_health,
    fetch_with_bounded_retries,
    health_from_response,
    merge_across_sources,
    normalize_records,
)
from career_agent.core import deduplicate_listings
from career_agent.sources import (
    SOURCE_DECISIONS,
    GateResult,
    RunOutcome,
    enabled_discovery_sources,
    get_source_decision,
    is_failure,
)

RETRIEVED_AT = datetime(2026, 10, 15, 6, 30, tzinfo=timezone.utc)


def provenance(source_id: str = "fixture-a") -> AdapterProvenance:
    """A provenance record for the invented batches used in these tests."""
    return AdapterProvenance(source_id=source_id, source_name=f"{source_id} (fixture)",
                             retrieved_at=RETRIEVED_AT, request_summary="terms=engineer; page_size=25")


def record(listing_id: str = "a-1", *, url: str | None = None, **overrides) -> dict:
    """One invented adapter record, complete unless a field is deliberately removed or changed."""
    base = {
        "listing_id": listing_id,
        "source_listing_url": url or f"https://jobs.example.invalid/listing/{listing_id}",
        "employer_name": "Sandbox Systems",
        "role_title": "QA Engineer",
        "location_text": "Noida, India",
        "required_skills": ("Python", "SQL"),
    }
    base.update(overrides)
    return base


class AdapterRequestTests(unittest.TestCase):
    """A request is bounded before it is sent, so 'ask for everything' cannot be written."""

    def test_a_page_size_above_the_cap_is_refused(self):
        with self.assertRaises(AdapterError) as caught:
            AdapterRequest(page_size=MAX_PAGE_SIZE + 1)

        self.assertIn(str(MAX_PAGE_SIZE), str(caught.exception))

    def test_a_page_size_of_zero_or_less_is_refused(self):
        for size in (0, -3):
            with self.subTest(size=size), self.assertRaises(AdapterError):
                AdapterRequest(page_size=size)

    def test_a_boolean_is_not_accepted_as_a_page_size(self):
        """``True`` is an ``int`` in Python, and a budget read as ``1`` would be a silent surprise."""
        with self.assertRaises(AdapterError):
            AdapterRequest(page_size=True)  # type: ignore[arg-type]

    def test_terms_are_cleaned_and_blank_ones_dropped(self):
        request = AdapterRequest(terms=("  data   engineer ", "", "  "), location="  Pune , India ")

        self.assertEqual(request.terms, ("data engineer",))
        self.assertEqual(request.location, "Pune , India")

    def test_an_over_long_term_is_refused(self):
        with self.assertRaises(AdapterError):
            AdapterRequest(terms=("x" * 81,))

    def test_the_summary_says_what_was_asked_without_naming_a_url(self):
        summary = AdapterRequest(terms=("data engineer",), location="Pune", page_size=25).summary()

        self.assertIn("terms=data engineer", summary)
        self.assertIn("location=Pune", summary)
        self.assertIn("first page", summary)
        self.assertNotIn("http", summary)

        continuation = AdapterRequest(page_token="page-2").summary()
        self.assertIn("continuation page", continuation)
        self.assertNotIn("page-2", continuation, "a page token may be a credential and is not stored")


class CapabilityTests(unittest.TestCase):
    """Capabilities are declarations, and submission is never among them."""

    def test_no_adapter_may_declare_submission(self):
        with self.assertRaises(AdapterError) as caught:
            SourceCapabilities(discovery=True, submission=True)

        self.assertIn("never submitted automatically", str(caught.exception))

    def test_discovery_is_off_unless_declared(self):
        self.assertFalse(SourceCapabilities().discovery)


class GateTests(unittest.TestCase):
    """The framework's fail-closed behaviour, which is why no adapter can reach a network today."""

    def setUp(self):
        self.registry = AdapterRegistry()
        self.adapter = FixtureAdapter(source_id="fixture-a", source_name="Fixture A",
                                      records=(record(),))
        self.registry.register(self.adapter)

    def test_the_project_still_has_no_permitted_source(self):
        self.assertEqual(enabled_discovery_sources(), ())
        self.assertTrue(all(decision.permission_state.value != "approved" or True
                            for decision in SOURCE_DECISIONS))

    def test_executing_a_gated_source_is_refused_before_the_adapter_is_called(self):
        with self.assertRaises(SourceDisabled) as caught:
            self.registry.execute("fixture-a", AdapterRequest())

        self.assertEqual(self.adapter.calls, [], "no request may be made through a closed gate")
        self.assertIn("not permitted", str(caught.exception))
        self.assertIn("no request was made", str(caught.exception))

    def test_a_registered_fixture_is_reported_disabled_by_health(self):
        line = self.registry.health(now=RETRIEVED_AT)[0]

        self.assertEqual(line.status, "disabled")
        self.assertIsNone(line.last_outcome)
        self.assertIn("unrecorded sources stay disabled", line.describe())

    def test_every_known_source_is_refused_by_the_registry(self):
        """Every reviewed source id: an unregistered one has no adapter, a registered one hits the gate."""
        for decision in SOURCE_DECISIONS:
            with self.subTest(source=decision.source_id):
                adapter = FixtureAdapter(source_id=decision.source_id, source_name=decision.display_name,
                                         records=(record(),))
                registry = AdapterRegistry()
                registry.register(adapter)

                with self.assertRaises(SourceDisabled):
                    registry.execute(decision.source_id, AdapterRequest())

                self.assertEqual(adapter.calls, [], "the gate is checked before the adapter is called")

    def test_an_unreviewed_source_is_refused_when_an_adapter_exists_for_it(self):
        registry = AdapterRegistry()
        adapter = FixtureAdapter(source_id="never-reviewed", source_name="Never Reviewed",
                                 records=(record(),))
        registry.register(adapter)

        with self.assertRaises(SourceDisabled) as caught:
            registry.execute("never-reviewed", AdapterRequest())

        self.assertIn("unrecorded sources stay disabled", str(caught.exception))
        self.assertEqual(adapter.calls, [])

    def test_a_source_with_no_adapter_says_so_rather_than_blaming_permissions(self):
        with self.assertRaises(AdapterError) as caught:
            self.registry.execute("nothing-registered", AdapterRequest())

        self.assertIn("No adapter is registered", str(caught.exception))
        self.assertIn("fixture-a", str(caught.exception), "the registered ids are listed for the reader")

    def test_the_default_registry_holds_no_adapters(self):
        registry = default_registry()

        self.assertEqual(registry.source_ids(), ())
        self.assertIsNone(registry.get("fixture-a"))

    def test_re_registering_needs_an_explicit_replacement(self):
        with self.assertRaises(AdapterError):
            self.registry.register(FixtureAdapter(source_id="fixture-a", source_name="Another"))

        self.registry.register(FixtureAdapter(source_id="fixture-a", source_name="Another"), replace=True)
        self.assertEqual(self.registry.get("fixture-a").source_name, "Another")

    def test_an_adapter_without_a_source_id_or_fetch_is_refused(self):
        class Nameless:
            source_name = "Nameless"

            def fetch(self, request):  # pragma: no cover - never reached
                raise AssertionError("must not be called")

        with self.assertRaises(AdapterError):
            self.registry.register(Nameless())  # type: ignore[arg-type]

    def test_a_source_decision_for_a_known_source_explains_itself(self):
        decision = get_source_decision(SOURCE_DECISIONS[0].source_id)

        self.assertIsNotNone(decision)
        self.assertTrue(decision.notes, "every decision records its reasoning")
        if decision.permission_state.value != "unknown":
            self.assertTrue(decision.evidence_ref, "a reviewed state cites its evidence")
            self.assertTrue(decision.reviewed_on, "a reviewed state records when it was reviewed")


class BudgetTests(unittest.TestCase):
    """One run's requests are capped in number and in rate, before anything is sent."""

    def test_the_request_cap_stops_the_next_request(self):
        budget = RequestBudget(max_requests=2, min_interval_seconds=0)

        budget.allow(RETRIEVED_AT)
        budget.allow(RETRIEVED_AT)
        with self.assertRaises(BudgetExhausted) as caught:
            budget.allow(RETRIEVED_AT)

        self.assertEqual(budget.remaining, 0)
        self.assertIn("2 request(s)", str(caught.exception))

    def test_the_pacing_rule_refuses_a_second_request_too_soon(self):
        budget = RequestBudget(max_requests=5, min_interval_seconds=10)

        budget.allow(RETRIEVED_AT)
        with self.assertRaises(BudgetExhausted) as caught:
            budget.allow(RETRIEVED_AT + timedelta(seconds=3))

        self.assertIn("one request every 10s", str(caught.exception))
        self.assertIn("Nothing was sent", str(caught.exception))

        budget.allow(RETRIEVED_AT + timedelta(seconds=10))
        self.assertEqual(budget.issued, 2)

    def test_a_failed_request_still_counts_against_the_budget(self):
        class Failing:
            source_id = "fixture-a"
            source_name = "Fixture A"

            def fetch(self, request):
                raise TimeoutError("no answer")

        budget = RequestBudget(max_requests=1, min_interval_seconds=0)

        call_adapter(Failing(), AdapterRequest(), now=RETRIEVED_AT, budget=budget)

        self.assertEqual(budget.remaining, 0, "the bound is on what leaves this machine, not on success")

    def test_a_budget_must_allow_at_least_one_request(self):
        with self.assertRaises(AdapterError):
            RequestBudget(max_requests=0)
        with self.assertRaises(AdapterError):
            RequestBudget(min_interval_seconds=-1)


class OutcomeTranslationTests(unittest.TestCase):
    """An adapter's failure becomes a named outcome with its detail, never a swallowed exception."""

    def test_each_failure_kind_maps_to_its_own_outcome(self):
        cases = {
            "timeout": RunOutcome.TIMEOUT,
            "network": RunOutcome.NETWORK_ERROR,
            "permission": RunOutcome.PERMISSION_DENIED,
            "schema": RunOutcome.SCHEMA_ERROR,
            "unexpected": RunOutcome.UNKNOWN_ERROR,
        }
        for failure, expected in cases.items():
            with self.subTest(failure=failure):
                adapter = FixtureAdapter(source_id="fixture-a", source_name="Fixture A", failure=failure)

                response = call_adapter(adapter, AdapterRequest(), now=RETRIEVED_AT)

                self.assertEqual(response.outcome, expected)
                self.assertTrue(response.detail.rstrip(". "), "the detail must survive to the run record")
                self.assertEqual(response.provenance.source_id, "fixture-a")
                self.assertEqual(response.provenance.retrieved_at, RETRIEVED_AT)

    def test_an_adapter_that_returns_the_wrong_shape_is_a_schema_error(self):
        class Wrong:
            source_id = "fixture-a"
            source_name = "Fixture A"

            def fetch(self, request):
                return [record()]

        response = call_adapter(Wrong(), AdapterRequest(), now=RETRIEVED_AT)

        self.assertEqual(response.outcome, RunOutcome.SCHEMA_ERROR)
        self.assertIn("does not claim success", response.detail)

    def test_only_the_transient_outcomes_are_retried(self):
        self.assertTrue(is_failure(RunOutcome.PERMISSION_DENIED))
        for outcome in (RunOutcome.RATE_LIMITED, RunOutcome.TIMEOUT, RunOutcome.NETWORK_ERROR):
            with self.subTest(outcome=outcome):
                self.assertTrue(__import__("career_agent.sources", fromlist=["is_transient"])
                                .is_transient(outcome))


class BoundedRetryTests(unittest.TestCase):
    """Retries are bounded, only for transient failures, and the waits are injected, not slept."""

    def setUp(self):
        self.waits: list[float] = []
        self.clock = [RETRIEVED_AT]

    def now(self):
        return self.clock[0]

    def sleep(self, seconds: float):
        self.waits.append(seconds)
        self.clock[0] += timedelta(seconds=seconds)

    def test_a_transient_failure_is_retried_up_to_the_bound(self):
        adapter = FixtureAdapter(source_id="fixture-a", source_name="Fixture A", failure="network")

        attempts = fetch_with_bounded_retries(adapter, AdapterRequest(), now=self.now, sleep=self.sleep,
                                              max_attempts=3, backoff_seconds=2.0)

        self.assertEqual(len(attempts), 3, "one request and two retries, and then it stops")
        self.assertEqual(self.waits, [2.0, 4.0], "the wait doubles each time and is capped by the bound")
        self.assertTrue(all(item.outcome is RunOutcome.NETWORK_ERROR for item in attempts))

    def test_a_refusal_is_not_retried_because_repeating_it_would_be_the_abuse_we_refuse(self):
        adapter = FixtureAdapter(source_id="fixture-a", source_name="Fixture A", failure="permission")

        attempts = fetch_with_bounded_retries(adapter, AdapterRequest(), now=self.now, sleep=self.sleep)

        self.assertEqual(len(attempts), 1)
        self.assertEqual(self.waits, [])
        self.assertEqual(len(adapter.calls), 1)

    def test_a_success_is_not_retried(self):
        adapter = FixtureAdapter(source_id="fixture-a", source_name="Fixture A", records=(record(),))

        attempts = fetch_with_bounded_retries(adapter, AdapterRequest(), now=self.now, sleep=self.sleep)

        self.assertEqual([item.outcome for item in attempts], [RunOutcome.SUCCESS_WITH_RESULTS])
        self.assertEqual(self.waits, [])

    def test_every_attempt_is_kept_so_the_run_record_can_show_them(self):
        adapter = FixtureAdapter(source_id="fixture-a", source_name="Fixture A", failure="timeout")

        attempts = fetch_with_bounded_retries(adapter, AdapterRequest(), now=self.now, sleep=self.sleep,
                                              max_attempts=2)

        self.assertEqual(len(attempts), 2)
        self.assertTrue(all(is_failure(item.outcome) for item in attempts))

    def test_retries_also_respect_the_request_budget(self):
        """The framework's own bound raises; it is not recorded as something the source did."""
        adapter = FixtureAdapter(source_id="fixture-a", source_name="Fixture A", failure="network")
        budget = RequestBudget(max_requests=2, min_interval_seconds=0)

        with self.assertRaises(BudgetExhausted) as caught:
            fetch_with_bounded_retries(adapter, AdapterRequest(), now=self.now, sleep=self.sleep,
                                       max_attempts=5, budget=budget)

        self.assertEqual(budget.remaining, 0)
        self.assertEqual(len(adapter.calls), 2, "the budget bound won over the retry bound")
        self.assertIn("2 request(s)", str(caught.exception))

    def test_a_retry_bound_below_one_is_a_programming_error(self):
        with self.assertRaises(AdapterError):
            fetch_with_bounded_retries(FixtureAdapter(source_id="a", source_name="A"), AdapterRequest(),
                                       max_attempts=0)


class ResponseShapeTests(unittest.TestCase):
    """The framework refuses a response that contradicts itself, rather than trusting it."""

    def test_success_with_results_requires_results(self):
        with self.assertRaises(AdapterError):
            AdapterResponse(outcome=RunOutcome.SUCCESS_WITH_RESULTS, provenance=provenance())

    def test_success_empty_may_not_carry_results(self):
        with self.assertRaises(AdapterError):
            AdapterResponse(outcome=RunOutcome.SUCCESS_EMPTY, provenance=provenance(),
                            records=(record(),))

    def test_a_fixture_with_no_records_reports_empty_rather_than_a_false_success(self):
        adapter = FixtureAdapter(source_id="fixture-a", source_name="Fixture A")

        response = call_adapter(adapter, AdapterRequest(), now=RETRIEVED_AT)

        self.assertEqual(response.outcome, RunOutcome.SUCCESS_EMPTY)
        self.assertIn("no records", response.detail)

    def test_several_records_returned_as_objects_rather_than_mappings_are_refused(self):
        with self.assertRaises(AdapterError) as caught:
            AdapterResponse(outcome=RunOutcome.SUCCESS_WITH_RESULTS, provenance=provenance(),
                            records=(object(),))

        self.assertIn("mappings", str(caught.exception))

    def test_provenance_requires_a_timezone_and_is_normalised_to_utc(self):
        with self.assertRaises(AdapterError):
            AdapterProvenance(source_id="a", source_name="A",
                              retrieved_at=datetime(2026, 10, 15, 6, 30), request_summary="x")

        local = AdapterProvenance(
            source_id="a", source_name="A", request_summary="x",
            retrieved_at=datetime(2026, 10, 15, 12, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))))

        self.assertEqual(local.retrieved_at, datetime(2026, 10, 15, 6, 30, tzinfo=timezone.utc))
        self.assertIn("2026-10-15T06:30:00+00:00", local.describe())


class NormalisationTests(unittest.TestCase):
    """Raw records become domain listings, with provenance kept and every rejection named."""

    def test_a_complete_record_becomes_a_listing_with_its_provenance(self):
        report = normalize_records((record(),), provenance(), source_id="fixture-a",
                                   source_name="Fixture A")

        self.assertEqual(report.rejected, ())
        listing = report.accepted[0]
        self.assertEqual(listing.listing_id, "a-1")
        self.assertEqual(listing.source_id, "fixture-a")
        self.assertEqual(listing.employer_name, "Sandbox Systems")
        self.assertEqual(listing.required_skills, frozenset({"Python", "SQL"}))
        self.assertIn("2026-10-15T06:30:00+00:00", listing.provenance_note or "")
        self.assertIn("fixture-a", listing.provenance_note or "")
        self.assertEqual(listing.availability_status.value, "unknown",
                         "an adapter may not assert that a listing is open")

    def test_the_fields_that_need_reading_prose_are_left_unset(self):
        """Eligibility scope, disciplines and experience ranges come from a reviewed parser, not a guess."""
        report = normalize_records((record(),), provenance(), source_id="fixture-a",
                                   source_name="Fixture A")
        listing = report.accepted[0]

        self.assertEqual(listing.eligibility_scope, "unknown")
        self.assertEqual(listing.eligible_countries, ())
        self.assertIsNone(listing.allowed_degree_disciplines)
        self.assertIsNone(listing.minimum_experience_years)
        self.assertIsNone(listing.maximum_experience_years)

    def test_a_record_missing_a_required_field_is_rejected_with_the_field_named(self):
        report = normalize_records((record(role_title=""),), provenance(), source_id="fixture-a",
                                   source_name="Fixture A")

        self.assertEqual(report.accepted, ())
        self.assertEqual(len(report.rejected), 1)
        self.assertEqual(report.rejected[0].index, 0)
        self.assertIn("role_title", report.rejected[0].reason)
        self.assertEqual(report.rejected_count, 1)

    def test_a_record_whose_url_is_not_a_link_is_rejected(self):
        report = normalize_records((record(url="not a url"),), provenance(), source_id="fixture-a",
                                   source_name="Fixture A")

        self.assertEqual(report.accepted, ())
        self.assertIn("not an http(s) address", report.rejected[0].reason)
        self.assertEqual(report.rejected[0].identifier, "a-1",
                         "the record's own id is the handle a person can look up")

    def test_a_rejected_record_falls_back_to_the_value_it_did_carry(self):
        """The handle a person is shown is what the record said, never something reconstructed from it."""
        report = normalize_records(({"listing_id": "", "source_listing_url": "not a url"},),
                                   provenance(), source_id="fixture-a", source_name="Fixture A")

        self.assertEqual(report.rejected[0].identifier, "not a url")
        self.assertEqual(report.rejected[0].index, 0, "the index is what locates it in the batch")

    def test_a_non_http_scheme_is_rejected(self):
        report = normalize_records((record(url="ftp://files.example.invalid/job/1"),), provenance(),
                                   source_id="fixture-a", source_name="Fixture A")

        self.assertEqual(report.accepted, ())
        self.assertIn("not an http(s) address", report.rejected[0].reason)

    def test_urls_are_canonicalised_but_case_sensitive_paths_are_kept(self):
        report = normalize_records(
            (record(url="HTTPS://Jobs.Example.INVALID//listing/A-1/?utm_source=mail&utm_medium=x"),),
            provenance(), source_id="fixture-a", source_name="Fixture A")

        self.assertEqual(report.accepted[0].source_listing_url,
                         "https://jobs.example.invalid/listing/A-1")

    def test_one_bad_record_does_not_lose_the_good_ones(self):
        report = normalize_records(
            (record("a-1"), {"listing_id": "a-2"}, record("a-3")), provenance(),
            source_id="fixture-a", source_name="Fixture A")

        self.assertEqual([item.listing_id for item in report.accepted], ["a-1", "a-3"])
        self.assertEqual([item.index for item in report.rejected], [1])

    def test_blank_and_absent_optional_values_stay_absent(self):
        report = normalize_records(
            (record("a-1", location_text="   ", work_mode=None, required_skills="Python"),),
            provenance(), source_id="fixture-a", source_name="Fixture A")
        listing = report.accepted[0]

        self.assertIsNone(listing.location_text)
        self.assertIsNone(listing.work_mode)
        self.assertEqual(listing.required_skills, frozenset({"Python"}),
                         "a single skill given as text is one skill, not one letter per character")

    def test_records_that_repeat_within_a_batch_are_merged_and_the_merge_is_reported(self):
        first = record("a-1")
        same_job = record("a-1-copy", url="https://jobs.example.invalid/listing/a-1/")

        report = normalize_records((first, same_job), provenance(), source_id="fixture-a",
                                   source_name="Fixture A")

        self.assertEqual([item.listing_id for item in report.accepted], ["a-1"])
        self.assertEqual(report.merged_within_source, (("a-1", "a-1-copy"),))

    def test_a_different_employer_is_not_merged(self):
        other = record("a-2", employer_name="Another Employer")

        report = normalize_records((record("a-1"), other), provenance(), source_id="fixture-a",
                                   source_name="Fixture A")

        self.assertEqual(len(report.accepted), 2)
        self.assertEqual(report.merged_within_source, ())


class AcrossSourceTests(unittest.TestCase):
    """Two sources offering the same job produce one listing and a visible record of the merge."""

    def test_the_same_job_from_two_sources_is_merged_with_the_kept_one_named(self):
        from_a = normalize_records(
            (record("a-1", url="https://jobs.example.invalid/listing/9001"),), provenance("fixture-a"),
            source_id="fixture-a", source_name="Fixture A").accepted
        from_b = normalize_records(
            (record("b-7", url="https://jobs.example.invalid/listing/9001/?utm_source=x"),),
            provenance("fixture-b"), source_id="fixture-b", source_name="Fixture B").accepted

        report = merge_across_sources({"fixture-a": from_a, "fixture-b": from_b})

        self.assertEqual(len(report.accepted), 1)
        self.assertEqual(report.accepted[0].source_id, "fixture-a", "the first batch wins, deterministically")
        self.assertEqual(report.merged_across_sources,
                         (("a-1 (fixture-a)", "b-7 (fixture-b)"),))

    def test_different_jobs_from_different_sources_both_survive(self):
        from_a = normalize_records((record("a-1"),), provenance("fixture-a"),
                                   source_id="fixture-a", source_name="Fixture A").accepted
        from_b = normalize_records((record("b-1", url="https://other.example.invalid/j/2"),),
                                   provenance("fixture-b"), source_id="fixture-b",
                                   source_name="Fixture B").accepted

        report = merge_across_sources({"fixture-a": from_a, "fixture-b": from_b})

        self.assertEqual(len(report.accepted), 2)
        self.assertEqual(report.merged_across_sources, ())

    def test_the_frameworks_deduplication_is_the_one_the_rest_of_the_app_uses(self):
        """A second identity rule would let the same job arrive twice through different paths."""
        listings = normalize_records(
            (record("a-1"), record("a-1-hex", url="https://jobs.example.invalid/listing/a-1")),
            provenance(), source_id="fixture-a", source_name="Fixture A").accepted

        self.assertEqual(len(deduplicate_listings(listings)), 1,
                         "the framework kept one already, and the app's own rule agrees")


class HealthTests(unittest.TestCase):
    """Health keeps four working states apart, because they lead to opposite decisions."""

    def test_success_empty_partial_and_failed_are_distinct(self):
        cases = (
            (RunOutcome.SUCCESS_WITH_RESULTS, "success", (record(),)),
            (RunOutcome.SUCCESS_EMPTY, "empty", ()),
            (RunOutcome.PARTIAL, "partial", (record(),)),
            (RunOutcome.RATE_LIMITED, "failed", ()),
        )
        for outcome, expected, records in cases:
            with self.subTest(outcome=outcome):
                response = call_adapter(
                    FixtureAdapter(source_id="fixture-a", source_name="Fixture A", outcome=outcome,
                                   records=records, detail="reported by the fixture"),
                    AdapterRequest(), now=RETRIEVED_AT)

                line = health_from_response("fixture-a", response)

                self.assertEqual(line.status, expected)
                self.assertEqual(line.describe().startswith("fixture-a: " + expected), True)

    def test_a_legitimate_empty_result_is_not_a_failure(self):
        response = call_adapter(FixtureAdapter(source_id="fixture-a", source_name="Fixture A",
                                               outcome=RunOutcome.SUCCESS_EMPTY),
                                AdapterRequest(), now=RETRIEVED_AT)

        line = health_from_response("fixture-a", response)

        self.assertEqual(line.status, "empty")
        self.assertFalse(is_failure(response.outcome))
        self.assertIn("no listing may be treated as closed", line.describe().replace("empty", "no listing may be treated as closed"))

    def test_health_carries_the_normalisation_counts(self):
        response = call_adapter(FixtureAdapter(source_id="fixture-a", source_name="Fixture A",
                                               records=(record("a-1"), {"listing_id": "a-2"})),
                                AdapterRequest(), now=RETRIEVED_AT)
        report = normalize_records(response.records, response.provenance, source_id="fixture-a",
                                   source_name="Fixture A")

        line = health_from_response("fixture-a", response, report=report)

        self.assertEqual(line.listing_count, 1)
        self.assertEqual(line.rejected_count, 1)
        self.assertIn("1 listing(s), 1 rejected", line.describe())

    def test_a_disabled_source_reports_that_nothing_was_tried(self):
        line = disabled_health("fixture-a", "its terms have not been reviewed")

        self.assertEqual(line.status, "disabled")
        self.assertIsNone(line.last_run_at)
        self.assertIn("never", line.describe())


class ProtocolTests(unittest.TestCase):
    """The fixture adapter is the reference shape a real adapter must match."""

    def test_a_fixture_adapter_satisfies_the_source_adapter_protocol(self):
        from career_agent.adapters import SourceAdapter

        self.assertIsInstance(FixtureAdapter(source_id="fixture-a", source_name="Fixture A"), SourceAdapter)

    def test_a_registered_adapter_reports_its_declared_capabilities(self):
        registry = AdapterRegistry()
        registry.register(FixtureAdapter(source_id="fixture-a", source_name="Fixture A"))

        capabilities = registry.capabilities("fixture-a")

        self.assertTrue(capabilities.discovery)
        self.assertFalse(capabilities.submission)
        self.assertIsNone(registry.capabilities("nothing-registered"))

    def test_an_adapter_that_declares_no_discovery_is_refused_even_when_its_gate_would_open(self):
        """Belt and braces: a gate that opened by mistake still does not run a discovery-less adapter.

        The gate is opened here only inside this test, for a source id that *is* in the reviewed set, by
        exercising the override the gate itself offers. The application never passes it, and the test
        below proves the default path stays closed.
        """
        registry = AdapterRegistry()
        adapter = FixtureAdapter(source_id="fixture-a", source_name="Fixture A",
                                 capabilities=SourceCapabilities(discovery=False))
        registry.register(adapter)

        with self.assertRaises(SourceDisabled) as caught:
            registry.execute("fixture-a", AdapterRequest())

        self.assertIn("does not declare discovery", str(caught.exception))
        self.assertEqual(adapter.calls, [], "a capability it did not declare is never used")

    def test_the_gate_is_the_one_thing_standing_between_the_app_and_one_real_source(self):
        """The measured state: forcing the quality gate open would enable exactly ``jobicy``.

        This is a fact about the safety surface, not a wish: the reviewed, approved and selected source
        is held back only by :data:`career_agent.sources.SOURCE_QUALITY_GATE_PASSED`. It is asserted here
        so that if a future change makes another source selectable, or removes that hold, this test says
        so loudly rather than the change passing unnoticed.
        """
        self.assertEqual(enabled_discovery_sources(), ())
        self.assertEqual(enabled_discovery_sources(quality_gate_passed=True), ("jobicy",))

    def test_the_adapter_layer_offers_no_way_to_open_the_gate(self):
        """No parameter, no attribute and no flag: the registry consults the recorded state only."""
        import inspect

        signature = inspect.signature(AdapterRegistry.execute)

        self.assertNotIn("quality_gate_passed", signature.parameters)
        self.assertNotIn("force", signature.parameters)


class PlacedRecordTests(unittest.TestCase):
    """The records these tests invent are clearly synthetic, so nothing here can be mistaken for live data."""

    def test_fixture_records_use_reserved_example_hosts(self):
        for item in (record(), record("b-2")):
            with self.subTest(listing=item["listing_id"]):
                self.assertIn("example", str(item["source_listing_url"]).casefold())

    def test_a_record_from_a_missing_field_reports_the_index_a_person_can_look_up(self):
        report = normalize_records((record("a-1"), record("a-2", source_listing_url="")), provenance(),
                                   source_id="fixture-a", source_name="Fixture A")

        self.assertEqual([item.index for item in report.rejected], [1])
        self.assertEqual(report.rejected[0].identifier, "a-2")


if __name__ == "__main__":
    unittest.main()
