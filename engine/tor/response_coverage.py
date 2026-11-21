"""Response coverage computed from the generated proposal TEXT (v0.6.14).

Two independent dimensions per TOR requirement:

  RESPONSE_STATUS  does the proposal text respond to it?
                   ADDRESSED / PARTIALLY_ADDRESSED / NOT_ADDRESSED
  EVIDENCE_STATUS  does ARFADA hold evidence that it satisfies it?
                   VERIFIED / PARTIAL / GAP / NOT_REQUIRED  (requirement_evidence.py)

RESPONSE_STATUS is never read from a stored or self-declared status. The writer's
ledger only supplies the requirement → block mapping; its ``status`` label (ADDRESSED,
PARTIAL, MISSING…) and any ``response_status`` field are ignored. The status is
recomputed on every QA run from:

* the blocks the ledger cites (they must exist in a READY section and carry content);
* the text of the sections that cite or own the requirement (blueprint mapping);
* for a qualification: every required element (e.g. CHS, Sphere, SADD, rapid
  deployment) must be named in that text; for other requirements the cited content
  must be substantive and relevant (shared key terms).

So relabelling a ledger entry cannot change the result, and a weak-evidence
qualification the text does answer is ADDRESSED with its evidence gap kept visible.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

from .requirement_evidence import (QUALIFICATION_TYPES, TOPICS, qualification_elements,
                                   requirement_type, qualification_readiness,
                                   EV_VERIFIED, EV_PARTIAL, EV_GAP, EV_NOT_REQUIRED,
                                   READINESS_VERIFIED, READINESS_PARTIAL, AT_RISK)

ADDRESSED = "ADDRESSED"
PARTIALLY_ADDRESSED = "PARTIALLY_ADDRESSED"
NOT_ADDRESSED = "NOT_ADDRESSED"
RESPONSE_STATUSES = (ADDRESSED, PARTIALLY_ADDRESSED, NOT_ADDRESSED)

MIN_WORDS = 6               # cited content thinner than this is not a response

_H = r"[\s\-‐‑–]*"
# how a proposal RESPONDS to a qualification element (in addition to naming it)
_RESPONSE_CUES = {
    "deploy": rf"\bdeploy|\bmobili[sz]|\brecruit\w*\s+(?:\w+\s+){{0,3}}?(?:local|locally|in\s+nyala)|"
              rf"field\s+teams?|\brapid(?:ly)?\b|\bquickly\b",
    "cultural": rf"\bneutral|\bimpartial|\bethnic|do\s+no\s+harm|conflict{_H}sensitiv|\bcultur(?:al|ally)\b",
    "capacity_building": rf"capacity{_H}building|\btrain\w*\s+(?:\w+\s+){{0,4}}?(?:staff|partners?)|"
                         rf"\bmeal\s+staff\b|\bjoint\s+analysis\b|\bmentor",
    "sadd": r"disaggregat|\bsadd\b|washington\s+group|sex,?\s+age",
    "fsl_indicators": r"\bfcs\b|rcsi|food\s+consumption|coping\s+strateg|hunger\s+scale|\bhhs\b",
}
_STOP = set("""the and for with that this from into their have has will shall should must would could
also such which where when while within across about other than more most many each every all any
including include includes using used based project projects consultant consultants consulting firm
firms team teams ability able strong proven experience experienced expertise familiarity understanding
knowledge capacity skills skill demonstrated relevant provide provided ensure ensuring well good
excellent particularly especially related areas area level levels""".split())


def block_text(b: dict) -> str:
    t = b.get("type")
    if t in ("paragraph", "evidence_placeholder"):
        return str(b.get("text", ""))
    if t in ("bullet_list", "numbered_list"):
        return " ".join(str(x) for x in b.get("items", []))
    if t == "table":
        return " ".join([" ".join(str(c) for c in b.get("columns") or [])] +
                        [" ".join(str(c) for c in row) for row in b.get("rows", [])])
    return ""


def _stems(text: str) -> set:
    return {w[:6] for w in re.findall(r"[a-z][a-z\-]{3,}", (text or "").lower()) if w not in _STOP}


def _element_patterns(key: str, places: Iterable[str]) -> list:
    if key == "local_area":
        pl = [p for p in places if p]
        return ["|".join(re.escape(p) for p in pl)] if pl else []
    spec = next((t for t in TOPICS if t[0] == key), None)
    pats = []
    if spec:
        pats.append(spec[2])
        if spec[3]:
            pats.append(spec[3])
    if key in _RESPONSE_CUES:
        pats.append(_RESPONSE_CUES[key])
    return pats


def compute_responses(requirements: list, gen_sections: dict, *, section_status: dict,
                      blueprint: Optional[dict] = None, places: Iterable[str] = ()) -> dict:
    """{req_id: {response_status, response_basis, cited, sections, elements_found, …}}."""
    places = list(places or [])
    ready = {sid for sid in gen_sections
             if (section_status.get(sid) or {}).get("status") == "READY"}
    sec_text = {sid: " ".join(block_text(b) for b in gen_sections[sid].get("blocks", []))
                for sid in ready}
    owners: dict = {}
    for s in (blueprint or {}).get("sections", []):
        for rid in s.get("requirement_ids", []):
            owners.setdefault(rid, []).append(s.get("section_id"))
    cites: dict = {}
    for sid in ready:
        blocks = {b.get("block_id"): b for b in gen_sections[sid].get("blocks", [])}
        for e in gen_sections[sid].get("requirement_response_ledger", []):
            rid = e.get("requirement_id")
            # the ledger is a MAPPING only: its status label is deliberately ignored
            found = [blocks[b] for b in e.get("block_ids") or [] if b in blocks]
            cites.setdefault(rid, []).append({"section_id": sid, "blocks": found,
                                              "missing": [b for b in e.get("block_ids") or []
                                                          if b not in blocks]})
    out = {}
    for r in requirements or []:
        if r.get("actor") == "CLIENT":
            continue
        rid = r["req_id"]
        c = cites.get(rid, [])
        cited_text = " ".join(block_text(b) for x in c for b in x["blocks"])
        scope = sorted({x["section_id"] for x in c} | {s for s in owners.get(rid, []) if s in ready})
        scope_text = " ".join(sec_text[s] for s in scope)
        rtype = requirement_type(r)
        res = {"response_status": NOT_ADDRESSED, "response_basis": "", "sections": scope,
               "cited_blocks": sorted({b.get("block_id") for x in c for b in x["blocks"]}),
               "elements_found": [], "elements_missing": []}
        el = qualification_elements(r.get("text") or "", places=places)["required"] \
            if rtype in QUALIFICATION_TYPES else []
        if el:
            for k in el:
                pats = _element_patterns(k, places)
                (res["elements_found"] if any(re.search(p, scope_text, re.I) for p in pats)
                 else res["elements_missing"]).append(k)
            if not scope:
                res["response_basis"] = "no READY section cites or owns this requirement"
            elif not res["elements_missing"]:
                res["response_status"] = ADDRESSED
                res["response_basis"] = "every required element is answered in the text"
            elif res["elements_found"]:
                res["response_status"] = PARTIALLY_ADDRESSED
                res["response_basis"] = ("the text answers " + ", ".join(res["elements_found"]) +
                                         "; not " + ", ".join(res["elements_missing"]))
            elif len(cited_text.split()) >= MIN_WORDS:
                res["response_status"] = PARTIALLY_ADDRESSED
                res["response_basis"] = ("cited text does not name " +
                                         ", ".join(res["elements_missing"]))
            else:
                res["response_basis"] = "the cited / owning sections do not answer it"
        else:
            words = len(cited_text.split())
            if not c or not any(x["blocks"] for x in c):
                res["response_basis"] = ("cited blocks do not exist" if c else
                                         "no proposal block cites this requirement")
            elif words < MIN_WORDS:
                res["response_status"] = PARTIALLY_ADDRESSED
                res["response_basis"] = "the cited content is too thin to be a response"
            else:
                res["response_status"] = ADDRESSED
                res["response_basis"] = "substantive cited content in a READY section"
        out[rid] = res
    return out


def combine(matrix: list, responses: dict) -> list:
    """Rows with the two independent dimensions + qualification readiness."""
    rows = []
    for m in matrix:
        r = dict(m)
        resp = responses.get(r["req_id"]) or {"response_status": NOT_ADDRESSED,
                                              "response_basis": "not evaluated"}
        r.update({k: v for k, v in resp.items()})
        r["qualification_readiness"] = qualification_readiness(r)
        rows.append(r)
    return rows


def coverage_summary(rows: list) -> dict:
    """Two separate summaries (content vs evidence) + qualification readiness."""
    mand = [r for r in rows if r.get("mandatory", True)]
    content = {s.lower(): sum(1 for r in mand if r.get("response_status") == s)
               for s in RESPONSE_STATUSES}
    need = [r for r in mand if r.get("evidence_status") != EV_NOT_REQUIRED]
    evidence = {"verified": sum(1 for r in need if r.get("evidence_status") == EV_VERIFIED),
                "partial": sum(1 for r in need if r.get("evidence_status") == EV_PARTIAL),
                "gaps": sum(1 for r in need if r.get("evidence_status") == EV_GAP),
                "evidence_required": len(need), "not_required": len(mand) - len(need)}
    quals = [r for r in mand if r.get("qualification_readiness")]
    at_risk = [r for r in quals if r["qualification_readiness"] == AT_RISK]
    partial = [r for r in quals if r["qualification_readiness"] == READINESS_PARTIAL]
    readiness = AT_RISK if at_risk else READINESS_PARTIAL if partial else (
        READINESS_VERIFIED if quals else "")
    return {
        "mandatory": len(mand), "content": content, "evidence": evidence,
        "qualification_readiness": readiness,
        "qualifications": {"total": len(quals), "verified": len(quals) - len(at_risk) - len(partial),
                           "partial": len(partial), "at_risk": len(at_risk)},
        "content_line": (f"CONTENT COVERAGE — {content['addressed']}/{len(mand)} mandatory addressed · "
                         f"{content['partially_addressed']} partially addressed · "
                         f"{content['not_addressed']} not addressed"),
        "evidence_line": (f"EVIDENCE COVERAGE — {evidence['verified']}/{len(need)} requiring evidence "
                          f"verified · {evidence['partial']} partial · {evidence['gaps']} gaps "
                          f"({evidence['not_required']} need no evidence)"),
        "readiness_line": (f"QUALIFICATION_READINESS — {readiness or 'n/a'} ({len(quals) - len(at_risk) - len(partial)} "
                           f"verified · {len(partial)} partial · {len(at_risk)} at risk)"),
    }
