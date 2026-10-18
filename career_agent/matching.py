"""Explainable matching: how well a listing lines up with what a person has and wants.

This module answers one question - "what overlaps, what does not, and what do we not know?" - for any
industry, because it works from the fields the domain model actually has rather than from a vocabulary
about software. A VLSI posting, a mechanical apprenticeship and a data-analytics role are all compared
through the same factors: the skills the listing requires, the experience it asks for, the qualification
it names, and the preferences the person recorded.

Four rules decide what a result may say, and each one is a test:

**Nothing is invented.** A missing value stays unknown. A listing that names no required skills has a
skills factor that is *not applicable* - never a score of zero, and never a perfect score. A person who
recorded no preferred locations gets "unknown" for location agreement, not a guess about where they would
work. The only normalisation applied to text is case, surrounding space and separators: no synonyms are
inferred, because "VHDL" and "Verilog" being different skills is a fact about the work, not a spelling
difference. A caller with a real, evidence-backed list of equivalents can pass ``skill_aliases``; this
module never ships one it cannot defend.

**A number is never a probability.** There is no "match probability" and no "chance of getting hired"
here: the score is the share of the *recorded* preference weight that the listing satisfies, it is always
reported with the coverage that produced it, and every result carries the disclaimer in
:data:`DISCLAIMER`. Ranking is explicitly a review order, not an expectation.

**A thin record cannot look like a good match.** Coverage - how much of the applicable weight had a known
value - is reported beside the score, and a low coverage produces the "not enough information" band and
the "needs more information" recommendation even when the few known factors agree. That is the same rule
the eligibility checker uses, applied to ranking: unknown never passes.

**Eligibility is not overridden.** If the eligibility report says FAIL, the listing is not recommended
whatever the overlap says, and the assessment says which requirement failed. If eligibility is UNKNOWN,
the recommendation says so rather than quietly ranking it. Overlap is not permission to apply.

The domain model has no compensation field yet, so there is no compensation factor: inventing one from
free text would be exactly the fabrication this module refuses. It is listed as outstanding work rather
than approximated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any, Iterable, Mapping, Sequence

from .core import (
    CandidateProfile, Decision, EligibilityReport, JobListing, RequirementResult,
    evaluate_eligibility,
)
from .strategies import RoleStrategy

DISCLAIMER = (
    "This is a comparison of the facts recorded here, not a prediction and not a probability of being "
    "hired. No employer sees this, and an employer's own screening is not modelled."
)

#: Words that must never appear in an assessment, because they make a comparison read as a forecast.
#: A test scans every string this module can produce and fails if one appears.
FORBIDDEN_CLAIMS = ("probability", "chance of", "likely to be hired", "guaranteed", "will be selected")

#: Below this share of the applicable weight, nothing is claimed about how well a listing fits: the
#: band is "not enough information" whatever the known factors said.
COVERAGE_FLOOR_FOR_COMPARISON = 0.5

#: How much of the applicable weight must be known before a reading may be called *strong*. Two thirds
#: was chosen because a bare majority is not a strong comparison: with 60% known, a fifth of the picture
#: is missing, and "strong overlap" would overstate it.
COVERAGE_FOR_STRONG = 2 / 3


class FactorStatus(str, Enum):
    """What one factor's comparison concluded.

    ``NOT_APPLICABLE`` and ``UNKNOWN`` are different states and both are different from ``FAIL``: a
    listing that asks for no particular degree does not fail a qualification check, and a person who has
    not recorded their experience years has not failed an experience check - the comparison simply cannot
    be made, and saying so is the point.
    """

    PASS = "pass"
    PARTIAL = "partial"
    FAIL = "fail"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"

    @property
    def known(self) -> bool:
        """Whether this factor produced a real comparison (PASS, PARTIAL or FAIL)."""
        return self in (FactorStatus.PASS, FactorStatus.PARTIAL, FactorStatus.FAIL)


class Band(str, Enum):
    """How much overlap a score represents, with the coverage caveat built in as its own band."""

    STRONG = "strong_overlap"
    MODERATE = "moderate_overlap"
    WEAK = "weak_overlap"
    INSUFFICIENT = "not_enough_information"


class Recommendation(str, Enum):
    """What to do next, in the app's own words. Never a prediction about the employer."""

    REVIEW = "review_this_listing"
    CHECK_GAPS = "worth_reviewing_but_check_the_gaps"
    LOW_OVERLAP = "little_overlap_recorded"
    NEEDS_INFORMATION = "record_more_information_first"
    BLOCKED = "blocked_by_a_requirement"
    ELIGIBILITY_UNKNOWN = "eligibility_could_not_be_decided"


@dataclass(frozen=True)
class MatchWeights:
    """How much each factor counts, when ranking.

    Weights are the person's priorities made explicit, not quality judgements: raising ``location`` above
    ``skills`` says "being nearby matters more to me than the tooling list", and the assessment shows that
    reasoning rather than hiding it inside a score. All zero is refused, because a comparison that counts
    nothing cannot rank anything.
    """

    skills: float = 3.0
    experience: float = 2.0
    qualification: float = 2.0
    location: float = 1.0
    work_mode: float = 1.0
    role_type: float = 1.0

    def __post_init__(self) -> None:
        for name in ("skills", "experience", "qualification", "location", "work_mode", "role_type"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"The {name} weight must be a number, not {value!r}.")
            if value < 0:
                raise ValueError(f"The {name} weight cannot be negative ({value}).")
            object.__setattr__(self, name, float(value))
        if sum(self.as_dict().values()) <= 0:
            raise ValueError("At least one matching weight must be greater than zero.")

    def as_dict(self) -> dict[str, float]:
        """Every weight by factor name, in one stable order."""
        return {
            "skills": self.skills, "experience": self.experience,
            "qualification": self.qualification, "location": self.location,
            "work_mode": self.work_mode, "role_type": self.role_type,
        }

    def describe(self) -> str:
        """One line naming the weights that are actually in play."""
        parts = [f"{name} {value:g}" for name, value in self.as_dict().items() if value > 0]
        return "weights: " + ", ".join(parts) if parts else "weights: none"


