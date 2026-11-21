"""repair_staff_country.py — re-derive staff-profile country fields in place.

Usage:
    python scripts/repair_staff_country.py            # repair + summary
    python scripts/repair_staff_country.py --check    # summary only, no write

Country = the first folder directly below "Staff CVs" (pools such as
"International Experts" set country_pool instead). Uses each profile's stored
source path — no CV is re-parsed, and only the staff index is written (Master
Tracker, company, brand, Writing DNA and run snapshots are untouched).
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


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    from engine.tor.gknowledge.cache import Cache
    from engine.tor.lknowledge import staff_country as SC

    cache = Cache()
    data = cache.staff()
    if not data or not data.get("profiles"):
        _out({"ok": False, "status": "NO_STAFF_INDEX",
              "message": "No staff profiles cached. Run refresh_knowledge.py first."})
        return 2
    if "--check" in args:
        profiles = [SC.apply_country(p, p["source_rel_path"]) if p.get("source_rel_path")
                    else p for p in data["profiles"]]
        _out({"ok": True, "mode": "CHECK", "profiles": len(profiles),
              **SC.summarize(profiles)})
        return 0
    _out({"ok": True, "mode": "REPAIR", **SC.repair_staff_index(cache)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
