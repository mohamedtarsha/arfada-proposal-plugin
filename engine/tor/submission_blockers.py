"""Pending submission items that block FINAL submission (never the draft).

The TOR often lists what the proposal must include ("1. Technical proposal …
2. Financial proposal: detailed budget … 3. Examples of previous work …"). Those
lines are frequently classified as proposal-format requirements, not
`submission`, so the package check never saw them. This module reads the run's own
state and reports, for TOR-required items, what is still unresolved:

* financial proposal / detailed budget — no reconciled ``budget.json`` and no budget
  file in the package (e.g. rates not provided);
* example of previous work — nothing registered, or sharing clearance not confirmed;
* evidence of registration (v0.6.10) — the TOR asks for it and no registration file
  is in the package.

Each is a FINAL_SUBMISSION_BLOCKER: proposal_draft_v1.docx is still produced.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from .submission import classify_submission_requirement, MANDATORY

# requirement categories whose items can name a physical submission deliverable
_ITEM_CATEGORIES = ("submission", "proposal_format")
_TRACKED = ("detailed_budget", "previous_work", "registration")
# registration is often an eligibility line ("Evidence of registration as a firm")
_REGISTRATION_ASK = re.compile(
    r"\b(?:evidence|proof|copy|certificate)\s+of\s+(?:\w+\s+){0,2}?registration\b|"
    r"\bregistration\s+(?:certificate|documents?|evidence)\b", re.I)


def _load(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except Exception:
        return None


def _files(run_dir: Path, sub: str) -> list:
    out = []
    for base in (run_dir / "annexes" / sub, run_dir / sub):
        if base.is_dir():
            out += [str(p) for p in base.iterdir() if p.is_file()]
    return out


def required_items(requirements: list) -> dict:
    """TOR-required tracked items: item_key -> checklist entry (MANDATORY only)."""
    found: dict = {}
    for r in requirements or []:
        if r.get("actor") == "CLIENT":
            continue
        if r.get("category") not in _ITEM_CATEGORIES:
            if _REGISTRATION_ASK.search(r.get("text") or ""):
                entry = classify_submission_requirement(r)
                entry.update(item_key="registration", obligation=MANDATORY)
                found.setdefault("registration", entry)
            continue
        entry = classify_submission_requirement(r)
        if entry["item_key"] in _TRACKED and entry["obligation"] == MANDATORY:
            found.setdefault(entry["item_key"], entry)
    return found


def budget_state(run_dir: Path) -> tuple[bool, str]:
    budget = _load(run_dir / "budget.json")
    files = _files(run_dir, "budget") + [str(p) for p in
             (run_dir / n for n in ("financial_offer.xlsx", "financial_offer.docx",
                                    "detailed_budget.xlsx", "detailed_budget.docx"))
             if p.exists()]
    if budget and budget.get("reconciles") and not budget.get("missing_inputs"):
        return True, "reconciled budget.json"
    if files:
        return True, "budget file in package"
    if budget and budget.get("missing_inputs"):
        return False, "budget inputs missing: " + ", ".join(map(str, budget["missing_inputs"]))
    if budget:
        return False, "budget does not reconcile to the approved total"
    return False, "no budget built (daily rates / costs not provided)"


def previous_work_state(run_dir: Path) -> tuple[bool, str]:
    """Resolved only when a report is SELECTED and explicit SHARING CLEARANCE exists
    (v0.6.12: a selection, or ARFADA authorship, is never clearance)."""
    from .previous_work_state import previous_work_states, VERIFIED
    st = previous_work_states(run_dir)
    sel, cl = st["selected"], st["clearance"]
    if sel["status"] != VERIFIED:
        return False, ("no example selected or cleared for sharing"
                       if sel["status"] == "MISSING" else sel["detail"])
    if cl["status"] != VERIFIED:
        return False, f"sharing clearance not confirmed for {sel.get('file', 'the selected report')}"
    return True, "selected, cleared and annexed"


def registration_state(run_dir: Path) -> tuple[bool, str]:
    files = _files(run_dir, "registration")
    if files:
        return True, "registration file in package"
    # v0.6.16: say whether ARFADA Knowledge holds candidates (the employee chooses one)
    try:
        from .package_builder import registration_candidates
        cands = registration_candidates()
    except Exception:
        cands = []
    if len(cands) > 1:
        return False, (f"{len(cands)} registration documents found in ARFADA Knowledge/Company — "
                       "choose one (run_decision.py <run_dir> registration-choice \"<file>\")")
    return False, "no registration evidence in the package (none found in ARFADA Knowledge/Company)"


def pending_submission_blockers(run_dir: str | Path, requirements: list) -> list:
    """FINAL_SUBMISSION_BLOCKER gaps for unresolved TOR-required budget / previous work."""
    run_dir = Path(run_dir)
    out = []
    items = required_items(requirements)
    if "detailed_budget" in items:
        ok, why = budget_state(run_dir)
        if not ok:
            out.append({"check": "SUBMISSION_PENDING", "item_key": "detailed_budget",
                        "requirement_id": items["detailed_budget"]["requirement_id"],
                        "message": f"Financial proposal / detailed budget pending — {why}",
                        "recommended_action": "Collect the rates and build the reconciled "
                                              "budget (budget_builder.py); never invent values."})
    if "previous_work" in items:
        ok, why = previous_work_state(run_dir)
        if not ok:
            out.append({"check": "SUBMISSION_PENDING", "item_key": "previous_work",
                        "requirement_id": items["previous_work"]["requirement_id"],
                        "message": f"Previous-work example pending — {why}",
                        "recommended_action": "Choose the report and confirm ARFADA may share it "
                                              "(previous_work.py clear <run_dir> --note "
                                              "\"<explicit permission words>\")."})
    if "registration" in items:
        ok, why = registration_state(run_dir)
        if not ok:
            out.append({"check": "SUBMISSION_PENDING", "item_key": "registration",
                        "requirement_id": items["registration"]["requirement_id"],
                        "message": f"Registration evidence pending — {why}",
                        "recommended_action": "Place the registration certificate under "
                                              "annexes/registration/."})
    return out