@dataclass(frozen=True)
class MatchFactor:
    """One comparison: what was compared, what came out, and the evidence behind it."""

    name: str
    status: FactorStatus
    explanation: str
    weight: float
    score: float | None = None  #: 0..1, or ``None`` when nothing could be compared
    evidence: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, FactorStatus):
            object.__setattr__(self, "status", FactorStatus(self.status))
        if self.score is not None and not 0.0 <= float(self.score) <= 1.0:
            raise ValueError(f"The {self.name} score must be between 0 and 1, not {self.score}.")
        if self.status.known and self.score is None:
            raise ValueError(f"The {self.name} factor concluded {self.status.value} without a score.")
        if not self.status.known and self.score is not None:
            raise ValueError(
                f"The {self.name} factor has a score but concluded {self.status.value}; a comparison "
                "that could not be made must not carry a number."
            )

    def line(self) -> str:
        """The factor as one line for a person: label, conclusion, reason."""
        return f"{self.name.replace('_', ' ').capitalize()}: {self.explanation}"


@dataclass(frozen=True)
class MatchAssessment:
    """Everything the comparison found, including what it could not find."""

    listing_id: str
    factors: tuple[MatchFactor, ...]
    score: float | None
    coverage: float
    band: Band
    recommendation: Recommendation
    eligibility: Decision
    skill_matches: tuple[str, ...] = ()
    missing_skills: tuple[str, ...] = ()
    unknown_inputs: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    weights: MatchWeights = field(default_factory=MatchWeights)

    @property
    def rank_key(self) -> tuple[int, float, float, str]:
        """The supported ranking order, in three parts, and each one has a reason.

        **Listings that could be compared come first.** A listing with less than
        :data:`COVERAGE_FLOOR_FOR_COMPARISON` of its applicable weight known cannot be placed against a
        listing that was actually compared, however good the few known values look.

        **Then the score**, because among listings that *were* compared, the one that fits the recorded
        preferences better is the one to look at first.

        **Then coverage, then the listing id.** Coverage breaks a score tie in favour of the
        better-understood listing, and the id makes the order stable between runs - the same data
        produces the same order every time, so a person can tell what changed and why.
        """
        return (
            0 if self.coverage >= COVERAGE_FLOOR_FOR_COMPARISON else 1,
            -(self.score if self.score is not None else 0.0),
            -self.coverage,
            self.listing_id,
        )

    def explanation_lines(self) -> tuple[str, ...]:
        """The whole assessment as plain lines, ready for a window or a report."""
        lines = [
            f"Listing: {self.listing_id}",
            (f"Overlap score: {self.score:.0%} of the recorded preferences" if self.score is not None
             else "Overlap score: nothing could be compared"),
            f"How much was known: {self.coverage:.0%} of the applicable weight",
            f"Reading: {self.band.value.replace('_', ' ')}",
            f"Recommended next step: {self.recommendation.value.replace('_', ' ')}",
        ]
        for factor in self.factors:
            lines.append("  " + factor.line())
        if self.missing_skills:
            lines.append("  Missing from your recorded skills: " + ", ".join(self.missing_skills))
        if self.unknown_inputs:
            lines.append("  Not recorded, so not compared: " + ", ".join(self.unknown_inputs))
        lines.extend(self.notes)
        lines.append(DISCLAIMER)
        return tuple(lines)


def normalize_skill(value: str | None) -> str | None:
    """A skill as a comparison key: case, surrounding space and separators folded, nothing else.

    ``"Power-BI"`` and ``"power_bi"`` are the same skill written two ways; ``"VHDL"`` and ``"SystemVerilog"``
    are not, and no rule here will ever make them equal. Abbreviations are matched only when the caller
    supplies an alias for them.
    """
    if value is None:
        return None
    text = " ".join(str(value).split()).casefold()
    for separator in ("-", "_", ".", "/"):
        text = text.replace(separator, " ")
    text = " ".join(text.split())
    return text or None


def _apply_aliases(key: str, aliases: Mapping[str, str]) -> str:
    """Fold a comparison key through the caller's alias table, if it names this key."""
    if not aliases:
        return key
    target = aliases.get(key)
    return normalize_skill(target) or key if target else key


def _normalized_set(values: Iterable[str], aliases: Mapping[str, str]) -> dict[str, str]:
    """Comparison keys mapped back to the wording the person or the listing actually used."""
    result: dict[str, str] = {}
    for value in values:
        key = normalize_skill(value)
        if key is None:
            continue
        result.setdefault(_apply_aliases(key, aliases), str(value).strip())
    return result


