"""Requirement types and evidence-aware compliance coverage (v0.6.13).

Every TOR requirement gets a type:

  PERSONNEL_QUALIFICATION  what the proposed people must know / have done
                           ("Strong understanding of CHS, Sphere and safeguarding")
  COMPANY_QUALIFICATION    what the firm must have / be able to do
                           ("Capacity to deploy teams in South Darfur quickly")
  METHODOLOGY_REQUIREMENT  what the evaluation must do (a commitment satisfies it)
  DELIVERABLE_REQUIREMENT  an output to deliver
  SUBMISSION_ARTIFACT      a document the package must contain (registration, CVs…)
  DESIGN_CONSTRAINT        a fixed parameter / limit the design must respect

A methodology promise ("tools will be referenced to CHS and Sphere") never satisfies a
qualification. A qualification is covered only by evidence: the selected experts' CV
evidence (team level — a requirement can be met collectively unless the TOR assigns it
to a role) or, for the firm, verified company evidence.

EVIDENCE_STATUS (v0.6.14 — independent of the proposal text):

  VERIFIED      every required element evidenced
  PARTIAL       some elements evidenced, or evidence only PROVISIONAL
  GAP           nothing evidenced (the proposal can only commit)
  NOT_REQUIRED  a proposal commitment satisfies the requirement

Whether the proposal TEXT responds is a separate dimension (RESPONSE_STATUS,
``response_coverage.py``). An evidence gap never makes a requirement "not addressed".
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

PERSONNEL_QUALIFICATION = "PERSONNEL_QUALIFICATION"
COMPANY_QUALIFICATION = "COMPANY_QUALIFICATION"
METHODOLOGY_REQUIREMENT = "METHODOLOGY_REQUIREMENT"
DELIVERABLE_REQUIREMENT = "DELIVERABLE_REQUIREMENT"
SUBMISSION_ARTIFACT = "SUBMISSION_ARTIFACT"
DESIGN_CONSTRAINT = "DESIGN_CONSTRAINT"
REQUIREMENT_TYPES = (PERSONNEL_QUALIFICATION, COMPANY_QUALIFICATION, METHODOLOGY_REQUIREMENT,
                     DELIVERABLE_REQUIREMENT, SUBMISSION_ARTIFACT, DESIGN_CONSTRAINT)
QUALIFICATION_TYPES = (PERSONNEL_QUALIFICATION, COMPANY_QUALIFICATION)

# v0.6.14: EVIDENCE_STATUS is independent of whether the proposal TEXT responds
# (RESPONSE_STATUS, computed from the generated text in response_coverage.py)
EV_VERIFIED = "VERIFIED"            # every required element evidenced
EV_PARTIAL = "PARTIAL"              # some elements evidenced, or only PROVISIONAL evidence
EV_GAP = "GAP"                      # nothing evidenced (a commitment only)
EV_NOT_REQUIRED = "NOT_REQUIRED"    # a commitment satisfies it (methodology, deliverable…)
EVIDENCE_STATUSES = (EV_VERIFIED, EV_PARTIAL, EV_GAP, EV_NOT_REQUIRED)

# qualification readiness (internal review / final-submission readiness, never a draft blocker)
READINESS_VERIFIED, READINESS_PARTIAL, AT_RISK = "VERIFIED", "PARTIAL", "AT_RISK"

VERIFIED, PROVISIONAL, UNVERIFIED = "VERIFIED", "PROVISIONAL", "UNVERIFIED"
_H = r"[\s\-‐‑–]*"          # space / hyphen / non-breaking hyphen

# ---------------------------------------------------------------------------
# Requirement type
# ---------------------------------------------------------------------------

_QUAL_START = re.compile(
    r"^(?:(?:proven|demonstrated|strong|solid|good|excellent|extensive|previous|prior|relevant|"
    r"technical|in-?depth|sound|proven\s+track)\s+)*"
    r"(?:experience|expertise|familiarity|knowledge|understanding|ability|capacity|track\s+record|"
    r"skills?|proficiency|fluency|qualifications?|neutrality|(?:(?:at\s+least|minimum(?:\s+of)?|over|"
    r"more\s+than)\s+)?\d{1,2}\+?\s+years|(?:a\s+)?(?:master|bachelor|phd|degree)\b)", re.I)
_ARTIFACT_START = re.compile(
    r"^(?:evidence|proof|copy|copies|certificates?)\s+of\b|^(?:comprehensive\s+|company\s+|"
    r"organi[sz]ational\s+|firm\s+)?profile\s+of\b|^(?:cvs?|curriculum)\b", re.I)
_QUAL_WORD = re.compile(
    r"\b(?:experience[ds]?|expertise|expert|degree|master['’]?s?|bachelor|phd|skills?|competenc\w*|"
    r"qualifi\w*|knowledge|familiar\w*|understanding|ability|able\s+to|proficien\w*|fluen\w*|"
    r"years?|availability|track\s+record|capacity|neutrality)\b", re.I)
_COMPANY = re.compile(r"\b(?:firm|company|organi[sz]ation|consultancy|agency)\b|^capacity\b", re.I)
_COMPOSITION = re.compile(r"^the\s+(?:evaluation\s+|core\s+|proposed\s+)?(?:team|consultants?)\s+"
                          r"(?:should|must|shall|will)\s+(?:include|comprise|consist)", re.I)
_DESIGN = re.compile(
    r"\bshould\s+not\b|\bmust\s+not\b|\bshall\s+not\b|\bno\s+more\s+than\b|\bnot\s+exceed\b|"
    r"\bmaximum\b|\bwithin\s+\d+\s+(?:working\s+|calendar\s+)?days\b|\bconfidence\s+level\b|"
    r"\bmargin\s+of\s+error\b", re.I)


def requirement_type(req: dict) -> str:
    """One of REQUIREMENT_TYPES (deterministic, from category + wording)."""
    cat = str(req.get("category") or "")
    text = " ".join(str(req.get("text") or "").split())
    low = text.lower()
    if cat == "submission" or _ARTIFACT_START.match(low):
        return SUBMISSION_ARTIFACT
    if cat == "deliverable":
        return DELIVERABLE_REQUIREMENT
    if _COMPOSITION.match(low):
        return DESIGN_CONSTRAINT
    # an extractor 'team' line is a qualification only when it is worded as one (not a
    # list header "… the following competencies:", a scope item or a definition)
    team_qual = cat in ("team", "eligibility") and _QUAL_WORD.search(low) and \
        not low.rstrip().endswith(":") and not re.search(r"\blegal\s+entity\b", low)
    if team_qual or _QUAL_START.match(low):
        if _COMPANY.search(low) and not re.search(r"\b(?:team\s+leader|expert|specialist|"
                                                  r"consultant\s+(?:must|should))\b", low):
            return COMPANY_QUALIFICATION
        return PERSONNEL_QUALIFICATION
    ct = str(req.get("constraint_type") or "").upper()
    if ct not in ("", "NONE") or cat in ("timeline", "proposal_format") or _DESIGN.search(low):
        return DESIGN_CONSTRAINT
    return METHODOLOGY_REQUIREMENT


# ---------------------------------------------------------------------------
# Qualification elements ("topics"): requirement wording -> evidence wording
# ---------------------------------------------------------------------------

from .lknowledge.staff_evidence import EXPERTISE, TOOLS  # noqa: E402

TOPICS = [
    # key, label, requirement regex, evidence regex
    ("chs", "Core Humanitarian Standard (CHS)", r"\bchs\b|core\s+humanitarian\s+standard",
     r"\bchs\b|core\s+humanitarian\s+standard"),
    ("sphere", "Sphere Standards", r"\bsphere\b", r"\bsphere\b"),
    ("safeguarding", "safeguarding", r"safeguard|\bpsea\b|child\s+protection",
     EXPERTISE["safeguarding"]),
    ("fsl_indicators", "food security indicators (FCS, rCSI, HHS)",
     r"food\s+security\s+indicators|\bfcs\b|\brcsi\b|food\s+consumption\s+score|coping\s+strateg",
     r"\bfcs\b|rcsi|food\s+consumption|coping\s+strateg|household\s+hunger|\bhhs\b|\bhdds\b|\bfies\b"),
    ("fsl", "food security / FSL", r"food\s+security|\bfsl\b|livelihood", EXPERTISE["fsl"]),
    ("evaluation", "baseline / evaluation experience",
     rf"\bevaluations?\b|baseline\s+surveys?|end{_H}line", EXPERTISE["evaluation"]),
    ("mixed_methods", "mixed-methods evaluation", rf"mixed{_H}methods?",
     rf"mixed{_H}methods?|quantitative\s+and\s+qualitative|qualitative\s+and\s+quantitative"),
    ("triangulation", "data triangulation", r"triangulat", r"triangulat"),
    ("sadd", "sex-, age- and disability-disaggregated data (SADD)", r"disaggregat|\bsadd\b",
     r"disaggregat|\bsadd\b|washington\s+group"),
    ("qualitative", "qualitative research (FGDs, KIIs, observation)",
     r"qualitative|\bfgds?\b|focus\s+group|\bkiis?\b|key\s+informant",
     r"qualitative|focus\s+group|\bfgds?\b|key\s+informant|\bkiis?\b|in-?depth\s+interview"),
    ("thematic", "thematic analysis", r"thematic\s+analysis",
     r"thematic|nvivo|maxqda|atlas\.?\s?ti|codebook"),
    ("gender", "gender-sensitive approaches", r"gender", EXPERTISE["gender"]),
    ("protection", "protection risks", r"(?<!child\s)protection", EXPERTISE["protection"]),
    ("conflict", "insecure / conflict-affected settings", r"insecur|conflict",
     rf"insecur|conflict{_H}(?:sensitiv|affected|setting|context|zone|area)|fragile|volatile|"
     rf"hard{_H}to{_H}reach|do\s+no\s+harm|humanitarian\s+(?:crisis|emergenc)"),
    ("cluster_sampling", "cluster sampling", r"cluster\s+sampling", r"cluster\s+sampl|multi-?stage"),
    ("sampling", "survey design and sampling", r"survey\s+design|sampling\b",
     r"sampl|survey\s+design|questionnaire\s+design"),
    ("statistics", "statistical analysis software", r"statistic|\bspss\b|\bstata\b|software",
     TOOLS + r"|statistic"),
    ("capacity_building", "capacity building of partner staff",
     r"capacity\s+building|strengthening\s+local",
     rf"capacity{_H}building|training\s+of|trained\s+(?:\w+\s+){{0,2}}(?:staff|enumerators|partners|"
     rf"teams)|\btrainer\b|mentor"),
    ("inclusion", "inclusion of marginalized groups",
     rf"inclusion|marginali[sz]ed|female{_H}headed|\bidps?\b",
     rf"inclusi|marginali|disabilit|female{_H}headed|\bidps?\b|displace|vulnerable\s+groups?"),
    ("cultural", "neutrality and cultural sensitivity",
     r"cultural(?:ly)?\s+sensitiv|neutrality|impartial",
     rf"\bcultur(?:al|ally)\b|neutral|impartial|conflict{_H}sensitiv"),
    ("deploy", "rapid field deployment", r"\bdeploy|\bmobili[sz]", None),   # company: roster
]
_TOPIC_BY_KEY = {k: (label, rq, ev) for k, label, rq, ev in TOPICS}
_PREFERRED = re.compile(r"\b(?:preferably|ideally|is\s+an\s+asset|an\s+advantage|desirable|"
                        r"would\s+be\s+an\s+asset)\b", re.I)
_YEARS = re.compile(r"(?:at\s+least|minimum(?:\s+of)?|over|more\s+than)?\s*(\d{1,2})\s*\+?\s*"
                    r"(?:\(\w+\)\s*)?years?\b", re.I)
_ROLES = {
    "team_leader": r"team\s+leader|lead\s+(?:evaluator|consultant|researcher)|principal\s+investigator",
    "statistician": r"statistician|data\s+analyst|data\s+manager",
    "gender": r"gender\s+(?:and\s+\w+\s+)?(?:specialist|expert|advisor|adviser)",
    "fsl": r"(?:fsl|food\s+security)\s+(?:and\s+livelihoods?\s+)?(?:specialist|expert|advisor|adviser)",
    "field": r"field\s+(?:coordinator|supervisor|manager)",
}


def qualification_elements(text: str, *, places: Iterable[str] = ()) -> dict:
    """Required / preferred elements of a qualification requirement."""
    t = " ".join(str(text or "").split())
    m = _PREFERRED.search(t)
    req_part, pref_part = (t[:m.start()], t[m.end():]) if m else (t, "")
    out = {"required": [], "preferred": [], "min_years": None, "places": [], "assigned_role": ""}
    for part, bucket in ((req_part, "required"), (pref_part, "preferred")):
        for key, _label, rq, _ev in TOPICS:
            if re.search(rq, part, re.I) and key not in out["required"]:
                out[bucket].append(key)
        hits = [p for p in places if p and re.search(re.escape(p), part, re.I)]
        if hits and "local_area" not in out["required"]:
            out[bucket].append("local_area")
            out["places"] = sorted(set(out["places"]) | set(hits))
    # "baseline surveys / evaluations related to FSL" — fsl indicators only when named
    if "fsl_indicators" in out["required"] and "fsl" not in out["required"] and \
            re.search(r"food\s+security", req_part, re.I):
        out["required"].append("fsl")
    y = _YEARS.search(req_part)
    if y:
        out["min_years"] = int(y.group(1))
    for role, rx in _ROLES.items():
        if re.search(rx, t, re.I):
            out["assigned_role"] = role
            break
    return out


# ---------------------------------------------------------------------------
# Evidence per selected expert
# ---------------------------------------------------------------------------

def _excerpt(text: str, m: re.Match, width: int = 70) -> str:
    s, e = max(0, m.start() - width), min(len(text), m.end() + width)
    return " ".join(text[s:e].split())[:160]


def member_topic_evidence(profile: dict, *, staff_facts: Optional[list] = None,
                          places: Iterable[str] = ()) -> dict:
    """{topic: {status, source, evidence}} for one selected expert.

    VERIFIED from the CV's own evidence text / promoted staff facts (quoted), PROVISIONAL
    from ARFADA's filing folder only, UNVERIFIED otherwise. Job titles are never evidence.
    """
    from .lknowledge.staff_evidence import _snippets, _folders
    snip, fold = _snippets(profile), _folders(profile)
    facts = [f for f in (staff_facts or []) if f.get("verified") and
             f.get("staff_id") in (profile.get("staff_id"), profile.get("staff_profile_id"))]
    fact_text = " ".join(" ".join([str(f.get("attribute") or "").replace("_", " "),
                                   str(f.get("value") or ""),
                                   str((f.get("provenance") or {}).get("quote") or f.get("quote") or "")])
                         for f in facts)
    verified_text = " ".join([snip, fact_text])
    out = {}
    topics = [(k, ev) for k, _l, _r, ev in TOPICS if ev]
    plist = [p for p in places if p]
    if plist:
        topics.append(("local_area", "|".join(re.escape(p) for p in plist)))
    for key, ev in topics:
        m = re.search(ev, verified_text, re.I)
        if m:
            src = "promoted staff fact" if m.start() > len(snip) else "CV evidence text"
            out[key] = {"status": VERIFIED, "source": src, "evidence": _excerpt(verified_text, m)}
            continue
        m = re.search(ev, fold, re.I) if fold else None
        out[key] = ({"status": PROVISIONAL, "source": "ARFADA CV filing folder",
                     "evidence": fold[:120]} if m else
                    {"status": UNVERIFIED, "source": "", "evidence": ""})
    return out


# ---------------------------------------------------------------------------
# Team-level coverage matrix
# ---------------------------------------------------------------------------

_RANK = {VERIFIED: 2, PROVISIONAL: 1}


def _role_key(role: str) -> str:
    for key, rx in _ROLES.items():
        if re.search(rx, role or "", re.I):
            return key
    return ""


def _years(member: dict) -> tuple:
    y = ((member.get("claims") or {}).get("years_experience") or {})
    return y.get("value"), y.get("status", UNVERIFIED)


def _element(key, members, *, company: Optional[dict] = None) -> dict:
    label = _TOPIC_BY_KEY.get(key, ("TOR location" if key == "local_area" else key,))[0]
    if key == "deploy":
        st = (company or {}).get("field_roster", UNVERIFIED)
        st = st if st in (VERIFIED, PROVISIONAL) else UNVERIFIED
        return {"element": key, "label": label, "status": st,
                "by": [{"source": "company field roster", "status": st,
                        "evidence": (company or {}).get("field_roster_detail", "")}]}
    by = []
    for m in members:
        ev = (m.get("qualification_evidence") or {}).get(key) or {}
        if ev.get("status") in (VERIFIED, PROVISIONAL):
            by.append({"staff_profile_id": m.get("staff_profile_id") or m.get("staff_id"),
                       "name": m.get("canonical_name") or m.get("name", ""),
                       "role": m.get("role", ""), "status": ev["status"],
                       "evidence": ev.get("evidence", "")})
    best = max((_RANK[b["status"]] for b in by), default=0)
    status = {2: VERIFIED, 1: PROVISIONAL}.get(best, UNVERIFIED)
    return {"element": key, "label": label, "status": status, "by": by}


def evidence_coverage(req: dict, team: list, *, places: Iterable[str] = (),
                      company: Optional[dict] = None, claims: Optional[dict] = None) -> dict:
    """Evidence-only coverage of one requirement (the draft's ledger is applied later)."""
    rtype = requirement_type(req)
    row = {"req_id": req.get("req_id", ""), "text": " ".join(str(req.get("text") or "").split())[:220],
           "requirement_type": rtype, "mandatory": bool(req.get("mandatory", True)),
           "scope": "", "assigned_role": "", "elements": [], "preferred": [], "min_years": None,
           "evidence_status": "", "basis": "", "gaps": []}
    if rtype == SUBMISSION_ARTIFACT:
        from .submission import identify_item, is_status_item
        text = req.get("text") or ""
        key, label = identify_item(text)
        keys = [k for k in [{"registration": "registration_evidence",
                             "detailed_budget": "financial_proposal",
                             "previous_work": "previous_work_sample",
                             "cv_annex": "team_cv_package"}.get(key)] if k]
        if not keys and re.search(r"\bregistration\b", text, re.I):
            keys = ["registration_evidence"]
        if is_status_item(text):                      # deadline / channel instructions
            label = "Submission channel / deadline"
            keys = ([k for k, rx in (("deadline", r"\bdeadline\b|\bby\s+\d|\bclosing\b"),
                                     ("submission_channel", r"\bvia\b|\bthrough\b|\bportal\b|"
                                                            r"e-?mail|platform"))
                     if re.search(rx, text, re.I)] or ["deadline"])
        row["scope"] = "PACKAGE"
        if keys:
            order = {VERIFIED: 3, "NOT_APPLICABLE": 3, PROVISIONAL: 2}
            sts = [((claims or {}).get(k) or {}).get("status", UNVERIFIED) for k in keys]
            st = min(sts, key=lambda s: order.get(s, 0))
            row["evidence_status"] = (EV_VERIFIED if order.get(st, 0) == 3 else
                                      EV_PARTIAL if st == PROVISIONAL else EV_GAP)
            row["basis"] = "claim state: " + ", ".join(f"{k} {s}" for k, s in zip(keys, sts))
            if row["evidence_status"] != EV_VERIFIED:
                row["gaps"] = [label]
        else:
            row["evidence_status"] = EV_NOT_REQUIRED
            row["basis"] = "proposal content (answered by the technical proposal itself)"
        return row
    if rtype not in QUALIFICATION_TYPES:
        row["scope"] = "COMMITMENT"
        row["evidence_status"] = EV_NOT_REQUIRED
        row["basis"] = "a proposal commitment satisfies this requirement"
        return row

    el = qualification_elements(req.get("text") or "", places=places)
    row["assigned_role"] = el["assigned_role"]
    row["min_years"] = el["min_years"]
    members = list(team or [])
    if el["assigned_role"]:
        members = [m for m in members if _role_key(m.get("role", "")) == el["assigned_role"]]
        row["scope"] = "ROLE_ASSIGNED"
    else:
        row["scope"] = "COMPANY" if rtype == COMPANY_QUALIFICATION else "TEAM_COLLECTIVE"
    required = list(el["required"])
    if rtype == COMPANY_QUALIFICATION and not required:
        required = []
    row["elements"] = [_element(k, members, company=company) for k in required]
    row["preferred"] = [_element(k, members, company=company) for k in el["preferred"]]

    # "at least N years of <X>": one person must hold the years AND the named experience
    if el["min_years"]:
        topical = [k for k in required if k not in ("deploy",)]
        best = UNVERIFIED
        holder = None
        for m in members:
            val, st = _years(m)
            if val is None or float(val) < el["min_years"] or st not in (VERIFIED, PROVISIONAL):
                continue
            ev = m.get("qualification_evidence") or {}
            sts = [ev.get(k, {}).get("status", UNVERIFIED) for k in topical]
            if all(s in (VERIFIED, PROVISIONAL) for s in sts):
                cand = VERIFIED if st == VERIFIED and all(s == VERIFIED for s in sts) else PROVISIONAL
                if _RANK.get(cand, 0) > _RANK.get(best, 0):
                    best, holder = cand, m
        row["elements"].append({
            "element": "years", "label": f"at least {el['min_years']} years (one expert, same field)",
            "status": best,
            "by": ([{"staff_profile_id": holder.get("staff_profile_id") or holder.get("staff_id"),
                     "name": holder.get("canonical_name") or holder.get("name", ""),
                     "role": holder.get("role", ""), "status": best,
                     "evidence": f"{_years(holder)[0]} years"}] if holder else [])})

    if not team:
        row["evidence_status"] = EV_GAP
        row["basis"] = "no team selected — methodology commitments are not qualification evidence"
        row["gaps"] = [e["label"] for e in row["elements"]] or ["selected-expert evidence"]
        return row
    if not row["elements"]:
        row["evidence_status"] = EV_PARTIAL
        row["basis"] = "no deterministic evidence rule for this wording — reviewer to confirm"
        row["gaps"] = ["reviewer confirmation"]
        return row
    sts = [e["status"] for e in row["elements"]]
    row["gaps"] = [e["label"] for e in row["elements"] if e["status"] != VERIFIED]
    if all(s == VERIFIED for s in sts):
        row["evidence_status"] = EV_VERIFIED
        row["basis"] = ("verified company evidence" if row["scope"] == "COMPANY"
                        else "selected-expert CV evidence")
    elif any(s in (VERIFIED, PROVISIONAL) for s in sts):
        row["evidence_status"] = EV_PARTIAL
        row["basis"] = "part of the requirement is evidenced; the rest is a commitment only"
    else:
        row["evidence_status"] = EV_GAP
        row["basis"] = "methodology commitment only — no selected-expert or company evidence"
    return row


def evidence_matrix(requirements: list, team: list, *, places: Iterable[str] = (),
                    company: Optional[dict] = None, claims: Optional[dict] = None) -> list:
    """Evidence-only coverage rows for every bidder requirement (client obligations excluded)."""
    return [evidence_coverage(r, team, places=places, company=company, claims=claims)
            for r in requirements or [] if r.get("actor") != "CLIENT"]


def qualification_readiness(row: dict) -> str:
    """VERIFIED / PARTIAL / AT_RISK for a qualification row ('' for other types)."""
    if row.get("requirement_type") not in QUALIFICATION_TYPES:
        return ""
    return {EV_VERIFIED: READINESS_VERIFIED, EV_PARTIAL: READINESS_PARTIAL}.get(
        row.get("evidence_status"), AT_RISK)
