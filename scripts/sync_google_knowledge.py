"""sync_google_knowledge.py — incremental sync from Google → local cache.

Usage:
    python scripts/sync_google_knowledge.py

Reads arfada_sources.yaml, loads local OAuth creds, builds real Drive/Sheets
clients, and runs a transactional incremental sync. On any hard failure the
previous valid cache is kept. Prints an added/updated/unchanged/removed report.
No credentials are printed.
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
    from engine.tor.gknowledge import auth, sync as S
    from engine.tor.gknowledge.config import load_sources
    from engine.tor.gknowledge.clients import DriveClient, SheetsClient
    from engine.tor.gknowledge.cache import Cache

    sources = load_sources()
    if not sources.is_configured():
        _err("No arfada_sources.yaml configured — register source IDs first "
             "(see config/arfada_sources.example.yaml).", 2)

    creds = auth.load_credentials()
    if creds is None:
        _err("Google not connected (or token expired). Run connect_google.py first.", 3)

    try:
        drive = DriveClient(creds)
        sheets = SheetsClient(creds)
    except Exception as e:
        _err(f"Failed to build Google clients: {e}", 4)

    report = S.run_sync(sources=sources, drive=drive, sheets=sheets, cache=Cache())
    _out(report)
    return 0 if report.get("ok") else 5


if __name__ == "__main__":
    sys.exit(main())
