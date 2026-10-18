"""Versioned role strategies: what kinds of roles the person is pursuing, and how that changes.

A strategy is the person's own statement of intent - a role family and the titles that spell it,
where and how they would work, what the work must pay to be worth pursuing, which requirements they
treat as hard, which roles and employers they rule out, and which skills should make a listing rank
higher. It is deliberately **not** a second candidate profile: the facts about the person (skills,
experience, qualifications) live in ``core.CandidateProfile`` with their own provenance, and a
strategy only says what to do with them. Nothing here invents a qualification or claims the person
has a skill their profile does not state.

Three rules hold the model together:

* **Industry-agnostic by construction.** Every field is free text the person supplies; there is no
  built-in vocabulary of AI/ML, software or any other industry, and no field whose meaning depends on
  one. Role families are examples a person might type, never a list this module recognises.
* **Versions are append-only and honest.** Editing a strategy writes a *new version* beside the old
  one; a revision whose content is byte-identical to the current version writes nothing and says so,
  because a version that changed nothing is a claim that something did. Artifacts generated for a
  strategy reference it by ``(strategy_id, version)``, so a tailored document can always be traced to
  the exact statement of intent it was made under - and a later edit never silently rewrites what an
  earlier one meant.
* **Unknown means unknown.** Every field except the name and the role family is optional, and an
  absent field is *not stated* rather than empty-by-choice: a strategy that names no location says
  nothing about location, and a comparison that treats silence as a preference would be inventing one.

Compensation bounds and employment types are recorded but **not compared**: the job listing domain
model has no field for either (``career_agent.matching`` records the same limitation), so those two
are statements of what the person wants, not eligibility checks this build can run. Saying otherwise
would be the kind of untruthful status the rest of the product is built to avoid. The fields
``career_agent.matching`` *does* compare for a strategy are the excluded employers and role titles
(hard gates), the required skills (a hard gate against the profile), and the locations, work modes
and preferred skills (explainable ranking factors).
"""
from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable

#: A strategy name is what the person reads in a list of their own strategies: long enough for
#: "Backend roles, Berlin, no fintech", short enough that a window can show it on one line.
MAX_NAME_CHARS = 120

#: One free-text item (a title synonym, a place, a skill, a seniority label). Generous, because a
#: person pasting a title out of a listing should not have to argue with a length limit - but bounded,
#: because this text is stored, rendered and compared, and a megabyte in one cell is not a title.
MAX_ITEM_CHARS = 200

#: How many items one set-valued field may hold. Past this a "strategy" is a copy of a job board, and
#: every comparison over it gets slower for no decision it improves.
MAX_SET_ITEMS = 100

#: A strategy identifier is generated here, never typed: 32 hex characters, so the bound is generous.
MAX_ID_CHARS = 64


class StrategyError(ValueError):
    """A strategy could not be built, with a message written to be shown to the person as-is."""


def _clean_text(value: object, noun: str, *, maximum: int) -> str:
    """One required free-text field: stripped, bounded, and never empty."""
    if not isinstance(value, str):
        raise StrategyError(f"{noun} must be text, not {type(value).__name__}")
    cleaned = value.strip()
    if not cleaned:
        raise StrategyError(f"{noun} is required and cannot be empty")
    if len(cleaned) > maximum:
        raise StrategyError(
            f"{noun} is {len(cleaned)} characters, over the {maximum}-character limit")
    return cleaned


