"""analyze_tor.py — CLI bridge for ARFADA TOR analysis (Phase 1).

Usage:
    python scripts/analyze_tor.py <tor_file>  [--output-dir <dir>]

Runs deterministic PE2-compatible TOR extraction on a local PDF or DOCX file.
Writes JSON artifacts to <output_dir>/<run_id>/ and prints the directory path
to stdout (Claude Code skill reads from there).

No Anthropic API key required. All extraction is deterministic Python.
Claude Code's active session performs any additional semantic interpretation.

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


def _is_human_decision(req) -> tuple[bool, str]:
    """Return (True, note) if this requirement leaves a genuine bidder choice open."""
    text = req.text or ""
    # explicit open-choice language
    m = _OPEN_CHOICE.search(text)
    if m:
        return True, f"Open choice language: '{m.group(0)}'"
    # approximate or range quantity with no fixed upper bound
    for q in parse_quantities(text):
        if q.qualifier in _OPEN_QUANTITY_QUALIFIERS:
            return True, f"Unfixed quantity: '{q.raw}' ({q.qualifier})"
    return False, ""


# ---------------------------------------------------------------------------
# Actor classification (beyond PE2's mandatory/modality)
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


def _actor(req) -> str:
    text = req.text or ""
    if _CLIENT_CUES.search(text):
        return "CLIENT"
    if _BIDDER_CUES.search(text):
        return "BIDDER"
    # default: mandatory → bidder obligation; non-mandatory → unclear
    return "BIDDER" if req.mandatory else "UNKNOWN"


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
    did = store.documents(aid)[0]["document_id"]

    fields = extract_fields(store, aid)
    reqs = extract_requirements(store, aid, fields)

    # --- enrich requirements -----------------------------------------------
    enriched_reqs: list[dict] = []
    for r in reqs:
        is_dec, dec_note = _is_human_decision(r)
        actor = _actor(r)
        try:
            page = json.loads(r.__dict__.get("meta_json") or "{}").get("page")
        except Exception:
            page = None
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
            "is_human_decision": is_dec,
            "decision_note": dec_note,
        })

    # --- first-class objects from structuring ------------------------------
    deliverables = structuring.deliverables(aid, aid, reqs)
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

    # --- summary counts ----------------------------------------------------
    total = len(enriched_reqs)
    mandatory = sum(1 for r in enriched_reqs if r["mandatory"])
    optional_ = total - mandatory
    decisions = sum(1 for r in enriched_reqs if r["is_human_decision"])
    client_resp = sum(1 for r in enriched_reqs if r["actor"] == "CLIENT")
    bidder_obl = sum(1 for r in enriched_reqs if r["actor"] == "BIDDER")

    categories: dict[str, int] = {}
    for r in enriched_reqs:
        categories[r["category"]] = categories.get(r["category"], 0) + 1

    summary = {
        "total_requirements": total,
        "mandatory": mandatory,
        "optional": optional_,
        "human_decisions": decisions,
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
        "plugin_version": "0.2.0",
        "metadata": metadata,
        "summary": summary,
        "requirements": enriched_reqs,
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
        f"| Human decisions needed | {s['human_decisions']} |",
        f"| Bidder obligations | {s['bidder_obligations']} |",
        f"| Client responsibilities | {s['client_responsibilities']} |",
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
    # Machine-readable one-liner for skill parsing:
    print(f"OUTPUT_DIR={result['output_dir']}")
    print(f"RUN_ID={result['run_id']}")
    print(f"REQUIREMENTS={s['total_requirements']}")
    print(f"MANDATORY={s['mandatory']}")
    print(f"DECISIONS={s['human_decisions']}")
    print(f"DELIVERABLES={s['deliverables']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
