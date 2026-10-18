"""Email and calendar integrations: the shape one must have, and why none of them is switched on.

A job-hunt tool eventually wants to do two things outside its own database: write to somebody, and put a
date in a calendar. Both are irreversible in the way that matters - an email cannot be unsent, and an
invitation cannot be uninvited - so this module is written around the separation that makes them safe to
build before they are safe to enable:

    **A draft is not an action, and a preview is not an action either.**
    :class:`EmailDraft` and :class:`CalendarEventRequest` are values that describe what *would* happen.
    :func:`preview_email` and :func:`preview_event` turn one into the text a person would read. Neither has
    a side effect of any kind, and neither can be turned into a side effect by a flag: execution goes through
    an :class:`Integration`, and the integration this application returns by default is
    :class:`DisabledIntegration`, which refuses everything and does nothing.

    **Nothing reaches the network, and this module could not if it tried.** There is no provider account, no
    credential, and no HTTP or SMTP client here - and the project's own local-first check
    (``tests/test_local_only.py``) fails the build if a shipped module imports ``smtplib``, ``http.client``,
    ``urllib.request`` or anything else whose purpose is remote communication. :class:`LocalMockIntegration`
    exists for deterministic tests and for a person who wants to watch the whole
    draft/preview/dispatch/deduplicate sequence run on their own machine; it records operations in a ledger
    (in memory, or in a local owner-only file) and contacts nothing.

    **Doing it twice must not mean doing it twice.** Every request carries a stable ``operation_id`` derived
    from its own content, so asking again produces the same identity. An integration that has performed an
    operation refuses to perform it again and reports :attr:`Outcome.DUPLICATE` with the time it was first
    done; a retry after a genuine failure is allowed, because the key is resubmitted with it.

    **A refusal is a result, not an error.** Execution returns an :class:`IntegrationResult` whose outcome is
    one of completed, duplicate, failed, disabled, unsupported or invalid - and ``performed`` distinguishes
    "something happened because of this call" from "nothing did". No caller of this module is ever told a
    message was sent when it was not: the words "sent" and "created" do not appear in a successful result
    unless an integration actually performed the operation, and the only integration that does anything at
    all is the local mock, whose messages say exactly where the record went.

    **Missing facts are reported, never filled in.** Nothing here derives a recipient address from an
    employer's name, guesses a time of day for an interview, or assumes a timezone. A draft without a
    recipient is a valid draft with one missing fact, and :func:`preview_email` prints it as missing rather
    than producing something that looks ready to send.

What would have to be true before a real provider could be enabled is written down in
:data:`ENABLEMENT_REQUIREMENTS` and printed by ``python -m career_agent --integration-status``, so the
answer to "why can I not connect my mail account?" is available in the product rather than in a commit
message.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Mapping, Protocol, Sequence, runtime_checkable

from .attempts import AttemptError, AttemptState, may_attempt, state_from_outcome
from .followups import FollowUpReminder, event_summary, event_uid
from .policy import (
    ActionKind, GlobalPolicy, PolicyError, PolicySubject, evaluate_policy, no_authorisation,
)
from .store import write_private_text_file

#: The longest a subject line may be. Long enough for a real subject, short enough to stay a subject.
MAX_SUBJECT_LENGTH = 200

#: The longest a message body may be. Deliberately modest: this application does not compose essays, and a
#: bound keeps a pasted document from becoming an "email draft" nobody reads before sending.
MAX_BODY_LENGTH = 5000

#: The longest an event title may be.
MAX_TITLE_LENGTH = 200

#: Bounds for a timed event, if a person records one from an invitation they read. Under five minutes is a
#: typo; over eight hours is a day, and a day belongs in the calendar as an all-day entry instead.
MIN_DURATION_MINUTES = 5
MAX_DURATION_MINUTES = 8 * 60

#: The ledger file's format version, so a file written by a later build is refused rather than half-read.
LEDGER_VERSION = 1

#: How many times :func:`dispatch_with_retry` may attempt one operation. Two: a retry exists for a transient
#: failure, not for hammering a provider that is down.
DEFAULT_MAX_ATTEMPTS = 2

#: Largest ledger file this module will read. The ledger answers "has this already been performed?", so a
#: file that cannot be read means the application cannot establish that and must perform nothing - the
#: bound keeps a mistyped path from being loaded into memory *and* keeps that refusal fail-closed. A
#: ledger this application writes holds a handful of operations; 16 MB is far past any real one.
MAX_LEDGER_BYTES = 16 * 1024 * 1024

#: The purpose a draft generated from an application's follow-up day carries. A constant rather than a bare
#: string so the surfaces that build drafts agree on it.
PURPOSE_FOLLOW_UP = "follow-up"

#: The default explanation a refused operation carries. It names the reason *and* what to do instead, because
#: "not supported" on its own leaves a person hunting for a setting that does not exist.
DEFAULT_DISABLED_REASON = (
    "No email or calendar integration is enabled in this build, and this application has no provider account, "
    "credential or authorization to use one. Nothing was sent and nothing was created. What is available "
    "instead: the follow-up calendar export writes a local .ics file you can import into your own calendar, "
    "and a draft can be written, previewed and copied out of the window by hand."
)

#: What has to be true before a real provider could be enabled. Data rather than prose in a docstring, so the
#: status command prints the same list a reviewer reads, and a test can assert it is still there.
ENABLEMENT_REQUIREMENTS: tuple[tuple[str, str], ...] = (
    ("An approved provider and scope",
     "one named provider, the exact API and permission scope, and a written decision that using it is "
     "permitted - not a library that happens to be installed."),
    ("Credentials in the operating system's own store",
     "a token or app password kept in the OS keyring rather than in the database, a settings file or an "
     "environment variable, with a documented way to revoke it."),
    ("Provider-side idempotency",
     "the provider must accept the operation id and refuse a repeat, because a client cannot prove that a "
     "request it did not see answered never arrived. Without that, the honest answer is that the operation "
     "is unknown, and this application will not guess."),
    ("A data-minimization statement",
     "exactly which fields leave the machine (recipient, subject, body, or an event's title and time), what "
     "is logged, how long it is kept, and what is never sent - written before the first request."),
    ("An off-by-default switch with a visible state",
     "enabling it is an explicit act a person performs and can undo, the state is visible in the window, and "
     "every enabled integration can be described in one sentence to whoever is using the machine."),
    ("Failure handling that cannot lie",
     "a timeout, a refusal and a partial failure each produce a distinct result, a retry never duplicates a "
     "side effect, and a failure is never reported as a success."),
    ("A real test path",
     "provider-level tests against a sandbox or a recorded contract, not only a local mock - the mock proves "
     "this module's bookkeeping, not that a provider behaves as documented."),
)


class OperationKind(str, Enum):
    """The two kinds of operation an integration can be asked to perform."""

    EMAIL = "email"
    CALENDAR = "calendar"


class Outcome(str, Enum):
    """What happened when an operation was requested.

    Five of the six are refusals or failures of one kind or another, and they are deliberately distinct: a
    caller must be able to tell "the person has not enabled this" from "the request was wrong" from "the
    provider was down", because the three lead to different next steps.
    """

    COMPLETED = "completed"      #: the operation was performed, and this call is what performed it
    DUPLICATE = "duplicate"      #: it had already been performed; nothing was done again
    FAILED = "failed"            #: an attempt was made and did not complete; a retry is allowed
    DISABLED = "disabled"        #: no integration is enabled, so nothing was attempted
    UNSUPPORTED = "unsupported"  #: this integration cannot perform this kind of operation at all
    INVALID = "invalid"          #: the request itself is not ready (or not valid) to be performed


@dataclass(frozen=True)
class MissingFact:
    """A fact a request needs and does not have, with the reason it cannot be supplied by guessing."""

    field: str
    reason: str

    def describe(self) -> str:
        return f"{self.field}: {self.reason}"


def _text(value: object, *, noun: str, maximum: int, optional: bool = False) -> str | None:
    """Trim, bound and return a text field, refusing one that is blank or too long.

    Identical in spirit to the store's own text handling: whitespace-only is not a value, and inner runs of
    whitespace collapse, so a title built from the UI cannot differ from the same title typed twice.
    """
    if value is None:
        if optional:
            return None
        raise ValueError(f"Give the {noun}: a request with an empty one describes nothing.")
    text = " ".join(str(value).split())
    if not text:
        if optional:
            return None
        raise ValueError(f"Give the {noun}: a request with an empty one describes nothing.")
    if len(text) > maximum:
        raise ValueError(f"The {noun} is {len(text)} characters; at most {maximum} are accepted.")
    return text


def _multiline(value: object, *, noun: str, maximum: int) -> str:
    """Trim a multi-line field, keeping its line structure (a body's paragraphs are its content)."""
    text = "\n".join(line.rstrip() for line in str(value or "").splitlines()).strip()
    if not text:
        raise ValueError(f"Give the {noun}: a message with an empty one says nothing.")
    if len(text) > maximum:
        raise ValueError(f"The {noun} is {len(text)} characters; at most {maximum} are accepted.")
    return text


#: A deliberately conservative address shape: one ``@``, a non-empty local part, and a dotted domain.
#: This is not RFC 5322 and does not try to be - the point is to refuse what a person can see is wrong
#: (a missing domain, a stray space, an empty local part) without pretending to decide deliverability.
_EMAIL_SHAPE = re.compile(r"^[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+$")


def validate_email_address(address: str) -> str:
    """Return a checked recipient address, or refuse it with the reason.

    Whitespace is refused rather than stripped from the middle of an address: ``a @b.example`` and
    ``a@b.example `` are different strings, and silently "fixing" one would hide a copy-paste mistake in an
    address that is about to receive a person's private message.
    """
    text = str(address or "")
    if text != text.strip():
        raise ValueError("The recipient address has leading or trailing spaces; check it and try again.")
    if not text:
        raise ValueError("Give the recipient's address; nothing here can know it.")
    if any(character.isspace() for character in text):
        raise ValueError(f"{text!r} contains a space, which an email address cannot.")
    if len(text) > 254:
        raise ValueError(f"The recipient address is {len(text)} characters; at most 254 are accepted.")
    if _EMAIL_SHAPE.fullmatch(text) is None:
        raise ValueError(
            f"{text!r} is not an address this application will use: an address needs one '@', something "
            "before it, and a domain with a dot in it."
        )
    return text


def validate_timezone(name: str) -> str:
    """Return a checked IANA timezone name, or refuse it with the reason.

    A timezone is checked against the platform's own database rather than accepted as a string, because an
    unrecognised name would otherwise travel as far as a provider and fail there - or, worse, be ignored and
    move the event. A platform without the tz database is reported as such instead of being treated as
    "every name is fine".
    """
    text = str(name or "").strip()
    if not text:
        raise ValueError("Give the timezone for a timed event, for example Asia/Kolkata.")
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    except ImportError as exc:  # pragma: no cover - zoneinfo is in the standard library from 3.9
        raise ValueError(
            "This Python has no zoneinfo module, so a timezone cannot be checked. Use an all-day entry "
            "instead, or run on a supported interpreter."
        ) from exc
    try:
        ZoneInfo(text)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"{text!r} is not a timezone this machine's database knows. Use an IANA name such as "
            "Asia/Kolkata, or leave the event as an all-day entry."
        ) from exc
    except ValueError as exc:
        raise ValueError(f"{text!r} is not a timezone name ({exc}).") from exc
    return text


