#!/usr/bin/env python3
"""End-to-end smoke test for application-tracker integrity (schema version 2).

This script exercises the real store and domain APIs against isolated temporary
SQLite databases. It never reads or writes a user's application database, and it
uses only synthetic fixture data.

Run from the repository root:
    python scripts/tracker_smoke_test.py
    python scripts/tracker_smoke_test.py --keep

Exit code 0 means every scenario passed; any failure or error returns nonzero.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Callable

if __package__ in (None, ""):
    # Allow "python scripts/tracker_smoke_test.py" without installing the package.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from career_agent import (
    ApplicationStatus, ApplicationTracker, Availability, CandidateProfile, Decision,
    JobListing, StaleApplicationError, evaluate_eligibility,
)
from career_agent.export import FORMAT_VERSION, build_export_payload, write_export
from career_agent.store import CareerStore


class SmokeFailure(AssertionError):
    """A scenario assertion failed."""


class SkipScenario(Exception):
    """The repository does not implement the capability this scenario would check."""


def expect(condition: object, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


SCENARIOS: list[tuple[str, Callable[[Path], str | None]]] = []


def scenario(name: str):
    def register(function: Callable[[Path], str | None]) -> Callable[[Path], str | None]:
        SCENARIOS.append((name, function))
        return function
    return register


# --------------------------------------------------------------------- fixtures

def sample_profile(**overrides) -> CandidateProfile:
    values = dict(
        candidate_country="India", degree_discipline="ECE", study_status="undergraduate",
        graduation_year=2027, experience_years=0.5, skills=frozenset({"Python"}),
    )
    values.update(overrides)
    return CandidateProfile(**values)


def sample_job(listing_id: str = "j1", availability: Availability = Availability.OPEN, **overrides) -> JobListing:
    values = dict(
        listing_id=listing_id, source_id="manual", source_name="Manual",
        source_listing_url="https://jobs.example/role/1", employer_name="Example",
        role_title="AI Intern", availability_status=availability,
        eligibility_scope="restricted", eligible_countries=("India",),
        allowed_degree_disciplines=("ECE",), allowed_study_statuses=("undergraduate",),
        allowed_graduation_years=(2027,), required_skills=frozenset({"Python"}),
        provenance_note="Synthetic smoke-test listing; checked locally.",
    )
    values.update(overrides)
    return JobListing(**values)


def open_store(workspace: Path, name: str = "smoke.sqlite3") -> CareerStore:
    workspace.mkdir(parents=True, exist_ok=True)
    return CareerStore(workspace / name)


def walk_to_submission(store: CareerStore, listing_id: str = "j1") -> ApplicationTracker:
    tracker = store.start_application(listing_id)
    for status in (
        ApplicationStatus.SHORTLISTED,
        ApplicationStatus.PREPARED,
        ApplicationStatus.AWAITING_USER,
        ApplicationStatus.SUBMISSION_ATTEMPTED,
    ):
        tracker = store.save_tracker(tracker.transition(status))
    return tracker


def confirm(store: CareerStore, tracker: ApplicationTracker, evidence: str = "Synthetic employer confirmation") -> ApplicationTracker:
    return store.save_tracker(
        tracker.transition(ApplicationStatus.CONFIRMED, evidence=evidence, candidate_confirmed=True)
    )


def table_names(store: CareerStore) -> set[str]:
    rows = store._connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row["name"] for row in rows}


def schema_version(store: CareerStore) -> int:
    return store._connection.execute("PRAGMA user_version").fetchone()[0]


def row_counts(store: CareerStore) -> tuple[int, int]:
    jobs = store._connection.execute("SELECT COUNT(*) AS n FROM job_listings").fetchone()["n"]
    events = store._connection.execute("SELECT COUNT(*) AS n FROM application_events").fetchone()["n"]
    return jobs, events


# -------------------------------------------------------------------- scenarios

@scenario("fresh database initializes schema version 2")
def fresh_database(workspace: Path) -> str:
    with open_store(workspace) as store:
        expect(schema_version(store) == 2, f"expected schema 2, found {schema_version(store)}")
        expect(
            {"job_listings", "application_tracker", "application_events", "candidate_profile"} <= table_names(store),
            f"missing tables: {sorted(table_names(store))}",
        )
        expect(store.get_profile() is None, "a fresh database must not contain a profile")
    with open_store(workspace) as reopened:
        expect(schema_version(reopened) == 2, "re-opening a v2 database must not change its version")
    return ""


@scenario("an open listing starts attempt 1 with a recorded event")
def attempt_creation(workspace: Path) -> str:
    with open_store(workspace) as store:
        store.save_profile(sample_profile())
        store.save_job(sample_job())
        expect(store.get_tracker("j1") is None, "saving a job must not fabricate a tracker")
        tracker = store.start_application("j1")
        expect(tracker.attempt_number == 1, f"expected attempt 1, got {tracker.attempt_number}")
        expect(tracker.status is ApplicationStatus.DISCOVERED, f"expected discovered, got {tracker.status}")
        expect(tracker.revision == 0, f"expected revision 0, got {tracker.revision}")
        expect(len(store.list_attempts("j1")) == 1, "expected exactly one attempt")
        events = store.list_events("j1", 1)
        expect(len(events) == 1, f"expected 1 event, got {len(events)}")
        expect(events[0].from_status is None, "the first event must have no source status")
        expect(events[0].to_status is ApplicationStatus.DISCOVERED, "the first event must record discovered")
    return ""


@scenario("a valid transition is persisted and audited")
def valid_transition(workspace: Path) -> str:
    with open_store(workspace) as store:
        store.save_job(sample_job())
        started = store.start_application("j1")
        saved = store.save_tracker(started.transition(ApplicationStatus.SHORTLISTED))
        expect(saved.status is ApplicationStatus.SHORTLISTED, f"returned {saved.status}")
        expect(saved.revision == 1, f"expected revision 1, got {saved.revision}")
        reloaded = store.get_tracker("j1")
        expect(reloaded == saved, f"persisted {reloaded} does not match returned {saved}")
        events = store.list_events("j1", 1)
        expect(len(events) == 2, f"expected 2 events, got {len(events)}")
        expect(events[-1].from_status is ApplicationStatus.DISCOVERED, "event must record the source status")
        expect(events[-1].to_status is ApplicationStatus.SHORTLISTED, "event must record the destination status")
    return ""


@scenario("confirmation evidence survives a later status change")
def evidence_survives(workspace: Path) -> str:
    with open_store(workspace) as store:
        store.save_job(sample_job())
        confirmed = confirm(store, walk_to_submission(store))
        response = store.save_tracker(confirmed.transition(ApplicationStatus.RESPONSE_RECEIVED))
        expect(
            response.status_evidence == "Synthetic employer confirmation",
            f"evidence was erased: {response.status_evidence!r}",
        )
        expect(response.candidate_confirmed, "the candidate-confirmed flag was lost")
        reloaded = store.get_tracker("j1")
        expect(reloaded.status_evidence == "Synthetic employer confirmation", "reload lost the evidence")
        confirmation_events = [
            event for event in store.list_events("j1", 1) if event.to_status is ApplicationStatus.CONFIRMED
        ]
        expect(len(confirmation_events) == 1, "expected exactly one confirmation event")
        expect(
            confirmation_events[0].evidence == "Synthetic employer confirmation",
            "the confirmation event no longer records its evidence",
        )
        expect(store.list_events("j1", 1)[-1].to_status is ApplicationStatus.RESPONSE_RECEIVED, "latest event is wrong")
    return ""


@scenario("a new attempt inherits nothing from the withdrawn attempt")
def reapplication_is_clean(workspace: Path) -> str:
    with open_store(workspace) as store:
        store.save_job(sample_job())
        confirmed = confirm(store, walk_to_submission(store))
        store.save_tracker(confirmed.transition(ApplicationStatus.WITHDRAWN))
        second = store.start_application("j1")
        expect(second.attempt_number == 2, f"expected attempt 2, got {second.attempt_number}")
        expect(second.status is ApplicationStatus.DISCOVERED, f"expected discovered, got {second.status}")
        expect(second.status_evidence is None, f"evidence leaked into the new attempt: {second.status_evidence!r}")
        expect(not second.candidate_confirmed, "the confirmation flag leaked into the new attempt")
        first = store.get_tracker("j1", 1)
        expect(first.status is ApplicationStatus.WITHDRAWN, "attempt 1 must stay withdrawn")
        expect(first.status_evidence == "Synthetic employer confirmation", "attempt 1 lost its evidence")
        expect(len(store.list_events("j1", 1)) == 7, f"attempt 1 history changed: {len(store.list_events('j1', 1))}")
        expect(len(store.list_events("j1", 2)) == 1, "attempt 2 history must start fresh")
    return ""


@scenario("invalid and bypassing transitions are rejected without corruption")
def invalid_transition_is_safe(workspace: Path) -> str:
    with open_store(workspace) as store:
        store.save_job(sample_job())
        started = store.start_application("j1")
        baseline = store.get_tracker("j1")
        events_before = len(store.list_events("j1", 1))

        try:
            store.save_tracker(ApplicationTracker("j1", ApplicationStatus.CONFIRMED, "bypass evidence"))
            raise SmokeFailure("a new attempt was allowed to start as confirmed")
        except ValueError:
            pass
        try:
            store.save_tracker(ApplicationTracker("j1", ApplicationStatus.PREPARED, revision=started.revision))
            raise SmokeFailure("a skipped transition was accepted")
        except ValueError:
            pass
        try:
            store.save_tracker(
                ApplicationTracker("j1", ApplicationStatus.CONFIRMED, None, True, 1, started.revision)
            )
            raise SmokeFailure("confirmation without evidence was accepted")
        except ValueError:
            pass

        after = store.get_tracker("j1")
        expect(after == baseline, f"failed writes changed the record: {after} != {baseline}")
        expect(len(store.list_events("j1", 1)) == events_before, "failed writes appended events")
        valid = store.save_tracker(store.get_tracker("j1").transition(ApplicationStatus.SHORTLISTED))
        expect(valid.status is ApplicationStatus.SHORTLISTED, "the record became unusable after rejected writes")
    return ""


@scenario("a stale update is detected and does not overwrite newer state")
def stale_update(workspace: Path) -> str:
    path = workspace / "concurrent.sqlite3"
    workspace.mkdir(parents=True, exist_ok=True)
    with CareerStore(path) as window_a, CareerStore(path) as window_b:
        window_a.save_job(sample_job())
        window_a.start_application("j1")
        view_a = window_a.get_tracker("j1")
        view_b = window_b.get_tracker("j1")
        window_a.save_tracker(view_a.transition(ApplicationStatus.SHORTLISTED))
        events_after_a = len(window_b.list_events("j1", 1))
        try:
            window_b.save_tracker(view_b.transition(ApplicationStatus.WITHDRAWN))
            raise SmokeFailure("a stale write was accepted")
        except StaleApplicationError:
            pass
        persisted = window_b.get_tracker("j1")
        expect(persisted.status is ApplicationStatus.SHORTLISTED, f"stale write corrupted status: {persisted.status}")
        expect(persisted.revision == 1, f"stale write changed revision: {persisted.revision}")
        expect(len(window_b.list_events("j1", 1)) == events_after_a, "stale write appended an event")
        fresh = window_b.get_tracker("j1")
        expect(
            window_b.save_tracker(fresh.transition(ApplicationStatus.PREPARED)).status is ApplicationStatus.PREPARED,
            "a reloaded record could not be saved",
        )
    return ""


@scenario("repeated observations and saves do not duplicate records or events")
def repeated_writes(workspace: Path) -> str:
    with open_store(workspace) as store:
        store.save_job(sample_job())
        store.save_job(sample_job(), observed_at="2026-10-18T00:00:00+00:00")
        jobs, _events = row_counts(store)
        expect(jobs == 1, f"saving the same listing twice created {jobs} rows")

        started = store.start_application("j1")
        events_after_start = len(store.list_events("j1", 1))
        store.save_tracker(started)
        store.save_tracker(started)
        expect(len(store.list_events("j1", 1)) == events_after_start, "identical saves appended events")
        expect(store.get_tracker("j1").revision == started.revision, "identical saves advanced the revision")

        try:
            store.start_application("j1")
            raise SmokeFailure("a second attempt was started while one was active")
        except ValueError:
            pass
        expect(len(store.list_attempts("j1")) == 1, "an active attempt was duplicated")

        store.save_job(sample_job("j2", source_listing_url="https://jobs.example/role/1?utm_source=feed"))
        store.start_application("j2")
        store.save_tracker(store.get_tracker("j1", 1).transition(ApplicationStatus.SHORTLISTED))
        try:
            store.save_tracker(store.get_tracker("j2").transition(ApplicationStatus.SHORTLISTED))
            raise SmokeFailure("a duplicate observation was shortlisted twice")
        except ValueError:
            pass
        expect(
            store.get_tracker("j2").status is ApplicationStatus.DISCOVERED,
            "the blocked duplicate was mutated anyway",
        )
    return ""


@scenario("withdrawal keeps the attempt and its history intact")
def withdrawal_preserves_history(workspace: Path) -> str:
    with open_store(workspace) as store:
        store.save_job(sample_job())
        confirmed = confirm(store, walk_to_submission(store))
        withdrawn = store.save_tracker(confirmed.transition(ApplicationStatus.WITHDRAWN))
        expect(withdrawn.is_terminal, "withdrawn must be terminal")
        expect(withdrawn.status_evidence == "Synthetic employer confirmation", "withdrawal erased the evidence")
        reloaded = store.get_tracker("j1")
        expect(reloaded.status is ApplicationStatus.WITHDRAWN, f"persisted {reloaded.status}")
        expect(len(store.list_attempts("j1")) == 1, "withdrawal created an unexpected attempt")
        expect(store.list_events("j1", 1)[-1].to_status is ApplicationStatus.WITHDRAWN, "withdrawal event missing")
    return ""


@scenario("re-application to a still-open listing creates a separate attempt")
def reapplication_creates_attempt(workspace: Path) -> str:
    with open_store(workspace) as store:
        store.save_job(sample_job())
        store.save_tracker(store.start_application("j1").transition(ApplicationStatus.WITHDRAWN))
        second = store.start_application("j1")
        expect(second.attempt_number == 2, f"expected attempt 2, got {second.attempt_number}")
        expect([a.attempt_number for a in store.list_attempts("j1")] == [1, 2], "attempts were not preserved")
        shortlisted = store.save_tracker(second.transition(ApplicationStatus.SHORTLISTED))
        expect(
            (shortlisted.attempt_number, shortlisted.status) == (2, ApplicationStatus.SHORTLISTED),
            f"unexpected second attempt: {shortlisted.attempt_number}/{shortlisted.status}",
        )
        expect(store.get_tracker("j1", 1).status is ApplicationStatus.WITHDRAWN, "attempt 1 was revived")
    return ""


@scenario("closed and ineligible listings cannot start an application")
def closed_listing_restrictions(workspace: Path) -> str:
    with open_store(workspace) as store:
        store.save_job(sample_job("closed", Availability.CLOSED, source_listing_url="https://jobs.example/closed"))
        expect(store.get_tracker("closed") is None, "a closed listing was tracked")
        try:
            store.start_application("closed")
            raise SmokeFailure("a closed listing started an application")
        except ValueError:
            pass
        expect(store.get_tracker("closed") is None, "the refused attempt was still persisted")

        store.save_job(sample_job("expired", Availability.EXPIRED, source_listing_url="https://jobs.example/expired"))
        try:
            store.start_application("expired")
            raise SmokeFailure("an expired listing started an application")
        except ValueError:
            pass

        store.save_job(sample_job("withdrawn", source_listing_url="https://jobs.example/withdrawn"))
        store.save_tracker(store.start_application("withdrawn").transition(ApplicationStatus.WITHDRAWN))
        store.save_job(sample_job("withdrawn", Availability.CLOSED, source_listing_url="https://jobs.example/withdrawn"))
        try:
            store.start_application("withdrawn")
            raise SmokeFailure("a withdrawn attempt was re-opened on a closed listing")
        except ValueError:
            pass

        ineligible = evaluate_eligibility(
            sample_profile(candidate_country="Brazil"), sample_job("closed", Availability.CLOSED),
        )
        expect(ineligible.decision is not Decision.PASS, "an ineligible/closed listing evaluated as PASS")
    return "shortlisting also requires eligibility PASS in the UI; that button-level gate is not exercised headlessly"


@scenario("format-v2 export preserves attempts and their event history")
def export_preserves_history(workspace: Path) -> str:
    with open_store(workspace) as store:
        store.save_profile(sample_profile())
        store.save_job(sample_job())
        confirmed = confirm(store, walk_to_submission(store))
        store.save_tracker(confirmed.transition(ApplicationStatus.WITHDRAWN))
        store.start_application("j1")

        payload = build_export_payload(store)
        expect(payload["format_version"] == FORMAT_VERSION == 2, f"unexpected format {payload['format_version']}")
        expect(payload["privacy_note"], "export must carry its privacy note")
        attempts = payload["jobs"][0]["application_attempts"]
        expect([a["attempt_number"] for a in attempts] == [1, 2], f"attempts missing: {attempts}")
        expect(attempts[0]["status"] == "withdrawn", f"attempt 1 status: {attempts[0]['status']}")
        confirmation = [e for e in attempts[0]["application_events"] if e["to_status"] == "confirmed"]
        expect(len(confirmation) == 1, "the confirmation event is missing from the export")
        expect(confirmation[0]["evidence"] == "Synthetic employer confirmation", "export lost the evidence")
        expect(attempts[1]["status"] == "discovered" and attempts[1]["status_evidence"] is None, "attempt 2 is not fresh")
        expect(payload["profile"]["skills"] == ["Python"], "profile sets are not JSON-safe")

        destination = workspace / "export.json"
        written = write_export(store, destination)
        reloaded = json.loads(destination.read_text(encoding="utf-8"))
        expect(reloaded == written, "written export does not match the returned payload")
        expect(reloaded == payload, "written export does not match the built payload")
    return ""


@scenario("export can be restored through an import API")
def import_round_trip(workspace: Path) -> str:
    raise SkipScenario("the repository has no import/restore API; export is validated but not round-tripped")


@scenario("failed operations leave the database consistent and usable")
def failure_consistency(workspace: Path) -> str:
    path = workspace / "consistency.sqlite3"
    workspace.mkdir(parents=True, exist_ok=True)
    with CareerStore(path) as store, CareerStore(path) as other:
        store.save_job(sample_job())
        started = store.start_application("j1")
        baseline = store.get_tracker("j1")
        events_before = len(store.list_events("j1", 1))

        for label, operation in (
            ("invalid transition", lambda: store.save_tracker(started.transition(ApplicationStatus.CONFIRMED))),
            ("skipped transition", lambda: store.save_tracker(ApplicationTracker("j1", ApplicationStatus.PREPARED, revision=started.revision))),
        ):
            try:
                operation()
                raise SmokeFailure(f"{label} was accepted")
            except ValueError:
                pass

        expect(store.get_tracker("j1") == baseline, "a failed operation changed the stored attempt")
        expect(len(store.list_events("j1", 1)) == events_before, "a failed operation appended an event")

        other.save_tracker(other.get_tracker("j1").transition(ApplicationStatus.SHORTLISTED))
        try:
            store.save_tracker(baseline.transition(ApplicationStatus.WITHDRAWN))
            raise SmokeFailure("a stale operation was accepted")
        except StaleApplicationError:
            pass

        expect(store.get_tracker("j1").status is ApplicationStatus.SHORTLISTED, "stale write corrupted the status")
        valid = store.save_tracker(store.get_tracker("j1").transition(ApplicationStatus.PREPARED))
        expect(valid.status is ApplicationStatus.PREPARED, "the database was unusable after failures")
        expect(store.list_events("j1", 1)[-1].to_status is ApplicationStatus.PREPARED, "history stopped recording")
    return ""


@scenario("a schema-v1 database migrates to attempt 1 with evidence intact")
def migrate_v1(workspace: Path) -> str:
    workspace.mkdir(parents=True, exist_ok=True)
    path = workspace / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE candidate_profile (
            profile_id INTEGER PRIMARY KEY CHECK (profile_id = 1),
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE job_listings (
            listing_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            duplicate_key TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        );
        CREATE TABLE application_tracker (
            listing_id TEXT PRIMARY KEY REFERENCES job_listings(listing_id) ON DELETE CASCADE,
            status TEXT NOT NULL,
            status_evidence TEXT,
            candidate_confirmed INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );
    """)
    connection.execute(
        "INSERT INTO job_listings VALUES (?, ?, ?, ?, ?)",
        (
            "legacy",
            json.dumps({
                "listing_id": "legacy", "source_id": "manual", "source_name": "Manual",
                "source_listing_url": "https://jobs.example/legacy", "employer_name": "Example",
                "role_title": "Legacy role", "availability_status": "open",
            }),
            "url:https://jobs.example/legacy",
            "2026-10-13T00:00:00+00:00",
            "2026-10-13T00:00:00+00:00",
        ),
    )
    connection.execute(
        "INSERT INTO application_tracker VALUES (?, ?, ?, ?, ?)",
        ("legacy", "confirmed", "Legacy employer email", 1, "2026-10-13T00:00:00+00:00"),
    )
    connection.execute("PRAGMA user_version = 1")
    connection.commit()
    connection.close()

    with CareerStore(path) as store:
        expect(schema_version(store) == 2, f"expected schema 2 after migration, found {schema_version(store)}")
        migrated = store.get_tracker("legacy")
        expect(migrated.attempt_number == 1, f"expected attempt 1, got {migrated.attempt_number}")
        expect(migrated.revision == 0, f"expected revision 0, got {migrated.revision}")
        expect(migrated.status is ApplicationStatus.CONFIRMED, f"expected confirmed, got {migrated.status}")
        expect(migrated.status_evidence == "Legacy employer email", "migration lost the evidence")
        expect(migrated.candidate_confirmed, "migration lost the confirmation flag")
        expect(store.list_events("legacy") == (), "migration must not fabricate history")
    with CareerStore(path) as reopened:
        expect(schema_version(reopened) == 2, "reopening the migrated database changed its version")
        expect(len(reopened.list_attempts("legacy")) == 1, "reopening duplicated the migrated attempt")
    return ""


