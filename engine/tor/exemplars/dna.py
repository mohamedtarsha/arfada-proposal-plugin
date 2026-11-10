"""Deterministic extraction of Writing DNA, Formatting DNA, section exemplars, and
TOR→response patterns from winning-proposal DOCX files. No model, no network, no OCR.

Everything produced here is STYLE metadata + local section text — never a factual
source. Section text is cached locally only (gitignored), never committed.
"""
from __future__ import annotations

import re
import statistics
import sys
from pathlib import Path
from typing import Any

_DEPS = Path(__file__).resolve().parent.parent.parent.parent / ".mcp_deps"
if _DEPS.exists() and str(_DEPS) not in sys.path:
    sys.path.insert(0, str(_DEPS))

# section-type classification by heading keywords (lowercased substring match)
SECTION_KEYS = [
    ("EXECUTIVE_SUMMARY", ["executive summary", "ملخص تنفيذي"]),
    ("CONTEXT", ["context", "background", "understanding", "introduction", "السياق", "الخلفية"]),
    ("OBJECTIVES", ["objective", "scope", "purpose", "الأهداف", "النطاق"]),
    ("EVALUATION_FRAMEWORK", ["evaluation framework", "evaluation matrix", "إطار التقييم"]),
    ("ASSESSMENT_FRAMEWORK", ["assessment framework", "إطار التقييم"]),
    ("MONITORING_FRAMEWORK", ["monitoring framework", "monitoring matrix"]),
    ("RESEARCH_FRAMEWORK", ["research framework"]),
    ("SAMPLING", ["sampling", "sample", "العينة"]),
    ("DATA_COLLECTION", ["data collection", "data-collection", "tools", "جمع البيانات"]),
    ("DATA_ANALYSIS", ["analysis", "data analysis", "التحليل"]),
    ("METHODOLOGY", ["methodology", "approach", "method", "المنهجية"]),
    ("QUALITY_ASSURANCE", ["quality assurance", "quality control", "ضمان الجودة"]),
    ("ETHICS", ["ethic", "safeguard", "do no harm", "الأخلاقيات", "الحماية"]),
    ("WORKPLAN", ["work plan", "workplan", "timeline", "schedule", "الجدول الزمني"]),
    ("DELIVERABLES", ["deliverable", "outputs", "المخرجات", "التسليمات"]),
    ("TEAM", ["team", "personnel", "staffing", "الفريق", "الكادر"]),
    ("EXPERIENCE", ["experience", "capacity", "track record", "الخبرة"]),
    ("SUBMISSION", ["submission", "compliance", "التقديم"]),
]

_MODALS = ["will", "shall", "proposed", "propose", "ensure", "conduct", "undertake"]
_METHOD_TERMS = {
    "KII": r"\bkiis?\b|key\s+informant", "FGD": r"\bfgds?\b|focus\s+group",
    "survey": r"\bsurveys?\b|household\s+survey", "desk_review": r"desk\s+review",
    "observation": r"observation", "idi": r"\bidi\b|in-depth\s+interview",
}
# TOR→response pattern tags detectable deterministically in proposal methodology text
_PATTERN_TAGS = {
    "rationale": r"\b(rationale|purpose|in order to|aims? to|designed to)\b",
    "respondent_categories": r"\b(respondents?|stakeholders?|participants?|key informants?|categories)\b",
    "triangulation": r"\b(triangulat|cross-?check|corroborat|mixed[- ]methods)\b",
    "analysis": r"\b(analys|thematic|coding|disaggregat|statistical)\b",
    "quality_safeguards": r"\b(quality|validation|pilot|back-?check|supervision)\b",
    "ethics": r"\b(consent|confidential|do no harm|safeguard)\b",
}


def classify_section(heading: str) -> str:
    h = (heading or "").lower()
    for key, cues in SECTION_KEYS:
        if any(c in h for c in cues):
            return key
    return "OTHER"


