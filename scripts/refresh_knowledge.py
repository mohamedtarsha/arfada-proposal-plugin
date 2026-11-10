"""refresh_knowledge.py — refresh the ARFADA knowledge cache from the active source.

Usage:
    python scripts/refresh_knowledge.py

Priority: if a LOCAL_FOLDER knowledge root is configured, scan it (no OAuth, no
API). Otherwise, if Google is connected + sources configured, sync Google.
Otherwise report STATIC_FALLBACK. Incremental + transactional; a failed refresh
keeps the previous valid cache.
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
    sys.stderr.buffer.write((json.dumps(msg if isinstance(msg, dict) else {"error": msg},
                                        ensure_ascii=False) + "\n").encode("utf-8"))
    sys.exit(code)


def main(argv=None) -> int:
    from engine.tor.lknowledge import local_config as LC
    from engine.tor.gknowledge.cache import Cache

    root = LC.get_knowledge_root()
    if root:
        from engine.tor.lknowledge.scan import scan_local_folder
        report = scan_local_folder(root, cache=Cache())
        report["source_mode"] = "LOCAL_FOLDER"
        _out(_summary(report))
        return 0 if report.get("ok") else 5

    # fall back to the optional Google API connector only if explicitly set up
    from engine.tor.gknowledge import auth
    from engine.tor.gknowledge.config import load_sources
    sources = load_sources()
    if auth.is_connected() and sources.is_configured():
        from engine.tor.gknowledge import sync as S
        from engine.tor.gknowledge.clients import DriveClient, SheetsClient
        creds = auth.load_credentials()
        report = S.run_sync(sources=sources, drive=DriveClient(creds),
                            sheets=SheetsClient(creds), cache=Cache())
        report["source_mode"] = "GOOGLE_API"
        _out(report)
        return 0 if report.get("ok") else 5

    _err({"status": "NO_SOURCE", "source_mode": "STATIC_FALLBACK",
          "message": "No local knowledge folder set and Google not configured. "
                     "Run knowledge_folder.py set <path> (recommended)."}, 2)


def _summary(report: dict) -> dict:
    p = report.get("projects", {}) or {}
    s = report.get("staff", {}) or {}
    c = report.get("company", {}) or {}
    b = report.get("brand", {}) or {}
    m = p.get("metrics", {}) or {}
    return {
        "ok": report.get("ok"),
        "source_mode": "LOCAL_FOLDER",
        "knowledge_root": report.get("knowledge_root"),
        "summary": {
            "projects": m.get("total_projects"),
            "countries": m.get("countries"),
            "surveys": m.get("total_surveys"),
            "kii": m.get("total_kii"),
            "fgd": m.get("total_fgd"),
            "cvs_indexed": s.get("profiles"),
            "cv_updated": s.get("added", 0) + s.get("updated", 0),
            "cv_unavailable": s.get("unavailable", 0),
            "company_files": c.get("documents"),
            "logo_found": b.get("available"),
        },
        "warnings": _warnings(report),
        "detail": report,
    }


def _warnings(report: dict) -> list:
    w = []
    if (report.get("projects", {}) or {}).get("status") not in ("OK", None):
        w.append(f"projects: {report['projects'].get('status')}")
    su = report.get("staff_unavailable")
    if su:
        w.append(f"{len(su)} CV file(s) not available locally (cloud placeholder)")
    low = (report.get("staff", {}) or {}).get("low_confidence")
    if low:
        w.append(f"{low} CV(s) low-confidence (possibly scanned)")
    return w


if __name__ == "__main__":
    sys.exit(main())
