"""Writing DNA style QA (v0.6.6) — make new proposals read like ARFADA wrote them.

Deterministic checks run AFTER Draft v1 to keep the prose in ARFADA's established
voice and away from generic AI proposal language. It reports wording issues and
targeted rewrite suggestions ONLY — it never changes facts, approved/provisional
decisions, methodology numbers, or budget values.

Checks:
  * generic AI filler — excessive/repeated stock words & phrases (not a hard ban),
  * unnatural uniformity — paragraphs all the same length, repeated sentence openers,
  * excessive headings / bullet lists vs prose,
  * divergence from ARFADA historical style (paragraph length, prose/bullet balance),
  * suspicious copying from historical proposals (long verbatim phrase reuse).

Severity is WARNING or IMPROVEMENT only — style QA never blocks the FINAL submission
on wording, and it never touches the facts engine.
"""
from __future__ import annotations

import re
import statistics
from pathlib import Path
from typing import Optional

from .exemplars.anticopy import similarity_report, long_shared_phrases

WARNING = "WARNING"
IMPROVEMENT = "IMPROVEMENT"

# Generic proposal filler (spec §5). NOT a mechanical ban — only excessive/repeated
# or clustered usage is flagged.
_GENERIC_WORDS = ["robust", "comprehensive", "holistic", "rigorous", "seamless",
                  "tailored", "cutting-edge", "state-of-the-art", "world-class",
                  "synergy", "leverage", "best-in-class"]
_GENERIC_PHRASES = ["this approach ensures", "this will ensure",
                    "our methodology will ensure", "it is important to note",
                    "in today's world", "plays a crucial role", "plays a vital role",
                    "a wide range of", "it should be noted that"]
# per-1000-words density above which generic-word usage reads as templated
_WORD_DENSITY_PER_1000 = 6.0
_PHRASE_REPEAT_LIMIT = 2   # a stock phrase appearing > this many times is flagged


def _finding(category, message, *, severity=IMPROVEMENT, section_id="",
             suggestion="", evidence=""):
    return {"check": "STYLE_DNA", "category": category, "severity": severity,
            "section_id": section_id, "message": message,
            "suggestion": suggestion, "evidence": evidence}


def _blocks_text(candidate: dict) -> str:
    parts = []
    for b in candidate.get("blocks", []):
        t = b.get("type")
        if t == "paragraph":
            parts.append(b.get("text", ""))
        elif t in ("bullet_list", "numbered_list"):
            parts.extend(str(x) for x in b.get("items", []))
    return "\n".join(parts)


def _paragraphs(candidate: dict) -> list[str]:
    return [b.get("text", "") for b in candidate.get("blocks", [])
            if b.get("type") == "paragraph" and b.get("text", "").strip()]


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]


# ---------------------------------------------------------------------------
# individual checks
# ---------------------------------------------------------------------------

def filler_findings(text: str, *, section_id="") -> list[dict]:
    out = []
    low = (text or "").lower()
    words = max(1, len(re.findall(r"[a-z']+", low)))
    word_hits = {w: len(re.findall(rf"\b{re.escape(w)}\b", low)) for w in _GENERIC_WORDS}
    total_word_hits = sum(word_hits.values())
    density = total_word_hits * 1000.0 / words
    if density > _WORD_DENSITY_PER_1000:
        top = sorted((w for w, c in word_hits.items() if c),
                     key=lambda w: -word_hits[w])[:5]
        out.append(_finding(
            "generic_filler",
            f"Generic buzzword density is high ({density:.1f} per 1000 words): "
            f"{', '.join(top)}", severity=WARNING, section_id=section_id,
            suggestion="Replace buzzwords with specific, operational detail from this TOR."))
    for ph in _GENERIC_PHRASES:
        c = low.count(ph)
        if c > _PHRASE_REPEAT_LIMIT:
            out.append(_finding(
                "stock_phrase", f"Stock phrase '{ph}' used {c} times",
                severity=IMPROVEMENT, section_id=section_id,
                suggestion=f"Vary or remove '{ph}'; say concretely what will happen."))
    return out


def uniformity_findings(candidate: dict, *, section_id="") -> list[dict]:
    out = []
    paras = _paragraphs(candidate)
    lens = [len(p.split()) for p in paras]
    if len(lens) >= 4:
        mean = statistics.mean(lens)
        stdev = statistics.pstdev(lens)
        cov = (stdev / mean) if mean else 0
        if cov < 0.15:
            out.append(_finding(
                "uniform_paragraphs",
                f"Paragraphs are unnaturally uniform (~{mean:.0f} words each, "
                f"variation {cov:.0%})", severity=WARNING, section_id=section_id,
                suggestion="Vary paragraph length — mix short and longer paragraphs."))
    # repeated sentence openers
    openers = {}
    for p in paras:
        for s in _sentences(p):
            w = s.split()
            if w:
                key = w[0].lower()
                openers[key] = openers.get(key, 0) + 1
    for opener, c in openers.items():
        if c >= 3 and opener not in ("the", "a", "an"):
            out.append(_finding(
                "repetitive_openers",
                f"{c} sentences open with '{opener}…'", severity=IMPROVEMENT,
                section_id=section_id, suggestion="Vary sentence openings."))
            break
    # excessive bullets vs prose
    n_para = sum(1 for b in candidate.get("blocks", []) if b.get("type") == "paragraph")
    n_bullet_items = sum(len(b.get("items", [])) for b in candidate.get("blocks", [])
                         if b.get("type") in ("bullet_list", "numbered_list"))
    if n_bullet_items >= 8 and n_bullet_items > 3 * max(1, n_para):
        out.append(_finding(
            "excessive_bullets",
            f"Section is bullet-heavy ({n_bullet_items} list items vs {n_para} paragraphs)",
            severity=IMPROVEMENT, section_id=section_id,
            suggestion="Convert some lists into ARFADA's explanatory prose."))
    return out


