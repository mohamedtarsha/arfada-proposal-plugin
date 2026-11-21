"""Two-status QA for Fast Proposal Mode (v0.6.5, §12).

Runs the EXISTING deterministic Final QA (unchanged) and reports TWO independent
statuses instead of one overall RED/YELLOW/GREEN:

  TECHNICAL_DRAFT_STATUS   — is the technical proposal content itself sound?
      READY_FOR_REVIEW | NEEDS_FIXES | BLOCKED
  SUBMISSION_PACKAGE_STATUS — are the compliance/package items in place?
      READY | NOT_READY

A missing package document (CV file, budget, registration, previous-work annex)
makes the package NOT READY but does NOT make the technical draft BLOCKED — so a
working draft is never withheld for a package gap. The underlying GREEN/YELLOW/RED
overall verdict is still returned for the FINAL submission gate (unchanged).
"""
from __future__ import annotations

from pathlib import Path

from .final_qa import run_final_qa
from .blockers import (classify_blockers, render_internal_gaps,
                       DRAFT_BLOCKER, FINAL_SUBMISSION_BLOCKER, WARNING)

TECH_READY = "READY_FOR_REVIEW"
TECH_NEEDS_FIXES = "NEEDS_FIXES"
TECH_BLOCKED = "BLOCKED"
PKG_READY = "READY"
PKG_NOT_READY = "NOT_READY"


def two_status_report(run_dir: str | Path, *, extra_submission_gaps: list = None,
                      extra_notes: list = None) -> dict:
    """Return both statuses + the blocker buckets + internal gaps text."""
    run_dir = Path(run_dir)
    qa = run_final_qa(run_dir)
    # TOR-required budget / previous-work items that are still unresolved block the
    # FINAL submission (never the draft) — v0.6.9
    from .submission_blockers import pending_submission_blockers
    try:
        import json as _json
        reqs = _json.loads((run_dir / "requirements.json").read_text(encoding="utf-8")
                           ).get("requirements", [])
    except Exception:
        reqs = []
    pending = pending_submission_blockers(run_dir, reqs)
    keys = {p["item_key"] for p in pending}
    _labels = {"detailed_budget": "Financial offer / detailed budget",
               "previous_work": "Previous-work example",
               "registration": "Registration evidence"}
    extra = [g for g in (extra_submission_gaps or [])
             if not any(_labels[k] in str(g.get("message", "") if isinstance(g, dict) else g)
                        for k in keys)]
    buckets = classify_blockers(qa, extra_submission_gaps=extra + pending)

    # v0.6.11: one canonical blocker per unresolved item (claim state included);
    # proposal_final.docx is an export step, never a substantive blocker
    from .claim_state import write_claim_state
    from .canonical_blockers import canonicalize
    try:
        claim_state = write_claim_state(run_dir)
    except Exception:
        claim_state = {}
    buckets[FINAL_SUBMISSION_BLOCKER] = canonicalize(buckets[FINAL_SUBMISSION_BLOCKER],
                                                     claim_state=claim_state)

    draft_blockers = buckets[DRAFT_BLOCKER]
    final_blockers = buckets[FINAL_SUBMISSION_BLOCKER]
    warnings = buckets[WARNING]

    if draft_blockers:
        technical = TECH_BLOCKED
    elif warnings:
        technical = TECH_NEEDS_FIXES
    else:
        technical = TECH_READY

    package = PKG_READY if not final_blockers else PKG_NOT_READY

    gaps_md = render_internal_gaps(buckets, extra_notes=extra_notes)

    return {
        "run_id": qa.get("run_id"),
        "plugin_version": qa.get("plugin_version"),
        "overall_status": qa.get("overall_status"),   # unchanged FINAL gate
        "technical_draft_status": technical,
        "submission_package_status": package,
        "draft_blockers": draft_blockers,
        "final_submission_blockers": final_blockers,
        "canonical_blockers": [b["blocker"] for b in final_blockers],
        "claim_state": {k: v.get("status") for k, v in
                        (claim_state.get("claims") or {}).items()},
        "warnings": warnings,
        "improvements": buckets["IMPROVEMENT"],
        "internal_gaps_md": gaps_md,
        "summary_line": f"Technical Draft: {technical.replace('_', ' ')}  ·  "
                        f"Submission Package: {package.replace('_', ' ')}",
    }
