"""knowledge_status.py — show ARFADA knowledge source + freshness (spec §18).

Usage:
    python scripts/knowledge_status.py

Reports: Google connected, source mode, last sync, cache counts, freshness
(fresh < 24h, warning 1-7d, stale > 7d), and the static fallback version.
No credentials printed.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

FRESH_H = float(os.environ.get("ARFADA_FRESH_HOURS", "24"))
STALE_H = float(os.environ.get("ARFADA_STALE_HOURS", str(7 * 24)))


def _out(d):
    sys.stdout.buffer.write((json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _freshness(age_h):
    if age_h is None:
        return "NONE"
    if age_h < FRESH_H:
        return "FRESH"
    if age_h <= STALE_H:
        return "WARNING"
    return "STALE"


def main(argv=None) -> int:
    from engine.tor.gknowledge import auth
    from engine.tor.gknowledge.cache import Cache
    from engine.tor.gknowledge.config import load_sources
    from engine.tor.knowledge import knowledge_version

    cache = Cache()
    sources = load_sources()
    connected = auth.is_connected()
    age = cache.age_hours()

    projects = cache.projects()
    staff = cache.staff()
    company = cache.company()
    brand = cache.brand()

    source_mode = "STATIC_FALLBACK"
    if cache.has_any():
        source_mode = "LIVE_GOOGLE" if connected else "LIVE_GOOGLE_OFFLINE_CACHE"

    _out({
        "google_connected": connected,
        "source_mode": source_mode,
        "sources_configured": sources.is_configured(),
        "sources_config_path": sources.path,
        "last_sync": cache.last_sync(),
        "cache_age_hours": round(age, 1) if age is not None else None,
        "freshness": _freshness(age),
        "projects": {"synced": bool(projects), "count": (projects or {}).get("count", 0),
                     "metrics": {k: v.get("value") for k, v in (projects or {}).get("metrics", {}).items()}},
        "staff": {"synced": bool(staff), "profiles": (staff or {}).get("count", 0)},
        "company": {"synced": bool(company),
                    "documents": len((company or {}).get("facts", []))},
        "brand": {"available": bool((brand or {}).get("available"))},
        "static_fallback_version": knowledge_version(),
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
