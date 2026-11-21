"""previous_work.py — validate + register a previous-work annex (v0.6.4 §6).

Usage:
    python scripts/previous_work.py validate <file>
    python scripts/previous_work.py register <run_dir> <file> [--clearance-note "<permission>"]
    python scripts/previous_work.py clear <run_dir> --note "<explicit permission words>"

`validate` classifies a candidate file: it must be an actual evaluation/endline/
assessment deliverable produced by/for ARFADA — NOT a proposal, TOR, policy, or
branding/manual document. `register` copies the validated file into the run package
(annexes/previous_work/) and records the SELECTION in previous_work.json.

v0.6.12: selection and sharing clearance are independent. "Use the IRC report" is a
selection (PREVIOUS_WORK_SELECTED = VERIFIED, PREVIOUS_WORK_CLEARANCE = UNVERIFIED).
Only explicit permission wording ("cleared to share", "permission confirmed", "yes, it
may be shared externally") recorded via --clearance-note / `clear` sets clearance.
ARFADA authorship is not clearance. Until cleared, the proposal may name the report
but never say it is attached / accompanies / enclosed / annexed.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from engine.tor.annex import validate_previous_work


def _out(d):
    sys.stdout.buffer.write((json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _err(d, code=1):
    sys.stderr.buffer.write((json.dumps(d if isinstance(d, dict) else {"error": d},
                                        ensure_ascii=False) + "\n").encode("utf-8"))
    sys.exit(code)


def _arfada_names():
    try:
        from engine.tor.knowledge import Knowledge
        k = Knowledge()
        org = k.fact("org_name") or {}
        names = ["ARFADA"]
        if org.get("value"):
            names.append(str(org["value"]))
        return names
    except Exception:
        return ["ARFADA"]


def cmd_validate(args) -> int:
    if not args:
        _err("Usage: previous_work.py validate <file>")
    verdict = validate_previous_work(args[0], arfada_names=_arfada_names())
    _out(verdict)
    return 0


def _opt(args, name):
    if name in args:
        i = args.index(name)
        return args[i + 1] if i + 1 < len(args) else ""
    return None


def cmd_register(args) -> int:
    """Register the SELECTED report (selection only — v0.6.12).

    Sharing clearance is a separate state: pass --clearance-note "<the user's exact
    permission words>" here, or run `previous_work.py clear` later. A selection such
    as "use the IRC report", ARFADA authorship, or a bare --confirm-clearance flag
    never clears the report.
    """
    if len(args) < 2:
        _err("Usage: previous_work.py register <run_dir> <file> [--clearance-note \"<permission>\"]")
    run_dir = Path(args[0]).expanduser().resolve()
    src = Path(args[1]).expanduser().resolve()
    note = _opt(args, "--clearance-note")
    if not run_dir.exists():
        _err(f"Run directory not found: {run_dir}", 2)

    verdict = validate_previous_work(src, arfada_names=_arfada_names())
    if not verdict["ok"]:
        _err({"status": "REJECTED", "verdict": verdict,
              "message": "File is not an acceptable previous-work deliverable or does not exist."}, 4)

    from engine.tor.previous_work_state import record_selection, record_clearance
    dest_dir = run_dir / "annexes" / "previous_work"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copyfile(src, dest)
    record = record_selection(run_dir, file=dest, original=src, verdict=verdict)
    clearance = None
    if note:
        clearance = record_clearance(run_dir, note)
    elif "--confirm-clearance" in args:
        clearance = {"ok": False, "status": "NOT_EXPLICIT_PERMISSION",
                     "message": "--confirm-clearance alone no longer clears a report; pass "
                                "--clearance-note with the user's explicit permission words."}
    from engine.tor.previous_work_state import previous_work_states
    st = previous_work_states(run_dir)
    _out({"status": "REGISTERED", "annex": f"annexes/previous_work/{src.name}",
          "record": "previous_work.json", "by_arfada": verdict["by_arfada"],
          "previous_work_selected": st["selected"]["status"],
          "previous_work_clearance": st["clearance"]["status"],
          "clearance": clearance})
    return 0


def cmd_clear(args) -> int:
    """Record explicit sharing permission for the selected report."""
    if not args:
        _err("Usage: previous_work.py clear <run_dir> --note \"<explicit permission words>\"")
    run_dir = Path(args[0]).expanduser().resolve()
    note = _opt(args, "--note") or ""
    from engine.tor.previous_work_state import record_clearance
    res = record_clearance(run_dir, note)
    if not res["ok"]:
        _err(res, 6)
    _out(res)
    return 0


_COMMANDS = {"validate": cmd_validate, "register": cmd_register, "clear": cmd_clear}


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if not args or args[0] not in _COMMANDS:
        _err("Usage: previous_work.py <validate|register|clear> ...")
    return _COMMANDS[args[0]](args[1:])


if __name__ == "__main__":
    sys.exit(main())