def docx_sections(path: Path) -> list[dict]:
    """Split a proposal DOCX into sections by heading. Returns [{heading, type, text, blocks}]."""
    from docx import Document
    doc = Document(str(path))
    sections: list[dict] = []
    cur = {"heading": "", "type": "OTHER", "paras": [], "bullets": 0, "numbered": 0, "tables": 0}

    def flush():
        if cur["paras"] or cur["heading"]:
            text = "\n".join(cur["paras"]).strip()
            sections.append({"heading": cur["heading"], "type": cur["type"], "text": text,
                             "bullets": cur["bullets"], "numbered": cur["numbered"],
                             "tables": cur["tables"], "paragraphs": len(cur["paras"])})

    # iterate body in order (paragraphs + tables)
    from docx.text.paragraph import Paragraph as _P
    from docx.table import Table as _T
    for child in doc.element.body:
        tag = child.tag.split("}")[-1]
        if tag == "p":
            para = _P(child, doc)
            style = (para.style.name or "").lower() if para.style else ""
            text = (para.text or "").strip()
            if not text:
                continue
            if "heading" in style or ("title" in style and len(text) < 90):
                flush()
                cur = {"heading": text, "type": classify_section(text), "paras": [],
                       "bullets": 0, "numbered": 0, "tables": 0}
            else:
                if "list bullet" in style or (text[:1] in "-•*–"):
                    cur["bullets"] += 1
                elif "list number" in style:
                    cur["numbered"] += 1
                cur["paras"].append(text)
        elif tag == "tbl":
            cur["tables"] += 1
    flush()
    return [s for s in sections if s["text"] or s["tables"]]


def writing_dna_for_doc(sections: list[dict]) -> dict:
    """Per-document writing DNA (aggregated later across the corpus)."""
    para_lens, sent_lens = [], []
    modal_counts = {m: 0 for m in _MODALS}
    bullets = numbered = tables = 0
    first_person = org_voice = 0
    all_text = []
    for s in sections:
        bullets += s.get("bullets", 0)
        numbered += s.get("numbered", 0)
        tables += s.get("tables", 0)
        for para in s["text"].split("\n"):
            words = para.split()
            if len(words) >= 3:
                para_lens.append(len(words))
            for sent in re.split(r"(?<=[.!?])\s+", para):
                w = sent.split()
                if len(w) >= 2:
                    sent_lens.append(len(w))
            low = para.lower()
            for m in _MODALS:
                modal_counts[m] += len(re.findall(rf"\b{m}\b", low))
            first_person += len(re.findall(r"\b(we|our|us)\b", low))
            org_voice += len(re.findall(r"\barfada\b|the (consultant|team|firm)\b", low))
            all_text.append(low)
    return {
        "paragraph_word_median": statistics.median(para_lens) if para_lens else 0,
        "paragraph_word_p90": _pctl(para_lens, 90),
        "sentence_word_median": statistics.median(sent_lens) if sent_lens else 0,
        "bullets": bullets, "numbered": numbered, "tables": tables,
        "modal_usage": modal_counts,
        "voice": ("first_person" if first_person > org_voice else "organizational"),
        "section_count": len(sections),
    }


def _pctl(vals, p):
    if not vals:
        return 0
    s = sorted(vals)
    k = int(round((p / 100) * (len(s) - 1)))
    return s[k]


