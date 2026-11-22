"""arfada_policy.py — governed ARFADA organisation policies (v0.6.16).

Usage:
    python scripts/arfada_policy.py set previous-work-sharing --note "<the user's/admin's explicit confirmation>"
    python scripts/arfada_policy.py revoke previous-work-sharing [--note "<reason>"]
    python scripts/arfada_policy.py show

Stored once in ARFADA_HOME/governance/policies.json (not per run, never inferred). The
previous-work sharing policy clears ARFADA client evaluation reports for use as
previous-work samples, unless a report carries an explicit restriction.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from engine.tor import governance as G  # noqa: E402


def _out(d):
    sys.stdout.buffer.write((json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    note = args[args.index("--note") + 1] if "--note" in args and args.index("--note") + 1 < len(args) else ""
    if args[:1] == ["show"]:
        _out({G.PREVIOUS_WORK_SHARING: G.previous_work_sharing_policy() or "NOT SET"})
        return 0
    if args[:2] == ["set", "previous-work-sharing"]:
        res = G.set_previous_work_sharing_policy(note)
        _out(res)
        return 0 if res["ok"] else 4
    if args[:2] == ["revoke", "previous-work-sharing"]:
        _out(G.revoke_previous_work_sharing_policy(note))
        return 0
    sys.stderr.write(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