def _operation_id(kind: OperationKind, payload: Mapping[str, object]) -> str:
    """A stable identity for one operation, derived from its own content.

    Stable is the whole point: the same draft asked for twice must produce the same id, or an integration
    cannot recognise the repeat. Content *is* the identity here - editing the body makes it a different
    operation, deliberately, because a person who changed what they want to say is asking for a new thing.

    Nothing time-dependent goes into the digest: a timestamp would make every attempt a new operation, which
    is exactly the bug idempotency keys exist to prevent.
    """
    canonical = json.dumps(
        {"kind": kind.value, "payload": payload}, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), default=str,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{kind.value}-{digest[:20]}"


@dataclass(frozen=True)
class EmailDraft:
    """A message that has been written and not sent. Never sent by existing.

    ``recipient`` is optional because a draft is still useful without one: the text is the part a person
    writes, and the address is a fact about somebody else's employer that this application has no way to
    know. A draft without a recipient reports it as a :class:`MissingFact`, and an integration refuses to
    perform it.
    """

    subject: str
    body: str
    listing_id: str | None = None
    recipient: str | None = None
    purpose: str = PURPOSE_FOLLOW_UP
    operation_id: str | None = None

    def __post_init__(self):
        subject = _text(self.subject, noun="subject", maximum=MAX_SUBJECT_LENGTH)
        body = _multiline(self.body, noun="message body", maximum=MAX_BODY_LENGTH)
        purpose = _text(self.purpose, noun="purpose", maximum=80)
        listing_id = None if self.listing_id is None else str(self.listing_id).strip() or None
        # The address is checked here, at construction, so an invalid one cannot reach an integration at all.
        # A blank string means "not supplied", which is a different thing from a wrong address.
        supplied = None if self.recipient is None else str(self.recipient)
        recipient = validate_email_address(supplied) if supplied is not None and supplied.strip() else None
        identity = self.operation_id or _operation_id(OperationKind.EMAIL, {
            "listing_id": listing_id,
            "recipient": recipient.lower() if recipient else None,
            "subject": subject,
            "body": body,
        })
        object.__setattr__(self, "subject", subject)
        object.__setattr__(self, "body", body)
        object.__setattr__(self, "purpose", purpose)
        object.__setattr__(self, "listing_id", listing_id)
        object.__setattr__(self, "recipient", recipient)
        object.__setattr__(self, "operation_id", identity)

    @property
    def is_ready(self) -> bool:
        """Whether this draft carries everything an integration needs to perform it."""
        return not self.missing()

    def missing(self) -> tuple[MissingFact, ...]:
        """The facts that are not in the draft, each with the reason it cannot be guessed."""
        if self.recipient is None:
            return (MissingFact(
                "recipient",
                "no address is recorded anywhere in this application, and guessing one from an employer's "
                "name would send a private message to a stranger. Type the address the employer gave you.",
            ),)
        return ()

    def describe(self) -> str:
        """One line for a log or a list: what the draft is, never whom it is to."""
        return (f"{self.purpose} draft for {self.listing_id or 'no stored application'} "
                f"({len(self.body)} characters, operation {self.operation_id})")


