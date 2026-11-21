"""Role-specific staff ranking for the TOR's team roles (v0.6.12).

The generic nomination score ranks "a good CV for this TOR". Proposal teams are
built per ROLE, so each TOR role gets its own ``role_fit_score`` from evidence only:

  evidence text of the CV (stored snippets)          full weight  (VERIFIED)
  ARFADA's filing (folders) and the CV file name      half weight  (PROVISIONAL)
  parsed role titles                                  only for "has held this role"
  nothing else — sector expertise is never inferred from a job title

Roles: TEAM_LEADER · FSL · GENDER_PROTECTION · DATA_ANALYST · FIELD_COORDINATOR,
detected from the TOR's team requirements (a Team Leader is always included once
any role is required). SUPPORTING_DOCUMENT stays ineligible (nominate excludes it).
"""
from __future__ import annotations

import re
from pathlib import PurePath
from typing import Optional

ROLE_ORDER = ["TEAM_LEADER", "FSL", "GENDER_PROTECTION", "DATA_ANALYST", "FIELD_COORDINATOR"]
ROLE_LABEL = {"TEAM_LEADER": "Team Leader", "FSL": "Food Security & Livelihoods Specialist",
              "GENDER_PROTECTION": "Gender, Protection & Safeguarding Specialist",
              "DATA_ANALYST": "Data Analyst / Statistician",
              "FIELD_COORDINATOR": "Field Coordinator"}
ROLE_CUES = {
    "TEAM_LEADER": r"team\s+leader|lead\s+(?:evaluator|consultant|researcher)|evaluation\s+lead|"
                   r"principal\s+investigator",
    "FSL": r"food\s+security|\bfsl\b|livelihood|food\s+assistance|voucher|\bcash\b",
    "GENDER_PROTECTION": r"gender|protection|safeguard|\bpsea\b|\bseah?\b|\bgbv\b",
    "DATA_ANALYST": r"data\s+analys|statistic|sampling|survey\s+design|quantitative\s+analysis",
    "FIELD_COORDINATOR": r"field\s+(?:coordinator|supervisor|work|team|operations)|operat\w*\s+"
                         r"environment|local\s+context|data\s+collection\s+team|enumerators?",
}
# role -> [(criterion, regex, weight, title_ok)]  title_ok: parsed role titles count
_CRITERIA = {
    "TEAM_LEADER": [
        ("leadership", r"team\s+leader|lead\s+evaluator|evaluation\s+lead|principal\s+investigator|"
                       r"\bled\b[^.]{0,30}evaluation", 10, True),
        ("evaluation", r"evaluat|\bmeal\b|m\s*&\s*e|base-?\s?line|end-?\s?line", 8, False),
        ("insecure_context", r"conflict|fragile|insecur|humanitarian|crisis|emergenc", 4, False),
        ("mixed_methods", r"mixed[- ]methods?|qualitative\s+and\s+quantitative|"
                          r"quantitative\s+and\s+qualitative", 3, False),
    ],
    "FSL": [
        ("food_security", r"food\s+security|\bfsl\b|livelihood", 6, False),
        ("vouchers_cash", r"voucher|\bcash\b|\bcva\b|\bmpca\b|cash[- ]based|\bcbi\b", 5, False),
        ("fsl_indicators", r"\bfcs\b|food\s+consumption|rcsi|coping\s+strateg|\bhhs\b|hunger\s+scale", 5, False),
        ("fsl_assessment", r"(?:food\s+security|fsl|livelihood)[^.]{0,40}(?:assessment|evaluation|survey)|"
                           r"(?:assessment|evaluation|survey)[^.]{0,40}(?:food\s+security|fsl)", 4, False),
        ("market_analysis", r"market\s+(?:analysis|assessment|monitoring|systems?)", 4, False),
    ],
    "GENDER_PROTECTION": [
        ("safeguarding", r"safeguard", 5, False),
        ("protection", r"protection", 5, False),
        ("gender", r"\bgender\b|\bgesi\b", 5, False),
        ("psea_seah_gbv", r"\bpsea\b|\bseah?\b|sea[- ]sh|\bgbv\b|sexual\s+exploitation", 5, False),
    ],
    "DATA_ANALYST": [
        ("statistics", r"statistic", 5, True),
        ("sampling", r"sampl", 4, False),
        ("stats_software", r"\bspss\b|\bstata\b|\br\s+studio\b|\brstudio\b|\bin\s+r\b", 5, False),
        ("kobo_odk", r"\bkobo|\bodk\b", 4, False),
        ("evaluation_analysis", r"data\s+analy|evaluation\s+analysis|quantitative\s+analysis", 3, True),
    ],
    "FIELD_COORDINATOR": [
        ("field_operations", r"field\s+(?:operations|coordinat\w*|work|team|supervis\w*)|supervis|"
                             r"operations\s+manager|head\s+of\s+(?:sub-?)?office", 5, True),
        ("access_liaison", r"\baccess\b|liaison|security|coordination\s+with|local\s+authorit", 3, False),
        ("modality", r"voucher|distribution|\bcash\b|redemption", 3, False),
    ],
}
_GEO_WEIGHT = {"FIELD_COORDINATOR": 8, "TEAM_LEADER": 6, "GENDER_PROTECTION": 3}


