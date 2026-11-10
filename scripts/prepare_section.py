"""prepare_section.py — build a bounded generation packet for ONE section.

Usage:
    python scripts/prepare_section.py <run_dir> <section_id>

Writes generation_packets/<section_id>.json and prints it to stdout so the
active Claude Code session can read it and produce the section candidate.
If the section is BLOCKED_BY_DECISION, prints that status and does not emit a packet.
No LLM, no network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from engine.tor.generation import build_packet, atomic_write_json, set_section_status


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
    if len(args) < 2:
        _err("Usage: prepare_section.py <run_dir> <section_id>")
    run_dir = Path(args[0]).expanduser().resolve()
    section_id = args[1]
    if not run_dir.exists():
        _err(f"Run directory not found: {run_dir}")

    bp_path = run_dir / "proposal_blueprint.json"
    if not bp_path.exists():
        _err("proposal_blueprint.json missing — run build_blueprint.py first", 2)
    blueprint = _read_json(bp_path)

    section = next((s for s in blueprint["sections"] if s["section_id"] == section_id), None)
    if section is None:
        _err(f"Section '{section_id}' not in blueprint", 3)

    register = None
    reg_path = run_dir / "decision_register.json"
    if reg_path.exists():
        register = _read_json(reg_path)

    # blocked check
    status_path = run_dir / "generation_status.json"
    status_doc = _read_json(status_path) if status_path.exists() else None
    if status_doc:
        sec_status = status_doc["sections"].get(section_id, {}).get("status")
        if sec_status == "BLOCKED_BY_DECISION":
            _out({"status": "BLOCKED_BY_DECISION", "section_id": section_id,
                  "message": "Section depends on unresolved decisions — resolve them first."})
            return 0

    # requirements by id
    reqs_doc = _read_json(run_dir / "requirements.json")
    requirements_by_id = {r["req_id"]: r for r in reqs_doc.get("requirements", [])}

    # assignment metadata
    tor = _read_json(run_dir / "tor_analysis.json")
    meta = tor.get("metadata", {})
    assignment_metadata = {
        k: (meta.get(k, {}) or {}).get("value", "") if isinstance(meta.get(k), dict) else ""
        for k in ("assignment", "client", "country")
    }

    # verified ARFADA knowledge facts relevant to this section (Phase 4 / 4.1).
    # Knowledge(run_dir) uses the FROZEN proposal snapshot (live Google or static
    # fallback) — immutable for the duration of this run.
    from engine.tor.knowledge import Knowledge
    kb = Knowledge(run_dir=run_dir)
    country = assignment_metadata.get("country", "")
    verified_facts = kb.facts_for_section(
        section_id, assignment_type=blueprint.get("assignment_type", ""),
        country=country, region="MENA",
    )

    # Historical winning-proposal STYLE exemplars (v0.6.1) — LOWEST authority, bounded,
    # section-specific. Never facts; the validator runs an anti-copy guard.
    writing_dna = {}
    response_patterns = {}
    historical_exemplars = []
    try:
        from engine.tor.exemplars import retrieval as _ex
        if _ex.is_configured():
            writing_dna = _ex.writing_dna()
            response_patterns = _ex.response_patterns()
            historical_exemplars = _ex.retrieve_for_section(
                section_id, assignment_type=blueprint.get("assignment_type", ""),
                country=country, region="MENA", top=3)
    except Exception:
        pass

    packet = build_packet(
        section=section,
        slots=blueprint.get("slots", []),
        requirements_by_id=requirements_by_id,
        decision_register=register,
        language=blueprint.get("language", "english"),
        assignment_metadata=assignment_metadata,
        verified_arfada_facts=verified_facts,
        framework_columns=blueprint.get("framework_columns", []),
        assignment_type=blueprint.get("assignment_type", ""),
        knowledge_version=blueprint.get("knowledge_version", kb.version),
        writing_dna=writing_dna,
        response_patterns=response_patterns,
        historical_exemplars=historical_exemplars,
    )

    packets_dir = run_dir / "generation_packets"
    packets_dir.mkdir(exist_ok=True)
    atomic_write_json(packets_dir / f"{section_id}.json", packet)

    # mark GENERATING
    if status_doc:
        try:
            set_section_status(status_doc, section_id, "GENERATING")
            atomic_write_json(status_path, status_doc)
        except KeyError:
            pass

    _out(packet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
