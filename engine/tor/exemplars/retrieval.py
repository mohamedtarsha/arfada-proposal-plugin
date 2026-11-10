"""Section-aware exemplar retrieval + corpus DNA access (v0.6.1).

Returns only the top-N relevant historical section exemplars for a given section
(STYLE guidance, never facts). Ranked by assignment type, country, region, sector,
methods, and section type. Excerpts are bounded; full corpus is never returned.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .scan import exemplar_cache_dir, _load_index, _load_sections

_DEFAULT_TOP = 3
_EXCERPT_CHARS = 600


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


def retrieve_for_section(
    section_id: str, *, assignment_type: str = "", country: str = "",
    region: str = "MENA", top: int = _DEFAULT_TOP, cache_dir: Optional[Path] = None,
) -> list[dict]:
    """Top-N historical section exemplars for this section (bounded excerpts, style only)."""
    cache_dir = cache_dir or exemplar_cache_dir()
    idx = _index(cache_dir)
    scored: list[tuple[int, dict, dict]] = []
    # normalize framework section ids so a type-specific framework matches historical ones
    want_types = {section_id}
    if section_id.endswith("FRAMEWORK"):
        want_types |= {"EVALUATION_FRAMEWORK", "ASSESSMENT_FRAMEWORK",
                       "MONITORING_FRAMEWORK", "RESEARCH_FRAMEWORK"}

    for e in idx.get("exemplars", []):
        sections = _load_sections(cache_dir, e["exemplar_id"])
        for s in sections:
            if s["type"] not in want_types:
                continue
            score = 3  # section-type match baseline
            if assignment_type and e.get("assignment_type") == assignment_type:
                score += 4
            if country and (e.get("country") or "").lower() == country.lower():
                score += 3
            if region and (e.get("region") or "").lower() == region.lower():
                score += 1
            scored.append((score, e, s))

    scored.sort(key=lambda x: -x[0])
    out = []
    for score, e, s in scored[:top]:
        out.append({
            "exemplar_id": e["exemplar_id"],
            "country": e.get("country", ""),
            "assignment_type": e.get("assignment_type", ""),
            "project_label": e.get("project_folder", ""),
            "section_type": s["type"],
            "relevance_score": score,
            "relevance_reason": _reason(e, assignment_type, country),
            # bounded excerpt — STYLE reference only, must NOT be copied verbatim
            "style_excerpt": s["text"][:_EXCERPT_CHARS],
        })
    return out


def _reason(e, atype, country) -> str:
    bits = ["same section type"]
    if atype and e.get("assignment_type") == atype:
        bits.append(f"same assignment type ({atype})")
    if country and (e.get("country") or "").lower() == country.lower():
        bits.append(f"same country ({country})")
    return ", ".join(bits)
