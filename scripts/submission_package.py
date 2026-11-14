"""submission_package.py — verify the physical submission package (v0.6.4 §11).

Usage:
    python scripts/submission_package.py <run_dir> [--min-cvs N]

Before final export (or right after GREEN QA), verify the ACTUAL files exist:
proposal_final.docx, required CVs, previous-work example, financial offer / detailed
budget, and any other TOR-required annex. A textual statement like "CVs annexed" is
NOT accepted as proof — only files physically present in the run package count.

Item expectations are derived from the submission checklist (requirements.json).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from engine.tor.package import check_submission_package
from engine.tor.submission import build_submission_checklist


def _out(d):
    sys.stdout.buffer.write((json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        sys.stderr.write("Usage: submission_package.py <run_dir> [--min-cvs N]\n")
        return 1
    run_dir = Path(args[0]).expanduser().resolve()
    min_cvs = 0
    if "--min-cvs" in args:
        min_cvs = int(args[args.index("--min-cvs") + 1])

    item_keys = []
    reqs_path = run_dir / "requirements.json"
    if reqs_path.exists():
        reqs = json.loads(reqs_path.read_text(encoding="utf-8")).get("requirements", [])
        item_keys = sorted({e["item_key"] for e in build_submission_checklist(reqs)})

    result = check_submission_package(run_dir, item_keys=item_keys, min_cvs=min_cvs)
    _out(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
