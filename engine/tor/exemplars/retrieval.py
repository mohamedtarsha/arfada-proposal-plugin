"""Section-aware exemplar retrieval + corpus DNA access (v0.6.1 / v0.6.6).

Returns only the top-N relevant historical section exemplars for a given section
(STYLE guidance, never facts). Ranked by assignment type, country, region, sector,
donor/client, evaluation type, humanitarian/development context, and section type —
with the extra dimensions matched as tokens against the exemplar's project folder so
no re-indexing of the (confidential, local) corpus is needed. Excerpts are bounded;
the full corpus is never returned.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .scan import exemplar_cache_dir, _load_index, _load_sections

_DEFAULT_TOP = 3
_EXCERPT_CHARS = 600

_CONTEXT_TERMS = {
    "humanitarian": ["humanitarian", "emergency", "idp", "refugee", "conflict", "crisis",
                     "displacement", "wash", "shelter", "protection", "nexus"],
    "development": ["development", "resilience", "livelihood", "governance", "capacity",
                    "systems", "sustainable", "education", "institutional"],
}


def _tok(text: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]{3,}", (text or "").lower())}


def _context_of(text: str) -> str:
    low = (text or "").lower()
    h = sum(1 for w in _CONTEXT_TERMS["humanitarian"] if w in low)
    d = sum(1 for w in _CONTEXT_TERMS["development"] if w in low)
    if h == d:
        return ""
    return "humanitarian" if h > d else "development"


def _index(cache_dir: Optional[Path] = None) -> dict:
    return _load_index(cache_dir or exemplar_cache_dir())


def is_configured(cache_dir: Optional[Path] = None) -> bool:
    return bool(_index(cache_dir).get("exemplars"))


def writing_dna(cache_dir: Optional[Path] = None) -> dict:
    return _index(cache_dir).get("writing_dna", {})


def formatting_dna(cache_dir: Optional[Path] = None) -> dict:
    return _index(cache_dir).get("formatting_dna", {})


def response_patterns(cache_dir: Optional[Path] = None) -> dict:
    return _index(cache_dir).get("response_patterns", {})


def _score_exemplar(e: dict, *, assignment_type="", country="", region="MENA",
                    sector="", donor="", evaluation_type="", context="",
                    thematic="") -> tuple[int, dict]:
    """Deterministic relevance score for one historical proposal (whole doc)."""
    score, why = 0, {}
    folder_tok = _tok(e.get("project_folder", ""))
    if assignment_type and e.get("assignment_type") == assignment_type:
        score += 4; why["assignment_type"] = 4
    if evaluation_type and evaluation_type.lower() in (e.get("assignment_type") or "").lower():
        score += 1; why["evaluation_type"] = 1
    if country and (e.get("country") or "").lower() == country.lower():
        score += 3; why["country"] = 3
    if region and (e.get("region") or "").lower() == region.lower():
        score += 1; why["region"] = 1
    # sector / donor / thematic matched as tokens against the project-folder name
    for key, val in (("sector", sector), ("donor", donor), ("thematic", thematic)):
        hits = _tok(val) & folder_tok
        if hits:
            score += min(len(hits), 2); why[key] = min(len(hits), 2)
    if context and context == _context_of(e.get("project_folder", "")):
        score += 1; why["context"] = 1
    return score, why


def retrieve_for_section(
    section_id: str, *, assignment_type: str = "", country: str = "",
    region: str = "MENA", sector: str = "", donor: str = "", evaluation_type: str = "",
    context: str = "", thematic: str = "", top: int = _DEFAULT_TOP,
    cache_dir: Optional[Path] = None,
) -> list[dict]:
    """Top-N historical section exemplars for this section (bounded excerpts, style only)."""
    cache_dir = cache_dir or exemplar_cache_dir()
    idx = _index(cache_dir)
    scored: list[tuple[int, dict, dict, dict]] = []
    # normalize framework section ids so a type-specific framework matches historical ones
    want_types = {section_id}
    if section_id.endswith("FRAMEWORK"):
        want_types |= {"EVALUATION_FRAMEWORK", "ASSESSMENT_FRAMEWORK",
                       "MONITORING_FRAMEWORK", "RESEARCH_FRAMEWORK"}

    for e in idx.get("exemplars", []):
        sections = _load_sections(cache_dir, e["exemplar_id"])
        doc_score, why = _score_exemplar(
            e, assignment_type=assignment_type, country=country, region=region,
            sector=sector, donor=donor, evaluation_type=evaluation_type,
            context=context, thematic=thematic)
        for s in sections:
            if s["type"] not in want_types:
                continue
            scored.append((doc_score + 3, e, s, why))  # +3 section-type baseline

    scored.sort(key=lambda x: -x[0])
    out = []
    for score, e, s, why in scored[:top]:
        out.append({
            "exemplar_id": e["exemplar_id"],
            "country": e.get("country", ""),
            "assignment_type": e.get("assignment_type", ""),
            "project_label": e.get("project_folder", ""),
            "section_type": s["type"],
            "relevance_score": score,
            "scored_on": why,
            "relevance_reason": _reason(e, assignment_type, country, why),
            # bounded excerpt — STYLE reference only, must NOT be copied verbatim
            "style_excerpt": s["text"][:_EXCERPT_CHARS],
        })
    return out


def relevant_proposals(
    *, assignment_type: str = "", country: str = "", region: str = "MENA",
    sector: str = "", donor: str = "", evaluation_type: str = "", context: str = "",
    thematic: str = "", top: int = 4, cache_dir: Optional[Path] = None,
) -> list[dict]:
    """Rank whole historical proposals; return the closest 2–4 as writing references."""
    cache_dir = cache_dir or exemplar_cache_dir()
    idx = _index(cache_dir)
    scored = []
    for e in idx.get("exemplars", []):
        score, why = _score_exemplar(
            e, assignment_type=assignment_type, country=country, region=region,
            sector=sector, donor=donor, evaluation_type=evaluation_type,
            context=context, thematic=thematic)
        scored.append((score, e, why))
    scored.sort(key=lambda x: -x[0])
    out = []
    for score, e, why in scored[:max(2, min(top, 4))]:
        out.append({
            "exemplar_id": e["exemplar_id"],
            "project_label": e.get("project_folder", ""),
            "assignment_type": e.get("assignment_type", ""),
            "country": e.get("country", ""),
            "relevance_score": score,
            "scored_on": why,
            "has_tor_pair": bool(e.get("tor_file")),
        })
    return out


def retrieval_summary(*, assignment_type="", country="", region="MENA", sector="",
                      donor="", evaluation_type="", context="", thematic="",
                      cache_dir: Optional[Path] = None) -> dict:
    """Init-line summary: DNA active, historical pairs, relevant proposals retrieved."""
    cache_dir = cache_dir or exemplar_cache_dir()
    idx = _index(cache_dir)
    exemplars = idx.get("exemplars", [])
    pairs = sum(1 for e in exemplars if e.get("tor_file"))
    rel = relevant_proposals(assignment_type=assignment_type, country=country,
                             region=region, sector=sector, donor=donor,
                             evaluation_type=evaluation_type, context=context,
                             thematic=thematic, cache_dir=cache_dir)
    return {
        "writing_dna_active": bool(exemplars),
        "historical_pairs": pairs,
        "relevant_proposals_retrieved": len(rel),
        "relevant_proposals": rel,
    }


def _reason(e, atype, country, why=None) -> str:
    bits = ["same section type"]
    if atype and e.get("assignment_type") == atype:
        bits.append(f"same assignment type ({atype})")
    if country and (e.get("country") or "").lower() == country.lower():
        bits.append(f"same country ({country})")
    for k in ("sector", "donor", "thematic", "context"):
        if why and why.get(k):
            bits.append(f"{k} match")
    return ", ".join(bits)
