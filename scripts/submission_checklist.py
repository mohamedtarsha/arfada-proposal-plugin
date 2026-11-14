"""submission_checklist.py — classify TOR submission requirements (v0.6.4 §2).

Usage:
    python scripts/submission_checklist.py <run_dir>

Reads requirements.json and emits each submission/compliance requirement with a
stable human item identity (e.g. "Detailed budget", "Example of previous work",
"CV annex") and an obligation level: MANDATORY | SCORING | OPTIONAL. Never invents
requirements. QA consumes the same classifier so missing items are reported by name.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from engine.tor.submission import build_submission_checklist, MANDATORY, SCORING, OPTIONAL


def _out(d):
    sys.stdout.buffer.write((json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        sys.stderr.write("Usage: submission_checklist.py <run_dir>\n")
        return 1
    run_dir = Path(args[0]).expanduser().resolve()
    reqs_path = run_dir / "requirements.json"
    if not reqs_path.exists():
        sys.stderr.write(f"requirements.json not found in {run_dir}\n")
        return 2
    reqs = json.loads(reqs_path.read_text(encoding="utf-8")).get("requirements", [])
    checklist = build_submission_checklist(reqs)
    by = {MANDATORY: [], SCORING: [], OPTIONAL: []}
    for e in checklist:
        by.setdefault(e["obligation"], []).append(e)
    _out({
        "run_id": run_dir.name,
        "total": len(checklist),
        "counts": {k: len(v) for k, v in by.items()},
        "mandatory": by[MANDATORY],
        "scoring": by[SCORING],
        "optional": by[OPTIONAL],
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
