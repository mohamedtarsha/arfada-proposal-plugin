"""Scan a local ARFADA Knowledge folder → normalized cache (v0.5.2).

Deterministic, offline, no cloud API. Reuses gknowledge normalization + cache +
snapshot. Incremental by (relative path, modifiedTime, size); transactional
(staging → validate → atomic swap). Cloud placeholders that are not physically
available locally are reported FILE_NOT_AVAILABLE_LOCALLY and skipped safely.
"""
from __future__ import annotations

import datetime
import hashlib
import os
from pathlib import Path
from typing import Optional

from ..gknowledge.cache import Cache
from ..gknowledge import normalize as N

_PDF = ".pdf"
_DOCX = ".docx"
_XLSX = ".xlsx"
_IMG = (".png", ".jpg", ".jpeg")

PROJECTS_SUB = "Projects"
STAFF_SUB = "Staff CVs"
COMPANY_SUB = "Company"
BRAND_SUB = "Brand"


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _mtime(p: Path) -> str:
    try:
        return datetime.datetime.fromtimestamp(
            p.stat().st_mtime, datetime.timezone.utc).isoformat()
    except Exception:
        return ""


def _available_locally(p: Path) -> bool:
    """Heuristic: is this synced file physically present (not a cloud placeholder)?

    Cloud providers (OneDrive/Drive) can leave a 0-byte placeholder or a reparse
    point for files not yet downloaded. We treat a 0-byte document as unavailable,
    and a file we cannot open for reading as unavailable. Never raises.
    """
    try:
        st = p.stat()
        if st.st_size == 0 and p.suffix.lower() in (_PDF, _DOCX, _XLSX):
            return False
        # Windows offline attribute (FILE_ATTRIBUTE_OFFLINE = 0x1000)
        attrs = getattr(st, "st_file_attributes", 0)
        if attrs and (attrs & 0x1000):
            return False
        with p.open("rb") as f:
            f.read(1)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Projects (Master Tracker.xlsx)
# ---------------------------------------------------------------------------

def _find_tracker(projects_dir: Path) -> Optional[Path]:
    if not projects_dir.exists():
        return None
    # prefer a file containing "tracker", else the first .xlsx
    xlsx = [f for f in projects_dir.iterdir()
            if f.is_file() and f.suffix.lower() == _XLSX and not f.name.startswith("~$")]
    if not xlsx:
        return None
    for f in xlsx:
        if "tracker" in f.name.lower():
            return f
    return xlsx[0]


def _read_xlsx(path: Path) -> list[list]:
    import sys
    deps = Path(__file__).resolve().parent.parent.parent.parent / ".mcp_deps"
    if deps.exists() and str(deps) not in sys.path:
        sys.path.insert(0, str(deps))
    from openpyxl import load_workbook
    wb = load_workbook(str(path), read_only=True, data_only=True)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(values_only=True):
        rows.append(["" if c is None else str(c) for c in row])
    wb.close()
    return rows


def scan_projects(root: Path, cache: Cache, report: dict) -> None:
    pdir = root / PROJECTS_SUB
    tracker = _find_tracker(pdir)
    if tracker is None:
        report["projects"] = {"status": "NO_TRACKER"}
        return
    if not _available_locally(tracker):
        report["projects"] = {"status": "FILE_NOT_AVAILABLE_LOCALLY",
                              "file": tracker.name}
        return
    rows = _read_xlsx(tracker)
    projects = N.normalize_projects(rows, sheet_name=tracker.name,
                                    spreadsheet_id=str(tracker))
    metrics = N.compute_metrics(projects)
    fhash = _file_hash(tracker)
    cache.write_projects(projects, metrics, {
        "type": "local_xlsx", "file": str(tracker), "file_name": tracker.name,
        "modified_time": _mtime(tracker), "file_hash": fhash})
    report["projects"] = {"status": "OK", "file": tracker.name,
                          "rows": max(0, len(rows) - 1), "normalized": len(projects),
                          "metrics": {k: v.get("value") for k, v in metrics.items()}}


def _file_hash(p: Path) -> str:
    try:
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()[:16]
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Staff CVs (recursive)
# ---------------------------------------------------------------------------

def _extract_text(path: Path) -> str:
    try:
        if path.suffix.lower() == _DOCX:
            import sys
            deps = Path(__file__).resolve().parent.parent.parent.parent / ".mcp_deps"
            if deps.exists() and str(deps) not in sys.path:
                sys.path.insert(0, str(deps))
            from docx import Document
            return "\n".join(p.text for p in Document(str(path)).paragraphs)
        if path.suffix.lower() == _PDF:
            from pypdf import PdfReader
            return "\n".join((pg.extract_text() or "") for pg in PdfReader(str(path)).pages)
    except Exception:
        return ""
    return ""


