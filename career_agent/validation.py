"""Pure input parsing helpers shared by the desktop UI and tests."""
from __future__ import annotations

import math
import re


def split_values(value: str) -> tuple[str, ...]:
    """Split comma/newline-delimited values, removing blanks and case-insensitive duplicates."""
    result: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[,\n]", value):
        item = part.strip()
        if item and item.casefold() not in seen:
            result.append(item)
            seen.add(item.casefold())
    return tuple(result)


def optional_int(value: str, label: str) -> int | None:
    if not value.strip():
        return None
    try:
        return int(value.strip())
    except ValueError as exc:
        raise ValueError(f"{label} must be a whole number.") from exc


def optional_float(value: str, label: str) -> float | None:
    """A blank field is unknown (None); otherwise a finite, non-negative number.

    float() accepts nan, inf and 1e400, and every one of those is a number no
    person can mean here. They are refused rather than stored, because a stored
    nan compares false against every bound: an experience range checked against it
    would fall through to \"within the stated range\" and let an ineligible listing
    pass, and null-substitutes such as NaN are not valid JSON, so an export or
    backup holding one is not readable by strict readers.
    """
    if not value.strip():
        return None
    try:
        number = float(value.strip())
    except ValueError as exc:
        raise ValueError(f"{label} must be a number.") from exc
    if not math.isfinite(number):
        raise ValueError(
            f"{label} must be a real, finite number (nan and infinity are not accepted)."
        )
    if number < 0:
        raise ValueError(f"{label} cannot be negative.")
    return number
