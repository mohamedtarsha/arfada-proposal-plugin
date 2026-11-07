"""PE2 first-class object derivation (spec §4-10, §30-31).

Turns the flat requirement list + fields into queryable structured objects:
deliverables, methods, sampling constraints, team requirements, evaluation
questions, submission requirements, scoring criteria, and defined terms — each
with provenance carried straight from its source requirement/cell. Deterministic;
never invents values; preserves numeric qualifiers via `value.parse_quantities`.
"""
from __future__ import annotations

import hashlib
import re

from . import value


def _id(*p) -> str:
    return hashlib.sha1("|".join(str(x) for x in p).encode()).hexdigest()[:16]


def _prov(r):
    return (r.source_locator or "", r.block_sequence)


_DELIV_NAMES = [
    ("inception report", "Inception Report"), ("draft report", "Draft Report"),
    ("final report", "Final Report"), ("final assessment report", "Final Report"),
    ("final study report", "Final Report"), ("dataset", "Dataset"), ("raw data", "Dataset"),
    ("presentation", "Presentation"), ("power point", "Presentation"), ("powerpoint", "Presentation"),
    ("validation workshop", "Validation Workshop"), ("workshop", "Workshop"),
    ("data collection tool", "Tools"), ("tools", "Tools"), ("work plan", "Work Plan"),
    ("workplan", "Work Plan"), ("methodology", "Methodology Note"),
]
_DAYS = re.compile(r"\b(working\s+days|calendar\s+days)\b", re.I)
_RELATIVE = [
    (r"after\s+(?:the\s+)?fieldwork|end of (?:the )?data collection", "FIELDWORK_COMPLETION"),
    (r"after\s+(?:the\s+)?(?:contract|agreement)\s+sign|after\s+signature|commencement", "CONTRACT_SIGNATURE"),
    (r"after\s+(?:the\s+)?inception", "INCEPTION_APPROVAL"),
    (r"following the desk review|prior to (?:beginning )?field", "AFTER_DESK_REVIEW"),
    (r"after\s+(?:the\s+)?draft", "AFTER_DRAFT"),
    (r"upon (?:approval|submission)", "UPON_APPROVAL"),
]
_LANGS_IN = re.compile(r"\b(english|arabic|french|kurdish|spanish|dari|pashto)\b", re.I)
_REVIEW = re.compile(r"\b(approv|review|valida|accept|sign[- ]off|comment)", re.I)
_REVIS = re.compile(r"\b(one|two|three|\d+)\s+(?:round|revision|iteration)s?\b", re.I)


def _relative_to(low):
    for pat, label in _RELATIVE:
        if re.search(pat, low):
            return label
    return ""


def deliverables(analysis_id, aid, reqs):
    out = []
    for r in reqs:
        low = r.text.lower()
        if r.category != "deliverable" and not any(k in low for k, _ in _DELIV_NAMES):
            continue
        name = next((label for k, label in _DELIV_NAMES if k in low), "Deliverable")
        qs = value.parse_quantities(r.text)
        timing = next((q for q in qs if q.kind in ("DURATION", "DATE")), None)
        day_type = ""
        m = _DAYS.search(r.text)
        if m:
            day_type = m.group(1).lower().replace(" ", "_")
        elif timing and timing.kind == "DURATION":
            day_type = "calendar_days" if "day" in (timing.unit or "") else ""
        lang = _LANGS_IN.search(r.text)
        rev = _REVIS.search(low)
        loc, seq = _prov(r)
        out.append(dict(id=_id("del", r.req_id), analysis_id=analysis_id, assignment_id=aid,
                        name=name, description=r.text[:400],
                        timing_raw=(timing.raw if timing else ""),
                        timing_qualifier=(timing.qualifier if timing else ""), day_type=day_type,
                        relative_to=_relative_to(low), fmt="", language=(lang.group(1).title() if lang else ""),
                        contents="", review_condition=("review/approval" if _REVIEW.search(low) else ""),
                        revisions=(rev.group(0) if rev else ""), channel=("email" if "email" in low else ""),
                        mandatory=int(r.mandatory), source_locator=loc, block_sequence=seq,
                        confidence=r.confidence))
    return out


