"""Cross-source job identity: when two listings are the *same* job, and when nobody can say.

Two sources describing one vacancy is the normal case, and acting on it twice - applying twice,
emailing the same team twice - is a real harm to the person this application is for. So this module
answers one question, "are these the same job?", and it answers it in three ways rather than two:
**same**, **different**, and **unknown**. The third is the point. A pair this module cannot prove is
the same job is kept apart, and a pair it cannot prove is different is *not* merged either - it is
reported as something a person can look at.

What counts as proof, in order:

1. the same employer and the same canonical requisition id - the identifier an employer's own system
   issues, which is the only cross-source identifier worth trusting;
2. the same employer application URL after canonicalisation - two sources pointing at one employer
   page;
3. the same source listing URL - the same page, reached twice.

What is deliberately *not* proof: a similar title, a shared employer, a shared location, or any
combination of them. "GenAI Engineer at Example Employer in Delhi" can be two openings on two teams,
and a framework that merges them has silently decided the person may only apply once. Those pairs are
reported as :attr:`IdentityVerdict.UNKNOWN` with the reason, which is a sentence a person can act on.

Nothing here reads the network, opens a gate, or decides to do anything: it compares records that are
already stored.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence

from .core import JobListing, canonicalize_url


class IdentityError(ValueError):
    """A listing cannot be compared, because what it says about itself is not usable."""


class IdentityVerdict(str, Enum):
    """The three answers. ``UNKNOWN`` is a verdict, not a missing one."""

    SAME = "same"        #: proved the same job by an identifier or a shared employer page
    DIFFERENT = "different"  #: proved different - different employers, or different requisitions
    UNKNOWN = "unknown"  #: no evidence either way; the two are kept apart and reported


#: How two listings were proved the same, in the words a person would read.
BASIS_REQUISITION = "the employer's own requisition id"
BASIS_APPLY_URL = "the same employer application page"
BASIS_LISTING_URL = "the same listing page"


@dataclass(frozen=True)
class IdentityDecision:
    """One comparison: the verdict, what proved it, and the sentence to show."""

    verdict: IdentityVerdict
    basis: str
    reason: str

    @property
    def is_same(self) -> bool:
        """True only for a proved match. An unknown is never treated as a match."""
        return self.verdict is IdentityVerdict.SAME

    def describe(self) -> str:
        return f"[{self.verdict.value}] {self.reason}"


def _text(value: str | None) -> str:
    return " ".join((value or "").strip().casefold().split())


def _employer(listing: JobListing) -> str:
    """The employer, normalised for comparison. Blank is not a match for blank."""
    return re.sub(r"[.,]", "", _text(listing.employer_name))


def _requisition(listing: JobListing) -> str:
    return _text(listing.canonical_requisition_id)


def _loose_requisition(listing: JobListing) -> str:
    """The requisition id with separators removed, used only to *doubt* a difference.

    An identifier is opaque, so ``REQ-42`` and ``REQ 42`` are not merged on the strength of
    punctuation - that would be this module deciding two ids are one. But they are not declared
    *different* either: the pair is reported as unknown so a person can look, because the cost of
    getting that wrong is applying to one job twice.
    """
    return re.sub(r"[^a-z0-9]", "", _requisition(listing))


def _apply_url(listing: JobListing) -> str:
    url = (listing.employer_apply_url or "").strip()
    return canonicalize_url(url) if url else ""


def _listing_url(listing: JobListing) -> str:
    url = (listing.source_listing_url or "").strip()
    return canonicalize_url(url) if url else ""


def identity_key(listing: JobListing) -> str:
    """A stable key for one listing: shared across sources only where there is proof.

    With no cross-source evidence the key stays tied to the source that produced it, so two listings
    that cannot be proved the same can never collide by accident. This is the conservative direction:
    the cost of a missed merge is seeing a job twice, and the cost of a wrong merge is not applying.
    """
    if not isinstance(listing, JobListing):
        raise IdentityError("Only a stored job listing can be given an identity key.")
    employer = _employer(listing)
    requisition = _requisition(listing)
    if employer and requisition:
        return f"requisition:{employer}:{requisition}"
    apply_url = _apply_url(listing)
    if apply_url:
        return f"apply:{apply_url}"
    listing_url = _listing_url(listing)
    if listing_url:
        return f"listing:{listing_url}"
    return f"source:{_text(listing.source_id)}:{_text(listing.listing_id)}"


def compare_listings(first: JobListing, second: JobListing) -> IdentityDecision:
    """Whether two listings are the same job, with the evidence or the lack of it."""
    for listing in (first, second):
        if not isinstance(listing, JobListing):
            raise IdentityError("Only stored job listings can be compared.")
    employers = (_employer(first), _employer(second))
    requisitions = (_requisition(first), _requisition(second))
    if all(employers) and employers[0] != employers[1]:
        return IdentityDecision(
            IdentityVerdict.DIFFERENT, "",
            f"different employers: {first.employer_name!r} and {second.employer_name!r}")
    if all(employers) and all(requisitions):
        if requisitions[0] == requisitions[1]:
            return IdentityDecision(
                IdentityVerdict.SAME, BASIS_REQUISITION,
                f"both are {first.employer_name} requisition {first.canonical_requisition_id}")
        if _loose_requisition(first) == _loose_requisition(second):
            return IdentityDecision(
                IdentityVerdict.UNKNOWN, "",
                f"the same employer, and two spellings of what may be one requisition id "
                f"({first.canonical_requisition_id!r} and {second.canonical_requisition_id!r}); "
                f"an identifier is not merged on punctuation, so they are kept apart for you to "
                f"check")
        return IdentityDecision(
            IdentityVerdict.DIFFERENT, "",
            f"the same employer issued two requisition ids: {first.canonical_requisition_id!r} and "
            f"{second.canonical_requisition_id!r}")
    apply_urls = (_apply_url(first), _apply_url(second))
    if all(apply_urls) and apply_urls[0] == apply_urls[1]:
        return IdentityDecision(IdentityVerdict.SAME, BASIS_APPLY_URL,
                                f"both point at {apply_urls[0]}")
    listing_urls = (_listing_url(first), _listing_url(second))
    if all(listing_urls) and listing_urls[0] == listing_urls[1]:
        return IdentityDecision(IdentityVerdict.SAME, BASIS_LISTING_URL,
                                f"both are {listing_urls[0]}")
    same_employer = all(employers) and employers[0] == employers[1]
    if same_employer:
        return IdentityDecision(
            IdentityVerdict.UNKNOWN, "",
            f"both are at {first.employer_name}, and nothing here says whether they are one opening "
            f"or two: no shared requisition id and no shared page. They are kept apart.")
    return IdentityDecision(
        IdentityVerdict.UNKNOWN, "",
        "nothing these two records carry proves they are the same job, so they are kept apart")


@dataclass(frozen=True)
class IdentityGroup:
    """Listings proved to be one job, and where each was seen."""

    identity_key: str
    listing_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    basis: str

    @property
    def is_cross_source(self) -> bool:
        """Whether one job was seen on more than one source."""
        return len(set(self.source_ids)) > 1

    def describe(self) -> str:
        where = ", ".join(self.source_ids)
        if self.is_cross_source:
            return (f"{len(self.listing_ids)} records of one job, seen on {where}, matched by "
                    f"{self.basis}")
        return f"{len(self.listing_ids)} record(s) from {where}"


def group_by_identity(listings: Sequence[JobListing]) -> tuple[IdentityGroup, ...]:
    """Group listings by proved identity, keeping unproved pairs in groups of their own.

    Grouping is by :func:`identity_key` only, so a group is always backed by an identifier or a shared
    page. Two listings with no evidence between them come back as two groups, which is the application
    saying "I do not know", not "these are different".
    """
    order: list[str] = []
    members: dict[str, list[JobListing]] = {}
    for listing in listings:
        key = identity_key(listing)
        if key not in members:
            members[key] = []
            order.append(key)
        members[key].append(listing)
    groups: list[IdentityGroup] = []
    for key in order:
        found = members[key]
        basis = (BASIS_REQUISITION if key.startswith("requisition:")
                 else BASIS_APPLY_URL if key.startswith("apply:")
                 else BASIS_LISTING_URL if key.startswith("listing:")
                 else "one source's own identifier")
        groups.append(IdentityGroup(
            identity_key=key,
            listing_ids=tuple(listing.listing_id for listing in found),
            source_ids=tuple(dict.fromkeys(listing.source_id for listing in found)),
            basis=basis))
    return tuple(groups)


def possible_duplicates(listings: Sequence[JobListing]) -> tuple[tuple[str, str, str], ...]:
    """Pairs a person should look at: same employer, no proof either way, different identity keys.

    These are exactly the pairs this module refuses to merge. Reporting them is the honest half of
    refusing: the application does not pretend the question does not exist, it hands it over.
    """
    pairs: list[tuple[str, str, str]] = []
    for index, first in enumerate(listings):
        for second in listings[index + 1:]:
            if identity_key(first) == identity_key(second):
                continue
            decision = compare_listings(first, second)
            if decision.verdict is IdentityVerdict.UNKNOWN and _employer(first) == _employer(second):
                pairs.append((first.listing_id, second.listing_id, decision.reason))
    return tuple(pairs)


def identity_keys(listings: Iterable[JobListing]) -> tuple[str, ...]:
    """Every distinct identity key in the order first seen. Used for counting, never for merging."""
    seen: dict[str, None] = {}
    for listing in listings:
        seen.setdefault(identity_key(listing), None)
    return tuple(seen)