def divergence_findings(candidate: dict, writing_dna: dict, *, section_id="") -> list[dict]:
    out = []
    if not writing_dna:
        return out
    dna_med = writing_dna.get("paragraph_word_median")
    paras = _paragraphs(candidate)
    lens = [len(p.split()) for p in paras]
    if dna_med and lens:
        med = statistics.median(lens)
        if dna_med >= 10 and (med > 2.2 * dna_med or med < 0.45 * dna_med):
            out.append(_finding(
                "style_divergence",
                f"Paragraph length (~{med:.0f} words) diverges from ARFADA's historical "
                f"style (~{dna_med:.0f})", severity=WARNING, section_id=section_id,
                suggestion=f"Aim for paragraphs near {dna_med:.0f} words, as in ARFADA's "
                           "past winning proposals."))
    return out


def copy_findings(text: str, exemplar_excerpts: list, *, section_id="") -> list[dict]:
    out = []
    if not exemplar_excerpts:
        return out
    sim = similarity_report(text, exemplar_excerpts)
    if sim["flagged"]:
        phrases = long_shared_phrases(text, exemplar_excerpts)
        out.append(_finding(
            "suspicious_copy",
            f"Possible copying from a historical proposal ({sim['detail']})",
            severity=WARNING, section_id=section_id,
            suggestion="Rewrite in ARFADA's voice; keep the style, not the wording.",
            evidence="; ".join(phrases[:3])))
    return out


def conformance(text: str, writing_dna: dict) -> float:
    """0..1 — how closely the text follows ARFADA's historical style.

    Rewards paragraph length near the DNA median, sentence-length variation, and low
    generic-filler density. Used for regression (ARFADA-like text must out-score
    generic templated text).
    """
    low = (text or "")
    paras = [p for p in re.split(r"\n{2,}|\n", low) if len(p.split()) >= 5]
    words = max(1, len(re.findall(r"[A-Za-z']+", low)))

    # filler component (1 = no filler, 0 = saturated)
    filler = sum(len(re.findall(rf"\b{re.escape(w)}\b", low.lower())) for w in _GENERIC_WORDS)
    filler += sum(low.lower().count(p) for p in _GENERIC_PHRASES)
    filler_score = max(0.0, 1.0 - (filler * 1000.0 / words) / 12.0)

    # paragraph-length proximity to DNA median
    para_score = 0.5
    dna_med = (writing_dna or {}).get("paragraph_word_median")
    if dna_med and paras:
        med = statistics.median(len(p.split()) for p in paras)
        para_score = max(0.0, 1.0 - abs(med - dna_med) / max(dna_med, 1))

    # sentence-length variation (reward some variety)
    sents = _sentences(low)
    var_score = 0.3
    if len(sents) >= 3:
        slens = [len(s.split()) for s in sents]
        mean = statistics.mean(slens)
        var_score = min(1.0, (statistics.pstdev(slens) / mean) / 0.4) if mean else 0.3

    return round(0.45 * filler_score + 0.35 * para_score + 0.20 * var_score, 3)


# ---------------------------------------------------------------------------
# section + run aggregation
# ---------------------------------------------------------------------------

def style_qa_section(candidate: dict, writing_dna: dict,
                     exemplar_excerpts: list, *, section_id="") -> list[dict]:
    text = _blocks_text(candidate)
    findings = []
    findings += filler_findings(text, section_id=section_id)
    findings += uniformity_findings(candidate, section_id=section_id)
    findings += divergence_findings(candidate, writing_dna, section_id=section_id)
    findings += copy_findings(text, exemplar_excerpts, section_id=section_id)
    return findings


def style_qa_report(run_dir: str | Path) -> dict:
    """Aggregate Writing-DNA style QA across all generated sections of a run."""
    run_dir = Path(run_dir)
    sections_dir = run_dir / "generated_sections"
    packets_dir = run_dir / "generation_packets"
    import json

    writing_dna = {}
    try:
        from .exemplars import retrieval as _ex
        writing_dna = _ex.writing_dna()
    except Exception:
        writing_dna = {}

    findings: list[dict] = []
    conformances = []
    sections_checked = 0
    if sections_dir.exists():
        for f in sorted(sections_dir.glob("*.json")):
            try:
                cand = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            sid = cand.get("section_id", f.stem)
            excerpts = []
            pk = packets_dir / f"{sid}.json"
            if pk.exists():
                try:
                    packet = json.loads(pk.read_text(encoding="utf-8"))
                    excerpts = [e.get("style_excerpt", "")
                                for e in packet.get("historical_exemplars", [])]
                except Exception:
                    excerpts = []
            findings += style_qa_section(cand, writing_dna, excerpts, section_id=sid)
            conformances.append(conformance(_blocks_text(cand), writing_dna))
            sections_checked += 1

    by_sev = {WARNING: 0, IMPROVEMENT: 0}
    for f in findings:
        by_sev[f["severity"]] = by_sev.get(f["severity"], 0) + 1
    status = "OK" if not findings else ("NEEDS_STYLE_EDITS" if by_sev[WARNING] else "MINOR")

    return {
        "check": "WRITING_DNA_STYLE_QA",
        "writing_dna_active": bool(writing_dna),
        "sections_checked": sections_checked,
        "status": status,
        "counts": by_sev,
        "mean_conformance": round(statistics.mean(conformances), 3) if conformances else None,
        "findings": findings,
        "note": "Style QA rewrites WORDING ONLY. It must not change facts, approved or "
                "provisional decisions, methodology numbers, or budget values.",
    }
