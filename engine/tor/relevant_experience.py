"""Relevant-experience selection from the Master Tracker (v0.6.17).

The TOR asks for examples of previous assignments; ARFADA's Master Tracker records them.
This module ranks the tracker for THIS TOR and selects the 3–5 closest assignments
automatically, with tracker provenance. It is a separate concept from
PREVIOUS_WORK_SELECTED (the actual report file offered as a work sample).

Score (transparent, recorded per assignment in ``scored_on``):
  stage        same evaluation stage (endline / final evaluation)  4, evaluation family 2
  themes       TOR themes in the project's sectors (food security, voucher / cash …)  ≤ 4
  country      same country  3
  location     TOR region / places in the project record  3   (never inferred)
  client       same client  3
  methods      household survey + KIIs / FGDs on record  ≤ 2
  recency      year in the project id: last 2 years 2, 3 years ago 1

Ties are broken deterministically (score, same country, recency, stage, survey volume).
A FAST question is raised only for a genuine tie at the cut-off between strategically
different assignments (different country or client), or when fewer than 3 qualify.
No experience is invented: if the tracker records no assignment in the TOR's location,
the selection says so.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path
from typing import Optional

FILE = "relevant_experience.json"
AUTO_SELECTED, USER_SELECTED = "AUTO_SELECTED", "USER_SELECTED"
NEEDS_DECISION, INSUFFICIENT = "NEEDS_DECISION", "INSUFFICIENT"
MIN_SCORE = 6
_THEMES = {   # theme -> (TOR / sector regex, weight)
    "food security": (r"food\s+secur|\bfsl\b|food\s+assistance|food\s+consumption|hunger", 2),
    "voucher / cash": (r"voucher|\bcash\b|\bcva\b|\bmpca\b|e-?voucher", 2),
    "livelihoods": (r"livelihood", 1),
    "nutrition": (r"nutrition", 1),
    "protection": (r"protection|\bgbv\b|safeguard", 1),
    "agriculture": (r"agricultur", 1),
}
_STAGE = {"ENDLINE": r"endline|end\s*line|final\s+evalu|final\s+external",
          "FINAL_EVALUATION": r"endline|end\s*line|final\s+evalu|final\s+external",
          "BASELINE": r"baseline", "MIDTERM": r"mid[-\s]?term|mid\s+evalu"}


def _year(p: dict) -> Optional[int]:
    m = re.match(r"^\s*\d{1,4}-(\d{4})-", str(p.get("project_id") or ""))
    return int(m.group(1)) if m else None


def _tor_profile(tor: dict, requirements: list) -> dict:
    meta = (tor or {}).get("metadata", {}) or {}
    mv = lambda k: (meta.get(k) or {}).get("value", "") if isinstance(meta.get(k), dict) else ""
    text = " ".join([mv("assignment"), mv("title"), mv("sector")] +
                    [str(r.get("text") or "") for r in requirements or []])
    themes = [t for t, (rx, _w) in _THEMES.items() if re.search(rx, text, re.I)]
    places = list(((meta.get("subnational_location") or {}).get("values") or [])) \
        if isinstance(meta.get("subnational_location"), dict) else []
    # a wider region named inside a place ("South Darfur" → "Darfur")
    regions = sorted({w for p in places for w in re.findall(r"[A-Z][a-z]{3,}", p)} - {"South", "North",
                                                                                    "East", "West", "Central"})
    at = (tor.get("assignment_type") or {}).get("assignment_type", "")
    return {"themes": themes, "country": mv("country"), "client": mv("client"),
            "places": places, "regions": regions, "assignment_type": at,
            "title": mv("assignment") or mv("title"),
            "needs_survey": bool(re.search(r"household\s+survey|\bsurvey", text, re.I)),
            "needs_qual": bool(re.search(r"\bfgds?\b|focus\s+group|\bkiis?\b|key\s+informant", text, re.I))}


def score_project(p: dict, prof: dict, *, this_year: int) -> tuple:
    why = {}
    name = " ".join(str(p.get(k) or "") for k in ("project_name", "project_id"))
    stage = _STAGE.get(prof["assignment_type"])
    if stage and re.search(stage, name, re.I):
        why["stage"] = 4
    elif p.get("assignment_type") == "EVALUATION":
        why["evaluation_family"] = 2
    sector = str(p.get("sector") or "")
    th = [t for t in prof["themes"] if re.search(_THEMES[t][0], sector, re.I)]
    if th:
        why["themes"] = min(4, sum(_THEMES[t][1] for t in th))
    if prof["country"] and str(p.get("country") or "").strip().lower() == prof["country"].lower():
        why["country"] = 3
    loc = " ".join(str(p.get(k) or "") for k in ("region", "project_name", "description"))
    if any(re.search(rf"\b{re.escape(x)}\b", loc, re.I) for x in prof["places"] + prof["regions"]):
        why["location"] = 3
    if prof["client"] and prof["client"].lower() in " ".join(
            str(p.get(k) or "") for k in ("client", "donor")).lower():
        why["client"] = 3
    m = 0
    if prof["needs_survey"] and (p.get("surveys") or 0) > 0:
        m += 1
    if prof["needs_qual"] and ((p.get("kii") or 0) > 0 or (p.get("fgd") or 0) > 0):
        m += 1
    if m:
        why["methods"] = m
    y = _year(p)
    if y and this_year - y <= 1:
        why["recency"] = 2
    elif y and this_year - y == 2:
        why["recency"] = 1
    return sum(why.values()), why, th


def _is_current(p: dict, prof: dict) -> bool:
    """The assignment this TOR is for (never cited as past experience)."""
    title = prof.get("title") or ""
    if not title:
        return False
    toks = {t for t in re.findall(r"[a-z]{4,}", title.lower())} - {"evaluation", "final", "project",
                                                                 "support", "endline", "baseline"}
    hay = " ".join(str(p.get(k) or "") for k in ("project_name", "description")).lower()
    hit = sum(1 for t in toks if t in hay)
    return bool(toks) and hit >= max(2, int(0.6 * len(toks))) and \
        str(p.get("country") or "").lower() == (prof.get("country") or "").lower()


def _entry(p: dict, s: int, why: dict, themes: list) -> dict:
    stage = ("Final / endline evaluation" if "stage" in why else
             str(p.get("assignment_type") or "Assignment").title())
    client = str(p.get("client") or "").split(" - ")[0].strip()
    reason = stage
    if "country" in why:
        reason += f" in {p.get('country')}"
    if "client" in why and client:
        reason += f" for {client}"
    if themes:
        reason += " covering " + (", ".join(themes[:-1]) + " and " + themes[-1] if len(themes) > 1
                                  else themes[0])
    return {"project_id": p.get("project_id"), "project_name": p.get("project_name"),
            "client": p.get("client"), "donor": p.get("donor"), "country": p.get("country"),
            "assignment_type": p.get("assignment_type"), "sector": p.get("sector"),
            "year": _year(p), "surveys": p.get("surveys"), "kii": p.get("kii"), "fgd": p.get("fgd"),
            "score": s, "scored_on": why, "relevance": reason,
            "provenance": {"source": "Master Tracker", "file": p.get("source_sheet") or "",
                           "row": p.get("source_row"), "fact_id": p.get("fact_id") or p.get("project_id")}}


def select(projects: list, tor: dict, requirements: list, *, limit: int = 5,
           today: Optional[_dt.date] = None) -> dict:
    prof = _tor_profile(tor, requirements)
    this_year = (today or _dt.date.today()).year
    ranked = []
    for p in projects or []:
        if _is_current(p, prof):
            continue
        s, why, th = score_project(p, prof, this_year=this_year)
        if s >= MIN_SCORE:
            ranked.append((s, p, why, th))
    key = lambda x: (-x[0], -("country" in x[2]), -(_year(x[1]) or 0), -("stage" in x[2]),
                     -(x[1].get("surveys") or 0))
    ranked.sort(key=key)
    cands = [_entry(p, s, w, th) for s, p, w, th in ranked[:12]]
    notes = []
    if prof["places"] and not any("location" in c["scored_on"] for c in cands):
        notes.append("The Master Tracker records no ARFADA assignment in " +
                     ", ".join(prof["places"][:3]) + "; none is claimed.")
    if len(cands) < 3:
        return {"status": INSUFFICIENT, "selected": cands, "candidates": cands, "notes": notes,
                "question": None, "tor_profile": prof}
    n = min(limit, len(cands))
    selected = cands[:n]
    question = None
    if len(ranked) > n and key(ranked[n - 1]) == key(ranked[n]):
        a, b = ranked[n - 1][1], ranked[n][1]
        if (a.get("country"), a.get("client")) != (b.get("country"), b.get("client")):
            tied = [c for c, r in zip(cands, ranked[:12]) if key(r) == key(ranked[n - 1])]
            question = {"key": "relevant_experience",
                        "question": "Two or more past assignments are equally relevant — which "
                                    "should be featured?",
                        "options": [f"{c['project_id']} · {c['client']}" for c in tied][:6],
                        "record": "run_decision.py <run_dir> relevant-experience \"<id>,<id>,…\"",
                        "reason": "A genuine tie at the cut-off between assignments in different "
                                  "countries / for different clients."}
    return {"status": NEEDS_DECISION if question else AUTO_SELECTED, "selected": selected,
            "candidates": cands, "notes": notes, "question": question, "tor_profile": prof}


def write(run_dir, result: dict) -> dict:
    doc = {**result, "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat()}
    doc.pop("tor_profile", None)
    (Path(run_dir) / FILE).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return doc


def load(run_dir) -> Optional[dict]:
    p = Path(run_dir) / FILE
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except Exception:
        return None


def override(run_dir, project_ids: list, *, note: str = "") -> dict:
    """The employee's own choice of 3–5 assignments (from the ranked candidates)."""
    doc = load(run_dir)
    if not doc:
        return {"ok": False, "status": "NO_RANKING", "message": "Run fast_proposal.py setup first."}
    by_id = {c["project_id"]: c for c in doc.get("candidates", [])}
    ids = [i.strip() for i in project_ids if i.strip()]
    unknown = [i for i in ids if i not in by_id]
    if unknown or not 3 <= len(ids) <= 5:
        return {"ok": False, "status": "INVALID",
                "message": "Choose 3–5 assignments from the ranked candidates "
                           f"(unknown: {unknown})" if unknown else "Choose 3–5 assignments."}
    doc.update({"status": USER_SELECTED, "selected": [by_id[i] for i in ids], "question": None,
                "user_note": note[:300]})
    (Path(run_dir) / FILE).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "status": USER_SELECTED, "selected": ids}


