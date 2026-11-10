"""Google OAuth desktop flow (local, per-user). Read-only scopes only.

Tokens are stored under the user config dir (gitignored) — NEVER in the repo,
NEVER printed. A missing/expired token triggers a browser consent flow via
google-auth-oauthlib's InstalledAppFlow (run from connect_google.py).

This module intentionally does NO printing of token material.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

_DEPS = Path(__file__).resolve().parent.parent.parent.parent / ".mcp_deps"
if _DEPS.exists() and str(_DEPS) not in sys.path:
    sys.path.insert(0, str(_DEPS))

from .paths import token_path, client_secret_path

# Least-privilege, read-only scopes (spec §4).
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]


def is_connected() -> bool:
    return token_path().exists()


def load_credentials():
    """Return valid google Credentials, refreshing if needed, or None.

    Never raises on a missing token (returns None) so callers can fall back to
    cache/offline. Raises only on a genuinely corrupt token.
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    tp = token_path()
    if not tp.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(tp), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save(creds)
        except Exception:
            return None
    return creds if creds and creds.valid else None


def run_oauth_flow() -> bool:
    """Interactive browser consent. Returns True on success.

    Requires a client_secret.json (desktop app). Run from connect_google.py.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    secret = client_secret_path()
    if not secret.exists():
        raise FileNotFoundError(
            f"Google OAuth client secret not found at {secret}. Place a desktop-app "
            "client_secret.json there (or set ARFADA_GOOGLE_CLIENT_SECRET)."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
    creds = flow.run_local_server(port=0)
    _save(creds)
    return True


def _save(creds) -> None:
    tp = token_path()
    tp.write_text(creds.to_json(), encoding="utf-8")
    # best-effort tighten perms (POSIX)
    try:
        import os
        os.chmod(tp, 0o600)
    except Exception:
        pass


def disconnect() -> None:
    tp = token_path()
    if tp.exists():
        tp.unlink()
