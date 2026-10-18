"""The operational report: what has been happening, from durable records only.

This is the answer to "what has this thing been doing, and what does it need from me?", and it is
built entirely from rows that already exist - scheduled tasks and their runs, the application tracker,
interviews and preparation, the attempt ledger, the standing authorisation, the source gates. Nothing
here performs anything, schedules anything, or asks a source for anything.

Three rules shaped it, and each one is load-bearing:

* **Queued is not done.** A task that is scheduled, a run that is pending, an application in a
  "prepared" state - none of them is evidence that anything reached anybody. They are reported as
  what they are, in their own section, and never counted as outcomes.
* **Unknown is a finding, not a gap.** A run that timed out, an attempt whose outcome was never
  established, an application recorded as sent-but-unverified: those lead the report, because they
  are the things only a person can resolve.
* **A refusal is not a failure.** A scheduled discovery run that refuses because the quality gate is
  closed is the product working as designed, and a report that counts it as an error teaches the
  person to ignore errors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Sequence

from .attempts import AttemptState, attempts_needing_reconciliation
from .core import ApplicationStatus, Availability
from .policy import ACTION_LABELS
from .sources import SOURCE_DECISIONS, discovery_gate, enabled_discovery_sources
from .tasks import RunState

#: Statuses that mean somebody still has to do something before anything can leave this machine.
AWAITING_PERSON = (
    ApplicationStatus.DISCOVERED, ApplicationStatus.SHORTLISTED, ApplicationStatus.PREPARED,
    ApplicationStatus.AWAITING_USER,
)

#: Statuses where what actually happened at the employer's end is not established.
UNVERIFIED_STATUSES = (
    ApplicationStatus.SUBMISSION_ATTEMPTED, ApplicationStatus.SUBMITTED_UNVERIFIED,
    ApplicationStatus.UNKNOWN_STATUS,
)

#: Run states that are a *finding* rather than a failure or a success.
UNRESOLVED_RUN_STATES = (RunState.TIMED_OUT, RunState.INTERRUPTED, RunState.RUNNING)


class ReportError(ValueError):
    """A report was asked for in terms it cannot honestly be produced in."""


@dataclass(frozen=True)
class ReportSection:
    """One part of the report: a heading, the lines under it, and whether it needs attention."""

    heading: str
    lines: tuple[str, ...]
    needs_attention: bool = False

    def describe(self) -> tuple[str, ...]:
        marker = " — needs you" if self.needs_attention else ""
        return (f"{self.heading}{marker}",) + tuple(f"  {line}" for line in self.lines)


@dataclass(frozen=True)
class OperationsReport:
    """What the records say about a window of time, and what they deliberately do not say."""

    generated_at: datetime
    window_days: int
    sections: tuple[ReportSection, ...]
    attention_count: int = 0
    caveats: tuple[str, ...] = field(default_factory=tuple)

    def headline(self) -> str:
        period = "day" if self.window_days == 1 else f"{self.window_days} days"
        if self.attention_count == 0:
            return (f"Nothing from the last {period} needs you, and nothing ran: every source and "
                    f"every outbound action is still switched off in this build.")
        items = "1 thing" if self.attention_count == 1 else f"{self.attention_count} things"
        return f"{items} from the last {period} need you."

    def describe(self) -> tuple[str, ...]:
        lines: list[str] = [
            f"Report for the {self.window_days} day(s) to "
            f"{self.generated_at.astimezone(timezone.utc).isoformat()}",
            "",
            self.headline(),
        ]
        for section in self.sections:
            lines.append("")
            lines.extend(section.describe())
        if self.caveats:
            lines.append("")
            lines.append("What this report does not say")
            lines.extend(f"  - {caveat}" for caveat in self.caveats)
        return tuple(lines)

    @property
    def needs_attention(self) -> bool:
        return self.attention_count > 0


def _moment(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ReportError("A report is produced as of a moment that carries its timezone.")
    return now.astimezone(timezone.utc)


def _within(value: datetime | None, *, since: datetime) -> bool:
    return value is not None and value.astimezone(timezone.utc) >= since


def _runs_section(store: Any, *, since: datetime, now: datetime) -> tuple[ReportSection, int]:
    """What the schedule did, with refusals kept apart from failures and queues from outcomes."""
    tasks = store.list_scheduled_tasks()
    runs = [run for run in store.list_task_runs() if _within(run.finished_at or run.created_at,
                                                             since=since)]
    counted: dict[RunState, int] = {}
    for run in runs:
        counted[run.state] = counted.get(run.state, 0) + 1
    lines: list[str] = []
    paused = [task for task in tasks if not task.enabled]
    lines.append(f"{len(tasks)} task(s) scheduled, {len(paused)} paused.")
    if not runs:
        lines.append("No attempt was recorded in this window.")
    else:
        lines.append(
            "Attempts recorded: "
            + ", ".join(f"{count} {state.value}" for state, count in sorted(
                counted.items(), key=lambda pair: pair[0].value)) + ".")
    refused = counted.get(RunState.REFUSED, 0)
    if refused:
        lines.append(f"{refused} refusal(s) are the permission rules working, not errors: a scheduled "
                     "discovery run refuses while the source gate is closed.")
    unresolved = sum(counted.get(state, 0) for state in UNRESOLVED_RUN_STATES)
    if unresolved:
        lines.append(f"{unresolved} attempt(s) ended without a recorded outcome (timed out, "
                     "interrupted, or still marked running). Those cannot be read as successes.")
    failed = counted.get(RunState.FAILED, 0)
    if failed:
        lines.append(f"{failed} attempt(s) failed and said why in their own record.")
    upcoming = [task for task in tasks if task.enabled and task.next_run_at is not None]
    if upcoming:
        following = min(upcoming, key=lambda task: task.next_run_at)
        when = following.next_run_at.astimezone(timezone.utc).isoformat()
        due = " (due now)" if following.next_run_at <= now else ""
        lines.append(f"Next: {following.task_id} at {when}{due}. Scheduled is not done.")
    else:
        lines.append("Nothing is scheduled to run next.")
    return ReportSection("Scheduled work", tuple(lines), bool(unresolved or failed)), unresolved + failed


def _sources_section(store: Any) -> tuple[ReportSection, int]:
    """What the sources did: nothing, and the report says so in the gate's own words."""
    enabled = enabled_discovery_sources()
    lines = [f"{len(SOURCE_DECISIONS)} source(s) known, {len(enabled)} enabled for discovery."]
    for decision in SOURCE_DECISIONS:
        gate = discovery_gate(decision.source_id)
        state = "permitted" if gate.allowed else "closed"
        lines.append(f"{decision.source_id}: {state} — {gate.reason}")
    lines.append("No listing in this database came from a live run: nothing has run.")
    return ReportSection("Sources", tuple(lines)), 0


