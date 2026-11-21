"""Build a synthetic South Darfur TOR (.pdf) at test time — v0.6.10.

Written for the test (not copied from the client's document), but laid out like the
REAL ZOA PDF that broke v0.6.9, so the extraction pattern is the same:

* page 1 has an indicator table (Indicator | Baseline | Target). pdfplumber emits
  table cells BEFORE the page text, so "Indicator" / "Baseline" cells come first;
* the assignment heading wraps over two lines and is followed, without a blank line,
  by "Terms of Reference (ToR)", "Background" and the first paragraph — extraction
  merges them into ONE long paragraph block;
* the submission list ("Interested parties must submit the following:" then
  "1. Technical Proposal: …", "2. Financial Proposal: …") is typed as HEADING
  blocks, one numbered item wrapping onto a lower-case continuation line;
* the evaluation is an end line / final evaluation against an existing baseline;
* the target areas are written as "Nyala Shamal and Nyala Janoub localities".
"""
from __future__ import annotations

from pathlib import Path

TITLE = "Final Evaluation for “Support to War Affected Communities in South Darfur Project”"


def build(path: Path) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, PageBreak
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors

    font = "Helvetica"
    for cand in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
        if Path(cand).exists():                      # curly quotes need a TTF font
            pdfmetrics.registerFont(TTFont("DejaVu", cand))
            font = "DejaVu"
            break
    body = ParagraphStyle("b", fontName=font, fontSize=10, leading=12, spaceAfter=0)
    title = ParagraphStyle("t", fontName=font, fontSize=13, leading=15, spaceAfter=0)

    story = [
        Paragraph("Final Evaluation for “ Support to War Affected Communities in", title),
        Paragraph("South Darfur Project”", title),
        Paragraph("Terms of Reference (ToR)", body),
        Paragraph("Background", body),
        Paragraph(
            "ZOA is seeking an independent consultant or company to conduct a final "
            "evaluation of its food assistance project in South Darfur, Sudan. The end "
            "line evaluation will assess progress against the established baseline "
            "information in Nyala Shamal and Nyala Janoub localities. The baseline "
            "assessment conducted in July 2026 set baseline figures for the indicators "
            "below.", body),
    ]
    tbl = Table([["Indicator", "Baseline", "Target"],
                 ["Food consumption score", "Poor 40%", "90% acceptable"],
                 ["Reduced coping strategy index", "0-3: 0%", "60% in 0-3"]])
    tbl.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                             ("FONTNAME", (0, 0), (-1, -1), font)]))
    story += [tbl, PageBreak()]
    story += [Paragraph(t, body) for t in (
        "Eligibility Criteria",
        "• Evidence of registration as a consultant or firm.",
        "• Capacity to deploy teams in South Darfur quickly.",
        "Submission Requirements Interested parties must submit the following:",
    )]
    story += [Paragraph(t, body) for t in (
        "1. Technical Proposal: Detailed methodology, work plan and team composition.",
        "2. Financial Proposal: Detailed budget, including daily rates and expenses.",
        "3. Relevant Experience: Provide examples of previous baseline surveys or evaluations.",
        "4. CVs/Profiles of Team Members: Relevant expertise in food security, gender,",
        "and conflict sensitivity.",
        "5. Risk Mitigation Plan: Address potential risks during the survey process.",
        "Selection Criteria:",
        "1. Technical Approach",
        "2. Value for money",
    )]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(path), pagesize=A4).build(story)
    return path
