"""build_blueprint.py — deterministic proposal blueprint builder (Phase 3).

Usage:
    python scripts/build_blueprint.py <run_dir>

Reads tor_analysis.json + requirements.json + (optional) decision_register.json,
validates run identity, builds proposal_blueprint.json and generation_status.json.
Prints a machine-readable summary. No LLM, no network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from engine.tor.blueprint import build_blueprint, blueprint_to_dict
from engine.tor.generation import init_status, atomic_write_json


def _out(data: dict) -> None:
    s = json.dumps(data, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write((s + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def _err(msg: str, code: int = 1) -> None:
    sys.stderr.buffer.write((json.dumps({"error": msg}) + "\n").encode("utf-8"))
    sys.exit(code)


def _read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        _err("Usage: build_blueprint.py <run_dir>")
    run_dir = Path(args[0]).expanduser().resolve()
    if not run_dir.exists():
        _err(f"Run directory not found: {run_dir}")

    tor_path = run_dir / "tor_analysis.json"
    req_path = run_dir / "requirements.json"
    if not tor_path.exists() or not req_path.exists():
        _err("tor_analysis.json or requirements.json missing — run analyze_tor.py first", 2)

    tor = _read_json(tor_path)
    reqs_doc = _read_json(req_path)
    requirements = reqs_doc.get("requirements", [])

    # run identity check
    run_id = tor.get("run_id")
    if reqs_doc.get("run_id") and reqs_doc["run_id"] != run_id:
        _err("run_id mismatch between tor_analysis.json and requirements.json", 3)

    # decision register (optional)
    register = None
    reg_path = run_dir / "decision_register.json"
    if reg_path.exists():
        register = _read_json(reg_path)
        if register.get("run_id") != run_id:
            _err("decision_register.json run_id does not match this run — cross-TOR state", 3)

    # metadata
    metadata = tor.get("metadata", {})
    fields_found = list(metadata.keys())
    language = tor.get("diagnostics", {}).get("language_detected", "english")
    # Assignment type inferred during analysis (Phase 4) — NO fixed evaluation default.
    at = tor.get("assignment_type", {})
    assignment_type = at.get("assignment_type", "OTHER")
    # If the type needs a decision and the user resolved it in the register, honor it.
    if register:
        for d in register.get("decisions", []):
            if d.get("requirement_id") == "assignment_type" \
                    and d.get("decision_status") == "RESOLVED" and d.get("selected_value"):
                assignment_type = str(d["selected_value"]).upper()

    tor_identity = register.get("tor_identity") if register else run_id

    bp = build_blueprint(
        run_id=run_id,
        tor_identity=tor_identity or run_id,
        assignment_type=assignment_type,
        language=language,
        created_at=tor.get("analyzed_at", ""),
        requirements=requirements,
        fields_found=fields_found,
        decision_register=register,
    )

    bp_dict = blueprint_to_dict(bp)
    atomic_write_json(run_dir / "proposal_blueprint.json", bp_dict)

    # generation status
    status = init_status(bp_dict, register)
    atomic_write_json(run_dir / "generation_status.json", status)

    # section status breakdown
    blocked = sum(1 for s in status["sections"].values()
                  if s["status"] == "BLOCKED_BY_DECISION")
    pending = sum(1 for s in status["sections"].values() if s["status"] == "PENDING")

    _out({
        "status": "ok",
        "run_id": run_id,
        "assignment_type": bp.assignment_type,
        "assignment_type_label": bp.assignment_type_label,
        "framework_section": bp.framework_section,
        "knowledge_version": bp.knowledge_version,
        "blueprint": {
            "sections": bp.coverage["sections"],
            "total_bidder_requirements": bp.coverage["total_bidder_requirements"],
            "mandatory_bidder_requirements": bp.coverage["mandatory_bidder_requirements"],
            "response_slots": bp.coverage["response_slots"],
            "open_decisions": bp.coverage["open_decisions"],
            "sections_blocked_by_decisions": blocked,
            "sections_pending": pending,
            "sections_needing_evidence": bp.coverage["sections_needing_evidence"],
        },
        "section_order": [s.title for s in bp.sections],
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
