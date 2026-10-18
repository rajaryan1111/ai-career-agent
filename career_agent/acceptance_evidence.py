"""What would have to be true, and written down, before a route could ever be switched on.

A gate that is closed "for now" tends to be opened by whoever is in a hurry. This module is the
answer to *what would have to exist first*, written down per route while nobody is in a hurry, so
that enabling a source later is a matter of producing evidence rather than of persuading somebody.

Nothing here enables anything, and nothing here reads a network. Every route below is **outstanding**
on every requirement, which is the honest state of this project: no permission basis has been
obtained for any of the named job platforms, and the four capabilities - discovery, submission,
outbound email and inbox reading - stay independently gated, so evidence for one never opens
another.

Two rules are deliberately part of the data rather than left to judgement:

* no requirement may be satisfied by *interpretation* of a site's terms - it needs a reference to a
  document somebody can read;
* nothing on this list can be met by a technique that circumvents a control (a CAPTCHA, an OTP, a
  rate limit, a login wall). A route that needs circumvention to work is not a route this project
  takes, and that is recorded as a requirement rather than as a hope.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping


class EvidenceError(ValueError):
    """A requirement cannot be stated in a way that could be checked."""


class EvidenceKind(str, Enum):
    """The kinds of evidence a route needs before it may be considered at all."""

    PERMISSION_BASIS = "permission_basis"
    TERMS_REVIEW = "terms_review"
    RATE_LIMITS = "rate_limits"
    IDENTIFIED_CLIENT = "identified_client"
    NO_CIRCUMVENTION = "no_circumvention"
    DATA_MINIMISATION = "data_minimisation"
    TEST_ROUTE = "test_route"
    HUMAN_VERIFICATION = "human_verification"
    WITHDRAWAL_PATH = "withdrawal_path"


#: What each kind means, in the words this project will have to answer for.
EVIDENCE_LABELS: dict[EvidenceKind, str] = {
    EvidenceKind.PERMISSION_BASIS:
        "a written permission basis naming this project: a public API's documented terms, a "
        "partner agreement, or an employer's own stated route - never an inference from silence",
    EvidenceKind.TERMS_REVIEW:
        "a dated review of the route's terms of service and robots policy, with the clauses that "
        "permit automated reading quoted rather than summarised",
    EvidenceKind.RATE_LIMITS:
        "the rate and volume limits the route states, and the limit this application will hold "
        "itself to, which must be the smaller of the two",
    EvidenceKind.IDENTIFIED_CLIENT:
        "an honest client identity: a user agent and contact route that say what this is and who "
        "runs it, never a browser impersonation",
    EvidenceKind.NO_CIRCUMVENTION:
        "a statement, checkable in the code, that the route needs no CAPTCHA solving, no OTP "
        "interception, no login wall bypass and no rate-limit evasion to work",
    EvidenceKind.DATA_MINIMISATION:
        "what fields would be read and kept, why each is needed, and how long it is kept - a "
        "listing's public facts, never a person's profile",
    EvidenceKind.TEST_ROUTE:
        "a sandbox, test account or documented test endpoint, so the first real run is not the "
        "first run",
    EvidenceKind.HUMAN_VERIFICATION:
        "a person's own account of one complete run on the real route, recorded with dates, "
        "counts and what was returned - not a passing test suite",
    EvidenceKind.WITHDRAWAL_PATH:
        "how the route is switched off and how data already read is removed, tested before it is "
        "switched on",
}

#: Every requirement applies to every route; a route may add more, never fewer.
BASELINE: tuple[EvidenceKind, ...] = tuple(EvidenceKind)


@dataclass(frozen=True)
class RouteRequirement:
    """One named route and what it would need. Frozen, and checked at construction."""

    route_id: str
    display_name: str
    #: Why this route is listed, and what is known about it today.
    notes: str
    #: Requirements beyond the baseline, specific to this route.
    additional: tuple[str, ...] = ()
    #: Capabilities this route could ever serve, each gated independently elsewhere.
    capabilities: tuple[str, ...] = ("discovery",)
    kinds: tuple[EvidenceKind, ...] = field(default=BASELINE)

    def __post_init__(self) -> None:
        if not self.route_id.strip() or not self.display_name.strip():
            raise EvidenceError("a route needs an id and a name somebody would recognise")
        if not self.notes.strip():
            raise EvidenceError(f"{self.route_id}: a route records why it is listed")
        missing = [kind for kind in BASELINE if kind not in self.kinds]
        if missing:
            raise EvidenceError(
                f"{self.route_id}: a route may add requirements, never drop them; missing "
                f"{', '.join(kind.value for kind in missing)}")


ROUTE_REQUIREMENTS: tuple[RouteRequirement, ...] = (
    RouteRequirement(
        route_id="linkedin",
        display_name="LinkedIn",
        notes=("Automated access to LinkedIn's pages is prohibited by its user agreement, and its "
               "partner APIs are not open to a project like this one. Nothing here reads it, and "
               "no version of this project will read it without a partner agreement naming it."),
        additional=(
            "a partner agreement or documented API programme admitting this project by name",
            "written confirmation that the agreement covers automated reading on a person's behalf",
        ),
        capabilities=("discovery",),
    ),
    RouteRequirement(
        route_id="unstop",
        display_name="Unstop",
        notes=("No public API documented for job listings, and the terms do not address automated "
               "reading. An inference either way would be a guess, so it stays closed."),
        additional=("a reply from Unstop stating whether automated reading is permitted, and on "
                    "what terms",),
        capabilities=("discovery",),
    ),
    RouteRequirement(
        route_id="internshala",
        display_name="Internshala",
        notes=("Listings sit behind a login for most detail, and applying is an authenticated "
               "action on a person's own account. Submission would mean acting as the person, "
               "which needs its own evidence and its own permission."),
        additional=(
            "a statement of how a person's own credentials would be used, stored and revoked, if "
            "they ever were - no credential is stored by this project today",
            "evidence that applying on a person's behalf is permitted by the platform",
        ),
        capabilities=("discovery", "submission"),
    ),
    RouteRequirement(
        route_id="naukri",
        display_name="Naukri.com",
        notes=("Naukri's terms prohibit automated collection, and its recruiter products are "
               "commercial agreements. Reading it would need a commercial relationship this "
               "project does not have."),
        additional=("a commercial or API agreement permitting automated reading",),
        capabilities=("discovery",),
    ),
    RouteRequirement(
        route_id="employer_site",
        display_name="An employer's own careers page",
        notes=("The most defensible route: an employer publishing its own vacancies usually "
               "intends them to be read. It is still per-employer, because a robots policy and a "
               "terms page are per-site, and 'most employers allow it' authorises nothing."),
        additional=(
            "the specific employer's robots policy and terms, reviewed per site rather than as a "
            "class",
            "a named contact at the employer for questions about automated reading, where the "
            "site offers one",
        ),
        capabilities=("discovery", "submission"),
    ),
    RouteRequirement(
        route_id="ats_provider",
        display_name="An ATS or job-board provider API (Greenhouse, Lever, SmartRecruiters, …)",
        notes=("The route most likely to be permitted in writing, because these providers publish "
               "API terms. Each provider is reviewed separately: one provider's documented terms "
               "say nothing about another's."),
        additional=(
            "the provider's published API terms, with the clause permitting this use quoted",
            "whether the employer whose jobs are read has itself enabled the public endpoint",
        ),
        capabilities=("discovery", "submission"),
    ),
)


def get_route(route_id: str) -> RouteRequirement | None:
    """One route by id, or ``None``. No fuzzy matching: a near-miss is not a permission."""
    wanted = str(route_id or "").strip().casefold()
    for route in ROUTE_REQUIREMENTS:
        if route.route_id == wanted:
            return route
    return None


#: A short name per requirement, for a list or a column heading where the full sentence in
#: :data:`EVIDENCE_LABELS` would not fit. The full sentence stays the definition; these are labels.
EVIDENCE_TITLES: dict[EvidenceKind, str] = {
    EvidenceKind.PERMISSION_BASIS: "Written permission basis",
    EvidenceKind.TERMS_REVIEW: "Terms and robots review",
    EvidenceKind.RATE_LIMITS: "Stated rate and volume limits",
    EvidenceKind.IDENTIFIED_CLIENT: "Honest client identity",
    EvidenceKind.NO_CIRCUMVENTION: "Nothing is circumvented",
    EvidenceKind.DATA_MINIMISATION: "Fields read and kept",
    EvidenceKind.TEST_ROUTE: "A test route to try first",
    EvidenceKind.HUMAN_VERIFICATION: "A person verified one real run",
    EvidenceKind.WITHDRAWAL_PATH: "A way to switch it off",
}


@dataclass(frozen=True)
class RouteEvidence:
    """One piece of evidence a person recorded against one requirement of one route.

    ``reference`` is where the evidence lives - a URL, a file, a message id, a ticket - because a
    claim nobody can go and check is not evidence. ``note`` is what was checked, in the recorder's
    own words. Neither is interpreted by this build: recording evidence enables nothing.
    """

    route_id: str
    kind: EvidenceKind
    recorded_at: str
    reference: str
    note: str = ""


def held_evidence(route_id: str) -> tuple[EvidenceKind, ...]:
    """What evidence this project actually holds for a route today: nothing, for every route.

    A function rather than a constant, because the day one of these is obtained this is where it is
    recorded - with a reference to the document - and every caller starts reporting it at once.
    """
    if get_route(route_id) is None:
        raise EvidenceError(f"{route_id!r} is not a route this project has written requirements for.")
    return ()


def outstanding(route_id: str, *, held: Iterable[EvidenceKind] | None = None) -> tuple[EvidenceKind, ...]:
    """The evidence a route still needs, in a stable order.

    ``held`` is what a caller can show it holds - the rows a person recorded in their own database,
    read by :meth:`career_agent.store.CareerStore.held_evidence_kinds`. Left out, the answer is about
    what *this project* holds in its own code, which is nothing, for every route.
    """
    route = get_route(route_id)
    if route is None:
        raise EvidenceError(f"{route_id!r} is not a route this project has written requirements for.")
    shown = set(held_evidence(route_id)) if held is None else {
        kind if isinstance(kind, EvidenceKind) else EvidenceKind(str(kind)) for kind in held}
    return tuple(kind for kind in route.kinds if kind not in shown)


def route_is_ready(route_id: str, *, held: Iterable[EvidenceKind] | None = None) -> bool:
    """Whether every requirement is met. False for every route in this build, by evidence.

    Being "ready" means every written requirement has something recorded against it. It is not a
    permission and it switches nothing on: the source-quality gate is a decision in code, each
    capability is gated separately, and a ready route still runs nothing until somebody changes
    both deliberately.
    """
    return not outstanding(route_id, held=held)


def describe_route(route_id: str, *, held: Iterable[EvidenceKind] | None = None) -> tuple[str, ...]:
    """One route as lines a person can read, ending in what is still missing."""
    route = get_route(route_id)
    if route is None:
        raise EvidenceError(f"{route_id!r} is not a route this project has written requirements for.")
    lines = [f"{route.display_name} ({route.route_id})", f"  {route.notes}",
             f"  Could ever serve: {', '.join(route.capabilities)} - each gated separately, and "
             f"evidence for one opens none of the others."]
    for extra in route.additional:
        lines.append(f"  Also needs: {extra}")
    missing = outstanding(route.route_id, held=held)
    lines.append(f"  Outstanding: {len(missing)} of {len(route.kinds)} requirement(s).")
    for kind in missing:
        lines.append(f"    - {EVIDENCE_LABELS[kind]}")
    return tuple(lines)


def describe_all(*, held_by_route: Mapping[str, Iterable[EvidenceKind]] | None = None) -> tuple[str, ...]:
    """Every route, with the standing summary first.

    ``held_by_route`` is what a person has recorded in their own database, route by route. Left out,
    the report is about what this project holds in its code: nothing.
    """
    def held_for(route_id: str) -> Iterable[EvidenceKind] | None:
        return None if held_by_route is None else tuple(held_by_route.get(route_id, ()))

    ready = [route.route_id for route in ROUTE_REQUIREMENTS
             if route_is_ready(route.route_id, held=held_for(route.route_id))]
    lines = [
        f"{len(ROUTE_REQUIREMENTS)} route(s) have written acceptance evidence requirements; "
        f"{len(ready)} are ready to be considered for enabling.",
        "Discovery, submission, outbound email and inbox reading are independently gated: evidence "
        "for one of them opens none of the others, and no evidence of any kind opens the "
        "source-quality gate.",
        "",
    ]
    for route in ROUTE_REQUIREMENTS:
        lines.extend(describe_route(route.route_id, held=held_for(route.route_id)))
        lines.append("")
    return tuple(lines[:-1])
