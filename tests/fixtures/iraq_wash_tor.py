"""A second, unrelated synthetic TOR (.docx) for generic claim-gating regressions.

Different country, client, sector and assignment type from South Darfur: a WASH
baseline survey in Ninewa, Iraq for NRC, with an explicit submission e-mail and a
clear deadline, CVs required, no registration requirement and consistent figures.
"""
from __future__ import annotations

from pathlib import Path

TITLE = "Baseline Survey for the Ninewa WASH Resilience Project"


def build(path: Path) -> Path:
    from docx import Document
    d = Document()
    d.add_paragraph("Terms of Reference", style="Title")
    d.add_heading(TITLE, level=1)
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text = "Location", "Mosul and Tel Afar districts, Ninewa, Iraq"
    t.cell(1, 0).text, t.cell(1, 1).text = "Duration", "45 days"
    d.add_heading("1. Background", level=1)
    d.add_paragraph(
        "NRC is seeking a qualified firm to conduct a baseline survey for its WASH resilience "
        "project. The project will reach 4,000 households. Current access to safe water: "
        "Low: 35%, Medium: 40%, High: 25%.")
    d.add_heading("2. Methodology", level=1)
    d.add_paragraph("A household survey with focus group discussions and key informant "
                    "interviews will establish the baseline values for all logframe indicators.")
    d.add_heading("3. Proposal requirements", level=1)
    d.add_paragraph("The proposal must include:")
    for x in ("Technical proposal: methodology, sampling and work plan.",
              "Financial proposal: detailed budget in USD.",
              "CVs of the proposed team members."):
        d.add_paragraph(x, style="List Number")
    d.add_heading("4. Submission", level=1)
    d.add_paragraph("Proposals must be submitted by e-mail to iq.tenders@nrc.example.org no later "
                    "than 15 March 2030, 17:00 Baghdad time.")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    d.save(str(path))
    return path
