"""Section- and entity-aware methodology counts for numeric QA.

Extracts the proposal's CURRENT methodology counts (household survey, KII, FGD,
census) so they can be checked against each other and against the run's
approved/provisional decisions. It deliberately ignores:

- historical sections (Relevant Experience, Team bios, organisational profile),
- past-project tables (Assignment / Client / Year / Scale columns),
- ARFADA portfolio statistics (e.g. "73,906 surveys" from the Master Tracker),
- reference values (minimum sample, baseline sample, reserve list, targets),
- breakdown rows, which are summed and compared to the stated total instead.

A number is attributed to a metric only when it is bound to it ("14 FGDs",
"19 key informant interviews", "250 household interviews", "census of all 40
CAC members"), never merely because it sits within a few characters of a word.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# metric → noun-phrase regex (order matters for decision mapping: specific first)
METRIC_NOUNS: dict[str, str] = {
    "FGD": r"fgds?\b|focus[- ]group(?:\s+discussions?)?",
    "KII": r"kiis?\b|key[- ]informant(?:\s+interviews?)?",
    "census": r"(?:cac\s+)?census\b",
    "survey": (r"(?:household|hh)\s+(?:interviews?|surveys?|questionnaires?)\b|surveys?\b|"
               r"survey\s+respondents?\b|households?\s+(?:surveyed|interviewed)\b"),
}

_NUM = r"(\d{1,3}(?:,\d{3})+|\d+)"
# words allowed between a number and its metric noun ("250 completed household
# interviews"); connectives such as "of/with/per" break the binding.
_FILLER = r"(?:(?!of\b|and\b|or\b|with\b|per\b|to\b|from\b|for\b|in\b|at\b|by\b|than\b)[a-z][\w-]*\s+){0,3}?"
_REFERENCE_BEFORE = re.compile(
    r"(?:minimum|min\.|baseline|previous|past|reserve|target(?:ed)?|maximum|before\s+correction|"
    r"contact\s+list|n0|formula)\W+(?:\w+\W+){0,3}$", re.I)
_SUBGROUP_AFTER = re.compile(r"^\s*(?:with|among|for|from|in\s+each|per|each)\b", re.I)

_HISTORICAL_SECTION = re.compile(
    r"EXPERIENCE|TEAM|ORGANI[SZ]ATION|COMPANY|PROFILE|ABOUT|PAST|REFERENCE|CAPABILIT|"
    r"QUALIFICATION|PERSONNEL|STAFF", re.I)
_HISTORICAL_HEADER = re.compile(r"\b(?:year|client|donor|assignment|scale|completed|period)\b", re.I)
_HISTORICAL_PROSE = re.compile(
    r"\barfada\b.{0,160}\b(?:tracker|has\s+(?:delivered|completed|conducted|carried\s+out)|"
    r"track\s+record|assignments|portfolio|to\s+date)\b|"
    r"\b(?:has|have)\s+(?:delivered|completed|conducted)\b.{0,80}\b(?:surveys|kiis|fgds)\b", re.I | re.S)
_TOTAL_LABEL = re.compile(r"\btotal\b", re.I)

# decision text → metric (specific first; a sample-size decision is the survey count)
_DECISION_HINTS = {
    "FGD": r"\bfgds?\b|focus[- ]group",
    "KII": r"\bkiis?\b|key[- ]informant",
    "census": r"\bcensus\b",
    "survey": r"\bsurvey|\bsample\s*size|\bhouseholds?\b|\brespondents?\b",
}


@dataclass
class Claim:
    metric: str
    value: int
    section_id: str
    kind: str          # prose | table_sum | table_total
    snippet: str
    subgroup: bool = False


def _int(s: str) -> int:
    return int(s.replace(",", ""))


def is_historical_section(section_id: str) -> bool:
    return bool(_HISTORICAL_SECTION.search(section_id or ""))


def _metric_of_label(text: str) -> Optional[str]:
    t = (text or "").strip().lower()
    for metric, noun in METRIC_NOUNS.items():
        if re.match(rf"^(?:{noun})", t):
            return metric
    return None


def metric_of_text(text: str) -> Optional[str]:
    t = (text or "").lower()
    for metric, noun in METRIC_NOUNS.items():
        if re.search(noun, t):
            return metric
    return None


def prose_claims(text: str, section_id: str, *, exclude_values: set = frozenset()) -> list[Claim]:
    """Metric-bound counts in running text (one sentence at a time)."""
    out: list[Claim] = []
    for sentence in re.split(r"(?<=[.;!?])\s+|\n+", text or ""):
        if _HISTORICAL_PROSE.search(sentence):
            continue
        low = sentence.lower()
        found: list[Claim] = []
        for metric, noun in METRIC_NOUNS.items():
            pats = [rf"{_NUM}\s+{_FILLER}(?:{noun})",                 # 14 FGDs
                    rf"(?:{noun})\s*[:(=]\s*{_NUM}"]                   # FGDs: 14
            if metric == "census":
                pats = [rf"census\s+(?:survey\s+)?of\s+(?:all\s+)?(?:the\s+)?{_NUM}",
                        rf"\ball\s+{_NUM}\s+(?:cac\s+)?(?:committee\s+)?members\b"]
            for pat in pats:
                for m in re.finditer(pat, low, re.I):
                    raw = next(g for g in m.groups() if g)
                    v = _int(raw)
                    if v == 0 or v in exclude_values or 1900 <= v <= 2100:
                        continue
                    if _REFERENCE_BEFORE.search(low[:m.start()][-40:]):
                        continue
                    if re.search(r"\d\s*[-–—]\s*$", low[:m.start(m.lastindex)]):
                        continue  # end of a range such as "0–3" or "8–10"
                    if metric == "survey" and re.search(r"\b(?:census)\b", low[max(0, m.start() - 20):m.end()]):
                        continue  # "census survey" belongs to the census metric
                    sub = bool(_SUBGROUP_AFTER.match(low[m.end():m.end() + 20]))
                    found.append(Claim(metric, v, section_id, "prose",
                                       sentence.strip()[:120], subgroup=sub))
        # in-sentence breakdown: "14 FGDs: 10 with … and 4 with …" keeps the total
        for metric in {c.metric for c in found}:
            vals = [c for c in found if c.metric == metric]
            if len(vals) >= 3:
                top = max(vals, key=lambda c: c.value)
                if sum(c.value for c in vals if c is not top) == top.value:
                    for c in vals:
                        if c is not top:
                            c.subgroup = True
        out.extend(found)
    return out


def table_claims(block: dict, section_id: str, *, exclude_values: set = frozenset()) -> list[Claim]:
    """Claims from a table: breakdown rows are summed per metric, Total rows kept."""
    cols = [str(c) for c in block.get("columns", [])]
    rows = [[str(c) for c in r] for r in block.get("rows", [])]
    header = " ".join(cols)
    if len(_HISTORICAL_HEADER.findall(header)) >= 2:
        return []                                   # a past-project table
    total_idx = next((i for i, c in enumerate(cols) if _TOTAL_LABEL.search(c)), None)
    out: list[Claim] = []
    if total_idx is not None:
        sums: dict[str, int] = {}
        for r in rows:
            if total_idx >= len(r):
                continue
            label = " ".join(r[:total_idx])
            m = re.match(rf"^\s*{_NUM}\s*$", r[total_idx])
            if not m:
                continue
            v = _int(m.group(1))
            if _TOTAL_LABEL.search(label):
                metric = metric_of_text(label)
                if metric:
                    out.append(Claim(metric, v, section_id, "table_total", label[:120]))
                continue
            metric = _metric_of_label(r[0]) or (_metric_of_label(r[1]) if len(r) > 1 else None)
            if metric:
                sums[metric] = sums.get(metric, 0) + v
        for metric, v in sums.items():
            out.append(Claim(metric, v, section_id, "table_sum",
                             f"sum of {metric} rows in table '{header[:60]}'"))
        return out
    # no Total column: treat each row as text (e.g. a parameter table)
    for r in rows:
        for cell in r:      # cell by cell: never bind a number across cell borders
            out.extend(prose_claims(cell, section_id, exclude_values=exclude_values))
    return out


def current_claims(gen_sections: dict, *, exclude_values: set = frozenset()) -> dict[str, list[Claim]]:
    """All current-methodology claims, grouped by metric."""
    by_metric: dict[str, list[Claim]] = {m: [] for m in METRIC_NOUNS}
    for sid, cand in gen_sections.items():
        if is_historical_section(sid):
            continue
        for b in cand.get("blocks", []):
            t = b.get("type")
            claims: list[Claim] = []
            if t in ("paragraph",):
                claims = prose_claims(b.get("text", ""), sid, exclude_values=exclude_values)
            elif t in ("bullet_list", "numbered_list"):
                for item in b.get("items", []):
                    claims.extend(prose_claims(str(item), sid, exclude_values=exclude_values))
            elif t == "table":
                claims = table_claims(b, sid, exclude_values=exclude_values)
            for c in claims:
                by_metric[c.metric].append(c)
    # sub-group mentions smaller than the metric's largest stated count are parts
    for metric, claims in by_metric.items():
        if not claims:
            continue
        biggest = max(c.value for c in claims)
        by_metric[metric] = [c for c in claims if not (c.subgroup and c.value < biggest)]
    return by_metric


def decision_targets(register: Optional[dict]) -> dict[str, int]:
    """Current-run numeric decisions (approved or provisional) mapped to metrics."""
    out: dict[str, int] = {}
    for d in (register or {}).get("decisions", []):
        if d.get("decision_status") not in ("RESOLVED", "PROVISIONAL_RECOMMENDATION"):
            continue
        val = d.get("selected_value")
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            continue
        text = " ".join(str(d.get(k) or "") for k in
                        ("decision_id", "question", "source_text", "category"))
        text = text.replace("_", " ").lower()
        metric = next((m for m, pat in _DECISION_HINTS.items() if re.search(pat, text)), None)
        if metric and metric not in out:
            out[metric] = int(val)
    return out
