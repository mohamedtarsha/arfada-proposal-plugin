"""final_qa.py — deterministic Final Quality Review (v0.6.0).

Usage:
    python scripts/final_qa.py <run_dir>
    python scripts/final_qa.py <run_dir> --repair-plan

Runs all QA checks over the run artifacts, writes final_qa.json + final_qa.md, and
prints a concise summary. A stored GREEN applies only to the exact reviewed
artifacts (fingerprint). No model call, no network.
Exit code: 0 GREEN, 10 YELLOW, 20 RED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from engine.tor.final_qa import run_final_qa, to_markdown, build_repair_plan


def _out(d):
    sys.stdout.buffer.write((json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _err(msg, code=1):
    sys.stderr.buffer.write((json.dumps({"error": msg}) + "\n").encode("utf-8"))
    sys.exit(code)


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        _err("Usage: final_qa.py <run_dir> [--repair-plan]")
    run_dir = Path(args[0]).expanduser().resolve()
    if not run_dir.exists():
        _err(f"Run directory not found: {run_dir}")

    report = run_final_qa(run_dir)  # version resolved from plugin.json

    # persist
    (run_dir / "final_qa.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "final_qa.md").write_text(to_markdown(report), encoding="utf-8")

    if "--repair-plan" in args:
        _out(build_repair_plan(report))
        return _exit_code(report)

    s = report["summary"]
    _out({
        "overall_status": report["overall_status"],
        "fingerprint": report["fingerprint"],
        "mandatory_addressed": f"{s['mandatory_addressed']}/{s['mandatory_requirements']}",
        "critical_failures": s["critical_failures"],
        "errors": s["errors"],
        "warnings": s["warnings"],
        "decisions_respected": f"{s['decisions_respected']}/{s['decisions_resolved']}",
        "critical": [f["message"] for f in report["critical_failures"]][:10],
        "top_warnings": [f["message"] for f in report["warnings"]][:5],
        "report_md": "final_qa.md",
    })
    return _exit_code(report)


def _exit_code(report) -> int:
    return {"GREEN": 0, "YELLOW": 10, "RED": 20}.get(report["overall_status"], 1)


if __name__ == "__main__":
    sys.exit(main())
