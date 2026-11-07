"""Generate synthetic TOR test fixtures.

Run once (from plugin root):
    python tests/fixtures/make_fixtures.py

Creates:
    tests/fixtures/synthetic_en.docx   — English TOR with known requirements
    tests/fixtures/synthetic_ar.docx   — Arabic TOR with mixed text
    tests/fixtures/synthetic_en.pdf    — PDF version of the English TOR
"""
from __future__ import annotations

import sys
from pathlib import Path

# allow fpdf2 from .mcp_deps when not in system site-packages
_root = Path(__file__).resolve().parent.parent.parent
_deps = _root / ".mcp_deps"
if _deps.exists() and str(_deps) not in sys.path:
    sys.path.insert(0, str(_deps))

# ---------------------------------------------------------------------------
# DOCX fixtures
# ---------------------------------------------------------------------------

def make_en_docx(path: Path) -> None:
    from docx import Document
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    def h(text, level=1):
        doc.add_heading(text, level=level)

    def p(text):
        doc.add_paragraph(text)

    def li(text):
        doc.add_paragraph(text, style="List Bullet")

    # --- Header ---
    h("TERMS OF REFERENCE", 1)
    p("Final Evaluation of the Resilience Programme in Lebanon")

    h("1. Background", 1)
    p("The programme has been implemented by ARFADA since 2022 in collaboration with WFP.")
    p("The evaluation covers the period 2022–2024 across three governorates.")

    h("2. Objectives", 1)
    p("The objective of this evaluation is to assess the relevance, effectiveness, "
      "efficiency, and sustainability of the programme.")

    h("3. Scope", 1)
    p("The evaluation covers all programme activities implemented between January 2022 and "
      "December 2024 in Bekaa, South Lebanon, and North Lebanon.")

    h("4. Evaluation Questions", 1)
    li("To what extent did the programme achieve its stated objectives?")
    li("What were the key factors enabling or hindering programme effectiveness?")
    li("How cost-efficient was the programme compared to similar interventions?")

    h("5. Methodology", 1)
    p("The consultant shall propose a rigorous mixed-methods evaluation design.")
    p("The methodology must include both quantitative and qualitative components.")
    li("The consultant shall conduct at least 30 Key Informant Interviews (KIIs).")
    li("A minimum of 6 Focus Group Discussions (FGDs) shall be conducted.")
    li("A household survey with a sample of approximately 400 respondents is required.")
    p("The consultant may propose additional methods as appropriate to the evaluation questions.")
    p("CVs of enumerators are not required at the proposal stage.")

    h("6. Deliverables", 1)
    li("Inception Report: within 10 working days of contract signature.")
    li("Draft Evaluation Report: within 45 working days after fieldwork completion.")
    li("Final Evaluation Report: within 15 calendar days after receiving client comments.")
    li("Presentation of findings to stakeholders.")

    h("7. Team Requirements", 1)
    p("The evaluation team must include:")
    li("Team Leader with at least 10 years of experience in programme evaluation.")
    li("One national consultant with knowledge of the Lebanese context.")
    li("At least two trained enumerators for data collection.")

    h("8. Submission Requirements", 1)
    p("Proposals must be submitted by 30 November 2026 at 17:00 Beirut time.")
    p("Technical and financial proposals shall be submitted separately.")
    p("The technical proposal must not exceed 20 pages excluding annexes.")
    p("All proposals shall be submitted in English.")

    h("9. Ethics and Safeguarding", 1)
    p("The consultant must adhere to ARFADA's Child Safeguarding Policy.")
    p("Informed consent must be obtained from all participants.")
    p("Client will provide security briefings before fieldwork begins.")

    # --- Table for scoring ---
    h("10. Scoring Criteria", 1)
    table = doc.add_table(rows=4, cols=2)
    table.style = "Table Grid"
    headers = ["Criteria", "Weight"]
    for i, h_text in enumerate(headers):
        table.rows[0].cells[i].text = h_text
    rows_data = [
        ("Technical approach and methodology", "40%"),
        ("Team qualifications and experience", "35%"),
        ("Financial proposal", "25%"),
    ]
    for r_idx, (a, b) in enumerate(rows_data, 1):
        table.rows[r_idx].cells[0].text = a
        table.rows[r_idx].cells[1].text = b

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    print(f"Created: {path}")


