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

# filename clues
_TOR_RE = re.compile(r"\b(tor|tors|terms?\s*of\s*reference|annex\s*\d*\s*-?\s*tor|rfp|rfq)\b", re.I)
_PROP_RE = re.compile(r"\b(proposal|technical|arfada|offer|submission)\b", re.I)


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


def _classify_docs(proj: Path):
    tors, props, others = [], [], []
    for f in proj.iterdir():
        if not f.is_file() or f.name.startswith("~$"):
            continue
        ext = f.suffix.lower()
        if ext not in (_DOCX, _PDF):
            continue
        name = f.name
        if _TOR_RE.search(name):
            tors.append(f)
        elif _PROP_RE.search(name):
            props.append(f)
        else:
            others.append(f)
    return tors, props, others


def _pick_proposal(props: list[Path], others: list[Path]) -> Optional[Path]:
    # prefer a DOCX proposal; fall back to any docx; then pdf
    docx = [f for f in props if f.suffix.lower() == _DOCX]
    if docx:
        return docx[0]
    if props:
        return props[0]
    docx_other = [f for f in others if f.suffix.lower() == _DOCX]
    return docx_other[0] if docx_other else (others[0] if others else None)


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
        if proposal.suffix.lower() != _DOCX:
            warnings.append(f"Proposal is PDF (section extraction limited): {proj.name}")
            # still record metadata-only exemplar
            sections = []
        else:
            try:
                sections = D.docx_sections(proposal)
            except Exception:
                unreadable += 1
                warnings.append(f"Could not parse proposal DOCX: {proj.name}")
                continue

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
