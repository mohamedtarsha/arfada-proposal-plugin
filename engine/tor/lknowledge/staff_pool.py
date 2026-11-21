"""Persisted staff pool for team ranking.

Team ranking searches the PERSISTED staff index (normalized profiles) — it never
needs the raw Staff CVs folder. The index is found, in order of preference by
size, from:

1. ``ARFADA_STAFF_INDEX`` (explicit path, e.g. a mounted copy),
2. the user cache ``~/.arfada-proposal/knowledge/staff_index.json``,
3. a portable copy inside the Knowledge folder,
   ``<ARFADA Knowledge>/.arfada-index/staff_index.json`` — written on every refresh
   so a session that can only see the Knowledge folder (e.g. a sandbox) still gets
   the full pool without re-scanning or transferring CVs.

The largest valid index wins, so a partial re-scan (a subset of CV folders) can
never shrink the searchable pool. Raw CV text is read only for shortlisted
candidates, on demand (``shortlist_details``).
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

PORTABLE_DIR = ".arfada-index"
INDEX_NAME = "staff_index.json"
STAFF_SUB = "Staff CVs"


def portable_index_path(knowledge_root: str | Path) -> Path:
    return Path(knowledge_root) / PORTABLE_DIR / INDEX_NAME


def _read(path: Path) -> Optional[dict]:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) and isinstance(doc.get("profiles"), list) else None
    except Exception:
        return None


def _knowledge_root() -> Optional[str]:
    try:
        from .local_config import get_knowledge_root
        return get_knowledge_root()
    except Exception:
        return None


def _candidates() -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    env = os.environ.get("ARFADA_STAFF_INDEX")
    if env:
        out.append(("ENV_STAFF_INDEX", Path(env).expanduser()))
    try:
        from ..gknowledge.cache import Cache
        out.append(("USER_CACHE", Cache().staff_path))
    except Exception:
        pass
    root = _knowledge_root()
    if root:
        out.append(("KNOWLEDGE_FOLDER_INDEX", portable_index_path(root)))
    return out


def _normalize(profiles: list) -> list:
    """Ensure country attribution is present (older indexes predate v0.6.7)."""
    from .staff_country import apply_country
    out = []
    for p in profiles:
        if "country_status" not in p and p.get("source_rel_path"):
            p = apply_country(p, p["source_rel_path"])
        out.append(p)
    return out


def load_staff_pool(current: Optional[list] = None, current_label: str = "RUN") -> dict:
    """Return the largest available staff pool.

    ``current`` (e.g. a run snapshot's profiles) competes with the persisted
    indexes; the biggest valid pool is used. Returns ``profiles``, ``source``,
    ``path``, ``count`` and ``considered`` (each candidate's size).
    """
    considered = []
    best = {"profiles": list(current or []), "source": current_label if current else "NONE",
            "path": "", "synced_at": ""}
    if current:
        considered.append({"source": current_label, "count": len(current)})
    for label, path in _candidates():
        doc = _read(path) if Path(path).exists() else None
        if not doc:
            continue
        n = len(doc["profiles"])
        considered.append({"source": label, "count": n})
        if n > len(best["profiles"]) or (
                n == len(best["profiles"]) and n and best["source"] == "NONE"):
            best = {"profiles": doc["profiles"], "source": label, "path": str(path),
                    "synced_at": doc.get("synced_at", "")}
    best["profiles"] = _normalize(best["profiles"])
    best["count"] = len(best["profiles"])
    best["considered"] = considered
    return best


def publish_portable_index(cache, knowledge_root: str | Path, *,
                           allow_shrink: bool = False) -> dict:
    """Copy the cached staff index into the Knowledge folder (atomic, best effort).

    Without ``allow_shrink`` an existing larger portable index is kept, so a
    partial cache can never overwrite the full pool. A full scan of that same
    folder passes ``allow_shrink=True`` (removed CVs really are gone).
    """
    data = cache.staff()
    if not data or not data.get("profiles"):
        return {"published": False, "reason": "no staff index"}
    target = portable_index_path(knowledge_root)
    existing = _read(target) if target.exists() else None
    if (not allow_shrink and existing
            and len(existing["profiles"]) > len(data["profiles"])):
        return {"published": False, "reason": "existing portable index is larger",
                "existing": len(existing["profiles"]), "cache": len(data["profiles"])}
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, target)
        return {"published": True, "path": str(target), "count": len(data["profiles"])}
    except Exception as e:  # read-only / synced folder issues never fail a refresh
        return {"published": False, "reason": str(e)}


def cv_file_for(profile: dict, knowledge_root: Optional[str | Path] = None) -> Optional[Path]:
    """Path of a profile's raw CV under the Knowledge folder, if reachable."""
    rel = profile.get("source_rel_path")
    root = knowledge_root or _knowledge_root()
    if not rel or not root:
        return None
    p = Path(root) / STAFF_SUB / rel
    return p if p.exists() else None


def shortlist_details(profiles: list, *, knowledge_root: Optional[str | Path] = None,
                      max_chars: int = 6000) -> list[dict]:
    """Read raw CV text for SHORTLISTED candidates only (never the whole pool)."""
    from .scan import _extract_text
    out = []
    for p in profiles:
        f = cv_file_for(p, knowledge_root)
        if f is None:
            out.append({"staff_id": p.get("staff_id"), "status": "FILE_NOT_AVAILABLE_LOCALLY",
                        "source_rel_path": p.get("source_rel_path", "")})
            continue
        text = _extract_text(f)
        out.append({"staff_id": p.get("staff_id"), "status": "AVAILABLE" if text else "NO_TEXT",
                    "source_rel_path": p.get("source_rel_path", ""),
                    "text": text[:max_chars]})
    return out