_METHODS = [("kii", "KII"), ("key informant", "KII"), ("fgd", "FGD"), ("focus group", "FGD"),
            ("idi", "IDI"), ("in-depth interview", "IDI"), ("household survey", "Survey"),
            ("survey", "Survey"), ("questionnaire", "Questionnaire"), ("desk review", "Desk Review"),
            ("secondary data", "Desk Review"), ("observation", "Observation"),
            ("field visit", "Field Visit"), ("workshop", "Workshop"), ("case study", "Case Study"),
            ("mixed method", "Mixed Methods"), ("remote", "Remote Data Collection")]


def methods(analysis_id, aid, reqs):
    out, seen = [], set()
    for r in reqs:
        low = r.text.lower()
        if r.category not in ("methodology", "data_collection_methods") and \
           not any(k in low for k, _ in _METHODS):
            continue
        for k, label in _METHODS:
            if k in low and (label) not in seen:
                seen.add(label)
                loc, seq = _prov(r)
                out.append(dict(id=_id("m", aid, label), analysis_id=analysis_id, assignment_id=aid,
                                method=label, detail=r.text[:300], mandatory=int(r.mandatory),
                                source_locator=loc, block_sequence=seq))
    return out


_APPROACHES = ("stratified", "multi-stage", "cluster", "purposive", "random", "systematic",
               "snowball", "quota", "convenience")
_DISAGG = ("age", "gender", "sex", "disability", "displacement", "vulnerability", "location")


def sampling(analysis_id, aid, reqs):
    out = []

    def add(attr, raw, val, vmax, unit, qual, r):
        loc, seq = _prov(r)
        out.append(dict(id=_id("s", r.req_id, attr, raw), analysis_id=analysis_id, assignment_id=aid,
                        attribute=attr, raw=raw[:200], value=val, value_max=vmax, unit=unit,
                        qualifier=qual, source_locator=loc, block_sequence=seq))
    for r in reqs:
        low = r.text.lower()
        if r.category != "sampling" and not any(w in low for w in
                                                ("sampl", "confidence", "margin of error", "respondent")):
            continue
        for ap in _APPROACHES:
            if ap in low:
                add("approach", ap, None, None, "", "EXACT", r)
        for q in value.parse_quantities(r.text):
            if q.kind == "PERCENT" and "confidence" in low:
                add("confidence_level", q.raw, q.value, None, "%", q.qualifier, r)
            elif q.kind == "PERCENT" and "margin" in low:
                add("margin_of_error", q.raw, q.value, None, "%", q.qualifier, r)
            elif q.kind in ("INT", "RANGE") and ("sample" in low or "respondent" in low or
                                                 "household" in low):
                add("sample_size", q.raw, q.value, q.value_max, "", q.qualifier, r)
        dis = [d for d in _DISAGG if re.search(r"\b" + d + r"\b", low)]
        if "disaggregat" in low and dis:
            add("disaggregation", ",".join(dis), None, None, "", "EXACT", r)
    return out


_ROLES = [("team leader", "Team Leader"), ("evaluator", "Evaluator"), ("enumerator", "Enumerator"),
          ("gender specialist", "Gender Specialist"), ("specialist", "Specialist"),
          ("expert", "Expert"), ("statistician", "Statistician"), ("data analyst", "Data Analyst"),
          ("consultant", "Consultant"), ("researcher", "Researcher")]
_EDU = [("phd", "PhD"), ("doctorate", "PhD"), ("master", "Master"), ("bachelor", "Bachelor"),
        ("degree", "Degree")]
_LANG = ("english", "arabic", "french", "kurdish", "spanish", "dari", "pashto")


_DISCIPLINE = ("social science", "public health", "education", "economics", "statistics",
               "development studies", "nutrition", "environment", "wash", "psychology",
               "international development", "monitoring and evaluation", "anthropolog")
_COUNTRY_EXP = re.compile(r"experience\s+(?:in|working in|of working in)\s+([A-Z][a-z]+"
                          r"(?:\s+[A-Z][a-z]+)?)")
_CERT = ("pmp", "certified", "accreditation", "license", "chartered")
_HEAD = re.compile(r"\b(?:a\s+)?(?:team|minimum|at least)\s+(?:of\s+)?(\d+)\s+(?:experts?|"
                   r"consultants?|members?|persons?|staff|enumerators?)\b", re.I)


