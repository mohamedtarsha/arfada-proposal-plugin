"""refresh_exemplars.py — scan the Winning Proposal Library → local exemplar index.

Usage:
    python scripts/refresh_exemplars.py            # incremental scan + summary
    python scripts/refresh_exemplars.py --status   # show library status only

Extracts Writing DNA, formatting patterns, section exemplars, and response patterns.
Historical content stays LOCAL (gitignored) and is STYLE guidance only — never facts.
No corpus content is printed. No OCR, no network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))


def _out(d):
    sys.stdout.buffer.write((json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _err(msg, code=1):
    sys.stderr.buffer.write((json.dumps(msg if isinstance(msg, dict) else {"error": msg},
                                        ensure_ascii=False) + "\n").encode("utf-8"))
    sys.exit(code)


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    from engine.tor.exemplars.exemplar_config import get_library_root
    from engine.tor.exemplars.scan import scan_library, _load_index, exemplar_cache_dir

    root = get_library_root()

    if "--status" in args:
        idx = _load_index(exemplar_cache_dir())
        _out({
            "configured": bool(root),
            "library_root": root,
            "projects_indexed": len(idx.get("exemplars", [])),
            "valid_pairs": sum(1 for e in idx.get("exemplars", []) if e.get("tor_file")),
            "countries": idx.get("countries", []),
            "assignment_types": idx.get("assignment_types", []),
            "last_refresh": idx.get("synced_at"),
            "writing_dna": idx.get("writing_dna", {}),
        })
        return 0

    if not root:
        _err({"status": "NOT_CONFIGURED",
              "message": "No Winning Proposal Library set. Run exemplar_library.py set <path>."}, 2)

    report = scan_library(root)
    if not report.get("ok"):
        _err(report, 5)
    # concise, no corpus content
    _out({
        "ok": True,
        "library_root": report["library_root"],
        "countries": report["countries"],
        "project_folders": report["project_folders"],
        "valid_pairs": report["valid_pairs"],
        "ambiguous": report["ambiguous"],
        "unreadable": report["unreadable"],
        "assignment_types": report["assignment_types"],
        "added": report["added"], "updated": report["updated"],
        "unchanged": report["unchanged"],
        "writing_dna": report["writing_dna"],
        "warnings": report["warnings"],
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