def detect_roles(requirements: Optional[list]) -> list:
    """TOR team roles, in canonical order (Team Leader first once any role is named)."""
    text = " ".join(str(r.get("text") or "") for r in requirements or []
                    if isinstance(r, dict) and r.get("category") == "team").lower()
    roles = [r for r in ROLE_ORDER if re.search(ROLE_CUES[r], text, re.I)]
    if roles and "TEAM_LEADER" not in roles:
        roles.insert(0, "TEAM_LEADER")
    return roles


def _texts(p: dict) -> tuple[str, str, str]:
    ev = p.get("evidence") or {}
    snippets = " ".join(str(v) for v in ev.values()) if isinstance(ev, dict) else ""
    # CV-text role evidence of shortlisted candidates (VERIFIED, full weight)
    snippets = " ".join([snippets] + list(p.get("role_evidence") or []))
    rel = str(p.get("source_rel_path") or "").replace("\\", "/")
    parts = PurePath(rel).parts
    filing = " ".join(list(parts[1:-1]) + [str(p.get("source_file_name") or (parts[-1] if parts else ""))])
    roles = " ".join(p.get("roles") or [])
    return snippets, filing, roles


def role_fit_score(p: dict, role: str, ctx: dict) -> tuple[float, dict]:
    """Evidence-only fit of one profile for one TOR role (with a breakdown)."""
    from .staff_country import matches_country
    from .staff_nominate import _THEMES, _lead_eligibility
    snippets, filing, roles = _texts(p)
    b: dict = {}

    def credit(name, pat, w, title_ok=False):
        if snippets and re.search(pat, snippets, re.I):
            b[name] = w
        elif title_ok and roles and re.search(pat, roles, re.I):
            b[name] = w
        elif filing and re.search(pat, filing, re.I):
            b[name] = w / 2

    for name, pat, w, title_ok in _CRITERIA[role]:
        credit(name, pat, w, title_ok)
    # sector evaluation experience relevant to the TOR's themes (Team Leader)
    if role == "TEAM_LEADER":
        themes = [t for t in (ctx.get("themes") or []) if t in _THEMES]
        if themes:
            credit("sector", "|".join(_THEMES[t] for t in themes), 6)
    # country / regional relevance: CV text (full), ARFADA filing (half), expert pool
    country = ctx.get("country") or ""
    if country and snippets and re.search(re.escape(country), snippets, re.I):
        b["country"] = 6
    elif country and matches_country(p, country):
        b["country"] = 3
    elif p.get("country_pool"):
        b["country"] = 1
    places = sorted(ctx.get("places") or [])
    if places and role in _GEO_WEIGHT:
        credit("geography", "|".join(re.escape(x) for x in places), _GEO_WEIGHT[role])
    # TOR-specific eligibility (lead years) — only structured, evidenced years count
    if role == "TEAM_LEADER":
        elig = _lead_eligibility(p, ctx)
        if elig == "MEETS":
            b["eligibility"] = 6
        elif elig == "FAILS":
            b["eligibility"] = -10
    if p.get("document_type") == "UNKNOWN":
        b["document_unclear"] = -5
    return round(sum(b.values()), 1), b


def assign_roles(candidates: list, roles: list, ctx: dict, *, top: int = 3) -> dict:
    """Best distinct person per role (Team Leader first) + the top alternatives per role."""
    from .staff_identity import same_person
    shortlist: dict = {}
    for role in roles:
        scored = []
        for c in candidates:
            s, br = role_fit_score(c, role, ctx)
            scored.append({**c, "role": role, "role_fit_score": s, "role_fit_breakdown": br})
        scored.sort(key=lambda x: (-x["role_fit_score"], -(x.get("nomination_score") or 0)))
        shortlist[role] = scored
    picks, used = {}, []
    for role in roles:
        for c in shortlist[role]:
            if c["role_fit_score"] <= 0:
                break
            if not any(same_person(c, u) for u in used):
                picks[role] = c
                used.append(c)
                break
    return {"picks": picks, "shortlist": {r: v[:top] for r, v in shortlist.items()},
            "ranked": shortlist}


