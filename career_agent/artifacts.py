"""Tailored artifacts: documents made from the candidate's own facts, with their lineage kept.

A tailored artifact is a résumé, cover letter or screening-answer document prepared for one listing
under one role-strategy version. Two rules hold the whole module together, and both come from the
product promise that a generated document must stay **truthful** and **traceable**:

* **Every claim in the content comes from a stored fact.** The builders here only select and arrange
  what the candidate's profile, work history and education already say — filtered and ordered by a
  strategy, aimed at one listing. Nothing is invented: a skill the profile does not state is a *gap*
  (reported, never written into the document), there is no name field in the profile so no name is
  written, and silence about experience produces no experience sentence.
* **The artifact carries the exact basis it was built from.** Alongside the content, the row stores
  the rendered profile facts, which of them were unconfirmed at the time, and the work and education
  records the document was arranged from. :func:`lineage_status` compares that snapshot with what is
  stored *now*, so a caller can refuse to attach an artifact whose source facts have moved on — the
  roadmap's "never silently reuse a stale artifact" — instead of guessing from timestamps.

The store owns the rows (schema 10, append-only); this module owns what the content may claim and
what the lineage says. Email bodies, uploads and any external transfer are not this module's business.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from .core import (
    PROFILE_FACTS, EducationEntry, EmploymentType, JobListing, WorkHistoryEntry, profile_fact_values,
)
from .strategies import RoleStrategy

if TYPE_CHECKING:
    # Type-only: ``store`` imports this module's record types, so a runtime import here would be a
    # cycle. Everything this module does with a store is call its documented read/write methods.
    from .store import CareerStore

#: One generated document. Generous for a résumé, bounded because it is stored, rendered and shown.
MAX_CONTENT_CHARS = 20_000

#: One rendered fact inside a basis snapshot. Rendered values are one-liners (see
#: ``core.profile_fact_values``), so this only needs to catch damage, not Style.
MAX_FACT_VALUE_CHARS = 2_000


class ArtifactError(ValueError):
    """An artifact could not be built or read, with a message written to be shown as-is."""


class ArtifactKind(str, Enum):
    """What kind of document an artifact is. A closed set, so a reader can group by it."""

    TAILORED_RESUME = "tailored_resume"
    COVER_LETTER = "cover_letter"
    SCREENING_ANSWERS = "screening_answers"


KIND_LABELS: dict[ArtifactKind, str] = {
    ArtifactKind.TAILORED_RESUME: "Tailored resume",
    ArtifactKind.COVER_LETTER: "Cover letter",
    ArtifactKind.SCREENING_ANSWERS: "Screening answers",
}


def new_artifact_id() -> str:
    """A fresh artifact identifier. Generated, never typed."""
    return uuid.uuid4().hex


# ---------------------------------------------------------------- the basis: what a document was built from

@dataclass(frozen=True)
class ArtifactBasis:
    """The stored facts one artifact was built from, as they were at build time.

    ``facts`` holds only the facts the profile states, rendered exactly as
    :func:`core.profile_fact_values` renders them, so a lineage comparison compares like with like.
    ``unconfirmed_facts`` names the stated facts that no person had confirmed when this document was
    built — a machine-read fact is a claim until the person says otherwise, and the artifact keeps
    saying so rather than quietly promoting it. ``work`` and ``education`` are the records the
    document arranges; a basis without them cannot later claim they were there.
    """

    facts: dict[str, str] = field(default_factory=dict)
    unconfirmed_facts: frozenset[str] = field(default_factory=frozenset)
    work: tuple[WorkHistoryEntry, ...] = ()
    education: tuple[EducationEntry, ...] = ()

    def __post_init__(self) -> None:
        for name, value in self.facts.items():
            if name not in PROFILE_FACTS:
                raise ArtifactError(
                    f"a basis fact must be one of the profile's own facts, not {name!r}")
            if not isinstance(value, str) or not value.strip():
                raise ArtifactError(f"the basis value for {name} must be non-empty text")
            if len(value) > MAX_FACT_VALUE_CHARS:
                raise ArtifactError(
                    f"the basis value for {name} is {len(value)} characters, over the "
                    f"{MAX_FACT_VALUE_CHARS}-character limit")
        unknown = sorted(set(self.unconfirmed_facts) - set(self.facts))
        if unknown:
            raise ArtifactError(
                f"the basis marks {', '.join(unknown)} as unconfirmed, but the basis does not state "
                "them: an unconfirmed fact is a stated fact nobody confirmed, not a fact on its own")

    def to_json(self) -> dict:
        """The stored form: plain JSON, dates as ISO text, no row identifiers."""
        return {
            "facts": dict(self.facts),
            "unconfirmed": sorted(self.unconfirmed_facts),
            "work": [_plain_work(entry) for entry in self.work],
            "education": [_plain_education(entry) for entry in self.education],
        }

    @classmethod
    def from_json(cls, payload: dict) -> "ArtifactBasis":
        """A stored basis back into a record, refusing what this build cannot read."""
        if not isinstance(payload, dict):
            raise ArtifactError("a stored basis is a JSON object")
        facts = payload.get("facts")
        if not isinstance(facts, dict):
            raise ArtifactError("a stored basis carries its facts as an object")
        unconfirmed = payload.get("unconfirmed", [])
        if not isinstance(unconfirmed, list) or any(not isinstance(item, str) for item in unconfirmed):
            raise ArtifactError("a stored basis carries its unconfirmed facts as a list of names")
        return cls(
            facts={str(name): value for name, value in facts.items()},
            unconfirmed_facts=frozenset(unconfirmed),
            work=tuple(_work_from_plain(item) for item in payload.get("work", [])),
            education=tuple(_education_from_plain(item) for item in payload.get("education", [])),
        )


def _plain_work(entry: WorkHistoryEntry) -> dict:
    """One work record as plain JSON. ``entry_id`` is left out on purpose: it is a row number, not a
    fact, and a delete-and-retype of the same record must not read as a changed history."""
    return {
        "employer": entry.employer,
        "job_title": entry.job_title,
        "start_date": entry.start_date.isoformat(),
        "end_date": entry.end_date.isoformat() if entry.end_date else None,
        "is_current": entry.is_current,
        "employment_type": entry.employment_type.value,
        "summary": entry.summary,
    }


def _plain_education(entry: EducationEntry) -> dict:
    return {
        "institution": entry.institution,
        "qualification": entry.qualification,
        "discipline": entry.discipline,
        "start_date": entry.start_date.isoformat() if entry.start_date else None,
        "completion_date": entry.completion_date.isoformat() if entry.completion_date else None,
        "is_ongoing": entry.is_ongoing,
    }


def _work_from_plain(payload: dict) -> WorkHistoryEntry:
    from datetime import date

    if not isinstance(payload, dict):
        raise ArtifactError("a stored work record is a JSON object")
    try:
        return WorkHistoryEntry(
            employer=str(payload["employer"]),
            job_title=str(payload["job_title"]),
            start_date=date.fromisoformat(payload["start_date"]),
            end_date=date.fromisoformat(payload["end_date"]) if payload.get("end_date") else None,
            is_current=bool(payload.get("is_current", False)),
            employment_type=EmploymentType(payload.get("employment_type",
                                                       EmploymentType.UNKNOWN.value)),
            summary=payload.get("summary"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ArtifactError(f"a stored work record could not be read ({exc})") from exc


def _education_from_plain(payload: dict) -> EducationEntry:
    from datetime import date

    if not isinstance(payload, dict):
        raise ArtifactError("a stored education record is a JSON object")
    try:
        return EducationEntry(
            institution=str(payload["institution"]),
            qualification=str(payload["qualification"]),
            discipline=payload.get("discipline"),
            start_date=date.fromisoformat(payload["start_date"]) if payload.get("start_date") else None,
            completion_date=date.fromisoformat(payload["completion_date"])
            if payload.get("completion_date") else None,
            is_ongoing=bool(payload.get("is_ongoing", False)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ArtifactError(f"a stored education record could not be read ({exc})") from exc


def capture_basis(store: "CareerStore") -> ArtifactBasis:
    """What the store holds *right now*, as the basis a document would be built from. Reads only.

    The history records are captured without their row identifiers: an ``entry_id`` is this
    database's row number, not a fact about the person, and a basis that carried it would read as
    changed after the same record was deleted and retyped - or, worse, would never round-trip
    through the stored JSON, which drops identifiers on purpose.
    """
    from dataclasses import replace as _replace

    profile = store.get_profile()
    if profile is None:
        raise ArtifactError(
            "A tailored artifact is built from the candidate's own facts, and no profile is saved yet. "
            "Save a profile first.")
    values = profile_fact_values(profile)
    facts = {name: value for name, value in values.items() if value}
    confirmed = {entry.fact for entry in store.get_profile_fact_provenance() if entry.is_confirmed}
    return ArtifactBasis(
        facts=facts,
        unconfirmed_facts=frozenset(name for name in facts if name not in confirmed),
        work=tuple(_replace(entry, entry_id=None, created_at=None, updated_at=None)
                   for entry in store.list_work_history()),
        education=tuple(_replace(entry, entry_id=None, created_at=None, updated_at=None)
                        for entry in store.list_education()),
    )


# ---------------------------------------------------------------- the builders: content from the basis only

@dataclass(frozen=True)
class BuiltArtifact:
    """What a builder produced: the document text, and the gaps it refused to paper over.

    ``gaps`` names what the strategy treats as required that the candidate's facts do not state.
    Gaps are reported to the person, never written into the document: a résumé that said
    "this candidate has not stated Python" would be inventing a sentence about them, and one that
    stayed quiet about a missing requirement would hide the gap the matching report should surface.
    """

    content: str
    gaps: tuple[str, ...] = ()


def _overlap(stated: frozenset[str], wanted: frozenset[str]) -> tuple[str, ...]:
    """Stated skills that appear in ``wanted``, case-insensitively, in the strategy's own spelling.

    The comparison key is lowercase; the text kept is the *profile's* spelling, because that is the
    fact the candidate stated. Sorted for a stable document.
    """
    lowered = {value.lower(): value for value in stated}
    return tuple(sorted(lowered[key] for key in {value.lower() for value in wanted} if key in lowered))


def tailored_resume_document(basis: ArtifactBasis, strategy: RoleStrategy) -> BuiltArtifact:
    """A résumé-shaped arrangement of the candidate's own facts, ordered for one role strategy.

    Skills the strategy asks for come first (still only stated ones), then every other stated skill;
    experience and education follow as the person recorded them. Seniority and role family appear
    only as the strategy stated them. The document carries no name, no contact details and no claim
    of any fact the basis does not hold — those sections belong to the person and the sources they
    choose, and this build does not invent them.
    """
    stated = {value.lower(): value for value in
              (basis.facts.get("skills", "").split(", ") if basis.facts.get("skills") else [])}
    stated_skills = frozenset(value for value in stated.values() if value)
    wanted = frozenset(strategy.required_skills | strategy.preferred_skills)
    relevant = _overlap(stated_skills, wanted)
    # "Other skills" is what is left after the relevant section took its own: the same skill must
    # not appear twice, which a case-folded difference would allow.
    other = tuple(sorted(
        value for value in stated_skills
        if value.lower() not in {item.lower() for item in relevant}))

    lines: list[str] = []
    heading = strategy.seniority.strip() if strategy.seniority else ""
    lines.append(f"Tailored resume — {strategy.role_family}"
                 + (f" ({heading})" if heading else ""))
    lines.append("")
    if relevant:
        lines.append("Skills for this role")
        lines.append(", ".join(relevant))
        lines.append("")
    if other:
        lines.append("Other skills")
        lines.append(", ".join(other))
        lines.append("")
    if basis.work:
        lines.append("Experience")
        for entry in basis.work:
            span = entry.start_date.isoformat()
            span += f" – {entry.end_date.isoformat() if entry.end_date else 'present'}"
            lines.append(f"- {entry.job_title} at {entry.employer}, {span}")
            if entry.summary:
                lines.append(f"  {entry.summary}")
        lines.append("")
    if basis.education:
        lines.append("Education")
        for entry in basis.education:
            described = f"- {entry.qualification} at {entry.institution}"
            if entry.discipline:
                described += f", {entry.discipline}"
            lines.append(described)
        lines.append("")

    while lines and not lines[-1]:
        lines.pop()
    gaps = tuple(sorted(
        skill for skill in strategy.required_skills
        if skill.lower() not in {value.lower() for value in stated_skills}))
    return BuiltArtifact(content="\n".join(lines) + "\n", gaps=gaps)


def cover_letter_document(basis: ArtifactBasis, strategy: RoleStrategy,
                          listing: JobListing) -> BuiltArtifact:
    """A letter that names the listing and states only what the candidate's facts say.

    The listing contributes its employer and role title — what the letter is *about*, not a claim
    about the candidate. Experience appears only as a stated number of years; relevant skills are the
    stated ones the strategy asks for. A fact the basis does not hold produces no sentence at all.
    """
    stated = {value.lower(): value for value in
              (basis.facts.get("skills", "").split(", ") if basis.facts.get("skills") else [])}
    stated_skills = frozenset(value for value in stated.values() if value)
    relevant = _overlap(stated_skills, frozenset(strategy.required_skills | strategy.preferred_skills))

    lines: list[str] = [f"Dear hiring team at {listing.employer_name},", ""]
    lines.append(f"I am applying for the {listing.role_title} role.")
    if relevant:
        lines.append("")
        lines.append(f"Skills I can bring to this role: {', '.join(relevant)}.")
    experience = basis.facts.get("experience")
    if experience:
        lines.append("")
        lines.append(f"My profile states {experience} of experience.")
    if basis.work:
        lines.append("")
        latest = basis.work[0]
        lines.append(f"Most recently I have worked as {latest.job_title} at {latest.employer}.")
    lines.append("")
    lines.append("With regards,")
    lines.append("[Your name]")
    return BuiltArtifact(content="\n".join(lines) + "\n")


# ---------------------------------------------------------------- the lineage: what has moved on since

@dataclass(frozen=True)
class LineageReport:
    """Whether an artifact's source facts and strategy are still what the artifact was built under.

    ``is_current`` is true only when nothing changed: the profile facts render exactly as the basis
    holds them, every fact the basis marked unconfirmed is still unconfirmed, the work and education
    records are unchanged, and the referenced strategy version is still that strategy's newest. Any
    other reading is ``False`` — and the ``summary`` lines say which part moved, because "stale"
    without a reason is a status, not an answer.
    """

    artifact_id: str
    facts_changed: tuple[str, ...]
    facts_confirmed_since: tuple[str, ...]
    work_changed: bool
    education_changed: bool
    strategy_version_current: bool

    @property
    def is_current(self) -> bool:
        return not (self.facts_changed or self.facts_confirmed_since
                    or self.work_changed or self.education_changed
                    or not self.strategy_version_current)

    def summary(self) -> tuple[str, ...]:
        lines = []
        if self.facts_changed:
            lines.append(f"facts changed since this was built: {', '.join(self.facts_changed)}")
        if self.facts_confirmed_since:
            lines.append(f"facts confirmed since this was built: "
                         f"{', '.join(self.facts_confirmed_since)}")
        if self.work_changed:
            lines.append("work history changed since this was built")
        if self.education_changed:
            lines.append("education changed since this was built")
        if not self.strategy_version_current:
            lines.append("the strategy has a newer version than the one this was built under")
        if not lines:
            lines.append("every source fact and the strategy version are unchanged")
        return tuple(lines)


def lineage_status(store: "CareerStore", artifact: "TailoredArtifact") -> LineageReport:
    """Compare one artifact's stored basis with what the store holds now. Reads only.

    The comparison is on rendered values, not timestamps: re-saving an unchanged fact is not a
    change, and confirming a fact does not change its value — which is why confirmation is reported
    as its own line. A strategy version never disappears while an artifact references it (the store
    refuses that deletion), so the only strategy question is whether a newer version exists.
    """
    basis = artifact.basis
    profile = store.get_profile()
    current_facts = {name: value for name, value in
                     (profile_fact_values(profile).items() if profile is not None else {})}
    facts_changed = tuple(sorted(
        name for name in basis.facts
        if current_facts.get(name, "") != basis.facts[name]))
    confirmed_now = {entry.fact for entry in store.get_profile_fact_provenance() if entry.is_confirmed}
    facts_confirmed_since = tuple(sorted(
        name for name in basis.unconfirmed_facts if name in confirmed_now and name not in facts_changed))
    strategy = store.get_role_strategy(artifact.strategy_id)
    strategy_version_current = strategy is not None and strategy.version == artifact.strategy_version
    work_changed = [_plain_work(entry) for entry in store.list_work_history()] \
        != [_plain_work(entry) for entry in basis.work]
    education_changed = [_plain_education(entry) for entry in store.list_education()] \
        != [_plain_education(entry) for entry in basis.education]
    return LineageReport(
        artifact_id=artifact.artifact_id,
        facts_changed=facts_changed,
        facts_confirmed_since=facts_confirmed_since,
        work_changed=work_changed,
        education_changed=education_changed,
        strategy_version_current=strategy_version_current,
    )


# ---------------------------------------------------------------- the record: identity + basis + content

@dataclass(frozen=True)
class TailoredArtifact:
    """One stored artifact: what it is for, what it says, and what it was built from."""

    artifact_id: str
    listing_id: str
    strategy_id: str
    strategy_version: int
    kind: ArtifactKind
    content: str
    basis: ArtifactBasis = field(default_factory=ArtifactBasis)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_id, str) or not self.artifact_id.strip():
            raise ArtifactError("an artifact needs an identifier")
        if len(self.artifact_id) > 64:
            raise ArtifactError("an artifact identifier is at most 64 characters")
        for field_name, noun in (("listing_id", "a listing"), ("strategy_id", "a strategy")):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ArtifactError(f"an artifact is made for {noun}; this one names none")
            if len(value) > 200:
                raise ArtifactError(f"the {field_name} is over 200 characters")
        if isinstance(self.strategy_version, bool) or not isinstance(self.strategy_version, int) \
                or self.strategy_version < 1:
            raise ArtifactError("the strategy version an artifact was built under is a whole number "
                                "starting at 1")
        if not isinstance(self.kind, ArtifactKind):
            raise ArtifactError("an artifact is a resume, a cover letter or screening answers")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ArtifactError("an artifact with no content is not an artifact")
        if len(self.content) > MAX_CONTENT_CHARS:
            raise ArtifactError(
                f"the content is {len(self.content)} characters, over the {MAX_CONTENT_CHARS}-character "
                "limit")
        if not isinstance(self.basis, ArtifactBasis):
            raise ArtifactError("an artifact carries the basis it was built from")

    def describe(self) -> str:
        return (f"{KIND_LABELS[self.kind]} for {self.listing_id} "
                f"(strategy {self.strategy_id} version {self.strategy_version})")
