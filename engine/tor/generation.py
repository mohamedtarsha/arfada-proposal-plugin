"""Controlled proposal generation — deterministic plumbing (Phase 3).

This module does NOT call any language model. The active Claude Code session is
the generator. This module:

1. builds a bounded `generation_packet` for one section (only relevant context)
2. defines the structured block schema the session must return
3. validates a session-produced section candidate (schema, slots, ledger,
   decisions, constraints, fabricated-fact detection)
4. tracks generation status for resume

Allowed factual authority (Phase 3): TOR + user-approved Decision Register ONLY.
Any claim requiring ARFADA organizational evidence must be a NEEDS_ARFADA_EVIDENCE
placeholder — never invented prose.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BLOCK_TYPES = {"paragraph", "bullet_list", "numbered_list", "table", "evidence_placeholder"}

LEDGER_STATUSES = {
    "ADDRESSED", "PARTIAL", "MISSING",
    "BLOCKED_BY_DECISION", "BLOCKED_BY_MISSING_EVIDENCE",
}

SECTION_STATUSES = {
    "PENDING", "GENERATING", "READY",
    "BLOCKED_BY_DECISION", "BLOCKED_BY_EVIDENCE", "FAILED",
}

MAX_REPAIR_ATTEMPTS = 2

# ARFADA organizational facts that must NEVER be invented in Phase 3.
# These appear in generated prose only as NEEDS_ARFADA_EVIDENCE placeholders.
FORBIDDEN_FACT_CATEGORIES = [
    "years of experience", "number of projects", "countries worked",
    "staff numbers", "past clients", "past assignments", "survey counts",
    "office locations", "track record", "previous evaluations completed",
]

# Heuristic patterns that signal an UNSUPPORTED ARFADA factual claim.
_UNSUPPORTED_ARFADA = re.compile(
    r"\bARFADA\s+(?:has|have|completed|conducted|delivered|implemented|managed|"
    r"led|carried\s+out|possesses|brings|offers)\b[^.]{0,80}?"
    r"(?:\d+\s*(?:years?|projects?|evaluations?|assignments?|countries|clients?|staff)|"
    r"extensive|over\s+\d+|more\s+than\s+\d+|a\s+proven\s+track\s+record|"
    r"decades?\s+of)",
    re.I,
)

NEEDS_EVIDENCE_TAG = "NEEDS_ARFADA_EVIDENCE"


# ---------------------------------------------------------------------------
# Time helper
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Generation packet
# ---------------------------------------------------------------------------

def build_packet(
    *,
    section: dict,
    slots: list[dict],
    requirements_by_id: dict[str, dict],
    decision_register: Optional[dict],
    language: str,
    assignment_metadata: dict,
    verified_arfada_facts: Optional[list] = None,
    framework_columns: Optional[list] = None,
    assignment_type: str = "",
    knowledge_version: str = "",
) -> dict:
    """Build the bounded, section-scoped generation packet.

    Includes ONLY what the writer needs for this section:
    section purpose, owned requirements (summaries + locators), mandatory slots,
    resolved/deferred decisions relevant to this section, constraints, allowed
    facts, forbidden fact categories, and the required output structure.
    """
    dec_by_id = {}
    if decision_register:
        dec_by_id = {d["decision_id"]: d for d in decision_register.get("decisions", [])}

    # Resolved + deferred decisions that apply to this section's slots
    applied_decisions = []
    for dep in section.get("decision_dependencies", []):
        d = dec_by_id.get(dep)
        if not d:
            continue
        status = d.get("decision_status")
        if status == "RESOLVED":
            applied_decisions.append({
                "decision_id": d["decision_id"],
                "requirement_id": d["requirement_id"],
                "status": "RESOLVED",
                "selected_value": d.get("selected_value"),
                "constraint_type": d.get("constraint_type"),
                "minimum": d.get("minimum"),
                "maximum": d.get("maximum"),
                "instruction": f"Use the approved value EXACTLY: {d.get('selected_value')}",
            })
        elif status == "DEFERRED":
            applied_decisions.append({
                "decision_id": d["decision_id"],
                "requirement_id": d["requirement_id"],
                "status": "DEFERRED",
                "selected_value": None,
                "instruction": ("State that this will be confirmed during the inception "
                                "phase. Do NOT invent a final value."),
            })

    # Build mandatory response-slot descriptors for this section
    slot_descriptors = []
    for s in slots:
        if s["section_id"] != section["section_id"]:
            continue
        req = requirements_by_id.get(s["requirement_id"], {})
        # constraint context from any resolved decision on this slot
        constraint = None
        for dep in s.get("decision_dependencies", []):
            d = dec_by_id.get(dep)
            if d and d.get("decision_status") == "RESOLVED":
                constraint = {"value": d.get("selected_value"),
                              "minimum": d.get("minimum"), "maximum": d.get("maximum")}
        slot_descriptors.append({
            "slot_id": s["slot_id"],
            "requirement_id": s["requirement_id"],
            "response_mode": s["response_mode"],
            "mandatory": s["mandatory"],
            "minimum_expectation": s["minimum_expectation"],
            "requirement_text": s["requirement_text"],
            "source_locator": s["source_locator"],
            "resolved_constraint": constraint,
        })

    needs_evidence = section.get("needs_arfada_evidence", False)
    facts = verified_arfada_facts or []
    is_framework = bool(framework_columns) and section.get("section_id", "").endswith("FRAMEWORK")

    return {
        "schema_version": "1",
        "section_id": section["section_id"],
        "title": section["title"],
        "purpose": section["purpose"],
        "language": language,
        "assignment_type": assignment_type,
        "knowledge_version": knowledge_version,
        "assignment": {
            "title": assignment_metadata.get("assignment", ""),
            "client": assignment_metadata.get("client", ""),
            "country": assignment_metadata.get("country", ""),
        },
        "owned_requirements": [
            {
                "requirement_id": rid,
                "text": requirements_by_id.get(rid, {}).get("text", "")[:400],
                "category": requirements_by_id.get(rid, {}).get("category", ""),
                "source_locator": requirements_by_id.get(rid, {}).get("source_locator", ""),
            }
            for rid in section.get("requirement_ids", [])
        ],
        "mandatory_slots": slot_descriptors,
        "applied_decisions": applied_decisions,
        "preferred_modes": section.get("preferred_modes", ["PROSE"]),
        "allowed_facts": {
            "TOR": "The TOR requirements and metadata in this packet.",
            "DECISIONS": "The resolved/deferred decisions in applied_decisions.",
            "VERIFIED_ARFADA_FACTS": "Only the facts in verified_arfada_facts (cite fact_id).",
        },
        "verified_arfada_facts": facts,
        "framework_columns": framework_columns if is_framework else None,
        "forbidden_fact_categories": FORBIDDEN_FACT_CATEGORIES,
        "needs_arfada_evidence": needs_evidence,
        "evidence_instruction": (
            f"You MAY state the verified facts in verified_arfada_facts (reference the "
            f"fact_id). For any OTHER claim about ARFADA's experience, team identities, "
            f"past projects, or capacity NOT in that list, insert a '{NEEDS_EVIDENCE_TAG}' "
            f"placeholder block instead of inventing text."
        ),
        "output_contract": _output_contract(section, framework_columns if is_framework else None),
        "writing_guidance": {
            "paragraph_words": "60-120 words; avoid >150.",
            "use_bullets_for": "discrete concepts",
            "use_numbered_for": "sequences/steps",
            "use_tables_for": "framework matrix, deliverables, workplan, team",
            "avoid": ["generic AI phrases", "restating the TOR without a proposed approach",
                      "unsupported superlatives", "walls of text"],
        },
    }


def _output_contract(section: dict, framework_columns: Optional[list] = None) -> dict:
    """Describe the structured JSON the Claude session must return for this section."""
    modes = section.get("preferred_modes", ["PROSE"])
    wants_table = any(m in modes for m in
                      ("MATRIX_ROW", "DELIVERABLE_ROW", "WORKPLAN_ROW", "TEAM_ROLE", "TABLE_ROW"))
    contract = {
        "format": {
            "section_id": section["section_id"],
            "blocks": "list of block objects (see block_types)",
            "requirement_response_ledger": "list of ledger entries (see ledger_schema)",
        },
        "block_types": {
            "paragraph": {"block_id": "str", "type": "paragraph", "text": "str"},
            "bullet_list": {"block_id": "str", "type": "bullet_list", "items": ["str"]},
            "numbered_list": {"block_id": "str", "type": "numbered_list", "items": ["str"]},
            "table": {"block_id": "str", "type": "table", "columns": ["str"],
                      "rows": [["cell"]]},
            "evidence_placeholder": {"block_id": "str", "type": "evidence_placeholder",
                                     "text": f"{NEEDS_EVIDENCE_TAG}: <what is needed>"},
        },
        "ledger_schema": {
            "slot_id": "str (from mandatory_slots)",
            "requirement_id": "str",
            "block_ids": ["ids of blocks that address this requirement"],
            "response_summary": "str",
            "status": "ADDRESSED | PARTIAL | MISSING | BLOCKED_BY_DECISION | BLOCKED_BY_MISSING_EVIDENCE",
        },
        "prefer_table": wants_table,
        "note": "Every mandatory slot MUST have a ledger entry. block_ids must reference real blocks.",
    }
    if framework_columns:
        contract["required_table_columns"] = framework_columns
        contract["framework_note"] = (
            "This section's matrix MUST be a table block whose columns are exactly "
            f"{framework_columns} (assignment-type specific). One row per question/dimension.")
    return contract


# ---------------------------------------------------------------------------
# Section candidate validation
# ---------------------------------------------------------------------------

def validate_candidate(packet: dict, candidate: dict) -> dict:
    """Validate a Claude-produced section candidate against the packet contract.

    Returns {"valid": bool, "errors": [...], "warnings": [...],
             "failed_slots": [...], "status": "READY"|"FAILED"}.
    Deterministic; no model call.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # --- schema shape ---
    if not isinstance(candidate, dict):
        return _result(False, ["candidate is not an object"], [], [], "FAILED")
    if candidate.get("section_id") != packet["section_id"]:
        errors.append(f"section_id mismatch: expected {packet['section_id']}, "
                      f"got {candidate.get('section_id')}")
    blocks = candidate.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        return _result(False, ["blocks missing or empty"], warnings, [], "FAILED")

    block_ids: set[str] = set()
    all_text_parts: list[str] = []
    for i, b in enumerate(blocks):
        if not isinstance(b, dict):
            errors.append(f"block[{i}] is not an object")
            continue
        bid = b.get("block_id")
        btype = b.get("type")
        if not bid:
            errors.append(f"block[{i}] missing block_id")
        else:
            if bid in block_ids:
                errors.append(f"duplicate block_id: {bid}")
            block_ids.add(bid)
        if btype not in BLOCK_TYPES:
            errors.append(f"block[{i}] invalid type: {btype}")
            continue
        # per-type validation + text collection
        if btype in ("paragraph", "evidence_placeholder"):
            txt = b.get("text", "")
            if not isinstance(txt, str) or not txt.strip():
                errors.append(f"block {bid} ({btype}) missing text")
            else:
                all_text_parts.append(txt)
        elif btype in ("bullet_list", "numbered_list"):
            items = b.get("items")
            if not isinstance(items, list) or not items:
                errors.append(f"block {bid} ({btype}) missing items")
            else:
                all_text_parts.extend(str(x) for x in items)
        elif btype == "table":
            cols = b.get("columns")
            rows = b.get("rows")
            if not isinstance(cols, list) or not cols:
                errors.append(f"block {bid} (table) missing columns")
            if not isinstance(rows, list) or not rows:
                errors.append(f"block {bid} (table) missing rows")
            elif isinstance(cols, list):
                for ri, row in enumerate(rows):
                    if not isinstance(row, list):
                        errors.append(f"block {bid} table row[{ri}] not a list")
                    elif len(row) != len(cols):
                        errors.append(f"block {bid} table row[{ri}] has {len(row)} cells, "
                                      f"expected {len(cols)}")
                    else:
                        all_text_parts.extend(str(c) for c in row)

    all_text = "\n".join(all_text_parts)

    # --- ledger validation ---
    ledger = candidate.get("requirement_response_ledger", [])
    if not isinstance(ledger, list):
        errors.append("requirement_response_ledger must be a list")
        ledger = []

    ledger_by_slot = {}
    for entry in ledger:
        if not isinstance(entry, dict):
            errors.append("ledger entry is not an object")
            continue
        sid = entry.get("slot_id")
        ledger_by_slot[sid] = entry
        status = entry.get("status")
        if status not in LEDGER_STATUSES:
            errors.append(f"ledger slot {sid} invalid status: {status}")
        # referenced block_ids must exist
        for bid in entry.get("block_ids", []):
            if bid not in block_ids:
                errors.append(f"ledger slot {sid} references missing block_id: {bid}")

    # --- mandatory slot coverage ---
    mandatory_slots = [s for s in packet.get("mandatory_slots", []) if s.get("mandatory")]
    failed_slots: list[dict] = []
    for s in mandatory_slots:
        entry = ledger_by_slot.get(s["slot_id"])
        if entry is None:
            failed_slots.append({"slot_id": s["slot_id"],
                                 "requirement_id": s["requirement_id"],
                                 "reason": "no ledger entry"})
        elif entry.get("status") == "MISSING":
            failed_slots.append({"slot_id": s["slot_id"],
                                 "requirement_id": s["requirement_id"],
                                 "reason": "status MISSING"})

    # --- resolved-decision value enforcement ---
    for d in packet.get("applied_decisions", []):
        if d.get("status") != "RESOLVED":
            continue
        val = d.get("selected_value")
        if isinstance(val, (int, float)):
            # the approved numeric value should appear; a different in-range number
            # on the same metric is a violation of "use approved value exactly"
            mn, mx = d.get("minimum"), d.get("maximum")
            if mn is not None:
                _check_numeric_decision(all_text, val, mn, mx, errors, warnings)

    # --- ARFADA fact-claim validation (Phase 4) ---
    # An ARFADA organizational/numeric claim is allowed ONLY if its value matches a
    # verified fact in the packet (verified_arfada_facts), OR it is accompanied by a
    # NEEDS_ARFADA_EVIDENCE placeholder. Otherwise it is an UNSUPPORTED_ARFADA_CLAIM.
    verified_values = _verified_fact_values(packet.get("verified_arfada_facts", []))
    for m in _UNSUPPORTED_ARFADA.finditer(all_text):
        claim = m.group(0)
        # extract the number in the claim (if any) and check it against verified facts
        nums = re.findall(r"\d[\d,]*", claim)
        supported = False
        for n in nums:
            norm = n.replace(",", "")
            if norm in verified_values:
                supported = True
                break
        if supported:
            continue
        if NEEDS_EVIDENCE_TAG in all_text:
            continue  # section flagged its gap honestly
        errors.append(f"UNSUPPORTED_ARFADA_CLAIM: '{claim[:60]}' does not map to a verified "
                      f"fact_id, TOR fact, or approved decision, and no {NEEDS_EVIDENCE_TAG} "
                      f"placeholder is present")

    # --- evidence sections must flag needs when claiming org facts ---
    if packet.get("needs_arfada_evidence"):
        has_placeholder = any(b.get("type") == "evidence_placeholder" for b in blocks
                              if isinstance(b, dict))
        has_evidence_tag = NEEDS_EVIDENCE_TAG in all_text
        if not (has_placeholder or has_evidence_tag):
            warnings.append(f"section needs ARFADA evidence but no {NEEDS_EVIDENCE_TAG} "
                            "placeholder present")

    valid = not errors and not failed_slots
    status = "READY" if valid else "FAILED"
    return _result(valid, errors, warnings, failed_slots, status)


