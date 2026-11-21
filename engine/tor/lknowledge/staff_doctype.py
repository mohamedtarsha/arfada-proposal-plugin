"""Deterministic CV-likeness of an indexed staff document (team ranking only).

The Staff CVs folders also hold certificates, declarations, diplomas, letters and
ID scans. They stay in the index (searchable as supporting evidence), but they
must not be nominated automatically as team members.

Classification uses ONLY what the index already stores — parsed roles, years of
experience, education, languages and the file/folder names — so nothing is
re-parsed.

document_type:
  CV                   the document is a CV/resume (named so, or shows work history)
  SUPPORTING_DOCUMENT  certificate / declaration / diploma / letter / ID / form,
                       and not named as a CV
  UNKNOWN              not enough evidence either way (e.g. scanned, no roles)
"""
from __future__ import annotations

import re
from pathlib import PurePath

# Names that say "this is a CV/resume".
_CV_NAME = re.compile(
    r"(?<![a-z])(?:cv|c\.v\.?|cvs|resume|résumé|resumé|curriculum[\s_-]*vita?e?|"
    r"bio[\s_-]?data)(?![a-z])|سيرة|السيرة",
    re.I)

# Names that say "this is a supporting document, not a CV".
_SUPPORTING_NAME = re.compile(
    r"(?<![a-z])(?:certificates?|certifications?|certs?|certified|declarations?|"
    r"diplomas?|transcripts?|recommendations?|reference[\s_-]+letters?|passports?|"
    r"national[\s_-]+id|identity|id[\s_-]*card|ids?|attendance|awards?|appreciation|"
    r"essays?|thesis|independence[\s_-]+and[\s_-]+availability)(?![a-z])"
    r"|شهادة|شهادات|إفادة|افادة|تزكية|جواز|هوية|إقرار|اقرار",
    re.I)
# Weaker words: supporting only when the name carries no job title
# ("Education Expert, Training & Capacity Development" is a CV).
_WEAK_SUPPORTING_NAME = re.compile(
    r"(?<![a-z])(?:training|trainings|courses?|workshops?|forms?|letters?)(?![a-z])", re.I)
_JOB_TITLE_NAME = re.compile(
    r"(?<![a-z])(?:expert|specialist|consultant|manager|coordinator|officer|leader|"
    r"analyst|researcher|engineer|advisor|adviser|director|evaluator|trainer|"
    r"facilitator|enumerator|supervisor|lead)(?![a-z])", re.I)

# Folder names count only with strong words: role folders such as
# "vocational education and training (TVET) - TVET Expert" hold real CVs.
_SUPPORTING_FOLDER = re.compile(
    r"(?<![a-z])(?:certificates?|certifications?|certs|declarations?|diplomas?|"
    r"transcripts?|passports?|national[\s_-]+id|independence[\s_-]+and[\s_-]+availability)"
    r"(?![a-z])|شهادات|جواز|هوية",
    re.I)

SUPPORTING_PENALTY = 60
CV_THRESHOLD = 40          # content evidence alone that makes an unnamed file a CV


def _content_score(profile: dict) -> tuple[int, list]:
    """Evidence of a professional CV in the parsed fields (0–70)."""
    why = []
    roles = [r for r in (profile.get("roles") or []) if r]
    years = profile.get("years_experience")
    edu = profile.get("education") or []
    langs = profile.get("languages") or []
    score = 0
    if roles:
        score += 15 * min(len(roles), 2)
        why.append(f"{len(roles)} role(s)")
    if years is not None:
        score += 20
        why.append("years of experience")
    if edu:
        score += 10
        why.append("education")
    if langs and (roles or years is not None):
        score += 10
        why.append("languages with work history")
    return score, why


def classify_document(profile: dict) -> dict:
    """Return ``document_type``, ``cv_likeness_score`` (0–100) and the evidence."""
    rel = str(profile.get("source_rel_path") or profile.get("source_file_name") or "")
    parts = PurePath(rel.replace("\\", "/")).parts
    file_name = parts[-1] if parts else ""
    folders = " ".join(parts[1:-1])          # below the country folder
    named_cv = bool(_CV_NAME.search(file_name))
    supporting = (
        bool(_SUPPORTING_NAME.search(file_name))
        or (bool(_WEAK_SUPPORTING_NAME.search(file_name))
            and not _JOB_TITLE_NAME.search(file_name))
        or (bool(_SUPPORTING_FOLDER.search(folders)) and not _CV_NAME.search(folders)))
    content, why = _content_score(profile)

    score = content + (30 if named_cv else 0)
    if supporting and not named_cv:
        score -= SUPPORTING_PENALTY
        doc_type = "SUPPORTING_DOCUMENT"
        why.insert(0, "named as a supporting document")
    elif named_cv:
        doc_type = "CV"
        why.insert(0, "named as a CV/resume")
    elif content >= CV_THRESHOLD:
        doc_type = "CV"
    else:
        doc_type = "UNKNOWN"
    return {"document_type": doc_type,
            "cv_likeness_score": max(0, min(100, score)),
            "document_type_evidence": why}


def with_document_type(profile: dict) -> dict:
    """Profile plus its document-type fields; provenance and parsed facts kept."""
    return {**profile, **classify_document(profile)}
