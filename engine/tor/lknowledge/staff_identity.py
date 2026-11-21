"""Stable staff identity (v0.6.12).

The canonical identity of a person is ``staff_profile_id`` (the index's ``staff_id``,
derived from the CV's source file ID) — never a name and never name tokens. Many
colleagues share tokens such as Ahmed, Mohamed, Ishag or Abdelkarim, so two profiles
are the SAME person only when their full canonical names are identical (in order) or
the files sit in the same person-named folder.

``canonical_name`` is the person's full name:
  VERIFIED     promoted from the CV text (staff fact attribute full_name / name)
  PROVISIONAL  derived from ARFADA's filing (a person-named folder, or the CV file
               name with CV / role / version / date words removed)
The proposal must render the full canonical name — never initials or a shortened form.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import PurePath
from typing import Optional

_NOISE = {
    "cv", "cvs", "resume", "résumé", "curriculum", "vitae", "vita", "final", "draft", "update",
    "updated", "ngo", "thematic", "version", "copy", "new", "english", "arabic", "en", "ar", "ok",
    "latest", "short", "long", "profile", "full", "bnp", "dr", "eng", "mr", "mrs", "ms", "prof",
    "expert", "experts", "specialist", "consultant", "officer", "manager", "coordinator",
    "analyst", "engineer", "advisor", "adviser", "director", "lead", "leader", "team", "senior",
    "junior", "field", "data", "project", "programme", "program", "gender", "protection",
    "safeguarding", "sea", "sh", "seah", "meal", "monitoring", "evaluation", "education",
    "health", "nutrition", "wash", "fsl", "operations", "head", "of", "the", "and", "in", "for",
    "collector", "collectors", "enumerator", "trainer", "researcher", "statistician", "sudan",
    "syria", "iraq", "jordan", "lebanon", "turkey", "yemen", "libya", "afghanistan", "palestine",
    "jan", "january", "feb", "february", "mar", "march", "apr", "april", "may", "jun", "june",
    "jul", "july", "aug", "august", "sep", "sept", "september", "oct", "october", "nov",
    "november", "dec", "december", "rd", "th", "nd", "st", "cover", "letter", "pdf", "docx",
    "merged", "arfada", "research", "classic", "style", "technical", "examples", "example",
    "previous", "projects", "certificate", "certificates", "updateed", "modfied", "modified",
    "consultancy", "proposal", "sample", "report", "cvv", "lv", "vw", "ev", "rw",
}
_NAME_TOKEN = re.compile(r"^[^\W\d_]{2,}$")


def _fold(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t or "").casefold())
    return "".join(ch for ch in t if not unicodedata.combining(ch))


def _title(tok: str) -> str:
    return tok if not tok.isupper() else tok.capitalize()


def _name_tokens(text: str) -> list:
    text = re.sub(r"\.(?:pdf|docx?|rtf)$", "", str(text or ""), flags=re.I)
    text = re.sub(r"[_\-–—,.()\[\]+@&/\\]|\d+", " ", text)
    out = []
    for tok in text.split():
        if not _NAME_TOKEN.match(tok) or _fold(tok) in _NOISE:
            continue
        out.append(_title(tok))
    return out


def _person_folder(profile: dict) -> list:
    """Name tokens of the CV's parent folder when it looks like a person's name."""
    rel = str(profile.get("source_rel_path") or "").replace("\\", "/")
    parts = PurePath(rel).parts
    for folder in reversed(parts[1:-1]):              # nearest folder first
        raw = re.sub(r"\.(?:pdf|docx?)$", "", folder, flags=re.I)
        words = raw.replace("_", " ").split()
        toks = _name_tokens(raw)
        if 2 <= len(toks) <= 5 and len(toks) >= len([w for w in words if re.search(r"[A-Za-z]", w)]) - 1:
            return toks
    return []


def canonical_identity(profile: dict, *, staff_facts: Optional[list] = None) -> dict:
    """staff_profile_id + full canonical name (with its evidence status)."""
    sid = profile.get("staff_id") or profile.get("staff_profile_id") or ""
    for f in staff_facts or []:
        if f.get("staff_id") in (sid, profile.get("staff_profile_id")) and f.get("verified") and \
                str(f.get("attribute") or "").lower() in ("full_name", "name", "canonical_name"):
            return {"staff_profile_id": sid, "source_file_id": profile.get("source_file_id", ""),
                    "canonical_name": " ".join(str(f.get("value") or "").split()),
                    "canonical_name_status": "VERIFIED", "canonical_name_source": "CV (promoted fact)"}
    folder = _person_folder(profile)
    filename = _name_tokens(profile.get("source_file_name") or
                            PurePath(str(profile.get("source_rel_path") or "")).name or
                            profile.get("name") or "")
    # a folder is the person's name only if it shares a name token with the CV file
    # name ("Cash-Based Intervention (CBI) Expert" is a topic folder, not a person)
    if folder and filename and not (set(map(_fold, folder)) & set(map(_fold, filename))):
        folder = []
    # prefer the folder name when it is the fuller form of the same person
    if folder and (not filename or set(map(_fold, filename)) <= set(map(_fold, folder))
                   or len(folder) > len(filename)):
        toks, src = folder, "person folder"
    else:
        toks, src = filename[:5], "CV file name"
    name = " ".join(toks)
    return {"staff_profile_id": sid, "source_file_id": profile.get("source_file_id", ""),
            "canonical_name": name,
            "canonical_name_status": "PROVISIONAL" if len(toks) >= 2 else "UNVERIFIED",
            "canonical_name_source": src if toks else ""}


def name_key(name: str) -> tuple:
    """Ordered, case-folded name tokens (identity comparison — never a subset)."""
    return tuple(_fold(t) for t in re.findall(r"[^\W\d_]+", name or ""))


def _keys(p: dict) -> tuple:
    k = p.get("_identity_keys")
    if k is None:
        folder = tuple(_person_folder(p))
        parent = str(p.get("source_rel_path") or "").replace("\\", "/").rsplit("/", 1)[0]
        k = (folder, parent, name_key(canonical_identity(p)["canonical_name"]))
        try:
            p["_identity_keys"] = k
        except Exception:
            pass
    return k


def same_person(a: dict, b: dict) -> bool:
    """Same person only for identical full names (in order) or one person-named folder."""
    if (a.get("staff_id") and a.get("staff_id") == b.get("staff_id")):
        return True
    (fa, pa, ka), (fb, pb, kb) = _keys(a), _keys(b)
    if fa and fa == fb and pa == pb:
        return True
    return len(ka) >= 2 and ka == kb


def abbreviation_pattern(canonical_name: str) -> Optional[re.Pattern]:
    """Initials forms of a full name: 'Ahmed M. A. Elamin', 'A. M. A. Elamin', 'Ahmed Elamin'."""
    toks = (canonical_name or "").split()
    if len(toks) < 3:
        return None
    first, mids, last = toks[0], toks[1:-1], toks[-1]
    mid_initials = r"\s+".join(rf"{re.escape(m[0])}\.?" for m in mids)
    pats = [rf"\b{re.escape(first)}\s+{mid_initials}\s+{re.escape(last)}\b",
            rf"\b{re.escape(first[0])}\.\s*{mid_initials}\s+{re.escape(last)}\b",
            rf"\b{re.escape(first)}\s+{re.escape(last)}\b"]
    return re.compile("|".join(pats))


def mentions(text: str, canonical_name: str) -> str:
    """'FULL' if the full name appears, 'SHORT' for an initials / shortened form, else ''."""
    if not canonical_name:
        return ""
    norm = " ".join((text or "").split())
    if re.search(rf"\b{re.escape(canonical_name)}\b", norm, re.I):
        return "FULL"
    pat = abbreviation_pattern(canonical_name)
    if pat and pat.search(norm):
        return "SHORT"
    return ""
