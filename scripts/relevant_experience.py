"""relevant_experience.py — rank past assignments for THIS TOR (v0.6.4 §5).

Usage:
    python scripts/relevant_experience.py <run_dir> [--limit N]

Ranks Master Tracker assignments by country, assignment/evaluation type, sector(s),
client/donor, and thematic similarity to the current TOR, EXCLUDING the current
TOR/project from retrieval (so a proposal never cites itself). The run-scoped
exclusion does NOT change ARFADA's global portfolio count — `global_total_projects`
is reported from the verified full-tracker metric, unchanged.

Emits ranked candidates the SKILL presents as selection cards; the user picks the
final 3–5. No selection is auto-made.
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


def _mv(meta, k):
    e = meta.get(k)
    return (e.get("value", "") if isinstance(e, dict) else "").strip()


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        sys.stderr.write("Usage: relevant_experience.py <run_dir> [--limit N]\n")
        return 1
    run_dir = Path(args[0]).expanduser().resolve()
    limit = 8
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    tor = {}
    tp = run_dir / "tor_analysis.json"
    if tp.exists():
        tor = json.loads(tp.read_text(encoding="utf-8"))
    meta = tor.get("metadata", {})
    at = tor.get("assignment_type", {})
    assignment_type = at.get("assignment_type") or at.get("type") or ""
    country = _mv(meta, "country")
    sector = _mv(meta, "sector")
    client = _mv(meta, "client")
    assignment_title = _mv(meta, "assignment") or _mv(meta, "title")

    from engine.tor.knowledge import Knowledge
    k = Knowledge(run_dir=run_dir)

    current = {"project_name": assignment_title, "assignment": assignment_title,
               "country": country, "assignment_type": assignment_type}
    ranked = k.relevant_projects(
        assignment_type=assignment_type or None,
        country=country or None,
        sector=sector or None,
        client=client or None,
        evaluation_type=assignment_type or None,
        thematic=assignment_title or None,
        exclude_current=current,
        limit=limit,
    )

    # global portfolio count comes from the verified full-tracker metric (unchanged
    # by the run-scoped exclusion above).
    global_total = None
    for m in (k.metrics() or []):
        if m.get("metric") == "total_projects" or m.get("fact_id") == "metric_total_projects":
            global_total = m.get("value")
            break

    card = {
        "header": "Experience",
        "question": "Select the 3–5 strongest past assignments to feature for this TOR.",
        "multi_select": True,
        "select_min": 3,
        "select_max": 5,
        "note": "Ranked by relevance to this TOR; the current assignment is excluded. "
                "No selection is auto-made.",
        "options": [
            {
                "label": f"{p.get('project_name') or p.get('project_id')} "
                         f"({p.get('country','')}, {p.get('assignment_type','')}) "
                         f"— score {p.get('match_score')}",
                "value": p.get("project_id") or p.get("fact_id"),
                "scored_on": p.get("scored_on", {}),
            }
            for p in ranked
        ],
    }

    _out({
        "run_id": run_dir.name,
        "current_assignment": {"type": assignment_type, "country": country,
                               "client": client, "title": assignment_title},
        "global_total_projects": global_total,
        "candidates": ranked,
        "selection_card": card,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
