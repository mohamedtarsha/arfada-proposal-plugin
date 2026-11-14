"""run_init.py — start-of-run initialization summary (v0.6.4 §1).

Usage:
    python scripts/run_init.py            # JSON status
    python scripts/run_init.py --compact  # compact human summary block

Verifies and reports Knowledge source, Master Tracker, Staff CVs, Company docs,
Previous Work library, Writing DNA, historical TOR↔Proposal pairs, plugin version,
and knowledge snapshot version. Does NOT regenerate or re-index anything — Writing
DNA / exemplars persist across sessions and are auto-discovered.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from engine.tor.run_init import gather_init_status, compact_summary


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    status = gather_init_status()
    if "--compact" in args:
        sys.stdout.buffer.write((compact_summary(status) + "\n").encode("utf-8"))
    else:
        sys.stdout.buffer.write(
            (json.dumps(status, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
