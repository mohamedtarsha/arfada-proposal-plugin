"""Previous-work annex validation (v0.6.4, production hardening §6).

When a TOR requests "an example of previous work", the file attached/selected must
be verified BEFORE it is registered as the annex. It must be an actual deliverable
(evaluation / endline / final-evaluation / assessment report), produced by/for
ARFADA, and NOT a proposal, TOR, policy, or branding/manual document.

Classification is deterministic (filename + text cues). ARFADA authorship and
sharing clearance that cannot be established FROM the file require explicit user
confirmation — never assumed. Nothing is claimed "annexed" until the file exists
in the run package (see engine/tor/package.py).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

# Document kinds
DELIVERABLE = "EVALUATION_DELIVERABLE"
PROPOSAL = "PROPOSAL"
TOR = "TOR"
POLICY = "POLICY"
BRANDING = "BRANDING_OR_MANUAL"
UNKNOWN = "UNKNOWN"

_PROPOSAL_RE = re.compile(
    r"\b(technical proposal|financial proposal|we (?:are )?(?:pleased to )?(?:propose|submit)|"
    r"our proposed (?:approach|methodology)|this proposal|bid submission|"
    r"expression of interest|in response to (?:the )?(?:rfp|rfq|tender))\b", re.I)
_TOR_RE = re.compile(
    r"\b(terms of reference|\bt\.?o\.?r\.?\b|scope of work|the consultant shall|"
    r"deadline for submission|request for (?:proposal|quotation)|"
    r"background and rationale|the (?:assignment|consultancy) (?:is|will|aims))\b", re.I)
_POLICY_RE = re.compile(
    r"\b(policy|guideline|standard operating procedure|\bsop\b|code of conduct|"
    r"terms and conditions|framework agreement)\b", re.I)
_BRANDING_RE = re.compile(
    r"\b(brand(?:ing)? guidelines?|visual identity|style guide|logo usage|"
    r"user manual|user guide|installation guide|template pack)\b", re.I)
_DELIVERABLE_RE = re.compile(
    r"\b(final (?:evaluation|report)|endline (?:report|evaluation|survey)|"
    r"baseline (?:report|survey)|midline|evaluation report|evaluation findings|"
    r"assessment report|research report|study report|executive summary)\b", re.I)
# Structural markers common to real evaluation deliverables.
_DELIVERABLE_STRUCT = [
    r"\bexecutive summary\b", r"\bkey findings\b", r"\bfindings\b",
    r"\brecommendations\b", r"\bmethodology\b", r"\bconclusions?\b",
    r"\blimitations\b", r"\bannex(?:es)?\b",
]


def _score_struct(text: str) -> int:
    low = text or ""
    return sum(1 for pat in _DELIVERABLE_STRUCT if re.search(pat, low, re.I))


def classify_document(*, text: str, file_name: str = "") -> dict:
    """Classify a candidate previous-work file by filename + content cues."""
    name = file_name or ""
    corpus = f"{name}\n{text or ''}"
    reasons: list[str] = []

    is_proposal = bool(_PROPOSAL_RE.search(corpus)) or bool(
        re.search(r"\bproposal\b", name, re.I))
    is_tor = bool(_TOR_RE.search(corpus)) or bool(
        re.search(r"\b(tor|tors|terms[_\- ]of[_\- ]reference)\b", name, re.I))
    is_policy = bool(_POLICY_RE.search(corpus))
    is_branding = bool(_BRANDING_RE.search(corpus))
    deliverable_hits = bool(_DELIVERABLE_RE.search(corpus))
    struct = _score_struct(text or "")

    # Decide kind by priority: disqualifiers first, then deliverable evidence.
    if is_proposal:
        kind = PROPOSAL
        reasons.append("Looks like a PROPOSAL (proposal language detected).")
    elif is_tor:
        kind = TOR
        reasons.append("Looks like a TOR / scope-of-work document.")
    elif is_branding:
        kind = BRANDING
        reasons.append("Looks like a branding/manual/template document.")
    elif is_policy and not deliverable_hits and struct < 3:
        kind = POLICY
        reasons.append("Looks like a policy / guideline document.")
    elif deliverable_hits or struct >= 3:
        kind = DELIVERABLE
        reasons.append("Matches an evaluation/assessment deliverable "
                       f"(title cue={deliverable_hits}, structure sections={struct}).")
    else:
        kind = UNKNOWN
        reasons.append("Could not confirm this is an evaluation deliverable.")

    acceptable = kind == DELIVERABLE
    return {
        "kind": kind,
        "acceptable": acceptable,
        "deliverable_structure_sections": struct,
        "reasons": reasons,
    }


def _arfada_authorship(text: str, file_name: str, arfada_names: list) -> bool:
    hay = f"{file_name}\n{text or ''}".lower()
    names = [n.lower() for n in (arfada_names or ["arfada"]) if n]
    return any(n in hay for n in names)


def validate_previous_work(
    path: str | Path, *, arfada_names: Optional[list] = None, text: Optional[str] = None,
) -> dict:
    """Full previous-work annex verdict for a file.

    Returns: ok (safe to register), kind, acceptable, by_arfada,
    needs_clearance_confirmation, reasons, file_exists.
    """
    p = Path(path)
    file_exists = p.exists() and p.is_file()
    content = text
    if content is None and file_exists:
        try:
            from .lknowledge.scan import _extract_text
            content = _extract_text(p)
        except Exception:
            content = ""
    content = content or ""

    cls = classify_document(text=content, file_name=p.name)
    by_arfada = _arfada_authorship(content, p.name, arfada_names or ["ARFADA"])
    reasons = list(cls["reasons"])
    if not file_exists:
        reasons.append("File does not exist on disk — cannot annex a non-existent file.")

    needs_clearance = not by_arfada
    if not by_arfada:
        reasons.append("ARFADA authorship not evident in the file — user must confirm "
                       "ARFADA produced it and is cleared to share it.")

    ok = bool(file_exists and cls["acceptable"])
    return {
        "ok": ok,
        "file": str(p),
        "file_exists": file_exists,
        "kind": cls["kind"],
        "acceptable": cls["acceptable"],
        "by_arfada": by_arfada,
        "needs_clearance_confirmation": needs_clearance,
        "deliverable_structure_sections": cls["deliverable_structure_sections"],
        "reasons": reasons,
    }
