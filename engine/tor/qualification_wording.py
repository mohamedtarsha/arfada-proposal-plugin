"""Client-facing qualification claims never stronger than the evidence (v0.6.15).

The internal engine grades each TOR qualification (EVIDENCE_STATUS + QUALIFICATION_
READINESS). The client draft must respect it:

  VERIFIED          the proposal may say the team demonstrates / meets it
  PARTIAL           state only the evidenced portion; the rest is a methodological
                    provision, never implied team experience
  GAP / AT_RISK     never say the team demonstrates or meets it; the proposal may explain
                    how the methodology complies — as a methodological provision

Internal labels (GAP, AT_RISK, PARTIAL…) never appear in client text. Deterministic
rewrites (used by the final-language sanitizer and reported by QA):

* a blanket "the qualification requirements can be met by the team collectively" →
  a neutral sentence about evidenced experience + methodological provisions;
* a qualification table's "how the team covers / meets it" column → a neutral header;
* in a PARTIAL / GAP row, each sentence about a not-evidenced element is labelled
  "Methodological provision:" (it is design, not prior personnel experience).

A sentence that attributes a not-evidenced element to a named expert or role (e.g.
"the Data Analyst's cluster-sampling experience") cannot be fixed by rewording and is
reported as a residual personnel-evidence error.
"""
from __future__ import annotations

import copy
import re
from typing import Optional

from .requirement_evidence import (QUALIFICATION_TYPES, EV_VERIFIED, EV_PARTIAL, EV_GAP,
                                   qualification_elements, qualification_readiness)

INTRO = ("The table below shows the selected team's evidenced experience together with the "
         "methodological provisions used to respond to the TOR requirements.")
TABLE_HEADER = "Evidenced team experience and methodological provisions"
PROVISION = "Methodological provision: "
INTERNAL_LABELS = re.compile(r"\b(?:AT_RISK|EVIDENCE_GAP|PARTIALLY_COVERED|FULLY_COVERED|"
                             r"QUALIFICATION_READINESS|EVIDENCE_STATUS|RESPONSE_STATUS|"
                             r"NOT_ADDRESSED|PARTIALLY_ADDRESSED)\b")

_BLANKET = re.compile(
    r"\b(?:the\s+)?(?:TOR['’]s\s+|TOR\s+)?(?:qualification|eligibility|personnel|team)\s+"
    r"requirements?\b[^.;\n]{0,40}?\b(?:can|will|are|is|have\s+been)\s+(?:be\s+|all\s+|fully\s+)*"
    r"(?:met|covered|fulfil+ed|satisfied)\s+by\s+the\s+(?:proposed\s+|selected\s+|core\s+)?team"
    r"|\b(?:the\s+)?(?:proposed\s+|selected\s+|core\s+)?team\s+(?:collectively\s+)?(?:meets|covers|"
    r"fulfils|fulfills|satisfies)\s+(?:all|each|every)\s+(?:of\s+)?(?:the\s+)?(?:TOR['’]?s?\s+)?"
    r"(?:qualification|requirement)", re.I)
_COVERED = re.compile(r"\bhow\s+(each|every)\s+((?:TOR\s+)?(?:qualification|requirement))\s+"
                      r"is\s+(?:covered|met|fulfil+ed|satisfied)\b", re.I)
# a qualification table: its first column names qualifications / competencies, or it is a
# requirements table whose other headers speak of the team (not ethics / submission tables)
_QUAL_HEAD = re.compile(r"qualif|competenc|expertise|personnel|eligib", re.I)
_REQ_HEAD = re.compile(r"requirement|criteri", re.I)
_TEAM_HEAD = re.compile(r"\bteam\b|\bexperts?\b|\bpersonnel\b", re.I)


def _is_qualification_table(cols: list) -> bool:
    if not cols:
        return False
    if re.search(r"\b(?:ethic\w*|submission|deliverable)\b", cols[0], re.I):
        return False
    return bool(_QUAL_HEAD.search(cols[0]) or
                (_REQ_HEAD.search(cols[0]) and any(_TEAM_HEAD.search(c) for c in cols[1:])))
_COVER_HEAD = re.compile(r"\b(?:cover\w*|meets?|fulfil\w*|satisf\w*)\b|how\s+the\s+team", re.I)
# sentences end at . ! ? or a line break (not at ';', which joins clauses of one sentence)
_SENT = re.compile(r"(?:[^.!?\n]|(?<=\b[A-Z])\.|\.(?=\d))*(?:[.!?\n]|$)")
_LEAD = re.compile(r"^\s*(?:applied|addressed|covered|met)\s+(?:in|through)\s+the\s+(?:evaluation\s+)?"
                   r"design\s*(?::|,|\bthrough\b)?\s*", re.I)
# extra cues for MENTIONS of an element in proposal text ("a cluster design", "Sphere")
_MENTION = {"cluster_sampling": r"\bcluster", "sphere": r"\bsphere\b",
            "sadd": r"disaggregat|\bsadd\b|washington\s+group|sex,?\s+age",
            "chs": r"\bchs\b|core\s+humanitarian\s+standard"}