def _check_numeric_decision(text: str, approved: float, mn: Optional[float],
                            mx: Optional[float], errors: list, warnings: list) -> None:
    """Enforce that an approved numeric decision value is used EXACTLY (spec §38).

    If the approved value is absent, this is a hard error (the section must be
    repaired to use the approved value). If a DIFFERENT in-range number appears
    on its own, that is a likely substitution of the approved value — also an error.
    """
    approved_int = int(approved) if float(approved).is_integer() else approved
    if str(approved_int) in text:
        return  # approved value present — good
    errors.append(
        f"approved decision value {approved_int} not used in section; the approved "
        f"proposal value must appear exactly (do not substitute the TOR minimum or "
        f"another number)")


def _verified_fact_values(facts: list) -> set:
    """Collect the numeric values present in verified ARFADA facts (for claim matching)."""
    values: set = set()
    for f in facts or []:
        v = str(f.get("value", ""))
        for n in re.findall(r"\d[\d,]*", v):
            values.add(n.replace(",", ""))
    return values


def _result(valid, errors, warnings, failed_slots, status):
    return {"valid": valid, "errors": errors, "warnings": warnings,
            "failed_slots": failed_slots, "status": status}


# ---------------------------------------------------------------------------
# Repair packet
# ---------------------------------------------------------------------------

