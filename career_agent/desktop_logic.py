"""Tk-free logic shared by the desktop UI and the tests.

This module imports no GUI toolkit: it maps raw form strings to validated domain
objects, decides how a save must behave (new listing versus edit of the selected
listing), resolves the per-user database path, and describes persisted records
back to form strings. The Tkinter layer in ``desktop.py`` stays thin and calls
these functions; no eligibility, deduplication, or persistence rule is duplicated
here — everything is delegated to ``core.py``, ``store.py``, and ``validation.py``.
"""
from __future__ import annotations

import os
import platform
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping

from .core import (
    ActivityKind, ApplicationActivity, Availability, CandidateProfile, FactSource, JobListing,
    PROFILE_FACTS, ProfileFactProvenance, REQUIRED_PROFILE_FACTS, missing_required_profile_facts,
    profile_fact_values,
)
# The résumé reviewer owns the profile vocabulary's user-facing names and the study-status choices, and
# this module reads them from there rather than keeping a second copy: one label list, so the form, the
# review screen and the confirmation table cannot call the same fact three different things.
from .acceptance_evidence import (
    EVIDENCE_LABELS, EVIDENCE_TITLES, ROUTE_REQUIREMENTS, get_route,
)
from .policy import ACTION_LABELS, ActionKind, GlobalPolicy, PolicyDecision
from .sources import (
    SOURCE_DECISIONS, SOURCE_QUALITY_GATE_PASSED, PermissionState, discovery_gate,
    enabled_discovery_sources, get_source_decision, submission_gate,
)
from .resume import PROFILE_FIELD_LABELS, study_status_choices
from .urls import validate_public_http_url
from .validation import optional_float, optional_int, split_values

APPLICATION_FOLDER_NAME = "AI Career Agent"

#: Overrides the platform's per-user data root for this application only, so the database and the
#: start-up note follow it. Absolute values only; see :func:`career_agent_data_root`.
CAREER_AGENT_HOME_ENV = "CAREER_AGENT_HOME"
DATABASE_FILE_NAME = "career_agent.sqlite3"

#: Fields that can change whether a listing is treated as currently open and
#: unchanged, or whether a candidate satisfies a hard eligibility requirement.
#: Values are the labels shown when a user is asked to confirm a consequential edit.
FIELD_LABELS: dict[str, str] = {
    "employer": "employer",
    "title": "role title",
    "source_url": "source listing URL",
    "apply_url": "employer apply URL",
    "requisition": "requisition ID",
    "availability": "availability",
    "scope": "eligibility scope",
    "countries": "allowed countries",
    "degrees": "allowed disciplines",
    "study_statuses": "allowed study statuses",
    "graduation_years": "allowed graduation years",
    "allowed_work_authorizations": "allowed work authorizations",
    "min_exp": "minimum experience",
    "max_exp": "maximum experience",
    "provenance_note": "availability evidence / note",
}
HIGH_CONSEQUENCE_FIELDS: tuple[str, ...] = tuple(FIELD_LABELS)


class JobSaveMode(str, Enum):
    """Explicit intent for a job save: create a separate listing or edit one in place."""

    NEW = "new"
    EDIT = "edit"


@dataclass(frozen=True)
class JobSavePlan:
    """What a save will do, decided without touching the UI or the database."""

    mode: JobSaveMode
    listing_id: str
    changed_consequential_fields: tuple[str, ...] = ()

    @property
    def is_edit(self) -> bool:
        return self.mode is JobSaveMode.EDIT

    @property
    def needs_update_confirmation(self) -> bool:
        """True when an edit changes eligibility-relevant fields and should be confirmed."""
        return self.is_edit and bool(self.changed_consequential_fields)

    def update_confirmation_message(self) -> str:
        labels = ", ".join(FIELD_LABELS.get(key, key) for key in self.changed_consequential_fields)
        return (
            f"This edit changes eligibility-relevant fields ({labels}). "
            "The saved listing keeps its identity but must be re-evaluated "
            "before it can be shortlisted.\n\nSave the change?"
        )


def form_values(variables: Mapping[str, object]) -> dict[str, str]:
    """Read plain strings from Tk StringVars (or any object exposing ``get()``)."""
    return {key: variable.get() for key, variable in variables.items()}  # type: ignore[attr-defined]


def _absolute_root(value: str | None) -> Path | None:
    """An environment-provided data root, or ``None`` when it cannot name a stable location.

    The XDG Base Directory Specification requires these variables to hold absolute paths, and says an
    implementation "should consider the path invalid and ignore it" when one does not. A relative root
    is resolved against whatever directory the app happened to be started from, so the person's own
    database would appear to move (and their profile with it) between launches; the documented
    per-user default is used instead. The same rule is applied to the Windows variable, because a
    relative value there has exactly the same problem.
    """
    if not value:
        return None
    candidate = Path(value)
    return candidate if candidate.is_absolute() else None