def resolved(doc: Optional[dict]) -> bool:
    return bool(doc) and doc.get("status") in (AUTO_SELECTED, USER_SELECTED) and \
        3 <= len(doc.get("selected") or []) <= 5


# ---------------------------------------------------------------------------
# client-facing table (from tracker records only)
# ---------------------------------------------------------------------------

TABLE_COLUMNS = ["Assignment (ARFADA project record)", "Client", "Country", "Year",
                 "Relevance to this TOR"]
# only a placeholder for SELECTING / FEATURING relevant assignments — never another evidence gap
# (e.g. "firm-level record of ARFADA assignments in South Darfur" stays an honest gap)
_PLACEHOLDER = re.compile(
    r"NEEDS_ARFADA_EVIDENCE[^\n]{0,400}?(?:relevant\s+(?:assignments?|experience|projects?)|"
    r"featured\s+(?:relevant\s+)?(?:past\s+)?(?:assignments?|projects?)|"
    r"(?:select\w*|choose|choice)\s+(?:of\s+)?(?:\d\s*[–-]\s*\d\s+)?(?:featured\s+)?(?:relevant\s+)?"
    r"(?:past\s+)?(?:assignments?|projects?))", re.I)


def table_block(doc: dict, block_id: str = "rel_exp") -> dict:
    rows = []
    for c in doc.get("selected") or []:
        # client-facing: the tracker's assignment name (the tracker id stays in provenance)
        rows.append([c.get("project_name") or "", c.get("client") or "",
                     c.get("country") or "", str(c.get("year") or ""), c.get("relevance") or ""])
    return {"block_id": block_id, "type": "table", "columns": list(TABLE_COLUMNS), "rows": rows}