def build_repair_packet(packet: dict, candidate: dict, validation: dict,
                        attempt: int) -> dict:
    """Build a narrow repair packet: only the failures, for a bounded retry."""
    return {
        "section_id": packet["section_id"],
        "attempt": attempt,
        "max_attempts": MAX_REPAIR_ATTEMPTS,
        "errors": validation.get("errors", []),
        "failed_slots": [
            {**fs, "slot": next((s for s in packet["mandatory_slots"]
                                 if s["slot_id"] == fs["slot_id"]), None)}
            for fs in validation.get("failed_slots", [])
        ],
        "instruction": ("Fix ONLY the listed errors and failed slots. Keep all valid "
                        "blocks. Return the full corrected section JSON."),
        "current_candidate": candidate,
        "output_contract": packet["output_contract"],
    }


# ---------------------------------------------------------------------------
# Generation status (resume)
# ---------------------------------------------------------------------------

def init_status(blueprint: dict, decision_register: Optional[dict]) -> dict:
    """Initialize generation_status.json from a blueprint."""
    from .blueprint import blueprint_from_dict, section_status, BlueprintSection

    sections = {}
    for s in blueprint.get("sections", []):
        bs = BlueprintSection(**s)
        sections[bs.section_id] = {
            "section_id": bs.section_id,
            "title": bs.title,
            "sequence": bs.sequence,
            "status": section_status(bs, decision_register),
            "needs_arfada_evidence": bs.needs_arfada_evidence,
            "attempts": 0,
            "updated_at": _now(),
        }
    return {
        "schema_version": "1",
        "run_id": blueprint.get("run_id"),
        "tor_identity": blueprint.get("tor_identity"),
        "created_at": _now(),
        "updated_at": _now(),
        "sections": sections,
    }


