"""Definitive-claim language checks, the final-language sanitizer and semantic QA (v0.6.11).

A sentence that states a fact as COMPLETE ("attached", "provided", "included",
"confirmed", "available", "registered", "submitted through …", "enclosed",
"annexed") is cross-checked against the canonical claim state:

* contradiction + deterministic rewrite  → the sentence is replaced with the safe
  provisional wording (SAFE_WORDING) before any client-style export;
* contradiction without a safe rewrite   → a QA finding (and the section fails
  validation so the writer repairs it).

Semantic checks (separate from numeric QA): an "Impact Evaluation" label while the
methodology limits inference to contribution; unverified personnel qualifications;
a local field roster claimed without evidence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .claim_state import SAFE_WORDING, VERIFIED, NOT_APPLICABLE

_DONE = r"(?:attached|provided|included|enclosed|annexed|submitted|appended|supplied)"
_IS = r"(?:is|are|has\s+been|have\s+been|was|were|been)"

# key -> (definitive-claim patterns, deterministic rewrite allowed)
CLAIM_PATTERNS: dict = {
    "registration_evidence": ([
        rf"\b(?:evidence|proof|copy|copies|certificates?)\s+of\s+(?:\w+['’]?s?\s+){{0,3}}?"
        rf"registration\b[^.;\n]{{0,80}}\b{_IS}\s+(?:also\s+)?{_DONE}\b",
        rf"\bregistration\s+(?:certificate|evidence|documents?)\b[^.;\n]{{0,60}}\b{_IS}\s+"
        rf"(?:also\s+)?{_DONE}\b",
        rf"\b(?:attached|enclosed|annexed|appended)\b[^.;\n]{{0,40}}\bregistration\b",
    ], True),
    "financial_proposal": ([
        r"\b(?:submission\s+)?(?:package|proposal|offer|submission)\b[^.;\n]{0,40}\b"
        r"(?:comprises|includes|contains|consists\s+of)\b[^.;\n]{0,80}\bfinancial\s+(?:proposal|offer)",
        rf"\bfinancial\s+(?:proposal|offer)\b[^.;\n]{{0,40}}\b{_IS}\s+(?:also\s+)?{_DONE}\b",
        r"\b(?:attached|enclosed|annexed|appended)\b[^.;\n]{0,40}\b(?:financial\s+(?:proposal|offer)|"
        r"detailed\s+budget)\b",
    ], True),
    "previous_work_sample": ([
        rf"\b(?:examples?|samples?)\s+of\s+(?:\w+['’]?s?\s+){{0,2}}?(?:previous|past|prior)\s+work\b"
        rf"[^.;\n]{{0,60}}\b{_IS}\s+(?:also\s+)?{_DONE}\b",
        r"\b(?:attached|enclosed|annexed|appended)\b[^.;\n]{0,40}\b(?:examples?|samples?)\s+of\s+"
        r"(?:previous|past|prior)\s+work\b",
        # v0.6.12: "the example report accompanies this proposal as a separate annex"
        r"\b(?:report|example|sample)\b[^.;\n]{0,120}\baccompan(?:y|ies|ied)\s+(?:this|the|our)\s+"
        r"(?:proposal|submission|offer|bid|application)\b",
        r"\b(?:example|sample|previous[- ]work|past[- ]work)\b[^.;\n]{0,80}\bas\s+an?\s+(?:separate\s+)?"
        r"annex\b",
        r"\b(?:example|sample)\s+(?:evaluation\s+)?report\b[^.;\n]{0,60}\b(?:is|are|has\s+been|have\s+been)"
        r"\s+(?:also\s+)?(?:attached|enclosed|annexed|provided|included|appended|submitted)\b",
    ], True),
    "team_cv_package": ([
        rf"\bCVs?\b[^.;\n]{{0,60}}\b{_IS}\s+(?:also\s+)?{_DONE}\b",
        r"\b(?:attached|enclosed|annexed|appended)\b[^.;\n]{0,30}\bCVs?\b",
    ], True),
    "team_availability": ([
        r"\b(?:proposed\s+|core\s+|all\s+)?(?:experts?|team(?:\s+members)?|consultants?|staff|"
        r"personnel|specialists?)\b[^.;\n]{0,50}\b(?:is|are)\s+(?:fully\s+|all\s+|both\s+)?"
        r"(?:available|confirmed)\b",
        rf"\bavailability\b[^.;\n]{{0,30}}\b{_IS}\s+(?:been\s+)?confirmed\b",
        r"\bhave\s+confirmed\s+(?:their\s+)?availability\b",
    ], True),
    "submission_channel": ([
        r"\b(?:channel|platform|portal|e-?mail\s+address|means)\s+(?:specified|indicated|requested|"
        r"stated|designated)\b",
        r"\bthrough\s+the\s+(?:channel|platform|portal)\s+(?:specified|indicated|requested)\b",
    ], True),
    "field_roster": ([
        r"\b(?:ARFADA|we|our\s+(?:firm|team|organi[sz]ation))\b[^.;\n]{0,30}\b(?:has|have|maintains?|"
        r"holds?|retains?|draws?\s+on)\s+(?:an?\s+|its\s+|our\s+)?(?:established\s+|existing\s+|ready\s+|"
        r"trained\s+|pre-?vetted\s+|standing\s+)?(?:local\s+|field\s+|national\s+|[A-Z][a-z]+\s+)?"
        r"(?:roster|pool|network)\s+of\b",
        r"\b(?:local|field)\s+(?:roster|pool)\b[^.;\n]{0,30}\b(?:is|are)\s+(?:in\s+place|ready|"
        r"available|established)\b",
    ], True),
}
# statements with no safe deterministic rewrite → finding only
UNSAFE_ONLY = {
    "registration_evidence": [r"\bARFADA\s+is\s+(?:a\s+)?(?:legally\s+|officially\s+|duly\s+)?registered\b"],
}

_IMPACT = re.compile(r"\bimpact\s+evaluation\b", re.I)
_CONTRIBUTION_ONLY = re.compile(
    r"\bno\s+causal\s+attribution\b|\bnot\s+(?:attempt\s+to\s+)?(?:establish|claim|attribute|"
    r"estimate)\s+(?:causal|causality|attribution|impact)\b|\bcontribution\s+analysis\b|"
    r"\bwithout\s+a\s+counterfactual\b|\bno\s+counterfactual\b|\bdoes\s+not\s+attribute\b|"
    r"\bcontribution[- ]focused\b|\bcontribution,?\s+(?:not|rather\s+than)\s+attribution\b", re.I)

# an initial ("M." in "Ahmed M. A. Elamin") or a decimal point is not a sentence end
_SENT = re.compile(r"(?:[^.;!?\n]|(?<=\b[A-Z])\.|\.(?=\d))*(?:[.;!?\n]|$)")


@dataclass
class ClaimIssue:
    claim: str
    status: str
    sentence: str
    section_id: str = ""
    rewritable: bool = True
    replacement: str = ""
    kind: str = "CLAIM_CONTRADICTION"
    detail: str = ""
    match: str = ""          # exact substring to replace (name rewrites)

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("kind", "claim", "status", "sentence",
                                              "section_id", "rewritable", "replacement",
                                              "detail", "match")}


def _status(state: dict, key: str) -> str:
    return ((state or {}).get("claims", {}).get(key) or {}).get("status", "")


def _unresolved(state: dict, key: str) -> bool:
    st = _status(state, key)
    return bool(st) and st not in (VERIFIED, NOT_APPLICABLE)


def _sentences(text: str):
    for m in _SENT.finditer(text or ""):
        s = m.group(0)
        if s.strip():
            yield s


def find_claim_issues(text: str, state: dict, *, section_id: str = "") -> list:
    """Definitive statements that contradict the claim state."""
    issues: list = []
    for sent in _sentences(text):
        if re.search(r"\b(?:will|shall|to\s+be|once|upon|when|if|pending|prior\s+to|before)\b",
                     sent, re.I) and not re.search(r"\b(?:specified|indicated|requested)\b", sent, re.I):
            # future / conditional wording is the allowed form (except "the channel
            # specified", which asserts the channel is known whatever the tense)
            continue
        for key, (pats, rewritable) in CLAIM_PATTERNS.items():
            if not _unresolved(state, key):
                continue
            if any(re.search(p, sent, re.I) for p in pats):
                issues.append(ClaimIssue(key, _status(state, key), sent.strip(), section_id,
                                         rewritable, SAFE_WORDING.get(key, "")))
                break
        else:
            for key, pats in UNSAFE_ONLY.items():
                if _unresolved(state, key) and any(re.search(p, sent, re.I) for p in pats):
                    issues.append(ClaimIssue(key, _status(state, key), sent.strip(), section_id,
                                             False, ""))
    # the submission-channel claim is wrong in any tense when the TOR leaves it open
    if _unresolved(state, "submission_channel"):
        pats = CLAIM_PATTERNS["submission_channel"][0]
        for sent in _sentences(text):
            if any(re.search(p, sent, re.I) for p in pats) and \
                    not any(i.sentence == sent.strip() for i in issues):
                issues.append(ClaimIssue("submission_channel", _status(state, "submission_channel"),
                                         sent.strip(), section_id, True,
                                         SAFE_WORDING["submission_channel"]))
    return issues


def _canonical(member: dict) -> str:
    """Full canonical name of a team member (v0.6.12 stable identity)."""
    name = member.get("canonical_name")
    if name:
        return " ".join(str(name).split())
    from .lknowledge.staff_identity import canonical_identity
    return canonical_identity({"source_file_name": str(member.get("name") or "")})["canonical_name"]


_QUALIFICATION_CUES = {
    "fsl": r"food\s+security|\bfsl\b|livelihood|\bfcs\b|rcsi",
    "evaluation": r"evaluat|\bmeal\b|m\s*&\s*e|base-?\s?line|end-?\s?line",
    "safeguarding": r"safeguard|\bpsea\b",
    "gender": r"\bgender\b",
    "protection": r"\bprotection\b|\bgbv\b",
    "software_tools": r"\b(?:spss|stata|kobo|odk|nvivo|python|power\s*bi)\b",
}


def find_personnel_issues(text: str, state: dict, *, section_id: str = "") -> list:
    """A named team member's qualification stated without VERIFIED CV evidence."""
    issues = []
    from .lknowledge.staff_identity import mentions, abbreviation_pattern
    for m in (state or {}).get("team") or []:
        full = _canonical(m)
        if len(full.split()) < 2:
            continue
        claims = m.get("claims") or {}
        for sent in _sentences(text):
            # a sentence is about this person only if it names them in full (or in an
            # initials form of THEIR full name) — shared tokens never link two people
            seen = mentions(sent, full)
            if not seen:
                continue
            if seen == "SHORT":
                pat = abbreviation_pattern(full)
                hit = pat.search(" ".join(sent.split())) if pat else None
                if hit and hit.group(0) != full:
                    issues.append(ClaimIssue("canonical_name", m.get("canonical_name_status",
                                                                     "PROVISIONAL"),
                                             sent.strip(), section_id, True, full,
                                             "STAFF_NAME_NOT_CANONICAL",
                                             f"render the full name '{full}', not '{hit.group(0)}'",
                                             hit.group(0)))
            y = re.search(r"\b(\d{1,2})\s*\+?\s*(?:years?|yrs)\b", sent, re.I)
            yc = claims.get("years_experience") or {}
            if y and (yc.get("status") != VERIFIED or int(y.group(1)) > int(yc.get("value") or 0)):
                issues.append(ClaimIssue("years_experience", yc.get("status", "UNVERIFIED"),
                                         sent.strip(), section_id, False, "",
                                         "PERSONNEL_UNVERIFIED",
                                         f"{full}: years not verified in the CV"))
                continue
            if not re.search(r"\b(?:experience|expertise|expert|specialist|background|track\s+record|"
                             r"skilled|proficient|qualified)\b", sent, re.I):
                continue
            for attr, cue in _QUALIFICATION_CUES.items():
                c = claims.get(attr) or {}
                if re.search(cue, sent, re.I) and c.get("status") not in (VERIFIED, None):
                    issues.append(ClaimIssue(attr, c.get("status", "UNVERIFIED"), sent.strip(),
                                             section_id, False, "", "PERSONNEL_UNVERIFIED",
                                             f"{full}: {attr} not verified in the CV"))
                    break
    return issues


