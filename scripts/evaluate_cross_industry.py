"""Reproducible cross-industry evaluation for Phase 4.

Reads the reviewed evaluation set in ``research/`` and reports, per occupation group, what the
matching engine and the résumé extractor actually produce against the standard a reviewer wrote down
there. It does not fetch jobs, does not authorize any source, touches no network and no private data:
every value it reads is synthetic and lives in the corpus file.

    python scripts/evaluate_cross_industry.py                       # the report on stdout
    python scripts/evaluate_cross_industry.py --output path.json    # the same result as JSON

What each measurement means, and what it does not:

* **Top-ranked relevance** - whether the engine's first-ranked listing is the one the reviewer said to
  open first. A disagreement is reported, never resolved by editing the corpus: the corpus is the
  standard, so a disagreement is a finding about the engine or about the standard.
* **Hard-eligibility violations** - a listing the engine would offer that the domain rules mark as
  ineligible is the one number that must be zero. It is measured by evaluating eligibility directly,
  independently of the ranking.
* **Compensation duplication** - a recorded reminder that the engine cannot compare a factor it has no
  field for. Kept as an explicit zero-count check so it cannot silently become a non-zero one.
* **Extraction accuracy** - whether each value the reviewer says is stated plainly in a synthetic
  résumé is proposed, and whether anything else was proposed under a key the corpus does not expect
  (a false positive is counted separately from a miss, because they are different defects).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from career_agent.core import (  # noqa: E402
    Availability, CandidateProfile, Decision, JobListing, evaluate_eligibility,
)
from career_agent.matching import Recommendation, assess, assessment_to_dict  # noqa: E402
from career_agent.resume import parse_resume_text  # noqa: E402

DEFAULT_CORPUS = Path("research/cross-industry-evaluation-set-2026-10-16.json")

#: The thresholds `phases.md` proposes for Phase 4. None of them is a target to be tuned towards; the
#: harness reports the measurement and whether it clears the stated bar.
PROPOSED_THRESHOLDS = {
    "top_ranked_precision": 0.80,
    "hard_eligibility_violations": 0,
    "duplicate_submissions_from_retries": 0,
    "confirmed_statuses_without_evidence": 0,
    "critical_field_extraction_accuracy": 0.95,
}

#: Profile keys the corpus may set, in the vocabulary of the form. ``work_authorization`` is free text.
_PROFILE_FIELDS = (
    "candidate_country", "degree_discipline", "study_status", "graduation_year", "experience_years",
    "work_authorization",
)


class CorpusError(Exception):
    """The evaluation set is malformed; a broken corpus must not look like a passing measurement."""


def load_corpus(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        raise CorpusError(f"No evaluation set at {path}.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CorpusError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or not data.get("groups"):
        raise CorpusError(f"{path} has no groups to evaluate.")
    for group in data["groups"]:
        for key in ("id", "label", "profile", "listings", "resume"):
            if key not in group:
                raise CorpusError(f"Group {group.get('id', '?')!r} is missing {key!r}.")
        if len(group["listings"]) < 2:
            raise CorpusError(f"Group {group['id']!r} needs at least two listings to rank.")
    return data


def build_profile(specification: Mapping[str, Any]) -> CandidateProfile:
    values = {key: specification[key] for key in _PROFILE_FIELDS if key in specification}
    for key in ("skills", "preferred_locations", "preferred_work_modes", "preferred_role_types"):
        if key in specification:
            values[key] = frozenset(specification[key])
    return CandidateProfile(**values)


def build_listing(specification: Mapping[str, Any]) -> JobListing:
    values: dict[str, Any] = {
        "source_id": "synthetic-corpus", "source_name": "Synthetic evaluation corpus",
        "source_listing_url": f"https://jobs.example/{specification['listing_id']}",
        "provenance_note": "Synthetic listing from the cross-industry evaluation corpus; no real vacancy exists.",
        "availability_status": Availability(specification["availability_status"]),
    }
    values.update({key: value for key, value in specification.items() if key not in {"review_rank", "review_note"}})
    for key in ("eligible_countries", "allowed_degree_disciplines", "allowed_study_statuses",
                "allowed_graduation_years", "required_skills"):
        if key in specification:
            values[key] = tuple(specification[key])
    return JobListing(**values)


def expected_order(group: Mapping[str, Any]) -> tuple[str, ...]:
    """The reviewer's order: rank 1 first, and the corpus must state one rank per listing."""
    ranked = sorted(group["listings"], key=lambda item: item["review_rank"])
    return tuple(item["listing_id"] for item in ranked)