def career_agent_data_root(
    *,
    system: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Return the per-user application-data root for the current platform.

    Parameters are injectable so each operating-system branch can be tested without
    being on that operating system.

    ``CAREER_AGENT_HOME`` overrides everything when it holds an absolute path, so someone who keeps
    their data somewhere else (an encrypted volume, a backed-up folder) can say so once instead of
    passing ``--database`` every time. A relative value in ``CAREER_AGENT_HOME``, ``XDG_DATA_HOME`` or
    ``LOCALAPPDATA`` is ignored, per the XDG Base Directory Specification, so the database path never
    depends on the current working directory; the doctor reports an ignored setting and why.
    """
    resolved_system = platform.system() if system is None else system
    environment = os.environ if environ is None else environ
    resolved_home = Path.home() if home is None else Path(home)
    override = _absolute_root(environment.get(CAREER_AGENT_HOME_ENV))
    if override is not None:
        return override
    if resolved_system == "Darwin":
        return resolved_home / "Library" / "Application Support"
    if resolved_system == "Windows":
        return _absolute_root(environment.get("LOCALAPPDATA")) or (resolved_home / "AppData" / "Local")
    return _absolute_root(environment.get("XDG_DATA_HOME")) or (resolved_home / ".local" / "share")


#: Shown when a record carries no usable timestamp. Never replaced with an invented time.
TIMESTAMP_NOT_RECORDED = "not recorded"


def format_stored_timestamp(value: str | None, *, fallback: str = TIMESTAMP_NOT_RECORDED) -> str:
    """Render a stored instant for display, or say exactly why it cannot be shown.

    This is a display helper: it never invents a time and never reinterprets one. The application
    writes UTC timestamps with an explicit offset; those are converted to UTC and rendered
    unambiguously. A value with no offset is timezone-ambiguous, and a value that cannot be parsed
    may have been written by another tool, so both are shown as they are stored with a plain label
    instead of being guessed at, dropped, or silently "corrected".
    """
    text = "" if value is None else str(value).strip()
    if not text:
        return fallback
    # ``fromisoformat`` accepts a trailing ``Z`` only from Python 3.11, so normalise it first: the
    # application runs on 3.10 as well and the same instant must format identically on both.
    parsable = f"{text[:-1]}+00:00" if text.endswith(("Z", "z")) else text
    try:
        moment = datetime.fromisoformat(parsable)
    except ValueError:
        return f"{text} (unrecognised timestamp format)"
    if moment.tzinfo is None:
        return f"{text} (no timezone recorded)"
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def default_data_folder(
    *,
    system: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """The per-user folder the app keeps its own files in; no directory is created here.

    Shared by the database path and by the start-up diagnostic note, so both always point at the
    same folder on every platform. Callers that need the folder to exist create it themselves;
    a diagnostics path in particular must not have directory side effects.
    """
    resolved_system = platform.system() if system is None else system
    folder_name = APPLICATION_FOLDER_NAME if resolved_system in {"Darwin", "Windows"} else "ai-career-agent"
    return career_agent_data_root(system=resolved_system, environ=environ, home=home) / folder_name


def default_database_path(
    *,
    system: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Choose a per-user app-data database path, creating the folder that holds it.

    Creating the folder is this function's one side effect, and it is deliberate: SQLite cannot open a
    database inside a folder that does not exist, so without it a first run would fail before the window
    opens. Nothing is written into the folder here, and candidate data never enters the repository.
    """
    folder = default_data_folder(system=system, environ=environ, home=home)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / DATABASE_FILE_NAME


def _require_http_url(value: str | None, label: str) -> None:
    """Reject anything that is not a plain, public http(s) address (see ``urls.py``)."""
    if value:
        validate_public_http_url(value, label=label)


def _split_or_none(value: str) -> tuple[str, ...] | None:
    values = split_values(value)
    return values or None


#: The kinds offered in the activity dialog, in the order the domain declares them.
ACTIVITY_KIND_CHOICES = tuple(kind.value for kind in ActivityKind)

#: How an activity date is written by this module, and the shape a typed one must have. The shape is
#: checked before parsing: ``date.fromisoformat`` also accepts basic-format and ISO week dates, and a
#: field that promises ``YYYY-MM-DD`` should not quietly accept three other spellings.
ACTIVITY_DATE_FORMAT = "%Y-%m-%d"
ACTIVITY_DATE_HINT = "YYYY-MM-DD"
ACTIVITY_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


def activity_form_values(*, today: date) -> dict[str, str]:
    """The starting values for a new activity entry: a neutral kind and today's date.

    ``note`` is the default on purpose. A neutral label cannot be saved by accident as the claim that
    an application was sent, which is the entry whose meaning matters most.
    """
    return {"kind": ActivityKind.NOTE.value, "occurred_on": today.strftime(ACTIVITY_DATE_FORMAT), "detail": ""}


def build_activity(values: Mapping[str, str]) -> ApplicationActivity:
    """Map the raw form strings to a validated activity entry; raise ``ValueError`` to show.

    The date must be written exactly as ``YYYY-MM-DD``: a date a person typed is not guessed at, so a
    value this cannot read is refused with the accepted form named rather than reinterpreted.
    """
    kind_text = (values.get("kind") or "").strip()
    try:
        kind = ActivityKind(kind_text)
    except ValueError as exc:
        raise ValueError(f"Choose what the entry records: {', '.join(ACTIVITY_KIND_CHOICES)}.") from exc
    raw_date = (values.get("occurred_on") or "").strip()
    if not raw_date:
        raise ValueError(f"Give the entry a date as {ACTIVITY_DATE_HINT}, for example 2026-10-12.")
    if ACTIVITY_DATE_PATTERN.fullmatch(raw_date) is None:
        raise ValueError(
            f"{raw_date!r} is not a date in the form this field expects. Write it as "
            f"{ACTIVITY_DATE_HINT}, for example 2026-10-12."
        )
    try:
        occurred_on = date.fromisoformat(raw_date)
    except ValueError as exc:
        raise ValueError(
            f"{raw_date!r} is not a real calendar date. Write it as {ACTIVITY_DATE_HINT}, for example "
            "2026-10-12."
        ) from exc
    return ApplicationActivity(kind=kind, occurred_on=occurred_on, detail=values.get("detail") or "")


def build_job_listing(values: Mapping[str, str], *, listing_id: str) -> JobListing:
    """Map raw form strings to a validated listing; raise ``ValueError`` with a user-facing message."""
    employer = (values.get("employer") or "").strip()
    title = (values.get("title") or "").strip()
    source_url = (values.get("source_url") or "").strip()
    if not (employer and title and source_url):
        raise ValueError("Employer, role title, and source listing URL are required.")
    _require_http_url(source_url, "Source listing URL")
    apply_url = (values.get("apply_url") or "").strip() or None
    _require_http_url(apply_url, "Employer apply URL")

    availability_text = (values.get("availability") or "").strip() or "unknown"
    try:
        availability = Availability(availability_text)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in Availability)
        raise ValueError(f"Availability must be one of: {allowed}.") from exc

    graduation_years = tuple(
        optional_int(item, "Graduation year") for item in split_values(values.get("graduation_years") or "")
    )
    minimum = optional_float(values.get("min_exp") or "", "Minimum experience")
    maximum = optional_float(values.get("max_exp") or "", "Maximum experience")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError("Minimum experience cannot exceed maximum experience.")

    return JobListing(
        listing_id=listing_id,
        source_id="manual",
        source_name=(values.get("source_name") or "").strip() or "Manual entry",
        source_listing_url=source_url,
        employer_name=employer,
        role_title=title,
        availability_status=availability,
        employer_apply_url=apply_url,
        canonical_requisition_id=(values.get("requisition") or "").strip() or None,
        location_text=(values.get("location") or "").strip() or None,
        work_mode=(values.get("work_mode") or "").strip() or None,
        role_type=(values.get("role_type") or "").strip() or None,
        eligibility_scope=(values.get("scope") or "").strip() or "unknown",
        eligible_countries=split_values(values.get("countries") or ""),
        allowed_work_authorizations=_split_or_none(values.get("allowed_work_authorizations") or ""),
        allowed_degree_disciplines=_split_or_none(values.get("degrees") or ""),
        allowed_study_statuses=_split_or_none(values.get("study_statuses") or ""),
        allowed_graduation_years=graduation_years or None,
        minimum_experience_years=minimum,
        maximum_experience_years=maximum,
        required_skills=frozenset(split_values(values.get("required_skills") or "")),
        provenance_note=(values.get("provenance_note") or "").strip() or None,
    )


def plan_job_save(
    values: Mapping[str, str],
    *,
    mode: JobSaveMode,
    new_listing_id: str,
    selected_job_id: str | None = None,
    baseline: Mapping[str, str] | None = None,
) -> tuple[JobListing, JobSavePlan]:
    """Build the listing to save and the plan describing what the save will do.

    ``NEW`` mode always uses the freshly generated ``new_listing_id``, so an unsaved
    form can never overwrite the currently selected listing. ``EDIT`` mode reuses the
    selected listing's identity and reports which eligibility-relevant fields changed.
    """
    try:
        mode = JobSaveMode(mode)
    except ValueError as exc:
        raise ValueError(f"Unknown job save mode: {mode!r}") from exc
    if mode is JobSaveMode.EDIT:
        if not selected_job_id:
            raise ValueError("Select a saved listing before editing it.")
        listing_id = selected_job_id
    else:
        listing_id = new_listing_id

    job = build_job_listing(values, listing_id=listing_id)
    changed: tuple[str, ...] = ()
    if mode is JobSaveMode.EDIT and baseline is not None:
        current = job_form_values(job)
        changed = tuple(
            key for key in HIGH_CONSEQUENCE_FIELDS
            if (baseline.get(key) or "") != (current.get(key) or "")
        )
    return job, JobSavePlan(mode=mode, listing_id=listing_id, changed_consequential_fields=changed)


