"""previous_work.py — validate + register a previous-work annex (v0.6.4 §6).

Usage:
    python scripts/previous_work.py validate <file>
    python scripts/previous_work.py register <run_dir> <file> [--confirm-clearance]

`validate` classifies a candidate file: it must be an actual evaluation/endline/
assessment deliverable produced by/for ARFADA — NOT a proposal, TOR, policy, or
branding/manual document. `register` copies the validated file into the run package
(annexes/previous_work/) and writes previous_work.json. If ARFADA authorship/sharing
clearance cannot be established FROM the file, registration requires
--confirm-clearance (the user confirming ARFADA is cleared to share it).
Nothing is claimed "annexed" until the file exists in the run package.
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


def cmd_register(args) -> int:
    if len(args) < 2:
        _err("Usage: previous_work.py register <run_dir> <file> [--confirm-clearance]")
    run_dir = Path(args[0]).expanduser().resolve()
    src = Path(args[1]).expanduser().resolve()
    confirm = "--confirm-clearance" in args
    if not run_dir.exists():
        _err(f"Run directory not found: {run_dir}", 2)

    verdict = validate_previous_work(src, arfada_names=_arfada_names())
    if not verdict["ok"]:
        _err({"status": "REJECTED", "verdict": verdict,
              "message": "File is not an acceptable previous-work deliverable or does not exist."}, 4)
    if verdict["needs_clearance_confirmation"] and not confirm:
        _err({"status": "CLEARANCE_REQUIRED", "verdict": verdict,
              "message": "ARFADA authorship/clearance not evident in the file. Re-run with "
                         "--confirm-clearance once the user confirms ARFADA may share it."}, 5)

    dest_dir = run_dir / "annexes" / "previous_work"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copyfile(src, dest)
    record = {
        "file": str(dest),
        "original": str(src),
        "kind": verdict["kind"],
        "by_arfada": verdict["by_arfada"],
        "clearance_confirmed": bool(confirm or verdict["by_arfada"]),
        "verdict": verdict,
    }
    (run_dir / "previous_work.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    _out({"status": "REGISTERED", "annex": f"annexes/previous_work/{src.name}",
          "record": "previous_work.json", "by_arfada": verdict["by_arfada"],
          "clearance_confirmed": record["clearance_confirmed"]})
    return 0


_COMMANDS = {"validate": cmd_validate, "register": cmd_register}


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if not args or args[0] not in _COMMANDS:
        _err("Usage: previous_work.py <validate|register> ...")
    return _COMMANDS[args[0]](args[1:])


if __name__ == "__main__":
    sys.exit(main())
