"""Interactive Decision-Review question descriptors (v0.6.3 — UX only).

Turns a genuine proposal decision into a structured descriptor the Claude Code
session feeds to the native AskUserQuestion UI (selectable option cards), with a
numbered-list fallback. This module changes NO decision semantics, validation, or
persistence — it only shapes how a decision is PRESENTED.

A descriptor:
{
  "decision_id": "...", "requirement_id": "...", "kind": "TOR_EXTRACTED|PROPOSAL_DESIGN|META",
  "header": "<=12 chars chip", "question": "short question",
  "tor_context": "optional one line",
  "options": [ {"label","value","recommended","action","kind"} ... ],
  "supports_custom": bool, "constraint": {"type","minimum","maximum"},
  "fallback_numbered": "…1. … 2. …",
}

`action` tells the skill which decision_register.py command to run:
  set | defer | unresolved | recommend | custom   (custom → prompt then set+validate)

Fixed TOR requirements never produce a descriptor (they are constraints, not questions).
"""
from __future__ import annotations

import re
from typing import Any, Optional

_OPEN_TYPES = {"OPEN_PROPOSAL_DECISION", "DEFERRED_DECISION", "OPTIONAL_CHOICE"}
_FIXED_TYPES = {"FIXED_REQUIREMENT", "FIXED_MINIMUM", "FIXED_MAXIMUM",
                "FIXED_RANGE", "NO_DECISION"}

# Arabic labels (canonical stored value is unchanged; only the label is localized)
_AR = {
    "Recommended": "موصى به",
    "Other": "أخرى",
    "Enter custom answer": "إدخال إجابة مخصصة",
    "Enter exact value": "إدخال قيمة محددة",
    "Enter another amount": "إدخال مبلغ آخر",
    "Determine during inception": "يُحدد في مرحلة الانطلاق",
    "Set a value now": "تحديد قيمة الآن",
    "Show me a recommendation": "اعرض توصية",
    "Leave unresolved": "تركه دون حسم",
    "Defer if TOR permits": "تأجيل إن سمح الـTOR",
    "Include": "تضمين",
    "Do not include": "عدم التضمين",
    "Decide later": "القرار لاحقاً",
    "Use recommended value": "استخدام القيمة الموصى بها",
    "weeks": "أسابيع",
    "Reply with the number.": "أجب برقم الخيار.",
}


def _t(label: str, language: str) -> str:
    if (language or "").lower().startswith("ar"):
        return _AR.get(label, label)
    return label


def _mark(label: str, recommended: bool, language: str) -> str:
    if recommended:
        return f"{label} — {_t('Recommended', language)}"
    return label


def is_question(decision: dict) -> bool:
    """A decision becomes an interactive card only if it is a genuine human decision."""
    if decision.get("decision_type") in _FIXED_TYPES:
        return False
    return bool(decision.get("is_human_decision")) or \
        decision.get("decision_type") in _OPEN_TYPES


def _header(category: str) -> str:
    # AskUserQuestion header chips are capped at 12 characters.
    label = {
        "assignment_type": "Assign type", "methodology": "Methodology",
        "sampling": "Sampling", "data_collection_methods": "Data collect",
        "evaluation_questions": "Eval matrix", "timeline": "Timeline",
        "team": "Team", "deliverable": "Deliverable", "submission": "Submission",
    }.get(category, (category or "Decision").replace("_", " ").title())
    return label[:12]


# ---------------------------------------------------------------------------
# Option builders
# ---------------------------------------------------------------------------

def _opt(label, value, *, recommended=False, action="set", kind="VALUE"):
    return {"label": label, "value": value, "recommended": recommended,
            "action": action, "kind": kind}


def _enum_options(allowed: list, language: str) -> list[dict]:
    opts = []
    for i, v in enumerate(allowed or []):
        opts.append(_opt(_mark(str(v), i == 0, language), str(v).upper(),
                         recommended=(i == 0), action="set", kind="ENUM"))
    opts.append(_opt(_t("Other", language), None, action="custom", kind="CUSTOM"))
    return opts


