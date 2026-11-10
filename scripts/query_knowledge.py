"""query_knowledge.py — deterministic ARFADA verified-fact lookup (Phase 4).

Usage:
    python scripts/query_knowledge.py version
    python scripts/query_knowledge.py metrics
    python scripts/query_knowledge.py fact <fact_id>
    python scripts/query_knowledge.py metric <metric_name>
    python scripts/query_knowledge.py search [--type T] [--country C] [--region R] [--sector S]

Returns verified facts with provenance. No network, no DB, no API. The Skill may
use this to show "ARFADA facts used" / "relevant experience used".
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _SCRIPT_DIR.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from engine.tor.knowledge import Knowledge


def _out(data) -> None:
    s = json.dumps(data, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write((s + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def _err(msg: str, code: int = 1) -> None:
    sys.stderr.buffer.write((json.dumps({"error": msg}) + "\n").encode("utf-8"))
    sys.exit(code)


def _parse_flags(args: list[str]) -> dict:
    flags = {}
    i = 0
    while i < len(args):
        if args[i].startswith("--") and i + 1 < len(args):
            flags[args[i][2:]] = args[i + 1]
            i += 2
        else:
            i += 1
    return flags


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    if not args:
        _err("Usage: query_knowledge.py <version|metrics|fact|metric|search> ...")

    k = Knowledge()
    cmd = args[0]

    if cmd == "version":
        _out({"knowledge_version": k.version})
    elif cmd == "metrics":
        _out({"knowledge_version": k.version, "metrics": k.metrics()})
    elif cmd == "fact":
        if len(args) < 2:
            _err("Usage: fact <fact_id>")
        f = k.fact(args[1])
        if f is None:
            _err(f"Fact '{args[1]}' not found (use a NEEDS_ARFADA_EVIDENCE placeholder)", 3)
        _out(f)
    elif cmd == "metric":
        if len(args) < 2:
            _err("Usage: metric <metric_name>")
        m = k.metric(args[1])
        if m is None:
            _err(f"Metric '{args[1]}' not found", 3)
        _out(m)
    elif cmd == "search":
        flags = _parse_flags(args[1:])
        projects = k.relevant_projects(
            assignment_type=flags.get("type"),
            country=flags.get("country"),
            region=flags.get("region"),
            sector=flags.get("sector"),
            limit=int(flags.get("limit", 5)),
        )
        _out({"knowledge_version": k.version, "count": len(projects), "projects": projects})
    else:
        _err(f"Unknown command: {cmd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
