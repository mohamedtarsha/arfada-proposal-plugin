"""decision_cards.py — emit ordered interactive-card descriptors (v0.6.3, UX only).

Bridges the live decision register + TOR candidate metadata into native
AskUserQuestion-ready descriptors (see engine/tor/decision_ui.py). This is a
PRESENTATION layer only: it never writes decisions. The Skill feeds each
descriptor to the native option-card UI, then calls decision_register.py to
persist the user's actual choice (with the same validation as before).

Usage:
    python scripts/decision_cards.py list <run_dir> [--language ar|en] [--all]
    python scripts/decision_cards.py next <run_dir> [--language ar|en]

`list`  → every actionable decision as an ordered descriptor array, plus a
          progress header ("Decision 2 of 6") derived from register status.
          --all includes already-resolved decisions (status shown), for review.
`next`  → the single next actionable descriptor (OPEN/RECOMMENDATION), or null.

Output is machine-readable JSON on stdout (UTF-8, Arabic-safe).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from engine.tor.register import load_register, get_summary, Status, CANDIDATES_FILE
from engine.tor import decision_ui


def _out(data) -> None:
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


def _candidate_index(run_dir: Path) -> dict:
    """Map decision_id -> candidate dict (for allowed_options & friends)."""
    cand_path = run_dir / CANDIDATES_FILE
    if not cand_path.exists():
        return {}
    with cand_path.open(encoding="utf-8") as f:
        data = json.load(f)
    return {c["decision_id"]: c for c in data.get("candidates", [])}


def _entry_as_decision(entry, cand: dict) -> dict:
    """Merge the live register entry with candidate-only fields (allowed_options)."""
    return {
        "decision_id": entry.decision_id,
        "requirement_id": entry.requirement_id,
        "decision_type": entry.decision_type,
        "question": entry.question,
        "constraint_type": entry.constraint_type,
        "minimum": entry.minimum,
        "maximum": entry.maximum,
        "source_text": entry.source_text,
        "category": entry.category,
        "actor": entry.actor,
        # register only stores is_human_decision=True entries, so these are decisions
        "is_human_decision": True,
        "allowed_options": (cand or {}).get("allowed_options", []),
    }


def _parse_flags(argv: list[str]) -> tuple[list[str], dict]:
    positional, flags = [], {"language": "english", "all": False}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--language" and i + 1 < len(argv):
            lang = argv[i + 1].lower()
            flags["language"] = "arabic" if lang.startswith("ar") else "english"
            i += 2
        elif a in ("--all", "-a"):
            flags["all"] = True
            i += 1
        else:
            positional.append(a)
            i += 1
    return positional, flags


def _descriptor_for(entry, cand_index, language):
    cand = cand_index.get(entry.decision_id, {})
    decision = _entry_as_decision(entry, cand)
    desc = decision_ui.build_question_descriptor(decision, language=language)
    if desc is not None:
        desc["decision_status"] = entry.decision_status
        desc["recommendation"] = entry.recommendation
    return desc


def cmd_list(argv: list[str]) -> None:
    positional, flags = _parse_flags(argv)
    if not positional:
        _err("Usage: list <run_dir> [--language ar|en] [--all]")
    run_dir = _run_dir(positional[0])
    reg = load_register(run_dir)
    cand_index = _candidate_index(run_dir)
    language = flags["language"]

    actionable = Status.actionable()
    cards = []
    for e in reg.decisions:
        if not flags["all"] and e.decision_status not in actionable:
            continue
        desc = _descriptor_for(e, cand_index, language)
        if desc is not None:
            cards.append(desc)

    summary = get_summary(reg)
    total_actionable = sum(
        1 for e in reg.decisions if e.decision_status in actionable
    )
    _out({
        "status": "ok",
        "run_id": reg.run_id,
        "language": language,
        "total_cards": len(cards),
        "total_actionable": total_actionable,
        "progress_label_template": "Decision {index} of {total}",
        "register_summary": summary,
        "cards": cards,
    })


def cmd_next(argv: list[str]) -> None:
    positional, flags = _parse_flags(argv)
    if not positional:
        _err("Usage: next <run_dir> [--language ar|en]")
    run_dir = _run_dir(positional[0])
    reg = load_register(run_dir)
    cand_index = _candidate_index(run_dir)
    language = flags["language"]

    actionable = Status.actionable()
    ordered = [e for e in reg.decisions if e.decision_status in actionable]
    total = len(ordered)
    for i, e in enumerate(ordered, 1):
        desc = _descriptor_for(e, cand_index, language)
        if desc is not None:
            desc["progress_index"] = i
            desc["progress_total"] = total
            desc["progress_label"] = f"Decision {i} of {total}"
            _out({"status": "ok", "card": desc})
            return
    _out({"status": "ok", "card": None, "message": "No more decisions to review"})


_COMMANDS = {"list": cmd_list, "next": cmd_next}


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if not args or args[0] not in _COMMANDS:
        cmds = " | ".join(sorted(_COMMANDS))
        print(f"Usage: decision_cards.py <{cmds}> <run_dir> ...", file=sys.stderr)
        return 1
    _COMMANDS[args[0]](args[1:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
