"""Staff-CV country attribution.

Rule: a CV's country comes from the FIRST directory directly below ``Staff CVs``,
however deeply the file is nested (``Staff CVs/Sudan/Senior Evaluation Expert/
Ahmed/cv.pdf`` → ``Sudan``). Role, person, employer and project-location folder
names below that level are NEVER used as a country.

A pool folder (``International Experts``) is not a country: it sets
``country_pool`` and leaves ``country`` empty — no country is invented.

Folder spellings are normalized only where unambiguous (``Palistin`` →
``Palestine``). Canonical names follow the Master Tracker (``Turkey``, not
``Türkiye``), so CV and project country values compare equal.
"""
from __future__ import annotations

from pathlib import Path, PurePath
from typing import Optional

COUNTRY_SOURCE = "STAFF_CVS_TOP_FOLDER"

# Canonical country names, aligned with the Master Tracker's values.
_CANONICAL = (
    "Afghanistan", "Egypt", "Iraq", "Jordan", "Lebanon", "Libya", "Palestine",
    "Somalia", "South Sudan", "Sudan", "Syria", "Turkey", "Yemen",
)
_CANON_BY_KEY = {c.casefold(): c for c in _CANONICAL}

# Unambiguous spelling variants → canonical name.
_ALIASES = {
    "palistin": "Palestine",
    "palestinian territories": "Palestine",
    "opt": "Palestine",
    "türkiye": "Turkey",
    "turkiye": "Turkey",
    "syrian arab republic": "Syria",
}

# Folders that hold a pool of experts rather than one country's staff.
_POOLS = {
    "international experts": "International Experts",
    "international expert": "International Experts",
    "international": "International Experts",
}


def _key(name: str) -> str:
    return " ".join((name or "").split()).casefold()


def canonical_country(name: Optional[str]) -> str:
    """Canonical country for a name, or "" when it is not a recognized country."""
    k = _key(name or "")
    if not k:
        return ""
    if k in _ALIASES:
        return _ALIASES[k]
    return _CANON_BY_KEY.get(k, "")


def canonical_pool(name: Optional[str]) -> str:
    return _POOLS.get(_key(name or ""), "")


def attribute_country(rel_path: str | PurePath) -> dict:
    """Country fields for a CV, from its path relative to ``Staff CVs``.

    Returns ``country``, ``country_pool``, ``source_country_folder``,
    ``country_status`` (COUNTRY | POOL | UNRECOGNIZED_FOLDER | NO_FOLDER) and
    ``country_source``.
    """
    parts = PurePath(str(rel_path).replace("\\", "/")).parts
    folder = parts[0] if len(parts) > 1 else ""   # a file directly in Staff CVs has none
    out = {"country": "", "country_pool": "", "source_country_folder": folder,
           "country_source": COUNTRY_SOURCE}
    if not folder:
        out["country_status"] = "NO_FOLDER"
        return out
    pool = canonical_pool(folder)
    if pool:
        out["country_pool"] = pool
        out["country_status"] = "POOL"
        return out
    country = canonical_country(folder)
    if country:
        out["country"] = country
        out["country_status"] = "COUNTRY"
        return out
    # An unknown top-level folder: keep it visible for review, never guess.
    out["country_status"] = "UNRECOGNIZED_FOLDER"
    return out


def apply_country(profile: dict, rel_path: str | PurePath) -> dict:
    """Return the profile with its country fields re-derived from ``rel_path``.

    Only the attribution fields change; parsed CV facts and provenance are kept.
    """
    rel = str(rel_path)
    return {**profile, "source_rel_path": profile.get("source_rel_path") or rel,
            **attribute_country(rel)}


def matches_country(profile: dict, query: Optional[str]) -> bool:
    """True when a profile belongs to the queried country or expert pool."""
    if not query:
        return False
    qc, qp = canonical_country(query), canonical_pool(query)
    if qp:
        return (profile.get("country_pool") or "") == qp
    pc = canonical_country(profile.get("country"))
    if qc:
        return pc == qc
    # unrecognized query: exact (case-insensitive) match on the stored value
    return _key(profile.get("country") or "") == _key(query)


def repair_staff_index(cache, staff_dir: Optional[str | Path] = None) -> dict:
    """Re-derive country fields for every cached staff profile — no CV re-parse.

    Uses each profile's stored ``source_rel_path``. Writes the staff index only
    (projects, company, brand and exemplars are untouched).
    """
    data = cache.staff() or {}
    profiles = data.get("profiles", [])
    source = data.get("source") or {}
    if staff_dir:
        source = {**source, "path": str(staff_dir)}
    changed = 0
    missing_path = 0
    fixed = []
    for p in profiles:
        rel = p.get("source_rel_path")
        if not rel:
            missing_path += 1
            fixed.append(p)
            continue
        q = apply_country(p, rel)
        from .staff_doctype import with_document_type
        q = with_document_type(q)
        if any(q.get(k) != p.get(k) for k in
               ("country", "country_pool", "source_country_folder", "country_status")):
            changed += 1
        fixed.append(q)
    cache.write_staff(fixed, source or {"type": "local_folder"})
    return {"profiles": len(fixed), "changed": changed,
            "missing_source_path": missing_path, **summarize(fixed)}


def summarize(profiles: list) -> dict:
    counts: dict[str, int] = {}
    pools: dict[str, int] = {}
    unresolved: dict[str, int] = {}
    for p in profiles:
        st = p.get("country_status")
        if st == "COUNTRY":
            counts[p["country"]] = counts.get(p["country"], 0) + 1
        elif st == "POOL":
            pools[p["country_pool"]] = pools.get(p["country_pool"], 0) + 1
        else:
            k = p.get("source_country_folder") or "(no folder)"
            unresolved[k] = unresolved.get(k, 0) + 1
    return {"with_valid_country": sum(counts.values()),
            "pools": dict(sorted(pools.items())),
            "missing_or_ambiguous": sum(unresolved.values()),
            "unresolved_folders": dict(sorted(unresolved.items())),
            "country_counts": dict(sorted(counts.items()))}
