"""Reproducible integrity summary for the research job-source audit CSV.

This tool audits the research CSV only. It does not fetch jobs or authorize source use.
Run from the repository root:
    python scripts/audit_job_source_csv.py
    python scripts/audit_job_source_csv.py --output research/job-source-audit-summary.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CSV = Path("research/job-source-audit-seed-2026-10-13.csv")


def audit_csv(path: str | Path) -> dict[str, Any]:
    csv_path = Path(path)
    raw = csv_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    rows: list[dict[str, str]] = []
    malformed_rows = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            raise ValueError("Audit CSV is empty; expected a header row.")
        if not header or len(set(header)) != len(header):
            raise ValueError("Audit CSV header is empty or contains duplicate column names.")
        for row in reader:
            if len(row) != len(header):
                malformed_rows += 1
                continue
            rows.append(dict(zip(header, row)))

    def value(row: dict[str, str], key: str) -> str:
        return (row.get(key) or "").strip()

    id_counts = Counter(value(row, "listing_id") for row in rows if value(row, "listing_id"))
    canonical_counts = Counter(
        value(row, "canonical_employer_url") for row in rows if value(row, "canonical_employer_url")
    )
    repeated_urls = {
        url: count for url, count in sorted(canonical_counts.items()) if count > 1
    }
    status_counts = Counter(value(row, "status") or "(blank)" for row in rows)
    permission_counts = Counter(value(row, "permission_status") or "(blank)" for row in rows)
    apply_outcome_counts = Counter(
        value(row, "apply_route_outcome") or "(not checked)"
        for row in rows
    )
    return {
        "report_schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input_path": str(csv_path),
        "input_sha256": digest,
        "header_columns": len(header),
        "record_count": len(rows),
        "malformed_width_rows_excluded": malformed_rows,
        "duplicate_listing_id_count": sum(count - 1 for count in id_counts.values() if count > 1),
        "duplicate_listing_ids": {key: count for key, count in sorted(id_counts.items()) if count > 1},
        "distinct_canonical_employer_urls": len(canonical_counts),
        "repeated_canonical_url_group_count": len(repeated_urls),
        "repeated_canonical_url_groups": repeated_urls,
        "status_counts": dict(sorted(status_counts.items())),
        "permission_status_counts": dict(sorted(permission_counts.items())),
        "permission_unknown_count": permission_counts.get("unknown", 0),
        "apply_route_outcome_counts": dict(sorted(apply_outcome_counts.items())),
        "apply_route_observed_record_count": sum(
            1 for row in rows if value(row, "apply_route_outcome")
        ),
        "direct_link_validity_percentage": None,
        "direct_link_validity_note": (
            "Not calculated: existing apply-route labels are not a complete, "
            "uniform HTTP/application-route validity measurement with a defensible denominator."
        ),
        "interpretation": (
            "Audit observations are not unique eligible vacancies. A status label of open, "
            "a readable page, or a visible Apply control is not by itself proof of current "
            "availability, candidate eligibility, or permission for automated collection."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="Path to the audit CSV")
    parser.add_argument("--output", help="Optional JSON report path; directories are not created automatically")
    args = parser.parse_args()
    report = audit_csv(args.csv)
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