def _applications_section(store: Any, *, since: datetime) -> tuple[ReportSection, int]:
    """Where applications stand, with the queue, the unverified and the outcomes kept apart."""
    trackers = store.list_trackers()
    by_status: dict[ApplicationStatus, int] = {}
    for tracker in trackers:
        by_status[tracker.status] = by_status.get(tracker.status, 0) + 1
    waiting = sum(by_status.get(status, 0) for status in AWAITING_PERSON)
    unverified = sum(by_status.get(status, 0) for status in UNVERIFIED_STATUSES)
    confirmed = by_status.get(ApplicationStatus.CONFIRMED, 0)
    replied = by_status.get(ApplicationStatus.RESPONSE_RECEIVED, 0)
    lines = [f"{len(trackers)} application record(s)."]
    if waiting:
        lines.append(f"{waiting} waiting on you before anything could be sent - prepared or "
                     "shortlisted is not sent.")
    if unverified:
        lines.append(f"{unverified} recorded as attempted or unverified: what the employer received "
                     "is not established, and this application will not assume it.")
    if confirmed or replied:
        lines.append(f"{confirmed} confirmed by your own check; {replied} with a recorded reply.")
    failures = by_status.get(ApplicationStatus.FAILED, 0)
    if failures:
        lines.append(f"{failures} recorded as failed.")
    if not trackers:
        lines.append("Nothing has been written down yet, so there is nothing to report.")
    return ReportSection("Applications", tuple(lines), bool(unverified)), unverified


def _attempts_section(store: Any, *, now: datetime) -> tuple[ReportSection, int]:
    """Attempts whose outcome nobody established - the part only a person can close."""
    records = store.list_attempts()
    if not records:
        return ReportSection("Attempts at outside actions",
                             ("No attempt at an outside action has been recorded.",)), 0
    unresolved = [record for record in records if record.state is AttemptState.UNKNOWN]
    stale = attempts_needing_reconciliation(records, now=now)
    counted = {state: sum(1 for record in records if record.state is state) for state in AttemptState}
    lines = [
        f"{len(records)} attempt(s) recorded: {counted[AttemptState.PERFORMED]} performed, "
        f"{counted[AttemptState.FAILED]} known not to have happened, "
        f"{counted[AttemptState.REFUSED]} refused before anything was tried.",
    ]
    if unresolved:
        lines.append(
            f"{len(unresolved)} with an outcome nobody established. Each one blocks any further "
            "attempt at the same job until you check what happened and record it.")
        lines.extend(f"- {record.describe()}" for record in unresolved)
    if stale:
        lines.append(f"{len(stale)} of those have been unresolved long enough to be worth checking "
                     "now. Age does not settle them.")
    return ReportSection("Attempts at outside actions", tuple(lines), bool(unresolved)), len(unresolved)


