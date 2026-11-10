"""Local normalized knowledge cache (outside the repo). Atomic writes.

Layout (under ~/.arfada-proposal/knowledge/):
  projects.json        normalized project records + metrics
  staff_index.json     normalized staff profiles (no full CV text)
  company_index.json   normalized company facts
  brand.json           brand asset pointers + local logo path
  source_state.json    per-file/sheet sync state (id → modifiedTime/hash)
  files/               cached downloaded blobs (CVs, logo)
"""
from __future__ import annotations

import datetime
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from .paths import user_cache_dir


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp", prefix="cache_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        with open(tmp, encoding="utf-8") as f:
            json.load(f)  # validate
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


class Cache:
    def __init__(self, base: Optional[Path] = None):
        self.base = Path(base) if base else user_cache_dir()
        self.base.mkdir(parents=True, exist_ok=True)

    # --- paths ---
    @property
    def projects_path(self): return self.base / "projects.json"
    @property
    def staff_path(self): return self.base / "staff_index.json"
    @property
    def company_path(self): return self.base / "company_index.json"
    @property
    def brand_path(self): return self.base / "brand.json"
    @property
    def state_path(self): return self.base / "source_state.json"
    @property
    def files_dir(self):
        d = self.base / "files"; d.mkdir(parents=True, exist_ok=True); return d

    # --- read ---
    def projects(self) -> Optional[dict]: return _read(self.projects_path)
    def staff(self) -> Optional[dict]: return _read(self.staff_path)
    def company(self) -> Optional[dict]: return _read(self.company_path)
    def brand(self) -> Optional[dict]: return _read(self.brand_path)
    def state(self) -> dict: return _read(self.state_path) or {"sources": {}}

    def has_any(self) -> bool:
        return self.projects_path.exists() or self.staff_path.exists()

    def last_sync(self) -> Optional[str]:
        st = self.state()
        return st.get("last_sync")

    def age_hours(self) -> Optional[float]:
        ls = self.last_sync()
        if not ls:
            return None
        try:
            then = datetime.datetime.fromisoformat(ls)
            now = datetime.datetime.now(datetime.timezone.utc)
            return (now - then).total_seconds() / 3600.0
        except Exception:
            return None

    # --- write ---
    def write_projects(self, projects: list, metrics: dict, source: dict) -> None:
        _atomic_write(self.projects_path, {
            "synced_at": _now(), "source": source,
            "count": len(projects), "metrics": metrics, "projects": projects})

    def write_staff(self, profiles: list, source: dict) -> None:
        _atomic_write(self.staff_path, {
            "synced_at": _now(), "source": source,
            "count": len(profiles), "profiles": profiles})

    def write_company(self, facts: list, source: dict) -> None:
        _atomic_write(self.company_path, {
            "synced_at": _now(), "source": source, "facts": facts})

    def write_brand(self, info: dict) -> None:
        _atomic_write(self.brand_path, {"synced_at": _now(), **info})

    def write_state(self, state: dict) -> None:
        state = dict(state)
        state["last_sync"] = _now()
        _atomic_write(self.state_path, state)
