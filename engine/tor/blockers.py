"""Blocker taxonomy + internal gaps (v0.6.5 — Fast Proposal Mode, §5/§6).

Separates issues so that package/compliance gaps never stop a technical draft:

  DRAFT_BLOCKER           — rare; genuinely prevents a technical draft (no TOR text,
                            no requirements, hard generation failure, contradiction/
                            fabrication in the technical content).
  FINAL_SUBMISSION_BLOCKER — must be resolved before submission, NOT before drafting
                            (registration cert, tax treatment, submission channel,
                            required annex not physically present, mandatory staff
                            availability unconfirmed, budget not reconciled).
  WARNING                 — quality issue to review.
  IMPROVEMENT             — optional competitiveness boost (scoring items, etc.).

Maps the EXISTING Final-QA findings (unchanged) into these buckets and renders an
actionable `internal_gaps.md` for the team — never leaked into the client draft.
"""
from __future__ import annotations

from typing import Any

DRAFT_BLOCKER = "DRAFT_BLOCKER"
FINAL_SUBMISSION_BLOCKER = "FINAL_SUBMISSION_BLOCKER"
WARNING = "WARNING"
IMPROVEMENT = "IMPROVEMENT"

# QA check names whose CRITICAL/ERROR findings are genuine DRAFT blockers (the
# technical content itself is broken). Everything else critical is a submission
# blocker (package/compliance), never a reason to withhold the working draft.
_DRAFT_BLOCKING_CHECKS = {
    "ARTIFACT_CONSISTENCY", "REQUIREMENT_COVERAGE", "LEDGER_VERIFICATION", "OWNERSHIP",
    "DECISION_COMPLIANCE", "ARFADA_FACT", "CONTRADICTION", "ASSIGNMENT_TYPE",
    "SECTION_COMPLETENESS", "FRAMEWORK", "HISTORICAL_COPY", "EXPERIENCE_CONTAMINATION",
    "PERSONNEL", "DELIVERABLES", "FIXED_CONSTRAINT", "SAMPLING", "TEAM",
}
# These are always submission-package / compliance blockers, not draft blockers.
_SUBMISSION_CHECKS = {
    "SUBMISSION", "CLAIMED_ANNEX", "BUDGET", "CLIENT_LEAKAGE", "CLIENT_PLACEHOLDER",
}


def classify_finding(finding: dict) -> str:
    """Map one QA finding to a blocker class."""
    check = finding.get("check", "")
    sev = finding.get("severity", "")
    cat = finding.get("category", "")

    if check in _SUBMISSION_CHECKS:
        # scoring/optional submission items are competitive, not blockers
        if cat in ("scoring_submission_missing", "optional_submission_missing"):
            return IMPROVEMENT
        if sev in ("CRITICAL", "ERROR"):
            return FINAL_SUBMISSION_BLOCKER
        return WARNING

    if sev == "CRITICAL":
        return DRAFT_BLOCKER if check in _DRAFT_BLOCKING_CHECKS else FINAL_SUBMISSION_BLOCKER
    if sev == "ERROR":
        return DRAFT_BLOCKER if check in _DRAFT_BLOCKING_CHECKS else WARNING
    if sev == "WARNING":
        return WARNING
    return IMPROVEMENT


def classify_blockers(qa_report: dict, *, extra_submission_gaps: list = None) -> dict:
    """Bucket all QA findings + extra package gaps into the four classes."""
    buckets: dict[str, list] = {DRAFT_BLOCKER: [], FINAL_SUBMISSION_BLOCKER: [],
                                WARNING: [], IMPROVEMENT: []}
    for f in qa_report.get("findings", []):
        buckets[classify_finding(f)].append({
            "check": f.get("check"), "message": f.get("message"),
            "section_id": f.get("section_id"), "requirement_id": f.get("requirement_id"),
            "recommended_action": f.get("recommended_action"),
        })
    for gap in (extra_submission_gaps or []):
        buckets[FINAL_SUBMISSION_BLOCKER].append(gap if isinstance(gap, dict)
                                                 else {"message": str(gap)})
    return buckets


def _bullet(item: Any) -> str:
    if isinstance(item, dict):
        msg = item.get("message") or item.get("check") or "item"
        act = item.get("recommended_action")
        return f"- {msg}" + (f" — {act}" if act else "")
    return f"- {item}"


def render_internal_gaps(buckets: dict, *, extra_notes: list = None) -> str:
    """Render internal_gaps.md — short, actionable, team-only (never client-facing)."""
    lines = ["# Internal gaps — NOT for the client draft", ""]
    final_b = buckets.get(FINAL_SUBMISSION_BLOCKER, [])
    draft_b = buckets.get(DRAFT_BLOCKER, [])
    warns = buckets.get(WARNING, [])
    improvements = buckets.get(IMPROVEMENT, [])

    if draft_b:
        lines.append("## Draft blockers (fix to produce a working draft)")
        lines += [_bullet(i) for i in draft_b]
        lines.append("")
    lines.append("## Final-submission blockers (resolve before submitting)")
    if final_b or extra_notes:
        lines += [_bullet(i) for i in final_b]
        lines += [_bullet(n) for n in (extra_notes or [])]
    else:
        lines.append("- None recorded")
    lines.append("")
    if warns:
        lines.append("## Warnings (review)")
        lines += [_bullet(i) for i in warns]
        lines.append("")
    if improvements:
        lines.append("## Improvements (optional, boost competitiveness)")
        lines += [_bullet(i) for i in improvements]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