def _optional_text(value: object, noun: str, *, maximum: int = MAX_ITEM_CHARS) -> str | None:
    """One optional free-text field: ``None`` (not stated) stays ``None``, and "" means not stated."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise StrategyError(f"{noun} must be text or absent, not {type(value).__name__}")
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > maximum:
        raise StrategyError(
            f"{noun} is {len(cleaned)} characters, over the {maximum}-character limit")
    return cleaned


def _clean_set(values: Iterable[Any] | frozenset[str] | None, noun: str) -> frozenset[str]:
    """One set-valued field: every item non-empty text, bounded, and no more of them than is useful.

    Accepts ``None`` as the empty set so a caller may pass an absent field; a *stored* empty set and
    an absent one are the same statement ("nothing ruled in here"), and pretending otherwise would
    make a revision that cleared a list look like a content change.
    """
    if values is None:
        return frozenset()
    if isinstance(values, str):
        raise StrategyError(f"{noun} must be a list of separate values, not one text blob")
    try:
        items = tuple(values)
    except TypeError as exc:
        raise StrategyError(f"{noun} must be a list of values: {exc}") from exc
    if len(items) > MAX_SET_ITEMS:
        raise StrategyError(
            f"{noun} holds {len(items)} values, over the {MAX_SET_ITEMS}-value limit")
    cleaned = []
    for item in items:
        if not isinstance(item, str):
            raise StrategyError(
                f"every value in {noun} must be text, not {type(item).__name__}")
        stripped = item.strip()
        if not stripped:
            raise StrategyError(f"{noun} holds an empty value; remove it or fill it in")
        if len(stripped) > MAX_ITEM_CHARS:
            raise StrategyError(
                f"a value in {noun} is {len(stripped)} characters, over the {MAX_ITEM_CHARS}-character "
                "limit")
        cleaned.append(stripped)
    return frozenset(cleaned)


def _optional_amount(value: object, noun: str) -> float | None:
    """One optional money amount: a finite, non-negative number, or not stated.

    The same boundary the JSON import holds (``validation.optional_float``): ``float()`` accepts
    ``nan``, ``inf`` and ``1e400``, and a boolean is ``1.0`` to ``float()``, and none of those is an
    amount of money anybody can act on.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise StrategyError(f"{noun} must be a number or absent, not a boolean")
    if not isinstance(value, (int, float)):
        try:
            number = float(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise StrategyError(f"{noun} must be a number or absent: {value!r} is not one") from exc
    else:
        number = float(value)
    if not math.isfinite(number):
        raise StrategyError(f"{noun} must be a finite number; {value!r} is not one")
    if number < 0:
        raise StrategyError(f"{noun} cannot be negative")
    return number


def new_strategy_id() -> str:
    """A fresh strategy identifier. Generated, never typed: identity is this module's business."""
    return uuid.uuid4().hex


@dataclass(frozen=True)
class RoleStrategy:
    """One version of one statement of intent about the roles the person is pursuing.

    ``strategy_id`` and ``version`` are the identity of the row; everything else is the content, and
    :meth:`content_key` renders exactly that content so two versions can be compared without their
    identity getting in the way.
    """

    strategy_id: str
    version: int
    name: str
    role_family: str
    title_synonyms: frozenset[str] = field(default_factory=frozenset)
    seniority: str | None = None
    locations: frozenset[str] = field(default_factory=frozenset)
    work_modes: frozenset[str] = field(default_factory=frozenset)
    employment_types: frozenset[str] = field(default_factory=frozenset)
    compensation_min: float | None = None
    compensation_max: float | None = None
    compensation_currency: str | None = None
    required_skills: frozenset[str] = field(default_factory=frozenset)
    excluded_role_titles: frozenset[str] = field(default_factory=frozenset)
    excluded_employers: frozenset[str] = field(default_factory=frozenset)
    preferred_skills: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        # Identity: validated here rather than trusted, because a stored row is rebuilt through this
        # constructor and a corrupted identifier must be reported as the problem it is.
        if not isinstance(self.strategy_id, str) or not self.strategy_id.strip():
            raise StrategyError("a strategy needs an identifier")
        if len(self.strategy_id) > MAX_ID_CHARS:
            raise StrategyError(
                f"a strategy identifier is at most {MAX_ID_CHARS} characters, "
                f"not {len(self.strategy_id)}")
        if isinstance(self.version, bool) or not isinstance(self.version, int):
            raise StrategyError(
                f"a strategy version must be a whole number, not {type(self.version).__name__}")
        if self.version < 1:
            raise StrategyError(f"a strategy version starts at 1, not {self.version}")

        # Content: every field goes through the same cleaners a fresh strategy does, so a stored row
        # and a typed one cannot disagree about what is acceptable.
        object.__setattr__(self, "name", _clean_text(self.name, "the strategy name",
                                                     maximum=MAX_NAME_CHARS))
        object.__setattr__(self, "role_family",
                           _clean_text(self.role_family, "the role family", maximum=MAX_ITEM_CHARS))
        object.__setattr__(self, "seniority", _optional_text(self.seniority, "the seniority"))
        for noun, attribute in (
                ("the title synonyms", "title_synonyms"),
                ("the locations", "locations"),
                ("the work modes", "work_modes"),
                ("the employment types", "employment_types"),
                ("the required skills", "required_skills"),
                ("the excluded role titles", "excluded_role_titles"),
                ("the excluded employers", "excluded_employers"),
                ("the preferred skills", "preferred_skills"),
        ):
            object.__setattr__(self, attribute, _clean_set(getattr(self, attribute), noun))
        object.__setattr__(self, "compensation_min",
                           _optional_amount(self.compensation_min, "the minimum compensation"))
        object.__setattr__(self, "compensation_max",
                           _optional_amount(self.compensation_max, "the maximum compensation"))
        currency = _optional_text(self.compensation_currency, "the compensation currency", maximum=12)
        object.__setattr__(self, "compensation_currency", currency)
        if (self.compensation_min is not None or self.compensation_max is not None) and currency is None:
            # An amount without a currency is not a statement about money: 50000 is rupees, dollars or
            # euros depending on who is reading, and a strategy is read back months later.
            raise StrategyError("a compensation bound needs its currency stated beside it")
        if (self.compensation_min is not None and self.compensation_max is not None
                and self.compensation_min > self.compensation_max):
            raise StrategyError(
                f"the minimum compensation {self.compensation_min:g} is above the maximum "
                f"{self.compensation_max:g}")

    def content_key(self) -> str:
        """A stable rendering of the content alone: two versions match when their strategies do.

        Identity (the identifier and the version number) is deliberately absent, sets are sorted and
        the JSON is key-sorted, so "the same strategy said the same way" always produces the same
        text and a revision that changed nothing can be recognised as one.
        """
        content = {
            "name": self.name,
            "role_family": self.role_family,
            "title_synonyms": sorted(self.title_synonyms),
            "seniority": self.seniority,
            "locations": sorted(self.locations),
            "work_modes": sorted(self.work_modes),
            "employment_types": sorted(self.employment_types),
            "compensation_min": self.compensation_min,
            "compensation_max": self.compensation_max,
            "compensation_currency": self.compensation_currency,
            "required_skills": sorted(self.required_skills),
            "excluded_role_titles": sorted(self.excluded_role_titles),
            "excluded_employers": sorted(self.excluded_employers),
            "preferred_skills": sorted(self.preferred_skills),
        }
        return json.dumps(content, sort_keys=True, ensure_ascii=False)

    def describe(self) -> str:
        """One line for a list: the name, the family, and the version a reader is looking at."""
        return f"{self.name} ({self.role_family}, version {self.version})"


#: The content fields a caller supplies, in the order the constructor holds them. One list so the
#: store's payload builder and the decoder cannot drift apart about what a strategy is made of.
CONTENT_FIELDS: tuple[str, ...] = (
    "name",
    "role_family",
    "title_synonyms",
    "seniority",
    "locations",
    "work_modes",
    "employment_types",
    "compensation_min",
    "compensation_max",
    "compensation_currency",
    "required_skills",
    "excluded_role_titles",
    "excluded_employers",
    "preferred_skills",
)

_SET_FIELDS: frozenset[str] = frozenset({
    "title_synonyms", "locations", "work_modes", "employment_types",
    "required_skills", "excluded_role_titles", "excluded_employers", "preferred_skills",
})


def strategy_payload(strategy: RoleStrategy) -> str:
    """One strategy version as the text the database stores: its content, without its identity.

    The identifier and version are columns, not payload, so the payload of two versions of one
    strategy differs exactly when the strategies do - which is what makes ``content_key`` comparisons
    over stored rows mean the same thing as over fresh ones.
    """
    content: dict[str, Any] = {}
    for name in CONTENT_FIELDS:
        value = getattr(strategy, name)
        content[name] = sorted(value) if name in _SET_FIELDS else value
    return json.dumps(content, sort_keys=True, ensure_ascii=False)


def strategy_from_payload(strategy_id: str, version: int, payload: str) -> RoleStrategy:
    """A stored row back into a strategy, refusing a payload this build cannot read as one.

    Raises :class:`StrategyError` (never a bare ``TypeError``/``KeyError``) so the store can report a
    damaged row as itself instead of crashing a read of the whole table.
    """
    try:
        content = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise StrategyError(f"a stored strategy is not readable JSON ({exc.msg})") from exc
    if not isinstance(content, dict):
        raise StrategyError("a stored strategy is a JSON object, not "
                            f"{type(content).__name__}")
    unknown = sorted(set(content) - set(CONTENT_FIELDS))
    if unknown:
        raise StrategyError(
            f"a stored strategy holds field(s) this version does not know: {', '.join(unknown)}")
    missing = [name for name in CONTENT_FIELDS if name not in content]
    if missing:
        raise StrategyError(
            f"a stored strategy is missing field(s) every strategy has: {', '.join(missing)}")
    values = {name: content[name] for name in CONTENT_FIELDS}
    for name in _SET_FIELDS:
        stored = values[name]
        if not isinstance(stored, list):
            raise StrategyError(f"a stored strategy's {name} is a list, not {type(stored).__name__}")
        values[name] = frozenset(stored)
    return RoleStrategy(strategy_id=strategy_id, version=version, **values)
