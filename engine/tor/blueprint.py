"""Proposal Blueprint — deterministic section architecture (Phase 3).

Plugin-native equivalent of the validated PE5-A blueprint lineage, simplified
for the plugin: no K3, no PE3 research, no PE4 exemplars, no word budgets.

Builds, from the TOR analysis + requirements + decision register:
- an assignment-aware ordered section set (only sections justified by the TOR)
- requirement ownership (each bidder requirement → exactly ONE owning section)
- response slots (one per owned bidder requirement, with a response mode)
- decision dependencies (which decisions each section depends on)

No LLM. No network. Pure deterministic Python.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Section taxonomy + ordering (from PE5-A lineage, trimmed to plugin scope)
# ---------------------------------------------------------------------------

SECTION_ORDER = [
    "EXECUTIVE_SUMMARY", "UNDERSTANDING", "CONTEXT", "OBJECTIVES", "METHODOLOGY",
    "EVALUATION_FRAMEWORK", "SAMPLING", "DATA_COLLECTION", "DATA_ANALYSIS",
    "QUALITY_ASSURANCE", "ETHICS", "WORKPLAN", "DELIVERABLES", "TEAM",
    "EXPERIENCE", "SUBMISSION",
]
_ORDER_IX = {k: i for i, k in enumerate(SECTION_ORDER)}

SECTION_TITLE = {
    "EXECUTIVE_SUMMARY": "Executive Summary",
    "UNDERSTANDING": "Understanding of the Assignment",
    "CONTEXT": "Context and Background",
    "OBJECTIVES": "Objectives and Scope",
    "METHODOLOGY": "Methodology and Approach",
    "EVALUATION_FRAMEWORK": "Evaluation Framework",
    "SAMPLING": "Sampling Strategy",
    "DATA_COLLECTION": "Data Collection",
    "DATA_ANALYSIS": "Data Analysis",
    "QUALITY_ASSURANCE": "Quality Assurance",
    "ETHICS": "Ethics and Safeguarding",
    "WORKPLAN": "Work Plan and Timeline",
    "DELIVERABLES": "Deliverables",
    "TEAM": "Team and Personnel",
    "EXPERIENCE": "Organizational Experience",
    "SUBMISSION": "Submission and Compliance",
}

SECTION_PURPOSE = {
    "EXECUTIVE_SUMMARY": "Summarize the proposal: understanding, approach, and value. Written LAST.",
    "UNDERSTANDING": "Demonstrate understanding of the assignment and what the client needs.",
    "CONTEXT": "Explain the operating context relevant to delivering the assignment.",
    "OBJECTIVES": "State the objectives and scope the proposal addresses.",
    "METHODOLOGY": "Describe the proposed methodology and overall approach.",
    "EVALUATION_FRAMEWORK": "Map evaluation questions to methods, sources, and analysis (matrix).",
    "SAMPLING": "Describe the sampling strategy and sample composition.",
    "DATA_COLLECTION": "Describe data collection methods and tools.",
    "DATA_ANALYSIS": "Describe how data will be analyzed and integrated.",
    "QUALITY_ASSURANCE": "Describe quality controls over the assignment.",
    "ETHICS": "Describe ethics and safeguarding measures.",
    "WORKPLAN": "Present the work plan, phases, and timeline.",
    "DELIVERABLES": "List deliverables with scope and timing.",
    "TEAM": "Present the proposed team and roles.",
    "EXPERIENCE": "Present relevant organizational experience and capacity.",
    "SUBMISSION": "Address submission and compliance requirements.",
}

# Requirement category → the single owning section (no double-count).
CATEGORY_SECTION = {
    "evaluation_questions": "EVALUATION_FRAMEWORK",
    "methodology": "METHODOLOGY",
    "data_collection_methods": "DATA_COLLECTION",
    "team": "TEAM",
    "deliverable": "DELIVERABLES",
    "submission": "SUBMISSION",
    "sampling": "SAMPLING",
    "scope": "OBJECTIVES",
    "ethics": "ETHICS",
    "timeline": "WORKPLAN",
    "eligibility": "EXPERIENCE",
    "proposal_format": "SUBMISSION",
    "general": "UNDERSTANDING",
    "needs_review": "UNDERSTANDING",
}

# TOR field_key (found metadata) → a section it justifies as TOR_EXPLICIT.
FIELD_SECTION = {
    "objectives": "OBJECTIVES", "scope": "OBJECTIVES", "background": "CONTEXT",
    "required_methodology": "METHODOLOGY", "data_collection_methods": "DATA_COLLECTION",
    "sampling_requirements": "SAMPLING", "ethics_safeguarding": "ETHICS",
    "team_requirements": "TEAM", "evaluation_questions": "EVALUATION_FRAMEWORK",
    "deliverables": "DELIVERABLES", "timeline": "WORKPLAN",
    "submission_requirements": "SUBMISSION",
}

# Sections always present (system scaffold).
_SYSTEM_SECTIONS = ["EXECUTIVE_SUMMARY", "UNDERSTANDING"]

# Default response mode per category (block type the writer should prefer).
CATEGORY_RESPONSE_MODE = {
    "evaluation_questions": "MATRIX_ROW",
    "deliverable": "DELIVERABLE_ROW",
    "timeline": "WORKPLAN_ROW",
    "team": "TEAM_ROLE",
    "submission": "SUBMISSION_ITEM",
    "proposal_format": "COMPLIANCE_ITEM",
    "eligibility": "COMPLIANCE_ITEM",
    "sampling": "PROSE",
    "methodology": "PROSE",
    "data_collection_methods": "PROSE",
    "ethics": "BULLET_LIST",
    "scope": "PROSE",
    "general": "PROSE",
    "needs_review": "PROSE",
}

# Sections whose owned requirements usually need ARFADA organizational evidence
# that the plugin does not yet have (Phase 3 → placeholders, never invented).
_EVIDENCE_SECTIONS = {"TEAM", "EXPERIENCE"}

# Decision types that represent an open human decision (create a slot dependency).
_OPEN_DECISION_TYPES = {"OPEN_PROPOSAL_DECISION", "DEFERRED_DECISION", "OPTIONAL_CHOICE"}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ResponseSlot:
    slot_id: str
    requirement_id: str
    section_id: str          # section KEY (e.g. METHODOLOGY)
    response_mode: str       # PROSE | BULLET_LIST | ... | TABLE_ROW
    mandatory: bool
    minimum_expectation: str
    decision_dependencies: list[str]  # decision_ids this slot depends on
    source_locator: str
    requirement_text: str


@dataclass
class BlueprintSection:
    section_id: str          # section KEY
    title: str
    purpose: str
    sequence: int
    origin: str              # TOR_EXPLICIT | COMPLIANCE_REQUIRED | SYSTEM_REQUIRED
    required: bool
    requirement_ids: list[str]
    mandatory_requirement_ids: list[str]
    slot_ids: list[str]
    decision_dependencies: list[str]
    preferred_modes: list[str]
    needs_arfada_evidence: bool


@dataclass
class ProposalBlueprint:
    schema_version: str
    run_id: str
    tor_identity: str
    assignment_type: str
    language: str
    created_at: str
    sections: list[BlueprintSection]
    slots: list[ResponseSlot]
    coverage: dict


# ---------------------------------------------------------------------------
# ID helpers
# ---------------------------------------------------------------------------

def _slot_id(req_id: str) -> str:
    return "slot_" + hashlib.sha1(req_id.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Blueprint construction
# ---------------------------------------------------------------------------

def build_blueprint(
    *,
    run_id: str,
    tor_identity: str,
    assignment_type: str,
    language: str,
    created_at: str,
    requirements: list[dict],
    fields_found: list[str],
    decision_register: Optional[dict] = None,
) -> ProposalBlueprint:
    """Deterministically build the proposal blueprint.

    `requirements`   : enriched requirements from requirements.json
    `fields_found`   : list of field_key strings present in metadata
    `decision_register` : loaded decision_register.json (or None)
    """
    # --- map requirement_id → decision_ids (from register) ---
    req_to_decisions: dict[str, list[dict]] = {}
    if decision_register:
        for d in decision_register.get("decisions", []):
            req_to_decisions.setdefault(d["requirement_id"], []).append(d)

    # --- determine which sections exist + origin ---
    origin: dict[str, str] = {}
    required_map: dict[str, bool] = {}

    rank = {"TOR_EXPLICIT": 3, "COMPLIANCE_REQUIRED": 2, "SYSTEM_REQUIRED": 0}

    def _mark(key: str, org: str, req: bool):
        if key not in origin or rank[org] > rank[origin[key]]:
            origin[key] = org
        required_map[key] = required_map.get(key, False) or req

    for k in _SYSTEM_SECTIONS:
        _mark(k, "SYSTEM_REQUIRED", True)

    # TOR fields → explicit sections
    for fk in fields_found:
        sec = FIELD_SECTION.get(fk)
        if sec:
            _mark(sec, "TOR_EXPLICIT", True)

    # --- route requirements to owning sections (bidder obligations only) ---
    # Each bidder requirement is owned by exactly one section.
    section_reqs: dict[str, list[dict]] = {}
    slots: list[ResponseSlot] = []

    for r in requirements:
        # Only bidder-facing obligations produce response slots.
        if r.get("actor") == "CLIENT":
            continue
        cat = r.get("category", "general")
        sec = CATEGORY_SECTION.get(cat, "UNDERSTANDING")
        org = "COMPLIANCE_REQUIRED" if cat in ("submission", "proposal_format", "eligibility") \
            else "TOR_EXPLICIT"
        _mark(sec, org, True)
        section_reqs.setdefault(sec, []).append(r)

        # build a response slot for this requirement.
        # Decision register entries carry decision_type (not is_human_decision);
        # OPEN-type decisions are the ones that create a slot dependency.
        decs = req_to_decisions.get(r["req_id"], [])
        dec_ids = [d["decision_id"] for d in decs
                   if d.get("is_human_decision")
                   or d.get("decision_type") in _OPEN_DECISION_TYPES]
        slots.append(ResponseSlot(
            slot_id=_slot_id(r["req_id"]),
            requirement_id=r["req_id"],
            section_id=sec,
            response_mode=CATEGORY_RESPONSE_MODE.get(cat, "PROSE"),
            mandatory=bool(r.get("mandatory", True)),
            minimum_expectation=_minimum_expectation(cat),
            decision_dependencies=dec_ids,
            source_locator=r.get("source_locator") or "",
            requirement_text=r.get("text", "")[:500],
        ))

    # CONTEXT is implied whenever UNDERSTANDING exists and there is background
    if "background" in fields_found:
        _mark("CONTEXT", "TOR_EXPLICIT", True)

    # --- assemble ordered sections ---
    slot_by_section: dict[str, list[ResponseSlot]] = {}
    for s in slots:
        slot_by_section.setdefault(s.section_id, []).append(s)

    sections: list[BlueprintSection] = []
    present_keys = sorted(origin.keys(), key=lambda k: _ORDER_IX.get(k, 999))

    for key in present_keys:
        reqs = section_reqs.get(key, [])
        sec_slots = slot_by_section.get(key, [])
        mand_ids = [r["req_id"] for r in reqs if r.get("mandatory", True)]
        dec_deps = sorted({dep for s in sec_slots for dep in s.decision_dependencies})
        modes = sorted({s.response_mode for s in sec_slots}) or ["PROSE"]
        sections.append(BlueprintSection(
            section_id=key,
            title=SECTION_TITLE.get(key, key.title()),
            purpose=SECTION_PURPOSE.get(key, ""),
            sequence=_ORDER_IX.get(key, 999),
            origin=origin[key],
            required=required_map.get(key, False),
            requirement_ids=[r["req_id"] for r in reqs],
            mandatory_requirement_ids=mand_ids,
            slot_ids=[s.slot_id for s in sec_slots],
            decision_dependencies=dec_deps,
            preferred_modes=modes,
            needs_arfada_evidence=(key in _EVIDENCE_SECTIONS),
        ))

    # --- coverage summary ---
    total_bidder = sum(1 for r in requirements if r.get("actor") != "CLIENT")
    mandatory_bidder = sum(1 for r in requirements
                           if r.get("actor") != "CLIENT" and r.get("mandatory", True))
    open_decisions = 0
    if decision_register:
        open_decisions = sum(
            1 for d in decision_register.get("decisions", [])
            if d.get("decision_status") in ("OPEN", "SKIPPED", "UNRESOLVED", "RECOMMENDATION")
        )
    coverage = {
        "sections": len(sections),
        "total_bidder_requirements": total_bidder,
        "mandatory_bidder_requirements": mandatory_bidder,
        "response_slots": len(slots),
        "open_decisions": open_decisions,
        "sections_blocked_by_decisions": sum(
            1 for s in sections if _is_blocked(s, decision_register)
        ),
        "sections_needing_evidence": sum(1 for s in sections if s.needs_arfada_evidence),
    }

    return ProposalBlueprint(
        schema_version="1",
        run_id=run_id,
        tor_identity=tor_identity,
        assignment_type=assignment_type,
        language=language,
        created_at=created_at,
        sections=sections,
        slots=slots,
        coverage=coverage,
    )


def _minimum_expectation(category: str) -> str:
    return {
        "methodology": "Describe the proposed approach, not just restate the requirement.",
        "data_collection_methods": "Explain purpose, respondents (if TOR-supported), and integration.",
        "sampling": "Describe sampling approach and composition respecting TOR constraints.",
        "evaluation_questions": "Map each question to method, source, and analysis.",
        "deliverable": "State deliverable, scope, and TOR-fixed timing.",
        "timeline": "Present phases/timing within TOR constraints.",
        "team": "State role and responsibility (identities need ARFADA evidence).",
        "submission": "Confirm compliance with the submission requirement.",
        "ethics": "State the ethics/safeguarding measure.",
    }.get(category, "Provide a substantive, TOR-grounded response.")


def _is_blocked(section: BlueprintSection, register: Optional[dict]) -> bool:
    """A section is blocked if any dependent decision is OPEN/SKIPPED/UNRESOLVED."""
    if not register or not section.decision_dependencies:
        return False
    status_by_id = {d["decision_id"]: d.get("decision_status")
                    for d in register.get("decisions", [])}
    for dep in section.decision_dependencies:
        if status_by_id.get(dep) in ("OPEN", "SKIPPED", "UNRESOLVED", "RECOMMENDATION", None):
            return True
    return False


def section_status(section: BlueprintSection, register: Optional[dict]) -> str:
    """Return the generation eligibility status for a section."""
    if _is_blocked(section, register):
        return "BLOCKED_BY_DECISION"
    return "PENDING"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def blueprint_to_dict(bp: ProposalBlueprint) -> dict:
    return {
        "schema_version": bp.schema_version,
        "run_id": bp.run_id,
        "tor_identity": bp.tor_identity,
        "assignment_type": bp.assignment_type,
        "language": bp.language,
        "created_at": bp.created_at,
        "coverage": bp.coverage,
        "sections": [asdict(s) for s in bp.sections],
        "slots": [asdict(s) for s in bp.slots],
    }


def blueprint_from_dict(d: dict) -> ProposalBlueprint:
    sections = [BlueprintSection(**s) for s in d.get("sections", [])]
    slots = [ResponseSlot(**s) for s in d.get("slots", [])]
    return ProposalBlueprint(
        schema_version=d.get("schema_version", "1"),
        run_id=d["run_id"],
        tor_identity=d.get("tor_identity", ""),
        assignment_type=d.get("assignment_type", ""),
        language=d.get("language", "english"),
        created_at=d.get("created_at", ""),
        sections=sections,
        slots=slots,
        coverage=d.get("coverage", {}),
    )