def _score_skills(
    profile: CandidateProfile, job: JobListing, aliases: Mapping[str, str],
) -> tuple[MatchFactor, tuple[str, ...], tuple[str, ...]]:
    """Required-skill overlap, or a factor that says none were stated."""
    required = _normalized_set(job.required_skills, aliases)
    if not required:
        return (MatchFactor(
            name="skills", status=FactorStatus.NOT_APPLICABLE, score=None, weight=0.0,
            explanation="the listing does not state required skills, so nothing was compared",
        ), (), ())
    held = _normalized_set(profile.skills, aliases)
    matched = tuple(required[key] for key in sorted(set(required) & set(held)))
    missing = tuple(required[key] for key in sorted(set(required) - set(held)))
    if not held:
        return (MatchFactor(
            name="skills", status=FactorStatus.UNKNOWN, score=None, weight=0.0,
            explanation=(f"the listing states {len(required)} required skill(s) and no skills are "
                         "recorded for you, so nothing could be compared"),
            evidence="required: " + ", ".join(required[key] for key in sorted(required)),
        ), matched, missing)
    ratio = len(matched) / len(required)
    status = (FactorStatus.PASS if not missing
              else FactorStatus.PARTIAL if matched else FactorStatus.FAIL)
    explanation = (f"{len(matched)} of {len(required)} required skill(s) are recorded for you"
                   + (f"; missing: {', '.join(missing)}" if missing else "; none are missing"))
    return (MatchFactor(
        name="skills", status=status, score=round(ratio, 4), weight=0.0, explanation=explanation,
        evidence="matched: " + (", ".join(matched) if matched else "none recorded"),
    ), matched, missing)


def _score_experience(profile: CandidateProfile, job: JobListing) -> MatchFactor:
    """Experience against the listing's range, never a guess about either side."""
    minimum = job.minimum_experience_years
    maximum = job.maximum_experience_years
    if minimum is None and maximum is None:
        return MatchFactor(
            name="experience", status=FactorStatus.NOT_APPLICABLE, score=None, weight=0.0,
            explanation="the listing states no experience requirement, so nothing was compared",
        )
    if profile.experience_years is None:
        return MatchFactor(
            name="experience", status=FactorStatus.UNKNOWN, score=None, weight=0.0,
            explanation=("the listing states an experience requirement and your experience is not "
                         "recorded, so nothing could be compared"),
            evidence=_experience_requirement_text(minimum, maximum),
        )
    years = profile.experience_years
    if not math.isfinite(years):
        # A stored ``nan``/``inf`` is not a number of years: the eligibility checker refuses to let one
        # satisfy a requirement, and a comparison that let one pass here would contradict it.
        return MatchFactor(
            name="experience", status=FactorStatus.UNKNOWN, score=None, weight=0.0,
            explanation=(f"your recorded experience ({years!r}) is not a usable number, so nothing could "
                         "be compared"),
            evidence=_experience_requirement_text(minimum, maximum),
        )
    if minimum is not None and years < minimum:
        gap = round(minimum - years, 4)
        return MatchFactor(
            name="experience", status=FactorStatus.FAIL, score=0.0, weight=0.0,
            explanation=(f"you recorded {years:g} year(s) and the listing asks for at least {minimum:g} "
                         f"({gap:g} short)"),
            evidence=_experience_requirement_text(minimum, maximum),
        )
    if maximum is not None and years > maximum:
        over = round(years - maximum, 4)
        return MatchFactor(
            name="experience", status=FactorStatus.PARTIAL, score=0.5, weight=0.0,
            explanation=(f"you recorded {years:g} year(s) and the listing asks for at most {maximum:g} "
                         f"({over:g} beyond the stated range; the listing's own wording is the source to "
                         "check, because some employers still consider more experience)"),
            evidence=_experience_requirement_text(minimum, maximum),
        )
    return MatchFactor(
        name="experience", status=FactorStatus.PASS, score=1.0, weight=0.0,
        explanation=f"you recorded {years:g} year(s), which is inside the listing's stated range",
        evidence=_experience_requirement_text(minimum, maximum),
    )


def _experience_requirement_text(minimum: float | None, maximum: float | None) -> str:
    """The listing's own requirement, quoted as the evidence for an experience conclusion."""
    if minimum is not None and maximum is not None:
        return f"listing: {minimum:g}-{maximum:g} years"
    if minimum is not None:
        return f"listing: at least {minimum:g} years"
    return f"listing: at most {maximum:g} years"