def find_semantic_issues(texts: dict, *, labels: Optional[list] = None) -> list:
    """Proposal-level contradictions (not numeric): Impact Evaluation vs contribution."""
    issues = []
    all_text = "\n".join(texts.values())
    if _CONTRIBUTION_ONLY.search(all_text):
        for where, text in list(texts.items()) + [("COVER", l) for l in (labels or [])]:
            for sent in _sentences(text):
                if _IMPACT.search(sent):
                    issues.append(ClaimIssue("assignment_label", "CONTRADICTED", sent.strip(),
                                             where, True, "", "SEMANTIC_IMPACT_VS_CONTRIBUTION",
                                             "'Impact Evaluation' while the methodology limits "
                                             "inference to contribution (no causal attribution)"))
    return issues


def rewrite_impact(text: str) -> str:
    """'Endline / Impact Evaluation' → 'Endline Evaluation'; 'impact evaluation' → 'evaluation'."""
    t = re.sub(r"\s*/\s*Impact\s+Evaluation\b", " Evaluation", text)
    t = re.sub(r"\bEndline\s+Evaluation\s+Evaluation\b", "Endline Evaluation", t)
    return re.sub(r"\b[Ii]mpact\s+[Ee]valuation\b", lambda m: "evaluation" if m.group(0)[0] == "i"
                  else "Evaluation", t)


