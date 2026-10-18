"""When this application may tell you something, and the ways it honestly can.

A notification is an interruption somebody did not ask for at that moment, so the defaults here are
the quiet ones: nothing is delivered until a person chooses a cadence, nothing is delivered during
their quiet hours, and nothing is delivered twice for the same period. There is also a limit worth
stating rather than hiding: **this build cannot reach you anywhere you are not already looking.** No
email is sent, no push is registered, no system notification is raised. The two channels are "shown
in the window the next time you open it" and "written to a file on this machine", and a preference
for anything else is refused rather than silently downgraded.

Nothing in this module performs a delivery, schedules one, or contacts anything. It decides, and the
caller that already has a report in its hands does the rest.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class NotificationError(ValueError):
    """A notification preference cannot mean what it is being asked to mean."""


class Cadence(str, Enum):
    """How often a person wants to be told. ``OFF`` is the default and is not a failure state."""

    OFF = "off"
    DAILY = "daily"
    WEEKLY = "weekly"


class DeliveryChannel(str, Enum):
    """Where a notification may appear. Both of these are places the person already controls."""

    IN_APP = "in_app"  #: shown in the window the next time it is opened
    FILE = "file"      #: written to a file on this machine, which the person may point anywhere


#: What each channel can and cannot do, in the words the window shows.
CHANNEL_LIMITS = {
    DeliveryChannel.IN_APP: ("shown in this window the next time you open it; nothing is sent "
                             "anywhere and nothing appears while the window is closed"),
    DeliveryChannel.FILE: ("written to a file on this machine; nothing is uploaded, and a file in a "
                           "synced folder is as private as that folder"),
}


@dataclass(frozen=True)
class NotificationPreferences:
    """What a person has asked to be told, and when. Frozen: a change is a new value."""

    cadence: Cadence = Cadence.OFF
    #: The local hour (0-23) at or after which the period's notification may be prepared.
    hour: int = 9
    channel: DeliveryChannel = DeliveryChannel.IN_APP
    #: When true, a period with nothing needing the person is passed over in silence.
    only_when_attention: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.cadence, Cadence):
            raise NotificationError(f"{self.cadence!r} is not a cadence this application offers.")
        if not isinstance(self.channel, DeliveryChannel):
            raise NotificationError(f"{self.channel!r} is not a delivery this application can do.")
        if not isinstance(self.hour, int) or isinstance(self.hour, bool):
            raise NotificationError("The hour of a notification is a whole number from 0 to 23.")
        if not 0 <= self.hour <= 23:
            raise NotificationError(
                f"{self.hour} is not an hour of the day; a notification hour is 0 to 23.")

    @property
    def is_off(self) -> bool:
        return self.cadence is Cadence.OFF

    def describe(self) -> str:
        if self.is_off:
            return "No notification is prepared; the report is there when you ask for it."
        when = "every day" if self.cadence is Cadence.DAILY else "once a week"
        only = (" only when something needs you" if self.only_when_attention
                else ", whether or not anything needs you")
        return (f"A report is prepared {when} from {self.hour:02d}:00{only}, and "
                f"{CHANNEL_LIMITS[self.channel]}.")


@dataclass(frozen=True)
class NotificationDecision:
    """Whether to prepare a notification now, and every reason not to."""

    deliver: bool
    reasons: tuple[str, ...] = ()

    def describe(self) -> str:
        if self.deliver:
            return "A report is due now."
        return "No report is due: " + "; ".join(self.reasons) + "."


def _aware(moment: datetime, *, noun: str) -> datetime:
    if not isinstance(moment, datetime) or moment.tzinfo is None or moment.utcoffset() is None:
        raise NotificationError(f"{noun} must carry its timezone.")
    return moment


def _in_quiet_hours(moment: datetime, quiet_hours: tuple[int, int] | None) -> bool:
    """Whether ``moment`` falls inside a quiet window, which may wrap past midnight."""
    if not quiet_hours:
        return False
    start, end = quiet_hours
    hour = moment.hour
    if start == end:
        raise NotificationError(
            "Quiet hours that start and end at the same hour say nothing; use no quiet hours, or a "
            "window with two different hours.")
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def _period_key(moment: datetime, cadence: Cadence) -> str:
    if cadence is Cadence.WEEKLY:
        year, week, _day = moment.isocalendar()
        return f"{year}-W{week:02d}"
    return moment.date().isoformat()


def notification_due(
    preferences: NotificationPreferences, *, now: datetime, last_delivered_at: datetime | None,
    quiet_hours: tuple[int, int] | None = None, attention_count: int = 0,
    stopped: bool = False,
) -> NotificationDecision:
    """Whether a report should be prepared at ``now``, given what was last delivered.

    Every refusal is reported, not just the first, because a person asking "why did I not get it?"
    deserves the whole answer. The order of the checks is not the order of the reasons: they are all
    evaluated.

    ``stopped`` is the standing authorisation's stop switch. It silences notifications too - a person
    who has stopped everything has said they do not want this application acting, and preparing a
    report under their nose is still acting.
    """
    if not isinstance(preferences, NotificationPreferences):
        raise NotificationError("A notification decision needs the person's own preferences.")
    moment = _aware(now, noun="The moment a notification is judged at")
    if last_delivered_at is not None:
        _aware(last_delivered_at, noun="The time of the last notification")
    reasons: list[str] = []
    if preferences.is_off:
        reasons.append("you have not asked for one")
    if stopped:
        reasons.append("everything is stopped")
    if _in_quiet_hours(moment, quiet_hours):
        start, end = quiet_hours  # type: ignore[misc]
        reasons.append(f"it is inside your quiet hours ({start:02d}:00-{end:02d}:00)")
    if moment.hour < preferences.hour and not preferences.is_off:
        reasons.append(f"it is before {preferences.hour:02d}:00")
    if last_delivered_at is not None and not preferences.is_off:
        if _period_key(last_delivered_at, preferences.cadence) == _period_key(
                moment, preferences.cadence):
            reasons.append("one has already been prepared for this period")
    if preferences.only_when_attention and attention_count == 0 and not preferences.is_off:
        reasons.append("nothing in the records needs you")
    return NotificationDecision(deliver=not reasons, reasons=tuple(reasons))


def preferences_payload(preferences: NotificationPreferences) -> str:
    """The preferences as the text stored in one row. Key-sorted, so a rewrite is comparable."""
    if not isinstance(preferences, NotificationPreferences):
        raise NotificationError("Only notification preferences can be stored as preferences.")
    return json.dumps({
        "cadence": preferences.cadence.value,
        "channel": preferences.channel.value,
        "hour": preferences.hour,
        "only_when_attention": preferences.only_when_attention,
    }, sort_keys=True)


def preferences_from_payload(payload: str) -> NotificationPreferences:
    """Read stored preferences, refusing anything that is not exactly what was written.

    A damaged row is never read as "notify freely": it raises, and the caller reports it. The quiet
    default would be tempting here, but silently replacing somebody's choice with a default is how an
    application ends up telling them something at three in the morning.
    """
    try:
        content = json.loads(payload)
    except (TypeError, ValueError) as exc:
        raise NotificationError(f"the stored notification preferences are not readable: {exc}") from exc
    if not isinstance(content, dict):
        raise NotificationError("the stored notification preferences are not a record of choices")
    known = {"cadence", "channel", "hour", "only_when_attention"}
    unknown = sorted(set(content) - known)
    if unknown:
        raise NotificationError(
            f"the stored notification preferences carry {', '.join(unknown)}, which this build does "
            f"not know how to honour")
    try:
        return NotificationPreferences(
            cadence=Cadence(content.get("cadence", Cadence.OFF.value)),
            hour=content.get("hour", 9),
            channel=DeliveryChannel(content.get("channel", DeliveryChannel.IN_APP.value)),
            only_when_attention=bool(content.get("only_when_attention", True)),
        )
    except ValueError as exc:
        raise NotificationError(f"the stored notification preferences cannot be read: {exc}") from exc