def job_form_values(job: JobListing) -> dict[str, str]:
    """Render a saved listing back into the job form's string fields."""
    return {
        "employer": job.employer_name,
        "title": job.role_title,
        "source_name": job.source_name,
        "source_url": job.source_listing_url,
        "apply_url": job.employer_apply_url or "",
        "requisition": job.canonical_requisition_id or "",
        "availability": job.availability_status.value,
        "scope": job.eligibility_scope,
        "work_mode": job.work_mode or "",
        "role_type": job.role_type or "",
        "location": job.location_text or "",
        "countries": ", ".join(job.eligible_countries),
        "degrees": ", ".join(job.allowed_degree_disciplines or []),
        "study_statuses": ", ".join(job.allowed_study_statuses or []),
        "graduation_years": ", ".join(str(item) for item in (job.allowed_graduation_years or [])),
        "allowed_work_authorizations": ", ".join(job.allowed_work_authorizations or []),
        "min_exp": "" if job.minimum_experience_years is None else str(job.minimum_experience_years),
        "max_exp": "" if job.maximum_experience_years is None else str(job.maximum_experience_years),
        "required_skills": ", ".join(sorted(job.required_skills)),
        "provenance_note": job.provenance_note or "",
    }


def build_candidate_profile(values: Mapping[str, str]) -> CandidateProfile:
    """Map raw profile form strings to a validated candidate profile."""
    return CandidateProfile(
        candidate_country=(values.get("country") or "").strip() or None,
        degree_discipline=(values.get("degree") or "").strip() or None,
        study_status=(values.get("study_status") or "").strip() or None,
        graduation_year=optional_int(values.get("graduation_year") or "", "Graduation year"),
        experience_years=optional_float(values.get("experience") or "", "Experience"),
        work_authorization=(values.get("work_authorization") or "").strip() or None,
        skills=frozenset(split_values(values.get("skills") or "")),
        preferred_locations=frozenset(split_values(values.get("locations") or "")),
        preferred_work_modes=frozenset(split_values(values.get("work_modes") or "")),
        preferred_role_types=frozenset(split_values(values.get("role_types") or "")),
    )


def profile_fields_not_matching(profile: CandidateProfile, expected: Mapping[str, str]) -> tuple[str, ...]:
    """Which expected form values the stored profile does not actually hold.

    A save is only reported as successful after the stored profile is read back and compared with what
    was asked for. Comparison is semantic rather than textual, because the form renders a multi-value
    field back in one canonical way (sorted, comma separated) and an integer field as a string: a
    textual comparison would report a failure for a value that was stored correctly, and a false
    failure is as unhelpful as a false success.
    """
    rendered = profile_form_values(profile)
    mismatched: list[str] = []
    for key, wanted in expected.items():
        stored = rendered.get(key, "")
        if key in ("skills", "locations", "work_modes", "role_types"):
            matches = (
                {item.casefold() for item in split_values(wanted)}
                == {item.casefold() for item in split_values(stored)}
            )
        elif key == "graduation_year":
            matches = _compared(optional_int, wanted, stored)
        elif key == "experience":
            matches = _compared(optional_float, wanted, stored)
        else:
            matches = wanted.strip().casefold() == stored.strip().casefold()
        if not matches:
            mismatched.append(key)
    return tuple(mismatched)


def _compared(parse, wanted: str, stored: str) -> bool:
    """Whether two form strings parse to the same value (``False`` when either cannot be parsed)."""
    try:
        return parse(wanted, "value") == parse(stored, "value")
    except ValueError:
        return False


def profile_form_values(profile: CandidateProfile) -> dict[str, str]:
    """Render a saved candidate profile back into the profile form's string fields.

    The rendering itself lives in :func:`career_agent.core.profile_fact_values`, beside the profile it
    describes, because the store compares a stored profile with an incoming one through the same
    function when it decides which facts a save actually changed. One renderer, so a fact cannot be
    "the same value" here and a different one there.
    """
    return profile_fact_values(profile)


# ------------------------------------------------------------------ the saved profile, fact by fact
#
# The profile has always been a list of ten facts; what was missing was a way for the person who owns them
# to see, one line each, what is stored, **where it came from** and **whether they have confirmed it**. This
# section is that read, and the questions for the facts a listing may require that the profile does not
# state. Both are Tk-free on purpose: the window draws them, the tests read them, and neither decides
# anything about the facts themselves - the vocabulary, what is missing and what a confirmation means all
# live in ``core.py`` and ``store.py``.
#
# Three rules hold this section together.
#
# * **Nothing here invents a fact.** The value shown is the value the store renders, a fact with no stored
#   value gets no line at all, and an origin the database does not hold is described as *not recorded* -
#   never as the person's own words.
# * **Nothing here is a second vocabulary.** The labels are the résumé reviewer's own (``PROFILE_FIELD_LABELS``),
#   the questions are keyed by the canonical fact names, and what counts as missing is
#   ``core.missing_required_profile_facts``; a drift test binds all three to the one list.
# * **A preference is not a requirement.** Only the six facts ``evaluate_eligibility`` can be blocked on are
#   ever asked for; skills, locations, work modes and role types are shown and can be confirmed, and are
#   never asked as if a listing required them.

#: The plain-language name of each profile fact, in the form's own key vocabulary. Taken from the résumé
#: reviewer's list rather than written a second time, so "Study status" cannot become "study status" here.
FACT_LABELS: dict[str, str] = dict(PROFILE_FIELD_LABELS)

#: What each origin means, in the words a candidate reads rather than the ones the database stores. The
#: internal enum values (``extracted_from_document`` and friends) are deliberately never shown: they are
#: field names, not explanations.
ORIGIN_NOT_RECORDED = "Not recorded — this profile was saved before the app kept track"
ORIGIN_TYPED = "You typed it in this app"
ORIGIN_FROM_DOCUMENT = "Read out of a document you chose"
ORIGIN_FROM_IMPORT = "Imported from a file you chose"

#: What an unconfirmed fact says. It is a statement about the record, not about the value: nothing here
#: suggests the value is wrong, only that nobody has said it is right.
CONFIRMATION_PENDING = "Not confirmed yet — you have not checked this value"


def fact_label(fact: str) -> str:
    """The plain-language name of one profile fact, for a table cell or a question.

    A name this build does not have a label for is rendered from the key itself rather than raising: a
    screen must never fail because a vocabulary grew, and a cell reading ``pronouns`` is at least honest
    about what it is showing.
    """
    label = FACT_LABELS.get(fact)
    return label if label is not None else fact.replace("_", " ")


def fact_origin_text(entry: ProfileFactProvenance) -> str:
    """Where one stored fact came from, in a sentence a candidate reads.

    A document or an imported file is named by its **name** - the store records no folder, and this
    function has none to show even if it wanted one. An origin the store reports as unknown is described
    as not recorded, because that is what it is: a profile written before origins were kept.
    """
    if entry.source is FactSource.USER_ENTERED:
        return ORIGIN_TYPED
    if entry.source is FactSource.EXTRACTED_FROM_DOCUMENT:
        return (f"{ORIGIN_FROM_DOCUMENT} ({entry.document_name})" if entry.document_name
                else f"{ORIGIN_FROM_DOCUMENT} (its name was not recorded)")
    if entry.source is FactSource.IMPORTED_FROM_FILE:
        return (f"{ORIGIN_FROM_IMPORT} ({entry.document_name})" if entry.document_name
                else f"{ORIGIN_FROM_IMPORT} (its name was not recorded)")
    return ORIGIN_NOT_RECORDED