# ------------------------------------------------------------------------ runner

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="keep the temporary workspace and print its path")
    args = parser.parse_args()

    workspace = Path(tempfile.mkdtemp(prefix="tracker-smoke-"))
    passed = failed = skipped = 0
    failures: list[str] = []
    try:
        for index, (name, run) in enumerate(SCENARIOS, start=1):
            label = f"{index:02d} {name}"
            try:
                note = run(workspace / f"scenario-{index:02d}")
            except SkipScenario as exc:
                skipped += 1
                print(f"SKIP  {label}\n      {exc}")
            except SmokeFailure as exc:
                failed += 1
                failures.append(label)
                print(f"FAIL  {label}\n      {exc}")
            except Exception as exc:  # noqa: BLE001 - a crash is a failed scenario, not a pass
                failed += 1
                failures.append(label)
                print(f"ERROR {label}\n      {type(exc).__name__}: {exc}")
            else:
                passed += 1
                print(f"PASS  {label}")
                if note:
                    print(f"      note: {note}")
    finally:
        if args.keep:
            print(f"\nWorkspace kept for inspection: {workspace}")
        else:
            shutil.rmtree(workspace, ignore_errors=True)

    print(f"\nSUMMARY: {passed} passed, {failed} failed, {skipped} skipped ({len(SCENARIOS)} scenarios)")
    if failures:
        print("Failed: " + "; ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
