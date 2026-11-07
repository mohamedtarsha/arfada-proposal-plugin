"""PE2 TOR-intelligence data types."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TORField:
    assignment_id: str
    tor_document_id: str
    field_key: str
    value_text: str
    source_section_id: Optional[str]
    source_section_path: str
    block_start: Optional[int]
    block_end: Optional[int]
    page: Optional[int]
    method: str                 # SECTION | PATTERN | METADATA | KEYWORD_SCAN
    confidence: str             # HIGH | MEDIUM | LOW | UNKNOWN
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class TORRequirement:
    req_id: str
    assignment_id: str
    tor_document_id: str
    text: str
    category: str               # deliverable|methodology|team|proposal_format|submission|scope|ethics
    mandatory: bool
    modality: str               # MANDATORY | OPTIONAL | PROHIBITION | UNSPECIFIED
    source_section_path: str
    block_sequence: Optional[int]
    page: Optional[int]
    method: str = "DETERMINISTIC"     # DETERMINISTIC | LIST | MODAL | TABLE_CELL
    confidence: str = "MEDIUM"
    source_locator: str = ""          # cell locator 'tblid:rIcJ' when table-derived
    atomic_group: str = ""            # shared id when one source split into many reqs


@dataclass
class ComplianceRow:
    row_id: str
    assignment_id: str
    requirement_id: str
    proposal_document_id: Optional[str]
    proposal_section_id: Optional[str]
    proposal_section_path: str
    status: str                 # COVERED | PARTIAL | GAP | UNKNOWN
    match_score: float
    note: str = ""


@dataclass
class TORProfile:
    assignment_id: str
    tor_document_ids: list[str]
    fields_found: int
    fields_total: int
    requirement_count: int
    mandatory_count: int
    coverage_pct: float
    method: str = "DETERMINISTIC"