def fact_confirmation_text(entry: ProfileFactProvenance) -> str:
    """Whether a person has confirmed one stored fact, and when, in a sentence a candidate reads.

    The time is the one the database holds, rendered by the same helper the rest of the window uses: a
    confirmation with no readable time says so rather than showing an invented one.
    """
    if not entry.is_confirmed:
        return CONFIRMATION_PENDING
    return f"Confirmed by you ({format_stored_timestamp(entry.confirmed_at)})"


@dataclass(frozen=True)
class FactReview:
    """One stored fact as the confirmation table shows it: the value, its origin, and its state."""

    fact: str
    label: str
    value: str
    origin: str
    confirmation: str
    confirmed: bool


def profile_fact_review(profile: CandidateProfile | None,
                        provenance: Iterable[ProfileFactProvenance]) -> tuple[FactReview, ...]:
    """One row per fact the stored profile **states**, in the profile's own order.

    A fact with no value has no row: there is nothing stored to show and nothing anybody could confirm.
    A stated fact the given origins say nothing about is described as not recorded rather than assumed to
    be the person's own - the same answer the store gives for a profile written before it kept origins.
    """
    if profile is None:
        return ()
    rendered = profile_fact_values(profile)
    entries = {entry.fact: entry for entry in provenance}
    rows = []
    for fact in PROFILE_FACTS:
        if not rendered[fact]:
            continue
        entry = entries.get(fact) or ProfileFactProvenance(fact=fact, source=FactSource.UNKNOWN)
        rows.append(FactReview(
            fact=fact,
            label=fact_label(fact),
            value=rendered[fact],
            origin=fact_origin_text(entry),
            confirmation=fact_confirmation_text(entry),
            confirmed=entry.is_confirmed,
        ))
    return tuple(rows)


def fact_review_summary(profile: CandidateProfile | None,
                        provenance: Iterable[ProfileFactProvenance]) -> str:
    """One sentence about the whole table: how many facts are stored, confirmed, and still not stated.

    The missing half names the six facts a listing can require, because "not stated" on its own leaves a
    person to guess which answer is worth supplying. It never says a profile is complete: what is complete
    is the set of required facts, which is a fact about those six and about nothing else.
    """
    if profile is None:
        return ("No profile is saved on this device yet. Fill in the form above and save it, or answer "
                "the facts a listing can require with \"Set up missing required facts...\".")
    rows = profile_fact_review(profile, provenance)
    confirmed = sum(1 for row in rows if row.confirmed)
    missing = missing_required_profile_facts(profile)
    parts = [f"{len(rows)} fact(s) stored · {confirmed} confirmed by you · "
             f"{len(rows) - confirmed} not confirmed"]
    parts.append(
        "required facts not stated yet: " + ", ".join(fact_label(fact) for fact in missing)
        if missing else "every fact a listing can require is stated"
    )
    return " · ".join(parts) + "."


@dataclass(frozen=True)
class SetupQuestion:
    """One question in the missing-information setup: which fact, what is asked, and how to answer it."""

    fact: str
    label: str
    question: str
    hint: str
    choices: tuple[str, ...] = ()


#: One question per fact a listing can require, keyed by the canonical fact name. The wording is plain and
#: each hint says what the answer is used for and that a blank is an honest answer; the choices are only
#: where the profile's own field offers them. ``study_status_choices`` is the profile form's list rather
#: than a second one, so an answer this dialog accepts is an answer the form can hold.
_FACT_QUESTIONS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "country": (
        "Which country do you live in?",
        "Write the country you actually live in. A listing that requires a country cannot be checked "
        "without it, and nothing here guesses one from anything else you have entered.",
        (),
    ),
    "degree": (
        "What degree or discipline are you studying, or have you completed?",
        "For example: B.Tech Computer Science, or MSc Data Science. Write what your own record says, not "
        "what a listing asks for.",
        (),
    ),
    "study_status": (
        "Where are you in your studies?",
        "Used to check listings that state a study status. Choose the one that describes you now.",
        study_status_choices(),
    ),
    "graduation_year": (
        "What year do you expect to graduate, or did you graduate?",
        "A four-digit year, for example 2027. Leave it blank if you are not sure what your record says.",
        (),
    ),
    "experience": (
        "How many years of experience do you have?",
        "A number, for example 0 or 1.5. Count only what you can support with a record you could show "
        "somebody.",
        (),
    ),
    "work_authorization": (
        "What work authorization do you hold where you want to work?",
        "Write it exactly as your own document states it: a listing's requirement is compared with this "
        "text word for word, and this app never decides it for you.",
        (),
    ),
}


def setup_question(fact: str) -> SetupQuestion:
    """The one question for a required fact, or a ``KeyError`` if a required fact has no question.

    A required fact with no question would be a fact the setup flow could never ask for, and silently
    skipping it would make the flow look complete while it is not, so this refuses instead of returning a
    placeholder. ``TheSetupQuestionsTests`` binds the mapping to ``REQUIRED_PROFILE_FACTS`` so the refusal
    is reachable only for a name no caller should be passing.
    """
    question, hint, choices = _FACT_QUESTIONS[fact]
    return SetupQuestion(fact=fact, label=fact_label(fact), question=question, hint=hint, choices=choices)


def required_fact_questions(profile: CandidateProfile | None) -> tuple[SetupQuestion, ...]:
    """The questions to ask: one per required fact the stored profile does not state.

    This is the whole of "ask only for what is genuinely missing". It delegates to
    :func:`career_agent.core.missing_required_profile_facts`, so a fact that is stored - whatever its
    origin, whatever its confirmation state - is not asked for again. A missing profile is asked for all
    six, which is what a first run is.
    """
    return tuple(setup_question(fact) for fact in missing_required_profile_facts(profile))


def required_facts_to_confirm(profile: CandidateProfile | None,
                              provenance: Iterable[ProfileFactProvenance]) -> tuple[FactReview, ...]:
    """Rows for the required facts that are stored but not yet confirmed, in the profile's own order.

    These are the facts the setup flow must **not** ask for again and must still put in front of the person:
    the value is already there, so the only open question is whether it is right. Optional preferences are
    excluded - they are choices, and a listing cannot be blocked on them.
    """
    required = set(REQUIRED_PROFILE_FACTS)
    return tuple(row for row in profile_fact_review(profile, provenance)
                 if row.fact in required and not row.confirmed)


# ---------------------------------------------------------------- tailored documents: what a row says

#: What the list shows for a document whose basis names no file. It is not "unknown": a basis without a
#: citation was built from values the person typed, or was stored before artifacts carried citations.
ARTIFACT_NO_DOCUMENT = "no source document recorded"


def artifact_citation_text(documents: Iterable[str]) -> str:
    """The documents an artifact was built from, as one cell of the list."""
    names = [name for name in documents if name]
    return ", ".join(names) if names else ARTIFACT_NO_DOCUMENT


def artifact_state_text(is_current: bool, reasons: Iterable[str]) -> str:
    """The state cell: current, or why this document must be rebuilt before it is used.

    The reasons come from the lineage report, which always has at least one line, so a row never says
    only "stale" - the point of the whole lineage is that the person is told what moved.
    """
    if is_current:
        return "Current"
    return "Rebuild before use — " + "; ".join(reasons)