def _score_qualification(profile: CandidateProfile, job: JobListing) -> MatchFactor:
    """Degree discipline, study status and graduation year, compared as the listing states them."""
    wanted_disciplines = tuple(job.allowed_degree_disciplines or ())
    wanted_statuses = tuple(job.allowed_study_statuses or ())
    wanted_years = tuple(job.allowed_graduation_years or ())
    if not (wanted_disciplines or wanted_statuses or wanted_years):
        return MatchFactor(
            name="qualification", status=FactorStatus.NOT_APPLICABLE, score=None, weight=0.0,
            explanation="the listing names no degree or graduation requirement, so nothing was compared",
        )
    recorded = {
        "degree discipline": profile.degree_discipline,
        "study status": profile.study_status,
        "graduation year": profile.graduation_year,
    }
    checks: list[tuple[str, bool, str]] = []
    unknown: list[str] = []
    if wanted_disciplines:
        if profile.degree_discipline is None:
            unknown.append(f"degree discipline (listing allows {', '.join(wanted_disciplines)})")
        else:
            checks.append(("degree discipline",
                           normalize_skill(profile.degree_discipline) in
                           {normalize_skill(value) for value in wanted_disciplines},
                           f"{profile.degree_discipline} vs allowed {', '.join(wanted_disciplines)}"))
    if wanted_statuses:
        if profile.study_status is None:
            unknown.append(f"study status (listing allows {', '.join(wanted_statuses)})")
        else:
            checks.append(("study status",
                           normalize_skill(profile.study_status) in
                           {normalize_skill(value) for value in wanted_statuses},
                           f"{profile.study_status} vs allowed {', '.join(wanted_statuses)}"))
    if wanted_years:
        if profile.graduation_year is None:
            unknown.append(f"graduation year (listing allows {', '.join(str(y) for y in wanted_years)})")
        else:
            checks.append(("graduation year", profile.graduation_year in wanted_years,
                           f"{profile.graduation_year} vs allowed {', '.join(str(y) for y in wanted_years)}"))
    if not checks:
        return MatchFactor(
            name="qualification", status=FactorStatus.UNKNOWN, score=None, weight=0.0,
            explanation=("the listing states a qualification requirement and none of it is recorded for "
                         "you, so nothing could be compared"),
            evidence="not recorded: " + ", ".join(unknown),
        )
    met = [name for name, ok, _detail in checks if ok]
    unmet = [f"{name} ({detail})" for name, ok, detail in checks if not ok]
    ratio = len(met) / len(checks)
    status = (FactorStatus.PASS if not unmet
              else FactorStatus.PARTIAL if met else FactorStatus.FAIL)
    explanation = f"{len(met)} of {len(checks)} stated qualification check(s) recorded here match"
    if unmet:
        explanation += "; not matching: " + "; ".join(unmet)
    if unknown:
        explanation += "; not recorded, so not compared: " + ", ".join(unknown)
    return MatchFactor(
        name="qualification", status=status, score=round(ratio, 4), weight=0.0,
        explanation=explanation, evidence="; ".join(detail for _name, _ok, detail in checks),
    )


def _score_membership(
    name: str, wanted: frozenset[str], value: str | None, *, unknown_subject: str,
) -> MatchFactor:
    """A single-value preference (work mode, role type) against what the listing states."""
    if not wanted:
        return MatchFactor(
            name=name, status=FactorStatus.NOT_APPLICABLE, score=None, weight=0.0,
            explanation=f"you have not recorded preferred {name.replace('_', ' ')} values, so nothing "
                        "was compared",
        )
    if value is None:
        return MatchFactor(
            name=name, status=FactorStatus.UNKNOWN, score=None, weight=0.0,
            explanation=(f"the listing does not state its {name.replace('_', ' ')} and your preference "
                         "is " + ", ".join(sorted(wanted)) + ", so nothing could be compared"),
        )
    options = {normalize_skill(option) for option in wanted}
    matches = normalize_skill(value) in options
    return MatchFactor(
        name=name,
        status=FactorStatus.PASS if matches else FactorStatus.FAIL,
        score=1.0 if matches else 0.0,
        weight=0.0,
        explanation=(f"the listing says {value}, which is one of your preferred "
                     f"{name.replace('_', ' ')} values" if matches else
                     f"the listing says {value}, which is not among your preferred "
                     f"{name.replace('_', ' ')} values ({', '.join(sorted(wanted))})"),
        evidence=f"listing: {value}",
    )


def _normalize_place(value: str) -> str | None:
    """A location key: case, spacing and punctuation folded, words kept.

    "Bengaluru, India" and "bengaluru india" are the same place written two ways. Countries are not
    inferred from city names and cities are not inferred from countries: "remote" is compared as the word
    the listing used, and a place this module cannot match simply does not match.
    """
    if value is None:
        return None
    text = str(value).casefold()
    for separator in (",", "-", "/", "(", ")"):
        text = text.replace(separator, " ")
    return " ".join(text.split()) or None


def _score_location(profile: CandidateProfile, job: JobListing) -> MatchFactor:
    """Location preference against the listing's own text, with no geographical inference."""
    if not profile.preferred_locations:
        return MatchFactor(
            name="location", status=FactorStatus.NOT_APPLICABLE, score=None, weight=0.0,
            explanation="you have not recorded preferred locations, so nothing was compared",
        )
    wanted = {_normalize_place(place) for place in profile.preferred_locations}
    wanted.discard(None)
    if not job.location_text:
        return MatchFactor(
            name="location", status=FactorStatus.UNKNOWN, score=None, weight=0.0,
            explanation=("the listing does not state a location and your preferences are "
                         + ", ".join(sorted(profile.preferred_locations)) + ", so nothing could be compared"),
        )
    listing_place = _normalize_place(job.location_text)
    if listing_place in wanted:
        return MatchFactor(
            name="location", status=FactorStatus.PASS, score=1.0, weight=0.0,
            explanation=f"the listing's location ({job.location_text}) is one you recorded as preferred",
            evidence=f"listing: {job.location_text}",
        )
    for preferred in sorted(wanted):
        if preferred and (preferred in listing_place or listing_place in preferred):
            return MatchFactor(
                name="location", status=FactorStatus.PASS, score=1.0, weight=0.0,
                explanation=(f"the listing's location ({job.location_text}) contains your preferred "
                             f"place ({preferred})"),
                evidence=f"listing: {job.location_text}",
            )
    return MatchFactor(
        name="location", status=FactorStatus.FAIL, score=0.0, weight=0.0,
        explanation=(f"the listing's location ({job.location_text}) is not among your preferred places "
                     f"({', '.join(sorted(profile.preferred_locations))})"),
        evidence=f"listing: {job.location_text}",
    )


