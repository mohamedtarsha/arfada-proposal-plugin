"""Richer Human Decision semantics for TOR analysis (Phase 1.2).

Separates TOR CONSTRAINTS from GENUINE PROPOSAL DECISIONS.

Key rule: a quantity pattern alone (AT_LEAST/APPROX/RANGE) does NOT make a
requirement a human decision. The semantic context matters:

  TEAM/ELIGIBILITY + AT_LEAST experience → FIXED_MINIMUM (constraint)
  DATA_COLLECTION + AT_LEAST method count → may be OPEN_PROPOSAL_DECISION
  SUBMISSION + AT_MOST pages → FIXED_MAXIMUM (constraint)
  Explicit "consultant proposes" → OPEN_PROPOSAL_DECISION
  "to be agreed during inception" → DEFERRED_DECISION
  APPROX quantity without open language → FIXED_MINIMUM (approximate target)

The backward-compatible `is_human_decision` flag is derived from the richer type.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional

from .value import parse_quantities, _ATLEAST, _ATMOST, _APPROX


# ---------------------------------------------------------------------------
# Decision types
# ---------------------------------------------------------------------------

# Human decision (bidder must choose a proposal value):
_OPEN_TYPES = {
    "OPEN_PROPOSAL_DECISION",
    "DEFERRED_DECISION",
    "OPTIONAL_CHOICE",
}

# Constraint (TOR-fixed, no proposal choice needed):
_CONSTRAINT_TYPES = {
    "FIXED_REQUIREMENT",
    "FIXED_MINIMUM",
    "FIXED_MAXIMUM",
    "FIXED_RANGE",
    "NO_DECISION",
}


# ---------------------------------------------------------------------------
# Data object
# ---------------------------------------------------------------------------

@dataclass
class DecisionCandidate:
    decision_id: str
    requirement_id: str
    decision_type: str          # see _OPEN_TYPES / _CONSTRAINT_TYPES
    is_human_decision: bool     # True iff decision_type in _OPEN_TYPES
    question: Optional[str]     # human-readable question (only for open types)
    constraint_type: str        # AT_LEAST | AT_MOST | RANGE | APPROX | EXACT | NONE
    minimum: Optional[float]
    maximum: Optional[float]
    fixed_value: Optional[str]
    allowed_options: list[str] = field(default_factory=list)
    reason: str = ""
    source_text: str = ""
    source_locator: str = ""
    category: str = ""
    actor: str = ""


# ---------------------------------------------------------------------------
# Semantic category groups
# ---------------------------------------------------------------------------

# Categories where AT_LEAST/APPROX on a QUANTITY = qualification constraint,
# not a proposal design decision (the minimum threshold is TOR-fixed).
_QUALIFICATION_CATEGORIES = {
    "team", "eligibility", "general",
}

# Categories where FIXED submissions / deadlines / outputs apply.
_SUBMISSION_CATEGORIES = {
    "submission", "deliverable", "timeline",
}

# Categories where method count minimums may become bounded design decisions.
_METHOD_CATEGORIES = {
    "methodology", "data_collection_methods", "sampling",
}

# Keywords that indicate method instances (KIIs, FGDs, surveys, etc.).
# Uses (?:...) without strict word boundaries to handle Arabic plurals (مقابلة/مقابلات)
# and English plurals (KIIs/FGDs).
_METHOD_INSTANCE = re.compile(
    r"(?:kiis?|fgds?|idis?|interviews?|focus\s+groups?|household\s+surveys?|surveys?|"
    r"questionnaires?|مقابل[ةاتهي]?|مجموع[ةاتهي]?|استبيان[ات]?|مسح[ات]?|"
    r"تركيز|بحث\s+ميدان|بيانات\s+أولية)",
    re.I | re.UNICODE,
)

# Keywords that indicate experience / qualifications.
_QUALIFICATION_KEYWORDS = re.compile(
    r"\b(year|experience|degree|certificate|assignment|contract|project|prior|previous|"
    r"سنة|سنوات|خبرة|شهادة|مؤهل|سابق)\b",
    re.I | re.UNICODE,
)

# Deferred-decision language.
_DEFERRED_CUES = re.compile(
    r"\b(to\s+be\s+(?:agreed|finalized|confirmed|determined|discussed|elaborated)|"
    r"during\s+(?:the\s+)?inception|at\s+inception|inception\s+phase|will\s+be\s+agreed|"
    r"يُتفق\s+عليه|سيتم\s+الاتفاق|خلال\s+مرحلة\s+الانطلاق|في\s+مرحلة\s+الانطلاق)\b",
    re.I | re.UNICODE,
)

# Open-choice / consultant-proposes language.
_OPEN_CHOICE = re.compile(
    r"\b(as\s+appropriate|consultant(?:'s)?\s+(?:discretion|choice|judgment|decision)|"
    r"propose(?:d)?\s+(?:approach|methodology|sample|method)|at\s+the\s+discretion|"
    r"to\s+be\s+(?:proposed|developed\s+by)|consultant\s+shall\s+propose|"
    r"to\s+be\s+determined\b|tbd\b)\b",
    re.I,
)
_AR_OPEN_CHOICE = re.compile(
    r"(?:حسب\s+ما\s+يراه\s+(?:الاستشاري\s+)?مناسباً?|وفق\s+(?:المنهجية\s+)?المقترحة?|"
    r"يقترح\s+(?:الاستشاري|مقدم\s+العرض)|حسب\s+الحاجة|عند\s+الاقتضاء|"
    r"حسب\s+تقديره|وفق\s+تقدير|حسب\s+رأيه)",
    re.UNICODE,
)


# ---------------------------------------------------------------------------
# Constraint extraction
# ---------------------------------------------------------------------------

def _extract_constraint(text: str) -> dict:
    """Determine constraint type and bounds from requirement text.

    Uses parse_quantities() for numeric values and also scans the full text
    for Arabic trailing qualifiers (e.g. '6 FGDs على الأقل').
    """
    qs = parse_quantities(text)

    # Supplement with direct pattern search (catches trailing Arabic qualifiers).
    has_at_least = any(q.qualifier == "AT_LEAST" for q in qs) or bool(_ATLEAST.search(text))
    has_at_most  = any(q.qualifier == "AT_MOST"  for q in qs) or bool(_ATMOST.search(text))
    has_approx   = any(q.qualifier == "APPROX"   for q in qs) or bool(_APPROX.search(text))
    has_range    = any(q.qualifier == "RANGE"     for q in qs)

    nums  = [q.value for q in qs if q.value  is not None]
    maxes = [q.value_max for q in qs if q.value_max is not None]

    min_val = min(nums)  if nums  else None
    max_val = (max(maxes) if maxes
               else (min_val if has_at_most and nums else None))

    if has_at_most and not has_at_least:
        return {"constraint_type": "AT_MOST", "minimum": None, "maximum": max_val or min_val}
    if has_range:
        range_q = next((q for q in qs if q.qualifier == "RANGE"), None)
        return {"constraint_type": "RANGE",
                "minimum": range_q.value     if range_q else min_val,
                "maximum": range_q.value_max if range_q else None}
    if has_at_least:
        return {"constraint_type": "AT_LEAST", "minimum": min_val, "maximum": None}
    if has_approx:
        return {"constraint_type": "APPROX", "minimum": min_val, "maximum": None}
    if nums:
        return {"constraint_type": "EXACT", "minimum": min_val, "maximum": min_val}
    return {"constraint_type": "NONE", "minimum": None, "maximum": None}


# ---------------------------------------------------------------------------
# Question generation
# ---------------------------------------------------------------------------

def _unit_label(text: str) -> str:
    """Extract the first method/unit mention for question phrasing."""
    m = _METHOD_INSTANCE.search(text)
    return m.group(0).upper() if m else "instances"


def _question_method_bounded(text: str, min_val: Optional[float],
                              max_val: Optional[float], ctype: str) -> str:
    unit = _unit_label(text)
    if ctype == "RANGE" and min_val is not None and max_val is not None:
        return (f"The TOR requires {int(min_val)}–{int(max_val)} {unit}s. "
                f"What exact number should ARFADA propose? "
                f"(must be between {int(min_val)} and {int(max_val)})")
    if min_val is not None:
        return (f"The TOR requires at least {int(min_val)} {unit}s. "
                f"What exact number should ARFADA propose? "
                f"(must be >= {int(min_val)})")
    return f"The TOR specifies a method count for {unit}s. What number should be proposed?"


def _question_open(req) -> str:
    cat = req.category or "methodology"
    return (f"The TOR leaves the {cat.replace('_', ' ')} to the consultant's discretion. "
            f"What approach should ARFADA propose?")


def _question_deferred(req) -> str:
    snippet = (req.text or "")[:80]
    return (f"The TOR states this will be agreed later: '{snippet}…'. "
            f"Should the proposal explicitly defer this decision to the inception phase?")


def _question_sampling_open(req) -> str:
    return ("The TOR leaves the sampling approach to the consultant. "
            "What sampling methodology, sample size, and strata should be proposed?")


# ---------------------------------------------------------------------------
# Main classifier
# ---------------------------------------------------------------------------

def classify_decision(req, actor: str) -> DecisionCandidate:
    """Classify a requirement into a richer decision type.

    Returns a DecisionCandidate with is_human_decision derived from decision_type.
    """
    text = req.text or ""
    cat  = req.category or "general"

    def _make(dtype: str, **kw) -> DecisionCandidate:
        did = "dec_" + hashlib.sha1(
            (req.req_id + dtype).encode()
        ).hexdigest()[:12]
        is_hd = dtype in _OPEN_TYPES
        return DecisionCandidate(
            decision_id=did,
            requirement_id=req.req_id,
            decision_type=dtype,
            is_human_decision=is_hd,
            question=kw.get("question"),
            constraint_type=kw.get("constraint_type", "NONE"),
            minimum=kw.get("minimum"),
            maximum=kw.get("maximum"),
            fixed_value=kw.get("fixed_value"),
            allowed_options=kw.get("allowed_options", []),
            reason=kw.get("reason", ""),
            source_text=text[:300],
            source_locator=req.source_locator or "",
            category=cat,
            actor=actor,
        )

    # Rule 1: CLIENT responsibilities never create bidder decisions.
    if actor == "CLIENT":
        return _make("NO_DECISION", reason="Client responsibility — no bidder choice")

    # Rule 2: Deferred language → DEFERRED_DECISION.
    if _DEFERRED_CUES.search(text):
        return _make("DEFERRED_DECISION",
                     question=_question_deferred(req),
                     reason="TOR defers this decision to a later phase")

    # Rule 3: Explicit open-choice → OPEN_PROPOSAL_DECISION.
    if _OPEN_CHOICE.search(text) or _AR_OPEN_CHOICE.search(text):
        if cat == "sampling":
            return _make("OPEN_PROPOSAL_DECISION",
                         question=_question_sampling_open(req),
                         reason="TOR explicitly defers sampling design to consultant")
        if cat in _METHOD_CATEGORIES | {"general"}:
            return _make("OPEN_PROPOSAL_DECISION",
                         question=_question_open(req),
                         reason="TOR explicitly defers approach/method to consultant")
        return _make("OPTIONAL_CHOICE",
                     reason="Optional enhancement left to consultant discretion")

    # Rule 4: Quantity analysis.
    con = _extract_constraint(text)
    ctype   = con["constraint_type"]
    min_val = con["minimum"]
    max_val = con["maximum"]

    # AT_MOST → always a fixed constraint (pages, deadlines, durations).
    if ctype == "AT_MOST":
        return _make("FIXED_MAXIMUM",
                     constraint_type=ctype, maximum=max_val,
                     reason="TOR-fixed upper bound — no proposal choice")

    # Fixed submission/deliverable/timeline → hard constraint.
    if cat in _SUBMISSION_CATEGORIES:
        return _make("FIXED_REQUIREMENT",
                     constraint_type=ctype, minimum=min_val, maximum=max_val,
                     reason="Submission/deliverable/timeline constraint — not a bidder choice")

    # TEAM/ELIGIBILITY with any quantity → qualification threshold, not decision.
    if cat in _QUALIFICATION_CATEGORIES and ctype != "NONE":
        return _make("FIXED_MINIMUM",
                     constraint_type=ctype, minimum=min_val, maximum=max_val,
                     reason="Qualification/eligibility threshold — constraint, not a proposal design choice")

    # METHOD_CATEGORIES with an AT_LEAST count on method instances →
    # bounded design decision (proposal must specify exact count ≥ min).
    if cat in _METHOD_CATEGORIES and ctype in ("AT_LEAST",) and _METHOD_INSTANCE.search(text):
        return _make("OPEN_PROPOSAL_DECISION",
                     constraint_type=ctype, minimum=min_val,
                     question=_question_method_bounded(text, min_val, max_val, ctype),
                     reason="TOR sets minimum method count; proposal must specify exact count")

    # Range on method count → bounded design decision.
    if cat in _METHOD_CATEGORIES and ctype == "RANGE" and _METHOD_INSTANCE.search(text):
        return _make("OPEN_PROPOSAL_DECISION",
                     constraint_type=ctype, minimum=min_val, maximum=max_val,
                     question=_question_method_bounded(text, min_val, max_val, ctype),
                     reason="TOR specifies allowed range; proposal must specify exact count within range")

    # APPROX in sampling/methodology = approximate target, not open choice.
    if ctype == "APPROX" and cat in (_METHOD_CATEGORIES | _QUALIFICATION_CATEGORIES):
        return _make("FIXED_MINIMUM",
                     constraint_type=ctype, minimum=min_val,
                     reason="Approximate TOR target — not an unrestricted bidder choice")

    # EXACT fixed count → requirement, no choice.
    if ctype == "EXACT" and min_val is not None:
        return _make("FIXED_REQUIREMENT",
                     constraint_type=ctype, minimum=min_val, maximum=min_val,
                     reason="TOR specifies exact count")

    # Fallback for any remaining AT_LEAST in a non-method context.
    if ctype in ("AT_LEAST",):
        return _make("FIXED_MINIMUM",
                     constraint_type=ctype, minimum=min_val,
                     reason="TOR minimum constraint")

    return _make("NO_DECISION", reason="No open bidder choice detected")


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------

def validate_proposed_value(candidate: DecisionCandidate, proposed: float) -> dict:
    """Check a proposed value against TOR constraints.

    Returns {"valid": bool, "message": str}.
    """
    if candidate.minimum is not None and proposed < candidate.minimum:
        return {"valid": False,
                "message": f"Proposed value {proposed} is below TOR minimum {candidate.minimum}"}
    if candidate.maximum is not None and proposed > candidate.maximum:
        return {"valid": False,
                "message": f"Proposed value {proposed} exceeds TOR maximum {candidate.maximum}"}
    return {"valid": True, "message": "Within TOR constraints"}
