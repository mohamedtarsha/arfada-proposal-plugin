"""knowledge_folder.py — set / show / change the local ARFADA Knowledge folder.

Usage:
    python scripts/knowledge_folder.py show
    python scripts/knowledge_folder.py set "<path to ARFADA Knowledge>"
    python scripts/knowledge_folder.py clear

Stores the path in the user config dir (not the repo). The folder may be a plain
folder or a Drive/OneDrive/Dropbox synced folder — the plugin only sees the path.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))


def _out(d):
    sys.stdout.buffer.write((json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _err(msg, code=1):
    sys.stderr.buffer.write((json.dumps({"error": msg}) + "\n").encode("utf-8"))
    sys.exit(code)


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    from engine.tor.lknowledge import local_config as LC
    if not args:
        _err("Usage: knowledge_folder.py <show|set <path>|clear>")
    cmd = args[0]
    if cmd == "show":
        root = LC.get_knowledge_root()
        _out({"knowledge_root": root, "configured": bool(root),
              "exists": bool(root and Path(root).exists())})
    elif cmd == "set":
        if len(args) < 2:
            _err("Usage: knowledge_folder.py set <path>")
        res = LC.set_knowledge_root(args[1])
        if not res.get("ok"):
            _err(res.get("error", "failed"), 2)
        _out(res)
    elif cmd == "clear":
        LC.clear_knowledge_root()
        _out({"ok": True, "message": "Local knowledge folder cleared."})
    else:
        _err(f"Unknown command: {cmd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
