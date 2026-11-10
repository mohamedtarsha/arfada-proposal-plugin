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


def infer_assignment_type(metadata: dict, requirements: list[dict]) -> AssignmentTypeResult:
    """Deterministically infer the assignment type with confidence + evidence."""
    text = _gather_text(metadata, requirements)
    scores: dict[str, int] = {}
    evidence_by_type: dict[str, list[str]] = {}

    # Presence-weighted scoring with a CAPPED frequency bonus, so a repeated
    # generic word ("assessment") cannot swamp a specific high-weight signal
    # ("needs assessment", "third-party monitoring"). Each signal contributes
    # its full weight on first match + at most +3 for additional occurrences.
    for atype, pattern, weight in _SIGNALS:
        matches = list(re.finditer(pattern, text, re.I))
        if not matches:
            continue
        freq_bonus = min(len(matches) - 1, 3)
        scores[atype] = scores.get(atype, 0) + weight + freq_bonus
        evidence_by_type.setdefault(atype, [])
        for m in matches:
            snippet = m.group(0)
            if snippet not in evidence_by_type[atype]:
                evidence_by_type[atype].append(snippet)

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

    return AssignmentTypeResult(
        assignment_type=top_type,
        label=TYPE_LABEL.get(top_type, top_type),
        confidence=confidence,
        evidence=evidence,
        scores=dict(ranked),
        needs_decision=(confidence == "LOW"),
    )
