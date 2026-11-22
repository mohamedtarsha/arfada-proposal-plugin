"""Source semantics of population figures (v0.6.13).

A number a TOR states about households is not always the same kind of fact:

  OBSERVED_BASELINE        measured at baseline ("In the baseline … HHs was 243")
  TARGET                   a planned / indicator target ("780 female-headed households …
                           receiving voucher-based food assistance" in the target column)
  REGISTERED_CASELOAD      the TOR states the caseload as registered / verified / enrolled
                           ("1,300 selected and verified food insecure households")
  PROPOSAL_ASSUMPTION      a figure the proposal itself derives (sample, stratum allocation)
  VERIFIED_PROJECT_RECORD  confirmed from a project record held in the run
                           (project_records.json, e.g. the registration list)

A TARGET is never silently promoted to REGISTERED_CASELOAD: proposal text may call a
figure "registered" only when the TOR or a project record supports it. A stratum
allocation derived from a TARGET composition is written as a provisional allocation
that will be recalculated at inception from the registration list.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

OBSERVED_BASELINE = "OBSERVED_BASELINE"
TARGET = "TARGET"
REGISTERED_CASELOAD = "REGISTERED_CASELOAD"
PROPOSAL_ASSUMPTION = "PROPOSAL_ASSUMPTION"
VERIFIED_PROJECT_RECORD = "VERIFIED_PROJECT_RECORD"
SEMANTICS = (OBSERVED_BASELINE, TARGET, REGISTERED_CASELOAD, PROPOSAL_ASSUMPTION,
             VERIFIED_PROJECT_RECORD)

SEMANTICS_FILE = "source_semantics.json"
RECORDS_FILE = "project_records.json"

_H = r"[\s\-‐\u2011–]*"
_NUM = r"(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d{2,6})(?![\d]|[.,]\d)"
_UNIT = (rf"(?:(?:female|male){_H}headed\s+households?|FHHs?|MHHs?|households?|HHs?|"
         rf"beneficiar(?:y|ies)|participants?)")
_AFTER = re.compile(rf"{_NUM}\s*(?:\(\s*)?(?:[A-Za-z\-\u2011]+\s+){{0,5}}?(?P<unit>{_UNIT})\b")
_BEFORE = re.compile(rf"(?P<unit>{_UNIT})\s+(?:was|were|is|are|of)\s+{_NUM}")
_BASELINE_CUE = re.compile(r"\b(?:in|at|during|from)\s+the\s+baseline\b|\bbaseline\s+(?:sample|"
                           r"value|figure|survey\s+sample)\b|\bat\s+baseline\b", re.I)
_TARGET_CUE = re.compile(r"\btargets?\b|\btargeted\b|\bat\s+least\b|%\s*=\s*$|=\s*$|\breceiving\b|"
                         r"to\s+be\s+achieved|\bplanned\b|\bproposed\s+number\b|\bexpected\s+to\b|"
                         r"\bwill\s+(?:reach|receive|benefit)", re.I)
_TARGET_AFTER = re.compile(r"^[^.]{0,60}?\b(?:receiving|report(?:s|ing)?|will\s+receive|targeted)\b|"
                           r"^\s*(?:hhs?\s+)?of\s+all\b", re.I)
_CASELOAD_CUE = re.compile(r"\bregist(?:ered|ration)\b|\benrolled\b|\bverified\b", re.I)
_TABLE_HEAD = re.compile(r"^\s*(?:indicators?\s+)?baseline\s+(?:values?\s+)?targets?\b", re.I | re.M)


def _num(s: str) -> int:
    return int(s.replace(",", ""))


def _label(unit: str) -> str:
    u = unit.lower()
    if u.startswith("female") or u.startswith("fhh"):
        return "FHH"
    if u.startswith("male") or u.startswith("mhh"):
        return "MHH"
    return "households"


def _table_regions(text: str) -> list:
    """[(start, end)] of indicator tables (a 'Baseline … Target' header, until prose)."""
    out = []
    for m in _TABLE_HEAD.finditer(text):
        pos, end = m.end(), min(len(text), m.end() + 8000)
        for line in re.finditer(r"[^\n]*\n?", text[pos:end]):
            if len(line.group(0).strip()) >= 85:
                end = pos + line.start()
                break
        out.append((m.start(), end))
    return out


def _window(text: str, s: int, e: int) -> tuple:
    before = text[max(0, s - 160):s]
    cut = max(before.rfind(". "), before.rfind(".\n"), before.rfind("\n\n"))
    before = before[cut + 1:] if cut >= 0 else before
    after = text[e:e + 100]
    cut = after.find(". ")
    after = after[:cut] if cut >= 0 else after
    return before, after


def scan_text(text: str) -> list:
    """Every household-figure mention in the TOR with its semantics and cue."""
    text = text or ""
    regions = _table_regions(text)
    found = {}
    for rx, gi in ((_AFTER, 1), (_BEFORE, 2)):
        for m in rx.finditer(text):
            g = m.group(gi)
            val = _num(g)
            if val < 10 or 1900 <= val <= 2100:
                continue
            s, e = m.start(gi), m.end(gi)
            if re.search(r"%[ \t]*\Z", text[max(0, s - 3):s]) or re.match(r"[ \t]*%", text[e:e + 3]):
                continue                                   # a percentage, not a count
            if (s, val) in found:
                continue
            before, after = _window(text, s, e)
            in_table = any(a <= s < b for a, b in regions)
            near_b, near_a = before[-120:], after[:80]
            if _BASELINE_CUE.search(near_b):
                sem, cue = OBSERVED_BASELINE, "baseline wording"
            elif in_table and (re.search(r"#\s*$", near_b) or re.match(r"^\s*HHs?\s*,\s*\d", after)):
                sem, cue = OBSERVED_BASELINE, "indicator table (baseline column)"
            elif _TARGET_CUE.search(near_b) or _TARGET_AFTER.search(near_a):
                sem, cue = TARGET, "target wording"
            elif _CASELOAD_CUE.search(before[-60:] + " " + after[:60]):
                sem, cue = REGISTERED_CASELOAD, "registered / verified wording"
            elif in_table:
                sem, cue = TARGET, "indicator table (target column)"
            else:
                sem, cue = TARGET, "TOR planning figure"
            found[(s, val)] = {"value": val, "label": _label(m.group("unit")), "semantics": sem,
                               "cue": cue,
                               "excerpt": " ".join((before[-80:] + g + after[:60]).split())[:180]}
    return [found[k] for k in sorted(found)]


# ---------------------------------------------------------------------------
# v0.6.15: table-column-aware semantics — a value in a recoverable TOR table inherits the
# role of its actual column (Baseline → OBSERVED_BASELINE, Target → TARGET); nearby
# target language never decides it
# ---------------------------------------------------------------------------

_COLUMN_ROLE = ((re.compile(r"\bbaseline\b", re.I), OBSERVED_BASELINE),
                (re.compile(r"\btargets?\b", re.I), TARGET))
# cues that come from position / nearby wording only — superseded by the table column
_WEAK_CUES = {"TOR planning figure", "target wording", "indicator table (target column)",
              "indicator table (baseline column)"}


def _figure_spans(text: str):
    """(value, label, start, end) household figures in a text (percentages skipped)."""
    seen = set()
    for rx, gi in ((_AFTER, 1), (_BEFORE, 2)):
        for m in rx.finditer(text or ""):
            g = m.group(gi)
            val = _num(g)
            s, e = m.start(gi), m.end(gi)
            if val < 10 or 1900 <= val <= 2100 or (s, val) in seen:
                continue
            if re.search(r"%[ \t]*\Z", text[max(0, s - 3):s]) or re.match(r"[ \t]*%", text[e:e + 3]):
                continue                    # a percentage on the same line, not a count
            seen.add((s, val))
            yield val, _label(m.group("unit")), s, e


def _column_mentions(column_texts: dict) -> list:
    out = []
    for (role, header), text in column_texts.items():
        for val, label, s, e in _figure_spans(text):
            out.append({"value": val, "label": label, "semantics": role,
                        "cue": f"TOR table: '{header}' column",
                        "excerpt": " ".join(text[max(0, s - 60):e + 40].split())[:180]})
    return out


def pdf_table_mentions(pdf_path) -> list:
    """Figures in PDF tables whose header names a Baseline and a Target column.

    pypdf's layout extraction keeps the horizontal position of every text run, so the
    column a value sits in is recoverable: a run belongs to the column whose span it lies
    in; a line with a run crossing a column boundary is prose and ends the table.
    """
    try:
        from pypdf import PdfReader
        pages = [p.extract_text(extraction_mode="layout") or "" for p in PdfReader(str(pdf_path)).pages]
    except Exception:
        return []
    cols, streams, out = None, {}, []

    def flush():
        nonlocal cols, streams
        if cols:
            out.extend(_column_mentions({k: "\n".join(v) for k, v in streams.items()}))
        cols, streams = None, {}

    for line in "\n".join(pages).splitlines():
        heads = [(m.start(), role, m.group(0)) for rx, role in _COLUMN_ROLE for m in rx.finditer(line)]
        if len(heads) == 2 and len(line.split()) <= 8 and heads[0][1] != heads[1][1]:
            flush()
            heads.sort()
            cols = heads                                   # [(start, role, header)…]
            streams = {(role, h): [] for _s, role, h in heads}
            continue
        if not cols or not line.strip():
            continue
        bounds = [s - 4 for s, _r, _h in cols]             # column spans start a little left
        runs = [(m.start(), m.end()) for m in re.finditer(r"\S+(?: \S+)*", line)]
        spans = [(0, bounds[0])] + [(bounds[i], bounds[i + 1] if i + 1 < len(bounds) else 10 ** 6)
                                    for i in range(len(bounds))]
        placed = []
        for a, b in runs:
            idx = next((i for i, (lo, hi) in enumerate(spans) if lo <= a and b <= hi + 2), None)
            if idx is None:
                placed = None
                break
            placed.append((idx, line[a:b]))
        if placed is None:                                 # a run crosses a column: prose
            flush()
            continue
        for idx, txt in placed:
            if idx >= 1:
                _s, role, h = cols[idx - 1]
                streams[(role, h)].append(txt)
    flush()
    return out


def cell_table_mentions(tables: list) -> list:
    """Figures in structured tables ([{rows: [[cell, …], …]}]) with Baseline / Target headers."""
    out = []
    for t in tables or []:
        rows = t.get("rows") or []
        if not rows:
            continue
        header = [str(c or "") for c in rows[0]]
        roles = {}
        for ci, h in enumerate(header):
            for rx, role in _COLUMN_ROLE:
                if rx.search(h) and not (rx.pattern.endswith("targets?\\b") and
                                         re.search(r"\bbaseline\b", h, re.I)):
                    roles[ci] = (role, h.strip())
                    break
        if not ({r for r, _h in roles.values()} >= {OBSERVED_BASELINE, TARGET}):
            continue
        texts = {}
        for row in rows[1:]:
            for ci, (role, h) in roles.items():
                if ci < len(row):
                    texts.setdefault((role, h), []).append(str(row[ci] or ""))
        out.extend(_column_mentions({k: "\n".join(v) for k, v in texts.items()}))
    return out


def build_register(text: str, *, records: Optional[list] = None,
                   table_mentions: Optional[list] = None) -> dict:
    by_val: dict = {}
    in_table = {m["value"] for m in table_mentions or []}
    for mnt in scan_text(text):
        if mnt["value"] in in_table and mnt["cue"] in _WEAK_CUES:
            continue                       # the recoverable table column decides (v0.6.15)
        f = by_val.setdefault(mnt["value"], {"value": mnt["value"], "labels": [], "mentions": []})
        if mnt["label"] not in f["labels"]:
            f["labels"].append(mnt["label"])
        f["mentions"].append({k: mnt[k] for k in ("semantics", "cue", "excerpt")})
    for mnt in table_mentions or []:
        f = by_val.setdefault(mnt["value"], {"value": mnt["value"], "labels": [], "mentions": []})
        if mnt["label"] not in f["labels"]:
            f["labels"].append(mnt["label"])
        f["mentions"].insert(0, {k: mnt[k] for k in ("semantics", "cue", "excerpt")})
    for r in records or []:
        try:
            val = int(str(r.get("value")).replace(",", ""))
        except (TypeError, ValueError):
            continue
        f = by_val.setdefault(val, {"value": val, "labels": [], "mentions": []})
        f["mentions"].append({"semantics": VERIFIED_PROJECT_RECORD, "cue": "project record",
                              "excerpt": f"{r.get('label', '')} — {r.get('source', '')}"[:180]})
    figures = []
    for val in sorted(by_val):
        f = by_val[val]
        sems = sorted({m["semantics"] for m in f["mentions"]})
        supported = bool({REGISTERED_CASELOAD, VERIFIED_PROJECT_RECORD} & set(sems))
        primary = next(s for s in (VERIFIED_PROJECT_RECORD, REGISTERED_CASELOAD, OBSERVED_BASELINE,
                                   TARGET) if s in sems)
        figures.append({"value": val, "label": "/".join(f["labels"]) or "households",
                        "semantics": sems, "primary": primary,
                        "registered_supported": supported, "mentions": f["mentions"][:6]})
    return {"schema": "source_semantics/1", "figures": figures}


def scan_blocks(blocks: list, *, records: Optional[list] = None,
                table_mentions: Optional[list] = None) -> dict:
    text = "\n".join((b.get("plain_text") or "") for b in blocks or [])
    return build_register(text, records=records, table_mentions=table_mentions)


def _load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_register(run_dir) -> dict:
    """The run's register, with VERIFIED_PROJECT_RECORD figures from project_records.json."""
    run_dir = Path(run_dir)
    reg = _load(run_dir / SEMANTICS_FILE) or {}
    recs = (_load(run_dir / RECORDS_FILE) or {}).get("records", [])
    if not recs:
        return reg
    figures = {f["value"]: f for f in reg.get("figures", [])}
    for r in recs:
        try:
            val = int(str(r.get("value")).replace(",", ""))
        except (TypeError, ValueError):
            continue
        f = figures.setdefault(val, {"value": val, "label": r.get("label", ""), "semantics": [],
                                     "primary": VERIFIED_PROJECT_RECORD, "mentions": []})
        if VERIFIED_PROJECT_RECORD not in f["semantics"]:
            f["semantics"] = sorted(set(f["semantics"]) | {VERIFIED_PROJECT_RECORD})
        f["primary"] = VERIFIED_PROJECT_RECORD
        f["registered_supported"] = True
        f.setdefault("mentions", []).append({"semantics": VERIFIED_PROJECT_RECORD,
                                             "cue": "project record",
                                             "excerpt": f"{r.get('label', '')} — {r.get('source', '')}"})
    return {**reg, "figures": [figures[v] for v in sorted(figures)]}