def _range_options(mn: float, mx: float, language: str, unit: str = "") -> tuple[list, Any]:
    mn_i, mx_i = int(mn), int(mx)
    mid = int(round((mn_i + mx_i) / 2))
    unit_lbl = (" " + _t(unit, language)) if unit else ""
    opts = []
    if (mx_i - mn_i) <= 4:
        for v in range(mn_i, mx_i + 1):
            opts.append(_opt(_mark(f"{v}{unit_lbl}", v == mid, language), v,
                             recommended=(v == mid), action="set"))
        opts.append(_opt(_t("Other", language), None, action="custom", kind="CUSTOM"))
    else:
        opts.append(_opt(_mark(f"{mid}{unit_lbl} ({_t('Use recommended value', language)})",
                               True, language), mid, recommended=True, action="set"))
        opts.append(_opt(_t("Enter exact value", language), None, action="custom", kind="CUSTOM"))
    return opts, mid


def _at_least_options(mn: float, language: str, unit: str = "") -> tuple[list, Any]:
    mn_i = int(mn)
    unit_lbl = (" " + _t(unit, language)) if unit else ""
    opts = [
        _opt(_mark(f"{mn_i}{unit_lbl}", True, language), mn_i, recommended=True, action="set"),
        _opt(_t("Enter exact value", language), None, action="custom", kind="CUSTOM"),
    ]
    return opts, mn_i


def _deferred_options(language: str) -> list[dict]:
    return [
        _opt(_mark(_t("Determine during inception", language), True, language),
             "DEFER_TO_INCEPTION", recommended=True, action="defer", kind="DEFER"),
        _opt(_t("Set a value now", language), None, action="custom", kind="CUSTOM"),
        _opt(_t("Show me a recommendation", language), None, action="recommend",
             kind="RECOMMENDATION"),
        _opt(_t("Leave unresolved", language), None, action="unresolved", kind="UNRESOLVED"),
    ]


def _optional_options(language: str) -> list[dict]:
    return [
        _opt(_t("Include", language), "INCLUDE", action="set"),
        _opt(_t("Do not include", language), "DO_NOT_INCLUDE", action="set"),
        _opt(_t("Decide later", language), None, action="defer", kind="DEFER"),
        _opt(_t("Leave unresolved", language), None, action="unresolved", kind="UNRESOLVED"),
    ]


def _open_options(language: str, permits_defer: bool = True) -> list[dict]:
    opts = [
        _opt(_t("Enter custom answer", language), None, action="custom", kind="CUSTOM"),
        _opt(_t("Show me a recommendation", language), None, action="recommend",
             kind="RECOMMENDATION"),
    ]
    if permits_defer:
        opts.append(_opt(_t("Defer if TOR permits", language), "DEFER_TO_INCEPTION",
                         action="defer", kind="DEFER"))
    return opts


# ---------------------------------------------------------------------------
# Unit detection
# ---------------------------------------------------------------------------

_UNIT_RE = {
    "weeks": r"\bweeks?\b|أسابيع", "days": r"\bdays?\b",
    "KII": r"\bkiis?\b|key\s+informant", "FGD": r"\bfgds?\b|focus\s+group",
}


def _unit(source_text: str) -> str:
    low = (source_text or "").lower()
    for unit, pat in _UNIT_RE.items():
        if re.search(pat, low, re.I):
            return unit
    return ""


# ---------------------------------------------------------------------------
# Main descriptor builder
# ---------------------------------------------------------------------------

