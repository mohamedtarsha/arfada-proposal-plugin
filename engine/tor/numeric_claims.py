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

import math
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

# v0.6.12: whole numbers only — "73,906" is one number; never a fragment of a
# decimal ("247.5" is not 247 or 5)
_NUM = r"(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d+)(?![\d]|[.,]\d)"
# words allowed between a number and its metric noun ("250 completed household
# interviews"); connectives such as "of/with/per" break the binding.
_FILLER = r"(?:(?!of\b|and\b|or\b|with\b|per\b|to\b|from\b|for\b|in\b|at\b|by\b|than\b)[a-z][\w-]*\s+){0,3}?"
_REFERENCE_BEFORE = re.compile(
    r"(?:minimum|min\.|baseline|previous|past|reserve|targeted|maximum|before\s+correction|"
    r"contact\s+list|n0|formula)\W+(?:\w+\W+){0,3}$", re.I)
_SUBGROUP_AFTER = re.compile(r"^\s*(?:with|among|for|from|in\s+each|per|each)\b", re.I)

# --- household survey count (v0.6.9): "248 households", "248 HH", "household survey
# of 248", "survey sample of 248", "149 + 99 = 248". Bare household counts are
# population figures unless the sentence is about the survey/sample, and caseload /
# beneficiary / baseline numbers are never the current survey count.
_SURVEY_CONTEXT = re.compile(
    r"survey|sampl|interview|questionnaire|enumerat|respondent", re.I)
_SPLIT_CONTEXT = re.compile(r"survey|sampl|household|\bfhh\b|\bmhh\b|headed", re.I)
_POPULATION_NEAR = re.compile(
    r"original|caseload|population|beneficiar|registered|received|verified|reached|"
    r"additional|frame|\blist\b|targeted|food[- ]insecure|total\s+of|vouchers?|rounds?|"
    r"baseline|minimum|reserve|contact", re.I)
_HH_NOUN = r"(?:households?|hh)\b"
_HH_DIRECT = re.compile(rf"{_NUM}\s+(?:sampled|surveyed|interviewed|completed)\s+{_HH_NOUN}", re.I)
_HH_BARE = re.compile(rf"{_NUM}\s+{_HH_NOUN}", re.I)
_HH_SURVEY_OF = re.compile(
    rf"(?:household|hh)\s+survey\s+(?:of|with|covering|among)\s+(?:a\s+sample\s+of\s+)?{_NUM}",
    re.I)
_SAMPLE_OF = re.compile(
    rf"\b(?:survey\s+)?sample(?:\s+size)?\s+(?:of|is|=|:|will\s+be)\s*{_NUM}", re.I)
_SUM_EQ = re.compile(rf"{_NUM}\s*(?:fhh|mhh|female[- ]headed|male[- ]headed)?\s*\+\s*{_NUM}\s*"
                     rf"(?:fhh|mhh|female[- ]headed|male[- ]headed)?\s*=\s*{_NUM}", re.I)
_SAMPLE_ROW_LABEL = re.compile(
    r"^\s*(?:proposed|planned|final|target|completed)?\s*(?:household\s+)?(?:survey\s+)?"
    r"(?:sample(?:\s+size)?|household\s+(?:survey|interviews?))\b", re.I)