def artifact_summary_text(total: int, stale: int) -> str:
    """The line above the list: how many documents are stored, and how many cannot be used as they are."""
    if total == 0:
        return ("No tailored document is stored yet. Documents are built from your saved facts under a "
                "role strategy; nothing here is sent anywhere.")
    documents = "1 tailored document" if total == 1 else f"{total} tailored documents"
    if stale == 0:
        return f"{documents} stored; every one still matches the facts and strategy it was built from."
    needs = "1 needs" if stale == 1 else f"{stale} need"
    return (f"{documents} stored; {needs} rebuilding before use because the facts or the strategy "
            "moved on. Nothing is reused silently.")


def artifact_rebuild_text(artifact_id: str, replaced_id: str, gaps: Iterable[str]) -> str:
    """What to say after a rebuild: the new document, the old one, and the gaps it refused to invent."""
    missing = [gap for gap in gaps if gap]
    line = (f"Rebuilt from your current facts as document {artifact_id}; {replaced_id} is kept as "
            "history and was not changed.")
    if missing:
        line += (" Your saved facts do not state " + ", ".join(missing)
                 + ", so the document does not claim them.")
    return line


# ---------------------------------------------------------------- standing authorisation
#
# The window's words for the policy. They live here, Tk-free, for the same reason the artifact
# sentences do: what a person is told before they agree to something is part of the decision, and a
# sentence that is only reachable through a dialog is a sentence nobody tests. Every one of these is a
# description of state or of a proposed change - none of them performs anything, and none of them can
# enable a source, because a source is enabled by the gate and the gate is not here.


def policy_summary_text(policy: GlobalPolicy, version: int) -> str:
    """The line above the list: what is authorised right now, and what that does and does not mean."""
    if version == 0 or policy.is_empty:
        return ("Nothing is authorised. This application performs no discovery, no submission and no "
                "email until you authorise it here, and authorising it here is still not enough on its "
                "own — every source is also switched off in this build.")
    if policy.revoked_at:
        return (f"Authorisation version {version} is withdrawn, so nothing is permitted. What it used to "
                f"cover is kept below so you can see what was withdrawn.")
    if policy.stop_all:
        return (f"Authorisation version {version} is in force but everything is stopped, so nothing is "
                f"permitted until you allow actions again.")
    pairs = "1 permission" if len(policy.allowed) == 1 else f"{len(policy.allowed)} permissions"
    quiet = ""
    if policy.quiet_hours:
        start, end = policy.quiet_hours
        quiet = f" Nothing runs between {start:02d}:00 and {end:02d}:00."
    return (f"Authorisation version {version} holds {pairs}, each with a daily ceiling.{quiet} Every "
            f"source is still switched off in this build, so nothing runs today whatever is listed here.")


def policy_rows(policy: GlobalPolicy) -> tuple[tuple[str, str, str, str], ...]:
    """One row per authorised pair: the source, the action, its daily ceiling, and what applies now.

    A pair with no recorded ceiling is shown as refused rather than unlimited, which is exactly what
    :func:`career_agent.policy.evaluate_policy` does with it - the list and the decision agree.
    """
    rows: list[tuple[str, str, str, str]] = []
    for source_id, action in sorted(policy.allowed, key=lambda pair: (pair[0], pair[1].value)):
        limit = policy.daily_limits.get(action)
        if limit is None:
            ceiling, state = "none recorded", "Refused: a permission without a daily ceiling is not acted on"
        else:
            ceiling = f"{limit} per day"
            state = "Permitted by you"
        if policy.revoked_at:
            state = "Withdrawn"
        elif policy.stop_all:
            state = "Stopped"
        rows.append((source_id, ACTION_LABELS[action], ceiling, state))
    return tuple(rows)


def policy_grant_question(source_id: str, action: ActionKind, limit: int) -> str:
    """What a person is asked before a permission is written. States the limit and the limits of it."""
    return (f"Authorise {ACTION_LABELS[action]} with {source_id}, at most {limit} time(s) a day?\n\n"
            "This is written to your local database as a new version and can be withdrawn at any time. "
            "It does not switch anything on by itself: every source in this build is disabled, so "
            "nothing will run because of this.")


def policy_removal_question(source_id: str, action: ActionKind) -> str:
    """What a person is asked before a permission is taken away again."""
    return (f"Remove your permission for {ACTION_LABELS[action]} with {source_id}?\n\n"
            "A new version is written without it; the version that had it is kept, so what was "
            "permitted when something ran stays readable.")


def policy_revocation_question(pairs: int) -> str:
    """What a person is asked before withdrawing everything at once."""
    counted = "1 permission" if pairs == 1 else f"{pairs} permissions"
    return (f"Withdraw all authorisation now? {counted} stop applying immediately.\n\n"
            "Nothing is deleted: a new version records the withdrawal and the earlier versions stay "
            "readable, so what was permitted at the time something ran can still be seen.")


def policy_stop_question(stopping: bool) -> str:
    """What a person is asked before the stop switch is moved, in whichever direction."""
    if stopping:
        return ("Stop everything now?\n\nWhile this is on, every permission below is refused, whatever "
                "else it says. Your permissions are not deleted and you can allow actions again later.")
    return ("Allow actions again?\n\nThe permissions below start applying again, within their daily "
            "ceilings and quiet hours. Every source in this build is still disabled, so this does not "
            "make anything run.")


def policy_decision_text(decision: PolicyDecision, *, gate_reason: str) -> str:
    """The answer to 'what would happen if I asked for this now?', including the gate's own answer."""
    if decision.allowed:
        return (f"{decision.describe()} The source gate also permits it, so this would run if you asked "
                f"for it.")
    return f"{decision.describe()}\n\nThe source gate says: {gate_reason}"


# ---------------------------------------------------------------- what has been happening

#: How an attempt's state is named on screen. The words matter: an attempt whose outcome was never
#: established is "not established", never "failed", because the two call for different actions.
ATTEMPT_STATE_LABELS: dict[str, str] = {
    "unknown": "outcome not established",
    "performed": "done",
    "failed": "did not happen",
    "refused": "refused by a rule",
}

#: What a person may record as the outcome of an attempt nobody could settle automatically.
RECONCILIATION_CHOICES: tuple[tuple[str, str], ...] = (
    ("performed", "It did happen"),
    ("failed", "It did not happen"),
    ("refused", "It was refused"),
)


def report_summary_text(headline: str, attention_count: int) -> str:
    """The one line above the report: the report's own headline, and where to act on it.

    The headline is used as the reporting module wrote it. Counting the same records again here would
    be a second opinion about them, and the two sentences would eventually disagree - the first version
    of this function did exactly that, and the window said "1 thing(s) from the last day need you. 1
    thing from the last day need you." All this adds is where the things that need a person are.
    """
    headline = headline.strip()
    if attention_count:
        return f"{headline} What needs you is listed below, with what is known about each one."
    return headline