def make_ar_docx(path: Path) -> None:
    """Comprehensive Arabic TOR fixture for Phase 1.1 testing.

    Covers:
    - Background sentences (يهدف / تم) → NOT requirements
    - Mandatory BIDDER obligations (يجب, يُطلب, على الاستشاري)
    - CLIENT responsibilities (ستوفر الجهة, ستقوم الجهة)
    - Fixed values → NOT decisions (30 نوفمبر, 20 صفحة, 10 مقابلات)
    - Open decisions (حوالي 400, على الأقل 10 سنوات, حسب ما يراه مناسباً)
    - Arabic prohibition (يجب ألا)
    - Mixed Arabic-English (KII, TOR, working days, Inception Report)
    - Deliverables section with timing
    - Team requirements
    - Submission requirements
    """
    from docx import Document

    doc = Document()

    def h(text, level=1):
        doc.add_heading(text, level=level)

    def p(text):
        doc.add_paragraph(text)

    def li(text):
        doc.add_paragraph(text, style="List Bullet")

    h("شروط المرجعية", 1)
    p("التقييم الختامي لبرنامج الصمود في لبنان — TOR شامل")

    # 1. Background — should NOT become requirements
    h("1. الخلفية", 1)
    p("تم تنفيذ البرنامج منذ عام 2022 بالتعاون مع WFP في ثلاث محافظات.")
    p("يهدف البرنامج إلى دعم المجتمعات الهشة عبر التدخلات المتعددة القطاعات.")
    p("تشمل المحافظات المستهدفة بعلبك والشمال والجنوب.")

    # 2. Objectives — informational, should NOT be requirements
    h("2. الأهداف", 1)
    p("يهدف هذا التقييم إلى قياس مدى الصلة والفعالية والكفاءة والاستدامة للبرنامج.")
    p("يرمي التقييم إلى تقديم توصيات عملية لتحسين البرمجة المستقبلية.")

    # 3. Methodology — BIDDER obligations
    h("3. المنهجية", 1)
    p("يجب على الاستشاري تقديم تصميم تقييم صارم يشمل المكونات الكمية والنوعية.")
    p("يجب أن تتضمن المنهجية مراجعة شاملة للبيانات الثانوية.")
    # AT_LEAST → DECISION
    li("يجب إجراء ما لا يقل عن 30 مقابلة مع مخبرين رئيسيين (KIIs).")
    li("يُطلب إجراء 6 مجموعات نقاش بؤرية على الأقل.")
    # APPROX → DECISION
    li("يُطلب إجراء مسح للأسر بعينة تضم حوالي 400 مستجيب.")
    # Fixed count — NOT a decision
    li("يجب إجراء 10 مقابلات مع المخبرين الرئيسيين في كل محافظة.")
    # Open choice → DECISION
    p("يمكن للاستشاري اقتراح مناهج إضافية حسب ما يراه مناسباً.")

    # 4. Deliverables — with timing (should be first-class deliverables)
    h("4. المخرجات", 1)
    li("يجب على الاستشاري تقديم Inception Report خلال 10 أيام عمل من توقيع العقد.")
    li("يُطلب تقديم مسودة تقرير التقييم خلال 45 يوم عمل بعد اكتمال العمل الميداني.")
    li("يجب تقديم التقرير النهائي للتقييم خلال 15 يوماً تقويمياً من استلام تعليقات العميل.")
    li("يُطلب تقديم عرض تقديمي للنتائج أمام لجنة توجيهية.")

    # 5. Team requirements — AT_LEAST for experience → DECISION
    h("5. فريق التقييم", 1)
    p("يجب أن يضم الفريق قائداً فريق بخبرة 10 سنوات على الأقل في التقييم.")
    p("يلتزم الاستشاري بتعيين استشاري وطني متخصص في السياق اللبناني.")
    li("يُطلب وجود على الأقل اثنين من المعددين المدربين على الاستبيانات.")

    # 6. Submission — fixed deadline → NOT decision
    h("6. متطلبات التقديم", 1)
    p("يجب تقديم العروض بحلول 30 نوفمبر 2026 الساعة 17:00 بتوقيت بيروت.")
    # AT_MOST → fixed → NOT decision
    p("يجب ألا يتجاوز العرض التقني 20 صفحة باستثناء الملاحق.")
    p("يجب تقديم العروض التقنية والمالية بشكل منفصل.")
    p("يجب أن تكون جميع الوثائق باللغة الإنجليزية.")

    # 7. Ethics — BIDDER obligation
    h("7. الأخلاقيات وحماية الطفل", 1)
    p("يلتزم الاستشاري بسياسة ARFADA لحماية الطفل.")
    p("يجب الحصول على موافقة مستنيرة من جميع المشاركين.")

    # 8. Client responsibilities — should be CLIENT actor
    h("8. مسؤوليات العميل", 1)
    p("ستوفر الجهة المتعاقدة جلسات توعوية أمنية قبل بدء العمل الميداني.")
    p("ستقوم الجهة المتعاقدة بمراجعة تقرير الانطلاق وتقديم التغذية الراجعة.")
    p("سيوفر العميل البيانات الأولية والوثائق المتعلقة بالبرنامج.")

    # Scoring criteria table
    h("9. معايير التقييم", 1)
    table = doc.add_table(rows=4, cols=2)
    table.style = "Table Grid"
    headers = ["المعيار", "الوزن"]
    for i, h_text in enumerate(headers):
        table.rows[0].cells[i].text = h_text
    rows_data = [
        ("النهج التقني والمنهجية", "40%"),
        ("مؤهلات الفريق وخبرته", "35%"),
        ("العرض المالي", "25%"),
    ]
    for r_idx, (a, b) in enumerate(rows_data, 1):
        table.rows[r_idx].cells[0].text = a
        table.rows[r_idx].cells[1].text = b

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    print(f"Created: {path}")


