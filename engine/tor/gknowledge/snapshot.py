"""Proposal-time frozen knowledge snapshot (spec §21-22).

At the start of proposal generation, freeze the knowledge actually relevant to
the run into arfada-output/<run_id>/knowledge_snapshot/ with a manifest. Once
created, that proposal uses its frozen snapshot — Google changes during the run
do NOT leak in. A new snapshot is created only on explicit refresh.

Source priority baked into the snapshot (spec §27):
1. frozen run snapshot (this file, once created)
2. latest validated live Google cache
3. static Git snapshot fallback (clearly labeled STATIC_FALLBACK)
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from .cache import Cache

SNAPSHOT_DIR = "knowledge_snapshot"
MANIFEST = "knowledge_manifest.json"


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _hash(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise


def snapshot_exists(run_dir: Path) -> bool:
    return (Path(run_dir) / SNAPSHOT_DIR / MANIFEST).exists()


def create_snapshot(run_dir: Path, *, cache: Optional[Cache] = None,
                    plugin_version: str = "0.5.1", force: bool = False,
                    offline: bool = False) -> dict:
    """Freeze current knowledge into the run dir. Idempotent unless force=True.

    Determines the active source: live cache if present, else STATIC_FALLBACK.
    Returns the manifest.
    """
    run_dir = Path(run_dir)
    snap_dir = run_dir / SNAPSHOT_DIR
    if snapshot_exists(run_dir) and not force:
        return json.loads((snap_dir / MANIFEST).read_text(encoding="utf-8"))

    cache = cache or Cache()
    snap_dir.mkdir(parents=True, exist_ok=True)

    source_mode = "STATIC_FALLBACK"
    projects_doc = None
    staff_doc = None
    company_doc = None
    brand_doc = None

    if cache.has_any():
        # Origin recorded by the sync/scan that wrote the cache.
        origin = cache.source_mode() or "LIVE_GOOGLE"
        # "offline" only applies to the Google API source — local files are always
        # local, so a LOCAL_FOLDER snapshot is never "offline".
        if offline and origin == "GOOGLE_API":
            source_mode = "GOOGLE_API_OFFLINE_CACHE"
        else:
            source_mode = origin
        projects_doc = cache.projects()
        staff_doc = cache.staff()
        company_doc = cache.company()
        brand_doc = cache.brand()
    else:
        # static fallback — copy the Git-versioned snapshot values
        from ..knowledge import Knowledge
        k = Knowledge()
        projects_doc = {"synced_at": None, "source": {"type": "static_fallback"},
                        "count": len(k._projects.get("projects", [])),
                        "metrics": {m["metric"]: {"value": m["value"]} for m in k.metrics()},
                        "projects": k._projects.get("projects", [])}

    # freeze files
    if projects_doc is not None:
        _write(snap_dir / "projects.json", projects_doc)
    if staff_doc is not None:
        _write(snap_dir / "staff_index.json", staff_doc)
    if company_doc is not None:
        _write(snap_dir / "company_index.json", company_doc)
    if brand_doc is not None:
        _write(snap_dir / "brand.json", brand_doc)

    manifest = {
        "snapshot_id": "snap_" + _now().replace(":", "").replace("-", "")[:15],
        "created_at": _now(),
        "plugin_version": plugin_version,
        "source_mode": source_mode,          # LIVE_GOOGLE | LIVE_GOOGLE_OFFLINE_CACHE | STATIC_FALLBACK
        "static_knowledge_version": _static_version(),
        "google_last_sync": cache.last_sync() if cache.has_any() else None,
        "projects_revision": _hash(projects_doc) if projects_doc else None,
        "projects_count": (projects_doc or {}).get("count", 0),
        "staff_revision": _hash(staff_doc) if staff_doc else None,
        "staff_count": (staff_doc or {}).get("count", 0),
        "company_revision": _hash(company_doc) if company_doc else None,
        "google_sources": _source_identities(cache) if cache.has_any() else {},
        "immutable": True,
    }
    _write(snap_dir / MANIFEST, manifest)
    return manifest


def load_manifest(run_dir: Path) -> Optional[dict]:
    p = Path(run_dir) / SNAPSHOT_DIR / MANIFEST
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def snapshot_projects(run_dir: Path) -> list:
    p = Path(run_dir) / SNAPSHOT_DIR / "projects.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("projects", [])


def snapshot_metrics(run_dir: Path) -> dict:
    p = Path(run_dir) / SNAPSHOT_DIR / "projects.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8")).get("metrics", {})


def snapshot_staff(run_dir: Path) -> list:
    p = Path(run_dir) / SNAPSHOT_DIR / "staff_index.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("profiles", [])


def _static_version() -> str:
    from ..knowledge import knowledge_version
    return knowledge_version()


def _source_identities(cache: Cache) -> dict:
    out = {}
    pj = cache.projects()
    if pj:
        out["projects"] = pj.get("source", {})
    sf = cache.staff()
    if sf:
        out["staff"] = sf.get("source", {})
    return out
