"""Pure input parsing helpers shared by the desktop UI and tests."""
from __future__ import annotations

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
    if not value.strip():
        return None
    try:
        number = float(value.strip())
    except ValueError as exc:
        raise ValueError(f"{label} must be a number.") from exc
    if number < 0:
        raise ValueError(f"{label} cannot be negative.")
    return number
