"""ARFADA source configuration — source IDs only, NEVER credentials.

Looks for arfada_sources.yaml in (first found wins):
1. $ARFADA_SOURCES (explicit path)
2. user config dir (~/.arfada-proposal/config/arfada_sources.yaml)
3. the plugin's config/arfada_sources.yaml (team-shared, in private repo)

Folder/sheet IDs are not secrets in the credential sense, so a team manifest
MAY live in the private repo. Tokens/secrets never do.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_DEPS = Path(__file__).resolve().parent.parent.parent.parent / ".mcp_deps"
if _DEPS.exists() and str(_DEPS) not in sys.path:
    sys.path.insert(0, str(_DEPS))

from .paths import user_config_dir


@dataclass
class SourceConfig:
    projects: dict = field(default_factory=dict)   # {type, spreadsheet_id, sheet_name, column_map?}
    staff: dict = field(default_factory=dict)       # {type, folder_id, subfolders_by_country}
    company: dict = field(default_factory=dict)
    brand: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)
    path: Optional[str] = None

    def is_configured(self) -> bool:
        return bool(self.projects or self.staff or self.company or self.brand)


def _plugin_config_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent / "config" / "arfada_sources.yaml"


def candidate_paths() -> list[Path]:
    out: list[Path] = []
    env = os.environ.get("ARFADA_SOURCES")
    if env:
        out.append(Path(env).expanduser())
    out.append(user_config_dir() / "arfada_sources.yaml")
    out.append(_plugin_config_path())
    return out


def load_sources() -> SourceConfig:
    import yaml
    for p in candidate_paths():
        if p.exists():
            with p.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return SourceConfig(
                projects=data.get("projects", {}) or {},
                staff=data.get("staff", {}) or {},
                company=data.get("company", {}) or {},
                brand=data.get("brand", {}) or {},
                raw=data,
                path=str(p),
            )
    return SourceConfig()
