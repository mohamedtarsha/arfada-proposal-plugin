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
    rec = _load(run_dir / "previous_work.json")
    files = _files(run_dir, "previous_work")
    if rec:
        f = rec.get("file")
        present = bool(files) or bool(f and Path(f).exists())
        if not rec.get("clearance_confirmed"):
            return False, "sharing clearance not confirmed"
        if not present:
            return False, "registered file not found in the package"
        return True, "cleared and annexed"
    if files:
        return False, "file present but not registered / clearance not confirmed"
    return False, "no example selected or cleared for sharing"


def registration_state(run_dir: Path) -> tuple[bool, str]:
    files = _files(run_dir, "registration")
    return (True, "registration file in package") if files else \
        (False, "no registration evidence in the package")


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
                                              "(previous_work.py register … --confirm-clearance)."})
    if "registration" in items:
        ok, why = registration_state(run_dir)
        if not ok:
            out.append({"check": "SUBMISSION_PENDING", "item_key": "registration",
                        "requirement_id": items["registration"]["requirement_id"],
                        "message": f"Registration evidence pending — {why}",
                        "recommended_action": "Place the registration certificate under "
                                              "annexes/registration/."})
    return out
