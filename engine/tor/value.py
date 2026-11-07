"""PE2 exact numeric / date / duration model (spec §28).

Every parsed value keeps the RAW phrase, a normalized value, a unit, and a qualifier
(AT_LEAST / AT_MOST / APPROX / RANGE / EXACT). Nothing is silently flattened:
"approximately 30 days" -> (APPROX, 30, days), "at least 10 KIIs" -> (AT_LEAST, 10),
"5-7 FGDs" -> (RANGE, 5, 7), "95% confidence" -> percentage, "17:00" -> time.
Deterministic regex only; no inference of missing components.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Quantity:
    raw: str
    kind: str                 # INT | DECIMAL | PERCENT | CURRENCY | DATE | TIME | DURATION | RANGE
    value: Optional[float]
    value_max: Optional[float]  # for RANGE
    unit: str
    qualifier: str            # EXACT | AT_LEAST | AT_MOST | APPROX | RANGE
    extras: dict = field(default_factory=dict)


_APPROX = re.compile(r"\b(approx(?:imately)?|around|about|roughly|circa|~)\b", re.I)
_ATLEAST = re.compile(r"\b(at\s+least|minimum(?:\s+of)?|no\s+less\s+than|\bmin\.?\b|>=|≥)\b", re.I)
_ATMOST = re.compile(r"\b(at\s+most|maximum(?:\s+of)?|no\s+more\s+than|not\s+exceed(?:ing)?|"
                     r"up\s+to|\bmax\.?\b|<=|≤)\b", re.I)
_RANGE = re.compile(r"(\d[\d,]*\.?\d*)\s*(?:-|–|—|to)\s*(\d[\d,]*\.?\d*)")
# a unit that may trail a range/number ("3-6 months", "10-15 working days")
_TRAIL_UNIT = re.compile(r"\s*(working\s+days|calendar\s+days|days|weeks|months|years|hours|%|"
                         r"kiis?|fgds?|idis?|interviews?|respondents?|reports?|participants?)\b", re.I)
# deterministic number-words only when directly followed by a countable unit/noun (spec §20)
_NUMWORD = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
            "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
_NUMWORD_RE = re.compile(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+"
                         r"(working\s+days|calendar\s+days|days|weeks|months|years|kiis?|fgds?|idis?|"
                         r"interviews?|reports?|respondents?|enumerators?|participants?)\b", re.I)
_PERCENT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
_CURRENCY = re.compile(r"\b(USD|EUR|GBP|SDG|EGP|JOD|\$|€|£)\s*([\d,]+(?:\.\d+)?)|"
                       r"([\d,]+(?:\.\d+)?)\s*(USD|EUR|GBP)\b", re.I)
_TIME = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_DURATION = re.compile(r"(\d[\d,]*\.?\d*)\s*(working\s+days|calendar\s+days|days|weeks|months|years|hours)", re.I)
_DATE = re.compile(
    r"\b(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4}|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}|"
    r"(?:end\s+of\s+)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}|"
    r"\d{4}-\d{2}-\d{2})\b", re.I)


def _num(s: str) -> float:
    s = (s or "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def _qualifier(ctx: str) -> str:
    if _APPROX.search(ctx):
        return "APPROX"
    if _ATLEAST.search(ctx):
        return "AT_LEAST"
    if _ATMOST.search(ctx):
        return "AT_MOST"
    return "EXACT"


def parse_quantities(text: str) -> list[Quantity]:
    """Extract every quantity in `text`, preserving raw phrase + qualifier. Order:
    range/percent/currency/time/date/duration/int (each region consumed once)."""
    out: list[Quantity] = []
    if not text:
        return out
    low = text
    used_spans: list[tuple[int, int]] = []

    def free(a, b):
        return not any(a < e and s < b for s, e in used_spans)

    for m in _RANGE.finditer(low):
        if free(*m.span()):
            # a range's qualifier is derived from its context ('at least 10-15' stays AT_LEAST,
            # 'approximately 3-6' stays APPROX); a bare range is RANGE. Trailing unit preserved.
            ctx_q = _qualifier(low[max(0, m.start() - 20):m.start()])
            qual = ctx_q if ctx_q != "EXACT" else "RANGE"
            um = _TRAIL_UNIT.match(low[m.end():])
            unit = re.sub(r"\s+", "_", um.group(1).lower()) if um else ""
            span = (m.start(), m.end() + (um.end() if um else 0))
            used_spans.append(span)
            out.append(Quantity(low[span[0]:span[1]], "RANGE", _num(m.group(1)), _num(m.group(2)),
                                unit, qual))
    # number-words directly before a countable unit (deterministic; spec §20)
    for m in _NUMWORD_RE.finditer(low):
        if free(*m.span()):
            used_spans.append(m.span())
            unit = re.sub(r"\s+", "_", m.group(2).lower())
            out.append(Quantity(m.group(0), "DURATION" if unit in
                                ("days", "working_days", "calendar_days", "weeks", "months", "years")
                                else "INT", float(_NUMWORD[m.group(1).lower()]), None, unit, "EXACT"))
    for m in _PERCENT.finditer(low):
        if free(*m.span()):
            used_spans.append(m.span())
            out.append(Quantity(m.group(0), "PERCENT", float(m.group(1)), None, "%",
                                _qualifier(low[max(0, m.start() - 20):m.start()])))
    for m in _CURRENCY.finditer(low):
        if free(*m.span()):
            num_str = m.group(2) or m.group(3) or ""
            if not num_str.strip(", "):
                continue
            used_spans.append(m.span())
            cur = (m.group(1) or m.group(4) or "").upper()
            out.append(Quantity(m.group(0), "CURRENCY", _num(num_str), None, cur, "EXACT"))
    for m in _TIME.finditer(low):
        if free(*m.span()):
            used_spans.append(m.span())
            out.append(Quantity(m.group(0), "TIME", float(m.group(1)) + float(m.group(2)) / 60.0,
                                None, "hh:mm", "EXACT", {"hh": int(m.group(1)), "mm": int(m.group(2))}))
    for m in _DATE.finditer(low):
        if free(*m.span()):
            used_spans.append(m.span())
            out.append(Quantity(m.group(0).strip(), "DATE", None, None, "", "EXACT"))
    for m in _DURATION.finditer(low):
        if free(*m.span()):
            used_spans.append(m.span())
            q = _qualifier(low[max(0, m.start() - 20):m.start()])
            out.append(Quantity(m.group(0), "DURATION", _num(m.group(1)), None,
                                re.sub(r"\s+", "_", m.group(2).lower()), q))
    for m in re.finditer(r"\b(\d[\d,]*)\b", low):
        if free(*m.span()):
            used_spans.append(m.span())
            q = _qualifier(low[max(0, m.start() - 20):m.start()])
            # trailing '+' ("5+ years", "10+") means AT_LEAST (spec §19)
            if q == "EXACT" and low[m.end():m.end() + 1] == "+":
                q = "AT_LEAST"
            out.append(Quantity(m.group(0), "INT", _num(m.group(1)), None, "", q))
    return out