_ROLE = re.compile(r"\b(?:team\s+leader|specialist|analyst|statistician|coordinator|expert|"
                   r"consultant|evaluator|adviser|advisor)\b", re.I)
# "Gender, Protection & Safeguarding Specialist: CHS-aligned case handling" lists CV experience
_ROLE_COLON = re.compile(r"^\s*[^.:]{0,80}\b(?:leader|specialist|analyst|statistician|coordinator|"
                         r"expert|consultant|evaluator)\b[^.:]{0,40}:", re.I)
_EXPERIENCE = re.compile(r"\b(?:experience[ds]?|expertise|track\s+record|background|skilled|"
                         r"proven|has\s+(?:led|conducted|designed)|CV|qualified)\b", re.I)


def _mention_patterns(key: str, places) -> list:
    from .response_coverage import _element_patterns
    pats = list(_element_patterns(key, places))
    if key in _MENTION:
        pats.append(_MENTION[key])
    return pats


def qualification_rows(state: dict) -> list:
    rows = []
    for r in (state or {}).get("requirement_evidence") or []:
        if r.get("requirement_type") not in QUALIFICATION_TYPES:
            continue
        r = dict(r)
        r["qualification_readiness"] = qualification_readiness(r)
        r["not_evidenced"] = [e["element"] for e in r.get("elements") or []
                              if e.get("status") != "VERIFIED" and e["element"] != "years"]
        rows.append(r)
    return rows


def _places(state: dict) -> list:
    return list((state or {}).get("places") or [])


def _match(cell: str, rows: list, places) -> Optional[dict]:
    """The qualification row a table's requirement cell refers to (by element overlap)."""
    el = set(qualification_elements(cell or "", places=places)["required"])
    if not el:
        return None
    best, score = None, 0.0
    for r in rows:
        req = {e["element"] for e in r.get("elements") or [] if e["element"] != "years"}
        if not req:
            continue
        j = len(el & req) / len(el | req)
        if j > score:
            best, score = r, j
    return best if score >= 0.5 else None


def _mentions(sentence: str, keys, places) -> list:
    return [k for k in keys if any(re.search(p, sentence, re.I) for p in _mention_patterns(k, places))]


def any_unverified(state: dict) -> bool:
    return any(r["qualification_readiness"] != "VERIFIED" and r.get("mandatory", True)
               for r in qualification_rows(state))


def find_qualification_issues(candidate: dict, state: dict, *, section_id: str = "") -> list:
    """[{kind, path, sentence, replacement, rewritable, detail}] — no mutation."""
    rows = qualification_rows(state)
    if not rows:
        return []
    places = _places(state)
    issues = []
    unverified = any_unverified(state)
    from .claim_language import candidate_texts
    for path, text in candidate_texts(candidate):
        if INTERNAL_LABELS.search(text or ""):
            issues.append({"kind": "INTERNAL_LABEL_IN_CLIENT_TEXT", "path": list(path),
                           "sentence": text[:200], "rewritable": False, "section_id": section_id,
                           "detail": "internal evidence label in proposal text"})
        if not unverified:
            continue
        sentences = [s.group(0) for s in _SENT.finditer(text or "") if s.group(0).strip()]
        for sent in sentences:
            if _BLANKET.search(sent):
                # the paragraph already introduces the table: drop the claim, don't repeat
                others = [x for x in sentences if x is not sent]
                repl = "" if any(re.search(r"\btable\s+below\b", x, re.I) for x in others) else INTRO
                issues.append({"kind": "BLANKET_QUALIFICATION_CLAIM", "path": list(path),
                               "sentence": sent.strip(), "replacement": repl, "rewritable": True,
                               "section_id": section_id,
                               "detail": "blanket claim that the team meets the TOR qualifications "
                                         "while some are not (fully) evidenced"})
            elif _COVERED.search(sent):
                issues.append({"kind": "BLANKET_QUALIFICATION_CLAIM", "path": list(path),
                               "sentence": sent.strip(),
                               "replacement": _COVERED.sub(lambda m: f"how {m.group(1)} "
                                                           f"{m.group(2)} is addressed", sent.strip()),
                               "rewritable": True, "section_id": section_id,
                               "detail": "'how each requirement is covered' implies full evidence"})
    for bi, b in enumerate(candidate.get("blocks", [])):
        if b.get("type") != "table":
            continue
        cols = [str(c) for c in b.get("columns") or []]
        if not _is_qualification_table(cols):
            continue
        matched = [(ri, _match(str(row[0]) if row else "", rows, places))
                   for ri, row in enumerate(b.get("rows") or [])]
        if not any(m for _ri, m in matched):
            continue
        for ci, c in enumerate(cols[1:], start=1):
            if unverified and _COVER_HEAD.search(c):
                issues.append({"kind": "QUALIFICATION_TABLE_HEADER", "path": [bi, "column", ci],
                               "sentence": c, "replacement": TABLE_HEADER, "rewritable": True,
                               "section_id": section_id,
                               "detail": f"column '{c}' presents every row as team coverage"})
        for ri, r in matched:
            if not r or r.get("evidence_status") == EV_VERIFIED or not r["not_evidenced"]:
                continue
            row = b["rows"][ri]
            for ci in range(1, len(row)):
                cell = str(row[ci] or "")
                new_parts, changed = [], False
                for s in _SENT.finditer(cell):
                    sent = s.group(0)
                    if not sent.strip():
                        new_parts.append(sent)
                        continue
                    named = _mentions(sent, r["not_evidenced"], places)
                    attributed = bool(_ROLE_COLON.match(sent) or
                                      (_ROLE.search(sent) and _EXPERIENCE.search(sent)))
                    if named and attributed:
                        issues.append({"kind": "UNEVIDENCED_PERSONNEL_CLAIM", "path": [bi, ri, ci],
                                       "sentence": sent.strip(), "rewritable": False,
                                       "section_id": section_id,
                                       "detail": f"attributes {', '.join(named)} to the team, but the "
                                                 "selected CVs do not evidence it"})
                        new_parts.append(sent)
                        continue
                    # GAP: nothing is evidenced, so every non-attributed sentence is design;
                    # PARTIAL: only the sentences about a not-evidenced element
                    hit = named or (r.get("evidence_status") == EV_GAP and not attributed)
                    if hit and not sent.lstrip().lower().startswith(PROVISION.strip().lower()):
                        lead = sent[:len(sent) - len(sent.lstrip())]
                        body = _LEAD.sub("", sent.lstrip())
                        body = body[:1].upper() + body[1:]
                        new_parts.append(lead + PROVISION + body)
                        changed = True
                    else:
                        new_parts.append(sent)
                if changed:
                    issues.append({"kind": "COMMITMENT_AS_QUALIFICATION", "path": [bi, ri, ci],
                                   "sentence": cell[:200], "replacement": "".join(new_parts),
                                   "rewritable": True, "section_id": section_id,
                                   "detail": f"'{str(row[0])[:60]}': methodological commitment shown as "
                                             f"team coverage (not evidenced: "
                                             f"{', '.join(r['not_evidenced'])})"})
    return issues


