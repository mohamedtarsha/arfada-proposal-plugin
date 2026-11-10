"""exemplar_library.py — set / show / clear the Winning Proposal Library folder.

Usage:
    python scripts/exemplar_library.py show
    python scripts/exemplar_library.py set "C:/Users/<you>/Firass's Proposals"
    python scripts/exemplar_library.py clear

Stored in the user config dir (never the repo). Historical proposals = STYLE
exemplars only, never a factual source.
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
    sys.stderr.buffer.write((json.dumps({"error": msg}) + "\n").encode("utf-8"))
    sys.exit(code)


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    from engine.tor.exemplars.exemplar_config import (
        get_library_root, set_library_root, clear_library_root)
    if not args:
        _err("Usage: exemplar_library.py <show|set <path>|clear>")
    cmd = args[0]
    if cmd == "show":
        root = get_library_root()
        _out({"library_root": root, "configured": bool(root),
              "exists": bool(root and Path(root).exists())})
    elif cmd == "set":
        if len(args) < 2:
            _err("Usage: exemplar_library.py set <path>")
        res = set_library_root(args[1])
        if not res.get("ok"):
            _err(res.get("error", "failed"), 2)
        _out(res)
    elif cmd == "clear":
        clear_library_root()
        _out({"ok": True, "message": "Winning Proposal Library cleared."})
    else:
        _err(f"Unknown command: {cmd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