def record_project_figure(run_dir, value: int, label: str, source: str) -> dict:
    """Record a figure confirmed from a project record (e.g. the registration list)."""
    p = Path(run_dir) / RECORDS_FILE
    doc = _load(p) or {"records": []}
    doc["records"] = [r for r in doc["records"] if str(r.get("value")) != str(value)]
    doc["records"].append({"value": int(value), "label": label, "source": source})
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return doc


# ---------------------------------------------------------------------------
# Proposal text: "registered" wording and provisional stratum allocations
# ---------------------------------------------------------------------------

_DRAFT_NUM = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d{2,6})(?![\d]|[.,]\d)")
_REGISTERED = re.compile(r"\bregistered\b", re.I)
_REG_PHRASE = re.compile(r"\bregistered(?=\s+(?:[\w\-‑]+\s+){0,2}?(?:households?|hhs?|caseload|"
                         r"participants?|beneficiar\w*|fhhs?|mhhs?)\b)", re.I)
_ALLOC_HEAD = re.compile(r"\b(?:proposed\s+sample|sample(?:\s+size)?|allocation|planned\s+sample|"
                         r"interviews?)\b", re.I)
_ALLOC_SENT = re.compile(r"\b(?:split|allocat\w*|proportional\w*|stratif\w*)\b", re.I)
_PROVISIONAL_NOTE = re.compile(r"\bprovisional\w*\b[\s\S]{0,250}?\binception\b|\binception\b"
                               r"[\s\S]{0,250}?\bprovisional\w*\b", re.I)
