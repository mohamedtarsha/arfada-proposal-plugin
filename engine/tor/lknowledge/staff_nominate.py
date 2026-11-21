"""Evidence-based nomination score for automatic team selection (Fast Mode).

``search_staff`` keeps its base ``match_score`` (country / role / language). For a
country-only query every in-country profile gets the same base score, so the
shortlist could not tell a strong CV from a weak one. This module adds a
deterministic ``nomination_score`` built ONLY from evidence already in the staff
index — nothing is re-parsed and no fact is invented:

  country / expert-pool relevance ........ 30 / 15
  document type is a CV ................... 15
  TOR team-role match ..................... 12 per role (max 24)
  parsed professional roles ............... 3 per role (max 9)
  sector / theme keywords ................. 6 per theme (max 12)
  evaluation / MEAL experience ............ 8, +4 for baseline/endline/final evaluation
  geography explicitly evidenced .......... 6 (TOR place named in the CV's folders/evidence)
  years_experience (structured + evidence)  0.4 per year (max 10)
  extraction confidence ................... +1 MEDIUM / +2 HIGH (tie-break only)

Theme, evaluation and geography evidence come from the CV's folder and file names
(how ARFADA files CVs, e.g. "FSL - food security and livelihood",
"Field data collectors in sudan/Darfur"), its parsed roles and its stored evidence
snippets.

``nominate`` then applies the CV-likeness rules (CVs first, SUPPORTING_DOCUMENT
never, UNKNOWN only to fill) and collapses duplicate files of one person.
``team_question`` decides whether the user must choose.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import PurePath
from typing import Optional

from .staff_country import canonical_country, canonical_pool, matches_country
from .staff_doctype import classify_document

# --- TOR team roles (staff-index role labels and the TOR wording that names them)
_TEAM_ROLES = (
    ("Team Leader", ("team leader", "lead evaluator", "lead consultant", "team lead")),
    ("Evaluator", ("evaluator",)),
    ("M&E Specialist", ("m&e specialist", "meal specialist", "monitoring and evaluation specialist")),
    ("M&E Officer", ("m&e officer", "meal officer", "monitoring and evaluation officer")),
    ("Data Analyst", ("data analyst", "data analysis")),
    ("Statistician", ("statistician",)),
    ("Researcher", ("researcher", "research assistant")),
    ("Enumerator", ("enumerator", "data collector")),
    ("Field Coordinator", ("field coordinator", "field supervisor", "field manager")),
)

# --- sector / theme vocabulary (TOR text ↔ CV folder/file/role evidence)
_THEMES = {
    "FSL": r"food\s+security|\bfsl\b|livelihood|food\s+assistance|food\s+consumption",
    "CASH": r"\bcash\b|voucher|\bcva\b|\bmpca\b|\bcbi\b",
    "NUTRITION": r"nutrition|anthropometr|\bsmart\b",
    "HEALTH": r"\bhealth\b|\bepi\b|immuni[sz]",
    "WASH": r"\bwash\b|water|sanitation|hygiene",
    "PROTECTION": r"protection|\bgbv\b|\bpsea\b|safeguard",
    "GENDER": r"gender|\bgesi\b|women",
    "EDUCATION": r"education|\btvet\b|school",
    "SHELTER": r"shelter|\bnfi\b",
    "AGRICULTURE": r"agricultur|agronom|livestock|farm",
    "MHPSS": r"mhpss|psychosocial|mental\s+health",
    "PEACE": r"peace|conflict|social\s+cohesion",
    "DISABILITY": r"disabilit|inclusion",
}
_EVALUATION = re.compile(r"evaluat|\bmeal\b|m\s*&\s*e|monitoring\s+and\s+evaluation", re.I)
_BASE_END = re.compile(r"base-?\s?line|end-?\s?line|final\s+evaluation|impact\s+evaluation", re.I)
_PLACE_STOP = {"south", "north", "east", "west", "central", "and", "the", "project", "state",
               "district", "locality", "localities", "province", "region", "governorate",
               "emergency", "food", "voucher", "terms", "reference", "evaluation", "final",
               "endline", "baseline", "of", "in", "for"}
_CONF = {"HIGH": 2, "MEDIUM": 1}

CLOSE_MARGIN = 3           # top two within this many points → genuinely close
WEAK_EVIDENCE = 45         # top candidate below this → evidence too weak to auto-select


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _mv(meta: dict, key: str) -> str:
    e = (meta or {}).get(key)
    return (e.get("value", "") if isinstance(e, dict) else str(e or "")).strip()


# ---------------------------------------------------------------------------
# TOR context
# ---------------------------------------------------------------------------

def tor_context(tor: Optional[dict], requirements: Optional[list], country: str = "") -> dict:
    meta = (tor or {}).get("metadata", {}) or {}
    team_reqs = [r for r in requirements or []
                 if isinstance(r, dict) and r.get("category") == "team"]
    team_text = _fold(" ".join(str(r.get("text") or "") for r in team_reqs))
    roles = [label for label, cues in _TEAM_ROLES if any(c in team_text for c in cues)]
    tor_text = _fold(" ".join([_mv(meta, k) for k in
                               ("assignment", "title", "objectives", "scope", "background",
                                "required_methodology", "sector")]
                              + [str(r.get("text") or "") for r in requirements or []
                                 if isinstance(r, dict)]))
    themes = {t for t, pat in _THEMES.items() if re.search(pat, tor_text, re.I)}
    place_text = " ".join([_mv(meta, k) for k in ("subnational_location", "location",
                                                  "geographic_scope", "area", "geography")])
    title = _mv(meta, "assignment") or _mv(meta, "title")
    m = re.search(r"\bin\s+(.+)$", title)
    place_text += " " + (m.group(1) if m else "")
    ctry = canonical_country(country) or canonical_country(_mv(meta, "country"))
    places = {w for w in re.findall(r"[a-z]{4,}", _fold(place_text))
              if w not in _PLACE_STOP and w != _fold(ctry)}
    # mandatory eligibility for the lead role
    lead_min_years, lead_req = None, None
    for r in team_reqs:
        t = _fold(r.get("text") or "")
        if r.get("mandatory", True) and re.search(r"team\s+leader|lead\s+(?:evaluator|consultant)", t):
            y = re.search(r"(\d{1,2})\s*\+?\s*years?", t)
            if y:
                lead_min_years, lead_req = int(y.group(1)), r.get("text")
                break
    return {"country": ctry or country, "pool": canonical_pool(country), "roles": roles,
            "themes": themes, "places": places, "lead_min_years": lead_min_years,
            "lead_requirement": lead_req,
            "assignment_type": ((tor or {}).get("assignment_type") or {}).get(
                "assignment_type", "")}


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------

def _evidence_text(p: dict) -> str:
    rel = str(p.get("source_rel_path") or "").replace("\\", "/")
    parts = PurePath(rel).parts
    ev = p.get("evidence") or {}
    snippets = " ".join(str(v) for v in ev.values()) if isinstance(ev, dict) else ""
    # v0.6.11 evidence gating: CV evidence text + ARFADA's filing folders only.
    # A parsed job title alone is never evidence of sector / evaluation expertise.
    return _fold(" ".join(list(parts[1:]) + [snippets]))


def nomination_score(p: dict, ctx: dict) -> tuple[float, dict]:
    """Deterministic score + per-factor breakdown (all from indexed evidence)."""
    b: dict[str, float] = {}
    if ctx.get("country") and matches_country(p, ctx["country"]):
        b["country"] = 30
    elif p.get("country_pool"):
        b["country_pool"] = 15
    doc = p.get("document_type") or classify_document(p)["document_type"]
    if doc == "CV":
        b["cv_document"] = 15
    roles = [r for r in p.get("roles") or [] if r]
    lowered = {r.casefold() for r in roles}
    hits = sum(1 for r in ctx.get("roles", []) if r.casefold() in lowered)
    if hits:
        b["tor_role_match"] = min(12 * hits, 24)
    if roles:
        b["parsed_roles"] = min(3 * len(roles), 9)
    text = _evidence_text(p)
    th = sum(1 for t in ctx.get("themes", ()) if re.search(_THEMES[t], text, re.I))
    if th:
        b["theme"] = min(6 * th, 12)
    if _EVALUATION.search(text):
        b["evaluation"] = 8
        if _BASE_END.search(text):
            b["baseline_endline"] = 4
    words = set(re.findall(r"[a-z]{4,}", text))
    if ctx.get("places") and words & ctx["places"]:
        b["geography"] = 6
    years = p.get("years_experience")
    ev = p.get("evidence") or {}
    if isinstance(years, (int, float)) and years > 0 and (ev.get("years_experience") if
                                                          isinstance(ev, dict) else ""):
        b["years_experience"] = round(min(years, 25) * 0.4, 1)
    conf = _CONF.get(str(p.get("extraction_confidence") or "").upper(), 0)
    if conf:
        b["confidence"] = conf
    return round(sum(b.values()), 1), b


# ---------------------------------------------------------------------------
# duplicates
# ---------------------------------------------------------------------------

_NOISE = {"cv", "cvs", "resume", "curriculum", "vitae", "updated", "update", "final", "new",
          "latest", "version", "english", "arabic", "copy", "draft", "and", "of", "the", "by",
          "dr", "eng", "mr", "mrs", "ms", "pdf", "docx"}


def person_key(p: dict) -> tuple:
    """Name tokens of the person behind a file ("<title> - <person>" convention)."""
    stem = str(p.get("source_file_name") or PurePath(
        str(p.get("source_rel_path") or "").replace("\\", "/")).name or p.get("name") or "")
    stem = stem.rsplit(".", 1)[0]
    if " - " in stem:
        stem = stem.rsplit(" - ", 1)[-1]
    toks = [t for t in re.findall(r"[^\W\d_]+", _fold(stem)) if t not in _NOISE and len(t) > 1]
    return tuple(toks)


def _parent(p: dict) -> str:
    rel = str(p.get("source_rel_path") or "").replace("\\", "/")
    return rel.rsplit("/", 1)[0].casefold() if "/" in rel else ""


def same_person(a: dict, b: dict) -> bool:
    ka, kb = person_key(a), person_key(b)
    if not ka or not kb:
        return False
    if set(ka) == set(kb):
        return True
    shorter, longer = (ka, kb) if len(ka) <= len(kb) else (kb, ka)
    return len(shorter) >= 2 and set(shorter) <= set(longer) and _parent(a) == _parent(b) != ""


# ---------------------------------------------------------------------------
# nomination + question
# ---------------------------------------------------------------------------

def nominate(candidates: list, ctx: dict, limit: int = 6) -> list:
    """Order candidates for automatic nomination (one entry per person).

    CVs first by nomination score; UNKNOWN only fills slots no CV can fill;
    SUPPORTING_DOCUMENT is never nominated (it stays searchable in the index).
    """
    scored = []
    for c in candidates:
        typed = c if "document_type" in c else {**c, **classify_document(c)}
        if typed["document_type"] == "SUPPORTING_DOCUMENT":
            continue
        s, breakdown = nomination_score(typed, ctx)
        scored.append({**typed, "nomination_score": s, "score_breakdown": breakdown})
    scored.sort(key=lambda c: (-c["nomination_score"], -(c.get("match_score") or 0),
                               -(c.get("cv_likeness_score") or 0)))

    def unique(items):
        kept = []
        for c in items:
            if not any(same_person(c, k) for k in kept):
                kept.append(c)
        return kept

    cvs = unique([c for c in scored if c["document_type"] == "CV"])
    if len(cvs) >= limit:
        return cvs[:limit]
    unknown = [c for c in unique([c for c in scored if c["document_type"] == "UNKNOWN"])
               if not any(same_person(c, k) for k in cvs)]
    return (cvs + unknown)[:limit]


def _lead_eligibility(top: dict, ctx: dict) -> str:
    """MEETS / FAILS / UNKNOWN for the mandatory lead-years criterion (if any)."""
    need = ctx.get("lead_min_years")
    if need is None:
        return "NOT_APPLICABLE"
    y = top.get("years_experience")
    ev = top.get("evidence") or {}
    if not isinstance(y, (int, float)) or not (isinstance(ev, dict) and ev.get("years_experience")):
        return "UNKNOWN"
    return "MEETS" if y >= need else "FAILS"


def team_question(team: list, ctx: dict) -> tuple[bool, str]:
    """Ask the user only when the choice is genuinely theirs.

    Asks when: no CV candidate; the evidence for the top candidate is weak; the top
    two (different people) are within CLOSE_MARGIN; or a mandatory eligibility
    requirement cannot be confirmed for the top candidate. Equal base match scores
    alone never trigger a question.
    """
    if not team:
        return False, "No CV candidates available in Knowledge (team is a gap, not a blocker)."
    top = team[0]
    if top.get("document_type") != "CV":
        return True, "No indexed document is clearly a CV — confirm the team lead."
    if top["nomination_score"] < WEAK_EVIDENCE or \
            str(top.get("extraction_confidence") or "").upper() == "LOW":
        return True, "Evidence for the top candidate is weak — confirm the team lead."
    elig = _lead_eligibility(top, ctx)
    if elig in ("UNKNOWN", "FAILS"):
        need = ctx.get("lead_min_years")
        state = "cannot be confirmed" if elig == "UNKNOWN" else "is not met"
        return True, (f"Mandatory requirement ({need}+ years for the team leader) {state} for "
                      f"the top candidate — confirm the team lead.")
    if len(team) >= 2 and team[1].get("document_type") == "CV" and \
            top["nomination_score"] - team[1]["nomination_score"] <= CLOSE_MARGIN:
        return True, "Top two candidates are closely ranked — confirm the lead."
    return False, ""
