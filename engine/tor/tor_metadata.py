"""Deterministic TOR metadata from the document itself (v0.6.9).

Uploaded TOR files carry no metadata, so assignment title, client and country
were always empty for file-based runs. This detector reads the document text and
returns only what the document STATES:

* title   — an explicit "Assignment title:" label, else the first-page heading that
            names the assignment ("Final Evaluation for “… Project”"), with a
            leading "Terms of Reference for" stripped;
* client  — the organisation the text names as commissioning / inviting / seeking
            the work ("ZOA is seeking …", "commissioned by ZOA", "Client: ZOA");
            a donor ("funded by …") is never taken as the client;
* country — the country of the assignment location (labels such as "Location:",
            the title, "in …, Sudan"), weighted above incidental mentions;
* subnational_location — states / localities / towns named with the assignment
            location ("Nyala, South Darfur", "South Darfur", "… locality").

Nothing is guessed: a value that the text does not support stays empty.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, Optional

FIRST_PAGE_BLOCKS = 45

# --- countries (canonical names follow the Master Tracker: "Turkey", "Palestine")
_COUNTRIES = [
    ("South Sudan", r"south\s+sudan"), ("Sudan", r"(?<!south\s)sudan"),
    ("Syria", r"syria|syrian\s+arab\s+republic"), ("Iraq", r"iraq|kurdistan\s+region\s+of\s+iraq"),
    ("Jordan", r"jordan"), ("Lebanon", r"lebanon"), ("Palestine", r"palestine|gaza|west\s+bank|opt\b"),
    ("Turkey", r"turkey|t[üu]rkiye"), ("Yemen", r"yemen"), ("Libya", r"libya"),
    ("Afghanistan", r"afghanistan"), ("Egypt", r"egypt"), ("Somalia", r"somalia"),
    ("Ethiopia", r"ethiopia"), ("Kenya", r"kenya"), ("Uganda", r"uganda"), ("Chad", r"chad"),
    ("Nigeria", r"nigeria"), ("Niger", r"niger(?!ia)"), ("Mali", r"mali"),
    ("Burkina Faso", r"burkina\s+faso"), ("Cameroon", r"cameroon"),
    ("Central African Republic", r"central\s+african\s+republic"),
    ("Democratic Republic of the Congo", r"democratic\s+republic\s+of\s+(?:the\s+)?congo|\bdrc\b(?=.*congo)"),
    ("Pakistan", r"pakistan"), ("Bangladesh", r"bangladesh"), ("Myanmar", r"myanmar"),
    ("Iran", r"iran"), ("Tunisia", r"tunisia"), ("Morocco", r"morocco"), ("Algeria", r"algeria"),
    ("Mauritania", r"mauritania"), ("Eritrea", r"eritrea"), ("Djibouti", r"djibouti"),
    ("Ukraine", r"ukraine"), ("Armenia", r"armenia"), ("Georgia", r"georgia"),
    ("Mozambique", r"mozambique"), ("Zimbabwe", r"zimbabwe"), ("Malawi", r"malawi"),
    ("Burundi", r"burundi"), ("Rwanda", r"rwanda"), ("Tanzania", r"tanzania"),
    ("Philippines", r"philippines"), ("Indonesia", r"indonesia"), ("Haiti", r"haiti"),
    ("Colombia", r"colombia"), ("Venezuela", r"venezuela"),
]
_COUNTRY_RE = [(name, re.compile(rf"\b(?:{pat})\b", re.I)) for name, pat in _COUNTRIES]

_LOCATION_LABEL = re.compile(
    r"^\s*(?:country|location|locations|duty\s+station|place\s+of\s+(?:the\s+)?assignment|"
    r"project\s+location|assignment\s+location|geographic(?:al)?\s+(?:area|scope|coverage)|"
    r"area\s+of\s+(?:implementation|intervention)|target\s+areas?)\s*[:\-–]\s*(.+)$", re.I)
_TITLE_LABEL = re.compile(
    r"^\s*(?:(?:assignment|consultancy|evaluation|study|position)\s+title|"
    r"title\s+of\s+(?:the\s+)?(?:assignment|consultancy|evaluation|study)|title)\s*[:\-–]\s*"
    r"(.{6,220})$", re.I)
_PROJECT_LABEL = re.compile(r"^\s*project\s+(?:title|name)\s*[:\-–]\s*(.{4,200})$", re.I)
_ASSIGN_WORDS = re.compile(
    r"\b(?:evaluation|assessment|baseline|end[- ]?line|mid[- ]?line|mid[- ]term|study|survey|"
    r"review|research|analysis|monitoring|mapping|tpm)\b", re.I)
_GENERIC_HEADING = re.compile(
    r"^(?:terms\s+of\s+reference|tor|tors|request\s+for\s+(?:proposals?|quotations?)|rfp|rfq|"
    r"annex\b.*|table\s+of\s+contents|contents|background|introduction|call\s+for\s+.*|"
    r"consultancy|invitation\s+to\s+tender|scope\s+of\s+work)\W*$", re.I)
_TOR_PREFIX = re.compile(
    r"^\s*(?:terms\s+of\s+reference|tor|tors|request\s+for\s+proposals?|rfp)\s*"
    r"(?:\((?:tor|tors|rfp)\))?\s*[:\-–]?\s*(?:for|of)?\s*(?:an?\s+|the\s+)?", re.I)

# --- client / commissioning organisation
_ACRONYM = r"[A-Z][A-Z&]{1,7}"
_NAME = r"[A-Z][a-z]+(?:\s+(?:the|of|for|and|[A-Z][a-z]+)){0,5}"
_ORG = rf"(?P<org>{_ACRONYM}|{_NAME})"
_NOT_ORG = {
    "TOR", "TORS", "KII", "KIIS", "FGD", "FGDS", "FCS", "RCSI", "HHS", "PMF", "CAC", "CACS",
    "NGO", "NGOS", "INGO", "PSEA", "GBV", "MEAL", "HH", "FHH", "MHH", "OECD", "DAC", "USD",
    "SDG", "CV", "CVS", "ID", "VAT", "IDP", "IDPS", "FSL", "CBI", "CVA", "MPCA", "WASH",
    "NFI", "AAP", "PDF", "AM", "PM", "SPSS", "GPS", "ODK", "IT", "HR", "QA", "UN", "EU",
    "The", "This", "These", "That", "Consultant", "Consultants", "Evaluation", "Evaluator",
    "Project", "Programme", "Program", "Proposal", "Applicants", "Bidders", "Team", "All",
    "Terms", "Reference", "Annex", "Final", "Baseline", "Endline", "Support",
}
_CLIENT_LABEL = re.compile(
    r"^\s*(?:client|commissioning\s+(?:organi[sz]ation|agency|party)|contracting\s+"
    r"(?:authority|organi[sz]ation|agency)|requesting\s+organi[sz]ation|organi[sz]ation|"
    r"employer|issued\s+by)\s*[:\-–]\s*(.{2,80})$", re.I)
_CLIENT_PATTERNS = [
    (rf"\b{_ORG}\s+(?:is|are|was)\s+(?:seeking|looking\s+for|inviting|commissioning|planning|"
     r"intending|requesting|hiring|recruiting|pleased)", 3),
    (rf"\b{_ORG}\s+(?:invites|seeks|intends|wishes|would\s+like|requires|plans|hereby|"
     r"is\s+therefore)\b", 3),
    (rf"\b(?:commissioned|issued|initiated|managed|launched)\s+by\s+{_ORG}", 3),
    (rf"\bon\s+behalf\s+of\s+{_ORG}", 3),
    (rf"\b(?:submitted|sent|addressed|emailed)\s+to\s+{_ORG}\b", 2),
    (rf"\b{_ORG}\s+(?:is|was)\s+an?\s+(?:international|non-?governmental|humanitarian|relief|"
     r"development|faith-based|christian|dutch|ngo|organi[sz]ation|agency)", 3),
    (rf"\b(?:implemented|delivered|run)\s+by\s+{_ORG}", 1),
]
_DONOR = re.compile(rf"\b(?:funded|financed|supported|sponsored)\s+(?:by|through)\s+{_ORG}")

# --- subnational places named with the assignment location
_DIRECTIONAL = re.compile(r"\b((?:North|South|East|West|Central|Upper|Lower)\s+[A-Z][a-z]{3,})\b")
_ADMIN_UNIT = re.compile(
    r"\b([A-Z][a-z]{3,}(?:\s+[A-Z][a-z]{3,})?)\s+(?:state|locality|localities|governorate|"
    r"province|district|region|town|city|camp)\b")
_PLACE_STOP = {"The", "This", "Republic", "State", "Country", "Project", "Office", "Final",
               "Support", "Evaluation", "Terms", "Reference", "Programme", "Program",
               "Central African", "North East", "South East", "South West", "North West"}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace(" ", " ")).strip(" \t:-–—")


def _lines(blocks: Iterable[dict]) -> list[tuple[str, str]]:
    """Text lines in order; a short table label cell followed by its value cell
    ("Location" | "Nyala, South Darfur, Sudan") also yields "Location: …"."""
    blocks = list(blocks)
    out = []
    for i, b in enumerate(blocks):
        t = _clean(b.get("plain_text", ""))
        if not t:
            continue
        out.append((t, b.get("block_type", "")))
        nxt = blocks[i + 1] if i + 1 < len(blocks) else None
        if b.get("block_type") == "TABLE_CELL" and nxt and nxt.get("block_type") == "TABLE_CELL" \
                and len(t.split()) <= 5 and ":" not in t:
            v = _clean(nxt.get("plain_text", ""))
            if v:
                out.append((f"{t}: {v}", "TABLE_PAIR"))
    return out


def _is_sentence(t: str) -> bool:
    return len(t.split()) > 28 or bool(re.search(r"\b(?:will|shall|is|are|was|were)\b.*\.$", t))


def detect_title(lines: list[tuple[str, str]]) -> tuple[str, str]:
    first = lines[:FIRST_PAGE_BLOCKS]
    for t, _bt in first:                                   # explicit label wins
        m = _TITLE_LABEL.match(t)
        if m and _ASSIGN_WORDS.search(m.group(1)):
            return _clean(m.group(1)), "LABEL"
    for i, (t, bt) in enumerate(first):
        if _GENERIC_HEADING.match(t) or _is_sentence(t) or len(t) < 8:
            continue
        cand = _clean(_TOR_PREFIX.sub("", t)) if _TOR_PREFIX.match(t) else t
        if not _ASSIGN_WORDS.search(cand) or len(cand) > 220:
            continue
        # a short heading ("Final Evaluation for") continued on the next line
        if (len(cand.split()) <= 4 or re.search(r"\b(?:for|of|on)$", cand, re.I)) \
                and i + 1 < len(first):
            nxt = first[i + 1][0]
            if re.match(r"^(?:for|of|on)\b|^[\"“‘']", nxt, re.I) or \
                    re.search(r"\b(?:for|of|on)$", cand, re.I):
                if not _is_sentence(nxt) and len(nxt) < 200:
                    cand = _clean(f"{cand} {nxt}")
        return cand.rstrip("."), "HEADING" if bt in ("HEADING", "TITLE") else "FIRST_PAGE"
    return "", ""


def detect_client(text: str, lines: list[tuple[str, str]]) -> tuple[str, str]:
    for t, _bt in lines[:FIRST_PAGE_BLOCKS * 2]:
        m = _CLIENT_LABEL.match(t)
        if m:
            org = _clean(re.split(r"[,;(]", m.group(1))[0])
            if org and org not in _NOT_ORG:
                return org, "LABEL"
    donors = {m.group("org") for m in _DONOR.finditer(text)}
    score: Counter = Counter()
    for pat, w in _CLIENT_PATTERNS:
        for m in re.finditer(pat, text):
            org = m.group("org").strip()
            org = re.sub(r"\s+(?:the|of|for|and)$", "", org)
            if org in _NOT_ORG or org in donors or len(org) < 2:
                continue
            score[org] += w
    if not score:
        return "", ""
    org, s = score.most_common(1)[0]
    if s < 3:
        return "", ""                                   # not explicit enough
    # prefer the acronym when the text defines one: "… Organisation (ZOA)"
    acr = re.search(rf"{re.escape(org)}\s*\(({_ACRONYM})\)", text)
    return (acr.group(1) if acr else org), "TEXT"


def detect_country(text: str, title: str, lines: list[tuple[str, str]]) -> tuple[str, str]:
    score: Counter = Counter()
    label_hit = False
    for t, _bt in lines:
        m = _LOCATION_LABEL.match(t)
        if m:
            for name, rx in _COUNTRY_RE:
                if rx.search(m.group(1)):
                    score[name] += 5
                    label_hit = True
    for name, rx in _COUNTRY_RE:
        if title and rx.search(title):
            score[name] += 5
        n = len(rx.findall(text))
        score[name] += n
        score[name] += 2 * len(re.findall(rf"\bin\s+(?:[A-Z][a-z]+[\s,]+){{0,3}}{rx.pattern}",
                                          text, re.I))
    score = Counter({k: v for k, v in score.items() if v > 0})
    if not score:
        return "", ""
    (top, s), *rest = score.most_common(2) + [("", 0)]
    runner = rest[0][1] if rest else 0
    if s >= 3 and s > runner:
        return top, "LABEL" if label_hit else "TEXT"
    return "", ""


def detect_subnational(text: str, title: str, country: str,
                       lines: list[tuple[str, str]]) -> list[str]:
    if not country:
        return []
    crx = next(rx for name, rx in _COUNTRY_RE if name == country)
    counts: Counter = Counter()
    sources = [title] + [m.group(1) for t, _ in lines if (m := _LOCATION_LABEL.match(t))]
    for src in sources:
        for m in _DIRECTIONAL.finditer(src or ""):
            counts[m.group(1)] += 3
    for m in _DIRECTIONAL.finditer(text):
        counts[m.group(1)] += 1
    for m in _ADMIN_UNIT.finditer(text):
        counts[m.group(1)] += 1
    before_country = (r"\b([A-Z][a-z]{3,}(?:\s+[A-Z][a-z]{3,})?)\s*,\s*(?:"
                      + crx.pattern + r")")
    for m in re.finditer(before_country, text):
        counts[m.group(1)] += 2
    # "Nyala, South Darfur": a town named right before a known state
    for state in [p for p in counts if _DIRECTIONAL.fullmatch(p)]:
        for m in re.finditer(rf"\b([A-Z][a-z]{{3,}})\s*,\s*{re.escape(state)}\b", text):
            counts[m.group(1)] += 2
    out = []
    for place, n in counts.most_common():
        if place in _PLACE_STOP or crx.fullmatch(place) or n < 2:
            continue
        if any(rx.fullmatch(place) for _nm, rx in _COUNTRY_RE):
            continue
        out.append(place)
    return out[:5]


def detect_metadata(blocks: list[dict]) -> dict:
    """Title / client / country / subnational_location stated by the TOR (or empty)."""
    lines = _lines(blocks)
    text = "\n".join(t for t, _ in lines)
    title, title_m = detect_title(lines)
    client, client_m = detect_client(text, lines)
    country, country_m = detect_country(text, title, lines)
    sub = detect_subnational(text, title, country, lines)
    return {"project_title": title, "title_method": title_m,
            "client": client, "client_method": client_m,
            "country": country, "country_method": country_m,
            "subnational_location": sub}