class _CombinedWeights:
    """The caller's ``MatchWeights`` with the strategy factors' own fixed weights beside them.

    Internal to :func:`assess_for_strategy`: the profile's weights object is returned untouched in
    the assessment, and this exists only so one weighted summary can cover both factor sets without
    ``MatchWeights`` - the profile comparison's contract - growing strategy fields.
    """

    def __init__(self, weights: MatchWeights,
                 strategy_factors: Sequence[MatchFactor] = ()) -> None:
        self._weights = weights
        self._strategy_factors = tuple(strategy_factors)

    def as_dict(self) -> dict[str, float]:
        combined = {**self._weights.as_dict()}
        for factor in self._strategy_factors:
            # A preference the strategy does not state is visible in the assessment but carries no
            # weight either way - the honest reading of "I have no preference here".
            combined[factor.name] = (0.0 if factor.status is FactorStatus.NOT_APPLICABLE
                                     else STRATEGY_FACTOR_WEIGHTS.get(factor.name, 0.0))
        return combined


def _weighted_summary(
    factors: Sequence[MatchFactor], weights: MatchWeights | "_CombinedWeights",
) -> tuple[float, float, float | None, Band, tuple[str, ...]]:
    """Total the known factors, and report how much of the applicable weight was known.

    Only factors with a known status contribute to the score. The coverage is the share of applicable
    weight those factors represent, so a single known factor out of six applicable ones cannot produce a
    confident-looking number, and the band says so.
    """
    weight_by_name = weights.as_dict()
    applicable = 0.0
    known_weight = 0.0
    earned = 0.0
    for factor in factors:
        weight = weight_by_name.get(factor.name, 0.0)
        if weight <= 0:
            continue  # the person set this factor's weight to zero: it does not count either way
        if factor.status.known:
            applicable += weight
            known_weight += weight
            earned += weight * float(factor.score or 0.0)
        else:
            applicable += weight
    if applicable <= 0:
        return 0.0, 0.0, None, Band.INSUFFICIENT, ()
    coverage = known_weight / applicable
    score = earned / known_weight if known_weight > 0 else None
    if score is None:
        band = Band.INSUFFICIENT
    elif coverage < COVERAGE_FLOOR_FOR_COMPARISON:
        # Deliberately checked before the score bands: a high score from a thin record is not a strong
        # overlap, it is a small sample, and the band the person reads must say that.
        band = Band.INSUFFICIENT
    elif score >= 0.75 and coverage >= COVERAGE_FOR_STRONG:
        band = Band.STRONG
    elif score >= 0.45:
        band = Band.MODERATE
    else:
        band = Band.WEAK
    return round(score, 4) if score is not None else 0.0, round(coverage, 4), score, band, ()


def _recommendation_for(decision: Decision, score: float | None, band: Band) -> Recommendation:
    """The one ladder from a comparison to a recommendation, so two callers cannot disagree.

    Order matters and is not symmetric: a failed requirement blocks whatever the score says, an
    undecided one stays undecided, and only a comparable score is read at all.
    """
    if score is None:
        return Recommendation.NEEDS_INFORMATION
    if decision is Decision.FAIL:
        return Recommendation.BLOCKED
    if decision is Decision.UNKNOWN:
        return Recommendation.ELIGIBILITY_UNKNOWN
    if band is Band.INSUFFICIENT:
        return Recommendation.NEEDS_INFORMATION
    if band is Band.STRONG:
        return Recommendation.REVIEW
    if band is Band.MODERATE:
        return Recommendation.CHECK_GAPS
    return Recommendation.LOW_OVERLAP


def assess(
    profile: CandidateProfile,
    job: JobListing,
    *,
    weights: MatchWeights | None = None,
    eligibility: EligibilityReport | None = None,
    skill_aliases: Mapping[str, str] | None = None,
) -> MatchAssessment:
    """Compare one listing with one profile and explain the result.

    The eligibility report is evaluated here unless the caller has already done it (the desktop does, so
    the same report is shown in both places). It is used for two things and never for the score: a FAIL
    blocks the recommendation, and UNKNOWN is reported as its own recommendation rather than being
    rounded to "fine".
    """
    weights = weights or MatchWeights()
    aliases = dict(skill_aliases or {})
    if eligibility is not None and not isinstance(eligibility, EligibilityReport):
        # ``assess`` takes the report, not its decision: the explanation of *which* requirement failed is
        # what makes a blocked listing reviewable, and a bare Decision would silently drop it.
        raise TypeError(
            "assess(eligibility=...) takes the whole EligibilityReport (so the failing requirement can "
            f"be named), not {type(eligibility).__name__}."
        )
    report = eligibility if eligibility is not None else evaluate_eligibility(profile, job)
    skill_factor, matched, missing = _score_skills(profile, job, aliases)
    factors = (
        skill_factor,
        _score_experience(profile, job),
        _score_qualification(profile, job),
        _score_location(profile, job),
        _score_membership("work_mode", profile.preferred_work_modes, job.work_mode,
                          unknown_subject="work mode"),
        _score_membership("role_type", profile.preferred_role_types, job.role_type,
                          unknown_subject="role type"),
    )
    _earned, coverage, score, band, _unused = _weighted_summary(factors, weights)

    unknown_inputs: list[str] = []
    for factor in factors:
        if factor.status is FactorStatus.UNKNOWN:
            unknown_inputs.append(factor.name.replace("_", " "))
    notes: list[str] = []
    if score is None:
        notes.append("Nothing could be compared from the facts recorded so far.")
    elif report.decision is Decision.FAIL:
        failed = ", ".join(result.requirement for result in report.failed_requirements)
        notes.append(f"A stated requirement is not met, so this listing is not recommended: {failed}.")
    elif report.decision is Decision.UNKNOWN:
        unknown = ", ".join(result.requirement for result in report.unknown_requirements)
        notes.append(
            f"Eligibility could not be decided from what is recorded ({unknown}), so this listing is "
            "shown as undecided rather than as a match.")
    elif band is Band.INSUFFICIENT:
        notes.append(
            f"Only {coverage:.0%} of the applicable weight had a recorded value, so the overlap is not "
            "enough to rank on. Recording the missing values is what moves this.")
    recommendation = _recommendation_for(report.decision, score, band)
    if missing:
        notes.append(
            "Skills the listing asks for that are not in your recorded skills (they may still be worth "
            "learning or mentioning, and this is not advice that you lack them): "
            + ", ".join(missing) + ".")

    return MatchAssessment(
        listing_id=job.listing_id, factors=factors, score=score, coverage=coverage, band=band,
        recommendation=recommendation, eligibility=report.decision, skill_matches=matched,
        missing_skills=missing, unknown_inputs=tuple(unknown_inputs), notes=tuple(notes), weights=weights,
    )


