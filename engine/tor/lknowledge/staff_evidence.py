"""Evidence-gated personnel claims and field-roster readiness (v0.6.11).

Every personnel attribute that may appear in team ranking, the proposal narrative
or compliance mapping gets a claim status from the indexed CV evidence:

  VERIFIED     stated in the CV's own stored evidence text (snippet), or a promoted
               staff fact with a quote (team_staff_facts.json)
  PROVISIONAL  supported only by how ARFADA filed the CV (folder name) or by a parsed
               keyword without a quote — usable for ranking, not as a verified claim
  UNVERIFIED   not evidenced (a job title alone is never evidence of sector expertise)

Field-roster readiness checks for usable field CVs in the right geography instead of
treating the existence of a country folder as an operational roster.
"""
from __future__ import annotations

import re
from pathlib import PurePath
from typing import Iterable, Optional

VERIFIED = "VERIFIED"
PROVISIONAL = "PROVISIONAL"
UNVERIFIED = "UNVERIFIED"
MISSING = "MISSING"

# attribute -> regex over evidence text
EXPERTISE = {
    "fsl": r"food\s+security|\bfsl\b|livelihood|food\s+assistance|food\s+consumption|\bfcs\b|rcsi",
    "evaluation": r"evaluat|\bmeal\b|m\s*&\s*e|monitoring\s+and\s+evaluation|base-?\s?line|end-?\s?line",
    "safeguarding": r"safeguard|\bpsea\b|child\s+protection",
    "gender": r"gender|\bgesi\b|women['’]?s\s+empowerment",
    "protection": r"protection|\bgbv\b",
    "nutrition": r"nutrition|anthropometr|\bsmart\b",
    "wash": r"\bwash\b|water|sanitation|hygiene",
    "cash": r"\bcash\b|voucher|\bcva\b|\bmpca\b",
}
TOOLS = r"\b(spss|stata|kobo(?:toolbox)?|odk|nvivo|python|power\s*bi|atlas\.ti|arcgis|qgis|excel|r\s+studio|rstudio)\b"
FIELD_ROLE = re.compile(
    r"field\s+data\s+collectors?|enumerators?|data\s+collectors?|field\s+(?:coordinator|"
    r"supervisor|researchers?|monitors?|team|officer)|interviewers?", re.I)


def _snippets(profile: dict) -> str:
    ev = profile.get("evidence") or {}
    return " ".join(str(v) for v in ev.values()) if isinstance(ev, dict) else ""


def _folders(profile: dict) -> str:
    rel = str(profile.get("source_rel_path") or "").replace("\\", "/")
    parts = PurePath(rel).parts
    return " ".join(parts[1:-1])          # below the country folder, excluding the file


def _status(pattern: str, snippets: str, folders: str) -> tuple[str, str]:
    if snippets and re.search(pattern, snippets, re.I):
        return VERIFIED, "CV evidence text"
    if folders and re.search(pattern, folders, re.I):
        return PROVISIONAL, "ARFADA CV filing folder"
    return UNVERIFIED, ""


def profile_claims(profile: dict, *, places: Iterable[str] = (),
                   staff_facts: Optional[list] = None) -> dict:
    """Claim status per personnel attribute (never inferred from the job title)."""
    snip, fold = _snippets(profile), _folders(profile)
    out: dict = {}
    # years of experience: only the v0.6.9 verified value
    ys = profile.get("years_experience_status")
    if profile.get("years_experience") is not None and ys in ("VERIFIED", None):
        ev = (profile.get("evidence") or {}).get("years_experience") if isinstance(
            profile.get("evidence"), dict) else ""
        out["years_experience"] = {"status": VERIFIED if ev else PROVISIONAL,
                                   "value": profile.get("years_experience"),
                                   "evidence": (ev or "")[:160]}
    else:
        out["years_experience"] = {"status": UNVERIFIED, "value": None, "evidence": ""}
    for key, pat in EXPERTISE.items():
        st, src = _status(pat, snip, fold)
        out[key] = {"status": st, "source": src}
    # country / sub-national experience: filing under a country folder is not
    # evidence of having worked there; the CV text must say so
    country = profile.get("country") or ""
    cst, csrc = _status(re.escape(country), snip, "") if country else (UNVERIFIED, "")
    if cst == UNVERIFIED and country:
        cst, csrc = PROVISIONAL, "filed under the country folder"
    out["country_experience"] = {"status": cst, "value": country, "source": csrc}
    plist = [p for p in places if p]
    if plist:
        pat = "|".join(re.escape(p) for p in plist)
        pst, psrc = _status(pat, snip, fold)
        out["local_experience"] = {"status": pst, "places": plist, "source": psrc}
    tools = sorted({m.group(1).lower() for m in re.finditer(TOOLS, snip, re.I)})
    out["software_tools"] = {"status": VERIFIED if tools else UNVERIFIED, "value": tools}
    langs = list(profile.get("languages") or [])
    out["languages"] = {"status": PROVISIONAL if langs else UNVERIFIED, "value": langs,
                        "source": "parsed from CV text" if langs else ""}
    # promoted staff facts (quoted from the CV by the session) are VERIFIED
    for f in staff_facts or []:
        if f.get("staff_id") != profile.get("staff_id") or not f.get("verified"):
            continue
        attr = str(f.get("attribute") or "").lower()
        quote = ((f.get("provenance") or {}).get("quote") or f.get("quote") or "")[:160]
        target = attr if attr in out else next((k for k in EXPERTISE if k in attr), attr)
        out[target] = {**out.get(target, {}), "status": VERIFIED,
                       "value": f.get("value"), "source": "promoted staff fact",
                       "evidence": quote}
    return out


def is_positive(claim: dict) -> bool:
    """Only VERIFIED claims may be stated as a team qualification."""
    return (claim or {}).get("status") == VERIFIED


def field_roster_readiness(profiles: list, *, country: str, places: Iterable[str] = (),
                           min_profiles: int = 5) -> dict:
    """VERIFIED only with enough usable field CVs in the TOR's own geography.

    A country folder, certificates or a handful of CVs are not an operational roster.
    """
    from .staff_country import matches_country
    places = [p for p in places if p]
    place_re = re.compile("|".join(re.escape(p) for p in places), re.I) if places else None
    in_country = local = 0
    for p in profiles:
        if p.get("document_type", "CV") != "CV" or not country or not matches_country(p, country):
            continue
        text = " ".join([_folders(p), " ".join(p.get("roles") or []),
                         str(p.get("source_file_name") or "")])
        if not FIELD_ROLE.search(text):
            continue
        in_country += 1
        if place_re and place_re.search(_folders(p) + " " + _snippets(p)):
            local += 1
    if places and local >= min_profiles:
        status = VERIFIED
    elif in_country >= min_profiles:
        status = PROVISIONAL          # national pool, not evidenced for the target area
    else:
        status = MISSING
    return {"status": status, "field_cvs_in_country": in_country,
            "field_cvs_in_target_area": local, "min_profiles": min_profiles,
            "places": places, "country": country}
