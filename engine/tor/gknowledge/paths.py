"""User-local paths for ARFADA knowledge (outside the Git repo).

Tokens, caches, and downloaded CVs live here — NEVER in the plugin repo.
Cross-platform: honors ARFADA_HOME override, else ~/.arfada-proposal/.
"""
from __future__ import annotations

import os
from pathlib import Path


def arfada_home() -> Path:
    """Root user-local dir. Override with ARFADA_HOME (used by tests)."""
    override = os.environ.get("ARFADA_HOME")
    base = Path(override).expanduser() if override else Path.home() / ".arfada-proposal"
    base.mkdir(parents=True, exist_ok=True)
    return base


def user_config_dir() -> Path:
    d = arfada_home() / "config"
    d.mkdir(parents=True, exist_ok=True)
    return d


def google_dir() -> Path:
    d = arfada_home() / "google"
    d.mkdir(parents=True, exist_ok=True)
    return d


def token_path() -> Path:
    """OAuth token store (gitignored, user-local)."""
    return google_dir() / "token.json"


def client_secret_path() -> Path:
    """OAuth client secret (user-provided; never committed)."""
    # allow an env override so a team can point at a shared desktop client file
    override = os.environ.get("ARFADA_GOOGLE_CLIENT_SECRET")
    if override:
        return Path(override).expanduser()
    return google_dir() / "client_secret.json"


def user_cache_dir() -> Path:
    d = arfada_home() / "knowledge"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_files_dir() -> Path:
    d = user_cache_dir() / "files"
    d.mkdir(parents=True, exist_ok=True)
    return d
