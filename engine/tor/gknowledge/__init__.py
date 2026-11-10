"""ARFADA live Google Workspace knowledge connector (Phase 4.1, local-only).

Google Drive/Sheets become the LIVE operational source of truth; the static
knowledge/ snapshot remains an explicit STATIC_FALLBACK. Everything runs locally
(OAuth desktop flow, local cache) — no VPS, no MCP server, no Anthropic API.

Public surface:
- paths:    user config/cache locations (outside the repo)
- config:   arfada_sources.yaml loader (source IDs, never credentials)
- auth:     OAuth desktop flow + token storage (user dir, gitignored)
- clients:  DriveClient / SheetsClient (injectable for tests)
- normalize: project rows → records + metrics; CV files → profiles
- sync:     incremental, transactional cache build
- cache:    local normalized store
- snapshot: per-run frozen knowledge snapshot + manifest
"""
from .paths import user_config_dir, user_cache_dir, token_path
from .config import load_sources, SourceConfig
