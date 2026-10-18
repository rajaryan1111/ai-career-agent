"""Attempts with uncertain outcomes: write before acting, and never retry blind.

An application sent, an email dispatched, a submission posted - each is an act with a consequence
somebody else sees, and each can end in a state this machine cannot resolve on its own. A request that
timed out may have arrived. A connection dropped after the provider accepted it looks exactly like one
dropped before. The usual shortcut is to call that a failure and try again, and the usual result is a
second application to the same job.

So this module records three things and refuses one:

* an attempt is written **before** the act, in the state :attr:`AttemptState.UNKNOWN`, so a crash
  between the write and the act leaves evidence rather than silence;
* an outcome is written only from what was observed - ``PERFORMED`` when the act completed,
  ``REFUSED`` when nothing was attempted at all, ``FAILED`` only when it is *known* nothing happened;
* an attempt that ends ambiguously **stays** ``UNKNOWN``, and an unknown attempt blocks every further
  attempt at the same job and action until a person reconciles it with evidence.

Time does not resolve anything here. An attempt that has been unknown for a week is still unknown; it
is merely *older*, and :func:`attempts_needing_reconciliation` lists it so somebody can go and look.
Nothing in this module performs anything or contacts anything.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Sequence


class AttemptError(ValueError):
    """An attempt record is being asked for something it cannot honestly represent."""


class AttemptState(str, Enum):
    """What is known about one attempt - not what is hoped about it."""

    UNKNOWN = "unknown"      #: started, and the outcome was never established. Blocks retries.
    PERFORMED = "performed"  #: it happened, and this attempt is what made it happen
    FAILED = "failed"        #: it is known that nothing happened; a further attempt is allowed
    REFUSED = "refused"      #: nothing was attempted (a gate, an authorisation, an invalid request)


#: The states a retry may follow. ``UNKNOWN`` and ``PERFORMED`` are deliberately absent.
RETRYABLE_STATES = (AttemptState.FAILED, AttemptState.REFUSED)

#: How long an unknown attempt may sit before it is reported as needing a person's attention. It is a
#: reporting threshold only: nothing about the attempt changes when it passes.
DEFAULT_STALE_AFTER = timedelta(hours=6)


@dataclass(frozen=True)
class AttemptRecord:
    """One attempt at one action against one job identity, as stored.

    ``identity_key`` is the cross-source job identity from :mod:`career_agent.identity`, not a listing
    id: the point of recording it this way is that the same job found on two sources cannot be applied
    to twice.
    """

    operation_id: str
    identity_key: str
    action: str
    state: AttemptState
    started_at: str
    settled_at: str | None = None
    detail: str = ""
    evidence: str = ""

    def __post_init__(self) -> None:
        for name in ("operation_id", "identity_key", "action", "started_at"):
            if not str(getattr(self, name) or "").strip():
                raise AttemptError(f"An attempt record needs a {name.replace('_', ' ')}.")
        if not isinstance(self.state, AttemptState):
            raise AttemptError(f"An attempt state must be an AttemptState, not {self.state!r}.")
        if self.state is AttemptState.UNKNOWN and self.settled_at:
            raise AttemptError("An unknown attempt has no settled time; that is what unknown means.")
        if self.state is not AttemptState.UNKNOWN and not self.settled_at:
            raise AttemptError(f"An attempt recorded as {self.state.value} must say when it settled.")

    @property
    def is_unresolved(self) -> bool:
        return self.state is AttemptState.UNKNOWN

    def describe(self) -> str:
        if self.state is AttemptState.UNKNOWN:
            return (f"{self.action} for {self.identity_key} was started at {self.started_at} and its "
                    f"outcome was never established")
        return (f"{self.action} for {self.identity_key} is recorded as {self.state.value} at "
                f"{self.settled_at}")


@dataclass(frozen=True)
class RetryDecision:
    """Whether another attempt may be made, and every reason it may not."""

    allowed: bool
    identity_key: str
    action: str
    reasons: tuple[str, ...] = ()
    blocking_operation_ids: tuple[str, ...] = ()

    def describe(self) -> str:
        if self.allowed:
            return f"Another {self.action} for {self.identity_key} is allowed by the record so far."
        return (f"Refused another {self.action} for {self.identity_key}: "
                + "; ".join(self.reasons) + ".")


def _require_action(action: str) -> str:
    cleaned = str(action or "").strip()
    if not cleaned:
        raise AttemptError("An attempt needs the name of the action it is an attempt at.")
    return cleaned


def _require_moment(now: datetime) -> datetime:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise AttemptError("A moment used to judge an attempt must carry its timezone.")
    return now.astimezone(timezone.utc)


def may_attempt(records: Sequence[AttemptRecord], *, identity_key: str, action: str) -> RetryDecision:
    """Whether to attempt this action for this job identity, given everything already recorded.

    Three ways to be refused, and they are reported together rather than one at a time:

    * an unknown attempt exists - it may already have happened, so a retry would be blind;
    * it has already been performed - a second one is not a retry, it is a duplicate;
    * the identity or the action is blank, which is a programming error and raises instead.
    """
    identity = str(identity_key or "").strip()
    if not identity:
        raise AttemptError("An attempt is judged against a job identity; none was given.")
    name = _require_action(action)
    relevant = [record for record in records
                if record.identity_key == identity and record.action == name]
    unresolved = [record for record in relevant if record.state is AttemptState.UNKNOWN]
    performed = [record for record in relevant if record.state is AttemptState.PERFORMED]
    reasons: list[str] = []
    if unresolved:
        reasons.append(
            f"{len(unresolved)} earlier attempt(s) ended without an established outcome, so another "
            f"one could repeat something that already happened; reconcile "
            f"{', '.join(record.operation_id for record in unresolved)} first")
    if performed:
        reasons.append(
            f"it was already performed ({', '.join(record.operation_id for record in performed)}), "
            f"and a second one would be a duplicate rather than a retry")
    return RetryDecision(
        allowed=not reasons, identity_key=identity, action=name, reasons=tuple(reasons),
        blocking_operation_ids=tuple(record.operation_id
                                     for record in unresolved + performed))


def state_from_outcome(outcome_value: str, *, performed: bool) -> AttemptState:
    """Translate an integration's outcome into what is actually known about the attempt.

    The one that matters is ``failed``: a failed dispatch is *not* proof that nothing happened - the
    request may have arrived and the acknowledgement may have been lost - so it becomes ``UNKNOWN``
    and blocks further attempts until somebody checks. ``disabled``, ``invalid`` and ``unsupported``
    mean nothing was attempted, which is knowledge, so they settle as ``REFUSED``.
    """
    value = str(outcome_value or "").strip().casefold()
    if performed or value in ("completed", "duplicate"):
        return AttemptState.PERFORMED
    if value in ("disabled", "invalid", "unsupported"):
        return AttemptState.REFUSED
    if value == "failed":
        return AttemptState.UNKNOWN
    raise AttemptError(
        f"{outcome_value!r} is not an outcome this application knows how to record, and guessing "
        f"would be the one mistake this module exists to prevent.")


def attempts_needing_reconciliation(
    records: Sequence[AttemptRecord], *, now: datetime, stale_after: timedelta = DEFAULT_STALE_AFTER,
) -> tuple[AttemptRecord, ...]:
    """Unknown attempts old enough that somebody should go and look. Changes nothing.

    Age is a reporting threshold, never a resolution: this function does not settle an attempt, and
    nothing else may settle one on the strength of its age either.
    """
    moment = _require_moment(now)
    if stale_after < timedelta(0):
        raise AttemptError("An age threshold cannot be negative.")
    stale: list[AttemptRecord] = []
    for record in records:
        if not record.is_unresolved:
            continue
        try:
            started = datetime.fromisoformat(record.started_at)
        except ValueError as exc:
            raise AttemptError(
                f"The attempt {record.operation_id} has an unreadable start time; it cannot be "
                f"judged stale or fresh.") from exc
        if started.tzinfo is None:
            raise AttemptError(
                f"The attempt {record.operation_id} recorded a start time without a timezone.")
        if moment - started.astimezone(timezone.utc) >= stale_after:
            stale.append(record)
    return tuple(stale)


def reconciliation_summary(records: Sequence[AttemptRecord]) -> str:
    """One line about what is settled and what is not. Counts only - no employer, no address."""
    if not records:
        return "No attempt has been recorded."
    counted = {state: 0 for state in AttemptState}
    for record in records:
        counted[record.state] += 1
    unknown = counted[AttemptState.UNKNOWN]
    line = (f"{len(records)} attempt(s) recorded: {counted[AttemptState.PERFORMED]} performed, "
            f"{counted[AttemptState.FAILED]} known not to have happened, "
            f"{counted[AttemptState.REFUSED]} refused before anything was tried")
    if unknown:
        return (line + f", and {unknown} whose outcome is unknown. Those {unknown} block further "
                "attempts at the same job and action until you establish what happened.")
    return line + ". Nothing is unresolved."
