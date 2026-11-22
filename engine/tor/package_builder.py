"""Auto-package submission annexes that already exist in ARFADA Knowledge (v0.6.16).

CV package
    Each selected expert (``staff_profile_id``) is resolved back to the ORIGINAL CV file
    under ``ARFADA Knowledge\\Staff CVs``. The canonical name must appear in the CV text,
    then the file is copied byte-for-byte into ``annexes/cvs/`` (never rewritten) and
    ``cv_package_manifest.json`` links staff_profile_id → canonical name → source path →
    packaged path. A member stays unresolved (TEAM_CV_PACKAGE remains a blocker) only
    when the CV cannot be resolved, the file is unavailable, the identity does not match,
    or the format cannot be packaged.

Registration evidence
    ``ARFADA Knowledge\\Company`` is searched for an authoritative registration / legal
    registration certificate. Exactly one current candidate → copied into
    ``annexes/registration/`` with provenance; several → the employee chooses (FAST
    question); none → REGISTRATION_EVIDENCE stays a blocker. Nothing is invented.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Optional

CV_MANIFEST = "cv_package_manifest.json"
REGISTRATION_PROVENANCE = "registration_provenance.json"
PACKAGEABLE = {".pdf", ".docx", ".doc"}
REG_FORMATS = {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}
_REG_NAME = re.compile(r"registration|registered|certificate\s+of\s+(?:registration|incorporation)|"
                       r"incorporation|commercial\s+regist|trade\s+licen[cs]e|business\s+licen[cs]e|"
                       r"\bHAC\b|تسجيل|شهادة", re.I)
_REG_EXCLUDE = re.compile(r"\b(?:policy|policies|procedure|consent|profile|guide|code\s+of\s+conduct|"
                          r"protocol|template|draft|form|ethic)", re.I)
_EXPIRY = re.compile(r"(?:valid\s+(?:until|till|through|to)|expir\w*(?:\s+on|\s+date)?)\s*[:\-]?\s*"
                     r"(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|"
                     r"[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{4}[/.\-]\d{1,2}[/.\-]\d{1,2})", re.I)


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _knowledge_root(explicit=None) -> Optional[Path]:
    if explicit:
        return Path(explicit)
    try:
        from .lknowledge.staff_pool import _knowledge_root as kr
        r = kr()
        return Path(r) if r else None
    except Exception:
        return None


def _team(run_dir: Path) -> list:
    try:
        setup = json.loads((run_dir / "proposed_setup.json").read_text(encoding="utf-8"))
    except Exception:
        return []
    return [m for m in setup.get("team") or [] if isinstance(m, dict) and
            (m.get("staff_profile_id") or m.get("staff_id"))]


def _fold(t: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", str(t or "").casefold())
    return "".join(ch for ch in t if not unicodedata.combining(ch))


def identity_matches(canonical_name: str, cv_text: str) -> tuple:
    """(ok, reason): the CV text names the selected expert (surname + one more name)."""
    toks = [t for t in re.findall(r"[^\W\d_]{2,}", canonical_name or "")]
    if len(toks) < 2:
        return False, "canonical name too short to verify"
    text = " " + " ".join(re.findall(r"[^\W\d_]+", _fold(cv_text[:6000]))) + " "
    present = [t for t in toks if f" {_fold(t)} " in text]
    if _fold(toks[-1]) not in [_fold(t) for t in present] and _fold(toks[0]) not in [_fold(t) for t in present]:
        return False, "the CV does not name the selected expert"
    if len(present) >= 2:
        return True, f"name found in CV ({' '.join(present)})"
    return False, "only one name token found in the CV"


def package_team_cvs(run_dir, *, knowledge=None, knowledge_root=None) -> dict:
    """Copy each selected expert's original CV into annexes/cvs/ (+ manifest)."""
    run_dir = Path(run_dir)
    team = _team(run_dir)
    if not team:
        return {"status": "NO_TEAM", "entries": []}
    from .lknowledge.staff_pool import cv_file_for
    from .lknowledge.staff_identity import canonical_identity
    from .lknowledge.scan import _extract_text
    root = _knowledge_root(knowledge_root)
    try:
        if knowledge is None:
            from .knowledge import Knowledge
            knowledge = Knowledge(run_dir=run_dir)
        pool = {p.get("staff_id"): p for p in getattr(knowledge, "_live_staff", []) or []}
    except Exception:
        pool = {}
    facts = []
    try:
        f = json.loads((run_dir / "team_staff_facts.json").read_text(encoding="utf-8"))
        facts = f.get("facts", f) if isinstance(f, dict) else f
    except Exception:
        pass
    out_dir = run_dir / "annexes" / "cvs"
    entries = []
    for m in team:
        sid = str(m.get("staff_profile_id") or m.get("staff_id"))
        p = pool.get(sid) or {**m, "staff_id": sid}
        ident = canonical_identity(p, staff_facts=facts if isinstance(facts, list) else [])
        e = {"staff_profile_id": sid, "canonical_name": ident.get("canonical_name") or m.get("name", ""),
             "role": m.get("role", ""), "source_cv_path": "", "packaged_cv_path": "",
             "stored_rel_path": p.get("source_rel_path", ""),     # provenance, as indexed
             "status": "UNRESOLVED", "reason": ""}
        # v0.6.17: portable resolution (either separator, re-anchored at Staff CVs, never
        # outside the Knowledge root) — the persisted index is never edited
        from .lknowledge.staff_pool import portable_rel_parts
        parts = portable_rel_parts(p.get("source_rel_path") or "")
        src = cv_file_for(p, root) if parts else None
        if not p.get("source_rel_path"):
            e["reason"] = "the CV could not be resolved from the staff index"
        elif not parts:
            e["reason"] = "the stored CV path is outside the Knowledge Staff CVs root"
        elif src is None or not Path(src).is_file():
            e["reason"] = "source CV file unavailable under Staff CVs"
            e["source_cv_path"] = str(Path(str(root or "")).joinpath("Staff CVs", *parts))
        elif Path(src).suffix.lower() not in PACKAGEABLE:
            e["source_cv_path"], e["reason"] = str(src), f"format {Path(src).suffix} cannot be packaged"
        else:
            e["source_cv_path"] = str(src)
            try:
                text = _extract_text(Path(src)) or ""
            except Exception:
                text = ""
            ok, why = identity_matches(e["canonical_name"], text) if text else \
                (False, "the CV text could not be read to verify identity")
            e["identity_check"] = why
            if not ok:
                e["reason"] = f"identity not verified: {why}"
            else:
                out_dir.mkdir(parents=True, exist_ok=True)
                dest = out_dir / Path(src).name
                if dest.exists() and _sha(dest) != _sha(Path(src)):
                    dest = out_dir / f"{sid}__{Path(src).name}"
                shutil.copy2(src, dest)                       # byte-for-byte; never rewritten
                e.update({"packaged_cv_path": str(dest.relative_to(run_dir)).replace("\\", "/"),
                          "sha256": _sha(dest), "status": "PACKAGED", "reason": ""})
        entries.append(e)
    doc = {"generated_at": _now(), "knowledge_root": str(root or ""), "entries": entries,
           "all_packaged": all(x["status"] == "PACKAGED" for x in entries)}
    (run_dir / CV_MANIFEST).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return doc