_RECALC = re.compile(r"\b(?:recalculat\w*|re-?calculat\w*|re-?computed|updated|adjusted|confirmed)\b"
                     r"[^.]{0,120}\bregistration\s+(?:list|data|records?)\b|\bregistration\s+"
                     r"(?:list|data|records?)\b[^.]{0,120}\b(?:recalculat\w*|re-?calculat\w*)", re.I)
_SENT = re.compile(r"(?:[^.;!?\n]|(?<=\b[A-Z])\.|\.(?=\d))*(?:[.;!?\n]|$)")
_TARGET_STATEMENT = re.compile(r"\bat\s+least\b|\d\s*%|\btargets?\b|\bpost[\s\-‑]?distribution\b",
                               re.I)


def _figures(register: dict) -> dict:
    return {f["value"]: f for f in (register or {}).get("figures", [])}


def _target_only(register: dict) -> set:
    return {v for v, f in _figures(register).items()
            if TARGET in f.get("semantics", []) and not f.get("registered_supported")}


def _nums(text: str) -> set:
    return {_num(n) for n in _DRAFT_NUM.findall(text or "")}


def _stratum_label(cell: str) -> str:
    low = (cell or "").lower()
    if re.search(rf"female{_H}headed|\bfhh", low):
        return "FHH"
    if re.search(rf"male{_H}headed|\bmhh", low):
        return "MHH"
    return " ".join(str(cell or "").split())[:40]


