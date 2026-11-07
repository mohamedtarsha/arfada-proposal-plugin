"""decision_register.py — CLI bridge for Human Decision Review (Phase 2).

The Skill (SKILL.md) handles human interaction.
This script handles validation, persistence, and atomic writes.

Usage:
    python scripts/decision_register.py init <run_dir>
    python scripts/decision_register.py show <run_dir>
    python scripts/decision_register.py get <run_dir> <decision_id>
    python scripts/decision_register.py set <run_dir> <decision_id> <value>
    python scripts/decision_register.py defer <run_dir> <decision_id> [<reason>]
    python scripts/decision_register.py skip <run_dir> <decision_id>
    python scripts/decision_register.py unresolved <run_dir> <decision_id> [<notes>]
    python scripts/decision_register.py clear <run_dir> <decision_id>
    python scripts/decision_register.py recommend <run_dir> <decision_id> <value>
    python scripts/decision_register.py approve <run_dir> <decision_id>
    python scripts/decision_register.py next <run_dir>
    python scripts/decision_register.py summary <run_dir>

Outputs are machine-readable (JSON on stdout, errors on stderr).
Exits 0 on success, non-zero on failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from engine.tor.register import (
    init_register, load_register, save_register, get_summary,
    set_decision, defer_decision, skip_decision, unresolve_decision,
    clear_decision, set_recommendation, approve_recommendation,
    next_open, register_to_dict,
    Status,
)


def _out(data: dict) -> None:
    """Write JSON to stdout using UTF-8 buffer to handle Arabic + special chars."""
    s = json.dumps(data, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write((s + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def _err(msg: str, code: int = 1) -> None:
    print(json.dumps({"error": msg}), file=sys.stderr)
    sys.exit(code)


def _run_dir(path_str: str) -> Path:
    p = Path(path_str).expanduser().resolve()
    if not p.exists():
        _err(f"Run directory not found: {p}")
    return p


def _load(run_dir: Path):
    try:
        return load_register(run_dir)
    except FileNotFoundError as e:
        _err(str(e), 2)


def _save_and_out(reg, run_dir: Path, msg: str = "OK") -> None:
    save_register(reg, run_dir)
    summary = get_summary(reg)
    _out({"status": "ok", "message": msg, "register_summary": summary})


def _parse_value(raw: str):
    """Try int → float → bool → str."""
    try:
        v = json.loads(raw)
        return v
    except (json.JSONDecodeError, ValueError):
        return raw


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_init(argv: list[str]) -> None:
    if len(argv) < 1:
        _err("Usage: init <run_dir>")
    run_dir = _run_dir(argv[0])
    try:
        reg = init_register(run_dir)
    except FileNotFoundError as e:
        _err(str(e))
    summary = get_summary(reg)
    _out({
        "status": "ok",
        "message": f"Decision register initialized with {summary['total_decisions']} decisions",
        "run_id": reg.run_id,
        "register_summary": summary,
    })


def cmd_show(argv: list[str]) -> None:
    if len(argv) < 1:
        _err("Usage: show <run_dir>")
    run_dir = _run_dir(argv[0])
    reg = _load(run_dir)
    summary = get_summary(reg)
    decisions_out = []
    for e in reg.decisions:
        decisions_out.append({
            "decision_id": e.decision_id,
            "decision_type": e.decision_type,
            "decision_status": e.decision_status,
            "question": e.question,
            "selected_value": e.selected_value,
            "constraint_type": e.constraint_type,
            "minimum": e.minimum,
            "maximum": e.maximum,
            "category": e.category,
            "source_text": e.source_text[:100],
        })
    _out({"run_id": reg.run_id, "summary": summary, "decisions": decisions_out})


def cmd_get(argv: list[str]) -> None:
    if len(argv) < 2:
        _err("Usage: get <run_dir> <decision_id>")
    run_dir = _run_dir(argv[0])
    reg = _load(run_dir)
    did = argv[1]
    for e in reg.decisions:
        if e.decision_id == did:
            _out({"status": "ok", "decision": {
                "decision_id": e.decision_id,
                "decision_type": e.decision_type,
                "decision_status": e.decision_status,
                "question": e.question,
                "selected_value": e.selected_value,
                "recommendation": e.recommendation,
                "value_type": e.value_type,
                "constraint_type": e.constraint_type,
                "minimum": e.minimum,
                "maximum": e.maximum,
                "source_text": e.source_text,
                "category": e.category,
                "actor": e.actor,
                "decided_by": e.decided_by,
                "decided_at": e.decided_at,
                "notes": e.notes,
                "previous_value": e.previous_value,
            }})
            return
    _err(f"Decision '{did}' not found", 3)


def cmd_set(argv: list[str]) -> None:
    if len(argv) < 3:
        _err("Usage: set <run_dir> <decision_id> <value> [<notes>]")
    run_dir = _run_dir(argv[0])
    reg = _load(run_dir)
    value = _parse_value(argv[2])
    notes = argv[3] if len(argv) > 3 else None
    result = set_decision(reg, argv[1], value, notes=notes)
    if not result["valid"]:
        print(json.dumps({"status": "error", "message": result["message"]}), file=sys.stderr)
        sys.exit(4)
    _save_and_out(reg, run_dir, result["message"])


def cmd_defer(argv: list[str]) -> None:
    if len(argv) < 2:
        _err("Usage: defer <run_dir> <decision_id> [<reason>]")
    run_dir = _run_dir(argv[0])
    reg = _load(run_dir)
    reason = argv[2] if len(argv) > 2 else ""
    defer_decision(reg, argv[1], reason=reason)
    _save_and_out(reg, run_dir, "Decision deferred")


def cmd_skip(argv: list[str]) -> None:
    if len(argv) < 2:
        _err("Usage: skip <run_dir> <decision_id>")
    run_dir = _run_dir(argv[0])
    reg = _load(run_dir)
    skip_decision(reg, argv[1])
    _save_and_out(reg, run_dir, "Decision skipped")


def cmd_unresolved(argv: list[str]) -> None:
    if len(argv) < 2:
        _err("Usage: unresolved <run_dir> <decision_id> [<notes>]")
    run_dir = _run_dir(argv[0])
    reg = _load(run_dir)
    notes = argv[2] if len(argv) > 2 else None
    unresolve_decision(reg, argv[1], notes=notes)
    _save_and_out(reg, run_dir, "Decision marked unresolved")


def cmd_clear(argv: list[str]) -> None:
    if len(argv) < 2:
        _err("Usage: clear <run_dir> <decision_id>")
    run_dir = _run_dir(argv[0])
    reg = _load(run_dir)
    clear_decision(reg, argv[1])
    _save_and_out(reg, run_dir, "Decision cleared (reset to OPEN)")


def cmd_recommend(argv: list[str]) -> None:
    if len(argv) < 3:
        _err("Usage: recommend <run_dir> <decision_id> <value>")
    run_dir = _run_dir(argv[0])
    reg = _load(run_dir)
    value = _parse_value(argv[2])
    set_recommendation(reg, argv[1], value)
    _save_and_out(reg, run_dir, "Recommendation stored (not yet approved)")


def cmd_approve(argv: list[str]) -> None:
    if len(argv) < 2:
        _err("Usage: approve <run_dir> <decision_id> [<notes>]")
    run_dir = _run_dir(argv[0])
    reg = _load(run_dir)
    notes = argv[2] if len(argv) > 2 else None
    result = approve_recommendation(reg, argv[1], notes=notes)
    if not result["valid"]:
        print(json.dumps({"status": "error", "message": result["message"]}), file=sys.stderr)
        sys.exit(4)
    _save_and_out(reg, run_dir, result["message"])


def cmd_next(argv: list[str]) -> None:
    if len(argv) < 1:
        _err("Usage: next <run_dir>")
    run_dir = _run_dir(argv[0])
    reg = _load(run_dir)
    e = next_open(reg)
    if e is None:
        _out({"status": "ok", "message": "No more open decisions", "decision": None})
    else:
        _out({"status": "ok", "decision": {
            "decision_id": e.decision_id,
            "decision_type": e.decision_type,
            "decision_status": e.decision_status,
            "question": e.question,
            "constraint_type": e.constraint_type,
            "minimum": e.minimum,
            "maximum": e.maximum,
            "source_text": e.source_text,
            "category": e.category,
            "recommendation": e.recommendation,
        }})


def cmd_summary(argv: list[str]) -> None:
    if len(argv) < 1:
        _err("Usage: summary <run_dir>")
    run_dir = _run_dir(argv[0])
    reg = _load(run_dir)
    _out(get_summary(reg))


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_COMMANDS = {
    "init": cmd_init,
    "show": cmd_show,
    "get": cmd_get,
    "set": cmd_set,
    "defer": cmd_defer,
    "skip": cmd_skip,
    "unresolved": cmd_unresolved,
    "clear": cmd_clear,
    "recommend": cmd_recommend,
    "approve": cmd_approve,
    "next": cmd_next,
    "summary": cmd_summary,
}


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if not args or args[0] not in _COMMANDS:
        cmds = " | ".join(sorted(_COMMANDS))
        print(f"Usage: decision_register.py <{cmds}> <run_dir> ...", file=sys.stderr)
        return 1
    cmd = args[0]
    _COMMANDS[cmd](args[1:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