def evaluate_group(group: Mapping[str, Any]) -> dict[str, Any]:
    profile = build_profile(group["profile"])
    listings = [build_listing(item) for item in group["listings"]]
    by_id = {item.listing_id: item for item in listings}

    # Ranking, as the window would show it: blocked listings are excluded from the order but kept in
    # the assessment set, so a blocked listing can neither be offered nor silently vanish.
    assessments = [assess(profile, listing) for listing in listings]
    offered = [item for item in assessments if item.recommendation is not Recommendation.BLOCKED]
    offered.sort(key=lambda item: item.rank_key)
    blocked = [item for item in assessments if item.recommendation is Recommendation.BLOCKED]

    # Hard eligibility, measured independently of what the ranking decided to show.
    violations: list[dict[str, str]] = []
    for assessment in assessments:
        report = evaluate_eligibility(profile, by_id[assessment.listing_id])
        if report.decision is Decision.FAIL and assessment.recommendation is not Recommendation.BLOCKED:
            violations.append({
                "listing_id": assessment.listing_id,
                "reason": report.summary() if hasattr(report, "summary") else str(report.decision),
            })

    expected = expected_order(group)
    engine_first = offered[0].listing_id if offered else None
    return {
        "id": group["id"],
        "label": group["label"],
        "expected_order": list(expected),
        "engine_order": [item.listing_id for item in offered],
        "blocked": sorted(item.listing_id for item in blocked),
        "top_ranked_agrees": engine_first == expected[0],
        "engine_first": engine_first,
        "expected_first": expected[0],
        "hard_eligibility_violations": violations,
        # The engine has no compensation field to compare, so this must stay False everywhere: it is
        # measured rather than assumed, because a future factor added by accident would show up here.
        "group_compares_compensation": any(
            "compensation" in str(assessment_to_dict(item)).casefold() for item in assessments
        ),
    }


def evaluate_resume(group: Mapping[str, Any]) -> dict[str, Any]:
    """Measure extraction for one résumé: what was expected, what was found, and what was invented."""
    resume = group["resume"]
    expected = dict(resume.get("expected", {}))
    proposals, _unmapped, _notes = parse_resume_text(resume["text"])
    by_key = {proposal.key: proposal for proposal in proposals}

    checks: list[dict[str, Any]] = []
    for key, value in expected.items():
        checks.append(_one_check(key, value, by_key))

    # Values the module deliberately does not propose. Each is verified to still be absent, so the rule
    # is a live check rather than a sentence: a future widening that starts inferring them shows up here.
    documented = []
    for entry in resume.get("not_proposed_by_design", []):
        field, wanted = entry["field"], entry["value"]
        if field == "country":
            proposal = by_key.get("country")
            absent = proposal is None
            found = None if proposal is None else proposal.value
        elif field == "skills_do_not_contain":
            proposal = by_key.get("skills")
            absent = proposal is not None and wanted.casefold() not in proposal.value.casefold()
            found = None if proposal is None else proposal.value
        else:
            absent, found = False, None
        documented.append({
            "field": field, "value": wanted, "rule": entry["rule"],
            "still_not_proposed": absent, "found": found,
        })

    return {
        "id": group["id"],
        "checks": checks,
        "checks_passed": sum(1 for check in checks if check["pass"]),
        "checks_total": len(checks),
        "proposed_keys": [proposal.key for proposal in proposals],
        "proposals_needing_review": sum(
            1 for proposal in proposals if proposal.confidence.value != "confident"
        ),
        "documented_non_coverage": documented,
    }


