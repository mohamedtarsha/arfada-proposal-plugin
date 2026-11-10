"""generation_status.py — report current draft-generation state (resume support).

Usage:
    python scripts/generation_status.py <run_dir>
    python scripts/generation_status.py <run_dir> --next   # next section to generate

Prints section-by-section status and the next PENDING section (if any).
No LLM, no network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from engine.tor.generation import next_pending_section


def _out(data: dict) -> None:
    s = json.dumps(data, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write((s + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def _err(msg: str, code: int = 1) -> None:
    sys.stderr.buffer.write((json.dumps({"error": msg}) + "\n").encode("utf-8"))
    sys.exit(code)


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        _err("Usage: generation_status.py <run_dir> [--next]")
    run_dir = Path(args[0]).expanduser().resolve()
    status_path = run_dir / "generation_status.json"
    if not status_path.exists():
        _err("generation_status.json missing — run build_blueprint.py first", 2)

    with status_path.open(encoding="utf-8") as f:
        status_doc = json.load(f)

    if "--next" in args:
        nxt = next_pending_section(status_doc)
        _out({"next_section": nxt})
        return 0

    secs = sorted(status_doc["sections"].values(), key=lambda s: s["sequence"])
    counts: dict[str, int] = {}
    for s in secs:
        counts[s["status"]] = counts.get(s["status"], 0) + 1

    _out({
        "run_id": status_doc.get("run_id"),
        "counts": counts,
        "next_section": next_pending_section(status_doc),
        "sections": [
            {"section_id": s["section_id"], "title": s["title"],
             "status": s["status"], "attempts": s["attempts"],
             "needs_arfada_evidence": s.get("needs_arfada_evidence", False)}
            for s in secs
        ],
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