def build_question_descriptor(decision: dict, *, language: str = "english",
                              kind: str = "TOR_EXTRACTED") -> Optional[dict]:
    """Build an AskUserQuestion-ready descriptor, or None for a fixed requirement."""
    if not is_question(decision):
        return None

    dtype = decision.get("decision_type")
    ctype = decision.get("constraint_type")
    mn, mx = decision.get("minimum"), decision.get("maximum")
    category = decision.get("category", "")
    source = decision.get("source_text", "")
    unit = _unit(source)
    recommended_value: Any = None

    # question text (keep short; Arabic if requested)
    q = decision.get("question") or "What should ARFADA propose?"
    q = re.sub(r"\s+", " ", q).strip()
    if len(q) > 160:
        q = q[:157] + "…"

    # options by shape
    if ctype == "ENUM" or decision.get("allowed_options"):
        options = _enum_options(decision.get("allowed_options", []), language)
        if options:
            recommended_value = options[0]["value"]
    elif dtype == "DEFERRED_DECISION":
        options = _deferred_options(language)
    elif dtype == "OPTIONAL_CHOICE":
        options = _optional_options(language)
    elif ctype == "RANGE" and mn is not None and mx is not None:
        options, recommended_value = _range_options(mn, mx, language, unit)
    elif ctype == "AT_LEAST" and mn is not None:
        options, recommended_value = _at_least_options(mn, language, unit)
    else:
        options = _open_options(language)

    supports_custom = any(o["action"] == "custom" for o in options)

    descriptor = {
        "decision_id": decision.get("decision_id"),
        "requirement_id": decision.get("requirement_id"),
        "kind": kind,  # TOR_EXTRACTED | PROPOSAL_DESIGN | META
        "header": _header(category),
        "question": q,
        "tor_context": _tor_context(source, language),
        "options": options,
        "supports_custom": supports_custom,
        "recommended_value": recommended_value,
        "constraint": {"type": ctype, "minimum": mn, "maximum": mx},
        "fallback_numbered": _fallback(q, options, language),
    }
    return descriptor


def _tor_context(source: str, language: str) -> str:
    s = re.sub(r"\s+", " ", (source or "")).strip()
    if not s:
        return ""
    if len(s) > 120:
        s = s[:117] + "…"
    prefix = "الـTOR: " if (language or "").lower().startswith("ar") else "TOR: "
    return prefix + s


def _fallback(question: str, options: list[dict], language: str) -> str:
    lines = [question]
    for i, o in enumerate(options, 1):
        lines.append(f"{i}. {o['label']}")
    lines.append(_t("Reply with the number.", language))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Meta: expired-date card (spec §13) — deterministic, optional
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(
    r"\b(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{4})|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+(\d{4})|"
    r"\b(20\d{2})-\d{2}-\d{2})\b", re.I)


def expired_date_descriptor(tor: dict, *, today_year: int, language: str = "english"
                            ) -> Optional[dict]:
    """If the TOR's submission/timeline dates are already past, return one concise card."""
    meta = tor.get("metadata", {})
    text = ""
    for k in ("submission_requirements", "timeline"):
        e = meta.get(k)
        if isinstance(e, dict):
            text += " " + (e.get("value") or "")
    years = [int(y) for m in _DATE_RE.finditer(text) for y in m.groups()[1:] if y]
    if not years or max(years) >= today_year:
        return None
    q = ("This TOR contains expired dates. How should I treat it?"
         if not (language or "").lower().startswith("ar")
         else "يحتوي هذا الـTOR على تواريخ منتهية. كيف أتعامل معه؟")
    opts = [
        _opt(_mark("Historical / test case", True, language), "HISTORICAL",
             recommended=True, action="meta"),
        _opt("Reissued tender" if not language.startswith("ar") else "مناقصة مُعاد إصدارها",
             "REISSUED", action="meta"),
        _opt("Live bid — dates need confirmation" if not language.startswith("ar")
             else "عطاء حالي — التواريخ تحتاج تأكيد", "LIVE", action="meta"),
    ]
    return {
        "decision_id": "meta_expired_dates",
        "requirement_id": "expired_dates",
        "kind": "META",
        "header": "TOR dates",
        "question": q,
        "tor_context": "",
        "options": opts,
        "supports_custom": False,
        "recommended_value": "HISTORICAL",
        "constraint": {"type": "ENUM", "minimum": None, "maximum": None},
        "fallback_numbered": _fallback(q, opts, language),
    }