def team(analysis_id, aid, reqs):
    out = []
    for r in reqs:
        low = r.text.lower()
        if r.category != "team":
            continue
        role = next((lab for k, lab in _ROLES if k in low), "")
        edu = next((lab for k, lab in _EDU if k in low), "")
        disc = next((d for d in _DISCIPLINE if d in low), "")
        yrs = next((q for q in value.parse_quantities(r.text)
                    if q.kind == "DURATION" and q.unit == "years"), None)
        if not yrs:
            m = re.search(r"(\d+)\s*\+?\s*years?", low)
            yq = ("AT_LEAST" if ("at least" in low or "minimum" in low or "+" in low) else "EXACT")
            yrs_raw, yq = (m.group(0), yq) if m else ("", "")
        else:
            yrs_raw, yq = yrs.raw, yrs.qualifier
        cexp = _COUNTRY_EXP.search(r.text)
        cert = next((c for c in _CERT if c in low), "")
        gender = ("female" if "female" in low or "woman" in low else
                  ("male" if "male expert" in low else ""))
        head = _HEAD.search(r.text)
        langs = [l for l in _LANG if l in low]
        ni = ("international" if "international" in low else ("national" if "national" in low else ""))
        loc, seq = _prov(r)
        out.append(dict(id=_id("t", r.req_id), analysis_id=analysis_id, assignment_id=aid,
                        role=role, headcount=(head.group(1) if head else ""), education=edu,
                        discipline=disc, years_experience_raw=yrs_raw, years_qualifier=yq,
                        experience_type=r.text[:200], country_experience=(cexp.group(1) if cexp else ""),
                        certification=cert, gender_condition=gender, language=",".join(langs),
                        national_intl=ni, mandatory=int(r.mandatory), source_locator=loc,
                        block_sequence=seq))
    return out


# ---- timeline / milestones (spec §9) ----
_MILESTONES = [
    ("inception", "INCEPTION"), ("fieldwork", "FIELDWORK"), ("field work", "FIELDWORK"),
    ("data collection", "FIELDWORK"), ("draft report", "DRAFT_REPORT"), ("draft final", "DRAFT_REPORT"),
    ("validation", "VALIDATION"), ("final report", "FINAL_REPORT"), ("final assessment", "FINAL_REPORT"),
    ("deadline", "SUBMISSION_DEADLINE"), ("closing date", "SUBMISSION_DEADLINE"),
    ("submission", "SUBMISSION_DEADLINE"), ("duration", "ASSIGNMENT_DURATION"),
    ("start date", "EXPECTED_START"), ("end date", "EXPECTED_END"), ("commence", "EXPECTED_START"),
]


def timeline(analysis_id, aid, reqs):
    out = []
    for r in reqs:
        # a submission deadline/window is NOT a project-timeline milestone (spec §17, §20):
        # never let submission requirements contaminate the project timeline.
        if getattr(r, "category", "") == "submission":
            continue
        low = r.text.lower()
        qs = value.parse_quantities(r.text)
        temporal = [q for q in qs if q.kind in ("DURATION", "DATE", "TIME", "RANGE")]
        if not temporal and not any(k in low for k, _ in _MILESTONES):
            continue
        milestone = next((lab for k, lab in _MILESTONES if k in low), "OTHER_MILESTONE")
        for q in (temporal or [None]):
            day_type = ("working_days" if "working day" in low else
                        ("calendar_days" if "calendar day" in low or (q and q.unit == "days") else ""))
            tz = ""
            mtz = re.search(r"\b(EET|EEST|GMT|UTC|CET|EST|AST)\b", r.text)
            if mtz:
                tz = mtz.group(1)
            loc, seq = _prov(r)
            out.append(dict(id=_id("tl", r.req_id, milestone, q.raw if q else ""),
                            analysis_id=analysis_id, assignment_id=aid, milestone=milestone,
                            raw=(q.raw if q else r.text[:80]),
                            value=(q.value if q else None), value_max=(q.value_max if q else None),
                            date_norm=(q.raw if q and q.kind == "DATE" else ""),
                            time_norm=(q.raw if q and q.kind == "TIME" else ""), timezone=tz,
                            day_type=day_type, qualifier=(q.qualifier if q else "EXACT"),
                            relative_to=_relative_to(low), source_locator=loc, block_sequence=seq,
                            confidence=r.confidence))
    return out