def attempt_rows(records: Iterable[object]) -> tuple[tuple[str, str, str, str, str], ...]:
    """The unresolved-attempt list as rows: id, what was attempted, which job, when, and its state.

    Shows the operation id because that is what a person types into a provider's own records to
    find out what happened; the identity key because one job may be the same job on two boards.
    """
    rows = []
    for record in records:
        state = getattr(getattr(record, "state", None), "value", "")
        rows.append((
            str(getattr(record, "operation_id", "")),
            str(getattr(record, "action", "")),
            str(getattr(record, "identity_key", "")),
            str(getattr(record, "started_at", "")),
            ATTEMPT_STATE_LABELS.get(state, state or "unknown"),
        ))
    return tuple(rows)


def attempt_detail_text(record: object) -> str:
    """What one unresolved attempt says, and what would settle it."""
    if record is None:
        return ("Select an attempt to see what is known about it. An attempt is listed here when "
                "nobody established what happened, which is the only state time cannot settle.")
    state = getattr(getattr(record, "state", None), "value", "unknown")
    detail = str(getattr(record, "detail", "") or "").strip()
    lines = [
        f"{getattr(record, 'operation_id', '')}: {getattr(record, 'action', '')} for "
        f"{getattr(record, 'identity_key', '')}.",
        f"Started {getattr(record, 'started_at', '')}, recorded as "
        f"{ATTEMPT_STATE_LABELS.get(state, state)}.",
    ]
    if detail:
        lines.append(f"What was recorded at the time: {detail}")
    lines.append(
        "Nothing here will settle it on its own: check the provider's own record, then write down "
        "what you found. Until then this blocks any further attempt at the same job.")
    return "\n".join(lines)


def reconciliation_question(operation_id: str, outcome_label: str, evidence: str) -> str:
    """What a person is asked before an unresolved attempt is settled by hand."""
    return (f"Record this outcome?\n\n{operation_id} will be recorded as “{outcome_label}”, with "
            f"your note as the evidence:\n\n{evidence.strip()}\n\nThis is how the block on further "
            f"attempts for this job is lifted, so record what you actually found, not what you "
            f"expect. It cannot be changed back by this application.")


def reconciliation_refusal(evidence: str) -> str | None:
    """Why a reconciliation cannot be recorded yet, or ``None`` when it can.

    Evidence is required because the whole point of the unresolved state is that nobody knows what
    happened; a settlement with no reason attached is a guess wearing a record's clothes.
    """
    if len(str(evidence or "").strip()) < 4:
        return ("Write down what you found first - where you looked and what it said. An outcome "
                "recorded without evidence cannot be told apart from a guess, so nothing was "
                "changed.")
    return None


def notification_summary_text(description: str, decision_description: str,
                              quiet_hours: tuple[int, int] | None) -> str:
    """The notification panel's own summary: the preference, the quiet window, and what is due."""
    lines = [description]
    if quiet_hours:
        lines.append(f"Quiet hours {quiet_hours[0]:02d}:00-{quiet_hours[1]:02d}:00 come from your "
                     f"standing authorisation; nothing is prepared inside them.")
    lines.append(decision_description)
    return " ".join(lines)


def notification_question(cadence_label: str, hour: int, channel_label: str) -> str:
    """What a person is asked before a notification preference is stored."""
    if cadence_label.casefold().startswith("no"):
        return ("Stop preparing reports?\n\nNothing will be prepared for you. The report is still "
                "there whenever you ask for it yourself.")
    return (f"Save this preference?\n\n{cadence_label} from {hour:02d}:00, {channel_label}.\n\n"
            f"Nothing is sent anywhere: this application has no email, no push and no system "
            f"notification. It prepares a report where you can already see it.")


def parse_notification_hour(value: str) -> int:
    """The hour a person typed, or a refusal explaining itself. 0-23, whole numbers only."""
    text = str(value or "").strip()
    if text.endswith(":00"):
        text = text[:-3]
    if not text.isdigit():
        raise ValueError("The hour is a whole number from 0 to 23, such as 9 for nine in the morning.")
    hour = int(text)
    if not 0 <= hour <= 23:
        raise ValueError(f"{hour} is not an hour of the day; use a number from 0 to 23.")
    return hour


# ---------------------------------------------------------------------------------------------
# The do-not-contact list, in the window
#
# Two marks existed before this: a column on the stored contact row, written by the HR contacts tab,
# and the list in ``contact_suppression`` that ``guarded_dispatch`` checks before anything is sent.
# A person who marks somebody "do not contact" means one thing by it, so the window now writes both -
# and these helpers describe the list, including the disagreement a database marked before this build
# will have, rather than hiding it behind a count that looks tidy.

#: The reasons a suppression may carry, in the order the window offers them. The labels are the
#: suppression module's own, so the window cannot invent a sixth reason or reword one of the five.
def suppression_reason_choices() -> tuple[tuple[str, str], ...]:
    """The stored reasons and their labels, in the module's own order."""
    from .suppression import REASON_LABELS  # noqa: PLC0415 - avoids a cycle at import time

    return tuple((reason.value, label) for reason, label in REASON_LABELS.items())


def suppression_rows(entries: Iterable[object]) -> tuple[tuple[str, str, str, str], ...]:
    """One row per suppressed address: the address, why, when, and whether a note is kept with it.

    The note's text is never a column. A reason typed about somebody else is stored on the record and
    shown nowhere else - not in a log, not in an event, not in a list a screen share would carry - and
    "a note is recorded" is all a reader needs to know that one exists.
    """
    from .suppression import REASON_LABELS  # noqa: PLC0415

    rows = []
    for entry in entries:
        reason = getattr(entry, "reason", None)
        # Matched on the stored value rather than on the object: a row read back from a database
        # written by a later build can carry a reason this one has no member for, and a list that
        # raised rather than drawing it would hide an address somebody must not be written to.
        value = getattr(reason, "value", reason)
        label = next((text for member, text in REASON_LABELS.items() if member.value == value),
                     str(value))
        note = (getattr(entry, "note", "") or "").strip()
        rows.append((
            getattr(entry, "address", ""),
            label,
            format_stored_timestamp(getattr(entry, "recorded_at", "")),
            "a note is recorded" if note else "no note",
        ))
    return tuple(rows)


def suppression_summary_text(listed: int, marked_contacts: int, unlisted: int) -> str:
    """The line above the list: what is enforced, what is only annotated, and whether they agree."""
    sentence = (f"{listed} address(es) on the list this application checks before anything may be sent "
                f"· {marked_contacts} stored contact(s) carry the mark.")
    if unlisted:
        return (f"{sentence} {unlisted} marked contact(s) are not on the list: they were marked before "
                "this window wrote both, and marking them again puts them on it.")
    return f"{sentence} Nothing in this build sends anything, either way."


def suppression_lift_refusal(note: str) -> str | None:
    """Why a lift cannot proceed, or ``None``. The store's rule, checked before anything is asked."""
    if len(str(note or "").strip()) < 4:
        return ("Taking a do-not-contact mark off needs a note saying why, of at least four "
                "characters. An entry removed without one cannot be told apart from a mistake, so "
                "nothing was changed.")
    return None


def suppression_mark_question(address_count: int, reason_label: str, permanent: bool) -> str:
    """What the confirmation adds when a mark also goes on the enforced list."""
    question = (f"This also records the address on the do-not-contact list this application checks "
                f"before anything may be sent, as: {reason_label}. Recording an address twice keeps "
                f"the first reason, so an earlier one is never overwritten.")
    if permanent:
        question += (" This reason is the one that is meant to be permanent: nothing expires it, and "
                     "taking it off later needs a note saying why.")
    if address_count:
        question += f" {address_count} address(es) are on that list now."
    return question