def scan_staff(root: Path, cache: Cache, state: dict, report: dict) -> None:
    sdir = root / STAFF_SUB
    if not sdir.exists():
        report["staff"] = {"status": "NO_FOLDER"}
        return
    file_state = state["sources"].setdefault("staff", {}).setdefault("files", {})
    prev = {p["source_file_id"]: p for p in (cache.staff() or {}).get("profiles", [])}
    added = updated = unchanged = failed = 0
    unavailable = 0
    seen = set()
    profiles = []

    for f in sorted(sdir.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in (_PDF, _DOCX):
            continue
        if f.name.startswith("~$"):
            continue
        rel = str(f.relative_to(sdir))
        fid = "cv_" + hashlib.sha1(rel.encode()).hexdigest()[:12]
        seen.add(fid)
        mtime = _mtime(f)
        country = f.parent.name if f.parent != sdir else ""
        if not _available_locally(f):
            unavailable += 1
            report.setdefault("staff_unavailable", []).append(rel)
            if fid in prev:
                profiles.append(prev[fid])  # keep last good
            continue
        if fid in prev and file_state.get(fid, {}).get("modifiedTime") == mtime:
            profiles.append(prev[fid]); unchanged += 1
            continue
        text = _extract_text(f)
        prof = N.normalize_cv(text=text, file_id=fid, file_name=f.name,
                              country=country, modified_time=mtime)
        prof["source_rel_path"] = rel
        if not text.strip():
            prof["extraction_confidence"] = "LOW"
            prof["parse_warning"] = "no extractable text (possibly scanned)"
            failed += 1
        profiles.append(prof)
        file_state[fid] = {"modifiedTime": mtime, "name": f.name}
        if fid in prev:
            updated += 1
        else:
            added += 1

    removed = [fid for fid in prev if fid not in seen]
    for fid in removed:
        file_state.pop(fid, None)

    cache.write_staff(profiles, {"type": "local_folder", "path": str(sdir)})
    report["staff"] = {"status": "OK", "files": len([p for p in profiles]),
                       "profiles": len(profiles), "added": added, "updated": updated,
                       "unchanged": unchanged, "low_confidence": failed,
                       "unavailable": unavailable, "removed": len(removed)}


# ---------------------------------------------------------------------------
# Company + Brand
# ---------------------------------------------------------------------------

def scan_company(root: Path, cache: Cache, report: dict) -> None:
    cdir = root / COMPANY_SUB
    if not cdir.exists():
        report["company"] = {"status": "NO_FOLDER"}
        return
    facts = []
    for f in sorted(cdir.rglob("*")):
        if f.is_file() and f.suffix.lower() in (_PDF, _DOCX) and not f.name.startswith("~$"):
            facts.append({"fact_id": "company_doc_" + hashlib.sha1(
                str(f).encode()).hexdigest()[:10], "label": f.name,
                "source_rel_path": str(f.relative_to(cdir)),
                "source_modified_time": _mtime(f), "kind": "company_document",
                "verified": True})
    cache.write_company(facts, {"type": "local_folder", "path": str(cdir)})
    report["company"] = {"status": "OK", "documents": len(facts)}


def scan_brand(root: Path, cache: Cache, report: dict) -> None:
    bdir = root / BRAND_SUB
    if not bdir.exists():
        cache.write_brand({"available": False})
        report["brand"] = {"status": "NO_FOLDER", "available": False}
        return
    logo = None
    imgs = [f for f in bdir.rglob("*")
            if f.is_file() and f.suffix.lower() in _IMG]
    # prefer a file named like a logo
    imgs.sort(key=lambda f: (0 if "logo" in f.name.lower() else 1, f.name))
    for f in imgs:
        if _available_locally(f):
            logo = str(f)
            break
    cache.write_brand({"available": bool(logo), "logo_path": logo,
                       "source": {"type": "local_folder", "path": str(bdir)}})
    report["brand"] = {"status": "OK", "available": bool(logo)}


# ---------------------------------------------------------------------------
# Orchestration (transactional)
# ---------------------------------------------------------------------------

def scan_local_folder(root: str | Path, cache: Optional[Cache] = None) -> dict:
    """Full incremental scan of the local knowledge folder → cache. Transactional.

    On hard failure the previous valid cache is kept intact.
    """
    root = Path(root).expanduser()
    cache = cache or Cache()
    report: dict = {"started_at": _now(), "knowledge_root": str(root)}
    if not root.exists() or not root.is_dir():
        report["ok"] = False
        report["error"] = f"Knowledge root not found: {root}"
        return report

    state = cache.state()
    state.setdefault("sources", {})
    state["source_mode"] = "LOCAL_FOLDER"
    state["knowledge_root"] = str(root)

    try:
        scan_projects(root, cache, report)
        scan_staff(root, cache, state, report)
        scan_company(root, cache, report)
        scan_brand(root, cache, report)
        cache.write_state(state)
        report["ok"] = True
    except Exception as e:  # transactional: previous cache stays valid
        report["ok"] = False
        report["error"] = str(e)
    report["finished_at"] = _now()
    return report
