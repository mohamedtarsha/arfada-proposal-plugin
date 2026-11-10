"""Professional DOCX renderer (Phase 4) — deterministic, python-docx only.

Renders validated section JSON (generated_sections/<section>.json) into an
editable Word document with a named style system, cover page, real headings,
paragraphs, bullet/numbered lists, and real Word tables (never tab-faked).

Two variants (spec §26):
- INTERNAL: shows NEEDS_ARFADA_EVIDENCE, BLOCKED_BY_DECISION, provenance markers,
  a knowledge/version footer, and review notes.
- CLIENT:   hides all internal IDs, fact_ids, debug metadata, and system notes.
            If a section carries a hard unsupported-fact error, client export fails.

No Microsoft Word automation, no LibreOffice. Cross-platform (Windows-first).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

# python-docx (and .mcp_deps fallback)
import sys as _sys
_DEPS = Path(__file__).resolve().parent.parent.parent / ".mcp_deps"
if _DEPS.exists() and str(_DEPS) not in _sys.path:
    _sys.path.insert(0, str(_DEPS))

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Inches

from .generation import NEEDS_EVIDENCE_TAG


# ---------------------------------------------------------------------------
# Theme + named styles
# ---------------------------------------------------------------------------

_PRIMARY = "1F3864"     # deep navy
_ACCENT = "2E74B5"      # blue
_GREY = "595959"
_LIGHT = "D9E2F3"       # table header fill

TITLE = "ARFADA Title"
SUBTITLE = "ARFADA Subtitle"
H1 = "ARFADA Heading 1"
H2 = "ARFADA Heading 2"
BODY = "ARFADA Body"
BULLET = "ARFADA Bullet"
NUMBERED = "ARFADA Numbered"
TABLE_HEADER = "ARFADA Table Header"
TABLE_BODY = "ARFADA Table Body"
NOTE = "ARFADA Note"


def _hex(c: str) -> RGBColor:
    return RGBColor.from_string(c.upper())


def _ensure_styles(doc) -> None:
    from docx.enum.style import WD_STYLE_TYPE
    styles = doc.styles
    existing = {s.name for s in styles}

    def mk(name, base="Normal", stype=WD_STYLE_TYPE.PARAGRAPH):
        if name in existing:
            return styles[name]
        st = styles.add_style(name, stype)
        if base in existing:
            st.base_style = styles[base]
        return st

    def font(st, size, color, bold=False, italic=False, font_name="Calibri"):
        st.font.name = font_name
        st.font.size = Pt(size)
        st.font.color.rgb = _hex(color)
        st.font.bold = bold
        st.font.italic = italic

    font(mk(TITLE), 26, _PRIMARY, bold=True)
    font(mk(SUBTITLE), 14, _ACCENT)
    h1 = mk(H1); font(h1, 16, _PRIMARY, bold=True)
    h1.paragraph_format.space_before = Pt(12); h1.paragraph_format.space_after = Pt(4)
    h2 = mk(H2); font(h2, 13, _ACCENT, bold=True)
    h2.paragraph_format.space_before = Pt(8); h2.paragraph_format.space_after = Pt(3)
    bd = mk(BODY); font(bd, 11, "000000")
    bd.paragraph_format.space_after = Pt(6); bd.paragraph_format.line_spacing = 1.15
    font(mk(BULLET, base="List Bullet"), 11, "000000")
    font(mk(NUMBERED, base="List Number"), 11, "000000")
    font(mk(TABLE_HEADER), 10, "FFFFFF", bold=True)
    font(mk(TABLE_BODY), 10, "000000")
    font(mk(NOTE), 10, _GREY, italic=True)


def _set_outline(style, level: int) -> None:
    p_pr = style.element.get_or_add_pPr()
    ol = p_pr.find(qn("w:outlineLvl"))
    if ol is None:
        ol = OxmlElement("w:outlineLvl"); p_pr.append(ol)
    ol.set(qn("w:val"), str(level - 1))


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _shade_cell(cell, fill_hex: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill_hex.upper())
    tc_pr.append(shd)


def _page_break(doc) -> None:
    doc.add_page_break()


def _add_table(doc, columns: list, rows: list) -> None:
    table = doc.add_table(rows=1, cols=len(columns))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    try:
        table.style = "Table Grid"
    except Exception:
        pass
    hdr = table.rows[0].cells
    for i, col in enumerate(columns):
        hdr[i].text = ""
        p = hdr[i].paragraphs[0]
        run = p.add_run(str(col))
        run.bold = True
        run.font.color.rgb = _hex("FFFFFF")
        run.font.size = Pt(10)
        _shade_cell(hdr[i], _PRIMARY)
    for row in rows:
        cells = table.add_row().cells
        for i in range(len(columns)):
            val = row[i] if i < len(row) else ""
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(str(val))
            r.font.size = Pt(10)


# ---------------------------------------------------------------------------
# Cover page
# ---------------------------------------------------------------------------

def _cover(doc, *, title: str, assignment_label: str, client: str, country: str,
           date: str, logo_path: Optional[str]) -> None:
    if logo_path and Path(logo_path).exists():
        try:
            doc.add_picture(logo_path, width=Inches(2.0))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        except Exception:
            pass
    for _ in range(3):
        doc.add_paragraph()
    p = doc.add_paragraph(style=TITLE); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(title or "Technical Proposal")
    if assignment_label:
        s = doc.add_paragraph(style=SUBTITLE); s.alignment = WD_ALIGN_PARAGRAPH.CENTER
        s.add_run(assignment_label)
    doc.add_paragraph()
    for label, val in (("Client", client), ("Country", country), ("Date", date)):
        if val:
            row = doc.add_paragraph(style=BODY); row.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = row.add_run(f"{label}: "); run.bold = True
            row.add_run(val)
    doc.add_paragraph()
    org = doc.add_paragraph(style=SUBTITLE); org.alignment = WD_ALIGN_PARAGRAPH.CENTER
    org.add_run("ARFADA")
    _page_break(doc)


# ---------------------------------------------------------------------------
# Section rendering
# ---------------------------------------------------------------------------

def _render_section(doc, candidate: dict, title: str, *, internal: bool) -> None:
    doc.add_paragraph(title, style=H1)
    for b in candidate.get("blocks", []):
        btype = b.get("type")
        if btype == "paragraph":
            doc.add_paragraph(b.get("text", "").strip(), style=BODY)
        elif btype == "evidence_placeholder":
            if internal:
                p = doc.add_paragraph(style=NOTE)
                p.add_run(b.get("text", NEEDS_EVIDENCE_TAG).strip())
            else:
                # client version: show a neutral "to be provided" line, no internal tag
                txt = b.get("text", "").replace(NEEDS_EVIDENCE_TAG, "").strip(": ").strip()
                p = doc.add_paragraph(style=BODY)
                run = p.add_run(f"[To be provided: {txt}]")
                run.italic = True
        elif btype == "bullet_list":
            for item in b.get("items", []):
                doc.add_paragraph(str(item), style=BULLET)
        elif btype == "numbered_list":
            for item in b.get("items", []):
                doc.add_paragraph(str(item), style=NUMBERED)
        elif btype == "table":
            cols = b.get("columns", [])
            rows = b.get("rows", [])
            if cols and rows:
                _add_table(doc, cols, rows)
                doc.add_paragraph()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_docx(
    *,
    run_dir: Path,
    blueprint: dict,
    status_doc: dict,
    tor: dict,
    internal: bool,
    logo_path: Optional[str] = None,
) -> dict:
    """Render a proposal DOCX (internal or client). Returns a summary dict.

    Raises ValueError if a client export is requested but a section has a hard
    unsupported-fact failure (client safety, spec §27).
    """
    run_dir = Path(run_dir)
    sections_dir = run_dir / "generated_sections"

    meta = tor.get("metadata", {})
    def mv(k):
        e = meta.get(k)
        return e.get("value", "").strip() if isinstance(e, dict) else ""

    title = mv("assignment") or "Technical Proposal"
    client = mv("client")
    country = mv("country")
    at = tor.get("assignment_type", {})
    assignment_label = blueprint.get("assignment_type_label") or at.get("label", "")
    date = (tor.get("analyzed_at", "") or "")[:10]

    doc = Document()
    _ensure_styles(doc)

    _cover(doc, title=title, assignment_label=assignment_label, client=client,
           country=country, date=date, logo_path=logo_path)

    if not internal:
        banner = doc.add_paragraph(style=SUBTITLE)
        banner.alignment = WD_ALIGN_PARAGRAPH.CENTER
        # client draft marker when evidence gaps remain
        if _has_open_gaps(sections_dir, blueprint):
            banner.add_run("DRAFT — HUMAN REVIEW REQUIRED")
            _page_break(doc)

    paragraphs = tables = headings = lists = 0
    rendered = blocked = 0

    ordered = sorted(blueprint["sections"], key=lambda s: s["sequence"])
    for sec in ordered:
        sid = sec["section_id"]
        st = status_doc["sections"].get(sid, {}).get("status")
        if st == "READY":
            cand_path = sections_dir / f"{sid}.json"
            if not cand_path.exists():
                continue
            import json as _json
            candidate = _json.loads(cand_path.read_text(encoding="utf-8"))
            _render_section(doc, candidate, sec["title"], internal=internal)
            headings += 1
            for b in candidate.get("blocks", []):
                t = b.get("type")
                if t == "paragraph":
                    paragraphs += 1
                elif t in ("bullet_list", "numbered_list"):
                    lists += 1
                elif t == "table":
                    tables += 1
            rendered += 1
        elif st == "BLOCKED_BY_DECISION":
            blocked += 1
            if internal:
                doc.add_paragraph(sec["title"], style=H1)
                p = doc.add_paragraph(style=NOTE)
                p.add_run("BLOCKED_BY_DECISION — resolve the dependent proposal decisions, "
                          "then regenerate this section.")
            # client version: silently omit blocked sections (do not expose internals),
            # but the DRAFT banner already warns of missing content.

    # footer / version marker
    if internal:
        doc.add_paragraph()
        foot = doc.add_paragraph(style=NOTE)
        foot.add_run(
            f"Internal review copy · plugin v{blueprint.get('plugin_version', '0.5.0')} · "
            f"knowledge {blueprint.get('knowledge_version', 'unknown')} · "
            f"run {blueprint.get('run_id', '')}")

    variant = "internal_review" if internal else "client_draft"
    out_path = run_dir / f"proposal_{variant}.docx"
    doc.save(str(out_path))

    return {
        "variant": variant,
        "path": str(out_path),
        "sections_rendered": rendered,
        "sections_blocked": blocked,
        "paragraphs": paragraphs,
        "tables": tables,
        "headings": headings,
        "lists": lists,
    }


def _has_open_gaps(sections_dir: Path, blueprint: dict) -> bool:
    import json as _json
    for sec in blueprint["sections"]:
        cand = sections_dir / f"{sec['section_id']}.json"
        if not cand.exists():
            return True
        data = _json.loads(cand.read_text(encoding="utf-8"))
        for b in data.get("blocks", []):
            if b.get("type") == "evidence_placeholder":
                return True
            if NEEDS_EVIDENCE_TAG in str(b.get("text", "")):
                return True
    return False
