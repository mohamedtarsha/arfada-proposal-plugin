"""Winning Proposal Library configuration (user config dir, not the repo).

library_root is a single local folder of past winning proposals. It may be a plain
folder or a synced (Drive/OneDrive/Dropbox) folder — the plugin only sees a path.
ARFADA_EXEMPLAR_ROOT env var overrides (tests).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from ..gknowledge.paths import user_config_dir

_CONFIG_NAME = "exemplar_library.json"


def _config_path() -> Path:
    return user_config_dir() / _CONFIG_NAME


def get_library_root() -> Optional[str]:
    env = os.environ.get("ARFADA_EXEMPLAR_ROOT")
    if env:
        return str(Path(env).expanduser())
    p = _config_path()
    if p.exists():
        try:
            root = json.loads(p.read_text(encoding="utf-8")).get("library_root")
            return str(Path(root).expanduser()) if root else None
        except Exception:
            return None
    return None


def set_library_root(path: str) -> dict:
    p = Path(path).expanduser()
    warnings = []
    if not p.exists():
        warnings.append("Folder does not exist yet.")
    elif not p.is_dir():
        return {"ok": False, "error": f"Not a directory: {p}"}
    _config_path().write_text(
        json.dumps({"library_root": str(p)}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(p), "exists": p.exists(), "warnings": warnings}


def clear_library_root() -> None:
    p = _config_path()
    if p.exists():
        p.unlink()
