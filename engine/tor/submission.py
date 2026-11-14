"""Submission checklist classifier (v0.6.4, production hardening §2).

Turns each submission/compliance requirement into a checklist entry with a STABLE
human item identity (e.g. "Example of previous work", "Detailed budget", "CV annex")
and an obligation level: MANDATORY | SCORING | OPTIONAL.

QA uses the item identity so a missing item is reported as the ACTUAL item
("Detailed budget missing") rather than a generic "[SUBMISSION] requirement missing".
Deterministic, text-cue based — never invents requirements.
"""
from __future__ import annotations

import re

MANDATORY = "MANDATORY"
SCORING = "SCORING"
OPTIONAL = "OPTIONAL"

# Obligation cues (checked in priority: optional > scoring > mandatory default).
_OPTIONAL_RE = re.compile(
    r"\b(optional|if available|if applicable|where possible|encouraged|desirable|"
    r"preferred|may (?:be )?(?:submit|include|provide)|nice to have)\b", re.I)
_SCORING_RE = re.compile(
    r"\b(scor\w*|evaluat\w* criteria|points?|weight\w*|\d{1,3}\s*%|percent|"
    r"assessed|marking|rated|technical score|financial score|criteria)\b", re.I)
_MANDATORY_RE = re.compile(
    r"\b(must|shall|mandatory|required|obligatory|is to be|are to be|"
    r"has to|have to|should (?:be )?(?:submit|include|provide))\b", re.I)

# Item identity cues → stable label + key. First match wins (order matters).
_ITEMS = [
    ("previous_work", "Example of previous work",
     r"\b(example|sample|previous|past)\b.*\b(work|report|evaluation|deliverable|assignment)\b"
     r"|\bwriting sample\b|\bsample report\b"),
    ("detailed_budget", "Detailed budget / financial offer",
     r"\b(detailed budget|budget breakdown|financial (?:offer|proposal|bid)|"
     r"price schedule|cost breakdown|bill of quantities|boq)\b"),
    ("cv_annex", "CV annex (team CVs)",
     r"\b(cv|cvs|curriculum vit|resum[eé]s?)\b"),
    ("cover_letter", "Cover letter",
     r"\bcover letter\b|\bletter of (?:interest|motivation|transmittal)\b"),
    ("technical_proposal", "Technical proposal",
     r"\btechnical (?:proposal|offer)\b"),
    ("work_plan", "Work plan / timeline",
     r"\b(work ?plan|workplan|timeline|schedule|gantt)\b"),
    ("methodology", "Methodology / approach",
     r"\b(methodolog|approach|inception)\b"),
    ("references", "References",
     r"\breferences?\b|\breference letters?\b"),
    ("registration", "Company registration / legal docs",
     r"\b(registration|incorporation|legal (?:entity|status)|licen[cs]e|certificate)\b"),
    ("tax", "Tax / VAT documentation",
     r"\b(tax|vat|fiscal|withholding)\b"),
    ("insurance", "Insurance",
     r"\binsurance\b"),
    ("signature", "Signed declaration / signature",
     r"\b(signature|signed|declaration|undertaking|self-?declaration)\b"),
    ("gender", "Gender-responsive procurement declaration",
     r"\bgender(?:-| )(?:responsive|equality)\b|\bwomen-?(?:owned|led)\b|\bgesi\b"),
    ("ethics", "Ethics / safeguarding",
     r"\b(ethic|safeguard|child protection|pseah|do no harm)\b"),
]


def classify_obligation(text: str, *, mandatory_flag: bool = True) -> str:
    """MANDATORY | SCORING | OPTIONAL from the requirement text and its parsed flag."""
    t = text or ""
    if _OPTIONAL_RE.search(t):
        return OPTIONAL
    if _SCORING_RE.search(t):
        return SCORING
    if _MANDATORY_RE.search(t):
        return MANDATORY
    # fall back to the extractor's mandatory flag (True → MANDATORY, else OPTIONAL)
    return MANDATORY if mandatory_flag else OPTIONAL


def identify_item(text: str) -> tuple[str, str]:
    """Return (item_key, human_label) for a submission requirement."""
    t = text or ""
    for key, label, pat in _ITEMS:
        if re.search(pat, t, re.I):
            return key, label
    return "other", "Submission item"


def classify_submission_requirement(req: dict) -> dict:
    """Full checklist entry for one requirement dict (req_id, text, mandatory…)."""
    text = req.get("text") or req.get("requirement") or ""
    key, label = identify_item(text)
    obligation = classify_obligation(text, mandatory_flag=req.get("mandatory", True))
    return {
        "requirement_id": req.get("req_id") or req.get("requirement_id") or "",
        "item_key": key,
        "item_label": label,
        "obligation": obligation,
        "text": text,
    }


def build_submission_checklist(requirements: list[dict]) -> list[dict]:
    """All submission/compliance requirements as classified checklist entries.

    Excludes CLIENT-actor requirements (obligations the client owes the bidder).
    """
    out = []
    for r in requirements or []:
        if r.get("actor") == "CLIENT":
            continue
        if r.get("category") != "submission":
            continue
        out.append(classify_submission_requirement(r))
    return out