#: The years an event day may fall in, matching the bounds the rest of the application uses for recorded
#: dates: a mistyped year is a typo, and a calendar entry in year 202 is not a plan.
YEAR_MINIMUM = 1900
YEAR_MAXIMUM = 2100


@dataclass(frozen=True)
class CalendarEventRequest:
    """An event that has been described and not created. Never created by existing.

    A day is required; a *time* is optional and never invented. An interview invitation a person read may
    say "10:30 IST", and then they can record that here - but an application that assumed a time would put a
    wrong appointment in somebody's calendar, and one that assumed a timezone would move it by hours. So a
    time requires a timezone and a duration, a duration requires a time, and a request that mixes them in
    other combinations is refused with the reason rather than silently reinterpreted as all-day.
    """

    title: str
    day: date
    listing_id: str | None = None
    start_time: time | None = None
    duration_minutes: int | None = None
    timezone_name: str | None = None
    notes: str | None = None
    operation_id: str | None = None

    def __post_init__(self):
        title = _text(self.title, noun="event title", maximum=MAX_TITLE_LENGTH)
        notes = _text(self.notes, noun="note", maximum=MAX_BODY_LENGTH, optional=True)
        if not isinstance(self.day, date) or isinstance(self.day, datetime):
            raise ValueError("Give the event a day as a date, not a moment in time.")
        if not (YEAR_MINIMUM <= self.day.year <= YEAR_MAXIMUM):
            raise ValueError(f"The event day {self.day.isoformat()} is outside the years this app records "
                             f"({YEAR_MINIMUM}-{YEAR_MAXIMUM}).")
        start_time = self.start_time
        if start_time is not None and not isinstance(start_time, time):
            raise ValueError("Give a start time as a time of day, or leave it out for an all-day event.")
        if start_time is not None and start_time.tzinfo is not None:
            raise ValueError(
                "Give the start time as a plain time of day and name the timezone separately, so the two "
                "cannot disagree."
            )
        duration = self.duration_minutes
        if duration is not None:
            if not isinstance(duration, int) or isinstance(duration, bool):
                raise ValueError("Give the duration as a whole number of minutes.")
            if not (MIN_DURATION_MINUTES <= duration <= MAX_DURATION_MINUTES):
                raise ValueError(
                    f"A duration of {duration} minute(s) is outside the range this app records "
                    f"({MIN_DURATION_MINUTES}-{MAX_DURATION_MINUTES})."
                )
        timezone_name = None if self.timezone_name is None else validate_timezone(self.timezone_name)
        if start_time is None and duration is not None:
            raise ValueError("A duration needs a start time. Leave both out for an all-day entry.")
        if start_time is not None and duration is None:
            raise ValueError("Give how long the event is expected to take, in minutes.")
        if start_time is None and timezone_name is not None:
            raise ValueError(
                "A timezone without a time of day means nothing here. Leave it out for an all-day entry."
            )
        if start_time is not None and timezone_name is None:  # pragma: no cover - enforced by validate above
            raise ValueError("Give the timezone the start time is in.")
        listing_id = None if self.listing_id is None else str(self.listing_id).strip() or None
        identity = self.operation_id or _operation_id(OperationKind.CALENDAR, {
            "listing_id": listing_id,
            "title": title,
            "day": self.day.isoformat(),
            "start_time": start_time.isoformat() if start_time else None,
            "duration_minutes": duration,
            "timezone": timezone_name,
        })
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "notes", notes)
        object.__setattr__(self, "start_time", start_time)
        object.__setattr__(self, "duration_minutes", duration)
        object.__setattr__(self, "timezone_name", timezone_name)
        object.__setattr__(self, "listing_id", listing_id)
        object.__setattr__(self, "operation_id", identity)

    @property
    def is_all_day(self) -> bool:
        """Whether this is an all-day entry: no time of day was recorded, and none was invented."""
        return self.start_time is None

    @property
    def is_ready(self) -> bool:
        """Whether this request carries everything needed to be performed. A day and a title suffice."""
        return not self.missing()

    def missing(self) -> tuple[MissingFact, ...]:
        """The facts a request cannot be performed without. A day and a title are enough, so usually none."""
        return ()

    def imprecisions(self) -> tuple[MissingFact, ...]:
        """What this request does not pin down, reported without blocking it.

        An all-day entry is a complete request: it says what a person actually knows. But it does not say
        *when*, and this application will not close that gap by choosing a time. Saying so is the difference
        between a calendar entry that is vague and one that is wrong.
        """
        if self.is_all_day:
            return (MissingFact(
                "start time",
                "no time of day is recorded, so this is an all-day entry. If the invitation you received "
                "names a time, record it - this application will not guess one, and a guessed appointment "
                "is worse than a vague one.",
            ),)
        return ()

    def describe(self) -> str:
        when = self.start_time.strftime("%H:%M") if self.start_time else "all day"
        return f"{self.day.isoformat()} {when}: {self.title} ({self.operation_id})"


@dataclass(frozen=True)
class IntegrationResult:
    """What an integration did, or why it did not. ``performed`` is never inferred, only stated."""

    outcome: Outcome
    operation_id: str
    message: str
    performed: bool
    integration_name: str
    detail: str | None = None
    attempts: int = 1

    @property
    def succeeded(self) -> bool:
        """Whether the caller's intent is satisfied - including by an earlier, identical operation."""
        return self.outcome in (Outcome.COMPLETED, Outcome.DUPLICATE)

    def describe(self) -> str:
        return f"[{self.outcome.value}] {self.message}"


