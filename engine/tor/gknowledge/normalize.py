"""Deterministic normalization: Master Tracker rows → project records + metrics;
CV files → normalized staff profiles. No invented values for empty cells.

All numeric aggregation is done here in Python (spec §8) — never by the model.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Optional

from ..assignment_type import ASSIGNMENT_TYPES

# Canonical project fields (spec §7). Missing → None/"" (never invented).
PROJECT_FIELDS = [
    "project_id", "project_name", "assignment_type", "country", "region", "sector",
    "client", "donor", "start_date", "end_date", "status",
    "surveys", "kii", "fgd", "observations", "description",
]

# Header aliases (lowercased, fuzzy contains) → canonical field.
_HEADER_ALIASES = {
    "project_id": ["project id", "id", "code", "project code", "ref"],
    "project_name": ["project name", "project", "title", "assignment", "name"],
    "assignment_type": ["assignment type", "type", "category", "modality"],
    "country": ["country", "countries"],
    "region": ["region"],
    "sector": ["sector", "theme", "thematic"],
    "client": ["client", "organisation", "organization", "ngo", "agency"],
    "donor": ["donor", "funder", "funded by"],
    "start_date": ["start date", "start", "from"],
    "end_date": ["end date", "end", "to", "completion"],
    "status": ["status", "state"],
    "surveys": ["surveys", "survey", "hh survey", "household survey", "questionnaires"],
    "kii": ["kii", "kiis", "key informant"],
    "fgd": ["fgd", "fgds", "focus group"],
    "observations": ["observation", "observations", "site visit"],
    "description": ["description", "summary", "scope", "notes"],
}

_TYPE_CANON = {
    "evaluation": "EVALUATION", "final evaluation": "EVALUATION",
    "external evaluation": "EVALUATION", "mid-term": "MIDLINE", "midline": "MIDLINE",
    "midterm": "MIDLINE", "endline": "ENDLINE", "impact": "ENDLINE", "baseline": "BASELINE",
    "needs assessment": "NEEDS_ASSESSMENT", "assessment": "ASSESSMENT",
    "tpm": "TPM", "third-party monitoring": "TPM", "monitoring": "MONITORING",
    "research": "RESEARCH_STUDY", "study": "RESEARCH_STUDY", "survey": "SURVEY",
    "market assessment": "MARKET_ASSESSMENT", "capacity assessment": "CAPACITY_ASSESSMENT",
}


def _canon_type(v: str) -> str:
    low = (v or "").strip().lower()
    for key, canon in _TYPE_CANON.items():
        if key in low:
            return canon
    up = low.upper().replace(" ", "_")
    return up if up in ASSIGNMENT_TYPES else (v or "")


def _num(v) -> Optional[int]:
    if v is None:
        return None
    s = str(v).replace(",", "").strip()
    if not s:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        f = float(m.group(0))
        return int(f) if f.is_integer() else int(round(f))
    except ValueError:
        return None


def _map_headers(header_row: list, column_map: Optional[dict] = None) -> dict:
    """Return {col_index: canonical_field}. Explicit column_map (field→header) wins."""
    idx_for: dict[int, str] = {}
    headers = [str(h or "").strip().lower() for h in header_row]
    if column_map:
        for field, header in column_map.items():
            h = str(header).strip().lower()
            if h in headers:
                idx_for[headers.index(h)] = field
        return idx_for
    for i, h in enumerate(headers):
        for field, aliases in _HEADER_ALIASES.items():
            if field in idx_for.values():
                continue
            if any(a == h for a in aliases) or any(a in h for a in aliases):
                idx_for[i] = field
                break
    return idx_for


def normalize_projects(rows: list[list], *, sheet_name: str = "", spreadsheet_id: str = "",
                       column_map: Optional[dict] = None) -> list[dict]:
    """Normalize Master Tracker rows → project records with provenance.

    Empty cells stay None/"" — never invented.
    """
    if not rows:
        return []
    header = rows[0]
    idx_for = _map_headers(header, column_map)
    out: list[dict] = []
    for r_i, row in enumerate(rows[1:], start=2):  # 1-based + header offset
        rec: dict[str, Any] = {f: None for f in PROJECT_FIELDS}
        any_value = False
        for col_i, field in idx_for.items():
            val = row[col_i].strip() if col_i < len(row) and row[col_i] is not None else ""
            if not val:
                continue
            any_value = True
            if field in ("surveys", "kii", "fgd", "observations"):
                rec[field] = _num(val)
            elif field == "assignment_type":
                rec[field] = _canon_type(val)
            else:
                rec[field] = val
        if not any_value:
            continue
        if not rec.get("project_id"):
            rec["project_id"] = "row_" + hashlib.sha1(
                f"{spreadsheet_id}|{r_i}".encode()).hexdigest()[:10]
        rec["source_sheet"] = sheet_name
        rec["source_spreadsheet_id"] = spreadsheet_id
        rec["source_row"] = r_i
        out.append(rec)
    return out


def compute_metrics(projects: list[dict]) -> dict:
    """Deterministic organizational metrics from normalized projects (spec §8)."""
    def total(field):
        return sum(p[field] for p in projects if isinstance(p.get(field), int))

    countries = sorted({(p.get("country") or "").strip()
                        for p in projects if (p.get("country") or "").strip()})
    return {
        "total_projects": {"value": len(projects), "rule": "count of normalized project rows"},
        "total_surveys": {"value": total("surveys"), "rule": "sum(surveys) over projects"},
        "total_kii": {"value": total("kii"), "rule": "sum(kii) over projects"},
        "total_fgd": {"value": total("fgd"), "rule": "sum(fgd) over projects"},
        "countries": {"value": len(countries), "list": countries,
                      "rule": "distinct non-empty country values"},
    }


# ---------------------------------------------------------------------------
# CV normalization
# ---------------------------------------------------------------------------

_LANG = re.compile(r"\b(english|arabic|french|kurdish|spanish|dari|pashto|turkish)\b", re.I)
_DEGREE = re.compile(r"\b(ph\.?d|doctorate|master'?s|msc|ma\b|mba|bachelor'?s|bsc|ba\b)\b", re.I)
_YEARS = re.compile(r"(\d{1,2})\+?\s*years?", re.I)
_ROLE = re.compile(
    r"\b(team\s+leader|evaluator|researcher|m&e\s+(?:officer|specialist)|"
    r"enumerator|data\s+analyst|statistician|field\s+coordinator|consultant|"
    r"sector\s+specialist|qualitative\s+specialist|quantitative\s+specialist)\b", re.I)

# A "N years" match is NOT years-of-experience when the surrounding window is about
# someone's age, a project/grant duration, beneficiaries, a date range, or schooling.
# Only accept a match when the window has an experience cue AND no disqualifier.
_EXP_CUE = re.compile(
    r"\b(experience|professional|career|working|worked|practitioner|expertise|"
    r"consult|evaluation|research|m&e|monitoring|field\s*work|sector)\b", re.I)
_EXP_DISQUALIFY = re.compile(
    r"\b(age[d]?|years?\s*old|year-?old|born|children|child|adolescent|youth|"
    r"beneficiar|participant|respondent|household|students?|pupils?|grade|"
    r"duration|project|programme|program|grant|contract|phase|period|"
    r"warrant[y]?|valid|gpa|graduat|degree|enrol)\b", re.I)
_DATE_RANGE = re.compile(r"\b(19|20)\d{2}\s*[-–—/]\s*((19|20)\d{2}|present|now|date)\b", re.I)


# v0.6.9: years are accepted only when the number is BOUND to the person's own
# experience ("30 years of professional experience", "over 20 years' experience",
# "experience: 12 years"). A loose "N years" near the word "working" is not enough:
# "an NGO that has been working in Tanzania for over 30 years" is the organisation's
# history, not the candidate's career.
_PERSONAL_YEARS = re.compile(
    r"(?:(?:over|more\s+than|nearly|almost|about|around|approximately|some|at\s+least)\s+)?"
    r"(\d{1,2})\s*\+?[\s-]*(?:years?|yrs?)['’]?\s*(?:of\s+)?"
    r"(?:(?!has\b|have\b|with\b|but\b|in\b|at\b|for\b|on\b)[^\W\d_][\w&/-]*\s+){0,4}?"
    r"(?:experience|expertise|career)\b", re.I)
# "N years in/of/across …" counts when the same clause marks it as the person's own
# ("professional with over 12 years in …", "career spanning over 45 years").
_SPAN_YEARS = re.compile(
    r"(?:(?:over|more\s+than|nearly|almost|about|around|approximately|some|at\s+least)\s+)?"
    r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)\s+(?:in|of|across|as|since|[a-z]+ing)\b", re.I)
_PERSONAL_CUE = re.compile(
    r"\b(?:professional|career|experienced|expert|specialist|consultant|practitioner|"
    r"journey|spans?|spanning|i\s+have|i['’]ve|with\s+(?:over|more\s+than|nearly|about|"
    r"some|almost)?|has\s+(?:over|more\s+than|nearly|almost|about))\b|experience\s*:", re.I)
_EXPERIENCE_OF = re.compile(
    r"\b(?:experience|expertise)\s*(?:of|:|-|–|—|\(|spans?(?:\s+over)?|\s)\s*"
    r"(?:over|more\s+than|about|nearly)?\s*"
    r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b", re.I)
# The clause is about someone/something else: an organisation, its history, a
# relative clause ("that has been working …"), or an age.
_THIRD_PARTY = re.compile(
    r"\b(?:organi[sz]ations?|ngos?|ingos?|agency|agencies|company|companies|firm|"
    r"institution|institute|foundation|association|society|ministry|government|network|"
    r"consortium|charity|cooperative|established|founded|operating|in\s+operation|"
    r"since\s+its|existence)\b"
    r"|\b(?:that|which)\s+(?:has|have|had)\b", re.I)
_AGE_NEAR = re.compile(r"\b(?:aged?|years?\s*old|year-?old|born)\b", re.I)


def _clause_before(text: str, start: int, limit: int = 140) -> str:
    """Text from the last sentence/clause break before ``start``."""
    window = text[max(0, start - limit):start]
    cut = max(window.rfind(ch) for ch in ".;\n•▪")
    return window[cut + 1:] if cut >= 0 else window


def _personal_year_matches(text: str):
    for pat in (_PERSONAL_YEARS, _EXPERIENCE_OF, _SPAN_YEARS):
        for m in pat.finditer(text or ""):
            val = int(m.group(1))
            if val < 2 or val > 60:              # "1 year 11 months" is a job, not a career
                continue
            clause = _clause_before(text, m.start()) + text[m.start():m.end()]
            if _THIRD_PARTY.search(clause):
                continue
            if pat is _SPAN_YEARS and not (
                    _PERSONAL_CUE.search(text[max(0, m.start() - 60):m.end()])
                    or re.match(r"\W{0,3}\s*i\s+(?:have|['’]ve|worked)\b", text[m.end():],
                                re.I)):
                continue
            if _AGE_NEAR.search(text[max(0, m.start() - 22):m.end() + 22]):
                continue
            yield val, m


def _experience_years(text: str) -> tuple[Optional[int], str]:
    """Years of the candidate's OWN professional experience, or (None, "").

    Accepts only an explicit statement bound to experience/expertise/career and
    not about an organisation, a project or someone's age. Ambiguous text yields
    None — no replacement value is ever guessed.
    """
    low = text or ""
    best: Optional[int] = None
    best_snip = ""
    for val, m in _personal_year_matches(low):
        if best is None or val > best:
            best = val
            best_snip = low[max(0, m.start() - 45): m.end() + 45].strip()
    return best, best_snip


def years_supported_by_snippet(value, snippet: str) -> bool:
    """True if a stored evidence snippet still supports ``value`` under the v0.6.9
    rule (used to re-check an existing index without re-parsing any CV)."""
    if not isinstance(value, (int, float)) or not snippet:
        return False
    return any(v == int(value) for v, _m in _personal_year_matches(snippet))


def revalidate_years(profile: dict) -> dict:
    """Re-check a stored ``years_experience`` against its own evidence snippet.

    Unsupported values become None with ``years_experience_status = UNVERIFIED``;
    the rejected value and the snippet are kept for provenance. Idempotent; no CV
    is re-parsed and no replacement value is ever guessed.
    """
    years = profile.get("years_experience")
    if years is None:
        return profile if "years_experience_status" in profile else \
            {**profile, "years_experience_status": profile.get(
                "years_experience_rejected") and "UNVERIFIED" or "NOT_STATED"}
    ev = profile.get("evidence")
    if not isinstance(ev, dict) or "years_experience" not in ev:
        # not produced by the CV text parser (structured source): nothing to re-check.
        # Nomination and eligibility already ignore years without evidence.
        return {**profile, "years_experience_status": "NO_EVIDENCE"}
    snippet = ev.get("years_experience") or ""
    if years_supported_by_snippet(years, snippet):
        return {**profile, "years_experience_status": "VERIFIED"}
    return {**profile, "years_experience": None, "years_experience_status": "UNVERIFIED",
            "years_experience_rejected": {
                "value": years, "snippet": snippet,
                "reason": "not clearly linked to the candidate's own professional experience"}}


def normalize_cv(*, text: str, file_id: str, file_name: str, country: str = "",
                 modified_time: str = "") -> dict:
    """Normalize one CV's text → structured profile with evidence locators.

    Critical qualification claims keep the evidence snippet; nothing is invented.
    """
    low = (text or "")
    name = _guess_name(file_name)
    max_years, years_snip = _experience_years(low)
    langs = sorted({m.group(1).title() for m in _LANG.finditer(low)})
    degrees = sorted({m.group(0).upper() for m in _DEGREE.finditer(low)})
    roles = sorted({m.group(0).title() for m in _ROLE.finditer(low)})

    def _evidence(pat):
        m = pat.search(low)
        return low[max(0, m.start() - 25): m.end() + 25].strip() if m else ""

    return {
        "staff_id": "cv_" + hashlib.sha1(file_id.encode()).hexdigest()[:12],
        "name": name,
        "country": country,
        "roles": roles,
        "education": degrees,
        "years_experience": max_years,
        "languages": langs,
        "source_file_id": file_id,
        "source_file_name": file_name,
        "source_modified_time": modified_time,
        "evidence": {
            "years_experience": years_snip,
            "education": _evidence(_DEGREE) if degrees else "",
        },
        "extraction_confidence": "MEDIUM" if (max_years or degrees or roles) else "LOW",
    }


def promote_staff_fact(*, name: str, attribute: str, value: Any, source_file: str,
                       quote: str = "", confidence: str = "MEDIUM",
                       staff_profile_id: str = "") -> dict:
    """Promote a fact read directly from a CV into a structured staff fact (§4).

    When the session reads a CV and accepts a claim (role, years, education,
    language, availability, full_name), it must be promoted to a provenance-bearing
    staff fact BEFORE the proposal may use it — no named-person claim without evidence.
    v0.6.12: pass ``staff_profile_id`` (the index staff_id) so the fact attaches to the
    canonical identity, never to a name.
    """
    staff_id = staff_profile_id or "cv_" + hashlib.sha1((source_file or name).encode()).hexdigest()[:12]
    return {
        "fact_id": "stafffact_" + hashlib.sha1(
            f"{staff_id}|{attribute}|{value}".encode()).hexdigest()[:12],
        "staff_id": staff_id,
        "name": (name or "").strip(),
        "attribute": attribute,
        "value": value,
        "verified": True,
        "confidence": confidence,
        "provenance": {
            "method": "cv_read_promoted",
            "source_file": source_file,
            "quote": (quote or "")[:240],
        },
    }


def _guess_name(file_name: str) -> str:
    base = re.sub(r"\.(pdf|docx)$", "", file_name, flags=re.I)
    base = re.sub(r"\b(cv|resume|curriculum\s+vitae)\b", "", base, flags=re.I)
    base = re.sub(r"[_\-]+", " ", base).strip()
    return base.title() if base else file_name
