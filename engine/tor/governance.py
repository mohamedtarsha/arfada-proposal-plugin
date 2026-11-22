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

# v0.6.17: confirmation is classified by meaning, not by a magic phrase. The same words give
# the same result whether stated alone or inside a longer note.
AFFIRMATIVE, NEGATIVE, AMBIGUOUS = "AFFIRMATIVE", "NEGATIVE", "AMBIGUOUS"
_AFFIRM = re.compile(
    r"\b(?:yes|yeah|yep|correct|confirm\w*|approv\w*|appl(?:y|ies|ied)|in\s+place|granted|"
    r"permission|permitted|allowed|agreed?|authori[sz]\w*|consent\w*|cleared|valid|"
    r"(?:may|can)\s+(?:be\s+)?shar\w*|ok(?:ay)?)\b", re.I)
_NO_OBJECTION = re.compile(r"\bno\s+(?:restrictions?|objections?|issues?|problems?|concerns?)\b", re.I)
_NEGATE = re.compile(
    r"\b(?:no|not|never|none|cannot|can't|cant|don't|doesn't|isn't|aren't|won't|without|"
    r"denied|refus\w*|revok\w*|withdr[ae]w\w*|declin\w*|forbid\w*|prohibit\w*|disallow\w*)\b", re.I)
_HEDGE = re.compile(
    r"\b(?:maybe|perhaps|probably|possibly|might|unsure|unless|if|whether|pending|depends?|"
    r"check|ask|should|tbc|tbd|i\s+think|i\s+believe|i\s+guess|some\s+clients?|most\s+clients?|"
    r"case[- ]by[- ]case|not\s+sure|partly|partially)\b|\?", re.I)
CONFIRM_QUESTION = ("Please confirm explicitly: does ARFADA have its clients' permission to share "
                    "previous evaluation reports as examples of previous work? (Yes / No)")


def classify_confirmation(text: Optional[str]) -> str:
    """AFFIRMATIVE / NEGATIVE / AMBIGUOUS for a governance confirmation statement."""
    t = " ".join(str(text or "").split())
    if not t:
        return AMBIGUOUS
    t = _NO_OBJECTION.sub(" approved ", t)
    if _NEGATE.search(t):
        return NEGATIVE
    if _HEDGE.search(t):
        return AMBIGUOUS
    return AFFIRMATIVE if _AFFIRM.search(t) else AMBIGUOUS
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
    return classify_confirmation(note) == AFFIRMATIVE


def set_previous_work_sharing_policy(note: str, *, scope: str = SCOPE,
                                     confirmed: bool = False) -> dict:
    """Record the organisation-level approval from an explicit confirmation state.

    AFFIRMATIVE wording is accepted as stated; AMBIGUOUS wording needs the explicit Yes/No
    confirmation (``confirmed=True``); NEGATIVE wording is never recorded as approval. The
    user's exact words are kept as provenance.
    """
    cls = classify_confirmation(note)
    if cls == NEGATIVE:
        return {"ok": False, "status": "NOT_APPROVED", "classification": cls,
                "message": "The statement does not approve sharing; nothing was recorded."}
    if cls == AMBIGUOUS and not confirmed:
        return {"ok": False, "status": "NEEDS_CONFIRMATION", "classification": cls,
                "question": CONFIRM_QUESTION,
                "message": "The statement is not clearly affirmative; ask the explicit "
                           "confirmation question (arfada_policy.py … --confirm yes)."}
    doc = _load()
    doc[PREVIOUS_WORK_SHARING] = {
        "status": APPROVED, "scope": scope, "source": "explicit user/admin confirmation",
        "confirmation_state": ("EXPLICITLY_CONFIRMED" if confirmed and cls == AMBIGUOUS
                               else "AFFIRMATIVE_STATEMENT"),
        "classification": cls,
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
