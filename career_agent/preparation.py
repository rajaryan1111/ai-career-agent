"""What to do next: preparation items, interview rounds, and the one list that combines them.

An application is more than a status. Before sending one a person has things to do - tailor the résumé,
read up on the employer, get a reference letter - and after sending one there is usually a round to prepare
for, an answer to chase, or both. This module turns those records into the only question that actually
matters at a desk at nine in the morning: *what should I do today?*

Four rules shape it.

**Nothing here changes an application.** A preparation item being due, an interview being tomorrow, a
follow-up arriving - none of it moves :class:`~career_agent.core.ApplicationTracker.status`, writes an
activity entry, or decides that an employer did anything. The status moves only when the person moves it,
through the guarded transition path, with evidence. That is the same rule the activity log and the follow-up
day already follow, and it is what keeps the tracker an honest record rather than a guess.

**The day belongs to the caller.** Every comparison is made against a ``today`` the caller supplies, never
against this machine's clock inside a function, so a report is reproducible and no timezone is guessed. A
test does not depend on when it runs.

**An interview record is the candidate's own note.** Its outcome vocabulary is about how the person felt the
round went, and deliberately has no value that sounds like an employer's decision. The application cannot
know that, and offering a field for it would put words in an employer's mouth.

**Order is a decision, not an accident.** Actionable items come first (most overdue first), then today, then
what is coming; interviews sort before follow-ups, which sort before preparation, because an appointment is
on somebody else's clock, a chase is a promise, and preparation is your own to arrange. Within a group the
day, the listing id and the description break ties, so two runs over the same data print the same list.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Iterable, Mapping, Sequence

from .core import (
    InterviewOutcome, InterviewRound, JobListing, PreparationItem,
)
from .followups import DEFAULT_UPCOMING_DAYS, FollowUpReminder

#: How many days ahead counts as "coming up" when a report is produced. Shared with the follow-up module so
#: one number describes one window across the whole product.
UPCOMING_DAYS = DEFAULT_UPCOMING_DAYS

#: What is shown when a record outlives its listing. The store deletes these rows with their listing, so
#: this is a guard rather than an expected case - and hiding the row would drop something a person recorded.
_UNKNOWN_JOB = "(the listing is no longer stored)"


class Timing(str, Enum):
    """Where a dated record stands against the day it is being looked at."""

    OVERDUE = "overdue"
    TODAY = "today"
    SOON = "soon"
    LATER = "later"
    UNDATED = "undated"


class ActionKind(str, Enum):
    """The three things a person can have to do about an application."""

    INTERVIEW = "interview"
    FOLLOW_UP = "follow_up"
    PREPARATION = "preparation"


#: Lower sorts first. An appointment on somebody else's clock outranks a chase, which outranks your own
#: list - see the module docstring.
_KIND_ORDER = {ActionKind.INTERVIEW: 0, ActionKind.FOLLOW_UP: 1, ActionKind.PREPARATION: 2}
_TIMING_ORDER = {Timing.OVERDUE: 0, Timing.TODAY: 1, Timing.SOON: 2, Timing.LATER: 3, Timing.UNDATED: 4}

_TIMING_WORDS = {
    Timing.OVERDUE: "overdue",
    Timing.TODAY: "today",
    Timing.SOON: "coming up",
    Timing.LATER: "later",
    Timing.UNDATED: "no day",
}


def timing_for(day: date | None, today: date, *, upcoming_days: int = UPCOMING_DAYS) -> Timing:
    """Where ``day`` stands against ``today``: overdue, today, soon, later, or undated.

    ``None`` is its own answer rather than being treated as overdue. An item with no day is not late; it is
    something a person has not scheduled, and calling that overdue would train them to ignore the word.
    """
    if day is None:
        return Timing.UNDATED
    days = (day - today).days
    if days < 0:
        return Timing.OVERDUE
    if days == 0:
        return Timing.TODAY
    if days <= upcoming_days:
        return Timing.SOON
    return Timing.LATER


def open_items(items: Iterable[PreparationItem]) -> tuple[PreparationItem, ...]:
    """The preparation items still to do, earliest day first, then by title.

    Undated items come after the dated ones: a list that mixes "do this Thursday" with "do this eventually"
    in date order is how the dated ones get missed. Nothing is filtered out on age - an open item from three
    months ago is still open, and hiding it would be the application deciding a person's own list for them.
    """
    remaining = [item for item in items if not item.is_done]
    return tuple(sorted(remaining, key=lambda item: (item.due_on is None, item.due_on or date.max,
                                                    item.title, item.listing_id)))


def done_items(items: Iterable[PreparationItem]) -> tuple[PreparationItem, ...]:
    """The preparation items already ticked off, most recently finished first."""
    finished = [item for item in items if item.is_done]
    return tuple(sorted(finished, key=lambda item: (item.done_at or "", item.title), reverse=True))


def preparation_summary(items: Sequence[PreparationItem], today: date, *,
                        upcoming_days: int = UPCOMING_DAYS) -> str:
    """One line describing a list of preparation items, distinguishing "none" from "none due"."""
    remaining = open_items(items)
    if not remaining:
        if done_items(items):
            return "Every preparation item is done."
        return "No preparation items are recorded yet."
    overdue = sum(1 for item in remaining if timing_for(item.due_on, today, upcoming_days=upcoming_days) is Timing.OVERDUE)
    due_today = sum(1 for item in remaining if timing_for(item.due_on, today, upcoming_days=upcoming_days) is Timing.TODAY)
    undated = sum(1 for item in remaining if item.due_on is None)
    parts = [f"{len(remaining)} item(s) still to do"]
    if overdue:
        parts.append(f"{overdue} overdue")
    if due_today:
        parts.append(f"{due_today} due today")
    if undated:
        parts.append(f"{undated} with no day set")
    return ", ".join(parts) + "."


def rounds_ordered(rounds: Iterable[InterviewRound], today: date) -> tuple[InterviewRound, ...]:
    """Interview rounds with the next one to face first.

    Rounds still ahead come first, soonest first, because that is the one to prepare for - and a round
    planned for today is ahead, not past. Rounds whose day has gone by follow, most recent first, because
    the latest is the one a person is still thinking about. Ties break on the listing id so the order is
    stable.
    """
    upcoming = [item for item in rounds if item.is_ahead(today)]
    past = [item for item in rounds if item.is_past(today)]
    upcoming.sort(key=lambda item: (item.scheduled_on, item.listing_id, item.round_id or 0))
    past.sort(key=lambda item: (item.scheduled_on, item.listing_id, item.round_id or 0), reverse=True)
    return tuple(upcoming + past)


def interview_summary(rounds: Sequence[InterviewRound], today: date, *,
                      upcoming_days: int = UPCOMING_DAYS) -> str:
    """One line describing recorded rounds: what is next, and how many have happened."""
    if not rounds:
        return "No interview rounds are recorded yet."
    ahead = [item for item in rounds if item.is_ahead(today)]
    waiting = sum(1 for item in rounds
                  if item.outcome is InterviewOutcome.AWAITING and item.is_past(today))
    if not ahead:
        if waiting:
            return (f"No round ahead. {waiting} round(s) have happened without a note on how they went - "
                    "only you can say.")
        return f"No round ahead. {len(rounds)} round(s) recorded."
    nearest = min(ahead, key=lambda item: (item.scheduled_on, item.listing_id))
    days = nearest.days_away(today)
    when = "today" if days == 0 else ("tomorrow" if days == 1 else f"in {days} day(s)")
    soon = sum(1 for item in ahead if (item.scheduled_on - today).days <= upcoming_days)
    more = f" ({soon} rounds within {upcoming_days} days)" if soon > 1 else ""
    return f"Next: {nearest.stage_label} {when} on {nearest.scheduled_on.isoformat()}{more}."


@dataclass(frozen=True)
class Action:
    """One thing to do, with everything needed to recognise it in a list."""

    kind: ActionKind
    listing_id: str
    employer_name: str
    role_title: str
    what: str
    on: date | None = None
    timing: Timing = Timing.UNDATED
    days_away: int | None = None
    detail: str | None = None
    #: The row this came from - a preparation item's id or a round's id - so a caller can act on the
    #: record the line names instead of guessing which one it meant. ``None`` for a follow-up, which
    #: belongs to the application record itself.
    record_id: int | None = None

    @property
    def is_actionable(self) -> bool:
        """Whether this is for now: overdue or today."""
        return self.timing in (Timing.OVERDUE, Timing.TODAY)

    def describe(self) -> str:
        """One line: when, what, and which application it belongs to."""
        if self.on is None:
            when = "no day set"
        elif self.timing is Timing.OVERDUE:
            when = f"{self.on.isoformat()} ({abs(self.days_away or 0)} day(s) overdue)"
        elif self.timing is Timing.TODAY:
            when = f"{self.on.isoformat()} (today)"
        else:
            when = f"{self.on.isoformat()} (in {self.days_away} day(s))"
        detail = f" - {self.detail}" if self.detail else ""
        return f"{when}: {self.what}{detail} [{self.role_title} at {self.employer_name}]"


def actions(
    preparation: Sequence[PreparationItem], rounds: Sequence[InterviewRound],
    reminders: Sequence[FollowUpReminder], jobs: Mapping[str, JobListing], today: date, *,
    upcoming_days: int = UPCOMING_DAYS, include_later: bool = False, include_undated: bool = True,
) -> tuple[Action, ...]:
    """The combined to-do list across preparation, interviews and follow-ups.

    ``include_later`` and ``include_undated`` let a caller ask for just the actionable part (a daily
    reminder) or the whole picture (a report). Every input is passed in rather than read from the store, so
    the answer is a pure function of what the person has recorded and the day they are looking at it.
    """
    found: list[Action] = []

    def names(listing_id: str) -> tuple[str, str]:
        job = jobs.get(listing_id)
        if job is None:
            return (_UNKNOWN_JOB, listing_id)
        return (job.employer_name, job.role_title)

    for item in rounds:
        employer, role = names(item.listing_id)
        timing = timing_for(item.scheduled_on, today, upcoming_days=upcoming_days)
        # A round whose day has passed is still a thing to do - recording how it went, or carrying the
        # lesson into the next one - so it stays on the list as overdue rather than disappearing.
        found.append(Action(
            kind=ActionKind.INTERVIEW, listing_id=item.listing_id, employer_name=employer, role_title=role,
            what=f"{item.stage_label} ({item.mode_label})", on=item.scheduled_on, timing=timing,
            days_away=item.days_away(today), detail=item.notes, record_id=item.round_id,
        ))
    for item in open_items(preparation):
        employer, role = names(item.listing_id)
        timing = timing_for(item.due_on, today, upcoming_days=upcoming_days)
        found.append(Action(
            kind=ActionKind.PREPARATION, listing_id=item.listing_id, employer_name=employer,
            role_title=role, what=item.title, on=item.due_on, timing=timing,
            days_away=None if item.due_on is None else (item.due_on - today).days,
            detail=item.label, record_id=item.preparation_id,
        ))
    for reminder in reminders:
        timing = timing_for(reminder.on, today, upcoming_days=upcoming_days)
        found.append(Action(
            kind=ActionKind.FOLLOW_UP, listing_id=reminder.listing_id,
            employer_name=reminder.employer_name, role_title=reminder.role_title,
            what="Follow up on this application", on=reminder.on, timing=timing,
            days_away=reminder.days_away, detail=reminder.note,
        ))

    selected = [
        action for action in found
        if (include_later or action.timing is not Timing.LATER)
        and (include_undated or action.timing is not Timing.UNDATED)
    ]
    return tuple(sorted(
        selected,
        key=lambda action: (
            _TIMING_ORDER[action.timing],
            _KIND_ORDER[action.kind],
            action.on or date.max,
            action.listing_id,
            action.what,
        ),
    ))


def describe_actions(found: Sequence[Action], *, limit: int | None = None) -> tuple[str, ...]:
    """Turn actions into report lines, optionally capped, with the omitted count stated.

    A silent cap would make a long list look like a short one, so the last line always names what was left
    out - the same rule the run-detail limit follows.
    """
    shown = list(found) if limit is None else list(found[:limit])
    lines = [action.describe() for action in shown]
    if limit is not None and len(found) > limit:
        lines.append(f"...and {len(found) - limit} more, not listed here.")
    return tuple(lines)


def summary(found: Sequence[Action], today: date) -> str:
    """One line describing the combined list, distinguishing "nothing recorded" from "nothing due"."""
    if not found:
        return "Nothing is waiting on you: no follow-up day has arrived, no round is ahead and no preparation item is open."
    actionable = sum(1 for action in found if action.is_actionable)
    if not actionable:
        return f"Nothing is due yet; {len(found)} item(s) are coming up."
    overdue = sum(1 for action in found if action.timing is Timing.OVERDUE)
    due_today = actionable - overdue
    parts = []
    if overdue:
        parts.append(f"{overdue} overdue")
    if due_today:
        parts.append(f"{due_today} due today")
    return f"{actionable} item(s) need you now ({', '.join(parts)})."