def is_placeholder(block: dict) -> bool:
    text = str(block.get("text") or "") if block.get("type") in ("paragraph", "evidence_placeholder") else ""
    return bool(_PLACEHOLDER.search(text))


def apply_selection(candidate: dict, doc: Optional[dict], *, section_id: str = "") -> tuple:
    """Replace a relevant-experience placeholder with the tracker-backed table (copy)."""
    if not resolved(doc):
        return candidate, []
    blocks = candidate.get("blocks", [])
    idx = [i for i, b in enumerate(blocks) if is_placeholder(b)]
    if not idx:
        return candidate, []
    import copy
    cand = copy.deepcopy(candidate)
    i = idx[0]
    intro = {"block_id": "rel_exp_intro", "type": "paragraph",
             "text": "The assignments below, drawn from ARFADA's project records, are the closest "
                     "to this evaluation in type, sector and setting."}
    cand["blocks"][i:i + 1] = [intro, table_block(doc)]
    for j in sorted(idx[1:], reverse=True):
        del cand["blocks"][j + 1]
    return cand, [{"kind": "RELEVANT_EXPERIENCE_TABLE", "section_id": section_id,
                   "sentence": str(blocks[i].get("text", ""))[:200],
                   "replacement": f"{len(doc['selected'])} tracker-backed assignments",
                   "rewritable": True, "detail": "placeholder replaced by the selected assignments"}]


def presented(sections: dict, doc: Optional[dict]) -> int:
    """How many selected assignments the proposal text names (by client + name / id)."""
    if not resolved(doc):
        return 0
    from .response_coverage import block_text
    text = " ".join(block_text(b) for s in (sections or {}).values() for b in s.get("blocks", [])).lower()
    n = 0
    for c in doc["selected"]:
        cid = str(c.get("project_id") or "").lower()
        client = str(c.get("client") or "").split(" - ")[0].strip().lower()
        if (cid and cid in text) or (client and client in text and
                                     str(c.get("country") or "").lower() in text):
            n += 1
    return n
