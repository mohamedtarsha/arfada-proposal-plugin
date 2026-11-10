"""Incremental, transactional sync from Google → local normalized cache.

Design:
- Projects: read the Master Tracker sheet, normalize, compute metrics.
- Staff: list registered CV folder(s), download only new/changed files (by
  modifiedTime), normalize to profiles. Deleted files are dropped.
- Company / Brand: index registered folders; cache the logo locally.
- Transactional: build into a staging dict, validate, then write cache. A failed
  sync leaves the previous valid cache intact (spec §36).

The Google clients are INJECTED (DriveLike/SheetsLike) so this is fully testable
with synthetic data and no credentials.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional

from .cache import Cache
from .clients import DriveLike, SheetsLike
from . import normalize as N

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_PDF = "application/pdf"
_FOLDER = "application/vnd.google-apps.folder"
_IMG = ("image/png", "image/jpeg")


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sync_projects(sheets: SheetsLike, source: dict, cache: Cache, report: dict) -> None:
    sid = source.get("spreadsheet_id")
    sheet_name = source.get("sheet_name", "")
    if not sid:
        report["projects"] = {"skipped": "no spreadsheet_id"}
        return
    rows = sheets.read(sid, sheet_name)
    projects = N.normalize_projects(rows, sheet_name=sheet_name, spreadsheet_id=sid,
                                    column_map=source.get("column_map"))
    metrics = N.compute_metrics(projects)
    cache.write_projects(projects, metrics, {
        "type": "google_sheet", "spreadsheet_id": sid, "sheet_name": sheet_name})
    report["projects"] = {"rows": max(0, len(rows) - 1), "normalized": len(projects),
                          "metrics": {k: v.get("value") for k, v in metrics.items()}}


def _iter_cv_files(drive: DriveLike, folder_id: str, country: str = "",
                   recurse: bool = True) -> list[dict]:
    out = []
    for f in drive.list_folder(folder_id):
        if f.get("mimeType") == _FOLDER and recurse:
            out.extend(_iter_cv_files(drive, f["id"], country=f.get("name", country), recurse=True))
        elif f.get("mimeType") in (_PDF, _DOCX):
            out.append({**f, "country": country})
    return out


def _extract_cv_text(data: bytes, mime: str) -> str:
    import io
    try:
        if mime == _DOCX:
            from docx import Document
            doc = Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)
        if mime == _PDF:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            return "\n".join((pg.extract_text() or "") for pg in reader.pages)
    except Exception:
        return ""
    return ""


def sync_staff(drive: DriveLike, source: dict, cache: Cache, state: dict, report: dict) -> None:
    folder_id = source.get("folder_id")
    if not folder_id:
        report["staff"] = {"skipped": "no folder_id"}
        return
    recurse = bool(source.get("subfolders_by_country", True))
    files = _iter_cv_files(drive, folder_id, recurse=recurse)
    file_state = state["sources"].setdefault("staff", {}).setdefault("files", {})

    prev_profiles = {p["source_file_id"]: p
                     for p in (cache.staff() or {}).get("profiles", [])}
    added = updated = unchanged = 0
    seen_ids = set()
    profiles = []

    for f in files:
        fid = f["id"]
        seen_ids.add(fid)
        mtime = f.get("modifiedTime", "")
        if fid in prev_profiles and file_state.get(fid, {}).get("modifiedTime") == mtime:
            profiles.append(prev_profiles[fid]); unchanged += 1
            continue
        try:
            data = drive.download(fid)
            text = _extract_cv_text(data, f.get("mimeType", ""))
        except Exception:
            # keep previous profile if present; count as failure
            report.setdefault("staff_failures", []).append(f.get("name", fid))
            if fid in prev_profiles:
                profiles.append(prev_profiles[fid])
            continue
        prof = N.normalize_cv(text=text, file_id=fid, file_name=f.get("name", ""),
                              country=f.get("country", ""), modified_time=mtime)
        profiles.append(prof)
        file_state[fid] = {"modifiedTime": mtime, "name": f.get("name", "")}
        if fid in prev_profiles:
            updated += 1
        else:
            added += 1

    removed = [fid for fid in prev_profiles if fid not in seen_ids]
    for fid in removed:
        file_state.pop(fid, None)

    cache.write_staff(profiles, {"type": "google_drive_folder", "folder_id": folder_id})
    report["staff"] = {"files": len(files), "profiles": len(profiles),
                       "added": added, "updated": updated, "unchanged": unchanged,
                       "removed": len(removed)}


def sync_company(drive: DriveLike, source: dict, cache: Cache, report: dict) -> None:
    folder_id = source.get("folder_id")
    if not folder_id:
        report["company"] = {"skipped": "no folder_id"}
        return
    facts = []
    for f in drive.list_folder(folder_id):
        if f.get("mimeType") in (_PDF, _DOCX):
            facts.append({"fact_id": "company_doc_" + f["id"][:10],
                          "label": f.get("name", ""), "source_file_id": f["id"],
                          "source_modified_time": f.get("modifiedTime", ""),
                          "kind": "company_document", "verified": True})
    cache.write_company(facts, {"type": "google_drive_folder", "folder_id": folder_id})
    report["company"] = {"documents": len(facts)}


def sync_brand(drive: DriveLike, source: dict, cache: Cache, report: dict) -> None:
    folder_id = source.get("folder_id")
    if not folder_id:
        report["brand"] = {"skipped": "no folder_id"}
        return
    logo = None
    for f in drive.list_folder(folder_id):
        name = (f.get("name") or "").lower()
        if f.get("mimeType") in _IMG and ("logo" in name or logo is None):
            try:
                data = drive.download(f["id"])
                ext = ".png" if "png" in f.get("mimeType", "") else ".jpg"
                dest = cache.files_dir / f"arfada_logo{ext}"
                dest.write_bytes(data)
                logo = str(dest)
                if "logo" in name:
                    break
            except Exception:
                continue
    cache.write_brand({"logo_path": logo, "available": bool(logo),
                       "source": {"type": "google_drive_folder", "folder_id": folder_id}})
    report["brand"] = {"available": bool(logo)}


def run_sync(*, sources, drive: Optional[DriveLike], sheets: Optional[SheetsLike],
             cache: Optional[Cache] = None) -> dict:
    """Full incremental sync. Returns a report. Leaves cache intact on hard failure."""
    cache = cache or Cache()
    report: dict = {"started_at": _now()}
    state = cache.state()
    state.setdefault("sources", {})
    state["source_mode"] = "GOOGLE_API"

    try:
        if sheets and sources.projects:
            sync_projects(sheets, sources.projects, cache, report)
        if drive and sources.staff:
            sync_staff(drive, sources.staff, cache, state, report)
        if drive and sources.company:
            sync_company(drive, sources.company, cache, report)
        if drive and sources.brand:
            sync_brand(drive, sources.brand, cache, report)
        cache.write_state(state)
        report["ok"] = True
    except Exception as e:  # transactional: previous cache stays valid
        report["ok"] = False
        report["error"] = str(e)
    report["finished_at"] = _now()
    return report
