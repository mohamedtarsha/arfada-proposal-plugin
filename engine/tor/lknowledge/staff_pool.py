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
import re
import tempfile
import unicodedata
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
    """Ensure country attribution (v0.6.7), the v0.6.9 years rule and the document
    type (v0.6.8) are applied.

    All are derived from fields the index already holds; nothing is re-parsed.
    """
    from .staff_country import apply_country
    from .staff_doctype import classify_document
    from ..gknowledge.normalize import revalidate_years
    out = []
    for p in profiles:
        if "country_status" not in p and p.get("source_rel_path"):
            p = apply_country(p, p["source_rel_path"])
        p = revalidate_years(p)                 # unsupported years -> None (UNVERIFIED)
        p = {**p, **classify_document(p)}       # uses the (re-checked) years
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


def portable_rel_parts(stored: str) -> Optional[list]:
    """Path segments of a stored CV path, portable across Windows / Linux / synced folders.

    v0.6.17: the index may hold Windows separators (``Sudan\\Expert\\cv.pdf``), POSIX
    separators, or an absolute machine-specific path. Both separators are accepted; an
    absolute path is re-anchored at its ``Staff CVs`` segment (Knowledge-root-relative);
    traversal (``..``) and drive / root anchors that cannot be re-anchored are refused.
    The stored value itself is never rewritten (it stays as provenance).
    """
    raw = str(stored or "").strip()
    if not raw:
        return None
    parts = [p for p in re.split(r"[\\/]+", raw) if p not in ("", ".")]
    low = [p.casefold() for p in parts]
    if STAFF_SUB.casefold() in low:                      # absolute / machine path → re-anchor
        parts = parts[len(low) - 1 - low[::-1].index(STAFF_SUB.casefold()) + 1:]
    elif re.match(r"^(?:[A-Za-z]:|[\\/]{1,2})", raw):    # absolute path outside Staff CVs
        return None
    if not parts or any(p == ".." or re.match(r"^[A-Za-z]:$", p) for p in parts):
        return None
    return parts


def _match_segment(directory: Path, name: str) -> Optional[Path]:
    """The child of ``directory`` named ``name`` — tolerant of case / Unicode form only."""
    exact = directory / name
    if exact.exists():
        return exact
    want = unicodedata.normalize("NFC", name).casefold()
    try:
        for child in directory.iterdir():
            if unicodedata.normalize("NFC", child.name).casefold() == want:
                return child
    except OSError:
        return None
    return None


def cv_file_for(profile: dict, knowledge_root: Optional[str | Path] = None) -> Optional[Path]:
    """Path of a profile's raw CV under the Knowledge folder, if reachable.

    Resolves the stored path portably (see ``portable_rel_parts``) against the CURRENT
    ``<Knowledge>/Staff CVs`` root and never returns a path outside that root.
    """
    root = knowledge_root or _knowledge_root()
    if not root:
        return None
    parts = portable_rel_parts(profile.get("source_rel_path") or "")
    if not parts:
        return None
    base = Path(root) / STAFF_SUB
    cur = base
    for seg in parts:
        nxt = _match_segment(cur, seg)
        if nxt is None:
            return None
        cur = nxt
    try:
        cur.resolve().relative_to(base.resolve())          # never outside the allowed root
    except (ValueError, OSError):
        return None
    return cur if cur.is_file() else None


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
