"""FileStore — lightweight adapter that feeds PE2's extractor from a local PDF/DOCX.

Implements the same interface as PE2's TORStore (documents / blocks / tables /
cells / sections / section_text / assignment) without any SQLite dependency.
One FileStore instance covers one TOR file for a single analysis run.

DOCX: walks OOXML body in document order (paragraphs + tables interleaved).
PDF:  extracts text per page via pypdf; heuristically classifies headings and lists.
Tables: captured from DOCX; not extracted from PDF (text-only for now).
Page numbers: available for PDF; set to None for DOCX (not easily accessible).
Arabic / RTL text: preserved as-is (no normalization).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def file_store(file_path: str | Path) -> "FileStore":
    """Return a FileStore for a PDF or DOCX file."""
    p = Path(file_path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"TOR file not found: {p}")
    ext = p.suffix.lower()
    if ext == ".docx":
        return FileStore(p, *_extract_docx(p))
    elif ext == ".pdf":
        return FileStore(p, *_extract_pdf(p))
    else:
        raise ValueError(f"Unsupported format '{ext}'. Use .pdf or .docx")


# ---------------------------------------------------------------------------
# Store interface
# ---------------------------------------------------------------------------

class FileStore:
    """Minimal store interface that PE2's extractor.py expects.

    All heavy lifting (parsing) is done up front in _extract_docx/_extract_pdf.
    Every public method is O(n) over already-loaded data.
    """

    def __init__(
        self,
        file_path: Path,
        doc_id: str,
        blocks: list[dict],
        tables: list[dict],
        cells_by_table: dict[str, list[dict]],
    ):
        self._path = file_path
        self._doc_id = doc_id
        self._blocks = blocks
        self._tables = tables
        self._cells_by_table = cells_by_table
        self._sections: Optional[list[dict]] = None  # lazy

    # --- documents ---------------------------------------------------------

    def documents(self, aid: str, roles=None):
        return [{"document_id": self._doc_id, "file_path": str(self._path),
                 "role": "TOR", "file_name": self._path.name}]

    # --- blocks ------------------------------------------------------------

    def blocks(self, did: str) -> list[dict]:
        return self._blocks if did == self._doc_id else []

    def block(self, did: str, sequence: int) -> Optional[dict]:
        for b in self._blocks:
            if b["sequence"] == sequence and did == self._doc_id:
                return b
        return None

    # --- tables / cells ----------------------------------------------------

    def tables(self, did: str) -> list[dict]:
        return self._tables if did == self._doc_id else []

    def cells(self, table_id: str) -> list[dict]:
        return self._cells_by_table.get(table_id, [])

    def cell(self, table_id: str, row: int, col: int) -> Optional[dict]:
        for c in self._cells_by_table.get(table_id, []):
            if c["row_index"] == row and c["col_index"] == col:
                return c
        return None

    # --- sections ----------------------------------------------------------

    def sections(self, did: str) -> list[dict]:
        if did != self._doc_id:
            return []
        if self._sections is None:
            self._sections = _build_sections(self._blocks, self._doc_id)
        return self._sections

    def section_text(self, did: str, start: Optional[int], end: Optional[int]) -> tuple[str, list]:
        if did != self._doc_id:
            return "", []
        blks = [b for b in self._blocks
                if b["sequence"] is not None
                and (start is None or b["sequence"] >= start)
                and (end is None or b["sequence"] < end)
                and b["block_type"] != "TABLE_CELL"]
        text = "\n".join(b["plain_text"] for b in blks if b["plain_text"])
        return text, blks

    # --- assignment metadata -----------------------------------------------

    def assignment(self, aid: str) -> dict:
        return {"project_title": "", "assignment_id": aid,
                "file_name": self._path.name, "file_path": str(self._path)}

    # --- passthrough used by structuring / checks --------------------------

    def meta(self, key: str, default=None):
        return default


# ---------------------------------------------------------------------------
# DOCX extraction
# ---------------------------------------------------------------------------

def _extract_docx(path: Path):
    from docx import Document

    doc = Document(str(path))
    doc_id = _doc_id(path)
    blocks: list[dict] = []
    tables: list[dict] = []
    cells_by_table: dict[str, list[dict]] = {}
    seq = 0
    tbl_seq = 0

    for child in doc.element.body:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "p":
            from docx.text.paragraph import Paragraph as _Para
            para = _Para(child, doc)
            text = (para.text or "").strip()
            if not text:
                seq += 1
                continue
            style_name = (para.style.name or "") if para.style else ""
            bt = _docx_block_type(para, style_name, text)
            # strip leading bullet chars from list items
            if bt == "LIST_ITEM":
                text = _strip_bullet(text)
            blocks.append({"block_type": bt, "plain_text": text,
                           "sequence": seq, "meta_json": "{}"})
            seq += 1

        elif tag == "tbl":
            from docx.table import Table as _Table
            tbl = _Table(child, doc)
            tbl_id = f"tbl_{tbl_seq}"
            tbl_seq += 1
            caption = ""
            cell_list: list[dict] = []
            seen_text: set[str] = set()

            for r_idx, row in enumerate(tbl.rows):
                for c_idx, cell in enumerate(row.cells):
                    ct = (cell.text or "").strip()
                    if not ct or ct in seen_text:
                        continue
                    seen_text.add(ct)
                    locator = f"{tbl_id}:r{r_idx}c{c_idx}"
                    cell_list.append({"text": ct, "row_index": r_idx, "col_index": c_idx,
                                      "table_id": tbl_id, "locator": locator})
                    # Also emit as a TABLE_CELL block so the section-based
                    # extraction also sees table content.
                    blocks.append({"block_type": "TABLE_CELL", "plain_text": ct,
                                   "sequence": seq, "meta_json": json.dumps({"locator": locator}),
                                   "table_id": tbl_id})
                    seq += 1
                    if r_idx == 0 and c_idx == 0:
                        caption = ct[:80]

            tables.append({"table_id": tbl_id, "caption": caption, "document_id": doc_id})
            cells_by_table[tbl_id] = cell_list

    return doc_id, blocks, tables, cells_by_table


_HEADING_STYLE = re.compile(r"heading\s*\d+|titre\s*\d+|überschrift\s*\d+", re.I)
_LIST_STYLE = re.compile(r"list\s+(?:bullet|number|continue|paragraph)|^list$|^li\s", re.I)
_BULLET_CHARS = ("•", "·", "◦", "▪", "▸", "►", "○", "●", "–", "—", "-", "*")


def _docx_block_type(para, style_name: str, text: str) -> str:
    if _HEADING_STYLE.match(style_name):
        return "HEADING"
    # named list styles (e.g. "List Bullet", "List Number", "List Paragraph")
    if _LIST_STYLE.search(style_name):
        return "LIST_ITEM"
    # numbered/bulleted list via OOXML numPr
    try:
        if para._p.pPr is not None and para._p.pPr.numPr is not None:
            return "LIST_ITEM"
    except Exception:
        pass
    # bullet character heuristic
    if text and text[0] in _BULLET_CHARS and len(text) > 2:
        return "LIST_ITEM"
    return "PARAGRAPH"


def _strip_bullet(text: str) -> str:
    if text and text[0] in _BULLET_CHARS:
        return text[1:].lstrip()
    return text


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

_HEADING_PATTERNS = re.compile(
    r"^(?:"
    r"\d+(?:\.\d+)*\.?\s+[A-Z؀-ۿ]"       # 1. Title / 1.2 Title
    r"|[IVXLCDM]+\.\s+[A-Z؀-ۿ]"           # IV. Title
    r"|[A-Z][A-Z\s]{4,}$"                            # ALL CAPS LINE
    r"|(?:section|part|annex)\s+\w"                  # Section X
    r")",
    re.UNICODE,
)
_BULLET_LINE = re.compile(r"^[\•\·\◦\▪\▸\►\○\●\–\—\-\*]\s+\S")


def _extract_pdf(path: Path):
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    doc_id = _doc_id(path)
    blocks: list[dict] = []
    seq = 0

    for page_num, page in enumerate(reader.pages, 1):
        raw = page.extract_text() or ""
        lines = [ln.rstrip() for ln in raw.splitlines()]
        para_buf: list[str] = []

        def flush_para(page_n: int):
            nonlocal seq
            text = " ".join(para_buf).strip()
            para_buf.clear()
            if len(text) < 4:
                return
            bt = "PARAGRAPH"
            if _HEADING_PATTERNS.match(text):
                bt = "HEADING"
            elif _BULLET_LINE.match(text):
                bt = "LIST_ITEM"
                text = text[2:].lstrip()
            blocks.append({"block_type": bt, "plain_text": text,
                           "sequence": seq, "meta_json": json.dumps({"page": page_n})})
            seq += 1

        for line in lines:
            stripped = line.strip()
            if not stripped:
                flush_para(page_num)
                continue
            # Short ALL-CAPS line is likely a heading
            if _HEADING_PATTERNS.match(stripped):
                flush_para(page_num)
                blocks.append({"block_type": "HEADING", "plain_text": stripped,
                               "sequence": seq, "meta_json": json.dumps({"page": page_num})})
                seq += 1
                continue
            if _BULLET_LINE.match(stripped):
                flush_para(page_num)
                blocks.append({"block_type": "LIST_ITEM", "plain_text": stripped[2:].lstrip(),
                               "sequence": seq, "meta_json": json.dumps({"page": page_num})})
                seq += 1
                continue
            para_buf.append(stripped)
        flush_para(page_num)

    return doc_id, blocks, [], {}  # PDF: no structured tables


# ---------------------------------------------------------------------------
# Sections derived from HEADING blocks
# ---------------------------------------------------------------------------

def _build_sections(blocks: list[dict], doc_id: str) -> list[dict]:
    sections: list[dict] = []
    headings = [b for b in blocks if b["block_type"] == "HEADING"]
    all_seqs = [b["sequence"] for b in blocks]
    max_seq = max(all_seqs) + 1 if all_seqs else 0

    for i, h in enumerate(headings):
        end_seq = headings[i + 1]["sequence"] if i + 1 < len(headings) else max_seq
        sec_id = "sec_" + hashlib.sha1(
            f"{doc_id}|{h['sequence']}|{h['plain_text']}".encode()
        ).hexdigest()[:12]
        sections.append({
            "section_id": sec_id,
            "document_id": doc_id,
            "heading_text": h["plain_text"],
            "section_path": h["plain_text"],
            "start_block_sequence": h["sequence"],
            "end_block_sequence": end_seq,
            "level": 1,
        })
    return sections


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _doc_id(path: Path) -> str:
    h = hashlib.sha1(str(path).encode()).hexdigest()[:12]
    return f"doc_{h}"
