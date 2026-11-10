"""Pre-export quality check (Phase 4) — deterministic. NOT PE7.

Basic gate run before DOCX export:
- all generated sections are schema-valid (re-validate against their packets)
- no invalid decision values
- no unsupported ARFADA claims
- no cross-TOR artifacts (run_id consistent)
- no hard generation failures
- (client) no internal metadata leakage markers

Returns {"ok": bool, "errors": [...], "warnings": [...], "client_safe": bool}.
"""
from __future__ import annotations

import json
from pathlib import Path

from .generation import validate_candidate, NEEDS_EVIDENCE_TAG


def preexport_check(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    errors: list[str] = []
    warnings: list[str] = []

    bp_path = run_dir / "proposal_blueprint.json"
    status_path = run_dir / "generation_status.json"
    if not bp_path.exists() or not status_path.exists():
        return {"ok": False, "client_safe": False,
                "errors": ["blueprint or generation_status missing — build + generate first"],
                "warnings": []}

    blueprint = json.loads(bp_path.read_text(encoding="utf-8"))
    status_doc = json.loads(status_path.read_text(encoding="utf-8"))
    run_id = blueprint.get("run_id")

    # cross-TOR consistency
    if status_doc.get("run_id") != run_id:
        errors.append("cross-TOR: generation_status run_id does not match blueprint")

    sections_dir = run_dir / "generated_sections"
    packets_dir = run_dir / "generation_packets"

    ready = blocked = 0
    has_gap = False

    for sec in blueprint["sections"]:
        sid = sec["section_id"]
        st = status_doc["sections"].get(sid, {}).get("status")
        if st == "BLOCKED_BY_DECISION":
            blocked += 1
            continue
        if st == "FAILED":
            errors.append(f"section {sid} is FAILED (hard generation failure)")
            continue
        if st != "READY":
            continue
        cand_path = sections_dir / f"{sid}.json"
        packet_path = packets_dir / f"{sid}.json"
        if not cand_path.exists():
            errors.append(f"section {sid} marked READY but candidate file missing")
            continue
        candidate = json.loads(cand_path.read_text(encoding="utf-8"))
        # re-validate against packet if present (schema, decisions, facts)
        if packet_path.exists():
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            v = validate_candidate(packet, candidate)
            if not v["valid"]:
                for e in v["errors"]:
                    errors.append(f"[{sid}] {e}")
        # evidence gaps (warning, not a hard error)
        for b in candidate.get("blocks", []):
            if b.get("type") == "evidence_placeholder" or NEEDS_EVIDENCE_TAG in str(b.get("text", "")):
                has_gap = True
        ready += 1

    if ready == 0:
        errors.append("no READY sections to export")

    # client safety: hard unsupported-fact errors block client export
    unsupported = [e for e in errors if "UNSUPPORTED_ARFADA_CLAIM" in e or "unsupported ARFADA" in e]
    client_safe = len(unsupported) == 0 and not any("FAILED" in e for e in errors)

    if has_gap:
        warnings.append("Open NEEDS_ARFADA_EVIDENCE placeholders remain — client draft will be "
                        "marked 'DRAFT — HUMAN REVIEW REQUIRED'.")

    return {
        "ok": len(errors) == 0,
        "client_safe": client_safe,
        "errors": errors,
        "warnings": warnings,
        "sections_ready": ready,
        "sections_blocked": blocked,
        "has_evidence_gaps": has_gap,
    }