# ---------------------------------------------------------------------------
# section-level helpers
# ---------------------------------------------------------------------------

def candidate_texts(candidate: dict) -> list:
    """(path, text) for every text-bearing piece of a section candidate."""
    out = []
    for bi, b in enumerate(candidate.get("blocks", [])):
        t = b.get("type")
        if t in ("paragraph", "evidence_placeholder"):
            out.append(((bi, None, None), b.get("text", "")))
        elif t in ("bullet_list", "numbered_list"):
            for ii, it in enumerate(b.get("items", [])):
                out.append(((bi, ii, None), str(it)))
        elif t == "table":
            for ri, row in enumerate(b.get("rows", [])):
                for ci, cell in enumerate(row):
                    out.append(((bi, ri, ci), str(cell)))
    return out


def section_issues(candidate: dict, state: dict, *, section_id: str = "",
                   contribution_context: str = "") -> list:
    issues = []
    for _p, text in candidate_texts(candidate):
        issues += find_claim_issues(text, state, section_id=section_id)
        issues += find_personnel_issues(text, state, section_id=section_id)
        issues += find_duration_issues(text, state, section_id=section_id)
    if contribution_context and _CONTRIBUTION_ONLY.search(contribution_context):
        for _p, text in candidate_texts(candidate):
            issues += find_semantic_issues({section_id: text + "\n" + contribution_context})
    return issues


