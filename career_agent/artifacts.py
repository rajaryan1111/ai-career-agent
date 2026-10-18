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
    PROFILE_FACTS, EducationEntry, EmploymentType, JobListing, WorkHistoryEntry, document_name_only,
    profile_fact_values,
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
    fact_documents: dict[str, str] = field(default_factory=dict)

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
        uncited = sorted(set(self.fact_documents) - set(self.facts))
        if uncited:
            raise ArtifactError(
                f"the basis cites a document for {', '.join(uncited)}, but the basis does not state "
                "them: a citation describes a fact the document was built from, not a fact on its own")
        for name, document in self.fact_documents.items():
            if not isinstance(document, str):
                raise ArtifactError(f"the document cited for {name} must be a file's name")
            try:
                cleaned = document_name_only(document)
            except ValueError as exc:  # over the length a file name is recorded at
                raise ArtifactError(f"the document cited for {name} is refused: {exc}") from exc
            if cleaned != document:
                # Exactly what provenance recorded, or nothing: a path would put somebody's folders
                # in a row that gets backed up and handed around, and silently trimming it would make
                # the artifact cite a document the store never recorded.
                raise ArtifactError(
                    f"the document cited for {name} must be the file's name as it was recorded, not "
                    "a path or a blank")

    @property
    def source_documents(self) -> tuple[str, ...]:
        """The distinct documents this basis says its facts were read from, in name order.

        Empty means the basis cites no document - either every value was typed, or the row was
        written before artifacts carried citations. It never means "unknown file".
        """
        return tuple(sorted(set(self.fact_documents.values())))

    def to_json(self) -> dict:
        """The stored form: plain JSON, dates as ISO text, no row identifiers."""
        return {
            "facts": dict(self.facts),
            "unconfirmed": sorted(self.unconfirmed_facts),
            "work": [_plain_work(entry) for entry in self.work],
            "education": [_plain_education(entry) for entry in self.education],
            "documents": dict(self.fact_documents),
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
        # Citations arrived after the first artifacts were stored, so their absence is read as "this
        # row cites nothing" rather than as damage: an older row makes no claim about a document.
        documents = payload.get("documents", {})
        if not isinstance(documents, dict):
            raise ArtifactError("a stored basis carries its cited documents as an object")
        return cls(
            facts={str(name): value for name, value in facts.items()},
            unconfirmed_facts=frozenset(unconfirmed),
            work=tuple(_work_from_plain(item) for item in payload.get("work", [])),
            education=tuple(_education_from_plain(item) for item in payload.get("education", [])),
            fact_documents={str(name): document for name, document in documents.items()},
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
    provenance = store.get_profile_fact_provenance()
    confirmed = {entry.fact for entry in provenance if entry.is_confirmed}
    # The citation is copied from what the store recorded beside the fact, for the facts this basis
    # actually states. A fact the person typed names no document and so appears here at all - the
    # basis says "read out of this file" only where the store says exactly that.
    documents = {entry.fact: entry.document_name for entry in provenance
                 if entry.document_name and entry.fact in facts}
    return ArtifactBasis(
        facts=facts,
        unconfirmed_facts=frozenset(name for name in facts if name not in confirmed),
        fact_documents=documents,
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


def _stated_skills(basis: ArtifactBasis) -> frozenset[str]:
    """The skills the basis actually states, in the candidate's own spelling.

    One reader for the one fact the builders lean on hardest: a skill nobody wrote down is not a
    skill, and splitting the rendered value in three places invites three slightly different ideas
    of what counts.
    """
    rendered = basis.facts.get("skills", "")
    return frozenset(value.strip() for value in rendered.split(", ") if value.strip())


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
    stated_skills = _stated_skills(basis)
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
    stated_skills = _stated_skills(basis)
    relevant = _overlap(stated_skills, frozenset(strategy.required_skills | strategy.preferred_skills))

    lines: list[str] = [f"Dear hiring team at {listing.employer_name},", ""]
    lines.append(f"I am applying for the {listing.role_title} role.")
    if relevant:
        lines.append("")
        lines.append(f"Skills I can bring to this role: {', '.join(relevant)}.")
    experience = basis.facts.get("experience")
    if experience:
        # The fact is a number of years (``CandidateProfile.experience_years``); saying so is what
        # makes the sentence true as well as readable. It used to read "1.0 of experience", which
        # was nothing anybody would send to an employer - invisible while no screen could build a
        # cover letter, and the first thing a reader sees now that one can.
        lines.append("")
        years = "year" if experience.strip() == "1" else "years"
        lines.append(f"My profile states {experience} {years} of experience.")
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
    documents_changed: tuple[str, ...] = ()
    cited_documents: tuple[str, ...] = ()

    @property
    def is_current(self) -> bool:
        return not (self.facts_changed or self.facts_confirmed_since
                    or self.work_changed or self.education_changed
                    or self.documents_changed
                    or not self.strategy_version_current)

    def summary(self) -> tuple[str, ...]:
        lines = []
        if self.facts_changed:
            lines.append(f"facts changed since this was built: {', '.join(self.facts_changed)}")
        if self.facts_confirmed_since:
            lines.append(f"facts confirmed since this was built: "
                         f"{', '.join(self.facts_confirmed_since)}")
        if self.documents_changed:
            cited = ", ".join(self.cited_documents) or "a document that is no longer recorded"
            lines.append(
                f"these facts no longer come from the document this was built from ({cited}): "
                + ", ".join(self.documents_changed))
        if self.work_changed:
            lines.append("work history changed since this was built")
        if self.education_changed:
            lines.append("education changed since this was built")
        if not self.strategy_version_current:
            lines.append("the strategy has a newer version than the one this was built under")
        if not lines:
            lines.append("every source fact and the strategy version are unchanged")
        return tuple(lines)


class StaleArtifactError(ArtifactError):
    """An artifact whose sources have moved on was refused, with the lineage that says so.

    Raised by :func:`require_current_artifact` - the one gate any caller passes before an artifact is
    *used* (attached, sent, built on) rather than read. ``report`` carries the structured reason, so
    a caller can offer the person the exact lines instead of a bare "stale".
    """

    def __init__(self, artifact_id: str, report: LineageReport) -> None:
        self.report = report
        reasons = "; ".join(report.summary())
        super().__init__(
            f"The artifact {artifact_id} is no longer built on what is stored: {reasons}. Rebuild it "
            "from the current facts and strategy, or confirm them, before using this document.")


def require_current_artifact(store: "CareerStore", artifact_id: str) -> TailoredArtifact:
    """Return one stored artifact only while every source fact and its strategy version are current.

    This is the enforcement point of the rule the lineage report exists for: an artifact whose
    profile facts, history or strategy have moved on is refused with the named reason and is never
    silently reused. Reading the artifact back stays available through the store - the gate refuses
    *use*, not history.
    """
    artifact = store.get_tailored_artifact(artifact_id)
    if artifact is None:
        raise ArtifactError(f"no artifact with the identifier {artifact_id!r} is stored.")
    report = lineage_status(store, artifact)
    if not report.is_current:
        raise StaleArtifactError(artifact.artifact_id, report)
    return artifact


@dataclass(frozen=True)
class RebuiltArtifact:
    """What a rebuild produced: the new row, the gaps it reported, and what it was built instead of.

    The stale document is *not* touched - artifacts are append-only, and the record of what was
    prepared last week is evidence, not a draft. ``replaced_artifact_id`` only says which document
    this one was rebuilt from, so a window can show the pair.
    """

    artifact: "TailoredArtifact"
    gaps: tuple[str, ...]
    replaced_artifact_id: str


def rebuild_artifact(store: "CareerStore", artifact_id: str) -> RebuiltArtifact:
    """Build the same kind of document again from what the store holds now, as a new row.

    This is the answer to a refused artifact: the sources moved, so the document is made again from
    the current facts and the strategy's newest version, and the stale one stays stored. Screening
    answers are refused - the builders here only restate stored facts, and answers a person wrote
    are not facts this application can regenerate without inventing them.
    """
    stale = store.get_tailored_artifact(artifact_id)
    if stale is None:
        raise ArtifactError(f"no artifact with the identifier {artifact_id!r} is stored.")
    if stale.kind is ArtifactKind.SCREENING_ANSWERS:
        raise ArtifactError(
            "screening answers are written by the person, so this application will not rebuild them: "
            "open the questions again and answer them yourself.")
    listing = store.get_job(stale.listing_id)
    if listing is None:
        raise ArtifactError(
            f"the listing {stale.listing_id!r} this document was prepared for is no longer stored, "
            "so there is nothing to rebuild it for.")
    strategy = store.get_role_strategy(stale.strategy_id)
    if strategy is None:
        raise ArtifactError(
            f"the strategy {stale.strategy_id!r} this document was built under is no longer stored, "
            "so a rebuild would have no preferences to follow.")
    basis = capture_basis(store)
    if stale.kind is ArtifactKind.TAILORED_RESUME:
        built = tailored_resume_document(basis, strategy)
    else:
        built = cover_letter_document(basis, strategy, listing)
    artifact = store.new_tailored_artifact(
        listing_id=stale.listing_id, strategy=strategy, kind=stale.kind, content=built.content,
        basis=basis)
    return RebuiltArtifact(artifact=artifact, gaps=built.gaps, replaced_artifact_id=artifact_id)


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
    # Only the facts this basis *cites* can have a citation that stopped being true. A basis that
    # cites nothing - every value typed, or a row written before citations existed - claims nothing
    # about a document, so nothing about it can have moved. A fact whose value changed is reported
    # as a changed fact and not a second time here.
    documents_now = {entry.fact: entry.document_name for entry in store.get_profile_fact_provenance()}
    documents_changed = tuple(sorted(
        name for name, document in basis.fact_documents.items()
        if name not in facts_changed and documents_now.get(name) != document))
    cited_documents = tuple(sorted({basis.fact_documents[name] for name in documents_changed}))
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
        documents_changed=documents_changed,
        cited_documents=cited_documents,
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

    @property
    def source_documents(self) -> tuple[str, ...]:
        """The documents this artifact's facts were read from, as its basis recorded them."""
        return self.basis.source_documents

    def describe(self) -> str:
        cited = ", ".join(self.source_documents) or "no source document recorded"
        return (f"{KIND_LABELS[self.kind]} for {self.listing_id} "
                f"(strategy {self.strategy_id} version {self.strategy_version}, "
                f"built from {cited})")


# ---------------------------------------------------------------------------------------------
# Building the first one
#
# Everything above could rebuild a document that already existed. Making a *first* one was a thing
# only Python could do, which meant the lineage rules were enforced on documents nobody using the
# application could create. These three functions are the whole path: look at what a build would
# use (writing nothing), store exactly that, and write a copy out to a file.


@dataclass(frozen=True)
class ArtifactPlan:
    """What a build would use and produce, captured without writing anything.

    A plan is reviewed before it is stored, so the thing stored is the thing somebody read. It
    carries the basis it was captured from, which is what makes the "did anything move while you
    were reading?" check possible at the moment of writing.
    """

    listing_id: str
    kind: ArtifactKind
    strategy: RoleStrategy
    basis: ArtifactBasis
    content: str
    gaps: tuple[str, ...] = ()
    #: What *this listing* asks for that the saved facts do not state. Kept apart from ``gaps``,
    #: which is the strategy's requirements: a document is built under a strategy, but it is sent
    #: to one employer, and "your facts do not mention the thing this job asks for" is the sentence
    #: a person needs before they decide to use it. Neither list is ever written into the document.
    listing_gaps: tuple[str, ...] = ()
    duplicate_of: str | None = None

    @property
    def strategy_version(self) -> int:
        return self.strategy.version

    def describe(self) -> tuple[str, ...]:
        """The inputs, as lines a person can read before deciding anything."""
        facts = ", ".join(sorted(self.basis.facts)) or "none"
        unconfirmed = ", ".join(sorted(self.basis.unconfirmed_facts)) or "none"
        documents = ", ".join(sorted({name for name in self.basis.fact_documents.values() if name}))
        lines = [
            f"{KIND_LABELS[self.kind]} for {self.listing_id}, under {self.strategy.name} "
            f"version {self.strategy.version}.",
            f"Facts it would use: {facts}.",
            f"Read from: {documents or 'no source document recorded'}.",
            f"Still unconfirmed: {unconfirmed}.",
            f"Work records: {len(self.basis.work)}; education records: {len(self.basis.education)}.",
        ]
        if self.gaps:
            lines.append(
                "Your saved facts do not state " + ", ".join(self.gaps)
                + ", so the document will not claim them.")
        else:
            lines.append("Nothing the strategy asks for is missing from your saved facts.")
        if self.listing_gaps:
            lines.append(
                "This listing also asks for " + ", ".join(self.listing_gaps)
                + ", which your saved facts do not state either.")
        if self.duplicate_of is not None:
            lines.append(
                f"An identical document is already stored as {self.duplicate_of}; building this "
                f"again would write a second copy of the same text, so it is refused.")
        return tuple(lines)


@dataclass(frozen=True)
class ArtifactExport:
    """What was written out, and what the file says about where it came from."""

    artifact_id: str
    path: str
    characters: int
    provenance: tuple[str, ...]


def plan_artifact(store: "CareerStore", *, listing_id: str, strategy_id: str,
                  kind: ArtifactKind) -> ArtifactPlan:
    """Work out what a document would be built from and what it would say. Writes nothing.

    Every refusal :func:`rebuild_artifact` makes is made here too, and for the same reasons: a
    listing or strategy that is not stored leaves nothing to build from, and screening answers are
    written by the person rather than restated from facts.
    """
    listing = store.get_job(str(listing_id or "").strip())
    if listing is None:
        raise ArtifactError(
            f"the listing {listing_id!r} is not stored, so there is nothing to tailor a document to.")
    strategy = store.get_role_strategy(str(strategy_id or "").strip())
    if strategy is None:
        raise ArtifactError(
            f"the strategy {strategy_id!r} is not stored, so a document built now would have no "
            f"preferences to follow.")
    if kind is ArtifactKind.SCREENING_ANSWERS:
        raise ArtifactError(
            "screening answers are written by the person, so this application will not generate "
            "them: a plausible answer this build invented is exactly the thing it must never write.")
    basis = capture_basis(store)
    if kind is ArtifactKind.TAILORED_RESUME:
        built = tailored_resume_document(basis, strategy)
    else:
        built = cover_letter_document(basis, strategy, listing)
    duplicate = next(
        (stored.artifact_id for stored in store.list_tailored_artifacts(
            listing_id=listing.listing_id, strategy_id=strategy.strategy_id, kind=kind)
         if stored.strategy_version == strategy.version and stored.content == built.content),
        None)
    stated = {value.lower() for value in _stated_skills(basis)}
    listing_gaps = tuple(sorted(
        skill for skill in listing.required_skills
        if skill.lower() not in stated and skill not in built.gaps))
    return ArtifactPlan(listing_id=listing.listing_id, kind=kind, strategy=strategy, basis=basis,
                        content=built.content, gaps=tuple(built.gaps), listing_gaps=listing_gaps,
                        duplicate_of=duplicate)


def store_planned_artifact(store: "CareerStore", plan: ArtifactPlan) -> TailoredArtifact:
    """Store exactly the document that was planned, or refuse and say what moved.

    Three refusals, all of them about the same thing - what is stored must be what somebody read:

    * the **strategy version moved** between the preview and the confirmation, so the document in
      front of them was built under preferences that are no longer current;
    * the **facts moved**: the basis captured for the plan is not what the store holds now, so the
      document would be stored citing a basis it was not built from;
    * an **identical document already exists** for this listing, strategy version and kind - a
      second copy of the same text is not history, it is noise, and the identifier of the one
      already stored is the useful answer.
    """
    current_strategy = store.get_role_strategy(plan.strategy.strategy_id)
    if current_strategy is None:
        raise ArtifactError(
            f"the strategy {plan.strategy.strategy_id!r} is no longer stored, so the document you "
            f"are looking at cannot be recorded against it.")
    if current_strategy.version != plan.strategy.version:
        raise ArtifactError(
            f"{plan.strategy.name} moved to version {current_strategy.version} while this document "
            f"was being read (it was built under version {plan.strategy.version}). Look at it again "
            f"under the current version; nothing was stored.")
    if store.get_job(plan.listing_id) is None:
        raise ArtifactError(
            f"the listing {plan.listing_id!r} is no longer stored, so there is nothing to record "
            f"this document against.")
    if capture_basis(store) != plan.basis:
        raise ArtifactError(
            "your saved facts changed while this document was being read, so storing it would "
            "record a basis it was not built from. Look at it again; nothing was stored.")
    duplicate = next(
        (stored.artifact_id for stored in store.list_tailored_artifacts(
            listing_id=plan.listing_id, strategy_id=plan.strategy.strategy_id, kind=plan.kind)
         if stored.strategy_version == plan.strategy.version and stored.content == plan.content),
        None)
    if duplicate is not None:
        raise ArtifactError(
            f"an identical document is already stored as {duplicate}, built under the same "
            f"strategy version for the same listing. Nothing was stored; use that one, or change "
            f"what it is built from first.")
    return store.new_tailored_artifact(
        listing_id=plan.listing_id, strategy=plan.strategy, kind=plan.kind, content=plan.content,
        basis=plan.basis)


def export_provenance(artifact: TailoredArtifact) -> tuple[str, ...]:
    """The header written above an exported document: where it came from, and what it is not."""
    cited = ", ".join(artifact.source_documents) or "no source document recorded"
    unconfirmed = ", ".join(sorted(artifact.basis.unconfirmed_facts)) or "none"
    return (
        f"{KIND_LABELS[artifact.kind]}",
        f"Document id: {artifact.artifact_id}",
        f"Prepared for listing: {artifact.listing_id}",
        f"Strategy: {artifact.strategy_id} version {artifact.strategy_version}",
        f"Built at: {artifact.created_at}",
        f"Built from: {cited}",
        f"Facts recorded as unconfirmed when this was built: {unconfirmed}",
        "Built only from facts saved in this application. Nothing in it was invented, and nothing "
        "was sent anywhere: this file was written on this machine by the person who asked for it.",
    )


def export_artifact(store: "CareerStore", artifact_id: str, path) -> ArtifactExport:
    """Write one stored document to a new file, with its provenance above it.

    Two refusals matter more than the writing. A document whose facts or strategy have moved on is
    refused by :func:`require_current_artifact` - exporting it would put a stale résumé in a folder
    where nothing says so. And an **existing file is never overwritten**: the one file a person is
    most likely to name by accident is the résumé this document was built from.
    """
    from pathlib import Path as _Path  # noqa: PLC0415 - kept local, this module is store-agnostic
    from .store import PrivateWriteError, create_private_file  # noqa: PLC0415 - avoids a cycle

    artifact = require_current_artifact(store, artifact_id)
    destination = _Path(path)
    if destination.exists():
        raise ArtifactError(
            f"{destination.name} already exists. This application will not write a document over a "
            f"file you already have - the file most likely to be named here by mistake is the "
            f"résumé this was built from. Choose a name that is not in use.")
    if not destination.parent.is_dir():
        raise ArtifactError(
            f"the folder {destination.parent} does not exist, so nothing could be written there.")
    provenance = export_provenance(artifact)
    text = "\n".join(provenance) + "\n\n" + ("-" * 72) + "\n\n" + artifact.content.rstrip("\n") + "\n"
    try:
        descriptor = create_private_file(destination, exclusive=True)
    except PrivateWriteError as exc:
        raise ArtifactError(str(exc)) from exc
    try:
        with open(descriptor, "w", encoding="utf-8", closefd=True) as handle:
            handle.write(text)
    except OSError as exc:
        # The file was created before the write was attempted, so a failure half way through would
        # otherwise leave a truncated "tailored resume" on disk under the name somebody chose, and
        # the same name would then be refused as "already exists" on the next try.
        try:
            destination.unlink()
        except OSError:  # pragma: no cover - the cleanup failing is not the error worth reporting
            pass
        raise ArtifactError(
            f"the document could not be written ({exc}). Nothing was left behind under that "
            f"name.") from exc
    return ArtifactExport(artifact_id=artifact.artifact_id, path=str(destination),
                          characters=len(text), provenance=provenance)