# ---- organizational eligibility (spec §11) — SEPARATE from team ----
_ELIG = [
    ("company_years", ("company", "firm", "organization", "organisation")),
    ("similar_assignments", ("similar assignment", "similar project", "comparable assignment",
                             "track record of similar")),
    ("legal_registration", ("legally registered", "registration certificate", "legal registration",
                            "certificate of incorporation", "registered company")),
    ("tax", ("tax", "vat", "fiscal")),
    ("insurance", ("insurance", "liability cover")),
    ("references", ("references", "reference letter", "recommendation letter")),
    ("financial_capacity", ("financial capacity", "turnover", "audited accounts", "bank statement")),
    ("conflict_declaration", ("conflict of interest", "independence", "declaration of")),
    ("data_protection", ("data protection", "gdpr", "data policy")),
    ("licenses", ("license", "licence", "permit to operate", "accreditation")),
]


def eligibility(analysis_id, aid, reqs):
    out = []
    for r in reqs:
        low = r.text.lower()
        # organizational cues; exclude person-level (team) unless org keyword present
        for kind, cues in _ELIG:
            if any(c in low for c in cues):
                # skip if clearly a person qualification (e.g. "the expert's registration")
                if kind == "company_years" and not re.search(
                        r"(company|firm|organi[sz]ation).{0,40}(year|experience|established)", low):
                    continue
                loc, seq = _prov(r)
                out.append(dict(id=_id("el", r.req_id, kind), analysis_id=analysis_id,
                                assignment_id=aid, kind=kind, detail=r.text[:200],
                                value_raw="", mandatory=int(r.mandatory), source_locator=loc,
                                block_sequence=seq))
                break
    return out


# ---- language requirements (spec §12) — do NOT infer from doc language ----
_LANG_SCOPES = [
    ("report_language", ("report", "reporting", "deliverable")),
    ("tool_language", ("tool", "questionnaire", "instrument", "survey")),
    ("fieldwork_language", ("fieldwork", "data collection", "interview", "enumerat", "respondent")),
    ("proposal_language", ("proposal", "bid", "offer", "submission")),
]


def language(analysis_id, aid, reqs):
    out, seen = [], set()
    for r in reqs:
        low = r.text.lower()
        langs = _LANGS_IN.findall(r.text)
        if not langs:
            continue
        # only when the sentence is actually ABOUT language use, not incidental
        if not any(w in low for w in ("language", "written in", "prepared in", "translat",
                                      "interpret", "in english", "in arabic", "bilingual",
                                      "available in")):
            continue
        scope = next((s for s, cues in _LANG_SCOPES if any(c in low for c in cues)), "report_language")
        loc, seq = _prov(r)
        for lg in set(l.title() for l in langs):
            k = (scope, lg)
            if k in seen:
                continue
            seen.add(k)
            out.append(dict(id=_id("lg", aid, scope, lg), analysis_id=analysis_id, assignment_id=aid,
                            scope=scope, language=lg, source_locator=loc, block_sequence=seq))
        if "translat" in low:
            k = ("translation_required", "yes")
            if k not in seen:
                seen.add(k)
                out.append(dict(id=_id("lg", aid, "translation", "req"), analysis_id=analysis_id,
                                assignment_id=aid, scope="translation_required", language="yes",
                                source_locator=loc, block_sequence=seq))
    return out


_CRITERIA = ("relevance", "effectiveness", "efficiency", "impact", "sustainability", "coherence",
             "equity", "coverage", "connectedness", "appropriateness")


def eval_questions(analysis_id, aid, reqs):
    out = []
    for r in reqs:
        if r.category != "evaluation_questions" and not r.text.rstrip().endswith("?"):
            continue
        crit = next((c for c in _CRITERIA if c in r.text.lower()), "")
        loc, seq = _prov(r)
        out.append(dict(id=_id("eq", r.req_id), analysis_id=analysis_id, assignment_id=aid,
                        text=r.text[:500], criterion=crit, source_locator=loc, block_sequence=seq))
    return out