def _household_survey_claims(sentence: str, section_id: str, exclude_values) -> list:
    low = sentence.lower()
    out: list = []

    def keep(v, m, check_population=True):
        if v == 0 or v in exclude_values or 1900 <= v <= 2100:
            return
        before = low[max(0, m.start() - 40):m.start()]
        if _REFERENCE_BEFORE.search(before) or re.search(r"\d\s*[-–—]\s*$", before):
            return
        if re.search(r"\d\s*%\s*\(?\s*$", before):
            return      # "90% (1,170 HH)": an indicator count, not the sample
        if re.match(r"^\s*(?:fhh|mhh|female[- ]headed|male[- ]headed)?\s*\+", low[m.end():]):
            return      # the first part of "149 FHH + 99 MHH = 248"
        if re.match(r"^\s*[/÷×*]\s*\(?\s*\d", low[m.end():]):
            return      # v0.6.13: an operand of "225 / 0.90 = 250" (the result is the count)
        if check_population and _POPULATION_NEAR.search(
                low[max(0, m.start() - 30):m.end() + 25]):
            return
        # v0.6.12: a baseline figure later in the sentence ("the baseline round, which
        # interviewed 243 households") stays a reference value, never the current sample
        head = low[max(0, m.start() - 90):m.start()]
        b = head.rfind("baseline")
        if b >= 0 and not re.search(r"propos|endline|end line|this evaluation|we will|our",
                                    head[b:]):
            return
        out.append(Claim("survey", v, section_id, "prose", sentence.strip()[:120]))

    for m in _HH_DIRECT.finditer(low):           # "248 sampled households" is explicit
        keep(_int(m.group(1)), m, check_population=False)
    if _SURVEY_CONTEXT.search(low):
        for m in _HH_BARE.finditer(low):
            if any(c.value == _int(m.group(1)) for c in out):
                continue
            keep(_int(m.group(1)), m)
        for pat in (_HH_SURVEY_OF, _SAMPLE_OF):
            for m in pat.finditer(low):
                v = _int(m.group(1))
                if not any(c.value == v for c in out):
                    keep(v, m, check_population=False)
    if _SPLIT_CONTEXT.search(low):
        for m in _SUM_EQ.finditer(low):          # "149 + 99 = 248" (FHH + MHH)
            a, b, c = (_int(g) for g in m.groups())
            if a + b == c:
                out = [x for x in out if x.value not in (a, b)]   # parts, not totals
                if not any(x.value == c for x in out):
                    keep(c, m, check_population=False)
    return out

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
                    if re.match(r"^\s*(?:fhh|mhh|female[- ]headed|male[- ]headed)?\s*\+",
                                low[m.end(m.lastindex):]):
                        continue  # first part of a sum: "interviews: 149 FHH + 99 MHH = 248"
                    if metric == "survey" and re.search(r"\b(?:census)\b", low[max(0, m.start() - 20):m.end()]):
                        continue  # "census survey" belongs to the census metric
                    sub = bool(_SUBGROUP_AFTER.match(low[m.end():m.end() + 20]))
                    found.append(Claim(metric, v, section_id, "prose",
                                       sentence.strip()[:120], subgroup=sub))
        for c in _household_survey_claims(sentence, section_id, exclude_values):
            if not any(f.metric == "survey" and f.value == c.value for f in found):
                found.append(c)
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
        # "Proposed sample | 248" — the label names the current survey sample
        if len(r) >= 2 and _SAMPLE_ROW_LABEL.match(r[0]) and \
                not re.search(r"minimum|baseline|reserve|contact|n0", r[0], re.I):
            m = re.match(rf"^\s*{_NUM}\b", r[1])
            if m and _int(m.group(1)) not in exclude_values:
                out.append(Claim("survey", _int(m.group(1)), section_id, "table_row",
                                 f"{r[0]}: {r[1]}"[:120]))
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


# ---------------------------------------------------------------------------
# v0.6.12: sampling provenance — minimum → allowance → adjusted → proposed (rounded up)
# ---------------------------------------------------------------------------

_P_NUM = r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
_P_MIN = re.compile(rf"\bminimum(?:\s+sample(?:\s+size)?)?(?:\s+(?:of|is|=|:|after[^,.;]{{0,40}}?))?\s*"
                    rf"(?<![\d.,]){_P_NUM}|{_P_NUM}[ \t]+(?:\w+[ \t]+){{0,2}}?minimum\b", re.I)
_P_ALLOW = re.compile(rf"{_P_NUM}\s*%\s*(?:\w+\s+){{0,3}}?(?:non-?response|reserve|allowance|"
                      rf"contingency|attrition|buffer)|(?:non-?response|reserve|allowance|attrition|"
                      rf"buffer)[^.;\d]{{0,40}}?{_P_NUM}\s*%", re.I)
_P_ADJ = re.compile(rf"\b(?:adjusted|inflated|raw|gives?|giving|=|≈|to)\s+(?:a\s+)?(?:\w+\s+){{0,2}}?"
                    rf"(\d+\.\d+)\b"
                    # v0.6.13 divisor form: "225 / 0.90 = 250", "225 ÷ (1 − 0.10) = 250"
                    rf"|\b\d+(?:\.\d+)?\s*[/÷]\s*\(?\s*(?:1\s*[-−–]\s*)?0?\.\d+\s*\)?\s*=\s*{_P_NUM}",
                    re.I)
_P_PROPOSED = re.compile(rf"\b(?:propos\w*|planned|final|target)\s+(?:\w+\s+){{0,3}}?(?:sample\s+)?"
                         rf"(?:of\s+|is\s+|=\s*|:\s*)?{_P_NUM}\b|\brounded\s+up\s+to\s+{_P_NUM}\b", re.I)