def aggregate_writing_dna(per_doc: list[dict]) -> dict:
    """Corpus-level Writing DNA from per-document profiles."""
    if not per_doc:
        return {}
    def med(key):
        vals = [d[key] for d in per_doc if isinstance(d.get(key), (int, float))]
        return round(statistics.median(vals), 1) if vals else 0
    total_bullets = sum(d.get("bullets", 0) for d in per_doc)
    total_tables = sum(d.get("tables", 0) for d in per_doc)
    total_numbered = sum(d.get("numbered", 0) for d in per_doc)
    voices = [d.get("voice") for d in per_doc]
    modal = {}
    for m in _MODALS:
        modal[m] = sum(d.get("modal_usage", {}).get(m, 0) for d in per_doc)
    return {
        "documents": len(per_doc),
        "paragraph_word_median": med("paragraph_word_median"),
        "paragraph_word_p90": med("paragraph_word_p90"),
        "sentence_word_median": med("sentence_word_median"),
        "bullets_total": total_bullets, "numbered_total": total_numbered,
        "tables_total": total_tables,
        "bullets_per_doc": round(total_bullets / len(per_doc), 1),
        "tables_per_doc": round(total_tables / len(per_doc), 1),
        "dominant_voice": max(set(voices), key=voices.count) if voices else "organizational",
        "modal_usage_total": modal,
        "guidance": _dna_guidance(med("paragraph_word_median"),
                                  round(total_tables / len(per_doc), 1),
                                  max(set(voices), key=voices.count) if voices else "organizational"),
    }


def _dna_guidance(para_median, tables_per_doc, voice) -> list[str]:
    g = []
    if para_median:
        g.append(f"Aim for paragraphs around {int(para_median)} words (ARFADA median).")
    if tables_per_doc >= 2:
        g.append("ARFADA proposals use tables frequently — prefer tables for frameworks/deliverables/workplan.")
    g.append(f"Write in an {voice} voice consistent with past winning proposals.")
    g.append("Explain methods specifically (purpose, respondents, triangulation, analysis) — avoid generic AI framing.")
    return g


def formatting_dna_for_doc(sections: list[dict]) -> dict:
    return {
        "section_order": [s["type"] for s in sections if s["type"] != "OTHER"],
        "has_tables": any(s.get("tables", 0) for s in sections),
        "uses_bullets": any(s.get("bullets", 0) for s in sections),
    }


def aggregate_formatting_dna(per_doc: list[dict]) -> dict:
    orders = [tuple(d.get("section_order", [])) for d in per_doc if d.get("section_order")]
    common_seq = []
    if orders:
        # most frequent section-type ordering prefix (coarse)
        from collections import Counter
        flat = Counter()
        for o in orders:
            for i, t in enumerate(o):
                flat[t] += 1
        common_seq = [t for t, _ in flat.most_common(12)]
    return {
        "common_sections": common_seq,
        "table_docs": sum(1 for d in per_doc if d.get("has_tables")),
        "bullet_docs": sum(1 for d in per_doc if d.get("uses_bullets")),
    }


def response_patterns_for_doc(sections: list[dict]) -> dict:
    """Abstract TOR→response patterns observed in methodology/data-collection sections."""
    text = " ".join(s["text"].lower() for s in sections
                    if s["type"] in ("METHODOLOGY", "DATA_COLLECTION", "SAMPLING", "QUALITY_ASSURANCE"))
    methods = {name: bool(re.search(pat, text)) for name, pat in _METHOD_TERMS.items()}
    tags = {tag: bool(re.search(pat, text)) for tag, pat in _PATTERN_TAGS.items()}
    return {"methods": [k for k, v in methods.items() if v],
            "pattern_tags": [k for k, v in tags.items() if v]}


def aggregate_response_patterns(per_doc: list[dict]) -> dict:
    from collections import Counter
    method_c, tag_c = Counter(), Counter()
    for d in per_doc:
        method_c.update(d.get("methods", []))
        tag_c.update(d.get("pattern_tags", []))
    n = max(1, len(per_doc))
    return {
        "common_methods": [m for m, _ in method_c.most_common()],
        "response_pattern_tags": [t for t, c in tag_c.most_common() if c >= max(1, n // 3)],
        "note": ("When answering a TOR requirement, ARFADA winning proposals typically: "
                 + ", ".join(t.replace('_', ' ') for t, c in tag_c.most_common(5))
                 + " — reproduce this REASONING pattern, never the old wording."),
    }
