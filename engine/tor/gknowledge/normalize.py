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


def normalize_cv(*, text: str, file_id: str, file_name: str, country: str = "",
                 modified_time: str = "") -> dict:
    """Normalize one CV's text → structured profile with evidence locators.

    Critical qualification claims keep the evidence snippet; nothing is invented.
    """
    low = (text or "")
    name = _guess_name(file_name)
    years = [int(m.group(1)) for m in _YEARS.finditer(low)]
    max_years = max(years) if years else None
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
            "years_experience": _evidence(_YEARS) if max_years else "",
            "education": _evidence(_DEGREE) if degrees else "",
        },
        "extraction_confidence": "MEDIUM" if (max_years or degrees or roles) else "LOW",
    }


def _guess_name(file_name: str) -> str:
    base = re.sub(r"\.(pdf|docx)$", "", file_name, flags=re.I)
    base = re.sub(r"\b(cv|resume|curriculum\s+vitae)\b", "", base, flags=re.I)
    base = re.sub(r"[_\-]+", " ", base).strip()
    return base.title() if base else file_name