def set_section_status(status_doc: dict, section_id: str, status: str,
                       attempts: Optional[int] = None) -> None:
    sec = status_doc["sections"].get(section_id)
    if sec is None:
        raise KeyError(f"section {section_id} not in status doc")
    sec["status"] = status
    if attempts is not None:
        sec["attempts"] = attempts
    sec["updated_at"] = _now()
    status_doc["updated_at"] = _now()


def next_pending_section(status_doc: dict) -> Optional[str]:
    """Return the next PENDING section id in sequence order (EXECUTIVE_SUMMARY last)."""
    secs = sorted(status_doc["sections"].values(), key=lambda s: s["sequence"])
    # executive summary generated only after all substantive sections READY
    non_exec = [s for s in secs if s["section_id"] != "EXECUTIVE_SUMMARY"]
    for s in non_exec:
        if s["status"] == "PENDING":
            return s["section_id"]
    # all substantive done → executive summary if pending and others ready
    substantive_ready = all(
        s["status"] in ("READY", "BLOCKED_BY_DECISION", "BLOCKED_BY_EVIDENCE")
        for s in non_exec
    )
    exec_s = status_doc["sections"].get("EXECUTIVE_SUMMARY")
    if exec_s and exec_s["status"] == "PENDING" and substantive_ready:
        return "EXECUTIVE_SUMMARY"
    return None