def rank(
    profile: CandidateProfile,
    jobs: Iterable[JobListing],
    *,
    weights: MatchWeights | None = None,
    skill_aliases: Mapping[str, str] | None = None,
    include_blocked: bool = False,
) -> tuple[MatchAssessment, ...]:
    """Assess every listing and return them best-first, with a stable order and no silent drops.

    Listings whose eligibility is FAIL are excluded by default - they are not candidates for review -
    but they are never *hidden*: they stay in the assessment set with their recommendation saying why,
    and ``include_blocked=True`` returns the whole order. Two listings with the same coverage and score
    are ordered by id, so the same input always produces the same order.
    """
    assessed = [assess(profile, job, weights=weights, skill_aliases=skill_aliases) for job in jobs]
    if not include_blocked:
        chosen = [item for item in assessed if item.recommendation is not Recommendation.BLOCKED]
    else:
        chosen = assessed
    return tuple(sorted(chosen, key=lambda item: item.rank_key))


# ---------------------------------------------------------------- applying a role strategy
#
# A role strategy (``career_agent.strategies``) is the person's statement of intent about one kind of
# search. This section applies it in the only two ways the model supports, and keeps them separate:
#
# * **Hard statements gate before ranking** (``evaluate_strategy_eligibility``): an excluded employer
#   or role title fails outright, and a skill the strategy marks required fails when the *profile*
#   does not state it - the person declared it essential, and silence is not a pass. Every failure
#   names the statement that produced it, so a blocked listing is reviewable, not just rejected.
# * **Preferences rank, and only explainably**: the strategy's places, work modes and preferred
#   skills become their own factors beside the profile's, each with its evidence, each reported as
#   unknown when the listing is silent and not-applicable when the strategy states no preference. A
#   factor the strategy does not state contributes no weight at all - a bare strategy changes no
#   score, which is what "I have no preference here" has to mean.
#
# Two recorded strategy fields are deliberately **not compared**, because the listing domain model
# has no field to compare them against: compensation bounds and employment types. The honest answer
# is the one this module already gives for compensation - "recorded, not compared" - rather than a
# factor invented from free text. Ranking remains a review order, never a prediction.

#: The fixed weight each strategy preference carries. Strategy preferences are one person's stated
#: priorities for one search; they sit beside the profile factors at a deliberate, documented weight
#: rather than inside ``MatchWeights``, which is the profile's own comparison and must not drift.
STRATEGY_FACTOR_WEIGHTS: dict[str, float] = {
    "strategy_locations": 1.0,
    "strategy_work_mode": 1.0,
    "strategy_preferred_skills": 1.0,
}


def _contains_phrase(needles: Iterable[str], haystack: str) -> str | None:
    """The first needle that appears in ``haystack`` as a phrase, matched case- and space-insensitively.

    "Blocked Employer" matches "Blocked Employer Ltd" because that is what ruling an employer out
    means; "Sales Engineer" does not match "Aerospace Systems Engineer" because the words only
    co-occur there by accident. The returned needle is the *strategy's own spelling*, for the evidence.
    """
    def fold(value: str) -> str:
        return " ".join(value.split()).lower()

    folded = fold(haystack)
    for needle in needles:
        if fold(needle) and fold(needle) in folded:
            return needle
    return None