@dataclass(frozen=True)
class LedgerRecord:
    """One operation an integration has performed, as recorded locally."""

    operation_id: str
    kind: OperationKind
    listing_id: str | None
    target: str
    summary: str
    completed_at: str
    attempts: int = 1

    def to_json(self) -> dict:
        return {
            "operation_id": self.operation_id, "kind": self.kind.value, "listing_id": self.listing_id,
            "target": self.target, "summary": self.summary, "completed_at": self.completed_at,
            "attempts": self.attempts,
        }

    @classmethod
    def from_json(cls, payload: Mapping[str, object]) -> "LedgerRecord":
        return cls(
            operation_id=str(payload["operation_id"]),
            kind=OperationKind(str(payload["kind"])),
            listing_id=None if payload.get("listing_id") is None else str(payload["listing_id"]),
            target=str(payload.get("target", "")),
            summary=str(payload.get("summary", "")),
            completed_at=str(payload.get("completed_at", "")),
            attempts=int(payload.get("attempts", 1)),
        )


class IntegrationLedgerError(ValueError):
    """A ledger file exists and cannot be read, so what was already done cannot be established."""


class IntegrationLedger:
    """The operations one integration has already performed, keyed by operation id.

    The file is optional and local. Its one hard rule is at :meth:`load`: a ledger that exists and cannot be
    read raises rather than being treated as empty, because "I could not read the record of what I have
    already done" and "I have done nothing" are the same thing only in a system that is about to do it twice.
    """

    def __init__(self, records: Mapping[str, LedgerRecord] | None = None):
        self._records: dict[str, LedgerRecord] = dict(records or {})

    def __len__(self) -> int:
        return len(self._records)

    def __contains__(self, operation_id: object) -> bool:
        return str(operation_id) in self._records

    def record_for(self, operation_id: str) -> LedgerRecord | None:
        return self._records.get(str(operation_id))

    def records(self) -> tuple[LedgerRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records))

    def record(self, entry: LedgerRecord) -> None:
        self._records[entry.operation_id] = entry

    def count_of(self, kind: OperationKind) -> int:
        return sum(1 for entry in self._records.values() if entry.kind is kind)

    def to_json(self) -> dict:
        return {
            "ledger_version": LEDGER_VERSION,
            "operations": [entry.to_json() for entry in self.records()],
        }

    @classmethod
    def from_json(cls, payload: Mapping[str, object]) -> "IntegrationLedger":
        version = payload.get("ledger_version")
        if version != LEDGER_VERSION:
            raise IntegrationLedgerError(
                f"The ledger records format version {version!r}, and this build reads version "
                f"{LEDGER_VERSION}. Nothing was performed; remove or move the file if you want to start a "
                "fresh record."
            )
        operations = payload.get("operations")
        if not isinstance(operations, list):
            raise IntegrationLedgerError(
                "The ledger has no list of operations, so what has already been done cannot be established. "
                "Nothing was performed."
            )
        try:
            records = {str(item["operation_id"]): LedgerRecord.from_json(item) for item in operations}
        except (KeyError, TypeError, ValueError) as exc:
            raise IntegrationLedgerError(
                f"The ledger could not be read ({exc}). Nothing was performed; if the file was damaged, move "
                "it aside and start a fresh record."
            ) from exc
        return cls(records)

    @classmethod
    def load(cls, path: str | Path) -> "IntegrationLedger":
        """Read a ledger file, or return an empty ledger when there is no file yet.

        A *missing* file is a first run, which is not an error. A file that exists and cannot be parsed is an
        error the caller must see: continuing with an empty ledger would silently allow a repeat.
        """
        target = Path(path)
        if not target.exists():
            return cls()
        try:
            size = target.stat().st_size
        except OSError as exc:
            raise IntegrationLedgerError(
                f"The ledger at {target.name} could not be examined ({exc}). Nothing was performed, because "
                "this application cannot establish what it has already done and will not risk doing it twice."
            ) from exc
        if size > MAX_LEDGER_BYTES:
            raise IntegrationLedgerError(
                f"The ledger at {target.name} is {size / (1024 * 1024):.1f} MB, far too large to be one this "
                "application wrote, so it was not read. Nothing was performed, because this application "
                "cannot establish what it has already done and will not risk doing it twice."
            )
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise IntegrationLedgerError(
                f"The ledger at {target.name} could not be read ({exc}). Nothing was performed, because this "
                "application cannot establish what it has already done and will not risk doing it twice."
            ) from exc
        if not isinstance(payload, Mapping):
            raise IntegrationLedgerError(
                f"The ledger at {target.name} does not hold an object, so it was not written by this "
                "application. Nothing was performed."
            )
        return cls.from_json(payload)

    def save(self, path: str | Path) -> Path:
        """Write the ledger as an owner-only file, and return where it went."""
        text = json.dumps(self.to_json(), indent=2, sort_keys=True) + "\n"
        return write_private_text_file(Path(path), text)


@runtime_checkable
class Integration(Protocol):
    """What this application requires of anything it asks to perform an operation.

    Two methods, because there are two kinds of operation. An integration that supports only one of them
    returns :attr:`Outcome.UNSUPPORTED` for the other rather than raising: "I cannot do that" is information
    a caller can act on, and an exception would be indistinguishable from a bug.
    """

    name: str
    is_enabled: bool

    def send_email(self, draft: EmailDraft) -> IntegrationResult:
        """Perform an email draft, or refuse it. Must not raise for a refusal."""

    def create_event(self, request: CalendarEventRequest) -> IntegrationResult:
        """Perform a calendar event, or refuse it. Must not raise for a refusal."""


@dataclass(frozen=True)
class DisabledIntegration:
    """The integration this application uses until somebody decides otherwise: it does nothing.

    Every request is answered with :attr:`Outcome.DISABLED` and a message naming what to do instead. The type
    is the point - a default that raised, or one that wrote to a "dry run" log, would let a caller believe
    something had been configured; ``is_enabled`` is ``False`` and stays that way.
    """

    reason: str = DEFAULT_DISABLED_REASON
    name: str = "disabled"
    is_enabled: bool = False

    def _refuse(self, operation_id: str, *, kind: OperationKind) -> IntegrationResult:
        return IntegrationResult(
            outcome=Outcome.DISABLED, operation_id=operation_id,
            message=f"{kind.value} operations are disabled: {self.reason}",
            performed=False, integration_name=self.name,
        )

    def send_email(self, draft: EmailDraft) -> IntegrationResult:
        return self._refuse(draft.operation_id, kind=OperationKind.EMAIL)

    def create_event(self, request: CalendarEventRequest) -> IntegrationResult:
        return self._refuse(request.operation_id, kind=OperationKind.CALENDAR)