def sanitize_candidate(candidate: dict, state: dict, *, section_id: str = "",
                       contribution_context: str = "") -> tuple:
    """Rewrite deterministic contradictions in place (returns new candidate, changes, residual)."""
    import copy
    cand = copy.deepcopy(candidate)
    changes, residual = [], []
    contribution = bool(contribution_context and _CONTRIBUTION_ONLY.search(contribution_context))
    for (bi, ii, ci), text in candidate_texts(cand):
        new = text
        for issue in find_claim_issues(text, state, section_id=section_id):
            if issue.rewritable and issue.replacement:
                new = new.replace(issue.sentence, issue.replacement)
                changes.append(issue.to_dict())
            else:
                residual.append(issue.to_dict())
        for issue in find_personnel_issues(new, state, section_id=section_id):
            if issue.kind == "STAFF_NAME_NOT_CANONICAL" and issue.match and issue.replacement:
                # render the full canonical name instead of an initials form
                pat = re.compile(r"\s+".join(re.escape(t) for t in issue.match.split()))
                fixed = pat.sub(issue.replacement, new)
                if fixed != new:
                    changes.append(issue.to_dict())
                    new = fixed
                continue
            residual.append(issue.to_dict())
        for issue in find_duration_issues(new, state, section_id=section_id):
            new = new.replace(issue.match, issue.replacement)
            changes.append(issue.to_dict())
        if contribution and _IMPACT.search(new):
            fixed = rewrite_impact(new)
            if fixed != new:
                changes.append({"kind": "SEMANTIC_IMPACT_VS_CONTRIBUTION", "claim": "assignment_label",
                                "sentence": new.strip()[:200], "section_id": section_id,
                                "replacement": fixed.strip()[:200]})
                new = fixed
        if new != text:
            b = cand["blocks"][bi]
            if ii is None:
                b["text"] = new
            elif ci is None:
                b["items"][ii] = new
            else:
                b["rows"][ii][ci] = new
    # de-dup residual
    seen, res = set(), []
    for r in residual:
        k = (r["claim"], r["sentence"])
        if k not in seen:
            seen.add(k)
            res.append(r)
    return cand, changes, res


# ---------------------------------------------------------------------------
# v0.6.12: keep the TOR's duration wording ("30 days" is not "30 working days")
# ---------------------------------------------------------------------------

_DURATION_QUALIFIED = re.compile(
    r"\b(\d{1,3})\s+(working|calendar|business|consecutive)\s+(days?|weeks?|months?)\b", re.I)


def find_duration_issues(text: str, state: dict, *, section_id: str = "") -> list:
    """'N working days' where the TOR only ever says 'N days' (wording drift)."""
    mentions = (state or {}).get("tor_durations") or []
    if not mentions:
        return []
    tor = set()
    for m in mentions:
        try:
            n, q, u = str(m).split("|")
            tor.add((n, q, u))
        except ValueError:
            continue
    issues = []
    for m in _DURATION_QUALIFIED.finditer(text or ""):
        n, q, u = m.group(1), m.group(2).lower(), m.group(3).lower().rstrip("s")
        if (n, q, u) in tor or (n, "", u) not in tor:
            continue                        # the TOR uses this qualifier, or never says N u
        plain = f"{n} {m.group(3)}"
        issues.append(ClaimIssue("duration_wording", "TOR_WORDING", m.group(0), section_id,
                                 True, plain, "DURATION_WORDING",
                                 f"the TOR says '{n} {u}s', not '{m.group(0)}'", m.group(0)))
    return issues