def _section_has_note(candidate: dict) -> bool:
    from .claim_language import candidate_texts
    text = " ".join(t for _p, t in candidate_texts(candidate))
    return bool(_PROVISIONAL_NOTE.search(text) and _RECALC.search(text))


def find_population_issues(candidate: dict, register: dict, *, section_id: str = "") -> list:
    """[{kind, sentence, detail, values, rewritable, path}] (no mutation)."""
    target = _target_only(register)
    if not target:
        return []
    from .claim_language import candidate_texts
    issues = []
    for path, text in candidate_texts(candidate):
        for s in _SENT.finditer(text or ""):
            sent = s.group(0)
            vals = _nums(sent) & target
            # a target statement reproduced from the TOR ("At least 80% (1,040 HH) of
            # registered participant households …") uses 'registered' for the base
            # population, not as a claim that the target figure is a registered caseload
            if vals and _REG_PHRASE.search(sent) and not _TARGET_STATEMENT.search(sent):
                issues.append({"kind": "REGISTERED_TARGET_FIGURE", "section_id": section_id,
                               "sentence": sent.strip()[:200], "values": sorted(vals),
                               "rewritable": True, "path": list(path),
                               "detail": (f"{', '.join(map(str, sorted(vals)))} "
                                          f"{'is a' if len(vals) == 1 else 'are'} TOR TARGET "
                                          "figure(s), not a registered caseload")})
            if vals and _ALLOC_SENT.search(sent) and not _section_has_note(candidate):
                issues.append({"kind": "ALLOCATION_NOT_PROVISIONAL", "section_id": section_id,
                               "sentence": sent.strip()[:200], "values": sorted(vals),
                               "rewritable": True, "path": list(path),
                               "detail": "stratum allocation derived from the TOR target "
                                         "composition is not marked provisional"})
    for bi, b in enumerate(candidate.get("blocks", [])):
        if b.get("type") != "table":
            continue
        cols = [str(c) for c in b.get("columns") or []]
        rows = b.get("rows") or []
        tcols = [ci for ci in range(len(cols))
                 if any(ci < len(r) and _nums(str(r[ci])) & target for r in rows)]
        if not tcols:
            continue
        for ci in tcols:
            if _REGISTERED.search(cols[ci]):
                vals = sorted({v for r in rows if ci < len(r) for v in _nums(str(r[ci])) & target})
                issues.append({"kind": "REGISTERED_TARGET_FIGURE", "section_id": section_id,
                               "sentence": cols[ci], "values": vals, "rewritable": True,
                               "path": [bi, "column", ci],
                               "detail": f"column '{cols[ci]}' labels TOR TARGET figures "
                                         f"{vals} as registered"})
        acols = [ci for ci, c in enumerate(cols) if ci not in tcols and _ALLOC_HEAD.search(c)]
        if acols and (not all(re.search(r"provisional", cols[ci], re.I) for ci in acols)
                      or not _section_has_note(candidate)):
            issues.append({"kind": "ALLOCATION_NOT_PROVISIONAL", "section_id": section_id,
                           "sentence": " | ".join(cols), "values": [], "rewritable": True,
                           "path": [bi, "table"],
                           "detail": "sample allocation derived from the TOR target composition is "
                                     "not marked provisional / recalculated at inception"})
    return issues