CLOSE_MARGIN = 3
WEAK_FIT = 12


def role_team_question(tl_ranked: list, ctx: dict) -> tuple[bool, str]:
    """Team-lead question on ROLE fit (not the generic score)."""
    from .staff_nominate import _lead_eligibility
    cvs = [c for c in tl_ranked if c.get("document_type") == "CV"]
    if not cvs:
        return True, "No indexed document is clearly a CV — confirm the team lead."
    top = cvs[0]
    elig = _lead_eligibility(top, ctx)
    if elig in ("UNKNOWN", "FAILS"):
        need = ctx.get("lead_min_years")
        state = "cannot be confirmed" if elig == "UNKNOWN" else "is not met"
        return True, (f"Mandatory requirement ({need}+ years for the team leader) {state} for "
                      f"the top candidate — confirm the team lead.")
    if top["role_fit_score"] < WEAK_FIT:
        return True, "Evidence for the top Team Leader candidate is weak — confirm the team lead."
    if len(cvs) >= 2 and top["role_fit_score"] - cvs[1]["role_fit_score"] <= CLOSE_MARGIN:
        return True, "Top two Team Leader candidates are closely ranked — confirm the lead."
    return False, ""


# ---------------------------------------------------------------------------
# role evidence from the CV text of SHORTLISTED candidates (cached, snippets only)
# ---------------------------------------------------------------------------

import json as _json
import time as _time

_EVIDENCE_FILE = "role_evidence.json"
_EVIDENCE_VERSION = 2          # bump when the extraction rule changes
_ALL_CUES = re.compile("|".join(
    [p for crit in _CRITERIA.values() for _n, p, _w, _t in crit] +
    [r"sudan|darfur|nyala|syria|iraq|jordan|lebanon|yemen|afghanistan|turkey|libya|palestin"]),
    re.I)


def _cache_path():
    from ..gknowledge.cache import Cache
    return Cache().base / _EVIDENCE_FILE


def _load_cache() -> dict:
    try:
        p = _cache_path()
        return _json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    try:
        p = _cache_path()
        tmp = p.with_suffix(".tmp")
        tmp.write_text(_json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    except Exception:
        pass


def extract_role_evidence(text: str, *, limit: int = 80) -> list:
    """Sentences of a CV that carry role evidence (never the full CV text)."""
    out = []
    for s in re.split(r"(?<=[.;!?])\s+|\n+", text or ""):
        s = " ".join(s.split())
        if 20 <= len(s) and _ALL_CUES.search(s):
            out.append(s[:240])
            if len(out) >= limit:
                break
    return out


def attach_role_evidence(candidates: list, *, budget_s: float = 120.0,
                         knowledge_root=None) -> dict:
    """Add ``role_evidence`` (CV-text snippets) to shortlisted candidates in place.

    Reads only these candidates' own CV files (when reachable locally), caches the
    snippets by file modification time, and stops at the time budget. Returns stats.
    """
    from .staff_pool import cv_file_for
    from .scan import _extract_text
    cache = _load_cache()
    t0, read, cached, missing = _time.time(), 0, 0, 0
    changed = False
    for c in candidates:
        sid = c.get("staff_id")
        f = cv_file_for(c, knowledge_root)
        if f is None:
            missing += 1
            continue
        try:
            mtime = str(f.stat().st_mtime)
        except Exception:
            missing += 1
            continue
        hit = cache.get(sid)
        if hit and hit.get("mtime") == mtime and hit.get("v") == _EVIDENCE_VERSION:
            c["role_evidence"] = hit.get("snippets", [])
            cached += 1
            continue
        if _time.time() - t0 > budget_s:
            continue
        snippets = extract_role_evidence(_extract_text(f))
        cache[sid] = {"mtime": mtime, "v": _EVIDENCE_VERSION, "snippets": snippets}
        c["role_evidence"] = snippets
        read += 1
        changed = True
    if changed:
        _save_cache(cache)
    return {"read": read, "cached": cached, "not_reachable": missing,
            "seconds": round(_time.time() - t0, 1)}
