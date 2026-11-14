"""budget_builder.py — interactive detailed budget + reconciliation (v0.6.4 §7).

Usage:
    python scripts/budget_builder.py <run_dir> --spec budget_spec.json
    python scripts/budget_builder.py <run_dir> --spec -   # read spec JSON from stdin

Spec JSON:
    {
      "approved_total": 50000,
      "approved_loe": 80,
      "currency": "USD",
      "tolerance": 0,
      "lines": [
        {"label":"Team Leader fee","category":"expert_fees","quantity":30,"unit_cost":400},
        {"label":"Enumerators","category":"enumerators","quantity":50,"unit_cost":60},
        {"label":"Transport","category":"transport","amount":1500},
        {"label":"VAT","category":"taxes_mandatory","percent":16}
      ]
    }

The SKILL collects these line inputs interactively from the user (never invents a
value). The budget is computed and must reconcile EXACTLY to the approved total; the
reconciliation is shown BEFORE approval. On approval the result is saved to
budget.json and QA enforces reconciliation at Final QA.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from engine.tor.budget import build_budget


def _out(d):
    sys.stdout.buffer.write((json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _err(msg, code=1):
    sys.stderr.write(json.dumps({"error": msg}) + "\n")
    sys.exit(code)


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if not args or "--spec" not in args:
        _err("Usage: budget_builder.py <run_dir> --spec <spec.json|-> [--approve]")
    run_dir = Path(args[0]).expanduser().resolve()
    if not run_dir.exists():
        _err(f"Run directory not found: {run_dir}", 2)
    spec_arg = args[args.index("--spec") + 1]
    approve = "--approve" in args

    if spec_arg == "-":
        spec = json.loads(sys.stdin.read())
    else:
        spec = json.loads(Path(spec_arg).read_text(encoding="utf-8"))

    if spec.get("approved_total") is None:
        _err("spec.approved_total is required (use the approved total budget).", 3)

    budget = build_budget(
        approved_total=float(spec["approved_total"]),
        lines=spec.get("lines", []),
        approved_loe=spec.get("approved_loe"),
        currency=spec.get("currency", "USD"),
        tolerance=float(spec.get("tolerance", 0.0)),
    )

    if approve:
        if not budget["reconciles"]:
            _err({"status": "NOT_RECONCILED", "budget": budget,
                  "message": budget["reconciliation_message"]}, 4)
        (run_dir / "budget.json").write_text(
            json.dumps(budget, ensure_ascii=False, indent=2), encoding="utf-8")
        budget["saved"] = "budget.json"
        budget["status"] = "APPROVED"
    else:
        budget["status"] = "PREVIEW"
        budget["note"] = "Review the reconciliation, then re-run with --approve to save."

    _out(budget)
    return 0


if __name__ == "__main__":
    sys.exit(main())