class LocalMockIntegration:
    """A local stand-in that performs nothing outside this machine, and says so in every result.

    It exists for two reasons: deterministic tests of the bookkeeping around an operation (idempotency,
    duplicates, retries, refusals), and a person who wants to watch the whole sequence run without a provider
    account. Its guarantees, and their limits, are worth being precise about:

    * **It contacts nothing.** There is no code path here that opens a connection; the module imports nothing
      capable of it, and the project's local-first test enforces that for shipped code.
    * **Deduplication is local.** A record of what has been done lives in memory, or in a ledger file if one
      is given. The mock can therefore refuse a repeat *within* that record. It cannot prove that a request
      the network dropped never arrived, which is why a real provider has to enforce the operation id
      server-side - see :data:`ENABLEMENT_REQUIREMENTS`.
    * **A failed attempt is not recorded as done.** Failure injection exists to test that a retry after a
      failure performs the operation once, and that a retry of something already done performs nothing.
    * **A ledger write failure is reported as a failure.** If the record cannot be written, the operation is
      not reported as completed: this application will not claim to know something it cannot prove.
    * **One key means one operation.** An id already recorded against a different kind of operation is
      refused rather than treated as a repeat, because the ledger cannot say which of the two was meant.
    """

    name = "local-mock"
    is_enabled = True

    def __init__(
        self,
        *,
        ledger: IntegrationLedger | None = None,
        ledger_path: str | Path | None = None,
        fail_operation_ids: Mapping[str, int] | Iterable[str] = (),
        clock: Callable[[], datetime] | None = None,
    ):
        """``fail_operation_ids`` is either a mapping from operation id to how many attempts to fail, or an
        iterable of ids that fail every time - the first is how "a retry after a failure performs the
        operation once" is tested, the second how "retrying stops" is. Nothing else about an integration
        can be configured: there is no address, no account and no endpoint here to configure."""
        self.ledger_path = None if ledger_path is None else Path(ledger_path)
        if self.ledger_path is not None and self.ledger_path.exists():
            # The file is the record of what has already been done, so it wins over anything passed in: an
            # integration that started from an empty record would treat a repeat as a first operation.
            # An unreadable file raises here, which is the point (see `IntegrationLedger.load`).
            self._ledger = IntegrationLedger.load(self.ledger_path)
        elif ledger is not None:
            self._ledger = ledger
        else:
            self._ledger = IntegrationLedger()
        if isinstance(fail_operation_ids, Mapping):
            self._remaining_failures = {str(key): int(value) for key, value in fail_operation_ids.items()}
        else:
            self._remaining_failures = {str(key): 1_000_000 for key in fail_operation_ids}
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        #: How many attempts each operation has had, including the ones that failed. Useful in tests, and it
        #: is not the ledger: an attempt that failed is not a performed operation.
        self.attempts: dict[str, int] = {}

    @property
    def ledger(self) -> IntegrationLedger:
        return self._ledger

    def _now(self) -> datetime:
        moment = self._clock()
        return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)

    def _already_done(self, operation_id: str, *, kind: OperationKind) -> IntegrationResult | None:
        entry = self._ledger.record_for(operation_id)
        if entry is None:
            return None
        if entry.kind is not kind:
            # The ledger already holds this key for a different kind of operation. That is not a repeat and it
            # is not a duplicate either: it means the key is being asked to mean two things, and there is no
            # safe way to guess which. Refusing is the only answer that cannot perform the wrong operation.
            return IntegrationResult(
                outcome=Outcome.INVALID, operation_id=operation_id, performed=False,
                integration_name=self.name,
                message=(f"The operation id {operation_id} is already recorded against a "
                         f"{entry.kind.value} operation ({entry.summary}), so this {kind.value} operation was "
                         "not performed. Use a key that means one thing, or ask for the operation with its "
                         "own id - nothing was sent and nothing was created."),
                detail=f"recorded_kind={entry.kind.value}",
            )
        return IntegrationResult(
            outcome=Outcome.DUPLICATE, operation_id=operation_id, performed=False,
            integration_name=self.name,
            message=(f"This exact {kind.value} operation was already performed at {entry.completed_at} "
                     f"({entry.summary}). Nothing was performed again, and nothing was sent or created twice."),
            detail=f"completed_at={entry.completed_at}",
        )

    def _injected_failure(self, operation_id: str) -> bool:
        remaining = self._remaining_failures.get(operation_id, 0)
        if remaining <= 0:
            return False
        self._remaining_failures[operation_id] = remaining - 1
        return True

    def _record(self, entry: LedgerRecord) -> IntegrationResult | None:
        """Record a completed operation, or return the failure result if the record cannot be written."""
        self._ledger.record(entry)
        if self.ledger_path is None:
            return None
        try:
            self._ledger.save(self.ledger_path)
        except (OSError, ValueError) as exc:
            # The in-memory record is kept (it is the truth we have), but the operation is *not* reported as
            # completed: a caller that saw "completed" would stop trying, and the file that proves it is not
            # there. A real integration must reconcile with the provider instead - it cannot do this either.
            return IntegrationResult(
                outcome=Outcome.FAILED, operation_id=entry.operation_id, performed=False,
                integration_name=self.name,
                message=(f"The operation was recorded in memory, but the ledger at {self.ledger_path.name} "
                         f"could not be written ({exc}), so it is not being reported as completed. Nothing "
                         "left this machine."),
                attempts=self.attempts.get(entry.operation_id, 1),
            )
        return None

    def send_email(self, draft: EmailDraft) -> IntegrationResult:
        self.attempts[draft.operation_id] = self.attempts.get(draft.operation_id, 0) + 1
        if not draft.is_ready:
            return IntegrationResult(
                outcome=Outcome.INVALID, operation_id=draft.operation_id, performed=False,
                integration_name=self.name,
                message=("This draft is not ready: " + "; ".join(fact.describe() for fact in draft.missing())),
            )
        done = self._already_done(draft.operation_id, kind=OperationKind.EMAIL)
        if done is not None:
            return done
        if self._injected_failure(draft.operation_id):
            return IntegrationResult(
                outcome=Outcome.FAILED, operation_id=draft.operation_id, performed=False,
                integration_name=self.name,
                message=("The local mock was told to fail this operation. Nothing was recorded as done, so a "
                         "retry with the same operation id is allowed and will not duplicate anything."),
                attempts=self.attempts[draft.operation_id],
            )
        entry = LedgerRecord(
            operation_id=draft.operation_id, kind=OperationKind.EMAIL, listing_id=draft.listing_id,
            target=draft.recipient or "", summary=draft.subject,
            completed_at=self._now().astimezone(timezone.utc).isoformat(timespec="seconds"),
            attempts=self.attempts[draft.operation_id],
        )
        failure = self._record(entry)
        if failure is not None:
            return failure
        return IntegrationResult(
            outcome=Outcome.COMPLETED, operation_id=draft.operation_id, performed=True,
            integration_name=self.name, attempts=entry.attempts,
            message=(f"The local mock recorded this {entry.kind.value} operation in "
                     f"{self._describe_ledger_target()}. No email was sent, no server was contacted, and no "
                     "account was touched."),
            detail=f"target={entry.target} recorded_at={entry.completed_at}",
        )

    def create_event(self, request: CalendarEventRequest) -> IntegrationResult:
        self.attempts[request.operation_id] = self.attempts.get(request.operation_id, 0) + 1
        if not request.is_ready:  # pragma: no cover - a day and a title are always present; defensive
            return IntegrationResult(
                outcome=Outcome.INVALID, operation_id=request.operation_id, performed=False,
                integration_name=self.name,
                message=("This event is not ready: "
                         + "; ".join(fact.describe() for fact in request.missing())),
            )
        done = self._already_done(request.operation_id, kind=OperationKind.CALENDAR)
        if done is not None:
            return done
        if self._injected_failure(request.operation_id):
            return IntegrationResult(
                outcome=Outcome.FAILED, operation_id=request.operation_id, performed=False,
                integration_name=self.name,
                message=("The local mock was told to fail this operation. Nothing was recorded as done, so a "
                         "retry with the same operation id is allowed and will not duplicate anything."),
                attempts=self.attempts[request.operation_id],
            )
        entry = LedgerRecord(
            operation_id=request.operation_id, kind=OperationKind.CALENDAR, listing_id=request.listing_id,
            target=request.day.isoformat(), summary=request.title,
            completed_at=self._now().astimezone(timezone.utc).isoformat(timespec="seconds"),
            attempts=self.attempts[request.operation_id],
        )
        failure = self._record(entry)
        if failure is not None:
            return failure
        return IntegrationResult(
            outcome=Outcome.COMPLETED, operation_id=request.operation_id, performed=True,
            integration_name=self.name, attempts=entry.attempts,
            message=(f"The local mock recorded this {entry.kind.value} operation in "
                     f"{self._describe_ledger_target()}. No calendar account was contacted and no invitation "
                     "was sent to anybody."),
            detail=f"day={entry.target} recorded_at={entry.completed_at}",
        )

    def _describe_ledger_target(self) -> str:
        return "memory" if self.ledger_path is None else f"the ledger at {self.ledger_path.name}"


