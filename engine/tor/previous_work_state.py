"""Previous-work sample: SELECTION and SHARING CLEARANCE are independent (v0.6.12).

  PREVIOUS_WORK_SELECTED   the user chose a report ("Use the IRC report") and the file
                           is registered in the run package
  PREVIOUS_WORK_CLEARANCE  explicit permission to share that report externally

Choosing a report never clears it, and neither does ARFADA authorship (a report
written FOR a client usually needs that client's permission). Only explicit
permission wording sets clearance to VERIFIED, for example "cleared to share",
"permission confirmed", "yes, it may be shared externally".
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path
from typing import Optional

VERIFIED = "VERIFIED"
UNVERIFIED = "UNVERIFIED"
MISSING = "MISSING"

RECORD = "previous_work.json"

# explicit sharing permission (a selection such as "use the IRC report" is NOT this)
PERMISSION = re.compile(
    r"\bcleared\s+(?:to|for)\s+(?:share|sharing|external)|"
    r"\bclearance\s+(?:has\s+been\s+|was\s+|is\s+)?(?:confirmed|granted|obtained|received|given)\b|"
    r"\bpermission\s+(?:to\s+share\s+(?:it\s+)?)?(?:has\s+been\s+|was\s+|is\s+)?"
    r"(?:confirmed|granted|obtained|received|given)\b|"
    r"\b(?:may|can)\s+be\s+shared\b(?!\s+(?:only|if|once|after|subject))|"
    r"\bapproved\s+(?:it\s+)?(?:for\s+(?:external\s+)?sharing|to\s+(?:be\s+)?share)|"
    r"\b(?:consent|agreement)\s+(?:to\s+share\s+)?(?:has\s+been\s+|was\s+)?(?:obtained|given|received)\b|"
    r"\b(?:allowed|authori[sz]ed|permitted)\s+to\s+(?:be\s+)?shar|"
    r"\b(?:given|granted|obtained|received)\s+(?:its\s+|their\s+|written\s+)?"
    r"(?:consent|permission|clearance)\b", re.I)
# hedged / negated wording never clears
_HEDGE = re.compile(r"\b(?:not|no|never|pending|check|ask|need(?:s)?\s+to|should|if|whether|"
                    r"before|unless|once|maybe|probably)\b", re.I)


def is_explicit_permission(note: Optional[str]) -> bool:
    """True only for unhedged, explicit sharing permission."""
    if not note or not PERMISSION.search(note):
        return False
    return not _HEDGE.search(note)


def _load(run_dir: Path) -> Optional[dict]:
    p = Path(run_dir) / RECORD
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except Exception:
        return None


def _files(run_dir: Path) -> list:
    out = []
    for base in (Path(run_dir) / "annexes" / "previous_work", Path(run_dir) / "previous_work"):
        if base.is_dir():
            out += [str(p) for p in base.iterdir() if p.is_file()]
    return out


def previous_work_states(run_dir: str | Path) -> dict:
    """{'selected': {...}, 'clearance': {...}} — independent claim states."""
    run_dir = Path(run_dir)
    rec = _load(run_dir) or {}
    files = _files(run_dir)
    f = rec.get("file")
    present = bool(files) or bool(f and Path(f).exists())
    if rec and present:
        selected = {"status": VERIFIED, "file": Path(f).name if f else Path(files[0]).name,
                    "label": rec.get("label") or (Path(f).stem if f else ""),
                    "detail": "report selected and registered in the package"}
    elif rec:
        selected = {"status": UNVERIFIED, "detail": "registered file not found in the package"}
    elif files:
        selected = {"status": UNVERIFIED, "file": Path(files[0]).name,
                    "detail": "file present but not registered (previous_work.py register)"}
    else:
        selected = {"status": MISSING, "detail": "no previous-work report selected"}
    cl = rec.get("clearance") if isinstance(rec.get("clearance"), dict) else {}
    note = cl.get("evidence") or ""
    if cl.get("status") == VERIFIED and is_explicit_permission(note):
        clearance = {"status": VERIFIED, "evidence": note[:200],
                     "detail": "explicit sharing permission recorded"}
    elif selected["status"] == VERIFIED:
        clearance = {"status": UNVERIFIED,
                     "detail": "sharing clearance not confirmed (selection is not permission)"}
    else:
        clearance = {"status": MISSING, "detail": "no report selected yet"}
    return {"selected": selected, "clearance": clearance}


def record_selection(run_dir: Path, *, file: Path, original: Path, verdict: dict,
                     label: str = "") -> dict:
    """Register the chosen report — selection only; clearance stays UNVERIFIED."""
    prev = _load(run_dir) or {}
    keep = prev.get("clearance") if prev.get("original") == str(original) else None
    rec = {"file": str(file), "original": str(original), "label": label or Path(file).stem,
           "kind": verdict.get("kind"), "by_arfada": verdict.get("by_arfada"),
           "selected": True,
           "clearance": keep or {"status": UNVERIFIED, "evidence": "",
                                 "detail": "selection is not sharing permission"},
           "verdict": verdict}
    rec["clearance_confirmed"] = rec["clearance"].get("status") == VERIFIED   # legacy field
    (Path(run_dir) / RECORD).write_text(json.dumps(rec, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    return rec


def record_clearance(run_dir: Path, note: str) -> dict:
    """Set clearance VERIFIED only for explicit, unhedged permission wording."""
    rec = _load(run_dir)
    if not rec:
        return {"ok": False, "status": "NO_SELECTION",
                "message": "Register the selected report first (previous_work.py register)."}
    if not is_explicit_permission(note):
        return {"ok": False, "status": "NOT_EXPLICIT_PERMISSION",
                "message": "Clearance needs explicit permission wording, e.g. 'cleared to share' "
                           "or 'permission confirmed'. A selection ('use the IRC report') is "
                           "not permission."}
    rec["clearance"] = {"status": VERIFIED, "evidence": note.strip()[:300],
                        "recorded_at": _dt.datetime.now(_dt.timezone.utc).isoformat()}
    rec["clearance_confirmed"] = True
    (Path(run_dir) / RECORD).write_text(json.dumps(rec, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    return {"ok": True, "status": "CLEARED", "evidence": rec["clearance"]["evidence"]}
