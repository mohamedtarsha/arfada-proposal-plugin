"""Build a synthetic South Darfur TOR (.docx) at test time.

The wording is written for the test, not copied from the client's document, but it
follows the structure of the real ZOA TOR: a first-page heading with the assignment
title, a project details table, an organisation introduction ("ZOA is …"), an
end line evaluation measured against an existing baseline, and a numbered list of
what the proposal must include (financial proposal, examples of previous work).
"""
from __future__ import annotations

from pathlib import Path

TITLE = "Final Evaluation for “Support to War Affected Communities in South Darfur Project”"


def build(path: Path, *, variant: str = "table") -> Path:
    from docx import Document
    d = Document()
    d.add_paragraph("Terms of Reference", style="Title")
    if variant == "table":
        d.add_heading(TITLE, level=1)
        t = d.add_table(rows=4, cols=2)
        rows = [("Project title", "Support to War Affected Communities in South Darfur Project"),
                ("Location", "Nyala Shamal and Nyala Janoub localities, South Darfur, Sudan"),
                ("Project period", "July 2026 to December 2026"),
                ("Donor", "Canadian Foodgrains Bank (CFGB) through World Renew")]
        for i, (a, b) in enumerate(rows):
            t.cell(i, 0).text, t.cell(i, 1).text = a, b
    else:   # label paragraph, no table; the location only in running text
        d.add_paragraph("Assignment title: " + TITLE)
    d.add_heading("1. Background", level=1)
    d.add_paragraph(
        "ZOA is an international relief and recovery organisation that supports people "
        "affected by conflict and natural disasters. ZOA has worked in Sudan since 2004. The "
        "project is funded by Canadian Foodgrains Bank and implemented by ZOA and HOPE in "
        "Nyala, South Darfur. It provided four rounds of paper food vouchers to 1,300 "
        "households. A baseline survey was conducted in July 2026 with 243 households.")
    d.add_heading("2. Purpose of the end line evaluation", level=1)
    d.add_paragraph(
        "ZOA is seeking a qualified consultant or firm to conduct the end line evaluation. "
        "The end line evaluation will measure change against the baseline values for FCS, "
        "rCSI and the household hunger scale, and assess the contribution of the project.")
    d.add_heading("3. Methodology", level=1)
    d.add_paragraph(
        "Mixed methods: a household survey of the original caseload compared with the "
        "baseline data, focus group discussions and key informant interviews.")
    d.add_heading("4. Team qualifications", level=1)
    d.add_paragraph("At least 5 years of experience in evaluating food security programmes.",
                    style="List Bullet")
    d.add_heading("5. Deliverables", level=1)
    for x in ("Inception report", "Presentation of findings", "End line evaluation draft report",
              "Final report"):
        d.add_paragraph(x, style="List Bullet")
    d.add_heading("6. Technical proposal requirements", level=1)
    d.add_paragraph("The proposal must include:")
    for x in ("Technical proposal: methodology, work plan, timelines and team composition.",
              "Financial proposal: detailed budget with daily rates and expenses.",
              "Relevant experience: examples of previous baseline surveys or evaluations.",
              "CVs and profiles of team members.",
              "Evidence of registration and company profile."):
        d.add_paragraph(x, style="List Number")
    d.add_heading("7. Submission", level=1)
    d.add_paragraph("Proposals must be submitted to ZOA by 12:00 AM (Sudan time), "
                    "21 November 2026.")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    d.save(str(path))
    return path