# ---------------------------------------------------------------------------
# PDF fixture (via reportlab or fpdf2)
# ---------------------------------------------------------------------------

def make_en_pdf(path: Path) -> None:
    try:
        from fpdf import FPDF
    except ImportError:
        print("fpdf2 not installed — skipping PDF fixture (install with: pip install fpdf2)")
        return

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "TERMS OF REFERENCE", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, "Final Evaluation - Resilience Programme Lebanon", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    sections = [
        ("1. BACKGROUND",
         "The programme has been implemented since 2022 in collaboration with WFP. "
         "The evaluation covers the period 2022-2024 across three governorates."),
        ("2. OBJECTIVES",
         "The objective is to assess the relevance, effectiveness, efficiency, "
         "and sustainability of the programme."),
        ("3. METHODOLOGY",
         "The consultant shall propose a rigorous mixed-methods evaluation design. "
         "The methodology must include both quantitative and qualitative components. "
         "The consultant shall conduct at least 30 Key Informant Interviews (KIIs). "
         "A minimum of 6 Focus Group Discussions (FGDs) shall be conducted. "
         "A household survey with approximately 400 respondents is required."),
        ("4. DELIVERABLES",
         "Inception Report: within 10 working days of contract signature. "
         "Draft Evaluation Report: within 45 working days after fieldwork. "
         "Final Evaluation Report: within 15 calendar days after client comments."),
        ("5. SUBMISSION",
         "Proposals must be submitted by 30 November 2026 at 17:00 Beirut time. "
         "The technical proposal must not exceed 20 pages excluding annexes. "
         "Technical and financial proposals shall be submitted separately."),
    ]

    for heading, body in sections:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, heading, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, body)
        pdf.ln(3)

    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))
    print(f"Created: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    base = Path(__file__).parent
    make_en_docx(base / "synthetic_en.docx")
    make_ar_docx(base / "synthetic_ar.docx")
    make_en_pdf(base / "synthetic_en.pdf")
    print("Done.")