# deterministic submission-critical-field patterns (spec §2-8)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_URL_RE = re.compile(r"https?://[^\s)>\]]+|www\.[^\s)>\]]+", re.I)
_SUBJECT_RE = re.compile(r"subject\s*(?:line|title)?\s*[:\-]\s*[\"“]?([^\"”\n]{3,80})", re.I)
_VALIDITY_RE = re.compile(r"valid(?:ity)?\s+(?:for|of|period\s+of)?\s*(\d{1,3})\s*(days?|months?|weeks?)"
                          r"|(\d{1,3})\s*(days?|months?)\s+validity", re.I)
_FMT_RE = re.compile(r"\b(pdf|ms\s*word|word|docx?|excel|xlsx?|powerpoint|pptx?)\b", re.I)
# context cue that a clause is really about PROPOSAL SUBMISSION (spec §4 precision)
_SUBMIT_CTX = ("submit", "submission", "submitted", "send to", "sent to", "email to", "emailed to",
               "proposal", "bid", "offer", "application", "tender", "no later than", "deadline",
               "closing", "addressed to", "uploaded", "portal")


def _submit_ctx(low: str) -> bool:
    return any(c in low for c in _SUBMIT_CTX)


def submission(analysis_id, aid, reqs, fields):
    out = []
    seen = set()

    def add(attr, raw, norm, r, mand):
        key = (attr, str(raw)[:60])
        if key in seen:
            return
        seen.add(key)
        loc, seq = (_prov(r) if r else ("", None))
        out.append(dict(id=_id("sub", aid, attr, raw), analysis_id=analysis_id, assignment_id=aid,
                        attribute=attr, value_raw=str(raw)[:200], value_norm=str(norm), mandatory=int(mand),
                        source_locator=loc, block_sequence=seq))
    for r in reqs:
        low = r.text.lower()
        if r.category != "submission" and not any(w in low for w in
                ("page", "deadline", "closing date", "email", "portal", "cover letter", "annex",
                 "validity", "code of conduct", "font", "technical proposal", "financial proposal",
                 "subject", "signed", "signature", "stamp", "password", "encrypt", "file", "format",
                 "attach", "naming", "timezone", "gmt", "eet")):
            continue
        submit_ctx = (r.category == "submission") or _submit_ctx(low)
        for q in value.parse_quantities(r.text):
            if q.kind == "INT" and "page" in low:
                add("page_limit", q.raw, q.value, r, r.mandatory)
            elif q.kind == "DATE" and ("deadline" in low or "no later" in low or "closing" in low):
                add("DEADLINE", q.raw, q.raw, r, True)
            elif q.kind == "TIME":
                add("DEADLINE_TIME", q.raw, q.raw, r, True)
        # relative/text deadline with no parseable DATE (spec §5): keep it, don't drop
        if ("deadline" in low or "no later than" in low or "closing" in low) and \
                not any(o["attribute"] == "DEADLINE" for o in out):
            add("DEADLINE", r.text[:120], "", r, True)
        # timezone near a submission deadline (spec §5)
        mtz = re.search(r"\b(EET|EEST|GMT|UTC|CET|EST|AST|CAT|EAT)\b", r.text)
        if mtz and submit_ctx:
            add("TIMEZONE", mtz.group(1), mtz.group(1), r, r.mandatory)
        # EMAIL / PORTAL only in a submission context (spec §4 precision — not background contacts)
        if submit_ctx:
            for em in _EMAIL_RE.findall(r.text):
                add("EMAIL", em, em.lower(), r, r.mandatory)
            if "portal" in low or "e-tender" in low or "platform" in low or "upload" in low:
                url = _URL_RE.search(r.text)
                add("PORTAL", (url.group(0) if url else "portal"), (url.group(0) if url else "portal"),
                    r, r.mandatory)
            elif "email" in low:
                add("SUBMISSION_CHANNEL", "email", "email", r, r.mandatory)
        msub = _SUBJECT_RE.search(r.text)
        if msub and submit_ctx:
            add("SUBJECT_LINE", msub.group(1).strip(), msub.group(1).strip(), r, r.mandatory)
        mval = _VALIDITY_RE.search(r.text)
        if mval and "valid" in low:
            val = mval.group(1) or mval.group(3); unit = (mval.group(2) or mval.group(4) or "").lower()
            add("VALIDITY_PERIOD", f"{val} {unit}", val, r, r.mandatory)
        if "technical" in low and "financial" in low and ("separate" in low or "two" in low or
                                                          "envelope" in low or "not include" in low or
                                                          "no price" in low):
            add("TECHNICAL_FINANCIAL_SEPARATION", "required", "required", r, True)
        if ("password" in low or "encrypt" in low) and submit_ctx:
            add("PASSWORD_REQUIREMENT", "required", "required", r, r.mandatory)
        if ("signed" in low or "signature" in low) and submit_ctx:
            add("SIGNATURE_REQUIREMENT", "required", "required", r, r.mandatory)
        if ("stamp" in low or "stamped" in low) and submit_ctx:
            add("STAMP_REQUIREMENT", "required", "required", r, r.mandatory)
        if ("naming" in low or "file name" in low or "filename" in low) and submit_ctx:
            add("FILE_NAME", r.text[:100], "", r, r.mandatory)
        mfmt = _FMT_RE.search(r.text)
        if mfmt and submit_ctx and ("format" in low or "file" in low or "submit" in low):
            add("FILE_FORMAT", mfmt.group(1).upper(), mfmt.group(1).lower(), r, r.mandatory)
        if ("attach" in low or "enclose" in low or "annex" in low) and submit_ctx:
            add("ATTACHMENT", r.text[:100], "", r, r.mandatory)
        if "code of conduct" in low:
            add("code_of_conduct", "sign required", "required", r, True)
        if "cover letter" in low:
            add("cover_letter", "required", "required", r, r.mandatory)
    return out