def suppression_lift_question(address: str, reason_label: str | None, permanent: bool) -> str:
    """What the confirmation adds when a removal also takes an address off the enforced list."""
    if reason_label is None:
        return ("That address is not on the do-not-contact list this application checks, so only the "
                "mark on the stored contact is removed.")
    question = (f"The address also comes off the do-not-contact list this application checks before "
                f"anything may be sent, where it is recorded as: {reason_label}. Your note is kept "
                f"with the removal.")
    if permanent:
        question += (" That reason says they asked not to be contacted. Removing it is yours to do in "
                     "your own database, and it is not something time or an import may do.")
    return question


# ---------------------------------------------------------------------------------------------
# Conditions on what may be acted on, and the quiet window
#
# The standing authorisation has carried role terms, places, attachment rules, a follow-up limit and
# quiet hours since they were added: stored, enforced, round-tripped, and carried untouched through
# every change the window made. None of them could be *edited* anywhere but Python. These helpers are
# the reading half of putting them on the Permissions & limits tab - parsing what a person typed, and
# saying what is stored - with no Tk and no database in sight.

def parse_condition_terms(value: str, *, noun: str) -> tuple[str, ...]:
    """Split a typed list of terms on commas. Empty means no condition, which means no narrowing.

    Terms are not folded here: the policy value folds them once at its own edge, and a window that
    folded them too would be a second place that decides what two terms are the same.
    """
    terms = [part.strip() for part in str(value or "").replace("\n", ",").split(",")]
    kept = tuple(term for term in terms if term)
    if len(set(term.casefold() for term in kept)) != len(kept):
        raise ValueError(f"the same term is listed twice in the {noun}; list each one once")
    return kept


def parse_attachment_kinds(value: str) -> tuple[str, ...]:
    """Split typed file endings, each one a suffix. ``pdf`` and ``.pdf`` mean the same ending.

    An empty list is not "anything may be attached": with no rule, nothing may be attached at all,
    which is what the policy already enforces and what the window says beside this box.
    """
    kinds = []
    for term in parse_condition_terms(value, noun="attachment rules"):
        ending = term if term.startswith(".") else f".{term}"
        if ending.count(".") != 1 or len(ending) < 2 or any(ch.isspace() for ch in ending):
            raise ValueError(
                f"{term!r} is not a file ending; write endings like .pdf or .docx, separated by commas")
        kinds.append(ending)
    return tuple(kinds)


def parse_follow_up_limit(value: str) -> int | None:
    """A whole number of follow-ups per job, or ``None`` when the box is empty."""
    text = str(value or "").strip()
    if not text:
        return None
    if not text.isdigit():
        raise ValueError(f"{text!r} is not a whole number of follow-ups per job")
    return int(text)


def parse_quiet_hours(start: str, end: str) -> tuple[int, int] | None:
    """The quiet window as a pair of hours, or ``None`` when both boxes are empty.

    One box filled and the other empty is refused rather than guessed: "quiet from 22" with no end
    is either one hour or ten, and a window that picked one would be inventing a rule the person did
    not state. Equal hours are refused for the same reason the policy refuses them.
    """
    first, second = str(start or "").strip(), str(end or "").strip()
    if not first and not second:
        return None
    if not first or not second:
        raise ValueError(
            "quiet hours need both ends: say which hour they start and which hour they end, or "
            "leave both empty for none")
    hours = (parse_notification_hour(first), parse_notification_hour(second))
    if hours[0] == hours[1]:
        raise ValueError(
            "quiet hours that start and end at the same hour say nothing; leave them empty for "
            "none, or name two different hours")
    return hours


def condition_terms_text(terms: Iterable[str]) -> str:
    """How a stored set of terms is written back into a box, so a re-save changes nothing."""
    return ", ".join(sorted(str(term) for term in terms))


def conditions_summary_text(role_terms: Iterable[str], locations: Iterable[str],
                            attachments: Iterable[str], follow_up_limit: int | None,
                            quiet_hours: tuple[int, int] | None) -> str:
    """One line saying what is recorded now, in the words a refusal would use."""
    parts = []
    roles = sorted(role_terms)
    places = sorted(locations)
    endings = sorted(attachments)
    parts.append(f"roles must mention: {', '.join(roles)}" if roles
                 else "no role condition is recorded")
    parts.append(f"places allowed: {', '.join(places)}" if places
                 else "no place condition is recorded")
    parts.append(f"attachments allowed: {', '.join(endings)}" if endings
                 else "no attachment rule is recorded, so nothing may be attached")
    parts.append(f"at most {follow_up_limit} follow-up(s) per job" if follow_up_limit is not None
                 else "no follow-up limit is recorded")
    parts.append(f"quiet from {quiet_hours[0]:02d}:00 to {quiet_hours[1]:02d}:00"
                 if quiet_hours else "no quiet hours are recorded")
    return " · ".join(parts) + "."


def conditions_question(changes: Iterable[str], version: int) -> str:
    """The one confirmation before conditions are stored, naming what changes and what does not."""
    listed = list(changes)
    body = "\n".join(f"  - {change}" for change in listed) if listed else "  - nothing changes"
    return (
        "Record these conditions on what may be acted on?\n\n"
        f"{body}\n\n"
        "Conditions only narrow what is already authorised: they can refuse something that is "
        "otherwise allowed, and they can never permit something that is not. A condition that cannot "
        "be checked - because nothing describes the job being acted on - refuses.\n\n"
        f"This is stored as a new version of the standing authorisation (version {version + 1}); the "
        "version you have now is kept. Nothing is switched on, and nothing runs: every source is "
        "still disabled."
    )


def condition_changes(before: Mapping[str, object], after: Mapping[str, object]) -> tuple[str, ...]:
    """What a save would change, in a person's words, for the confirmation to list."""
    labels = {
        "role_terms": "roles must mention",
        "locations": "places allowed",
        "allowed_attachments": "attachments allowed",
        "follow_up_limit": "follow-ups per job",
        "quiet_hours": "quiet hours",
    }
    def quiet_text(value: object) -> str:
        if not value:
            return "nothing"
        start, end = tuple(value)  # type: ignore[arg-type]
        return f"{start:02d}:00-{end:02d}:00"

    changes = []
    for key, label in labels.items():
        old, new = before.get(key), after.get(key)
        if key == "quiet_hours":
            old_text, new_text = quiet_text(old), quiet_text(new)
            if old_text != new_text:
                changes.append(f"{label}: {old_text} → {new_text}")
            continue
        if isinstance(old, (set, frozenset, tuple, list)) or isinstance(new, (set, frozenset, tuple, list)):
            old_text = condition_terms_text(old or ()) or "nothing"
            new_text = condition_terms_text(new or ()) or "nothing"
        else:
            old_text = "nothing" if old is None else str(old)
            new_text = "nothing" if new is None else str(new)
        if old_text != new_text:
            changes.append(f"{label}: {old_text} → {new_text}")
    return tuple(changes)


# ---------------------------------------------------------------------------------------------
# Sources and acceptance evidence
#
# Two questions that are usually answered by a shrug - "why is nothing being fetched?" and "what
# would it take?" - turned into text a person can read in the window. The first comes from the
# reviewed source decisions and the gates that read them; the second from the written acceptance
# requirements and whatever evidence somebody has recorded in their own database. Neither of these
# functions can enable anything: they produce strings.


