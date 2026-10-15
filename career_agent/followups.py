"""Follow-ups: the day a person plans to act on an application, and what to do with it.

An application that has been sent and not answered is the state most job hunts die in. This module is
about the smallest useful thing an application can do about that: remember the day the person said they
would chase it, tell them when that day arrives, and give them a file they can put in their own calendar.

Three rules shape it.

**A reminder is not a status.** Nothing here changes :class:`~career_agent.core.ApplicationTracker.status`,
writes an activity entry, or decides that an employer has or has not replied. Silence from an employer is
not evidence of anything; a person chasing a listing is not evidence either. The tracker's own state
machine is untouched.

**The day belongs to the person.** Everything is counted in whole days against a date the caller supplies
(``today``), not against this machine's clock inside a function - so a report is reproducible, a test does
not depend on when it runs, and nobody is told a reminder was "due today" because a server in another
zone thought so. The window's default is the local day; the command line takes the same day.

**Nothing is sent anywhere.** The calendar file is written to a path the person chooses, on this machine.
There is no email, no webhook, no calendar account: an integration that would need credentials the
project does not have is documented as unavailable rather than mocked into looking present
(see ``docs/` or ``memory.md`` for the integrations that remain unimplemented).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Iterable, Sequence

from .core import ApplicationStatus, ApplicationTracker, JobListing

#: How many days ahead count as "coming up" when a report is produced.
DEFAULT_UPCOMING_DAYS = 7

#: The calendar file's product identifier: what a calendar app shows as the origin of an event.
CALENDAR_PRODUCT_ID = "-//AI Career Agent//Local follow-up reminders//EN"

#: The longest line a calendar file may hold before it must be folded (RFC 5545: 75 octets, excluding
#: the line break). Folding is not cosmetic - a calendar application that cannot parse the file will
#: silently drop the event, which is worse than not offering the export at all.
MAX_CALENDAR_LINE_OCTETS = 75


class FollowUpState(str, Enum):
    """Where a recorded follow-up day stands today."""

    NONE = "none"            #: no day recorded
    OVERDUE = "overdue"      #: the day has passed
    DUE_TODAY = "due_today"  #: the day is today
    UPCOMING = "upcoming"    #: the day is in the future
    LATER = "later"          #: in the future but beyond the report's window


@dataclass(frozen=True)
class FollowUpReminder:
    """One application's follow-up, with everything a person needs to recognise it.

    The employer, role and status are copied from the stored listing and tracker rather than looked up
    later, so a report printed or exported today still reads correctly after the listing is edited.
    """

    listing_id: str
    on: date
    state: FollowUpState
    days_away: int
    employer_name: str
    role_title: str
    status: ApplicationStatus | None = None
    note: str | None = None

    def describe(self) -> str:
        """One line for a report: when, what, and where the application stands."""
        when = {
            FollowUpState.OVERDUE: f"{abs(self.days_away)} day(s) overdue",
            FollowUpState.DUE_TODAY: "due today",
            FollowUpState.UPCOMING: f"in {self.days_away} day(s)",
            FollowUpState.LATER: f"in {self.days_away} day(s)",
            FollowUpState.NONE: "no day recorded",
        }[self.state]
        status = f" [{self.status.value}]" if self.status is not None else ""
        note = f" - {self.note}" if self.note else ""
        return f"{self.on.isoformat()} ({when}): {self.role_title} at {self.employer_name}{status}{note}"

    @property
    def is_actionable(self) -> bool:
        """Whether the day has arrived (today or earlier): the ones a person should look at now."""
        return self.state in (FollowUpState.OVERDUE, FollowUpState.DUE_TODAY)


def state_for(follow_up_on: date | None, today: date, *, upcoming_days: int = DEFAULT_UPCOMING_DAYS) -> FollowUpState:
    """Which of the states a follow-up day is in, given the day it is being looked at."""
    if follow_up_on is None:
        return FollowUpState.NONE
    days = (follow_up_on - today).days
    if days < 0:
        return FollowUpState.OVERDUE
    if days == 0:
        return FollowUpState.DUE_TODAY
    if days <= upcoming_days:
        return FollowUpState.UPCOMING
    return FollowUpState.LATER


def reminder_for(tracker: ApplicationTracker, job: JobListing, today: date, *,
                 upcoming_days: int = DEFAULT_UPCOMING_DAYS) -> FollowUpReminder | None:
    """The reminder for one application, or ``None`` when no day is recorded.

    Undated applications are left out rather than listed with an empty date: a report that includes them
    would slowly become the whole tracker, and the point of the list is what to act on.
    """
    if tracker.follow_up_on is None:
        return None
    return FollowUpReminder(
        listing_id=tracker.listing_id,
        on=tracker.follow_up_on,
        state=state_for(tracker.follow_up_on, today, upcoming_days=upcoming_days),
        days_away=(tracker.follow_up_on - today).days,
        employer_name=job.employer_name,
        role_title=job.role_title,
        status=tracker.status,
        note=tracker.follow_up_note,
    )


def reminders(
    pairs: Iterable[tuple[ApplicationTracker, JobListing]], today: date, *,
    upcoming_days: int = DEFAULT_UPCOMING_DAYS, include_later: bool = True,
) -> tuple[FollowUpReminder, ...]:
    """Every recorded follow-up, ordered so the ones to act on come first.

    The order is overdue (most overdue first), then due today, then the near future, then the rest - and
    within a group the date and then the listing id break ties, so two runs over the same data produce the
    same list.
    """
    found: list[FollowUpReminder] = []
    for tracker, job in pairs:
        reminder = reminder_for(tracker, job, today, upcoming_days=upcoming_days)
        if reminder is None:
            continue
        if reminder.state is FollowUpState.LATER and not include_later:
            continue
        found.append(reminder)
    order = {
        FollowUpState.OVERDUE: 0, FollowUpState.DUE_TODAY: 1,
        FollowUpState.UPCOMING: 2, FollowUpState.LATER: 3, FollowUpState.NONE: 4,
    }
    return tuple(sorted(found, key=lambda item: (order[item.state], item.on, item.listing_id)))


def summary(upcoming: Sequence[FollowUpReminder]) -> str:
    """One line saying how many follow-ups need looking at, or that none do.

    "Nothing is due" and "you have no follow-ups at all" are different sentences on purpose: the first is
    a working reminder list, the second usually means the person has not recorded any days yet.
    """
    actionable = [item for item in upcoming if item.is_actionable]
    if not upcoming:
        return "No follow-ups are recorded. Set a day on an application to be reminded about it."
    if not actionable:
        return f"{len(upcoming)} follow-up(s) coming up; none are due yet."
    overdue = sum(1 for item in actionable if item.state is FollowUpState.OVERDUE)
    due_today = len(actionable) - overdue
    parts = []
    if overdue:
        parts.append(f"{overdue} overdue")
    if due_today:
        parts.append(f"{due_today} due today")
    return f"{', '.join(parts)}: {len(actionable)} application(s) need a look."


# ---------------------------------------------------------------------------- calendar export

def to_calendar(
    upcoming: Sequence[FollowUpReminder], *, now: datetime, product_id: str = CALENDAR_PRODUCT_ID,
) -> str:
    """The reminders as an iCalendar document, ready to be imported into the person's own calendar.

    Every event is an all-day entry on the follow-up date, with the employer, the role and the person's
    own note in it. Deliberately absent: attendees, organizers, alarms by email, and any URL - an event
    that invites somebody else or mails a server would be the beginning of telling other people about this
    job hunt, and nothing here does that. The ``UID`` is derived from the listing and the day, so
    re-exporting after editing an unrelated application updates one event instead of creating a duplicate.

    The document is written to a path the person chooses; this function only produces text.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("A calendar export needs the moment it was produced, with its timezone.")
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:" + product_id,
        "CALSCALE:GREGORIAN",
        # A method of PUBLISH with no organizer is a personal record, which is what this is: the person's
        # own reminder, produced on their own machine.
        "METHOD:PUBLISH",
    ]
    for reminder in upcoming:
        lines.extend(_events_for(reminder, stamp))
    lines.append("END:VCALENDAR")
    # Folding is applied once, to the completed line, and the file ends with a line break.
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def _events_for(reminder: FollowUpReminder, stamp: str) -> list[str]:
    """The calendar lines for one reminder: an all-day event on its day."""
    day = reminder.on.strftime("%Y%m%d")
    next_day = date.fromordinal(reminder.on.toordinal() + 1).strftime("%Y%m%d")
    description_parts = [
        f"{reminder.role_title} at {reminder.employer_name}",
        f"Application status recorded in this app: "
        f"{reminder.status.value if reminder.status is not None else 'unknown'}",
    ]
    if reminder.note:
        description_parts.append(reminder.note)
    description_parts.append(
        "Reminder created locally by AI Career Agent. It records a day you chose to follow up; it is "
        "not a statement from the employer."
    )
    return [
        "BEGIN:VEVENT",
        f"UID:follow-up-{reminder.listing_id}-{day}@ai-career-agent.local",
        f"DTSTAMP:{stamp}",
        # DTSTART is a DATE (not a DATE-TIME) because an all-day reminder has no invented time of day,
        # and DTEND is exclusive, the following day.
        f"DTSTART;VALUE=DATE:{day}",
        f"DTEND;VALUE=DATE:{next_day}",
        f"SUMMARY:{_escape('Follow up: ' + reminder.role_title + ' at ' + reminder.employer_name)}",
        f"DESCRIPTION:{_escape(chr(10).join(description_parts))}",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
    ]