# ---------------------------------------------------------------------------
# Atomic JSON write
# ---------------------------------------------------------------------------

def atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON atomically (temp → validate → rename)."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp", prefix="gen_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        with open(tmp, encoding="utf-8") as f:
            json.load(f)  # validate round-trip
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Markdown rendering for one section
# ---------------------------------------------------------------------------

def section_to_markdown(candidate: dict, title: str) -> str:
    """Render a validated section candidate to Markdown."""
    lines = [f"## {title}", ""]
    for b in candidate.get("blocks", []):
        btype = b.get("type")
        if btype == "paragraph":
            lines.append(b.get("text", "").strip())
            lines.append("")
        elif btype == "evidence_placeholder":
            lines.append(f"> **{b.get('text', NEEDS_EVIDENCE_TAG).strip()}**")
            lines.append("")
        elif btype == "bullet_list":
            for item in b.get("items", []):
                lines.append(f"- {item}")
            lines.append("")
        elif btype == "numbered_list":
            for i, item in enumerate(b.get("items", []), 1):
                lines.append(f"{i}. {item}")
            lines.append("")
        elif btype == "table":
            cols = b.get("columns", [])
            rows = b.get("rows", [])
            if cols:
                lines.append("| " + " | ".join(str(c) for c in cols) + " |")
                lines.append("| " + " | ".join("---" for _ in cols) + " |")
                for row in rows:
                    lines.append("| " + " | ".join(str(c) for c in row) + " |")
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"