# v0.6.13: the baseline SAMPLE (a sample noun is required — "baseline indicators" in a
# table header is not a sample size); a label cell may be followed by its value cell
_P_BASELINE = re.compile(
    rf"\bbaseline\s+(?:(?:survey|round|study)\s+)?(?:sample(?:\s+size)?|target\s+number|"
    rf"number\s+of\s+(?:households|hhs?)|survey|round)\b(?:\s*\([^)\n]{{0,40}}\))?"
    rf"(?:[ \t]+\w+){{0,3}}?[ \t]*(?:of|was|were|is|=|:)?\s*{_P_NUM}\b", re.I)
_P_ROUND_UP = re.compile(r"\bround(?:ed|ing)?\s+up(?:ward)?|\bupward\b|\bceil", re.I)


def _first(rx, text):
    """First matching value that is not a calendar year ("the July 2026 baseline")."""
    for m in rx.finditer(text):
        g = next((x for x in m.groups() if x), None)
        if not g:
            continue
        v = float(g.replace(",", ""))
        if v.is_integer() and 1900 <= v <= 2100:
            continue
        return v
    return None


def required_initial_sample(minimum: float, nonresponse_pct: float) -> dict:
    """Non-response inflation: n_initial = n / (1 − r)  (v0.6.13).

    Interviewing n / (1 − r) households leaves n completed interviews when a share r does
    not respond; n × (1 + r) under-inflates (225 × 1.10 = 247.5 < 225 / 0.90 = 250).
    """
    r = nonresponse_pct / 100.0
    exact = minimum / (1.0 - r)
    return {"formula": "n / (1 - r)", "minimum": minimum, "nonresponse_rate": r,
            "exact": round(exact, 4), "required_initial": int(math.ceil(exact - 1e-9)),
            "arithmetic": f"{minimum:g} / (1 - {r:g}) = {minimum:g} / {1 - r:g} = {exact:g}"}


def sampling_provenance(text: str) -> dict:
    """Parse and check minimum → non-response → required initial → proposed (+ baseline).

    v0.6.13: the required initial sample is n / (1 − r) (225 / 0.90 = 250), never
    n × (1 + r); the arithmetic is stored with the result. The baseline sample is
    recorded separately and never compared with the proposed sample as if it were the
    same quantity.
    """
    t = text or ""
    prov = {"minimum": _first(_P_MIN, t), "allowance_pct": _first(_P_ALLOW, t),
            "adjusted": _first(_P_ADJ, t), "proposed": _first(_P_PROPOSED, t),
            "baseline": _first(_P_BASELINE, t),
            "rounding": "upward" if _P_ROUND_UP.search(t) else "",
            "formula": "n / (1 - r)", "required_initial": None, "exact_initial": None,
            "arithmetic": None, "draft_formula": ""}
    issues = []
    mn, pct, adj, prop = prov["minimum"], prov["allowance_pct"], prov["adjusted"], prov["proposed"]
    if mn and prop and prop < mn:
        issues.append(f"proposed sample {prop:g} is below the minimum {mn:g}")
    if mn and pct and 0 < pct < 100:
        req = required_initial_sample(mn, pct)
        prov["required_initial"], prov["exact_initial"] = req["required_initial"], req["exact"]
        prov["arithmetic"] = req["arithmetic"]
        if adj is not None:
            if abs(adj - req["exact"]) <= max(0.5, 0.005 * adj):
                prov["draft_formula"] = "n / (1 - r)"
            elif abs(adj - mn * (1 + pct / 100.0)) <= max(0.5, 0.005 * adj):
                prov["draft_formula"] = "n * (1 + r)"
                issues.append(f"adjusted value {adj:g} uses {mn:g} × (1 + {pct:g}%); the "
                              f"non-response adjustment is {mn:g} / (1 − {pct / 100.0:g}) = "
                              f"{req['exact']:g}")
            else:
                issues.append(f"adjusted value {adj:g} does not equal {mn:g} / (1 − "
                              f"{pct / 100.0:g}) = {req['exact']:g}")
        if prop and prop + 1e-9 < req["required_initial"]:
            issues.append(f"proposed sample {prop:g} is below the required initial sample "
                          f"{req['required_initial']} ({req['arithmetic']})")
    if adj and prop and prop < adj:
        issues.append(f"proposed sample {prop:g} is below the adjusted value {adj:g}")
    prov["consistent"] = not issues
    prov["issues"] = issues
    prov["found"] = any(prov[k] is not None for k in ("minimum", "adjusted", "proposed"))
    return prov
