"""run_decision.py — record a run-level user decision (v0.6.16).

Usage:
    python scripts/run_decision.py <run_dir> run-purpose <LIVE_SUBMISSION|TEST_REPLAY> [--note "<user words>"]
    python scripts/run_decision.py <run_dir> submission-channel "<e-mail | platform | URL | Not known yet>"
    python scripts/run_decision.py <run_dir> team-availability --note "<user words, e.g. All selected experts are available>"
    python scripts/run_decision.py <run_dir> registration-choice "<file under ARFADA Knowledge/Company>"
    python scripts/run_decision.py <run_dir> show

Only the employee's explicit decision is recorded (never inferred). Invalid input
(e.g. a placeholder channel, hedged availability wording) is refused with exit 4.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from engine.tor import run_decisions as RD  # noqa: E402

_KEYS = {"run-purpose": "run_purpose", "submission-channel": "submission_channel",
         "team-availability": "team_availability", "registration-choice": "registration_choice"}


def _out(d):
    sys.stdout.buffer.write((json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _opt(args, name):
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else ""


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if len(args) < 2:
        sys.stderr.write(__doc__)
        return 1
    run_dir = Path(args[0]).expanduser().resolve()
    if not run_dir.exists():
        _out({"ok": False, "message": f"Run directory not found: {run_dir}"})
        return 2
    if args[1] == "show":
        _out(RD.load(run_dir))
        return 0
    key = _KEYS.get(args[1])
    if not key:
        sys.stderr.write(__doc__)
        return 1
    note = _opt(args, "--note")
    value = args[2] if len(args) > 2 and not args[2].startswith("--") else ""
    res = RD.record(run_dir, key, value, note=note)
    _out(res)
    return 0 if res.get("ok") else 4


if __name__ == "__main__":
    sys.exit(main())
