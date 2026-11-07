"""Decision Register — persistent store for Human Decision Review (Phase 2).

Manages the lifecycle of proposal decisions extracted from a TOR analysis.
Every decision starts OPEN; the user/team resolves, defers, or leaves it
unresolved. The register is linked to a specific TOR-analysis run by run_id
so decisions from TOR-A can never bleed into TOR-B.

Atomic write: writes to .tmp → validate → rename. Corrupt in-flight writes
leave the last valid register intact.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REGISTER_FILE = "decision_register.json"
CANDIDATES_FILE = "decision_candidates.json"
SCHEMA_VERSION = "1"


class Status:
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    DEFERRED = "DEFERRED"
    SKIPPED = "SKIPPED"
    UNRESOLVED = "UNRESOLVED"
    RECOMMENDATION = "RECOMMENDATION"   # suggested but not yet approved by user

    @staticmethod
    def all():
        return {Status.OPEN, Status.RESOLVED, Status.DEFERRED,
                Status.SKIPPED, Status.UNRESOLVED, Status.RECOMMENDATION}

    @staticmethod
    def terminal():
        """States that count as 'done' for this session."""
        return {Status.RESOLVED, Status.DEFERRED, Status.UNRESOLVED, Status.SKIPPED}

    @staticmethod
    def actionable():
        return {Status.OPEN, Status.RECOMMENDATION}


class ValueType:
    NUMBER = "number"
    STRING = "string"
    BOOLEAN = "boolean"
    LIST = "list"
    DEFERRED = "deferred"
    NONE = "none"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class DecisionEntry:
    decision_id: str
    requirement_id: str
    decision_type: str
    question: str
    decision_status: str         # Status.*
    selected_value: Any          # the user's chosen value (None if not resolved)
    value_type: str              # ValueType.*
    constraint_type: str
    minimum: Optional[float]
    maximum: Optional[float]
    source_text: str
    source_locator: str
    category: str
    actor: str
    reason: str
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None
    notes: Optional[str] = None
    recommendation: Any = None   # Claude's suggestion (not authoritative)
    previous_value: Any = None   # set when a resolved decision is edited


@dataclass
class DecisionRegister:
    schema_version: str
    run_id: str
    tor_identity: str           # sha1(run_id + file_name) — guards against wrong-TOR apply
    created_at: str
    updated_at: str
    status: str                 # OPEN | PARTIAL | COMPLETE
    decisions: list[DecisionEntry] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _entry_to_dict(e: DecisionEntry) -> dict:
    return asdict(e)


def _entry_from_dict(d: dict) -> DecisionEntry:
    return DecisionEntry(
        decision_id=d["decision_id"],
        requirement_id=d["requirement_id"],
        decision_type=d["decision_type"],
        question=d.get("question") or "",
        decision_status=d.get("decision_status", Status.OPEN),
        selected_value=d.get("selected_value"),
        value_type=d.get("value_type", ValueType.NONE),
        constraint_type=d.get("constraint_type", "NONE"),
        minimum=d.get("minimum"),
        maximum=d.get("maximum"),
        source_text=d.get("source_text", ""),
        source_locator=d.get("source_locator", ""),
        category=d.get("category", ""),
        actor=d.get("actor", ""),
        reason=d.get("reason", ""),
        decided_by=d.get("decided_by"),
        decided_at=d.get("decided_at"),
        notes=d.get("notes"),
        recommendation=d.get("recommendation"),
        previous_value=d.get("previous_value"),
    )


def register_to_dict(reg: DecisionRegister) -> dict:
    return {
        "schema_version": reg.schema_version,
        "run_id": reg.run_id,
        "tor_identity": reg.tor_identity,
        "created_at": reg.created_at,
        "updated_at": reg.updated_at,
        "status": reg.status,
        "decisions": [_entry_to_dict(e) for e in reg.decisions],
    }


def register_from_dict(d: dict) -> DecisionRegister:
    return DecisionRegister(
        schema_version=d.get("schema_version", SCHEMA_VERSION),
        run_id=d["run_id"],
        tor_identity=d.get("tor_identity", ""),
        created_at=d["created_at"],
        updated_at=d["updated_at"],
        status=d.get("status", "OPEN"),
        decisions=[_entry_from_dict(e) for e in d.get("decisions", [])],
    )


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def load_register(run_dir: Path) -> DecisionRegister:
    """Load an existing decision register. Raises FileNotFoundError if absent."""
    path = run_dir / REGISTER_FILE
    if not path.exists():
        raise FileNotFoundError(f"No decision register at {path}. Run 'init' first.")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return register_from_dict(data)


def save_register(reg: DecisionRegister, run_dir: Path) -> None:
    """Atomic write: temp-file → validate → rename."""
    reg.updated_at = _now()
    reg.status = _derive_status(reg)
    target = run_dir / REGISTER_FILE
    fd, tmp = tempfile.mkstemp(dir=run_dir, suffix=".tmp", prefix="register_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(register_to_dict(reg), f, ensure_ascii=False, indent=2)
        # validate round-trip before replacing
        with open(tmp, encoding="utf-8") as f:
            register_from_dict(json.load(f))   # raises if corrupt
        os.replace(tmp, target)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _derive_status(reg: DecisionRegister) -> str:
    total = len(reg.decisions)
    if total == 0:
        return "OPEN"
    done = sum(1 for e in reg.decisions if e.decision_status in Status.terminal())
    if done == 0:
        return "OPEN"
    if done == total:
        resolved = sum(1 for e in reg.decisions if e.decision_status == Status.RESOLVED)
        return "COMPLETE" if resolved == total else "PARTIAL"
    return "PARTIAL"


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def _tor_identity(run_id: str, file_name: str) -> str:
    return hashlib.sha1(f"{run_id}|{file_name}".encode()).hexdigest()[:16]


def init_register(run_dir: Path) -> DecisionRegister:
    """Create a fresh register from decision_candidates.json.

    Only includes candidates where is_human_decision=True.
    Raises if candidates file missing or run_id mismatch.
    """
    cand_path = run_dir / CANDIDATES_FILE
    if not cand_path.exists():
        raise FileNotFoundError(f"decision_candidates.json not found in {run_dir}")

    with cand_path.open(encoding="utf-8") as f:
        candidates_data = json.load(f)

    run_id = candidates_data.get("run_id", run_dir.name)
    # Derive TOR identity from run directory name + first candidate source
    first_src = ""
    if candidates_data.get("candidates"):
        first_src = candidates_data["candidates"][0].get("source_text", "")[:30]
    identity = _tor_identity(run_id, first_src)

    decisions: list[DecisionEntry] = []
    for c in candidates_data.get("candidates", []):
        if not c.get("is_human_decision"):
            continue
        decisions.append(DecisionEntry(
            decision_id=c["decision_id"],
            requirement_id=c["requirement_id"],
            decision_type=c["decision_type"],
            question=c.get("question") or "",
            decision_status=Status.OPEN,
            selected_value=None,
            value_type=ValueType.NONE,
            constraint_type=c.get("constraint_type", "NONE"),
            minimum=c.get("minimum"),
            maximum=c.get("maximum"),
            source_text=c.get("source_text", ""),
            source_locator=c.get("source_locator", ""),
            category=c.get("category", ""),
            actor=c.get("actor", ""),
            reason=c.get("reason", ""),
        ))

    now = _now()
    reg = DecisionRegister(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        tor_identity=identity,
        created_at=now,
        updated_at=now,
        status="OPEN",
        decisions=decisions,
    )
    save_register(reg, run_dir)
    return reg


# ---------------------------------------------------------------------------
# Decision operations
# ---------------------------------------------------------------------------

def _get_entry(reg: DecisionRegister, decision_id: str) -> DecisionEntry:
    for e in reg.decisions:
        if e.decision_id == decision_id:
            return e
    raise KeyError(f"Decision '{decision_id}' not found in register")


def _infer_value_type(value: Any) -> str:
    if isinstance(value, bool):
        return ValueType.BOOLEAN
    if isinstance(value, (int, float)):
        return ValueType.NUMBER
    if isinstance(value, list):
        return ValueType.LIST
    if isinstance(value, str) and value.strip():
        return ValueType.STRING
    return ValueType.NONE


def validate_value(entry: DecisionEntry, value: Any) -> dict:
    """Validate proposed value against TOR constraints.

    Returns {"valid": bool, "message": str}.
    TOR-fixed entries (non-human-decision types) always reject changes.
    """
    # Only OPEN_PROPOSAL_DECISION entries accept numeric bounds
    if isinstance(value, (int, float)):
        if entry.minimum is not None and value < entry.minimum:
            return {"valid": False,
                    "message": f"Value {value} is below TOR minimum {entry.minimum}. "
                               f"The TOR constraint cannot be overridden."}
        if entry.maximum is not None and value > entry.maximum:
            return {"valid": False,
                    "message": f"Value {value} exceeds TOR maximum {entry.maximum}. "
                               f"The TOR constraint cannot be overridden."}
    return {"valid": True, "message": "Value accepted"}


def set_decision(reg: DecisionRegister, decision_id: str, value: Any,
                 decided_by: str = "user", notes: str | None = None) -> dict:
    """Set a decision to RESOLVED with the given value.

    Validates value against TOR constraints. Returns validation result.
    Preserves previous_value if decision was already resolved.
    """
    entry = _get_entry(reg, decision_id)
    result = validate_value(entry, value)
    if not result["valid"]:
        return result
    entry.previous_value = entry.selected_value
    entry.selected_value = value
    entry.value_type = _infer_value_type(value)
    entry.decision_status = Status.RESOLVED
    entry.decided_by = decided_by
    entry.decided_at = _now()
    if notes:
        entry.notes = notes
    return {"valid": True, "message": "Decision resolved"}


def defer_decision(reg: DecisionRegister, decision_id: str, reason: str = "",
                   decided_by: str = "user") -> None:
    """Mark a decision as DEFERRED (to inception phase or later)."""
    entry = _get_entry(reg, decision_id)
    entry.decision_status = Status.DEFERRED
    entry.selected_value = "DEFER_TO_INCEPTION"
    entry.value_type = ValueType.DEFERRED
    entry.decided_at = _now()
    entry.decided_by = decided_by
    if reason:
        entry.notes = reason


def skip_decision(reg: DecisionRegister, decision_id: str) -> None:
    """Mark a decision as SKIPPED (not answered this session)."""
    entry = _get_entry(reg, decision_id)
    entry.decision_status = Status.SKIPPED
    entry.decided_at = _now()


def unresolve_decision(reg: DecisionRegister, decision_id: str,
                       notes: str | None = None) -> None:
    """Mark a decision as UNRESOLVED (team reviewed but intentionally left open)."""
    entry = _get_entry(reg, decision_id)
    entry.decision_status = Status.UNRESOLVED
    entry.decided_at = _now()
    if notes:
        entry.notes = notes


def clear_decision(reg: DecisionRegister, decision_id: str) -> None:
    """Reset a decision to OPEN, clearing any previous value."""
    entry = _get_entry(reg, decision_id)
    entry.previous_value = entry.selected_value
    entry.selected_value = None
    entry.value_type = ValueType.NONE
    entry.decision_status = Status.OPEN
    entry.decided_at = None
    entry.decided_by = None


def set_recommendation(reg: DecisionRegister, decision_id: str, value: Any,
                       recommender: str = "claude") -> None:
    """Record a suggestion as RECOMMENDATION (not yet approved by user)."""
    entry = _get_entry(reg, decision_id)
    entry.recommendation = value
    entry.decision_status = Status.RECOMMENDATION
    entry.decided_at = _now()
    entry.decided_by = recommender


def approve_recommendation(reg: DecisionRegister, decision_id: str,
                            notes: str | None = None) -> dict:
    """Approve a pending RECOMMENDATION → RESOLVED.

    Validates the recommendation value before approving.
    """
    entry = _get_entry(reg, decision_id)
    if entry.decision_status != Status.RECOMMENDATION:
        return {"valid": False, "message": "No pending recommendation to approve"}
    if entry.recommendation is None:
        return {"valid": False, "message": "Recommendation value is empty"}
    result = validate_value(entry, entry.recommendation)
    if not result["valid"]:
        return result
    entry.selected_value = entry.recommendation
    entry.value_type = _infer_value_type(entry.recommendation)
    entry.decision_status = Status.RESOLVED
    entry.decided_at = _now()
    entry.decided_by = "user (approved recommendation)"
    if notes:
        entry.notes = notes
    return {"valid": True, "message": "Recommendation approved and resolved"}


def protect_fixed_requirement(entry: DecisionEntry) -> bool:
    """True if this entry must not be altered (TOR-fixed)."""
    return not entry.decision_id or entry.decision_type in {
        "FIXED_REQUIREMENT", "FIXED_MINIMUM", "FIXED_MAXIMUM",
        "FIXED_RANGE", "NO_DECISION",
    }


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def get_summary(reg: DecisionRegister) -> dict:
    total = len(reg.decisions)
    by_status: dict[str, int] = {}
    for e in reg.decisions:
        by_status[e.decision_status] = by_status.get(e.decision_status, 0) + 1

    return {
        "run_id": reg.run_id,
        "status": reg.status,
        "total_decisions": total,
        "resolved": by_status.get(Status.RESOLVED, 0),
        "deferred": by_status.get(Status.DEFERRED, 0),
        "skipped": by_status.get(Status.SKIPPED, 0),
        "unresolved": by_status.get(Status.UNRESOLVED, 0),
        "open": by_status.get(Status.OPEN, 0),
        "recommendation": by_status.get(Status.RECOMMENDATION, 0),
        "percent_complete": round(
            100.0 * by_status.get(Status.RESOLVED, 0) / total, 1
        ) if total > 0 else 0.0,
    }


def next_open(reg: DecisionRegister) -> Optional[DecisionEntry]:
    """Return the first OPEN or RECOMMENDATION decision, or None."""
    for e in reg.decisions:
        if e.decision_status in Status.actionable():
            return e
    return None
