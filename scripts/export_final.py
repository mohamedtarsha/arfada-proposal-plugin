"""export_final.py — gated final client deliverable (v0.6.0).

Usage:
    python scripts/export_final.py <run_dir>            # export if GREEN
    python scripts/export_final.py <run_dir> --confirm  # export on YELLOW too

Gating (spec §34):
  GREEN  → produce proposal_final.docx
  YELLOW → requires --confirm
  RED    → blocked (exit 20); no client deliverable produced

Re-runs Final QA first so the gate reflects the current artifacts (no stale GREEN).
proposal_final.docx is the validated client content — no new content is introduced.
No model call, no network.
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

from engine.tor.final_qa import run_final_qa, to_markdown


def _out(d):
    sys.stdout.buffer.write((json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _err(d, code=1):
    sys.stderr.buffer.write((json.dumps(d if isinstance(d, dict) else {"error": d},
                                        ensure_ascii=False) + "\n").encode("utf-8"))
    sys.exit(code)


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        _err("Usage: export_final.py <run_dir> [--confirm]")
    run_dir = Path(args[0]).expanduser().resolve()
    if not run_dir.exists():
        _err(f"Run directory not found: {run_dir}")
    confirm = "--confirm" in args

    # re-run QA (no stale GREEN)
    report = run_final_qa(run_dir, plugin_version="0.6.0")
    (run_dir / "final_qa.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "final_qa.md").write_text(to_markdown(report), encoding="utf-8")
    status = report["overall_status"]

    if status == "RED":
        _err({"status": "BLOCKED", "overall_status": "RED",
              "reason": "Final export blocked by critical QA failures.",
              "critical": [f["message"] for f in report["critical_failures"]][:10]}, 20)
    if status == "YELLOW" and not confirm:
        _err({"status": "CONFIRMATION_REQUIRED", "overall_status": "YELLOW",
              "message": "QA has warnings. Re-run with --confirm to export the final despite them.",
              "warnings": [f["message"] for f in report["warnings"]][:10]}, 10)

    # produce proposal_final.docx from the validated client draft (no new content).
    client = run_dir / "proposal_client_draft.docx"
    if not client.exists():
        _err({"status": "NO_CLIENT_DRAFT",
              "message": "proposal_client_draft.docx not found — run render_docx.py --client first."}, 2)
    final = run_dir / "proposal_final.docx"
    shutil.copyfile(client, final)

    _out({
        "status": "EXPORTED",
        "overall_status": status,
        "confirmed": confirm,
        "proposal_final": "proposal_final.docx",
        "note": "Final = validated client content. GREEN/confirmed-YELLOW only. "
                "Automated QA does not replace human review before submission.",
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