def evaluate_strategy_eligibility(profile: CandidateProfile, job: JobListing,
                                  strategy: RoleStrategy) -> EligibilityReport:
    """The strategy's hard statements about one listing, as requirement results with their reasons.

    Three requirements, always all three (a strategy that states none of a kind passes it with the
    reason it passes): the employer is not excluded, the role title is not excluded, and every skill
    the strategy marks required is stated in the *profile*. A listing whose skills are silent does
    not fail the skills requirement - the requirement here is about the profile's own completeness,
    which the listing cannot decide - and the assessment's notes carry that distinction.
    """
    requirements: list[RequirementResult] = []

    excluded_employer = _contains_phrase(strategy.excluded_employers, job.employer_name)
    if excluded_employer is not None:
        requirements.append(RequirementResult(
            requirement="an employer your strategy has not excluded", decision=Decision.FAIL,
            explanation=f"your strategy rules out {excluded_employer}, and this listing names "
                        f"{job.employer_name}",
            evidence=job.employer_name))
    else:
        requirements.append(RequirementResult(
            requirement="an employer your strategy has not excluded", decision=Decision.PASS,
            explanation="no excluded employer is named in this listing",
            evidence=job.employer_name or None))

    excluded_title = _contains_phrase(strategy.excluded_role_titles, job.role_title)
    if excluded_title is not None:
        requirements.append(RequirementResult(
            requirement="a role title your strategy has not excluded", decision=Decision.FAIL,
            explanation=f"your strategy rules out {excluded_title}, and this listing's title is "
                        f"{job.role_title}",
            evidence=job.role_title))
    else:
        requirements.append(RequirementResult(
            requirement="a role title your strategy has not excluded", decision=Decision.PASS,
            explanation="no excluded role title is named in this listing",
            evidence=job.role_title or None))

    stated = {normalize_skill(skill) for skill in profile.skills} - {None}
    # Named the way the strategy spelled them: the comparison folds case, the explanation must not
    # quietly lower-case the person's own words.
    missing = sorted(
        skill for skill in strategy.required_skills
        if (normalize_skill(skill) or "") not in stated)
    if missing:
        requirements.append(RequirementResult(
            requirement="the skills your strategy requires", decision=Decision.FAIL,
            explanation="your strategy requires " + ", ".join(missing)
                        + ", which your profile does not state",
            evidence=", ".join(sorted(item for item in stated if item)) or None))
    else:
        requirements.append(RequirementResult(
            requirement="the skills your strategy requires", decision=Decision.PASS,
            explanation="your profile states every skill your strategy requires"
            if strategy.required_skills else "your strategy requires no particular skills",
            evidence=", ".join(sorted(strategy.required_skills)) or None))

    decision = Decision.FAIL if any(result.decision is Decision.FAIL for result in requirements) \
        else Decision.PASS
    return EligibilityReport(decision=tuple(requirements) and decision, requirements=tuple(requirements))


def _score_strategy_locations(strategy: RoleStrategy, job: JobListing) -> MatchFactor:
    """Where the strategy wants to work, against where the listing says it is."""
    if not strategy.locations:
        return MatchFactor("strategy_locations", FactorStatus.NOT_APPLICABLE,
                           "your strategy names no places, so location is not compared here", 0.0)
    if not job.location_text:
        return MatchFactor("strategy_locations", FactorStatus.UNKNOWN,
                           "the listing does not state where it is", 1.0)
    matched = _contains_phrase(strategy.locations, job.location_text)
    if matched is not None:
        return MatchFactor("strategy_locations", FactorStatus.PASS,
                           f"the listing is in {job.location_text}, which your strategy names", 1.0,
                           1.0, matched)
    return MatchFactor("strategy_locations", FactorStatus.FAIL,
                       f"the listing is in {job.location_text}, which your strategy does not name",
                       1.0, 0.0, job.location_text)


def _score_strategy_work_mode(strategy: RoleStrategy, job: JobListing) -> MatchFactor:
    """How the strategy wants to work, against what the listing says about the work mode."""
    if not strategy.work_modes:
        return MatchFactor("strategy_work_mode", FactorStatus.NOT_APPLICABLE,
                           "your strategy names no work modes, so this is not compared here", 0.0)
    if not job.work_mode:
        return MatchFactor("strategy_work_mode", FactorStatus.UNKNOWN,
                           "the listing does not state a work mode", 1.0)
    matched = _contains_phrase(strategy.work_modes, job.work_mode)
    if matched is not None:
        return MatchFactor("strategy_work_mode", FactorStatus.PASS,
                           f"the listing's work mode is {job.work_mode}, which your strategy accepts",
                           1.0, 1.0, matched)
    return MatchFactor("strategy_work_mode", FactorStatus.FAIL,
                       f"the listing's work mode is {job.work_mode}, which your strategy does not "
                       "name", 1.0, 0.0, job.work_mode)


def _score_strategy_preferred_skills(strategy: RoleStrategy, job: JobListing) -> MatchFactor:
    """The skills the strategy would like to use, against what the listing asks for.

    The score is the share of the strategy's preferred skills the listing asks for: asking for all of
    them is a pass, asking for none is a fail, and a listing that states no required skills at all is
    unknown rather than failing a comparison nobody could make.
    """
    if not strategy.preferred_skills:
        return MatchFactor("strategy_preferred_skills", FactorStatus.NOT_APPLICABLE,
                           "your strategy names no preferred skills, so this is not compared here",
                           0.0)
    if not job.required_skills:
        return MatchFactor("strategy_preferred_skills", FactorStatus.UNKNOWN,
                           "the listing does not state the skills it asks for", 1.0)
    listing_keys = {normalize_skill(skill) for skill in job.required_skills} - {None}
    asked = sorted(
        skill for skill in strategy.preferred_skills
        if normalize_skill(skill) in listing_keys)
    share = len(asked) / len(strategy.preferred_skills)
    if not asked:
        return MatchFactor("strategy_preferred_skills", FactorStatus.FAIL,
                           "the listing asks for none of the skills your strategy prefers", 1.0,
                           0.0, ", ".join(sorted(job.required_skills)))
    if share >= 1.0:
        return MatchFactor("strategy_preferred_skills", FactorStatus.PASS,
                           "the listing asks for every skill your strategy prefers", 1.0, 1.0,
                           ", ".join(asked))
    return MatchFactor("strategy_preferred_skills", FactorStatus.PARTIAL,
                       f"the listing asks for {len(asked)} of the "
                       f"{len(strategy.preferred_skills)} skills your strategy prefers", 1.0,
                       round(share, 4), ", ".join(asked))


