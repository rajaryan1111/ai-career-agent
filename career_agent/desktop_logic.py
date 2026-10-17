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
