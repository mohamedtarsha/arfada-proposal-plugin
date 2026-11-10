"""Scan the Winning Proposal Library → local exemplar index/cache (gitignored).

Discovers project folders, pairs TOR↔Proposal, extracts section exemplars +
Writing/Formatting DNA + response patterns. No OCR; scanned/unreadable docs warn.
Transactional + incremental (by path+mtime). Cache lives under
~/.arfada-proposal/exemplars/ and is NEVER committed.

Confidentiality: section text is cached locally only; the final report and Git
contain NO corpus content.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Optional

from ..gknowledge.paths import arfada_home
from ..assignment_type import infer_assignment_type
from . import dna as D

_DEPS = Path(__file__).resolve().parent.parent.parent.parent / ".mcp_deps"
if _DEPS.exists() and str(_DEPS) not in sys.path:
    sys.path.insert(0, str(_DEPS))

_DOCX = ".docx"
_PDF = ".pdf"

# Filename clues. Use LETTER boundaries (?<![a-z]) … (?![a-z]) instead of \b so a
# token glued to an underscore/digit/hyphen still matches — e.g. "ToR_NRC",
# "BHA_TOR_Endline", "RFQ_Section", "Annex-1-ToRs", "TOR_-_SRRVCM". A plain \b fails
# on "tor_" because "_" is a word char (no boundary). Letters-only lookaround also
# avoids false hits inside words ("tortoise", "contractor", "technically").
def _lb(*cues: str) -> "re.Pattern":
    body = "|".join(cues)
    return re.compile(rf"(?<![a-z])(?:{body})(?![a-z])", re.I)

# TOR / tender / schedule-of-requirements family (all are "the requirements doc").
_TOR_RE = _lb("tor", "tors", "terms of reference", "terms_of_reference",
              "tender", "rfp", "rfq", "scope of work", "schedule of requirements")
# "annex" counts as a TOR cue only when a TOR/terms token is also present in the name.
_ANNEX_TOR_RE = re.compile(r"annex.*(?<![a-z])tors?(?![a-z])|(?<![a-z])tors?(?![a-z]).*annex", re.I)
_PROP_RE = _lb("proposal", "technical", "arfada", "offer", "submission")
# demote these as proposal candidates (not the submitted technical proposal)
_PROP_DEMOTE_RE = _lb("cover letter", "cover_letter", "coverletter", "annex",
                      "draft", "old", "comment", "comments", "backup", "copy")
# boost these as the submitted/final technical proposal
_PROP_BOOST_RE = _lb("proposal", "technical", "final", "submitted")


def exemplar_cache_dir() -> Path:
    d = arfada_home() / "exemplars"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _mtime(p: Path) -> str:
    try:
        return datetime.datetime.fromtimestamp(p.stat().st_mtime, datetime.timezone.utc).isoformat()
    except Exception:
        return ""


def _hash(p: Path) -> str:
    try:
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()[:16]
    except Exception:
        return ""


def _available(p: Path) -> bool:
    try:
        st = p.stat()
        if st.st_size == 0:
            return False
        attrs = getattr(st, "st_file_attributes", 0)
        if attrs and (attrs & 0x1000):  # offline placeholder
            return False
        with p.open("rb") as f:
            f.read(1)
        return True
    except Exception:
        return False


def _docx_text(p: Path) -> str:
    try:
        from docx import Document
        return "\n".join(par.text for par in Document(str(p)).paragraphs)
    except Exception:
        return ""


def _pdf_sections(p: Path) -> list[dict]:
    """Extract sections from a text-extractable PDF proposal (no OCR).

    Splits page text into sections on short heading-like lines and classifies each
    by keyword. Returns [] for scanned/image-only PDFs (no extractable text).
    """
    try:
        from pypdf import PdfReader
        pages = [(pg.extract_text() or "") for pg in PdfReader(str(p)).pages]
    except Exception:
        return []
    text = "\n".join(pages).strip()
    if len(text.split()) < 40:          # effectively no extractable text
        return []
    sections: list[dict] = []
    cur = {"heading": "", "type": "OTHER", "paras": [], "bullets": 0, "numbered": 0, "tables": 0}

    def flush():
        if cur["paras"] or cur["heading"]:
            sections.append({"heading": cur["heading"], "type": cur["type"],
                             "text": "\n".join(cur["paras"]).strip(),
                             "bullets": cur["bullets"], "numbered": cur["numbered"],
                             "tables": 0, "paragraphs": len(cur["paras"])})

    heading_re = re.compile(
        r"^(?:\d+(?:\.\d+)*\.?\s+\S|[A-Z][A-Za-z /&-]{3,60})$")
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        looks_heading = (len(line) <= 70 and heading_re.match(line)
                         and D.classify_section(line) != "OTHER")
        if looks_heading:
            flush()
            cur = {"heading": line, "type": D.classify_section(line), "paras": [],
                   "bullets": 0, "numbered": 0, "tables": 0}
        else:
            if line[:1] in "-•*–":
                cur["bullets"] += 1
            cur["paras"].append(line)
    flush()
    return [s for s in sections if s["text"]]


def _project_dirs(root: Path) -> list[Path]:
    """A project dir is a leaf-ish folder containing at least one docx/pdf."""
    out = []
    for d in root.rglob("*"):
        if not d.is_dir():
            continue
        docs = [f for f in d.iterdir() if f.is_file()
                and f.suffix.lower() in (_DOCX, _PDF) and not f.name.startswith("~$")]
        if docs:
            out.append(d)
    return out


def _is_tor_name(name: str) -> bool:
    return bool(_TOR_RE.search(name) or _ANNEX_TOR_RE.search(name))


def _classify_docs(proj: Path):
    tors, props, others = [], [], []
    for f in proj.iterdir():
        if not f.is_file() or f.name.startswith("~$"):
            continue
        ext = f.suffix.lower()
        if ext not in (_DOCX, _PDF):
            continue
        name = f.name
        if _is_tor_name(name):
            tors.append(f)
        elif _PROP_RE.search(name):
            props.append(f)
        else:
            others.append(f)
    return tors, props, others


def _proposal_score(f: Path) -> int:
    """Rank proposal candidates: prefer the submitted/final technical proposal;
    demote cover letters / drafts / annexes; prefer DOCX over PDF only as a tiebreak
    (a text-extractable PDF proposal is still a valid exemplar)."""
    name = f.name
    score = 0
    if _PROP_BOOST_RE.search(name):
        score += 5
    if _PROP_DEMOTE_RE.search(name):
        score -= 6
    # a clear "proposal" token outweighs a generic org-name match
    if re.search(r"(?<![a-z])proposal(?![a-z])", name, re.I):
        score += 3
    if f.suffix.lower() == _DOCX:
        score += 1
    return score


def _pick_proposal(props: list[Path], others: list[Path]) -> Optional[Path]:
    """Pick the submitted technical proposal via scoring (cover letters/drafts demoted).

    PDF proposals remain eligible (score tiebreak only). `others` (files that matched
    neither TOR nor proposal cues) are considered as a last resort.
    """
    candidates = list(props) + [f for f in others if f.suffix.lower() in (_DOCX, _PDF)]
    if not candidates:
        return None
    # drop clearly-non-proposal files (cover letters) if any real proposal remains
    ranked = sorted(candidates, key=lambda f: -_proposal_score(f))
    best = ranked[0]
    # if the best scored candidate is still a demoted file AND a non-demoted exists, take that
    if _PROP_DEMOTE_RE.search(best.name):
        non_demoted = [f for f in ranked if not _PROP_DEMOTE_RE.search(f.name)]
        if non_demoted:
            best = non_demoted[0]
    return best


def _country_of(proj: Path, root: Path) -> str:
    try:
        rel = proj.relative_to(root).parts
        return rel[0] if rel else ""
    except Exception:
        return ""


def scan_library(root: str | Path, cache_dir: Optional[Path] = None) -> dict:
    """Scan the library → exemplar index + corpus DNA. Transactional, incremental."""
    root = Path(root).expanduser()
    cache_dir = Path(cache_dir) if cache_dir else exemplar_cache_dir()
    report: dict = {"started_at": _now(), "library_root": str(root)}
    if not root.exists() or not root.is_dir():
        return {**report, "ok": False, "error": f"Library root not found: {root}"}

    prev = _load_index(cache_dir)
    prev_by_id = {e["exemplar_id"]: e for e in prev.get("exemplars", [])}

    exemplars = []
    section_store: dict[str, list] = {}   # exemplar_id -> [sections] (local only)
    per_doc_dna, per_doc_fmt, per_doc_resp = [], [], []
    countries, atypes = set(), set()
    warnings = []
    pairs = ambiguous = unreadable = 0
    added = updated = unchanged = 0

    for proj in _project_dirs(root):
        tors, props, others = _classify_docs(proj)
        proposal = _pick_proposal(props, others)
        # AMBIGUOUS: multiple TOR-like files with no identifiable proposal → cannot pair
        if len(tors) > 1 and proposal is None:
            ambiguous += 1
            warnings.append(f"AMBIGUOUS pairing in {proj.name} ({len(tors)} TOR-like files, "
                            "no proposal)")
            continue
        if proposal is None:
            # a folder with only TOR/annex files and no proposal — nothing to learn from
            continue
        tor = tors[0] if tors else None

        exemplar_id = "ex_" + hashlib.sha1(str(proj).encode()).hexdigest()[:12]
        mtime = _mtime(proposal)
        country = _country_of(proj, root)

        # incremental: reuse if unchanged
        if exemplar_id in prev_by_id and prev_by_id[exemplar_id].get("proposal_mtime") == mtime:
            e = prev_by_id[exemplar_id]
            exemplars.append(e); unchanged += 1
            # reuse cached DNA inputs
            sects = _load_sections(cache_dir, exemplar_id)
            if sects:
                per_doc_dna.append(D.writing_dna_for_doc(sects))
                per_doc_fmt.append(D.formatting_dna_for_doc(sects))
                per_doc_resp.append(D.response_patterns_for_doc(sects))
                section_store[exemplar_id] = sects
            countries.add(country); atypes.add(e.get("assignment_type", ""))
            pairs += 1 if e.get("tor_file") else 0
            continue

        if not _available(proposal):
            unreadable += 1
            warnings.append(f"Proposal not readable locally: {proj.name}")
            continue
        if proposal.suffix.lower() == _DOCX:
            try:
                sections = D.docx_sections(proposal)
            except Exception:
                unreadable += 1
                warnings.append(f"Could not parse proposal DOCX: {proj.name}")
                continue
        else:
            # PDF proposal: usable as an exemplar when text is extractable (no OCR).
            sections = _pdf_sections(proposal)
            if not sections:
                # genuinely scanned/image-only → metadata-only, warn (not unreadable)
                warnings.append(f"PDF proposal has no extractable text (scanned?) — "
                                f"metadata only: {proj.name}")

        # infer assignment type from TOR text or folder/file names
        atype = _infer_type(tor, proj)
        methods = D.response_patterns_for_doc(sections).get("methods", []) if sections else []

        e = {
            "exemplar_id": exemplar_id,
            "country": country,
            "region": "MENA",
            "project_folder": proj.name,
            "assignment_type": atype,
            "proposal_language": _language(sections),
            "tor_file": tor.name if tor else "",
            "proposal_file": proposal.name,
            "section_inventory": sorted({s["type"] for s in sections if s["type"] != "OTHER"}),
            "methods": methods,
            "proposal_mtime": mtime,
            "proposal_hash": _hash(proposal),
        }
        exemplars.append(e)
        if exemplar_id in prev_by_id:
            updated += 1
        else:
            added += 1
        if sections:
            _save_sections(cache_dir, exemplar_id, sections)
            section_store[exemplar_id] = sections
            per_doc_dna.append(D.writing_dna_for_doc(sections))
            per_doc_fmt.append(D.formatting_dna_for_doc(sections))
            per_doc_resp.append(D.response_patterns_for_doc(sections))
        countries.add(country)
        atypes.add(atype)
        if tor:
            pairs += 1

    writing = D.aggregate_writing_dna(per_doc_dna)
    formatting = D.aggregate_formatting_dna(per_doc_fmt)
    responses = D.aggregate_response_patterns(per_doc_resp)

    index = {
        "schema_version": "1",
        "synced_at": _now(),
        "library_root": str(root),
        "exemplars": exemplars,
        "writing_dna": writing,
        "formatting_dna": formatting,
        "response_patterns": responses,
        "countries": sorted(c for c in countries if c),
        "assignment_types": sorted(a for a in atypes if a),
    }
    _save_index(cache_dir, index)

    return {
        **report, "ok": True,
        "countries": sorted(c for c in countries if c),
        "project_folders": len(exemplars),
        "valid_pairs": pairs,
        "ambiguous": ambiguous,
        "unreadable": unreadable,
        "assignment_types": sorted(a for a in atypes if a),
        "added": added, "updated": updated, "unchanged": unchanged,
        "writing_dna": writing,
        "warnings": warnings[:20],
        "finished_at": _now(),
    }


def _infer_type(tor: Optional[Path], proj: Path) -> str:
    text = ""
    if tor and tor.suffix.lower() == _DOCX and _available(tor):
        text = _docx_text(tor)
    meta = {"assignment": {"value": (text[:400] + " " + proj.name)}}
    res = infer_assignment_type(meta, [])
    return res.assignment_type if res.assignment_type != "UNRESOLVED" else "OTHER"


def _language(sections: list) -> str:
    text = " ".join(s["text"] for s in sections[:5])
    ar = sum(1 for c in text if "؀" <= c <= "ۿ")
    return "arabic" if ar > len(text) * 0.3 else "english"


# ---------------------------------------------------------------------------
# cache I/O (local only; section text never committed)
# ---------------------------------------------------------------------------

def _index_path(cache_dir: Path) -> Path:
    return cache_dir / "exemplar_index.json"


def _sections_path(cache_dir: Path, exemplar_id: str) -> Path:
    d = cache_dir / "sections"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{exemplar_id}.json"


def _atomic(path: Path, data) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise


def _save_index(cache_dir: Path, index: dict) -> None:
    _atomic(_index_path(cache_dir), index)


def _load_index(cache_dir: Path) -> dict:
    p = _index_path(cache_dir)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_sections(cache_dir: Path, exemplar_id: str, sections: list) -> None:
    _atomic(_sections_path(cache_dir, exemplar_id), {"sections": sections})


def _load_sections(cache_dir: Path, exemplar_id: str) -> list:
    p = _sections_path(cache_dir, exemplar_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("sections", [])
        except Exception:
            return []
    return []
