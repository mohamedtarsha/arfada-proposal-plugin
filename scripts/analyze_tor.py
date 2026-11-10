"""analyze_tor.py — CLI bridge for ARFADA TOR analysis (Phase 1 / 1.1).

Usage:
    python scripts/analyze_tor.py <tor_file>  [--output-dir <dir>]

Runs deterministic PE2-compatible TOR extraction on a local PDF or DOCX file.
Writes JSON artifacts to <output_dir>/<run_id>/ and prints the directory path
to stdout (Claude Code skill reads from there).

Phase 1.1 additions:
- Arabic actor classification (_AR_BIDDER_CUES / _AR_CLIENT_CUES)
- Arabic open-decision detection (_AR_OPEN_CHOICE / _AR_APPROX_QUANT)
- Arabic fixed-value protection (AT_MOST constructs not flagged as decisions)
- Language detection heuristic
- Diagnostics section in tor_analysis.json

No Anthropic API key required. All extraction is deterministic Python.
Exits 0 on success, non-zero on failure.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Engine path setup: works from any working directory
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from engine.tor.adapter import file_store
from engine.tor.extractor import extract_fields, extract_requirements
from engine.tor import structuring
from engine.tor.fields import FIELDS, FIELD_LABEL
from engine.tor.value import parse_quantities
from engine.tor.decision_model import (
    classify_decision, validate_proposed_value,
    DecisionCandidate, _OPEN_TYPES, _CONSTRAINT_TYPES,
)
from engine.tor.assignment_type import infer_assignment_type


# ---------------------------------------------------------------------------
# Human-decision detection
# ---------------------------------------------------------------------------

_OPEN_CHOICE = re.compile(
    r"\b(as\s+appropriate|consultant(?:'s)?\s+(?:discretion|choice|judgment|decision)|"
    r"propose(?:d)?\s+(?:approach|methodology|sample|method)|"
    r"at\s+the\s+discretion|to\s+be\s+determined|tbd|to\s+be\s+agreed|"
    r"based\s+on\s+available\s+resources)\b",
    re.I,
)
_OPEN_QUANTITY_QUALIFIERS = {"APPROX", "AT_LEAST", "RANGE"}

# Arabic open-choice language (Phase 1.1)
_AR_OPEN_CHOICE = re.compile(
    r"(?:حسب\s+ما\s+يراه\s+(?:الاستشاري\s+)?مناسباً?|وفق\s+(?:المنهجية\s+)?المقترحة?|"
    r"يقترح\s+(?:الاستشاري|مقدم\s+العرض)|حسب\s+الحاجة|عند\s+الاقتضاء|"
    r"حسب\s+تقديره|وفق\s+تقدير|حسب\s+رأيه)",
    re.UNICODE,
)
# Arabic approximate/open-quantity words (→ human decision)
_AR_APPROX_QUANT = re.compile(
    r"(?:حوالي|نحو\b|تقريباً|تقريبي|"
    r"ما\s+بين\s+\d+\s+و[َ]?\s*\d+|من\s+\d+\s+إلى\s+\d+|"
    r"على\s+الأقل|لا\s+يقل\s+عن|على\s+أقل\s+تقدير)",
    re.UNICODE,
)
# Arabic AT_MOST — fixed upper bound, NOT a human decision
_AR_AT_MOST = re.compile(
    r"(?:لا\s+يتجاوز|لا\s+يزيد\s+عن|على\s+الأكثر|بحد\s+أقصى|في\s+حدود\s+\d)",
    re.UNICODE,
)


def _is_human_decision(req) -> tuple[bool, str]:
    """Return (True, note) if this requirement leaves a genuine bidder choice open.
    Phase 1.1: Arabic open-choice and approximate-quantity detection added.
    AT_MOST constructs (لا يتجاوز / AT_MOST) are fixed limits — never flagged.
    """
    text = req.text or ""
    # Arabic AT_MOST protection: fixed upper bound is not a decision
    if _AR_AT_MOST.search(text):
        return False, ""
    # Arabic open-choice language
    m = _AR_OPEN_CHOICE.search(text)
    if m:
        return True, f"Arabic open choice: '{m.group(0)}'"
    # Arabic approximate quantity
    m = _AR_APPROX_QUANT.search(text)
    if m:
        return True, f"Arabic approximate quantity: '{m.group(0)}'"
    # English open-choice language
    m = _OPEN_CHOICE.search(text)
    if m:
        return True, f"Open choice language: '{m.group(0)}'"
    # English approximate/open quantity
    for q in parse_quantities(text):
        if q.qualifier in _OPEN_QUANTITY_QUALIFIERS:
            return True, f"Unfixed quantity: '{q.raw}' ({q.qualifier})"
    return False, ""


# ---------------------------------------------------------------------------
# Actor classification (English + Arabic, Phase 1.1)
# ---------------------------------------------------------------------------

_CLIENT_CUES = re.compile(
    r"\b(client|contracting\s+authority|donor|un\s+agency|ngo|"
    r"unicef|unhcr|wfp|undp|ocha|world\s+bank)\s+(?:will|shall|must|is\s+responsible|"
    r"provides?|reviews?|approves?|arranges?|facilitates?)\b",
    re.I,
)
_BIDDER_CUES = re.compile(
    r"\b(consultant|evaluation\s+team|firm|contractor|bidder|service\s+provider|"
    r"team\s+leader|researcher)\s+(?:shall|must|will|is\s+required\s+to|is\s+expected\s+to)\b",
    re.I,
)
# Arabic bidder cues (Phase 1.1)
_AR_BIDDER_CUES = re.compile(
    r"(?:على\s+الاستشاري|على\s+مقدم\s+العرض|على\s+فريق\s+التقييم|على\s+الشركة|"
    r"على\s+المتقدم|على\s+المُقيِّم|على\s+المستشار|يلتزم\s+الاستشاري|"
    r"يتعين\s+على\s+الاستشاري|يقوم\s+الاستشاري)",
    re.UNICODE,
)
# Arabic client cues (Phase 1.1)
_AR_CLIENT_CUES = re.compile(
    r"(?:ستوفر\s+الجهة|ستقوم\s+الجهة|سيوفر\s+العميل|ستتولى\s+الجهة|"
    r"الجهة\s+المتعاقدة\s+ست|سيقوم\s+الممول|ستقوم\s+المنظمة|"
    r"يتولى\s+الممول|سيتولى\s+العميل|ستراجع\s+الجهة|ستعتمد\s+الجهة)",
    re.UNICODE,
)


def _actor(req) -> str:
    text = req.text or ""
    # Arabic checks first (Phase 1.1)
    if _AR_CLIENT_CUES.search(text):
        return "CLIENT"
    if _AR_BIDDER_CUES.search(text):
        return "BIDDER"
    # English checks
    if _CLIENT_CUES.search(text):
        return "CLIENT"
    if _BIDDER_CUES.search(text):
        return "BIDDER"
    return "BIDDER" if req.mandatory else "UNKNOWN"


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

_AR_CHAR = re.compile(r"[؀-ۿ]")


def _detect_language(blocks: list[dict]) -> str:
    """Heuristic: 'arabic', 'english', or 'mixed' based on character proportion."""
    all_text = " ".join(b.get("plain_text", "") for b in blocks)
    total = len(all_text.replace(" ", ""))
    if total == 0:
        return "unknown"
    ar_chars = len(_AR_CHAR.findall(all_text))
    ratio = ar_chars / total
    if ratio > 0.4:
        return "arabic"
    if ratio > 0.1:
        return "mixed"
    return "english"


# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------

def analyze(tor_path: str | Path, output_root: str | Path | None = None) -> dict:
    """Full TOR analysis. Returns the output directory path and summary dict."""
    tor_path = Path(tor_path).expanduser().resolve()
    if not tor_path.exists():
        raise FileNotFoundError(f"TOR file not found: {tor_path}")

    # output directory
    run_id = "tor_" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    if output_root is None:
        # Place arfada-output/ next to the working directory (or CWD)
        output_root = Path.cwd() / "arfada-output"
    out_dir = Path(output_root) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- extraction --------------------------------------------------------
    store = file_store(tor_path)
    aid = "analysis_" + run_id
    doc = store.documents(aid)[0]
    did = doc["document_id"]

    fields = extract_fields(store, aid)
    reqs = extract_requirements(store, aid, fields)

    # --- diagnostics -------------------------------------------------------
    all_blocks = store.blocks(did)
    all_tables = store.tables(did)
    language = _detect_language(all_blocks)
    table_cells_total = sum(
        len(store.cells(t["table_id"])) for t in all_tables
    )
    reqs_from_tables = sum(
        1 for r in reqs
        if (r.source_locator or "").startswith("tbl") or ":tbl" in (r.source_locator or "")
    )
    diagnostics = {
        "language_detected": language,
        "total_blocks": len(all_blocks),
        "heading_blocks": sum(1 for b in all_blocks if b.get("block_type") == "HEADING"),
        "list_item_blocks": sum(1 for b in all_blocks if b.get("block_type") == "LIST_ITEM"),
        "table_cell_blocks": sum(1 for b in all_blocks if b.get("block_type") == "TABLE_CELL"),
        "pdf_tables_found": len(all_tables),
        "pdf_table_cells": table_cells_total,
        "pdf_tables_unavailable": bool(
            getattr(store, "_pdf_tables_unavailable", False)
        ),
        "requirements_from_tables": reqs_from_tables,
        "deliverables_detected": 0,  # filled after structuring
        "open_decisions_detected": 0,  # filled after enrichment
    }

    # --- enrich requirements + classify decisions --------------------------
    enriched_reqs: list[dict] = []
    decision_candidates: list[DecisionCandidate] = []

    for r in reqs:
        actor = _actor(r)
        # Richer decision classification (Phase 1.2)
        dc = classify_decision(r, actor)
        # Narrow fallback: if decision_model says NO_DECISION but old heuristics
        # catch EXPLICIT OPEN-CHOICE LANGUAGE (not quantity patterns), upgrade.
        # Quantity patterns (AT_LEAST/APPROX) are intentionally reclassified as
        # constraints by the new model — do NOT let the old model override them.
        if not dc.is_human_decision:
            old_dec, old_note = _is_human_decision(r)
            if old_dec and ("Open choice" in old_note or "Arabic open choice" in old_note):
                dc.decision_type = "OPEN_PROPOSAL_DECISION"
                dc.is_human_decision = True
                dc.reason = old_note
                dc.question = old_note

        if dc.decision_type not in ("NO_DECISION",):
            decision_candidates.append(dc)

        enriched_reqs.append({
            "req_id": r.req_id,
            "text": r.text,
            "category": r.category,
            "mandatory": r.mandatory,
            "modality": r.modality,
            "actor": actor,
            "source_section": r.source_section_path,
            "page": r.page,
            "method": r.method,
            "confidence": r.confidence,
            "source_locator": r.source_locator,
            "atomic_group": r.atomic_group,
            "is_human_decision": dc.is_human_decision,
            "decision_type": dc.decision_type,
            "decision_note": dc.reason,
            "constraint_type": dc.constraint_type,
            "constraint_min": dc.minimum,
            "constraint_max": dc.maximum,
        })

    # fill decisions count in diagnostics
    diagnostics["open_decisions_detected"] = sum(
        1 for r in enriched_reqs if r["is_human_decision"]
    )

    # --- first-class objects from structuring ------------------------------
    deliverables = structuring.deliverables(aid, aid, reqs)
    diagnostics["deliverables_detected"] = len(deliverables)
    submission = structuring.submission(aid, aid, reqs, fields) if hasattr(structuring, "submission") else []
    team_items = structuring.team(aid, aid, reqs) if hasattr(structuring, "team") else []
    eval_qs = structuring.eval_questions(aid, aid, reqs) if hasattr(structuring, "eval_questions") else []
    methods = structuring.methods(aid, aid, reqs) if hasattr(structuring, "methods") else []
    timeline = structuring.timeline(aid, aid, reqs) if hasattr(structuring, "timeline") else []

    # --- metadata from fields ----------------------------------------------
    metadata: dict = {}
    for f in fields:
        metadata[f.field_key] = {
            "value": f.value_text,
            "confidence": f.confidence,
            "method": f.method,
            "page": f.page,
            "source_section": f.source_section_path,
        }

    # --- assignment type inference (Phase 4) -------------------------------
    atype = infer_assignment_type(metadata, enriched_reqs)
    assignment_type = {
        "assignment_type": atype.assignment_type,
        "label": atype.label,
        "assignment_type_confidence": atype.confidence,
        "assignment_type_evidence": atype.evidence,
        "scores": atype.scores,
        "needs_decision": atype.needs_decision,
    }

    # LOW-confidence type → surface a genuine classification decision (spec §2).
    # Never silently fall back to EVALUATION.
    if atype.needs_decision:
        options = [atype.assignment_type] + [
            t for t, _ in list(atype.scores.items())[1:3]
            if t != atype.assignment_type
        ]
        decision_candidates.append(DecisionCandidate(
            decision_id="dec_assignment_type",
            requirement_id="assignment_type",
            decision_type="OPEN_PROPOSAL_DECISION",
            is_human_decision=True,
            question=("How should this assignment be classified for proposal "
                      f"structuring? Best guess: {atype.label}. "
                      f"Evidence: {', '.join(atype.evidence[:3])}"),
            constraint_type="ENUM",
            minimum=None, maximum=None, fixed_value=None,
            allowed_options=options or [atype.assignment_type],
            reason="Assignment type could not be inferred with high confidence.",
            source_text=(metadata.get("assignment", {}) or {}).get("value", "")[:200]
            if isinstance(metadata.get("assignment"), dict) else "",
            source_locator="", category="assignment_type", actor="BIDDER",
        ))

    # --- summary counts ----------------------------------------------------
    total = len(enriched_reqs)
    mandatory = sum(1 for r in enriched_reqs if r["mandatory"])
    optional_ = total - mandatory
    decisions = sum(1 for r in enriched_reqs if r["is_human_decision"])
    client_resp = sum(1 for r in enriched_reqs if r["actor"] == "CLIENT")
    bidder_obl = sum(1 for r in enriched_reqs if r["actor"] == "BIDDER")

    # Constraint / decision breakdown (Phase 1.2)
    constraint_count = sum(
        1 for dc in decision_candidates
        if dc.decision_type in _CONSTRAINT_TYPES and dc.decision_type != "NO_DECISION"
    )
    open_decision_count = sum(
        1 for dc in decision_candidates if dc.decision_type == "OPEN_PROPOSAL_DECISION"
    )
    deferred_count = sum(
        1 for dc in decision_candidates if dc.decision_type == "DEFERRED_DECISION"
    )
    optional_choice_count = sum(
        1 for dc in decision_candidates if dc.decision_type == "OPTIONAL_CHOICE"
    )

    categories: dict[str, int] = {}
    for r in enriched_reqs:
        categories[r["category"]] = categories.get(r["category"], 0) + 1

    summary = {
        "total_requirements": total,
        "mandatory": mandatory,
        "optional": optional_,
        "human_decisions": decisions,
        "proposal_decisions": open_decision_count,
        "deferred_decisions": deferred_count,
        "optional_choices": optional_choice_count,
        "constraints": constraint_count,
        "bidder_obligations": bidder_obl,
        "client_responsibilities": client_resp,
        "deliverables": len(deliverables),
        "timeline_items": len(timeline),
        "submission_items": len(submission),
        "team_items": len(team_items),
        "eval_questions": len(eval_qs),
        "methodology_items": len(methods),
        "categories": categories,
        "metadata_fields_found": len(fields),
        "metadata_fields_total": len(FIELDS),
    }

    # --- assemble full output ----------------------------------------------
    result = {
        "run_id": run_id,
        "file_path": str(tor_path),
        "file_name": tor_path.name,
        "analyzed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "plugin_version": "0.5.0",
        "diagnostics": diagnostics,
        "assignment_type": assignment_type,
        "metadata": metadata,
        "summary": summary,
        "requirements": enriched_reqs,
        "decision_candidates_summary": {
            "proposal_decisions": open_decision_count,
            "deferred": deferred_count,
            "optional_choices": optional_choice_count,
            "constraints": constraint_count,
        },
        "deliverables": deliverables,
        "submission": submission,
        "team": team_items,
        "eval_questions": eval_qs,
        "methodology": methods,
        "timeline": timeline,
        "output_dir": str(out_dir),
    }

    # --- write artifacts ---------------------------------------------------
    _write_json(out_dir / "tor_analysis.json", result)
    _write_json(out_dir / "requirements.json", {
        "run_id": run_id, "total": total, "mandatory": mandatory,
        "requirements": enriched_reqs,
    })
    # decision_candidates.json — validated candidates for Phase 2 Decision Review
    _write_json(out_dir / "decision_candidates.json", {
        "run_id": run_id,
        "proposal_decisions": open_decision_count,
        "deferred_decisions": deferred_count,
        "constraints": constraint_count,
        "candidates": [
            {
                "decision_id": dc.decision_id,
                "requirement_id": dc.requirement_id,
                "decision_type": dc.decision_type,
                "is_human_decision": dc.is_human_decision,
                "question": dc.question,
                "constraint_type": dc.constraint_type,
                "minimum": dc.minimum,
                "maximum": dc.maximum,
                "fixed_value": dc.fixed_value,
                "allowed_options": dc.allowed_options,
                "reason": dc.reason,
                "source_text": dc.source_text,
                "category": dc.category,
                "actor": dc.actor,
            }
            for dc in decision_candidates
        ],
    })
    _write_summary_md(out_dir / "analysis_summary.md", result, tor_path)

    return result


# ---------------------------------------------------------------------------
# Markdown summary
# ---------------------------------------------------------------------------

def _write_summary_md(path: Path, r: dict, tor_path: Path) -> None:
    s = r["summary"]
    meta = r["metadata"]

    def mv(key: str) -> str:
        entry = meta.get(key, {})
        v = entry.get("value", "") if isinstance(entry, dict) else ""
        return v.strip()[:200] if v else "NOT_SPECIFIED"

    lines = [
        "# ARFADA TOR Analysis",
        "",
        f"**File:** {tor_path.name}  ",
        f"**Run:** {r['run_id']}  ",
        f"**Analyzed:** {r['analyzed_at'][:19].replace('T', ' ')} UTC",
        "",
        "## Assignment",
        "",
        f"| Field | Value |",
        "| --- | --- |",
        f"| Title | {mv('assignment')} |",
        f"| Client | {mv('client')} |",
        f"| Country | {mv('country')} |",
        f"| Background | {mv('background')[:120]}... |",
        f"| Objectives | {mv('objectives')[:120]}... |",
        f"| Timeline | {mv('timeline')} |",
        f"| Submission | {mv('submission_requirements')[:100]} |",
        "",
        "## Requirements Summary",
        "",
        f"| | Count |",
        "| --- | --- |",
        f"| Total requirements | **{s['total_requirements']}** |",
        f"| Mandatory | {s['mandatory']} |",
        f"| Optional | {s['optional']} |",
        f"| Bidder obligations | {s['bidder_obligations']} |",
        f"| Client responsibilities | {s['client_responsibilities']} |",
        "",
        "## Decision & Constraint Analysis",
        "",
        f"| Type | Count |",
        "| --- | --- |",
        f"| **Proposal decisions requiring review** | **{s['proposal_decisions']}** |",
        f"| Deferred decisions | {s['deferred_decisions']} |",
        f"| Optional choices | {s['optional_choices']} |",
        f"| TOR constraints (not decisions) | {s['constraints']} |",
        "",
        "> Proposal decisions = genuine choices the ARFADA team must make for the proposal.",
        "> Constraints = TOR-fixed values the proposal must respect but cannot change.",
        "",
        "## Extracted Objects",
        "",
        f"| Type | Count |",
        "| --- | --- |",
        f"| Deliverables | {s['deliverables']} |",
        f"| Timeline items | {s['timeline_items']} |",
        f"| Submission items | {s['submission_items']} |",
        f"| Team requirements | {s['team_items']} |",
        f"| Evaluation questions | {s['eval_questions']} |",
        f"| Methodology items | {s['methodology_items']} |",
        "",
        "## Category Breakdown",
        "",
    ]
    for cat, count in sorted(s["categories"].items(), key=lambda x: -x[1]):
        lines.append(f"- **{cat}**: {count}")

    decisions_list = [req for req in r["requirements"] if req["is_human_decision"]]
    if decisions_list:
        lines += ["", "## Decisions Required", ""]
        for d in decisions_list[:20]:
            lines.append(f"- [{d['req_id'][-8:]}] {d['text'][:120]}")
            if d["decision_note"]:
                lines.append(f"  _(reason: {d['decision_note']})_")

    lines += ["", f"---", f"*Generated by ARFADA Proposal Plugin v0.2.0*"]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args(argv):
    p = argparse.ArgumentParser(
        description="ARFADA TOR Analysis — deterministic PE2-compatible extraction")
    p.add_argument("tor_file", help="Path to the TOR file (.pdf or .docx)")
    p.add_argument("--output-dir", default=None,
                   help="Root output directory (default: ./arfada-output)")
    return p.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv or sys.argv[1:])
    try:
        result = analyze(args.tor_file, args.output_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"ERROR: Unexpected failure — {e}", file=sys.stderr)
        sys.exit(3)

    s = result["summary"]
    # Machine-readable one-liners for skill parsing:
    print(f"OUTPUT_DIR={result['output_dir']}")
    print(f"RUN_ID={result['run_id']}")
    print(f"REQUIREMENTS={s['total_requirements']}")
    print(f"MANDATORY={s['mandatory']}")
    print(f"PROPOSAL_DECISIONS={s['proposal_decisions']}")
    print(f"DEFERRED_DECISIONS={s['deferred_decisions']}")
    print(f"CONSTRAINTS={s['constraints']}")
    print(f"DELIVERABLES={s['deliverables']}")
    # backward-compat
    print(f"DECISIONS={s['human_decisions']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
