"""The one standing authorisation, checked immediately before anything leaves this machine.

P8 asks for a global policy a person gives **once** and can revoke: which source may be used for
which action, how many of each may run in a day, when the application must stay quiet, and a way to
stop everything at once. This module is that policy and the decision made from it. Three rules shape
everything here:

* **It authorises, it never enables.** A policy is one half of a conjunction; the other half is the
  source's own permission and quality gate (:mod:`career_agent.sources`), which is closed today. A
  decision is *allowed* only when both say so, so a policy that names every source and every action
  still opens nothing. The composition is the caller's: it passes the gate's answer in, and this
  module refuses outright if that answer is no.
* **It fails closed, and it says why.** Anything not named is refused: an unknown source, an action
  the policy does not list, an action with no recorded daily limit, a clock without a timezone. A
  refusal carries every reason, not the first one found, because a person fixing one condition
  should not discover the next one by trying again.
* **It performs nothing.** There is no network, no mail, no process and no database here - only a
  value and a decision about it. What a caller does with the decision is the caller's business, and
  where the policy is stored is the store's.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Mapping


class PolicyError(ValueError):
    """A policy, or a question asked of one, that this application refuses to interpret."""


class ActionKind(str, Enum):
    """The external actions this application can be authorised to take.

    One member per independently gated capability in the roadmap, so an authorisation for one can
    never read as an authorisation for another: reading job listings is not submitting an
    application, and sending an email is not reading a mailbox.
    """

    DISCOVERY = "discovery"
    SUBMISSION = "submission"
    EMAIL_SEND = "email_send"
    INBOX_READ = "inbox_read"


#: How each action reads in a sentence meant for a person.
ACTION_LABELS: dict[ActionKind, str] = {
    ActionKind.DISCOVERY: "look for jobs",
    ActionKind.SUBMISSION: "submit an application",
    ActionKind.EMAIL_SEND: "send an email",
    ActionKind.INBOX_READ: "read your mailbox",
}


def _as_action(value: object) -> ActionKind:
    """``value`` as a known action, or a refusal naming what was asked for."""
    if isinstance(value, ActionKind):
        return value
    try:
        return ActionKind(value)  # type: ignore[arg-type]
    except (ValueError, TypeError) as exc:
        raise PolicyError(
            f"{value!r} is not an action this application can be authorised to take; the actions are "
            f"{', '.join(kind.value for kind in ActionKind)}") from exc


@dataclass(frozen=True)
class GlobalPolicy:
    """What the person has standing-authorised, as one value.

    ``allowed`` holds ``(source_id, action)`` pairs - the pair is the unit, because "this board, for
    looking only" is a different permission from "this board, for applying". ``daily_limits`` is per
    action and is **required** for any action that is allowed: an authorisation without a ceiling is
    how an automated system runs away with somebody's name on it. ``quiet_hours`` is a pair of local
    hours ``(from, until)`` and may wrap past midnight. ``stop_all`` and ``revoked_at`` are the two
    ways to switch everything off, and both are checked before anything else.
    """

    allowed: frozenset[tuple[str, ActionKind]] = field(default_factory=frozenset)
    daily_limits: Mapping[ActionKind, int] = field(default_factory=dict)
    quiet_hours: tuple[int, int] | None = None
    stop_all: bool = False
    revoked_at: str | None = None

    def __post_init__(self) -> None:
        pairs: set[tuple[str, ActionKind]] = set()
        for pair in self.allowed:
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise PolicyError(
                    "an authorisation is a (source, action) pair: a source on its own authorises "
                    "nothing, because reading and applying are different permissions")
            source_id, action = pair
            if not isinstance(source_id, str) or not source_id.strip():
                raise PolicyError("an authorisation names the source it is for")
            pairs.add((source_id, _as_action(action)))
        object.__setattr__(self, "allowed", frozenset(pairs))

        limits: dict[ActionKind, int] = {}
        for action, limit in dict(self.daily_limits).items():
            kind = _as_action(action)
            if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
                raise PolicyError(
                    f"the daily limit for {kind.value} must be a whole number of actions, not "
                    f"{limit!r}")
            limits[kind] = limit
        object.__setattr__(self, "daily_limits", limits)

        if self.quiet_hours is not None:
            hours = tuple(self.quiet_hours)
            if len(hours) != 2:
                raise PolicyError("quiet hours are a pair of hours, from and until")
            for hour in hours:
                if isinstance(hour, bool) or not isinstance(hour, int) or not 0 <= hour <= 23:
                    raise PolicyError(f"{hour!r} is not an hour of the day (0-23)")
            if hours[0] == hours[1]:
                # "From 9 until 9" is either no quiet hours or every hour of the day, and guessing
                # which one somebody meant is exactly the kind of guess this module does not make.
                raise PolicyError(
                    "quiet hours that start and end at the same hour say nothing; leave them unset "
                    "for none, or name the two hours")
            object.__setattr__(self, "quiet_hours", (int(hours[0]), int(hours[1])))

        if self.revoked_at is not None and not str(self.revoked_at).strip():
            raise PolicyError("a revoked policy records when it was revoked")

    @property
    def is_empty(self) -> bool:
        """Whether this policy authorises nothing at all."""
        return not self.allowed

    def authorises(self, source_id: str, action: object) -> bool:
        """Whether this policy names this exact ``(source, action)`` pair. Not a decision on its own."""
        return (source_id, _as_action(action)) in self.allowed


def no_authorisation() -> GlobalPolicy:
    """The policy a person has not given yet: nothing is authorised. The starting state, always."""
    return GlobalPolicy()


@dataclass(frozen=True)
class PolicyDecision:
    """Whether one action may run now, and every reason it may not.

    ``refusals`` is empty exactly when ``allowed`` is true. It carries *all* the reasons rather than
    the first: somebody who turns off quiet hours should be told in the same breath that the daily
    limit is also reached, instead of finding out by trying again an hour later.
    """

    allowed: bool
    source_id: str
    action: ActionKind
    refusals: tuple[str, ...] = ()

    def describe(self) -> str:
        """One line for a person or a log. Carries ids and reasons only - never candidate data."""
        what = f"{ACTION_LABELS[self.action]} ({self.action.value}) with '{self.source_id}'"
        if self.allowed:
            return (f"Permission to {what} is authorised: the standing policy allows it, the source's "
                    "own gate is open, it is not quiet hours and today's limit is not reached.")
        return f"Refused permission to {what}: " + "; ".join(self.refusals)


def _in_quiet_hours(moment: datetime, quiet_hours: tuple[int, int]) -> bool:
    """Whether ``moment`` falls inside quiet hours, including a pair that wraps past midnight."""
    start, until = quiet_hours
    hour = moment.hour
    if start < until:
        return start <= hour < until
    return hour >= start or hour < until


def evaluate_policy(policy: GlobalPolicy, *, source_id: str, action: object, now: datetime,
                    done_today: int, source_gate_allows: bool) -> PolicyDecision:
    """Decide whether one external action may run **now**, failing closed on anything unnamed.

    ``source_gate_allows`` is the answer from the source's own permission and quality gate
    (:func:`career_agent.sources.discovery_gate` or :func:`~career_agent.sources.submission_gate`,
    or the equivalent authorisation for mail). It is passed in rather than read here so that this
    module cannot be the place where a gate is accidentally bypassed, and a ``False`` refuses the
    action whatever the policy says. ``done_today`` is what the caller has counted from durable
    records - this module counts nothing and remembers nothing between calls.
    """
    kind = _as_action(action)
    if not isinstance(source_id, str) or not source_id.strip():
        raise PolicyError("a decision is about a named source")
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise PolicyError(
            "a decision needs an instant that knows its own zone: quiet hours on a clock with no "
            "zone would be somebody else's quiet hours")
    if isinstance(done_today, bool) or not isinstance(done_today, int) or done_today < 0:
        raise PolicyError(
            f"how many of these already ran today is a whole number from the records, not {done_today!r}")

    refusals: list[str] = []
    if policy.revoked_at:
        refusals.append(f"the standing authorisation was revoked at {policy.revoked_at}")
    if policy.stop_all:
        refusals.append("everything is stopped by the standing policy's stop switch")
    if policy.is_empty:
        refusals.append("there is no standing authorisation for anything yet")
    elif not policy.authorises(source_id, kind):
        refusals.append(
            f"the standing authorisation does not cover '{source_id}' for {ACTION_LABELS[kind]} "
            f"({kind.value})")
    if not source_gate_allows:
        refusals.append(
            f"the source's own gate for '{source_id}' is closed, and a standing authorisation "
            "cannot open it")
    if policy.quiet_hours is not None and _in_quiet_hours(now, policy.quiet_hours):
        start, until = policy.quiet_hours
        refusals.append(f"it is quiet hours ({start:02d}:00 until {until:02d}:00)")
    limit = policy.daily_limits.get(kind)
    if limit is None:
        refusals.append(
            f"no daily limit is recorded for {ACTION_LABELS[kind]} ({kind.value}), and an "
            "authorisation without a ceiling is not one this application will act on")
    elif done_today >= limit:
        refusals.append(
            f"today's limit of {limit} for {ACTION_LABELS[kind]} ({kind.value}) is already reached "
            f"({done_today} so far)")
    return PolicyDecision(allowed=not refusals, source_id=source_id, action=kind,
                          refusals=tuple(refusals))
