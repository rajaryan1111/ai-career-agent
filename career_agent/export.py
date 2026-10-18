"""Local JSON export contract for AI Career Agent.

The desktop UI and the smoke-test script both call this module, so the export
format has exactly one definition. No network access, no candidate data leaves
the machine.

Format version 2 adds every application attempt with its append-only event
history. There is deliberately no import/restore API yet; see the README.
"""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from .store import CareerStore

FORMAT_VERSION = 2
PRIVACY_NOTE = "Export may contain personal information; store securely."


def _json_ready(values: dict[str, Any]) -> dict[str, Any]:
    """Convert sets/frozensets/tuples to sorted lists so the payload is JSON-safe."""
    for key, value in values.items():
        if isinstance(value, (set, frozenset, tuple)):
            values[key] = sorted(value)
    return values


def build_export_payload(store: CareerStore) -> dict[str, Any]:
    """Return the complete local export for ``store`` without touching the filesystem."""
    profile = store.get_profile()
    payload: dict[str, Any] = {
        "format_version": FORMAT_VERSION,
        "profile": _json_ready(asdict(profile)) if profile else None,
        "jobs": [],
        "privacy_note": PRIVACY_NOTE,
    }
    for job in store.list_jobs():
        record = _json_ready(asdict(job))
        record["availability_status"] = job.availability_status.value
        record["application_attempts"] = [
            {
                "attempt_number": attempt.attempt_number,
                "status": attempt.status.value,
                "status_evidence": attempt.status_evidence,
                "candidate_confirmed": attempt.candidate_confirmed,
                "application_events": [
                    {
                        "from_status": event.from_status.value if event.from_status else None,
                        "to_status": event.to_status.value,
                        "evidence": event.evidence,
                        "candidate_confirmed": event.candidate_confirmed,
                        "recorded_at": event.recorded_at,
                    }
                    for event in store.list_events(job.listing_id, attempt.attempt_number)
                ],
            }
            for attempt in store.list_attempts(job.listing_id)
        ]
        payload["jobs"].append(record)
    return payload


def write_export(store: CareerStore, destination: str | Path) -> dict[str, Any]:
    """Write the export to ``destination`` and return the payload that was written."""
    payload = build_export_payload(store)
    Path(destination).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return payload