def sanitize_qualifications(candidate: dict, state: dict, *, section_id: str = "") -> tuple:
    """Apply the deterministic rewrites to a copy: (candidate, changes, residual)."""
    issues = find_qualification_issues(candidate, state, section_id=section_id)
    if not issues:
        return candidate, [], []
    cand = copy.deepcopy(candidate)
    changes, residual = [], []
    for it in issues:
        if not it.get("rewritable"):
            residual.append(it)
            continue
        p = it["path"]
        b = cand["blocks"][p[0]]
        if p[1] == "column":
            b["columns"][p[2]] = it["replacement"]
        elif it["kind"] == "COMMITMENT_AS_QUALIFICATION":
            b["rows"][p[1]][p[2]] = it["replacement"]
        else:
            bi, ii, ci = p
            fix = lambda t: " ".join(str(t).replace(it["sentence"], it["replacement"]).split())
            if ii is None:
                b["text"] = fix(b["text"])
            elif ci is None:
                b["items"][ii] = fix(b["items"][ii])
            else:
                b["rows"][ii][ci] = fix(b["rows"][ii][ci])
        changes.append(it)
    return cand, changes, residual


def rendering_policy(state: dict) -> dict:
    """What the writer may claim per qualification (for the generation packet)."""
    rows = qualification_rows(state)
    if not rows:
        return {}
    rules = {EV_VERIFIED: "May state that the proposed team demonstrates / meets it.",
             EV_PARTIAL: "State only the evidenced portion (named experts); write the rest as a "
                         "methodological provision — never imply full qualification evidence.",
             EV_GAP: "Never say the team demonstrates or meets it. You may explain how the "
                     "methodology complies, as a methodological provision — not prior experience."}
    out = []
    for r in rows:
        evidenced = [{"element": e["label"], "by": [x.get("name") for x in e.get("by") or []
                                                     if x.get("status") == "VERIFIED"]}
                     for e in r.get("elements") or [] if e.get("status") == "VERIFIED"]
        out.append({"req_id": r["req_id"], "requirement": r["text"][:160],
                    "evidence_status": r.get("evidence_status"),
                    "qualification_readiness": r["qualification_readiness"],
                    "evidenced": evidenced,
                    "not_evidenced": [e["label"] for e in r.get("elements") or []
                                      if e.get("status") != "VERIFIED"],
                    "client_rule": rules.get(r.get("evidence_status"), rules[EV_GAP])})
    return {"qualifications": out,
            "intro_wording": INTRO if any_unverified(state) else "",
            "instruction": ("Client-facing qualification claims must never be stronger than the "
                            "evidence: follow each client_rule; never write internal labels (GAP, "
                            "AT_RISK, PARTIAL) in the proposal; avoid blanket claims such as 'the "
                            "qualification requirements can be met by the team collectively'.")}