_SCORE = re.compile(r"([A-Za-z][A-Za-z /&-]{2,40}?)\s*[:\-–=]?\s*\(?(\d{1,3})\s*(?:%|points|pts|marks|"
                    r"point|/\s*100)", re.I)
_SCORE_WORDS = ("technical", "financial", "weight", "score", "scoring", "criteria", "criterion",
                "points", "marks", "methodology", "evaluation of", "award")


# points grid where criterion + weight are separated across sibling blocks (spec §12) —
# deterministic, never fabricated
_POINTS_INLINE = re.compile(r"([A-Za-z][A-Za-z /&,'()-]{2,60}?)\s*[:\-–(]\s*(\d{1,3})\s*"
                            r"(?:points?|marks|pts)\b", re.I)
_POINTS_BARE = re.compile(r"^\s*(\d{1,3})\s*(?:points?|marks|pts)\b", re.I)


def _crit_type(low: str, unit_is_pct: bool) -> tuple[str, int]:
    """(criterion_type, is_threshold). Minimum-technical / pass-fail -> threshold (excluded from
    weight totals so a 65/35 split + a points grid is not spuriously a SCORING_CONFLICT)."""
    if ("minimum" in low and "technical" in low) or any(w in low for w in
            ("threshold", "pass mark", "pass/fail", "pass or fail", "qualify", "reject")):
        return "threshold_technical", 1
    if "technical" in low and "financial" in low:
        return "weight_group", 0
    return ("percent" if unit_is_pct else "points"), 0