def cv_package_state(run_dir) -> Optional[dict]:
    """From the manifest: {ok, detail, unresolved} — None when no manifest exists."""
    run_dir = Path(run_dir)
    try:
        doc = json.loads((run_dir / CV_MANIFEST).read_text(encoding="utf-8"))
    except Exception:
        return None
    team_ids = {str(m.get("staff_profile_id") or m.get("staff_id")) for m in _team(run_dir)}
    entries = {e["staff_profile_id"]: e for e in doc.get("entries", [])}
    unresolved = []
    for sid in sorted(team_ids):
        e = entries.get(sid)
        if not e:
            unresolved.append(f"{sid}: not packaged yet")
        elif e.get("status") != "PACKAGED" or not (run_dir / e.get("packaged_cv_path", "")).is_file():
            unresolved.append(f"{e.get('canonical_name') or sid}: {e.get('reason') or 'packaged file missing'}")
    n = len(team_ids) - len(unresolved)
    return {"ok": not unresolved and bool(team_ids), "packaged": n, "team_size": len(team_ids),
            "unresolved": unresolved,
            "detail": (f"{n}/{len(team_ids)} selected experts' CVs packaged from Staff CVs"
                       + (f"; unresolved: {'; '.join(unresolved)}" if unresolved else ""))}


