"""Deterministic assignment-type inference (Phase 4).

Infers the assignment type from TOR CONTENT (title, objectives, scope, methodology,
deliverables, requirement categories) — not folder/filename. Produces a type,
a confidence (HIGH/MEDIUM/LOW), and the evidence that drove the decision.

No fixed "evaluation" default: when evidence is weak the type is UNRESOLVED and a
genuine Human Decision is surfaced for the user to classify it.

Canonical taxonomy (extends the validated PE2 TYPE_TOKENS lineage).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# Canonical types (spec §1). OTHER is a real bucket, not a dumping ground.
ASSIGNMENT_TYPES = [
    "EVALUATION", "BASELINE", "MIDLINE", "ENDLINE", "NEEDS_ASSESSMENT",
    "TPM", "MONITORING", "RESEARCH_STUDY", "SURVEY", "ASSESSMENT",
    "CAPACITY_ASSESSMENT", "MARKET_ASSESSMENT", "OTHER",
]

TYPE_LABEL = {
    "EVALUATION": "Evaluation",
    "BASELINE": "Baseline Study",
    "MIDLINE": "Midline Study",
    "ENDLINE": "Endline / Impact Evaluation",
    "NEEDS_ASSESSMENT": "Needs Assessment",
    "TPM": "Third-Party Monitoring",
    "MONITORING": "Monitoring",
    "RESEARCH_STUDY": "Research Study",
    "SURVEY": "Survey",
    "ASSESSMENT": "Assessment",
    "CAPACITY_ASSESSMENT": "Capacity Assessment",
    "MARKET_ASSESSMENT": "Market Assessment",
    "OTHER": "Assignment",
    "UNRESOLVED": "Unclassified Assignment",
}

# Weighted keyword signals. Order matters only for evidence display; scoring is additive.
# More-specific types carry stronger weights so "midline evaluation" → MIDLINE not EVALUATION.
_SIGNALS: list[tuple[str, str, int]] = [
    # (type, regex, weight)
    ("MIDLINE", r"\bmid-?line\b|\bmid-?term\s+(?:review|evaluation)\b|\bmtr\b", 6),
    ("ENDLINE", r"\bend-?line\b|\bimpact\s+evaluation\b|\bfinal\s+impact\b", 6),
    ("BASELINE", r"\bbase-?line\b", 6),
    ("TPM", r"\bthird[- ]party\s+monitoring\b|\btpm\b|\bverification\s+monitoring\b", 7),
    ("MONITORING", r"\bmonitoring\s+(?:framework|system|plan|visits?)\b|\bremote\s+monitoring\b", 4),
    ("NEEDS_ASSESSMENT", r"\bneeds?\s+assessment\b|\bmulti-?sector(?:al)?\s+needs\b|\bmsna\b|"
                         r"\bhumanitarian\s+needs\b", 7),
    ("CAPACITY_ASSESSMENT", r"\bcapacity\s+assessment\b|\binstitutional\s+assessment\b|"
                            r"\borgani[sz]ational\s+capacity\b", 7),
    ("MARKET_ASSESSMENT", r"\bmarket\s+(?:assessment|analysis|needs\s+assessment)\b|"
                          r"\bmarket\s+systems?\b|\beconomy-based\s+market\b", 7),
    ("SURVEY", r"\bhousehold\s+survey\b|\bpopulation\s+survey\b|\bkap\s+survey\b|"
               r"\bperception\s+survey\b", 4),
    ("RESEARCH_STUDY", r"\bresearch\s+(?:study|questions?|design)\b|\bqualitative\s+study\b|"
                       r"\btracer\s+study\b|\bformative\s+research\b|\bstudy\s+on\b", 5),
    ("ASSESSMENT", r"\bassessment\b|\bvulnerability\s+assessment\b|\bcvca\b|"
                   r"\brapid\s+assessment\b", 3),
    ("EVALUATION", r"\bevaluation\b|\bexternal\s+evaluation\b|\bfinal\s+evaluation\b|"
                   r"\boecd[- ]dac\b|\bevaluation\s+questions?\b|\bevaluability\b", 4),
]

# TOR-analysis signals (context_aware=True): "end line" written as two words and
# "end-of-project evaluation" also count as ENDLINE. The legacy table above is kept
# unchanged for the Writing DNA exemplar scan.
_SIGNALS_TOR: list[tuple[str, str, int]] = [
    ("ENDLINE", r"\bend[- ]?line\b|\bimpact\s+evaluation\b|\bfinal\s+impact\b|"
                r"\bend[- ]of[- ]project\s+evaluation\b", 6)
    if atype == "ENDLINE" else (atype, pattern, weight)
    for atype, pattern, weight in _SIGNALS
]

# "baseline" used as the comparison/reference dataset — not the requested work.
_BASELINE_REFERENCE = re.compile(
    r"(?:against|compared\s+(?:to|with)|relative\s+to|from|since|at|versus|vs\.?|"
    r"existing|previous|available|completed|conducted|established|in|on\s+the)\s+"
    r"(?:(?:the|a|its|this)\s+)?"
    r"(?:[\w-]+\s+){0,3}?base-?line\b"
    r"|\bbase-?line\s+(?:values?|data(?:set)?|figures?|findings|results|reports?|levels?|"
    r"measurements?|samples?|tools?|instruments?|questionnaires?|indicators?|targets?|"
    r"information|benchmarks?|"
    r"(?:survey|study|assessment)\s+(?:was|were|has|had|conducted|carried\s+out|completed|"
    r"undertaken|methods?|tools?|process)|was|were|showed|shows|found|"
    r"indicated|reported|established|conducted|and\s+end[- ]?line|vs\.?|–|-)"
    # bidder qualifications / past experience ("experience in conducting baseline surveys")
    r"|\bexperience\s+(?:in\s+|of\s+)?(?:[\w-]+\s+){0,2}?base-?line\b",
    re.I)
# a short "field: value" pair ("Indicator: Baseline") is a table cell, not a title
_FIELD_PAIR_TITLE = re.compile(r"^\s*[^:]{1,40}:\s*\S")
# explicit labels for the requested assignment ("conduct a final evaluation")
_EXPLICIT_LABEL = re.compile(
    r"(?:conduct|undertake|carry\s+out|commission|perform|lead)\s+(?:an?\s+|the\s+)?"
    r"(?:external\s+|independent\s+)?((?:[\w-]+\s+){0,2}?"
    r"(?:evaluation|assessment|study|survey|review|monitoring))"
    r"|(?:this|the)\s+((?:final|end[- ]?line|mid-?line|mid-?term|baseline)\s+"
    r"(?:evaluation|study|survey|assessment))", re.I)
_TITLE_BONUS = 8          # a type named in the document title
_LABEL_BONUS = 4          # a type named as the requested work (once per type)
_FINAL_EVAL = re.compile(r"\bfinal\s+evaluation\b|\bend[- ]of[- ]project\s+evaluation\b", re.I)

# Requirement-category reinforcement (small nudges; never decisive alone).
_CATEGORY_NUDGE = {
    "evaluation_questions": ("EVALUATION", 2),
    "sampling": ("SURVEY", 1),
}

# Strongest-vs-runnerup ratio thresholds for confidence.
_HIGH_MARGIN = 4
_MEDIUM_MARGIN = 2
_MIN_HIGH_SCORE = 6


@dataclass
class AssignmentTypeResult:
    assignment_type: str          # a canonical type or "UNRESOLVED"
    label: str
    confidence: str               # HIGH | MEDIUM | LOW
    evidence: list[str] = field(default_factory=list)
    scores: dict = field(default_factory=dict)
    needs_decision: bool = False


def _gather_text(metadata: dict, requirements: list[dict]) -> str:
    parts: list[str] = []
    for key in ("assignment", "objectives", "scope", "background",
                "required_methodology", "deliverables", "evaluation_questions"):
        entry = metadata.get(key)
        if isinstance(entry, dict):
            v = entry.get("value", "")
            if v:
                parts.append(v)
    # include requirement text (bounded) — helps thin-metadata PDFs
    for r in requirements[:120]:
        t = r.get("text", "")
        if t:
            parts.append(t)
    return "\n".join(parts).lower()


def _suspicious_title(value: str, confidence: str = "") -> bool:
    """A title candidate too weak to steer the classification (e.g. "Indicator: Baseline")."""
    v = (value or "").strip()
    if str(confidence or "").upper() == "LOW":
        return True
    return bool(_FIELD_PAIR_TITLE.match(v)) and len(v.split()) <= 8


def _title_text(metadata: dict) -> str:
    parts = []
    for key in ("assignment", "title"):
        entry = metadata.get(key)
        if isinstance(entry, dict) and entry.get("value"):
            if _suspicious_title(entry["value"], entry.get("confidence", "")):
                continue
            parts.append(entry["value"])
    return " ".join(parts).lower()


def _types_in(text: str) -> set:
    return {atype for atype, pattern, _w in _SIGNALS_TOR if re.search(pattern, text, re.I)}


def infer_assignment_type(metadata: dict, requirements: list[dict], *,
                          context_aware: bool = False) -> AssignmentTypeResult:
    """Deterministically infer the assignment type with confidence + evidence.

    ``context_aware=True`` (TOR analysis) applies the title / explicit-label /
    baseline-reference rules below. The default keeps the legacy scoring, which the
    Writing DNA exemplar scan relies on, unchanged.

    With context_aware, the document title and explicit assignment labels weigh most. "baseline"
    used as the comparison dataset (against the baseline, baseline values, the
    baseline was conducted) does not count towards BASELINE; it signals an
    end-of-project measurement instead, so a "Final Evaluation" measured against
    an existing baseline is classified ENDLINE.
    """
    text = _gather_text(metadata, requirements)
    title = _title_text(metadata)
    scores: dict[str, int] = {}
    evidence_by_type: dict[str, list[str]] = {}

    signals = _SIGNALS_TOR if context_aware else _SIGNALS
    # "baseline" mentions that only reference the comparison dataset
    baseline_refs = len(_BASELINE_REFERENCE.findall(text)) if context_aware else 0
    baseline_total = len(re.findall(r"\bbase-?line\b", text, re.I))
    baseline_is_reference = baseline_refs > 0 and baseline_refs * 2 >= baseline_total
    final_eval = False

    # Presence-weighted scoring with a CAPPED frequency bonus, so a repeated
    # generic word ("assessment") cannot swamp a specific high-weight signal
    # ("needs assessment", "third-party monitoring"). Each signal contributes
    # its full weight on first match + at most +3 for additional occurrences.
    for atype, pattern, weight in signals:
        matches = list(re.finditer(pattern, text, re.I))
        if context_aware and atype == "BASELINE" and matches:
            # only baseline mentions that are NOT the reference dataset count
            requested = max(len(matches) - baseline_refs, 0)
            if baseline_is_reference or requested == 0:
                matches = []
            else:
                matches = matches[:requested]
        if not matches:
            continue
        freq_bonus = min(len(matches) - 1, 3)
        scores[atype] = scores.get(atype, 0) + weight + freq_bonus
        evidence_by_type.setdefault(atype, [])
        for m in matches:
            snippet = m.group(0)
            if snippet not in evidence_by_type[atype]:
                evidence_by_type[atype].append(snippet)

    if context_aware:
        # an end-of-project evaluation measured against an existing baseline is ENDLINE
        final_eval = bool(_FINAL_EVAL.search(text) or _FINAL_EVAL.search(title))
        if baseline_refs and final_eval:
            scores["ENDLINE"] = scores.get("ENDLINE", 0) + min(baseline_refs, 3)
            evidence_by_type.setdefault("ENDLINE", []).append("final evaluation against baseline")

        # document title: strongest signal (a final evaluation title counts as ENDLINE
        # when the TOR measures change against a baseline)
        title_types = _types_in(title) if title else set()
        if _FINAL_EVAL.search(title) and baseline_refs:
            title_types.add("ENDLINE")
            title_types.discard("EVALUATION")
        if baseline_is_reference:
            title_types.discard("BASELINE")
        for atype in title_types:
            scores[atype] = scores.get(atype, 0) + _TITLE_BONUS
            evidence_by_type.setdefault(atype, []).insert(0, f"title: {title[:80]}")

        # explicit assignment labels ("conduct a final evaluation", "this endline study")
        labelled = set()
        for m in _EXPLICIT_LABEL.finditer(text):
            phrase = (m.group(1) or m.group(2) or "").lower()
            types = _types_in(phrase)
            if _FINAL_EVAL.search(phrase) and baseline_refs:
                types = (types - {"EVALUATION"}) | {"ENDLINE"}
            if baseline_is_reference:
                types.discard("BASELINE")
            labelled |= types
        for atype in labelled:
            scores[atype] = scores.get(atype, 0) + _LABEL_BONUS

        # specific beats generic: "end line evaluation" also matched EVALUATION
        if scores.get("ENDLINE") and scores.get("EVALUATION"):
            overlap = len(re.findall(r"\bend[- ]?line\s+evaluations?\b", text, re.I))
            scores["EVALUATION"] = max(scores["EVALUATION"] - min(overlap, 3), 0)

    # category nudges
    cats = {r.get("category") for r in requirements}
    for cat, (atype, w) in _CATEGORY_NUDGE.items():
        if cat in cats:
            scores[atype] = scores.get(atype, 0) + w

    if not scores:
        return AssignmentTypeResult(
            assignment_type="UNRESOLVED", label=TYPE_LABEL["UNRESOLVED"],
            confidence="LOW", evidence=["No assignment-type signals found in the TOR."],
            scores={}, needs_decision=True,
        )

    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    top_type, top_score = ranked[0]
    runner_score = ranked[1][1] if len(ranked) > 1 else 0
    margin = top_score - runner_score

    if top_score >= _MIN_HIGH_SCORE and margin >= _HIGH_MARGIN:
        confidence = "HIGH"
    elif margin >= _MEDIUM_MARGIN:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    evidence = [f"'{s}'" for s in evidence_by_type.get(top_type, [])][:6]
    if len(ranked) > 1 and confidence != "HIGH":
        evidence.append(f"(competing: {TYPE_LABEL.get(ranked[1][0], ranked[1][0])} "
                        f"score {runner_score} vs {top_score})")

    label = TYPE_LABEL.get(top_type, top_type)
    if top_type == "ENDLINE" and final_eval:
        label = "Final (Endline) Evaluation"
    return AssignmentTypeResult(
        assignment_type=top_type,
        label=label,
        confidence=confidence,
        evidence=evidence,
        scores=dict(ranked),
        needs_decision=(confidence == "LOW"),
    )
