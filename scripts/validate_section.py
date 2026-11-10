"""validate_section.py — validate + persist a Claude-produced section candidate.

Usage:
    python scripts/validate_section.py <run_dir> <section_id> <candidate.json>

Validates the candidate against the section's generation packet (schema, slots,
ledger, decisions, constraints, fabricated-fact detection). On success:
- persists generated_sections/<section_id>.json
- renders generated_sections/<section_id>.md
- marks the section READY in generation_status.json
On failure: prints errors + failed slots (for a bounded repair) and exit code 4.
Does NOT overwrite a prior valid section on failure (transactional).
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

from engine.tor.generation import (
    validate_candidate, build_repair_packet, section_to_markdown,
    atomic_write_json, set_section_status, MAX_REPAIR_ATTEMPTS,
)


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
    if len(args) < 3:
        _err("Usage: validate_section.py <run_dir> <section_id> <candidate.json>")
    run_dir = Path(args[0]).expanduser().resolve()
    section_id = args[1]
    candidate_path = Path(args[2]).expanduser().resolve()

    if not run_dir.exists():
        _err(f"Run directory not found: {run_dir}")
    if not candidate_path.exists():
        _err(f"Candidate file not found: {candidate_path}")

    packet_path = run_dir / "generation_packets" / f"{section_id}.json"
    if not packet_path.exists():
        _err(f"Packet not found for {section_id} — run prepare_section.py first", 2)
    packet = _read_json(packet_path)

    try:
        candidate = _read_json(candidate_path)
    except json.JSONDecodeError as e:
        _err(f"Candidate is not valid JSON: {e}", 5)

    validation = validate_candidate(packet, candidate)

    status_path = run_dir / "generation_status.json"
    status_doc = _read_json(status_path) if status_path.exists() else None
    cur_attempts = 0
    if status_doc and section_id in status_doc["sections"]:
        cur_attempts = status_doc["sections"][section_id].get("attempts", 0)

    if not validation["valid"]:
        new_attempts = cur_attempts + 1
        repair = build_repair_packet(packet, candidate, validation, new_attempts)
        if status_doc:
            new_status = "FAILED" if new_attempts > MAX_REPAIR_ATTEMPTS else "GENERATING"
            try:
                set_section_status(status_doc, section_id, new_status, attempts=new_attempts)
                atomic_write_json(status_path, status_doc)
            except KeyError:
                pass
        # write repair packet for the session
        repair_dir = run_dir / "generation_packets"
        repair_dir.mkdir(exist_ok=True)
        atomic_write_json(repair_dir / f"{section_id}.repair.json", repair)
        out = {
            "status": "INVALID",
            "section_id": section_id,
            "attempt": new_attempts,
            "max_attempts": MAX_REPAIR_ATTEMPTS,
            "can_repair": new_attempts <= MAX_REPAIR_ATTEMPTS,
            "errors": validation["errors"],
            "failed_slots": validation["failed_slots"],
            "warnings": validation["warnings"],
            "repair_packet": f"generation_packets/{section_id}.repair.json",
        }
        sys.stderr.buffer.write((json.dumps(out, ensure_ascii=False) + "\n").encode("utf-8"))
        sys.exit(4)

    # --- valid: persist transactionally ---
    sections_dir = run_dir / "generated_sections"
    sections_dir.mkdir(exist_ok=True)
    atomic_write_json(sections_dir / f"{section_id}.json", candidate)
    title = packet.get("title", section_id)
    md = section_to_markdown(candidate, title)
    (sections_dir / f"{section_id}.md").write_text(md, encoding="utf-8")

    if status_doc:
        try:
            set_section_status(status_doc, section_id, "READY", attempts=cur_attempts)
            atomic_write_json(status_path, status_doc)
        except KeyError:
            pass

    _out({
        "status": "READY",
        "section_id": section_id,
        "blocks": len(candidate.get("blocks", [])),
        "ledger_entries": len(candidate.get("requirement_response_ledger", [])),
        "warnings": validation["warnings"],
        "markdown": f"generated_sections/{section_id}.md",
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