def default_integration() -> Integration:
    """The integration this application uses unless a caller asks for a specific one: none.

    There is deliberately no configuration that switches this: a real provider needs credentials, an
    authorization decision and provider-side idempotency (see :data:`ENABLEMENT_REQUIREMENTS`), and a
    function that read an environment variable to pick an integration would make "is this machine able to
    email people on its own?" a question nobody could answer by looking at the app.
    """
    return DisabledIntegration()


def describe_integrations() -> tuple[str, ...]:
    """The integration state as lines to show a person, for ``--integration-status``."""
    lines = [
        "Integration state: nothing is enabled.",
        f"  The default is {DisabledIntegration().name}: every email or calendar operation is refused with "
        "the reason, and nothing anywhere is attempted.",
        f"  {LocalMockIntegration.name} exists as a local stand-in: it contacts nothing, keeps a record of the "
        "operations it has been asked to perform, and is selected only by asking for it explicitly - the "
        "tests, or --mock-ledger PATH on a command. It is never chosen by configuration.",
        "",
        "Available today without any integration:",
        "  - draft an email and read it in full before deciding anything (nothing is sent);",
        "  - preview exactly what a follow-up calendar export would contain, then write that .ics file for "
        "your own calendar;",
        "  - keep every record on this machine: nothing is uploaded, and no employer is contacted.",
        "",
        "Before a real provider could be enabled:",
    ]
    lines.extend(f"  - {name}: {reason}" for name, reason in ENABLEMENT_REQUIREMENTS)
    return tuple(lines)