def scoring(store, analysis_id, aid, reqs, fields):
    out = []
    texts = [(r.text, _prov(r)) for r in reqs] + \
            [(f.value_text, ("", f.block_start)) for f in fields if f.field_key == "scoring_criteria"]
    for text, (loc, seq) in texts:
        low = (text or "").lower()
        if not any(w in low for w in _SCORE_WORDS) or "%" not in text and not re.search(
                r"\d\s*(?:points|marks|pts)", low):
            continue
        for m in _SCORE.finditer(text):
            crit = m.group(1).strip(" -:–=(")
            if len(crit) < 3 or crit.lower() in ("no", "the", "up to", "than", "score of"):
                continue
            unit_pct = "%" in (m.group(0) or "")
            ctype, is_thr = _crit_type(low, unit_pct)
            out.append(dict(id=_id("sc", aid, crit, m.group(2)), analysis_id=analysis_id,
                            assignment_id=aid, criterion=crit[:60], weight=float(m.group(2)),
                            parent="", is_threshold=int(is_thr or "minimum" in low or "threshold" in low
                                                        or "pass" in low), source_locator=loc,
                            block_sequence=seq,
                            points=(None if unit_pct else float(m.group(2))),
                            criterion_type=ctype, parent_criterion_id="", confidence="high"))
    # points-grid RECOVERY across sibling blocks: a doc with a real scoring signal, where the
    # criterion label and its 'NN points' weight sit in separate blocks (spec §12, §13 IRQ74 shape)
    for doc in store.documents(aid, ("TOR", "TOR_ANNEX")):
        blocks = [b for b in store.blocks(doc["document_id"]) if (b.get("plain_text") or "").strip()]
        doc_low = " ".join((b.get("plain_text") or "").lower() for b in blocks)
        has_signal = bool(re.search(r"\d\s*(?:points|marks|pts)\b", doc_low)) or (
            bool(re.search(r"\d{1,3}\s*%", doc_low)) and any(w in doc_low for w in
                 ("technical proposal", "financial proposal", "evaluation criteria",
                  "scoring", "weighting")))
        if not has_signal:
            continue
        prev_label = None
        for b in blocks:
            t = (b.get("plain_text") or "").strip()
            low = t.lower()
            for m in _POINTS_INLINE.finditer(t):
                crit = m.group(1).strip(" -:–=(")
                if len(crit) < 3:
                    continue
                ctype, is_thr = _crit_type(low, False)
                out.append(dict(id=_id("sc", aid, crit, m.group(2)), analysis_id=analysis_id,
                                assignment_id=aid, criterion=crit[:60], weight=float(m.group(2)),
                                parent="", is_threshold=is_thr,
                                source_locator="", block_sequence=b["sequence"],
                                points=float(m.group(2)), criterion_type=ctype,
                                parent_criterion_id="", confidence="high"))
            bare = _POINTS_BARE.match(t)
            if bare and len(t) <= 18 and prev_label and 3 <= len(prev_label[0]) <= 60:
                ctype, is_thr = _crit_type(prev_label[1], False)
                out.append(dict(id=_id("sc", aid, prev_label[0][:40], bare.group(1)),
                                analysis_id=analysis_id, assignment_id=aid,
                                criterion=prev_label[0][:60], weight=float(bare.group(1)),
                                parent="", is_threshold=is_thr, source_locator="",
                                block_sequence=b["sequence"], points=float(bare.group(1)),
                                criterion_type=ctype, parent_criterion_id="", confidence="medium"))
            if re.search(r"[A-Za-z]", t) and not re.search(r"\d\s*(?:points|marks|pts|%)", low) \
                    and len(t.split()) <= 10:
                prev_label = (t, low)
    # scoring tables: a criterion cell + an adjacent weight cell in the same row
    for doc in store.documents(aid, ("TOR", "TOR_ANNEX")):
        for t in store.tables(doc["document_id"]):
            cells = store.cells(t["table_id"])
            by_row = {}
            for c in cells:
                by_row.setdefault(c["row_index"], []).append(c)
            header = " ".join((c["text"] or "").lower() for c in cells if c["row_index"] == 0)
            if not any(w in header for w in ("weight", "score", "points", "marks", "criteria", "%")):
                continue
            for ri, row in by_row.items():
                if ri == 0:
                    continue
                crit_txt = next((c["text"] for c in sorted(row, key=lambda x: x["col_index"])
                                 if c["text"] and not re.fullmatch(r"[\d.%\s]+", c["text"])), "")
                wcell = next((c for c in row if c["text"] and re.search(r"\d", c["text"])
                              and re.fullmatch(r"[\d.%\s/]+", c["text"].strip())), None)
                if crit_txt and wcell:
                    mm = re.search(r"(\d{1,3})", wcell["text"])
                    if mm:
                        loc = f"{t['table_id']}:r{wcell['row_index']}c{wcell['col_index']}"
                        out.append(dict(id=_id("sc", aid, crit_txt[:40], mm.group(1)),
                                        analysis_id=analysis_id, assignment_id=aid,
                                        criterion=crit_txt[:60], weight=float(mm.group(1)), parent="",
                                        is_threshold=0, source_locator=loc, block_sequence=None))
    uniq, seen = [], set()
    for r in out:
        k = (r["criterion"].lower(), r["weight"])
        if k not in seen:
            seen.add(k); uniq.append(r)
    return uniq


_SCORE_SIGNAL = re.compile(r"\d\s*(?:points|marks|pts)\b|\b(?:technical|financial)\b[^.]{0,40}?\d{1,3}\s*%|"
                           r"\bweight(?:ing|ed)?\b[^.]{0,30}?\d{1,3}\s*%|\bevaluation\s+criteria\b", re.I)


