"""style_qa.py — Writing DNA style QA over a run (v0.6.6).

Usage:
    python scripts/style_qa.py <run_dir>

Runs the deterministic Writing-DNA style checks across all generated sections and
writes style_qa.json. Reports generic AI filler, stock phrases, unnatural uniformity,
excessive headings/bullets, divergence from ARFADA's historical style, and suspicious
copying — with targeted rewrite suggestions. WORDING ONLY: it never changes facts,
decisions, or numbers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from engine.tor.style_qa import style_qa_report


def _out(d):
    sys.stdout.buffer.write((json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        sys.stderr.write("Usage: style_qa.py <run_dir>\n")
        return 1
    run_dir = Path(args[0]).expanduser().resolve()
    if not run_dir.exists():
        sys.stderr.write(f"Run directory not found: {run_dir}\n")
        return 2
    report = style_qa_report(run_dir)
    (run_dir / "style_qa.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _out(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
