"""Typed numeric tokens for QA (v0.6.12).

"73,906" is ONE number, "247.5" is one decimal number, "CFGB 3350" is an identifier,
"30 days" is a duration. Each number gets a context type so a check compares only
the numbers it is about:

  PERCENTAGE · YEAR · DURATION · IDENTIFIER · MONEY ·
  PORTFOLIO_METRIC   ARFADA organisational figures (projects, surveys, KIIs, years of
                     experience …) stated about ARFADA's record
  HISTORICAL_STAT    figures of a past project ("197 surveys" in an experience row)
  METHODOLOGY_COUNT  this proposal's planned counts (households, interviews, FGDs …)
  COUNT              anything else
"""
from __future__ import annotations

import re
from dataclasses import dataclass

NUMBER = re.compile(r"(?<![\w.,])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?![\w]|,\d{3})")
_UNIT_DURATION = re.compile(r"^\s*(?:working\s+|calendar\s+|consecutive\s+)?"
                            r"(?:days?|weeks?|months?|hours?|years?)\b", re.I)
_YEARS_OF_EXPERIENCE = re.compile(r"^\s*\+?\s*years?\s+(?:of\s+)?(?:\w+\s+){0,2}?"
                                  r"(?:experience|operation|operations|work|existence)\b", re.I)
_PERCENT = re.compile(r"^\s*(?:%|percent\b|per\s+cent\b|pp\b|percentage\s+points?)", re.I)
_MONEY_BEFORE = re.compile(r"(?:\$|usd|eur|€|£|sdg|gbp)\s*$", re.I)
_MONEY_AFTER = re.compile(r"^\s*(?:usd|eur|euros?|dollars?|gbp|sdg)\b", re.I)
_IDENT_BEFORE = re.compile(r"\b(?:[A-Z]{2,}[A-Z0-9&/-]*|No\.?|no\.|ref\.?|grant|project|"
                           r"contract|award|tender|rfq|rfp|code|id)\s*[#:]?\s*$")
_PORTFOLIO_NOUN = re.compile(
    r"^\s*(?:[\w-]+\s+){0,2}?(?:projects?|assignments?|evaluations?|studies|surveys?|"
    r"household\s+surveys?|kiis?|key\s+informant\s+interviews?|fgds?|focus\s+group\s+"
    r"discussions?|countries|clients?|donors?|staff|experts?|consultants?|enumerators?|"
    r"offices?|reports?)\b", re.I)
_METHOD_NOUN = re.compile(
    r"^\s*(?:[\w-]+\s+){0,2}?(?:households?|hh\b|respondents?|interviews?|participants?|"
    r"members?|fgds?|kiis?|focus\s+groups?|sites?|villages?|enumerators?|beneficiar)", re.I)
_PORTFOLIO_CONTEXT = re.compile(
    r"\bARFADA\b|\bportfolio\b|\btracker\b|\bto\s+date\b|\b(?:has|have)\s+(?:delivered|"
    r"completed|conducted|carried\s+out|implemented)\b|\bour\s+(?:record|track\s+record)\b", re.I)
_FUTURE = re.compile(r"\b(?:will|shall|propose[sd]?|plan(?:s|ned)?|aim|intend)\b", re.I)


@dataclass
class NumToken:
    value: float
    raw: str
    kind: str
    start: int
    end: int

    @property
    def int_value(self) -> int:
        return int(round(self.value))


def _kind(text: str, m, sentence: str) -> str:
    before, after = text[max(0, m.start() - 20):m.start()], text[m.end():m.end() + 60]
    raw = m.group(1)
    val = float(raw.replace(",", ""))
    if _PERCENT.match(after):
        return "PERCENTAGE"
    if _MONEY_BEFORE.search(before) or _MONEY_AFTER.match(after):
        return "MONEY"
    if _IDENT_BEFORE.search(before) and "," not in raw and "." not in raw:
        return "IDENTIFIER"
    if _YEARS_OF_EXPERIENCE.match(after):
        return "PORTFOLIO_METRIC" if _PORTFOLIO_CONTEXT.search(sentence) else "COUNT"
    if _UNIT_DURATION.match(after):
        return "DURATION"
    if "," not in raw and "." not in raw and 1900 <= val <= 2100:
        return "YEAR"
    if len(raw.replace(",", "")) >= 6 and "," not in raw:
        return "IDENTIFIER"                       # long bare codes (e.g. tender numbers)
    if _PORTFOLIO_NOUN.match(after) and _PORTFOLIO_CONTEXT.search(sentence) and \
            not _FUTURE.search(sentence):
        return "PORTFOLIO_METRIC"
    if _METHOD_NOUN.match(after) or _PORTFOLIO_NOUN.match(after):
        return "METHODOLOGY_COUNT" if _FUTURE.search(sentence) or not _PORTFOLIO_CONTEXT.search(
            sentence) else "HISTORICAL_STAT"
    return "COUNT"


def tokenize(text: str) -> list:
    out = []
    # a "." followed by a digit is a decimal point, not a sentence end ("247.5")
    for sent_m in re.finditer(r"(?:[^.;!?\n]|\.(?=\d))+[.;!?]?", text or ""):
        sentence = sent_m.group(0)
        for m in NUMBER.finditer(sentence):
            out.append(NumToken(float(m.group(1).replace(",", "")), m.group(1),
                                _kind(sentence, m, sentence),
                                sent_m.start() + m.start(1), sent_m.start() + m.end(1)))
    return out


def portfolio_metrics(text: str) -> list:
    return [t for t in tokenize(text) if t.kind == "PORTFOLIO_METRIC"]