def _allocation_text(block: dict, target: set) -> str:
    cols = [str(c) for c in block.get("columns") or []]
    tcol = next((ci for ci in range(len(cols)) if any(ci < len(r) and _nums(str(r[ci])) & target
                                                      for r in block.get("rows") or [])), None)
    acol = next((ci for ci, c in enumerate(cols) if ci != tcol and _ALLOC_HEAD.search(c)), None)
    if tcol is None or acol is None:
        return ""
    parts = []
    for r in block.get("rows") or []:
        if len(r) <= max(tcol, acol) or not (_nums(str(r[tcol])) & target):
            continue
        if re.search(r"\b(?:all|total)\b", str(r[0]), re.I):
            continue
        n = _DRAFT_NUM.search(str(r[acol]))
        if n:
            parts.append(f"{n.group(1)} {_stratum_label(str(r[0]))}")
    return " / ".join(parts)


def sanitize_population(candidate: dict, register: dict, *, section_id: str = "") -> tuple:
    """Deterministic rewrites (in a copy): returns (candidate, changes)."""
    import copy
    from .claim_state import SAFE_WORDING
    target = _target_only(register)
    issues = find_population_issues(candidate, register, section_id=section_id)
    if not issues:
        return candidate, []
    cand = copy.deepcopy(candidate)
    changes, note_needed, after_block = [], False, None
    for it in issues:
        path = it["path"]
        if it["kind"] == "REGISTERED_TARGET_FIGURE" and path[1] == "column":
            b = cand["blocks"][path[0]]
            old = b["columns"][path[2]]
            b["columns"][path[2]] = "TOR target composition"
            changes.append({**it, "replacement": "TOR target composition", "original": old})
        elif it["kind"] == "REGISTERED_TARGET_FIGURE":
            bi, ii, ci = path
            b = cand["blocks"][bi]
            cur = (b["text"] if ii is None else b["items"][ii] if ci is None else b["rows"][ii][ci])
            new = _REG_PHRASE.sub(lambda m: "target" if m.group(0).islower() else "Target", str(cur))
            if new != cur:
                if ii is None:
                    b["text"] = new
                elif ci is None:
                    b["items"][ii] = new
                else:
                    b["rows"][ii][ci] = new
                changes.append({**it, "replacement": new[:200]})
        elif it["kind"] == "ALLOCATION_NOT_PROVISIONAL":
            note_needed = True
            if path[1] == "table":
                b = cand["blocks"][path[0]]
                after_block = path[0] if after_block is None else after_block
                for ci, c in enumerate(b.get("columns") or []):
                    if _ALLOC_HEAD.search(str(c)) and not re.search(r"provisional", str(c), re.I) and \
                            not any(ci < len(r) and _nums(str(r[ci])) & target for r in b["rows"]):
                        b["columns"][ci] = "Provisional allocation"
                        changes.append({**it, "replacement": "Provisional allocation",
                                        "original": str(c)})
            elif after_block is None:
                after_block = path[0]
    if note_needed and not _section_has_note(cand):
        alloc = ""
        for b in cand.get("blocks", []):
            if b.get("type") == "table":
                alloc = alloc or _allocation_text(b, target)
        note = SAFE_WORDING["target_allocation"].format(
            allocation=alloc or "stratum sizes proportional to the TOR target figures")
        pos = (after_block if after_block is not None else len(cand["blocks"]) - 1) + 1
        cand["blocks"].insert(pos, {"block_id": f"{section_id or 'sec'}_alloc_note",
                                    "type": "paragraph", "text": note})
        changes.append({"kind": "ALLOCATION_NOT_PROVISIONAL", "section_id": section_id,
                        "sentence": "", "replacement": note, "rewritable": True,
                        "detail": "provisional-allocation note added"})
    return cand, changes
