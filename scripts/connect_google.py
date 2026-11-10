"""connect_google.py — one-time local Google OAuth (desktop flow).

Usage:
    python scripts/connect_google.py            # start browser consent
    python scripts/connect_google.py --status   # show connection status
    python scripts/connect_google.py --disconnect

Opens the browser for the user to authorize READ-ONLY Drive + Sheets access.
Tokens are stored under the user config dir (gitignored), never printed.
Requires a desktop-app client_secret.json (see assets/brand/README or SKILL).
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
    from engine.tor.gknowledge import auth
    from engine.tor.gknowledge.paths import token_path, client_secret_path

    if "--status" in args:
        _out({"connected": auth.is_connected(),
              "token_store": str(token_path()),
              "client_secret_expected": str(client_secret_path())})
        return 0
    if "--disconnect" in args:
        auth.disconnect()
        _out({"connected": False, "message": "Disconnected — token removed."})
        return 0

    try:
        auth.run_oauth_flow()
    except FileNotFoundError as e:
        _err(str(e), 2)
    except Exception as e:
        _err(f"OAuth failed: {e}", 3)
    _out({"connected": True, "message": "Google Workspace connected (read-only)."})
    return 0


if __name__ == "__main__":
    sys.exit(main())