def scoring_status(store, aid, reqs, fields, scoring_rows) -> dict:
    """Spec §24-26: machine-readable scoring state so downstream never treats 'not extracted' as
    'no scoring'. Also a total-sanity check (§25): weights that don't reconcile -> SCORING_CONFLICT.

    KNOWN   : criteria extracted AND (weights absent or reconcile to ~100 / tech+fin).
    PARTIAL : criteria extracted but weights don't reconcile, OR a scoring signal exists with fewer
              rows than signalled.
    UNKNOWN : a scoring signal exists in the TOR but ZERO criteria were extracted (a missed grid),
              OR no signal at all (TOR may carry no scoring) — either way, not zero.
    """
    signal = False
    texts = [r.text for r in reqs] + [f.value_text for f in fields if f.field_key == "scoring_criteria"]
    for t in texts:
        if _SCORE_SIGNAL.search(t or ""):
            signal = True
            break
    if not signal:
        for doc in store.documents(aid, ("TOR", "TOR_ANNEX")):
            for b in store.blocks(doc["document_id"]):
                if _SCORE_SIGNAL.search(b.get("plain_text") or ""):
                    signal = True
                    break
            if signal:
                break
    weights = [r["weight"] for r in scoring_rows if r.get("weight")]
    total = round(sum(weights), 1) if weights else 0.0
    reconciles = (not weights) or abs(total - 100.0) <= 1.0 or abs(total - 1.0) <= 0.01
    if scoring_rows:
        if weights and not reconciles:
            status = "SCORING_CONFLICT" if total > 100.5 else "SCORING_PARTIAL"
        elif signal and len(scoring_rows) < 2 and total < 50:
            status = "SCORING_PARTIAL"
        else:
            status = "SCORING_KNOWN"
    else:
        status = "SCORING_UNKNOWN"           # includes 'signal but 0 rows' (a missed grid)
    return {"scoring_status": status, "scoring_signal_present": bool(signal),
            "scoring_criteria_count": len(scoring_rows), "scoring_weight_total": total}


_ABBR = re.compile(r"\b([A-Z][A-Za-z&]*(?:\s+[A-Za-z&]+){1,5})\s*\((([A-Z]{2,6})s?)\)")
_ABBR2 = re.compile(r"\b([A-Z]{2,6})\s*[=:]\s*([A-Z][A-Za-z ]{4,60})")


def terms(store, analysis_id, aid):
    out, seen = [], set()
    for doc in store.documents(aid, ("TOR", "TOR_ANNEX")):
        for b in store.blocks(doc["document_id"]):
            t = b["plain_text"] or ""
            for m in _ABBR.finditer(t):
                ab = m.group(3)
                if ab in seen or len(m.group(1)) > 70:
                    continue
                seen.add(ab)
                out.append(dict(id=_id("term", aid, ab), analysis_id=analysis_id, assignment_id=aid,
                                term=ab, definition=m.group(1).strip()[:120], source_locator="",
                                block_sequence=b["sequence"]))
            for m in _ABBR2.finditer(t):
                ab = m.group(1)
                if ab in seen:
                    continue
                seen.add(ab)
                out.append(dict(id=_id("term", aid, ab), analysis_id=analysis_id, assignment_id=aid,
                                term=ab, definition=m.group(2).strip()[:120], source_locator="",
                                block_sequence=b["sequence"]))
    return out


def derive_all(store, analysis_id, aid, fields, reqs) -> dict:
    return {
        "pe_tor_deliverables": deliverables(analysis_id, aid, reqs),
        "pe_tor_timeline": timeline(analysis_id, aid, reqs),
        "pe_tor_methods": methods(analysis_id, aid, reqs),
        "pe_tor_sampling": sampling(analysis_id, aid, reqs),
        "pe_tor_team": team(analysis_id, aid, reqs),
        "pe_tor_eligibility": eligibility(analysis_id, aid, reqs),
        "pe_tor_language": language(analysis_id, aid, reqs),
        "pe_tor_eval_questions": eval_questions(analysis_id, aid, reqs),
        "pe_tor_submission": submission(analysis_id, aid, reqs, fields),
        "pe_tor_scoring": scoring(store, analysis_id, aid, reqs, fields),
        "pe_tor_terms": terms(store, analysis_id, aid),
    }