def _expired(text: str) -> bool:
    m = _EXPIRY.search(text or "")
    if not m:
        return False
    s = m.group(1)
    for fmt in ("%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y",
                "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%y"):
        try:
            return _dt.datetime.strptime(s.replace(",", ""), fmt).date() < _dt.date.today()
        except ValueError:
            continue
    return False


def registration_candidates(knowledge_root=None) -> list:
    """Current registration-certificate files under ARFADA Knowledge/Company."""
    root = _knowledge_root(knowledge_root)
    if not root:
        return []
    company = root / "Company"
    if not company.is_dir():
        return []
    out = []
    for f in sorted(company.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in REG_FORMATS:
            continue
        name = f.stem.replace("_", " ").replace("-", " ")
        if not _REG_NAME.search(name) or _REG_EXCLUDE.search(name):
            continue
        text = ""
        if f.suffix.lower() in (".pdf", ".docx", ".doc"):
            try:
                from .lknowledge.scan import _extract_text
                text = _extract_text(f) or ""
            except Exception:
                text = ""
        if text and _expired(text):
            continue                                      # an expired certificate is not current
        out.append(f)
    return out


def package_registration(run_dir, *, knowledge_root=None) -> dict:
    """Package the registration certificate when exactly one (or the chosen one) exists."""
    run_dir = Path(run_dir)
    dest_dir = run_dir / "annexes" / "registration"
    if dest_dir.is_dir() and any(p.is_file() for p in dest_dir.iterdir()):
        return {"status": "ALREADY_PACKAGED"}
    from .run_decisions import get as _decision
    chosen = _decision(run_dir, "registration_choice")
    cands = registration_candidates(knowledge_root)
    if chosen:
        src, how = Path(chosen["value"]), "chosen by the employee"
    elif len(cands) == 1:
        src, how = cands[0], "the only registration certificate found in ARFADA Knowledge/Company"
    elif len(cands) > 1:
        return {"status": "CHOOSE", "candidates": [str(c) for c in cands]}
    else:
        return {"status": "NONE_FOUND", "candidates": []}
    if not src.is_file():
        return {"status": "NONE_FOUND", "candidates": [str(c) for c in cands]}
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copy2(src, dest)
    prov = {"source_path": str(src), "packaged_path": str(dest.relative_to(run_dir)).replace("\\", "/"),
            "sha256": _sha(dest), "selection": how, "packaged_at": _now()}
    (run_dir / REGISTRATION_PROVENANCE).write_text(json.dumps(prov, ensure_ascii=False, indent=2),
                                                   encoding="utf-8")
    return {"status": "PACKAGED", **prov}


def auto_package(run_dir, *, knowledge=None, knowledge_root=None) -> dict:
    """Package what ARFADA Knowledge already holds (CVs, registration) for this run."""
    run_dir = Path(run_dir)
    try:
        reqs = json.loads((run_dir / "requirements.json").read_text(encoding="utf-8")).get("requirements", [])
    except Exception:
        reqs = []
    from .claim_state import _required_checklist_keys
    required = _required_checklist_keys(reqs)
    out = {}
    if "cv_annex" in required and _team(run_dir):
        out["cvs"] = package_team_cvs(run_dir, knowledge=knowledge, knowledge_root=knowledge_root)
    if "registration" in required:
        out["registration"] = package_registration(run_dir, knowledge_root=knowledge_root)
    return out