def dispatch_with_retry(
    integration: Integration, request: EmailDraft | CalendarEventRequest, *,
    attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> IntegrationResult:
    """Perform a request, retrying **only** a failure, and only because the operation id makes it safe.

    A retry is a second attempt at an operation that may already have arrived, so it is allowed here for one
    reason: the same operation id travels with it, and any integration that honours it will refuse the repeat.
    Everything else is returned as it came - a disabled integration stays disabled, an invalid request stays
    invalid (retrying bad input just fails twice), and a duplicate is already satisfied.
    """
    if attempts < 1:
        raise ValueError("A dispatch needs at least one attempt.")
    perform = integration.send_email if isinstance(request, EmailDraft) else integration.create_event
    result = perform(request)
    tried = 1
    while result.outcome is Outcome.FAILED and tried < attempts:
        result = perform(request)
        tried += 1
    return result if tried == 1 else replace(result, attempts=tried)


def authorised_dispatch(
    integration: Integration, request: EmailDraft | CalendarEventRequest, *,
    policy: GlobalPolicy | None,
    source_id: str,
    now: datetime,
    done_today: int | None,
    source_gate_allows: bool,
    subject: PolicySubject | None = None,
    attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> IntegrationResult:
    """Dispatch a request **only** when the standing authorisation and the enabling gate both permit it.

    This is a separate door from :func:`dispatch_with_retry` on purpose. That function is the mechanical
    part - perform, retry a failure, stop - and it is used by tests and by the local stand-in, where there
    is nothing to authorise because nothing leaves the machine. This one is what a real provider would be
    called through, and it refuses by default:

    * ``policy=None`` refuses: a missing authorisation is not an empty one, and neither permits anything;
    * ``done_today=None`` refuses: a daily limit cannot be honoured without today's count, and the count
      has to come from durable records rather than from a number this function could invent;
    * ``source_gate_allows=False`` refuses, whatever the authorisation says, so an authorisation can never
      open a gate;
    * an operation the authorisation has no word for refuses by raising :class:`PolicyError`, because
      guessing which action a request counts as is exactly the mistake a limit exists to prevent.

    A refusal is returned as :attr:`Outcome.DISABLED` with ``performed=False`` and the decision's own
    reasons in ``detail`` - the same shape a disabled integration returns, because to the caller the two
    mean the same thing: nothing happened, and here is why.
    """
    if isinstance(request, EmailDraft):
        action = ActionKind.EMAIL_SEND
    else:
        raise PolicyError(
            "A calendar event is not an action the standing authorisation can describe, so it cannot be "
            "authorised here. Write the .ics file and let the person's own calendar accept it."
        )
    operation_id = request.operation_id or ""
    if done_today is None and policy is not None:
        return IntegrationResult(
            outcome=Outcome.DISABLED, operation_id=operation_id,
            message="Nothing was sent: how many of today's messages have already gone out is not known, "
                    "and a daily limit cannot be honoured without it.",
            performed=False, integration_name=integration.name)
    decision = evaluate_policy(
        policy if policy is not None else no_authorisation(),
        source_id=source_id, action=action, now=now,
        done_today=done_today or 0, source_gate_allows=source_gate_allows, subject=subject)
    if not decision.allowed:
        return IntegrationResult(
            outcome=Outcome.DISABLED, operation_id=operation_id,
            message=f"Nothing was sent: this is not authorised. {decision.describe()}",
            performed=False, integration_name=integration.name,
            detail="; ".join(decision.refusals))
    return dispatch_with_retry(integration, request, attempts=attempts)


#: Pass as ``done_today`` to have :func:`guarded_dispatch` count the day's actions from the stored
#: attempt rows instead of being told. ``None`` keeps its meaning - *nobody counted* - and refuses.
COUNT_FROM_RECORDS = "count-from-records"


def guarded_dispatch(
    store, integration: Integration, request: EmailDraft, *,
    identity_key: str,
    policy: GlobalPolicy | None,
    source_id: str,
    now: datetime,
    done_today: int | str | None,
    source_gate_allows: bool,
    subject: PolicySubject | None = None,
    attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> IntegrationResult:
    """Dispatch at most once per job identity, writing the attempt down before it is made.

    This is :func:`authorised_dispatch` with the part that makes a retry safe to allow at all: a
    durable record of what has already been tried, keyed by the **cross-source job identity** rather
    than by a listing id, so the same vacancy found on two sources cannot be written to twice.

    The order is the point:

    1. read what is already recorded for this identity and action, and refuse when an earlier attempt
       ended without an established outcome (it may have happened) or already succeeded (a second one
       is a duplicate, not a retry);
    2. write the attempt as ``unknown`` **before** performing it, so a crash in the middle leaves
       evidence rather than silence;
    3. perform it through the authorised door, which still checks the policy and the gate;
    4. record what was observed - and a dispatch that *failed* settles as ``unknown``, not as
       ``failed``, because a failure mid-flight is exactly the case nobody can resolve from here.

    Nothing about this function can make an action permissible: every refusal in
    :func:`authorised_dispatch` still applies, and today every one of them fires.
    """
    identity = str(identity_key or "").strip()
    if not identity:
        raise AttemptError(
            "A dispatch is recorded against a job identity so it cannot be repeated; none was given.")
    operation_id = str(getattr(request, "operation_id", "") or "").strip()
    action = ActionKind.EMAIL_SEND.value
    if not operation_id:
        return IntegrationResult(
            outcome=Outcome.INVALID, operation_id="", integration_name=integration.name,
            performed=False,
            message="Nothing was sent: this request carries no operation id, and without one a "
                    "repeat could not be told from a first attempt.")
    if done_today is COUNT_FROM_RECORDS:
        # Counted before this attempt's own row exists, or an allowance of one would refuse the
        # first action of the day for having already spent itself.
        done_today = store.actions_done_today(action, now=now)
    recorded = store.list_attempts(identity_key=identity, action=action)
    if (policy is not None and policy.follow_up_limit is not None
            and (subject is None or subject.follow_ups_so_far is None)):
        # The limit is per job, so the count is per job identity, and it comes from the rows rather
        # than from the caller's memory of what it sent.
        already = sum(1 for attempt in recorded if attempt.state is not AttemptState.REFUSED)
        subject = (replace(subject, follow_ups_so_far=already) if subject is not None
                   else PolicySubject(follow_ups_so_far=already))
    decision = may_attempt(recorded, identity_key=identity, action=action)
    if not decision.allowed:
        return IntegrationResult(
            outcome=Outcome.INVALID, operation_id=operation_id, integration_name=integration.name,
            performed=False, message=decision.describe(),
            detail="; ".join(decision.blocking_operation_ids))
    # The attempt is stamped with the moment the policy was judged at, not with whatever the clock
    # says a few milliseconds later: a limit evaluated for one day must be counted against that day.
    moment = now.isoformat() if isinstance(now, datetime) else None
    store.begin_attempt(operation_id=operation_id, identity_key=identity, action=action, now=moment)
    result = authorised_dispatch(
        integration, request, policy=policy, source_id=source_id, now=now,
        done_today=done_today, source_gate_allows=source_gate_allows, subject=subject,
        attempts=attempts)
    state = state_from_outcome(result.outcome.value, performed=result.performed)
    store.settle_attempt(operation_id, state=state, detail=result.message[:300], now=moment)
    if state is AttemptState.UNKNOWN:
        return replace(
            result,
            message=(result.message + " Whether it arrived could not be established, so it is "
                     "recorded as unknown and no further attempt will be made at this job until "
                     "you check and reconcile it."),
            detail="unknown outcome recorded")
    return result


@dataclass(frozen=True)
class Preview:
    """What an operation would do, in the words a person would read, before anything happens.

    A preview is a *value*, and producing one has no side effect - the ``enabled`` field says whether an
    execution would be possible at all, which is the difference between "here is what it would send" and
    "here is what it would send, if you had an integration".
    """

    kind: OperationKind
    operation_id: str
    headline: str
    fields: tuple[tuple[str, str], ...]
    missing: tuple[MissingFact, ...]
    would_do: str
    integration_name: str
    enabled: bool
    body: str | None = None
    warnings: tuple[str, ...] = ()
    gaps: tuple[MissingFact, ...] = ()

    @property
    def is_ready(self) -> bool:
        """Whether the thing being previewed carries every fact it needs to be performed."""
        return not self.missing

    def describe(self) -> tuple[str, ...]:
        """The preview as lines, the way a terminal or a dialog would show it."""
        lines = [self.headline]
        lines.extend(f"  {label}: {value}" for label, value in self.fields)
        if self.missing:
            lines.append("  Missing, and not guessed:")
            lines.extend(f"    - {fact.describe()}" for fact in self.missing)
        if self.gaps:
            lines.append("  Not recorded, and not invented:")
            lines.extend(f"    - {fact.describe()}" for fact in self.gaps)
        if self.warnings:
            lines.extend(f"  ! {warning}" for warning in self.warnings)
        lines.append(f"  If performed: {self.would_do}")
        lines.append(f"  Operation id: {self.operation_id}")
        return tuple(lines)

    def render(self) -> str:
        """The preview as one block of text, for a dialog or a copied note."""
        return "\n".join(self.describe())


def _application_field(listing: object | None, listing_id: str | None) -> tuple[str, str]:
    """How the preview names the application an operation belongs to.

    Uses the stored listing's own words when it is there, and says plainly when it is not - an operation
    attached to a listing that is no longer stored is still allowed, and must not look attached to a job
    that has no name.
    """
    if listing is not None:
        return ("Application", f"{listing.role_title} at {listing.employer_name} [{listing.listing_id}]")
    if listing_id is None:
        return ("Application", "not linked to a stored application")
    return ("Application", f"listing {listing_id} (no longer stored)")


def preview_email(draft: EmailDraft, *, integration: Integration, listing: object | None = None) -> Preview:
    """Show exactly what a draft is, and exactly what sending it would do. Sends nothing."""
    missing = draft.missing()
    if integration.is_enabled:
        would_do = (f"Record this operation with the '{integration.name}' integration. No email leaves this "
                    "machine.")
    else:
        would_do = (f"Nothing: '{integration.name}' is not enabled. {DEFAULT_DISABLED_REASON}")
    fields = (
        ("To", draft.recipient if draft.recipient else "not supplied - no address is recorded anywhere"),
        ("Subject", draft.subject),
        ("Purpose", draft.purpose),
        _application_field(listing, draft.listing_id),
    )
    warnings: list[str] = []
    if draft.recipient is None:
        warnings.append("This draft is not ready to be performed: it has no recipient.")
    warnings.append("Nothing is sent by producing this preview.")
    return Preview(
        kind=OperationKind.EMAIL, operation_id=draft.operation_id,
        headline=f"Email draft preview ({integration.name})", fields=fields, missing=missing,
        would_do=would_do, integration_name=integration.name, enabled=integration.is_enabled,
        body=draft.body, warnings=tuple(warnings),
    )


def preview_event(
    request: CalendarEventRequest, *, integration: Integration, listing: object | None = None,
) -> Preview:
    """Show exactly what an event is, and exactly what creating it would do. Creates nothing."""
    if integration.is_enabled:
        would_do = (f"Record this operation with the '{integration.name}' integration. No calendar account "
                    "is contacted and nobody is invited.")
    else:
        would_do = (f"Nothing: '{integration.name}' is not enabled. {DEFAULT_DISABLED_REASON}")
    if request.is_all_day:
        when = f"{request.day.isoformat()} (all day)"
    else:
        when = (f"{request.day.isoformat()} {request.start_time.strftime('%H:%M')} "
                f"{request.timezone_name} for {request.duration_minutes} minute(s)")
    fields = (
        ("Title", request.title),
        ("When", when),
        ("Timezone", request.timezone_name or "not applicable - an all-day entry has no time of day"),
        _application_field(listing, request.listing_id),
    )
    if request.notes:
        fields = fields + (("Note", request.notes),)
    return Preview(
        kind=OperationKind.CALENDAR, operation_id=request.operation_id,
        headline=f"Calendar event preview ({integration.name})", fields=fields, missing=request.missing(),
        would_do=would_do, integration_name=integration.name, enabled=integration.is_enabled,
        gaps=request.imprecisions(),
        warnings=("Nothing is created in any calendar by producing this preview.",),
    )


@dataclass(frozen=True)
class CalendarExportPlan:
    """What the existing local ``.ics`` export would write, before it writes anything.

    This is the *working* calendar path in this application: a file the person chooses, on their own machine,
    with no account and no invitation. The preview exists so that "write 6 reminders" is something a person
    can read first - and so that the difference between this and a provider integration is visible rather
    than implied.
    """

    events: tuple[tuple[str, str, str], ...]  #: (day, summary, uid) per event, in export order
    would_write: str
    warnings: tuple[str, ...]

    def describe(self) -> tuple[str, ...]:
        lines = [f"Calendar export preview: {len(self.events)} event(s) would be written."]
        lines.extend(f"  {day}: {summary}  [{uid}]" for day, summary, uid in self.events)
        lines.append(f"  Where: {self.would_write}")
        lines.extend(f"  ! {warning}" for warning in self.warnings)
        return tuple(lines)

    def render(self) -> str:
        return "\n".join(self.describe())


def calendar_export_plan(reminders: Sequence[FollowUpReminder], *, target: str | None = None) -> CalendarExportPlan:
    """Describe the events the local export would write for these reminders. Writes nothing.

    The uid and the summary come from :mod:`career_agent.followups`, the same functions the writer uses, so a
    preview cannot promise a different event from the one the file will contain.
    """
    events = tuple(
        (reminder.on.isoformat(), event_summary(reminder), event_uid(reminder)) for reminder in reminders
    )
    return CalendarExportPlan(
        events=events,
        would_write=(f"a .ics file you choose{f' ({target})' if target else ''}, importable into your own "
                     "calendar"),
        warnings=(
            "Nothing has been written yet, and no calendar account is contacted.",
            "Every event is an all-day entry on the follow-up day: no time of day is invented, and no "
            "attendee is invited.",
        ),
    )


def draft_for_follow_up(
    reminder: FollowUpReminder, *, recipient: str | None = None, body: str | None = None,
    listing_id: str | None = None,
) -> EmailDraft:
    """Build a follow-up draft from an application's own recorded context.

    The subject and the body are built from the employer, the role, the day the person chose and their own
    note - facts already in the database - and from nothing else. The recipient is never derived: it is
    whatever the person typed, or absent, in which case the draft says so and cannot be performed.
    """
    subject = f"Following up on my application: {reminder.role_title} at {reminder.employer_name}"
    if body is None:
        lines = [
            f"Hello,",
            "",
            f"I applied for the {reminder.role_title} role at {reminder.employer_name} and wanted to follow up.",
        ]
        if reminder.note:
            lines.extend(["", f"My own note for this follow-up: {reminder.note}"])
        lines.extend([
            "",
            "If there is anything else you need from me, I am happy to send it.",
            "",
            "Thank you for your time.",
        ])
        body = "\n".join(lines)
    return EmailDraft(
        subject=subject, body=body, listing_id=listing_id or reminder.listing_id,
        recipient=recipient, purpose=PURPOSE_FOLLOW_UP,
    )


def draft_as_text(draft: EmailDraft) -> str:
    """The draft as a plain text block a person can read, copy out, or save to a local file.

    The header lines state the facts, including the one that is missing, so a draft that is not ready cannot
    be mistaken for one that is. The ``Operation id`` line is the idempotency key: a person who pastes the
    draft into a future integration, or sends it twice, can be told the two are the same operation.
    """
    recipient = draft.recipient if draft.recipient else "NOT SUPPLIED - this application never guesses an address"
    lines = [
        f"To: {recipient}",
        f"Subject: {draft.subject}",
        f"Purpose: {draft.purpose}",
        f"Operation id: {draft.operation_id}",
        "Status: DRAFT ONLY - nothing has been sent, and no integration is enabled to send it.",
    ]
    if draft.listing_id:
        lines.append(f"Application: {draft.listing_id}")
    return "\n".join(lines) + "\n\n" + draft.body + "\n"


def event_from_reminder(
    reminder: FollowUpReminder, *, start_time: time | None = None, duration_minutes: int | None = None,
    timezone_name: str | None = None,
) -> CalendarEventRequest:
    """Describe a calendar event for a follow-up: an all-day entry unless a time is supplied.

    ``title`` is the same summary the local export writes, so a person reading a preview of either path sees
    the same words for the same reminder.
    """
    return CalendarEventRequest(
        title=event_summary(reminder), day=reminder.on, listing_id=reminder.listing_id,
        start_time=start_time, duration_minutes=duration_minutes, timezone_name=timezone_name,
        notes=reminder.note,
    )