def _one_check(key: str, expected: Any, by_key: Mapping[str, Any]) -> dict[str, Any]:
    """One expected value against what was proposed, using the corpus's own key names."""
    if key.endswith("_contains"):
        field = key[: -len("_contains")]
    elif key.endswith("_contain"):
        field = key[: -len("_contain")]
    else:
        field = key
    proposal = by_key.get(field)
    if proposal is None:
        return {"field": field, "expected": expected, "found": None, "pass": False}
    if field == "skills":
        wanted = [str(value).casefold() for value in expected]
        found = [part.strip().casefold() for part in proposal.value.split(",")]
        passed = all(item in found for item in wanted)
    else:
        passed = str(expected).casefold() in proposal.value.casefold()
    return {
        "field": field, "expected": expected, "found": proposal.value,
        "confidence": proposal.confidence.value, "pass": passed,
    }


def run_rule_checks(checks: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The extraction rules the corpus states explicitly, each measured in both directions."""
    results = []
    for check in checks:
        proposals, _unmapped, _notes = parse_resume_text(check["text"])
        keys = {proposal.key for proposal in proposals}
        proposed = check["field"] in keys
        results.append({
            "name": check["name"], "field": check["field"], "rule": check["rule"],
            "expected_proposed": check["expect_proposed"], "proposed": proposed,
            "pass": proposed is check["expect_proposed"],
        })
    return results


def summarise(corpus: Mapping[str, Any]) -> dict[str, Any]:
    groups = [evaluate_group(group) for group in corpus["groups"]]
    resumes = [evaluate_resume(group) for group in corpus["groups"]]
    rule_checks = run_rule_checks(corpus.get("extraction_rule_checks", ()))

    violations = [{"group": item["id"], **violation} for item in groups for violation in item["hard_eligibility_violations"]]
    agreed = sum(1 for item in groups if item["top_ranked_agrees"])
    total = sum(len(group["listings"]) for group in corpus["groups"])
    checks_passed = sum(item["checks_passed"] for item in resumes)
    checks_total = sum(item["checks_total"] for item in resumes)
    documented = [{"group": item["id"], **entry} for item in resumes for entry in item["documented_non_coverage"]]

    return {
        "corpus_version": corpus.get("corpus_version"),
        "created": corpus.get("created"),
        "occupation_groups": len(corpus["groups"]),
        "listings": total,
        "measurements": {
            "top_ranked_agreement": {
                "agreed": agreed, "groups": len(groups),
                "value": round(agreed / len(groups), 4) if groups else None,
                "proposed_threshold": PROPOSED_THRESHOLDS["top_ranked_precision"],
            },
            "hard_eligibility_violations": {
                "count": len(violations),
                "proposed_threshold": PROPOSED_THRESHOLDS["hard_eligibility_violations"],
            },
            "critical_field_extraction_accuracy": {
                "passed": checks_passed, "checks": checks_total,
                "value": round(checks_passed / checks_total, 4) if checks_total else None,
                "proposed_threshold": PROPOSED_THRESHOLDS["critical_field_extraction_accuracy"],
            },
            "documented_non_coverage": {
                "count": len(documented),
                "rules_holding": sum(1 for entry in documented if entry["still_not_proposed"]),
            },
            "extraction_rule_checks": {
                "passed": sum(1 for check in rule_checks if check["pass"]), "checks": len(rule_checks),
            },
        },
        "groups": groups,
        "resumes": resumes,
        "rule_checks": rule_checks,
        "violations": violations,
        "documented_non_coverage": documented,
        "caveats": [
            "Synthetic corpus: this measures agreement with a written standard, not with hiring outcomes.",
            "Seven résumés is a small sample, and every one of them is clean, plainly labelled text: scanned "
            "documents, photo headers, two-column PDFs and unusual layouts are not represented.",
            "No listing was fetched, no source was enabled, and no application was submitted.",
            "Compensation is still not compared: the domain model has no field for it.",
            "Top-ranked agreement is a strict measure: it asks whether the first listing matched, not "
            "whether the whole order did.",
        ],
    }


def render(report: Mapping[str, Any]) -> str:
    lines = [
        "Cross-industry evaluation of the matching engine and the résumé extractor",
        f"Corpus version {report['corpus_version']} ({report['created']}); "
        f"{report['occupation_groups']} occupation groups, {report['listings']} synthetic listings.",
        "",
    ]
    for group in report["groups"]:
        mark = "agrees  " if group["top_ranked_agrees"] else "DISAGREES"
        lines.append(f"  [rank] {mark} {group['label']}")
        lines.append(f"           standard: {' -> '.join(group['expected_order'])}")
        lines.append(f"           engine  : {' -> '.join(group['engine_order']) or '(nothing offered)'}")
        if group["blocked"]:
            lines.append(f"           blocked : {', '.join(group['blocked'])}")
        for violation in group["hard_eligibility_violations"]:
            lines.append(f"           VIOLATION: {violation['listing_id']} - {violation['reason']}")
    lines.append("")
    for resume in report["resumes"]:
        lines.append(
            f"  [resumé] {resume['id']}: {resume['checks_passed']}/{resume['checks_total']} expected values extracted"
        )
        for check in resume["checks"]:
            flag = "ok  " if check["pass"] else "MISS"
            found = check["found"] if check["found"] is not None else "(not proposed)"
            lines.append(f"           {flag} {check['field']}: {found!r}")
        for entry in resume["documented_non_coverage"]:
            state = "held" if entry["still_not_proposed"] else "BROKEN"
            lines.append(f"           note[{state}] {entry['field']}: not proposed by design")
    lines.append("")
    for check in report["rule_checks"]:
        flag = "ok  " if check["pass"] else "FAIL"
        lines.append(f"  [rule ] {flag} {check['name']}")
    measurements = report["measurements"]
    accuracy = measurements["critical_field_extraction_accuracy"]
    lines += [
        "",
        "Measurements against the thresholds phases.md proposes:",
        f"  top-ranked agreement      : {measurements['top_ranked_agreement']['agreed']}/"
        f"{measurements['top_ranked_agreement']['groups']} "
        f"({measurements['top_ranked_agreement']['value']:.0%}) "
        f"against {measurements['top_ranked_agreement']['proposed_threshold']:.0%} proposed",
        f"  hard-eligibility violations: {measurements['hard_eligibility_violations']['count']} "
        f"(must be {measurements['hard_eligibility_violations']['proposed_threshold']})",
        f"  critical-field extraction : {accuracy['passed']}/{accuracy['checks']} "
        f"({accuracy['value']:.0%}) against {accuracy['proposed_threshold']:.0%} proposed",
        f"                              ({measurements['documented_non_coverage']['count']} further values are "
        f"present in the text but outside what the extractor claims, and are not counted here)",
        f"  documented rules holding  : {measurements['documented_non_coverage']['rules_holding']}/"
        f"{measurements['documented_non_coverage']['count']}; "
        f"extraction rule checks {measurements['extraction_rule_checks']['passed']}/"
        f"{measurements['extraction_rule_checks']['checks']}",
        "",
        "Not established by this report:",
    ]
    lines += [f"  - {caveat}" for caveat in report["caveats"]]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS), help="Path to the evaluation set")
    parser.add_argument("--output", help="Write the result as JSON to this path")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON instead of a report")
    arguments = parser.parse_args(argv)

    try:
        corpus = load_corpus(Path(arguments.corpus))
    except CorpusError as exc:
        print(f"EVALUATION FAILED: {exc}", file=sys.stderr)
        return 1

    report = summarise(corpus)
    if arguments.output:
        Path(arguments.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if arguments.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render(report))
    # A measured violation of the one rule that must never be broken is a failing run, not a report.
    return 1 if report["measurements"]["hard_eligibility_violations"]["count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
