"""PE2 deterministic TOR extraction (fields + requirements) with PE1 provenance."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Optional

from . import fields as F
from .models import TORField, TORRequirement


def _rid(*parts) -> str:
    return "req_" + hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


def _match_field(heading: str) -> Optional[str]:
    """First field whose heading alias is a substring of `heading` (priority order)."""
    h = (heading or "").lower()
    if not h.strip():
        return None
    for fkey in F.HEADING_ALIASES:                 # dict preserves priority order
        for alias in F.HEADING_ALIASES[fkey]:
            if alias in h:
                return fkey
    return None


def _block_page(block: dict) -> Optional[int]:
    try:
        return json.loads(block.get("meta_json") or "{}").get("page")
    except Exception:
        return None


_SOFT_SHOULD = re.compile(r"\bshould\s+(?:consider|explore|ideally|preferably|aim|try|seek to)", re.I)
# a modal directly negated -> a PROHIBITION, not a positive obligation (spec §8)
_NEG_MODAL = re.compile(r"\b(?:shall|must|will|should|may|is|are|to be|can)\s+(?:not|never)\b", re.I)
# pure exclusions that are NOT positive requirements at all ("CVs are not required")
_EXCLUSION = re.compile(r"\b(?:not|no)\s+(?:required|needed|necessary|expected|mandatory|permitted|"
                        r"allowed|accepted)\b|\bnot\s+be\s+(?:included|required|accepted|permitted)\b|"
                        r"\bno\s+\w+(?:\s+\w+)?\s+(?:is|are|will\s+be)\s+"
                        r"(?:required|needed|expected|necessary|permitted)\b", re.I)


def is_exclusion(text: str) -> bool:
    """True for a pure negative statement that should not become a positive requirement (spec §8)."""
    return bool(_EXCLUSION.search(text or ""))


def _modality(text: str) -> tuple[bool, str]:
    """Default-MANDATORY: TOR requirements are obligations unless explicitly softened or NEGATED.
    A directly-negated modal ('shall not', 'must not', 'will not') is a PROHIBITION (in force, but
    NOT a positive obligation to do X). Negated softeners ('not mandatory','not required') are
    checked BEFORE the bare mandatory cues so they are not swallowed by substring matching (§8)."""
    t = text.lower()
    if _EXCLUSION.search(t) or "not mandatory" in t:
        return False, "OPTIONAL"
    if _NEG_MODAL.search(t):
        return True, "PROHIBITION"
    if any(c in t for c in F.EXPLICIT_MANDATORY):
        return True, "MANDATORY"
    if any(c in t for c in F.STRONG_OPTIONAL_CUES) or _SOFT_SHOULD.search(t):
        return False, "OPTIONAL"
    return True, "MANDATORY"


_SENT = re.compile(r"(?<=[.;:])\s+|\n+")
_PAGE_LIMIT = re.compile(r"(?:max(?:imum)?(?:\s+of)?|not\s+exceed(?:ing)?|no\s+more\s+than|up\s+to)"
                         r"\D{0,20}?(\d{1,3})\s*pages?|(\d{1,3})\s*pages?\s*(?:max(?:imum)?|limit)",
                         re.IGNORECASE)
_DURATION = re.compile(r"(\d{1,3})\s*(working\s+days|days|weeks|months)", re.IGNORECASE)


def extract_fields(store, aid: str) -> list[TORField]:
    meta = store.assignment(aid) or {}
    docs = store.documents(aid, ("TOR", "TOR_ANNEX"))
    out: list[TORField] = []
    found_keys: set[str] = set()

    def add(fkey, value, doc_id, sec_id, path, bstart, bend, page, method, conf, extras=None):
        out.append(TORField(assignment_id=aid, tor_document_id=doc_id, field_key=fkey,
                            value_text=(value or "")[:6000], source_section_id=sec_id,
                            source_section_path=path or "", block_start=bstart, block_end=bend,
                            page=page, method=method, confidence=conf, extras=extras or {}))
        found_keys.add(fkey)

    # --- metadata-backed fields ---
    if meta.get("client"):
        add("client", meta["client"], docs[0]["document_id"] if docs else "", None, "", None, None, None,
            "METADATA", "HIGH")
    if meta.get("country"):
        add("country", meta["country"], docs[0]["document_id"] if docs else "", None, "", None, None, None,
            "METADATA", "HIGH")
    if meta.get("project_title"):
        add("assignment", meta["project_title"], docs[0]["document_id"] if docs else "", None, "",
            None, None, None, "METADATA", "MEDIUM")

    # --- structural: TOR sections -> fields ---
    all_blocks_text = []
    for doc in docs:
        did = doc["document_id"]
        secs = store.sections(did)
        blocks = store.blocks(did)
        seq_to_block = {b["sequence"]: b for b in blocks}
        for sec in secs:
            fkey = _match_field(sec["heading_text"] or "")
            if not fkey or fkey in found_keys:
                continue
            start, end = sec["start_block_sequence"], sec["end_block_sequence"]
            text, _ = store.section_text(did, start, end)
            if len(text) < 3:
                continue
            page = _block_page(seq_to_block.get(start, {}))
            add(fkey, text, did, sec["section_id"], sec["section_path"], start, end, page,
                "SECTION", "HIGH")
        all_blocks_text.append((did, blocks))

    # --- pattern fields over full TOR text ---
    for did, blocks in all_blocks_text:
        joined = "\n".join(b["plain_text"] for b in blocks if b["plain_text"])
        if "page_limits" not in found_keys:
            m = _PAGE_LIMIT.search(joined)
            if m:
                n = m.group(1) or m.group(2)
                add("page_limits", f"{n} pages (detected)", did, None, "", None, None, None,
                    "PATTERN", "MEDIUM", {"pages": int(n)})
        if "timeline" not in found_keys:
            m = _DURATION.search(joined)
            if m:
                add("timeline", f"{m.group(1)} {m.group(2)} (detected)", did, None, "", None, None, None,
                    "PATTERN", "LOW", {"amount": int(m.group(1)), "unit": m.group(2).lower()})

    # --- keyword-scan fallback for still-missing fields (esp. PDF TORs) ---
    for fkey, cues in F.KEYWORD_CUES.items():
        if fkey in found_keys:
            continue
        for did, blocks in all_blocks_text:
            hit = None
            for b in blocks:
                t = (b["plain_text"] or "").lower()
                if t and any(c in t for c in cues):
                    hit = b
                    break
            if hit:
                add(fkey, hit["plain_text"], did, None, hit.get("section_path", ""),
                    hit["sequence"], hit["sequence"], _block_page(hit), "KEYWORD_SCAN", "LOW")
                break
    return out


_ELIG_CUES = ("legally registered", "registration certificate", "certificate of incorporation",
              "registered company", "years in business", "annual turnover", "audited accounts",
              "financial capacity", "conflict of interest", "reference letter", "company profile",
              "legal entity", "valid license", "valid licence", "tax clearance", "vat registration")
# FIRM subject + eligibility predicate (spec §10-13): 'the firm shall have 10 years experience' is
# ORGANIZATION eligibility, not an individual TEAM qualification. Both must co-occur to route.
_FIRM_SUBJ = ("the firm", "the company", "the organisation", "the organization", "the bidder",
              "the contractor", "the tenderer", "the consultancy", "the institution", "the supplier",
              "the applicant", "bidding firm", "consulting firm", "the consultant firm",
              "the offeror", "the vendor", "the agency shall", "the ngo shall")
_ELIG_PRED = ("years of experience", "years of relevant experience", "years in business", "registered",
              "registration", "turnover", "audited", "financial capacity", "prior contract",
              "similar contract", "similar assignment", "track record", "incorporation",
              "legal entity", "insurance", "conflict of interest", "organizational experience",
              "organisational experience", "company experience", "references", "prior experience")


def _classify(text: str, heading: str) -> str:
    """Category from the nearest requirement-mapped heading, else content cues. Distinctive FIRM
    eligibility is routed before generic cues (spec §10-13, §25); genuinely contentless fragments
    get an explicit NEEDS_REVIEW marker rather than a confidently-wrong bucket (spec §11, §28)."""
    hk = _match_field(heading or "")
    if hk in F.REQUIREMENT_CATEGORY:
        return F.REQUIREMENT_CATEGORY[hk]
    low = (text or "").lower()
    if low.rstrip().endswith("?"):
        return "evaluation_questions"
    if any(c in low for c in _ELIG_CUES):
        return "eligibility"
    # firm subject + an eligibility predicate -> firm eligibility (not individual TEAM)
    if any(s in low for s in _FIRM_SUBJ) and any(p in low for p in _ELIG_PRED):
        return "eligibility"
    for cat, cues in F.CATEGORY_CONTENT_CUES:
        if any(c in low for c in cues):
            return cat
    if len(low.split()) < 5:
        return "needs_review"
    return "general"


def _looks_like_heading(txt: str) -> bool:
    t = txt.strip()
    if not t:
        return True
    words = t.split()
    if t.rstrip().endswith(("?", ".")) or _has_obligation(t):
        return False
    if t.endswith(":") and len(words) <= 8:
        return True
    if len(words) <= 6:
        return True
    # a short noun-phrase that IS a known field title (e.g. "Deliverables and timeline")
    if len(words) <= 8 and _match_field(t) is not None and not any(ch.isdigit() for ch in t):
        return True
    return False


_BULLET_CHARS = '-*•‣◦∙·–—▪●\uf0b7 \t'


def _debullet(txt: str) -> tuple[str, bool]:
    """Strip a leading bullet/number marker; report whether one was present.
    PDF TORs render bullets as PARAGRAPHs prefixed with a PUA glyph (e.g. \\uf0b7)."""
    t = txt.lstrip()
    stripped = t.lstrip(_BULLET_CHARS).lstrip()
    # also handle 'N.' / 'N)' / 'a)' enumerators
    m = re.match(r"^(?:\(?[0-9a-zA-Z]{1,3}[.)])\s+(.*)$", stripped)
    if m:
        stripped = m.group(1)
    was = len(stripped) < len(t) and len(stripped) >= 5
    return (stripped if was else t), was


def _has_obligation(txt: str) -> bool:
    clean, _ = _debullet(txt)
    low = clean.lower()
    if any(c in low for c in F.MANDATORY_CUES + F.OPTIONAL_CUES):
        return True
    first = low[:24]
    return any(first.startswith(v) for v in F.OBLIGATION_VERBS)


# split coordinated obligations sharing one source. Bare ' and '/' as well as ' are now split
# candidates (spec §22) but ONLY materialize when >=2 resulting clauses EACH independently look
# like an obligation — so noun coordination ('monitoring and evaluation', 'Arabic and English')
# is never split, while 'submit X and provide Y' is.
_CONJ = re.compile(r";\s+|,?\s+and\s+then\s+|,?\s+and\s+(?=[a-z])|,?\s+as\s+well\s+as\s+(?=[a-z])")


def _atomize(text: str) -> list[str]:
    """Conservatively split coordinated obligations sharing one source.
    Only splits when >=2 resulting clauses each look like an obligation."""
    text = text.strip()
    parts = [p.strip(" .;,") for p in _CONJ.split(text) if p.strip()]
    parts = [re.sub(r"^(?:and|then|also|or)\s+", "", p, flags=re.I) for p in parts]
    obl = [p for p in parts if len(p) >= 15 and _has_obligation(p)]
    if len(obl) >= 2:
        return obl
    return [text]


_SUBMISSION_PAT = re.compile(
    r"(\d{1,3}\s*pages?)|(?:not\s+exceed|no\s+more\s+than|max(?:imum)?)\b|"
    r"\b(?:deadline|closing date|no later than|submitted?\s+by)\b|"
    r"\b\d{1,2}:\d{2}\b", re.IGNORECASE)


_WILL_VERB = re.compile(r"\b(?:will|shall|to|is expected to|is required to)\s+(?:"
                        + "|".join(F.OBLIGATION_VERBS) + r")\b", re.I)


def _is_requirement_sentence(s: str) -> bool:
    if len(s) < 20:
        return False
    if _has_obligation(s) or bool(_SUBMISSION_PAT.search(s)):
        return True
    if _WILL_VERB.search(s):            # "the Consultant will submit/obtain/provide ..."
        return True
    return any(c in s.lower() for c in F.PRESCRIPTIVE_CUES)


# project-activity verbs that (as bare bullets) usually describe what the PROJECT does,
# not what the consultant must do; only treated as requirements with consultant context.
_PROJECT_VERBS = ("offer", "reinforce", "strengthen", "procure", "mobilize", "mobilise",
                  "improve", "provide", "support", "conduct", "implement", "train", "build",
                  "establish", "promote", "enhance", "reduce", "increase", "expand",
                  "coordinate", "maintain")
# consultant / evaluation context that redeems an imperative as a real requirement
_REQ_CONTEXT = ("consult", "evaluat", "assess", "proposal", "report", "deliverable", "inception",
                "sampl", "interview", "kii", "fgd", "survey", "questionnaire", "data collection",
                "analysis", "team", "cv", "submit", "ethic", "consent", "workplan", "work plan",
                "methodolog", "tender", "bidder", "annex", "budget", "review", "recommendation",
                "findings", "respondent", "enumerat", "tool", "dataset", "data set", "tables",
                "chart", "narrative", "presentation", "transcri", "training of enumer")


_LOC_MARK = re.compile(r"\b(localit(?:y|ies)|governorate|district)\b|\bState\s*[–\-:]|"
                       r"\bRegion\s*[:–\-]", re.I)
_SECTOR_LABEL = re.compile(r"^(nutrition|protection|health|wash|mpca|shelter|education|"
                           r"livelihoods?|food security|thematic)\b\s*[:\-]", re.I)


def _is_project_activity(clean: str) -> bool:
    """True for project/context noise formatted as a bullet — imperative activity, a
    location enumeration, or a sector-label line — with no consultant/eval context and
    no obligation modal. These describe the intervention/context, not the assignment."""
    low = clean.lower()
    if any(c in low for c in F.MANDATORY_CUES + F.OPTIONAL_CUES):
        return False
    if any(c in low for c in _REQ_CONTEXT):
        return False
    first = low.split()[0] if low.split() else ""
    if first in _PROJECT_VERBS:
        return True
    if _SECTOR_LABEL.match(clean):
        return True
    # location enumeration: has a place-marker and is mostly proper nouns
    if _LOC_MARK.search(clean):
        caps = sum(1 for w in clean.split() if w[:1].isupper())
        if caps >= max(2, len(clean.split()) // 2):
            return True
    return False


def _is_table_requirement(ct: str) -> bool:
    if len(ct) < 6:
        return False
    if ct.rstrip().endswith("?"):            # evaluation-question cell
        return True
    low = ct.lower()
    if _has_obligation(ct):
        return True
    # team / deliverable / scoring table rows
    return any(c in low for c in ("years of experience", "degree", "qualification", "proven",
                                  "deliverable", "inception", "report", "weight", "%", "points"))


def extract_requirements(store, aid: str, tor_fields: list[TORField] | None = None) -> list[TORRequirement]:
    """Section-INDEPENDENT, table-AWARE, atomic requirement extraction.

    Walks every TOR/TOR_ANNEX block in document order (tracking the nearest heading
    for section-path provenance and category), harvesting: list items, obligation/
    modal sentences in paragraphs, and requirement-like table cells. Works even when
    PE1 built no section tree (PDF / head-less DOCX) — the prior section-gated
    version collapsed to near-zero on 7/14 real TORs.
    """
    reqs: list[TORRequirement] = []
    seen: set[str] = set()

    def emit(text: str, did: str, heading: str, method: str, seq, page, locator: str, group: str):
        text = text.strip()
        if len(text) < 8:
            return
        key = re.sub(r"\s+", " ", text.lower())[:120]
        if key in seen:
            return
        seen.add(key)
        mand, modality = _modality(text)
        category = _classify(text, heading)
        reqs.append(TORRequirement(
            req_id=_rid(aid, did, seq if seq is not None else locator, key[:40]),
            assignment_id=aid, tor_document_id=did, text=text[:1000], category=category,
            mandatory=mand, modality=modality, source_section_path=heading or "",
            block_sequence=(seq if isinstance(seq, int) else None), page=page,
            method=method, confidence=("HIGH" if method in ("LIST", "TABLE_CELL") else "MEDIUM"),
            source_locator=locator, atomic_group=group))

    for doc in store.documents(aid, ("TOR", "TOR_ANNEX")):
        did = doc["document_id"]
        cur_heading = ""
        for b in store.blocks(did):
            bt = b["block_type"]; txt = (b["plain_text"] or "").strip()
            if bt == "HEADING":
                cur_heading = txt
                continue
            if not txt:
                continue
            page = _block_page(b); seq = b["sequence"]
            clean, bulleted = _debullet(txt)
            if bt == "LIST_ITEM" or bulleted:
                if _looks_like_heading(clean):      # sub-heading rendered as a bullet
                    cur_heading = clean
                    continue
                # project-context sections: keep only items with an explicit actor obligation
                hl = (cur_heading or "").lower()
                if any(nh in hl for nh in F.NON_REQ_HEADINGS) and \
                        not any(c in clean.lower() for c in F.ACTOR_OBLIGATION_CUES):
                    continue
                # bare project-activity bullets (no consultant/eval context) are not requirements
                if _is_project_activity(clean):
                    continue
                units = _atomize(clean)
                grp = f"g{seq}" if len(units) > 1 else ""
                for u in units:
                    emit(u, did, cur_heading, "LIST", seq, page, "", grp)
            elif bt in ("PARAGRAPH", "OTHER"):
                for s in _SENT.split(txt):
                    s = s.strip()
                    if _is_requirement_sentence(s):
                        units = _atomize(s)
                        grp = f"g{seq}" if len(units) > 1 else ""
                        for u in units:
                            emit(u, did, cur_heading, "MODAL", seq, page, "", grp)
        # table cells (deliverable/team/scoring/eval-question tables)
        for t in store.tables(did):
            tid = t["table_id"]
            for c in store.cells(tid):
                ct = (c["text"] or "").strip()
                if _is_table_requirement(ct):
                    loc = f"{tid}:r{c['row_index']}c{c['col_index']}"
                    for u in _atomize(ct):
                        emit(u, did, (t.get("caption") or "table"), "TABLE_CELL", None, None, loc, "")
    return reqs
