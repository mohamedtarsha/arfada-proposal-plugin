"""Single source of truth for runtime metadata (v0.6.4, production hardening §12).

Never hard-code plugin versions (e.g. "0.5.0") in scripts or the DOCX footer.
`plugin_version()` reads `.claude-plugin/plugin.json`; `knowledge_snapshot_version()`
reads the frozen per-run snapshot manifest (falling back to the static knowledge
version). These feed the internal provenance footer and every QA/export report.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
_PLUGIN_JSON = _PLUGIN_ROOT / ".claude-plugin" / "plugin.json"


@lru_cache(maxsize=1)
def plugin_version() -> str:
    """Current plugin version from .claude-plugin/plugin.json (authoritative)."""
    try:
        data = json.loads(_PLUGIN_JSON.read_text(encoding="utf-8"))
        v = str(data.get("version", "")).strip()
        if v:
            return v
    except Exception:
        pass
    return "unknown"


def _static_knowledge_version() -> str:
    try:
        from .knowledge import knowledge_version
        return knowledge_version()
    except Exception:
        return "unknown"


def knowledge_snapshot_version(run_dir: str | Path) -> str:
    """Snapshot version/date for THIS run, or the static knowledge version.

    Prefers the immutable per-run snapshot manifest written at generation time so
    the footer reflects what the proposal was actually built from.
    """
    run_dir = Path(run_dir)
    man_path = run_dir / "knowledge_snapshot" / "knowledge_manifest.json"
    try:
        man = json.loads(man_path.read_text(encoding="utf-8"))
        for key in ("knowledge_version", "snapshot_version", "version",
                    "created_at", "snapshot_id"):
            v = man.get(key)
            if v:
                return str(v)
    except Exception:
        pass
    return _static_knowledge_version()


def runtime_metadata(run_dir: Optional[str | Path] = None) -> dict:
    """Bundle used by footers / reports: actual plugin + snapshot version + run id."""
    md = {"plugin_version": plugin_version()}
    if run_dir is not None:
        run_dir = Path(run_dir)
        md["knowledge_snapshot_version"] = knowledge_snapshot_version(run_dir)
        md["run_id"] = run_dir.name
    return md