def assess_for_strategy(
    profile: CandidateProfile,
    job: JobListing,
    strategy: RoleStrategy,
    *,
    weights: MatchWeights | None = None,
    skill_aliases: Mapping[str, str] | None = None,
) -> MatchAssessment:
    """Compare one listing with one profile *under one role strategy*.

    The strategy's hard statements gate before anything is ranked (an excluded employer or title, or
    a required skill the profile does not state, blocks with the statement named); its preferences
    become three more explainable factors beside the profile's own six. Everything the profile-only
    comparison says is still here: the same factors, the same evidence, the same disclaimers - the
    strategy adds statements, it never removes them.
    """
    weights = weights or MatchWeights()
    if not isinstance(strategy, RoleStrategy):
        raise TypeError("assess_for_strategy takes a RoleStrategy, not "
                        f"{type(strategy).__name__}.")

    profile_report = evaluate_eligibility(profile, job)
    strategy_report = evaluate_strategy_eligibility(profile, job, strategy)
    requirements = profile_report.requirements + strategy_report.requirements
    if Decision.FAIL in {result.decision for result in requirements}:
        merged = EligibilityReport(decision=Decision.FAIL, requirements=requirements)
    elif Decision.UNKNOWN in {result.decision for result in requirements}:
        merged = EligibilityReport(decision=Decision.UNKNOWN, requirements=requirements)
    else:
        merged = EligibilityReport(decision=Decision.PASS, requirements=requirements)

    base = assess(profile, job, weights=weights, eligibility=merged, skill_aliases=skill_aliases)
    strategy_factors = (
        _score_strategy_locations(strategy, job),
        _score_strategy_work_mode(strategy, job),
        _score_strategy_preferred_skills(strategy, job),
    )
    # Every strategy factor stays in the assessment - a factor that says "your strategy names no
    # places" is an explanation, not a zero - and the combined weights give a not-applicable one no
    # weight at all, so a bare strategy changes neither the score nor the coverage it is read with.
    combined_factors = base.factors + strategy_factors

    combined = _CombinedWeights(weights, strategy_factors)
    _earned, coverage, score, band, _unused = _weighted_summary(combined_factors, combined)
    recommendation = _recommendation_for(merged.decision, score, band)

    notes = list(base.notes)
    for result in strategy_report.failed_requirements:
        # The gate's own explanation names the person's statement and what this listing is: the
        # requirement *name* alone ("an employer your strategy has not excluded") is not reviewable.
        notes.append(result.explanation)
    stated = {normalize_skill(skill) for skill in profile.skills} - {None}
    unmet = sorted(
        skill for skill in strategy.required_skills
        if (normalize_skill(skill) or "") not in stated)
    if unmet:
        notes.append("Your strategy requires " + ", ".join(unmet)
                     + " and your profile does not state any of them; state the ones you have, or "
                       "revise the strategy.")
    described = ", ".join(f"{factor.name.replace('strategy_', '').replace('_', ' ')} "
                          f"({factor.status.value.replace('_', ' ')})" for factor in strategy_factors)
    notes.insert(0, f"Assessed under your strategy '{strategy.name}': {described}.")

    return MatchAssessment(
        listing_id=job.listing_id, factors=combined_factors, score=score, coverage=coverage,
        band=band, recommendation=recommendation, eligibility=merged.decision,
        skill_matches=base.skill_matches, missing_skills=base.missing_skills,
        unknown_inputs=base.unknown_inputs, notes=tuple(notes), weights=weights,
    )


def rank_for_strategy(
    profile: CandidateProfile,
    jobs: Iterable[JobListing],
    strategy: RoleStrategy,
    *,
    weights: MatchWeights | None = None,
    skill_aliases: Mapping[str, str] | None = None,
    include_blocked: bool = False,
) -> tuple[MatchAssessment, ...]:
    """Assess every listing under one strategy and return them best-first, with no silent drops.

    The same contract as :func:`rank`: strategy-blocked listings leave the default order but stay in
    the assessment set saying why, and the order is stable for the same input.
    """
    assessed = [assess_for_strategy(profile, job, strategy, weights=weights,
                                    skill_aliases=skill_aliases) for job in jobs]
    chosen = assessed if include_blocked else [
        item for item in assessed if item.recommendation is not Recommendation.BLOCKED]
    return tuple(sorted(chosen, key=lambda item: item.rank_key))


def describe_ranking(results: Sequence[MatchAssessment]) -> tuple[str, ...]:
    """A ranked list as lines: position, the number, and the caveat that belongs with it."""
    lines = [DISCLAIMER, "Review order (not a prediction):"]
    for position, result in enumerate(results, start=1):
        score = f"{result.score:.0%}" if result.score is not None else "not comparable"
        lines.append(
            f"{position}. {result.listing_id}: {score} overlap, {result.coverage:.0%} of the applicable "
            f"weight known - {result.recommendation.value.replace('_', ' ')}")
    return tuple(lines)


def assessment_to_dict(assessment: MatchAssessment) -> Mapping[str, Any]:
    """The assessment as plain data, for a report, a test or a future export."""
    return {
        "listing_id": assessment.listing_id,
        "score": assessment.score,
        "coverage": assessment.coverage,
        "band": assessment.band.value,
        "recommendation": assessment.recommendation.value,
        "eligibility": assessment.eligibility.value,
        "skill_matches": list(assessment.skill_matches),
        "missing_skills": list(assessment.missing_skills),
        "unknown_inputs": list(assessment.unknown_inputs),
        "factors": [
            {
                "name": factor.name, "status": factor.status.value, "score": factor.score,
                "weight": assessment.weights.as_dict().get(factor.name, 0.0),
                "explanation": factor.explanation, "evidence": factor.evidence,
            }
            for factor in assessment.factors
        ],
        "notes": list(assessment.notes),
        "disclaimer": DISCLAIMER,
    }
