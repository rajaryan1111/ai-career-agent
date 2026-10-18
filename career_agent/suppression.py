"""Who must never be written to again, and why - kept so that it survives everything else.

A suppression is the one record in this application that exists for somebody who is **not** its
user. A person who asked not to be contacted, an address that hard-bounced, a contact who turned out
to be the wrong person: each of those is a decision that must outlive a restart, an import, a
re-discovery of the same job and anybody's enthusiasm. So it is stored, it is checked before the
one door that can send, and lifting one is a deliberate act with a reason attached.

Three rules are in the data rather than in a caller's good intentions:

* **A request to stop is permanent.** Any suppression blocks, but one recorded because a person
  asked may not be lifted by this application for any reason of its own; only a person saying so,
  with a note, can lift it.
* **An address is matched after normalisation**, so ``Someone@Example.COM`` and ``someone@example.com``
  are the same person, and a suppression cannot be walked around by capitalisation.
* **Nothing here expires.** There is no "after six months it is fine again": that would be this
  application deciding, on its own clock, that somebody's no has run out.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SuppressionError(ValueError):
    """A suppression cannot mean what it is being asked to mean."""


class SuppressionReason(str, Enum):
    """Why an address is suppressed. The reason is kept because it changes what may happen next."""

    ASKED_TO_STOP = "asked_to_stop"
    BOUNCED_PERMANENTLY = "bounced_permanently"
    WRONG_PERSON = "wrong_person"
    NOT_RECRUITING = "not_recruiting"
    OUR_OWN_DECISION = "our_own_decision"


#: What each reason means where a person can read it.
REASON_LABELS: dict[SuppressionReason, str] = {
    SuppressionReason.ASKED_TO_STOP: "they asked not to be contacted",
    SuppressionReason.BOUNCED_PERMANENTLY: "the address rejected mail permanently",
    SuppressionReason.WRONG_PERSON: "this was not the right person",
    SuppressionReason.NOT_RECRUITING: "they said they are not recruiting",
    SuppressionReason.OUR_OWN_DECISION: "you decided not to write to them",
}

#: Reasons this application may never lift on its own.
PERMANENT_REASONS = frozenset({SuppressionReason.ASKED_TO_STOP})


def normalise_address(address: str) -> str:
    """One spelling of an address, so a suppression cannot be walked around by capitalisation.

    Deliberately conservative: it folds case and strips surrounding whitespace and nothing else. No
    dot-stripping, no plus-tag removal - those are provider-specific conventions, and treating
    ``a.b@gmail.com`` as ``ab@gmail.com`` would be this module guessing that two addresses are one
    person. Guessing in that direction suppresses somebody who never asked.
    """
    text = str(address or "").strip().casefold()
    if not text:
        raise SuppressionError("a suppression is about an address, and none was given")
    if text.count("@") != 1 or text.startswith("@") or text.endswith("@"):
        raise SuppressionError(f"{address!r} is not an address this application can match on")
    if any(character.isspace() for character in text):
        raise SuppressionError(f"{address!r} contains a space, so it is not one address")
    return text


@dataclass(frozen=True)
class SuppressionEntry:
    """One address that must not be written to, with when and why."""

    address: str
    reason: SuppressionReason
    recorded_at: str
    note: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "address", normalise_address(self.address))
        if not isinstance(self.reason, SuppressionReason):
            raise SuppressionError(f"{self.reason!r} is not a reason this application records")
        if not str(self.recorded_at or "").strip():
            raise SuppressionError("a suppression records when it was made")

    @property
    def is_permanent(self) -> bool:
        """Whether this application may never lift it on its own."""
        return self.reason in PERMANENT_REASONS

    def describe(self) -> str:
        detail = f" ({self.note.strip()})" if self.note.strip() else ""
        permanence = (" This one stands until you lift it yourself."
                      if self.is_permanent else "")
        return (f"{self.address}: {REASON_LABELS[self.reason]}, recorded {self.recorded_at}"
                f"{detail}.{permanence}")


def refusal_message(entry: SuppressionEntry) -> str:
    """What a caller is told when it tries to write to a suppressed address."""
    return (f"Nothing was sent: {entry.address} is on your do-not-contact list because "
            f"{REASON_LABELS[entry.reason]} (recorded {entry.recorded_at}). Remove it there first "
            f"if that is wrong; nothing about this attempt changes it.")
