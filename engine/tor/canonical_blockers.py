"""Canonical submission blockers (v0.6.11).

Different checks can report the same missing artifact (a pending-item check, the
physical package check, a QA "claimed annex" finding …). Final-submission status
lists ONE canonical blocker per unresolved item:

  FINANCIAL_PROPOSAL · PREVIOUS_WORK_SAMPLE · REGISTRATION_EVIDENCE · TEAM_CV_PACKAGE ·
  TEAM_AVAILABILITY · SUBMISSION_CHANNEL · DEADLINE_CONFIRMATION · OTHER:<item>

``proposal_final.docx`` is an export step, not a substantive blocker: it is never
listed (the final is produced by export_final.py once the real items are resolved).
"""
from __future__ import annotations

import re

LABELS = {
    "FINANCIAL_PROPOSAL": "Financial proposal / detailed budget",
    "PREVIOUS_WORK_SAMPLE": "Previous-work sample",
    "PREVIOUS_WORK_CLEARANCE": "Previous-work sharing clearance",
    "REGISTRATION_EVIDENCE": "Registration evidence",
    "TEAM_CV_PACKAGE": "Team CV package",
    "TEAM_AVAILABILITY": "Team availability",
    "SUBMISSION_CHANNEL": "Submission channel",
    "DEADLINE_CONFIRMATION": "Deadline confirmation",
}
# claim-state key -> canonical blocker
CLAIM_TO_BLOCKER = {
    "financial_proposal": "FINANCIAL_PROPOSAL",
    "previous_work_sample": "PREVIOUS_WORK_SAMPLE",
    "registration_evidence": "REGISTRATION_EVIDENCE",
    "team_cv_package": "TEAM_CV_PACKAGE",
    "team_availability": "TEAM_AVAILABILITY",
    "submission_channel": "SUBMISSION_CHANNEL",
    "deadline": "DEADLINE_CONFIRMATION",
}
_ITEM_KEY = {"detailed_budget": "FINANCIAL_PROPOSAL", "previous_work": "PREVIOUS_WORK_SAMPLE",
             "registration": "REGISTRATION_EVIDENCE", "cv_annex": "TEAM_CV_PACKAGE"}
_RULES = [
    # a dated submission instruction ("submitted to ZOA by 12:00 AM, 21 November") is
    # the deadline item, whatever else the sentence names
    ("DEADLINE_CONFIRMATION", r"\bdeadline\b|closing\s+date|no\s+later\s+than|"
                              r"submi\w+\s+(?:[\w.@-]+\s+){0,5}?(?:by|before|until)\s+\d"),
    ("FINANCIAL_PROPOSAL", r"financial\s+(?:proposal|offer)|\bbudget\b"),
    ("PREVIOUS_WORK_SAMPLE", r"previous[- ]work|example\s+of\s+previous|past\s+work"),
    ("REGISTRATION_EVIDENCE", r"registration"),
    ("TEAM_CV_PACKAGE", r"\bcvs?\b|curriculum\s+vit|resum[eé]"),
    ("TEAM_AVAILABILITY", r"availability"),
    ("SUBMISSION_CHANNEL", r"submission\s+channel|submission\s+platform"),
    ("DEADLINE_CONFIRMATION", r"deadline"),
]
# the proposal documents themselves are produced by the workflow, not package items
_EXPORT_STEP = re.compile(r"proposal_final\.docx|final\s+(?:docx|export)|"
                          r"(?:missing|pending)[:\s—-]+technical\s+(?:proposal|offer)\b", re.I)


def _message(item) -> str:
    return str(item.get("message", "") if isinstance(item, dict) else item)


def classify(item) -> str:
    """Canonical key for one blocker (``EXPORT_STEP`` for proposal_final.docx)."""
    if isinstance(item, dict):
        if item.get("canonical"):
            return item["canonical"]
        if item.get("item_key") in _ITEM_KEY:
            return _ITEM_KEY[item["item_key"]]
    msg = _message(item)
    if _EXPORT_STEP.search(msg):
        return "EXPORT_STEP"
    for key, pat in _RULES:
        if re.search(pat, msg, re.I):
            return key
    m = re.search(r"(?:missing|pending)[:\s—-]+(.+)$", msg, re.I)
    label = (m.group(1) if m else msg).strip().rstrip(".")
    label = re.sub(r"^(?:Annex:\s*|Mandatory submission item missing:\s*)", "", label, flags=re.I)
    return "OTHER:" + re.sub(r"\s+", " ", label.lower())[:60]


def canonicalize(items: list, *, claim_state: dict = None) -> list:
    """One blocker per unresolved item; sources kept for traceability."""
    out: dict = {}
    order: list = []
    cs = (claim_state or {}).get("claims") or {}
    # v0.6.12: once a report is SELECTED, the open item is its sharing CLEARANCE
    pw_selected = (cs.get("previous_work_selected") or {}).get("status") == "VERIFIED"
    pw_cleared = (cs.get("previous_work_clearance") or {}).get("status") == "VERIFIED"
    pw_key = "PREVIOUS_WORK_CLEARANCE" if pw_selected and not pw_cleared else "PREVIOUS_WORK_SAMPLE"

    def add(key, item, primary=False):
        if key == "EXPORT_STEP":
            return
        if key == "PREVIOUS_WORK_SAMPLE":
            key = pw_key
        if key not in out:
            label = LABELS.get(key) or key.split(":", 1)[-1].capitalize()
            out[key] = {"blocker": key, "label": label, "message": _message(item),
                        "recommended_action": (item.get("recommended_action", "")
                                               if isinstance(item, dict) else ""),
                        "sources": []}
            order.append(key)
        elif primary:
            out[key]["message"] = _message(item)
            if isinstance(item, dict) and item.get("recommended_action"):
                out[key]["recommended_action"] = item["recommended_action"]
        out[key]["sources"].append(_message(item))

    # pending-item checks carry the most precise message → primary
    for it in items or []:
        add(classify(it), it, primary=isinstance(it, dict) and
            it.get("check") == "SUBMISSION_PENDING")
    # claim state: unresolved required facts are blockers too
    for ckey, bkey in CLAIM_TO_BLOCKER.items():
        c = ((claim_state or {}).get("claims") or {}).get(ckey) or {}
        if c.get("required", True) and c.get("status") in ("MISSING", "UNVERIFIED", "PROVISIONAL"):
            label = LABELS[pw_key] if bkey == "PREVIOUS_WORK_SAMPLE" else LABELS[bkey]
            detail = c.get("detail", c.get("status"))
            if bkey == "PREVIOUS_WORK_SAMPLE" and pw_key == "PREVIOUS_WORK_CLEARANCE":
                detail = (cs.get("previous_work_clearance") or {}).get("detail", detail)
            add(bkey, {"message": f"{label} pending — {detail}",
                       "recommended_action": ("Record explicit permission to share the selected "
                                              "report (previous_work.py clear --note …)."
                                              if pw_key == "PREVIOUS_WORK_CLEARANCE" and
                                              bkey == "PREVIOUS_WORK_SAMPLE"
                                              else "Resolve before final submission.")})
    return [out[k] for k in order]
