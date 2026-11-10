"""Local knowledge-root configuration (stored in the user config dir, not the repo).

knowledge_root is a single filesystem path chosen by the user. No username/drive
letter is hard-coded. An ARFADA_KNOWLEDGE_ROOT env var overrides (used by tests).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from ..gknowledge.paths import user_config_dir

_CONFIG_NAME = "local_knowledge.json"


def _config_path() -> Path:
    return user_config_dir() / _CONFIG_NAME


def get_knowledge_root() -> Optional[str]:
    env = os.environ.get("ARFADA_KNOWLEDGE_ROOT")
    if env:
        return str(Path(env).expanduser())
    p = _config_path()
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            root = data.get("knowledge_root")
            return str(Path(root).expanduser()) if root else None
        except Exception:
            return None
    return None


def set_knowledge_root(path: str) -> dict:
    """Validate + persist the knowledge root. Returns {ok, path, exists, warnings}."""
    p = Path(path).expanduser()
    warnings = []
    if not p.exists():
        warnings.append("Folder does not exist yet.")
    elif not p.is_dir():
        return {"ok": False, "error": f"Not a directory: {p}"}
    else:
        for sub in ("Projects", "Staff CVs", "Company", "Brand"):
            if not (p / sub).exists():
                warnings.append(f"Recommended subfolder missing: {sub}/")
    _config_path().write_text(
        json.dumps({"knowledge_root": str(p)}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return {"ok": True, "path": str(p), "exists": p.exists(), "warnings": warnings}


def clear_knowledge_root() -> None:
    p = _config_path()
    if p.exists():
        p.unlink()