def _actions_section(store: Any, *, now: datetime, horizon: int) -> tuple[ReportSection, int]:
    """Dates that are about to pass: follow-ups, interviews and preparation with a day on them."""
    today = now.date()
    limit = today + timedelta(days=horizon)
    due_follow_ups = [tracker for tracker in store.list_follow_up_trackers()
                      if tracker.follow_up_on is not None and tracker.follow_up_on <= limit]
    overdue = [tracker for tracker in due_follow_ups if tracker.follow_up_on < today]
    interviews = [round_ for round_ in store.list_interviews()
                  if round_.scheduled_on is not None and today <= round_.scheduled_on <= limit]
    preparation = [item for item in store.list_preparation()
                   if getattr(item, "due_on", None) is not None and item.due_on <= limit
                   and not getattr(item, "completed", False)]
    lines = []
    if due_follow_ups:
        lines.append(f"{len(due_follow_ups)} follow-up day(s) at or before {limit.isoformat()}, "
                     f"{len(overdue)} already past.")
    if interviews:
        lines.append(f"{len(interviews)} interview round(s) in the next {horizon} day(s).")
    if preparation:
        lines.append(f"{len(preparation)} preparation item(s) due.")
    if not lines:
        lines.append(f"Nothing is dated in the next {horizon} day(s).")
    attention = len(overdue) + len(interviews)
    return ReportSection("Dates coming up", tuple(lines), bool(attention)), attention


def _authorisation_section(store: Any) -> tuple[ReportSection, int]:
    """What the person has authorised, and the fact that it still does not switch anything on."""
    policy = store.get_global_policy()
    version = store.policy_version_number()
    if version == 0 or policy.is_empty:
        return ReportSection(
            "What is authorised",
            ("Nothing is authorised, so nothing may be attempted outside this machine.",)), 0
    if policy.revoked_at:
        return ReportSection(
            "What is authorised",
            (f"Authorisation version {version} is withdrawn; nothing may be attempted.",)), 0
    lines = [f"Authorisation version {version}: "
             + ", ".join(sorted(f"{source_id} — {ACTION_LABELS[action]}"
                                for source_id, action in policy.allowed)) + "."]
    if policy.stop_all:
        lines.append("Everything is stopped, so none of it applies right now.")
    lines.append("Every source is still switched off in this build, so none of this has run.")
    return ReportSection("What is authorised", tuple(lines)), 0


def build_operations_report(store: Any, *, now: datetime | None = None, window_days: int = 1,
                            horizon_days: int = 7) -> OperationsReport:
    """Build the report from stored records only.

    ``window_days`` is how far back the "what happened" sections look; ``horizon_days`` is how far
    forward the dated section looks. Neither reads anything outside the database, and no section
    treats scheduled or queued work as something that happened.
    """
    moment = _moment(now)
    if window_days < 1 or horizon_days < 0:
        raise ReportError("A report covers at least one day back and no negative days forward.")
    since = moment - timedelta(days=window_days)
    sections: list[ReportSection] = []
    attention = 0
    for section, count in (
        _attempts_section(store, now=moment),
        _applications_section(store, since=since),
        _actions_section(store, now=moment, horizon=horizon_days),
        _runs_section(store, since=since, now=moment),
        _sources_section(store),
        _authorisation_section(store),
    ):
        sections.append(section)
        attention += count
    caveats = (
        "nothing here was fetched, sent or submitted: discovery, submission, outbound email and "
        "inbox reading are all switched off in this build",
        "a scheduled task, a queued run and an application marked prepared are plans, not outcomes, "
        "and are never counted as things that happened",
        "an attempt whose outcome was never established stays unknown until you establish it; time "
        "does not settle one",
        "replies, bounces and employer decisions appear here only when you have written them down",
    )
    return OperationsReport(generated_at=moment, window_days=window_days, sections=tuple(sections),
                            attention_count=attention, caveats=caveats)


def daily_report(store: Any, *, now: datetime | None = None) -> OperationsReport:
    """The last day, with a week's horizon for dated work."""
    return build_operations_report(store, now=now, window_days=1, horizon_days=7)


def weekly_report(store: Any, *, now: datetime | None = None) -> OperationsReport:
    """The last seven days, with a fortnight's horizon for dated work."""
    return build_operations_report(store, now=now, window_days=7, horizon_days=14)
