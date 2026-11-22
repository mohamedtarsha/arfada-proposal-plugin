"""Governed ARFADA organisation policies (v0.6.16).

Stored once, from an explicit user / admin confirmation (never inferred), in
``ARFADA_HOME/governance/policies.json`` so every run can apply it:

  PREVIOUS_WORK_SHARING_POLICY
      status  APPROVED
      scope   ARFADA client evaluation reports
      source  explicit user/admin confirmation (the confirming words are kept)

When the policy applies, a SELECTED previous-work report that is in scope (an
ARFADA-produced evaluation / assessment report) is cleared for sharing — unless the
report itself carries an explicit restriction (confidential / restricted / do not
share …), which always overrides the general policy. Files outside the scope are never
cleared by it.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path
from typing import Optional

PREVIOUS_WORK_SHARING = "PREVIOUS_WORK_SHARING_POLICY"
APPROVED = "APPROVED"
SCOPE = "ARFADA client evaluation reports"
# annex.validate_previous_work kind for an evaluation / assessment deliverable (plus the
# legacy labels used by earlier registrations)
IN_SCOPE_KINDS = {"evaluation_deliverable", "evaluation_report", "endline_report",
                  "final_evaluation", "baseline_report", "assessment_report"}

_APPROVAL = re.compile(r"\bpermission\b[^.]{0,80}\bshar|\b(?:may|can|are\s+allowed\s+to|is\s+allowed\s+to)"
                       r"\s+(?:be\s+)?shar|\bapproved?\b[^.]{0,60}\bshar|\bclients?\b[^.]{0,60}"
                       r"\b(?:agreed|consent\w*|permit\w*)\b", re.I)
_HEDGE = re.compile(r"\b(?:not|no|never|pending|check|ask|maybe|probably|if|whether|unless|"
                    r"should|might|some\s+clients|case[- ]by[- ]case)\b|\?", re.I)
# an explicit report-level restriction overrides any general policy
RESTRICTION = re.compile(
    r"\bstrictly\s+confidential\b|\bconfidential\s+(?:report|document|draft|-\s*not)|"
    r"\bdo\s+not\s+(?:share|distribute|circulate|cite|quote|forward|disclose)\b|"
    r"\bnot\s+for\s+(?:public\s+|external\s+|wider\s+)?(?:distribution|circulation|release|"
    r"publication)\b|\binternal\s+use\s+only\b|\brestricted\s+(?:distribution|circulation)\b|"
    r"\bfor\s+official\s+use\s+only\b|^\s*CONFIDENTIAL\s*$|^\s*RESTRICTED\s*$", re.I | re.M)


def _store() -> Path:
    from .gknowledge.paths import arfada_home
    d = arfada_home() / "governance"
    d.mkdir(parents=True, exist_ok=True)
    return d / "policies.json"


def _load() -> dict:
    p = _store()
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        return {}


def is_explicit_approval(note: Optional[str]) -> bool:
    return bool(note and _APPROVAL.search(note) and not _HEDGE.search(note))


def set_previous_work_sharing_policy(note: str, *, scope: str = SCOPE) -> dict:
    """Record the organisation-level approval — explicit confirmation wording only."""
    if not is_explicit_approval(note):
        return {"ok": False, "status": "NOT_EXPLICIT_APPROVAL",
                "message": "The policy needs an explicit confirmation, e.g. 'ARFADA has "
                           "permission from its clients to share previous evaluation reports "
                           "as examples of previous work'."}
    doc = _load()
    doc[PREVIOUS_WORK_SHARING] = {
        "status": APPROVED, "scope": scope, "source": "explicit user/admin confirmation",
        "confirmation": note.strip()[:400],
        "recorded_at": _dt.datetime.now(_dt.timezone.utc).isoformat()}
    _store().write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "status": "RECORDED", "policy": doc[PREVIOUS_WORK_SHARING]}


def revoke_previous_work_sharing_policy(note: str = "") -> dict:
    doc = _load()
    doc[PREVIOUS_WORK_SHARING] = {"status": "REVOKED", "note": note[:300],
                                  "recorded_at": _dt.datetime.now(_dt.timezone.utc).isoformat()}
    _store().write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "status": "REVOKED"}


def previous_work_sharing_policy() -> Optional[dict]:
    p = _load().get(PREVIOUS_WORK_SHARING)
    return p if isinstance(p, dict) and p.get("status") == APPROVED else None


def report_restriction(path) -> str:
    """The explicit sharing restriction a report carries ('' when none is found)."""
    p = Path(str(path or ""))
    hit = RESTRICTION.search(p.name.replace("_", " ").replace("-", " "))
    if hit:
        return f"file name: '{hit.group(0)}'"
    try:
        if p.suffix.lower() == ".pdf":
            from pypdf import PdfReader
            r = PdfReader(str(p))
            meta = " ".join(str(v) for v in (r.metadata or {}).values())
            hit = RESTRICTION.search(meta)
            if hit:
                return f"document properties: '{hit.group(0)}'"
            text = "\n".join((pg.extract_text() or "") for pg in r.pages[:3])
        elif p.suffix.lower() == ".docx":
            from docx import Document
            d = Document(str(p))
            cp = d.core_properties
            meta = " ".join(str(x or "") for x in (cp.title, cp.subject, cp.keywords, cp.comments,
                                                     cp.category))
            hit = RESTRICTION.search(meta)
            if hit:
                return f"document properties: '{hit.group(0)}'"
            hdr = " ".join(par.text for s in d.sections for par in s.header.paragraphs)
            text = hdr + "\n" + "\n".join(par.text for par in d.paragraphs[:80])
        else:
            text = ""
    except Exception:
        text = ""
    hit = RESTRICTION.search(text or "")
    return f"report text: '{hit.group(0).strip()}'" if hit else ""


def policy_clearance(record: dict) -> Optional[dict]:
    """Clearance granted by the organisation policy for a selected report, or None."""
    pol = previous_work_sharing_policy()
    if not pol or not record:
        return None
    kind = str(record.get("kind") or (record.get("verdict") or {}).get("kind") or "").lower()
    by_arfada = record.get("by_arfada", (record.get("verdict") or {}).get("by_arfada"))
    if kind not in IN_SCOPE_KINDS or by_arfada is not True:
        return {"status": "OUT_OF_SCOPE",
                "detail": f"the organisation policy covers {pol.get('scope', SCOPE)} only"}
    restriction = record.get("restriction") or report_restriction(
        record.get("original") or record.get("file"))
    if restriction:
        return {"status": "RESTRICTED",
                "detail": f"the report carries an explicit sharing restriction ({restriction}); "
                          "the general policy does not override it"}
    return {"status": "APPROVED", "evidence": pol.get("confirmation", "")[:200],
            "detail": f"cleared by the ARFADA organisation-level sharing policy ({pol['scope']}, "
                      f"recorded {pol.get('recorded_at', '')[:10]})"}
