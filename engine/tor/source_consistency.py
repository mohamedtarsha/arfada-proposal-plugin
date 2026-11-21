"""TOR source-inconsistency register (v0.6.11).

Finds suspicious inconsistencies in the TOR's own figures and wording. Nothing is
corrected: each item is logged as SOURCE_INCONSISTENCY with the excerpt, so the
proposal can say values will be reconciled at inception instead of silently
"fixing" (or silently repeating) them.

Generic checks:
  PERCENT_SUM          labelled mutually exclusive categories whose percentages do
                       not add up to ~100% ("Poor 42.8%, Borderline 44.4%, Acceptable 15.8%")
  PARTS_EXCEED_TOTAL   category counts adding up to more than a total the TOR states
                       ("556 + 577 + 205 = 1,338" vs "1,300 households")
  OVERLAPPING_RANGES   category ranges that overlap ("Little or no hunger: 0-3",
                       "Moderate hunger: 2-3")
  TERMINOLOGY          the assignment named as different evaluation stages
                       ("final evaluation" … "the baseline survey process")
"""
from __future__ import annotations

import re
from collections import Counter

SOURCE_FILE = "source_inconsistencies.json"

_SUB_LABELS = {"fhh", "mhh", "male", "female", "men", "women", "boys", "girls", "total", "all",
               "all hh", "hh", "target", "baseline", "indicator"}
# "Poor: # 556 and % 42.8", "Little or no hunger: 0-3 = 23.9%", "Borderline 44.4%"
_LABELLED = re.compile(
    r"(?P<label>[A-Z][A-Za-z]+(?:\s+(?:or|and|no|to|[a-z]+|[A-Z][a-z]+)){0,4}?)\s*:\s*"
    r"(?:(?P<lo>\d{1,3})\s*[-–]\s*(?P<hi>\d{1,3})\s*=?\s*)?"
    r"(?:#\s*(?P<count>\d{1,3}(?:,\d{3})*|\d+)\s*(?:and|,)?\s*)?"
    r"(?:%\s*)?(?P<pct>\d{1,3}(?:\.\d+)?)\s*%?")
_TOTAL_STATED = re.compile(r"\b(\d{1,3}(?:,\d{3})+|\d{3,})\s+(?:selected\s+|verified\s+|"
                           r"registered\s+|targeted\s+|food[- ]insecure\s+)*"
                           r"(?:households?|hhs?|beneficiaries|participants)\b", re.I)
_STAGES = {
    "BASELINE": r"\bbase-?\s?line\s+(?:survey|study|assessment)\b",
    "ENDLINE": r"\b(?:end-?\s?line\s+(?:survey|study|evaluation)|final\s+evaluation)\b",
    "MIDLINE": r"\b(?:mid-?\s?line|mid-?term)\s+(?:survey|study|evaluation|review)\b",
}
# a stage phrase referring to THIS assignment (not to the existing baseline)
_SELF_REF = re.compile(
    r"(?:during|for|of|in|applying|conduct(?:ing)?|throughout)\s+(?:the|this|a)\s+"
    r"(?:[\w-]+\s+){0,2}?$", re.I)
_BASELINE_AS_DATA = re.compile(r"(?:against|from|in|on|established|existing|available|the)\s+"
                               r"(?:the\s+)?$", re.I)


def _num(s: str) -> int:
    return int(s.replace(",", ""))


def _groups(text: str) -> list:
    """Runs of distinct labelled categories (a repeated label starts a new run)."""
    runs, cur, labels, last_end = [], [], set(), -1
    for m in _LABELLED.finditer(text):
        label = " ".join(m.group("label").split()).lower()
        if label in _SUB_LABELS or label.split()[-1] in _SUB_LABELS:
            continue
        gap = m.start() - last_end if last_end >= 0 else 0
        between = text[last_end:m.start()] if last_end >= 0 else ""
        if label in labels or gap > 220 or re.search(r"[.;]\s+[A-Z]", between):
            if len(cur) >= 3:
                runs.append(cur)
            cur, labels = [], set()
        cur.append(m)
        labels.add(label)
        last_end = m.end()
    if len(cur) >= 3:
        runs.append(cur)
    return runs


def scan_text(text: str) -> list:
    items: list = []
    stated_totals = Counter(_num(m.group(1)) for m in _TOTAL_STATED.finditer(text or ""))
    for run in _groups(text or ""):
        excerpt = text[run[0].start():run[-1].end()][:300]
        labels = [" ".join(m.group("label").split()) for m in run]
        # a percentage only when a % sign is actually written with the value
        pcts = [float(m.group("pct")) for m in run if m.group("pct") and "%" in m.group(0)]
        if len(pcts) == len(run) and all(0 <= p <= 100 for p in pcts):
            s = round(sum(pcts), 1)
            if 60 <= s <= 160 and abs(s - 100) > 1.5:
                items.append({"type": "PERCENT_SUM", "labels": labels, "values": pcts,
                              "sum": s, "excerpt": excerpt,
                              "detail": f"category percentages add up to {s}%, not 100%"})
        counts = [_num(m.group("count")) for m in run if m.group("count")]
        if len(counts) == len(run):
            s = sum(counts)
            for total in stated_totals:
                if total < s <= total * 1.2:
                    items.append({"type": "PARTS_EXCEED_TOTAL", "labels": labels,
                                  "values": counts, "sum": s, "stated_total": total,
                                  "excerpt": excerpt,
                                  "detail": f"category counts add up to {s:,}, more than the "
                                            f"{total:,} stated elsewhere in the TOR"})
                    break
        ranges = [(" ".join(m.group("label").split()), int(m.group("lo")), int(m.group("hi")))
                  for m in run if m.group("lo") is not None]
        for i, (la, a1, a2) in enumerate(ranges):
            for lb, b1, b2 in ranges[i + 1:]:
                if la.lower() != lb.lower() and a1 <= b2 and b1 <= a2:
                    items.append({"type": "OVERLAPPING_RANGES", "labels": [la, lb],
                                  "values": [[a1, a2], [b1, b2]], "excerpt": excerpt,
                                  "detail": f"'{la}' ({a1}-{a2}) overlaps '{lb}' ({b1}-{b2})"})
    # terminology: the assignment named as different stages
    found: dict = {}
    for stage, pat in _STAGES.items():
        for m in re.finditer(pat, text or "", re.I):
            before = (text or "")[max(0, m.start() - 40):m.start()]
            if stage == "BASELINE" and _BASELINE_AS_DATA.search(before) and \
                    not _SELF_REF.search(before):
                continue
            if _SELF_REF.search(before) or stage != "BASELINE":
                found.setdefault(stage, []).append(text[max(0, m.start() - 30):m.end() + 20])
    if "BASELINE" in found and ("ENDLINE" in found or "MIDLINE" in found):
        other = "ENDLINE" if "ENDLINE" in found else "MIDLINE"
        items.append({"type": "TERMINOLOGY", "labels": ["BASELINE", other],
                      "excerpt": " … ".join([found["BASELINE"][0], found[other][0]])[:300],
                      "detail": "the TOR refers to this assignment both as a baseline survey "
                                f"and as a {other.lower()} / final evaluation"})
    # de-duplicate by (type, excerpt)
    seen, out = set(), []
    for it in items:
        k = (it["type"], it["excerpt"][:120], str(it.get("values")))
        if k not in seen:
            seen.add(k)
            out.append(it)
    return out


def scan_blocks(blocks: list) -> list:
    text = "\n".join((b.get("plain_text") or "") for b in blocks or [])
    return scan_text(text)