def _escape(text: str) -> str:
    """Escape calendar text: backslash, the separators, and newlines (RFC 5545 §3.3.11)."""
    return (text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n"))


def _fold(line: str) -> str:
    """Fold a content line at 75 *octets*, continuing with a single leading space.

    Octets, not characters: a role title with an accent or a Devanagari character in it must not be cut
    through the middle of a multi-byte sequence, which is what folding by character count can do.
    """
    encoded = line.encode("utf-8")
    if len(encoded) <= MAX_CALENDAR_LINE_OCTETS:
        return line
    pieces: list[str] = []
    remaining = encoded
    limit = MAX_CALENDAR_LINE_OCTETS
    while len(remaining) > limit:
        cut = limit
        # Do not split a multi-byte character: step back to a boundary, then re-check the byte budget.
        while cut > 0 and (remaining[cut] & 0xC0) == 0x80:
            cut -= 1
        if cut == 0:  # pragma: no cover - a single character longer than the fold width
            cut = limit
        pieces.append(remaining[:cut].decode("utf-8", errors="strict"))
        remaining = remaining[cut:]
        limit = MAX_CALENDAR_LINE_OCTETS - 1  # the continuation line carries a leading space
    pieces.append(remaining.decode("utf-8", errors="strict"))
    return "\r\n ".join(pieces)


def calendar_file_name(today: date) -> str:
    """The suggested name for an export made on ``today``."""
    return f"career-agent-follow-ups-{today.strftime('%Y%m%d')}.ics"