def source_rows() -> tuple[tuple[str, str, str, str, str], ...]:
    """One row per reviewed source: id, name, what the review decided, and each gate's answer."""
    rows = []
    for decision in SOURCE_DECISIONS:
        discovery = discovery_gate(decision.source_id)
        submission = submission_gate(decision.source_id)
        rows.append((
            decision.source_id,
            decision.display_name,
            decision.permission_state.value.replace("_", " "),
            "open" if discovery.allowed else "closed",
            "open" if submission.allowed else "closed",
        ))
    return tuple(rows)


def source_summary_text() -> str:
    """The standing answer to "is anything being fetched?", before any row is selected."""
    total = len(SOURCE_DECISIONS)
    approved = sum(1 for decision in SOURCE_DECISIONS
                   if decision.permission_state is PermissionState.APPROVED)
    open_now = sum(1 for decision in SOURCE_DECISIONS if discovery_gate(decision.source_id).allowed)
    enabled = len(enabled_discovery_sources())
    gate = "passed" if SOURCE_QUALITY_GATE_PASSED else "has not passed"
    return (
        f"{total} source(s) reviewed; {approved} approved in principle; {open_now} open for "
        f"discovery right now; {enabled} switched on. The source-quality gate {gate}, and while it "
        f"is closed every source stays closed with it - including the approved ones. Nothing on "
        f"this tab fetches anything."
    )


def source_detail_text(source_id: str) -> str:
    """One source in full: what was decided, on what date, and exactly what is holding it back."""
    decision = get_source_decision(source_id)
    if decision is None:
        return "Select a source to see what was decided about it and why it is closed."
    discovery = discovery_gate(decision.source_id)
    submission = submission_gate(decision.source_id)
    lines = [
        f"{decision.display_name} ({decision.source_id})",
        f"Reviewed {decision.reviewed_on or 'on no recorded date'}; "
        f"{decision.permission_state.value.replace('_', ' ')}.",
        decision.notes,
        "",
        f"Discovery: {'open' if discovery.allowed else 'closed'} - {discovery.reason}",
        f"Submission: {'open' if submission.allowed else 'closed'} - {submission.reason}",
    ]
    if decision.discovery_conditions:
        lines.append("")
        lines.append("Conditions written into the review for reading it:")
        lines.extend(f"  - {condition}" for condition in decision.discovery_conditions)
    if decision.submission_conditions:
        lines.append("")
        lines.append("Conditions written into the review for submitting through it:")
        lines.extend(f"  - {condition}" for condition in decision.submission_conditions)
    if decision.evidence_ref:
        lines.append("")
        lines.append(f"The decision is recorded in {decision.evidence_ref}")
    return "\n".join(lines)


def evidence_route_rows(
        held_by_route: Mapping[str, Iterable[object]]) -> tuple[tuple[str, str, str, str], ...]:
    """One row per route: id, name, how much of its requirement is recorded, and whether it is met."""
    rows = []
    for route in ROUTE_REQUIREMENTS:
        held = tuple(held_by_route.get(route.route_id, ()))
        total = len(route.kinds)
        rows.append((
            route.route_id,
            route.display_name,
            f"{len(held)} of {total} recorded",
            "every requirement recorded" if len(held) >= total else f"{total - len(held)} missing",
        ))
    return tuple(rows)


def evidence_summary_text(held_by_route: Mapping[str, Iterable[object]]) -> str:
    """The standing summary above the evidence list."""
    total_kinds = sum(len(route.kinds) for route in ROUTE_REQUIREMENTS)
    recorded = sum(len(tuple(held_by_route.get(route.route_id, ()))) for route in ROUTE_REQUIREMENTS)
    complete = sum(1 for route in ROUTE_REQUIREMENTS
                   if len(tuple(held_by_route.get(route.route_id, ()))) >= len(route.kinds))
    return (
        f"{recorded} of {total_kinds} written requirement(s) recorded across "
        f"{len(ROUTE_REQUIREMENTS)} route(s); {complete} route(s) have all of theirs. Recording "
        f"evidence here is a note to yourself and to whoever reads this later: it opens no source, "
        f"sends nothing, and changes none of the gates above."
    )


def evidence_kind_rows(route_id: str, records: Iterable[object]) -> tuple[tuple[str, str, str, str], ...]:
    """One row per requirement of one route: kind, title, held or missing, and when it was recorded."""
    route = get_route(route_id)
    if route is None:
        return ()
    by_kind = {record.kind: record for record in records}
    rows = []
    for kind in route.kinds:
        record = by_kind.get(kind)
        rows.append((
            kind.value,
            EVIDENCE_TITLES.get(kind, kind.value),
            "held" if record is not None else "missing",
            (record.recorded_at[:10] if record is not None and record.recorded_at else ""),
        ))
    return tuple(rows)


def evidence_detail_text(route_id: str, kind: object, record: object | None) -> str:
    """What one requirement means, and what - if anything - is recorded against it."""
    route = get_route(route_id)
    if route is None or kind is None:
        return "Select a requirement to see what it means and what is recorded against it."
    title = EVIDENCE_TITLES.get(kind, getattr(kind, "value", str(kind)))
    lines = [f"{title} - {route.display_name}", "", f"What this requires: {EVIDENCE_LABELS[kind]}."]
    if record is None:
        lines.extend([
            "",
            "Nothing is recorded against this requirement, so this route cannot be considered for "
            "enabling. Missing is the honest state: it is not a failure, and it is not something "
            "this application can produce on its own.",
        ])
    else:
        lines.extend([
            "",
            f"Recorded {record.recorded_at}.",
            f"Where to check it: {record.reference}",
            f"What was checked: {record.note}",
            "",
            "Recorded evidence is somebody's written claim, kept so it can be checked and "
            "withdrawn. It is not a permission granted by the route's owner.",
        ])
    return "\n".join(lines)


def evidence_record_question(route_id: str, kind: object, reference: str, note: str) -> str:
    """The one confirmation shown before a piece of evidence is written down."""
    route = get_route(route_id)
    name = route.display_name if route is not None else route_id
    title = EVIDENCE_TITLES.get(kind, getattr(kind, "value", str(kind)))
    return (
        f"Record \"{title}\" for {name}?\n\n"
        f"Where to check it: {reference.strip()}\n"
        f"What was checked: {note.strip()}\n\n"
        "This is written to your database and to the event log as a route and a requirement - the "
        "reference and the note stay in the database only.\n\n"
        "It switches nothing on. The source-quality gate stays closed, every source stays "
        "disabled, and discovery, submission, email and inbox reading each still need their own "
        "decision. To change this record later you withdraw it, with a reason, and record it again."
    )


def evidence_withdraw_question(route_id: str, kind: object, note: str) -> str:
    """The one confirmation shown before recorded evidence is removed."""
    route = get_route(route_id)
    name = route.display_name if route is not None else route_id
    title = EVIDENCE_TITLES.get(kind, getattr(kind, "value", str(kind)))
    return (
        f"Withdraw \"{title}\" for {name}?\n\n"
        f"Your reason: {note.strip()}\n\n"
        "The record is removed and this route goes back to missing that requirement. The reason "
        "is kept in your database with nothing else; the event log records only the route and the "
        "requirement. Nothing else changes: nothing was switched on by the record, so nothing is "
        "switched off by removing it."
    )
