"""v0.6.10 regression — the REAL South Darfur ZOA PDF broke v0.6.9.

The real-PDF extraction pattern (reproduced by tests/fixtures/south_darfur_pdf.py):
page-1 table cells come before the text, the title is merged with "Terms of
Reference (ToR) Background …" into one long paragraph, and the numbered submission
list is typed as HEADING blocks.

1. title: layout tolerant; "Indicator: Baseline"-style table pairs are never titles.
2. assignment type: ENDLINE / Final Evaluation (HIGH) even if the title is lost or
   suspicious; references to an existing baseline do not score BASELINE.
3. numbered submission items become submission requirements (scoped to a
   submission list) → budget / previous-work / registration FINAL blockers only.
4. coordinated localities ("Nyala Shamal and Nyala Janoub localities").

Optional: set ARFADA_REAL_TOR=<path to the original PDF> to also run the checks
against the real document (never committed).

    python -m pytest tests/test_v0610_real_pdf_pattern.py -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("ARFADA_HOME", tempfile.mkdtemp(prefix="arfada_v0610_home_"))

from tests.fixtures import south_darfur_pdf as SDP  # noqa: E402

TITLE = SDP.TITLE


def _pdf_available() -> bool:
    try:
        import reportlab  # noqa: F401
        import pdfplumber  # noqa: F401
        return True
    except Exception:
        return False


class _Run:
    cache: dict = {}

    @classmethod
    def get(cls, pdf: Path):
        key = str(pdf)
        if key not in cls.cache:
            from scripts.analyze_tor import analyze
            tmp = Path(tempfile.mkdtemp(prefix="arfada_v0610_"))
            analyze(pdf, output_root=tmp / "out")
            run = next((tmp / "out").iterdir())
            tor = json.loads((run / "tor_analysis.json").read_text(encoding="utf-8"))
            reqs = json.loads((run / "requirements.json").read_text(encoding="utf-8"))[
                "requirements"]
            cls.cache[key] = (run, tor, reqs)
        return cls.cache[key]


def _fixture_pdf() -> Path:
    p = Path(tempfile.gettempdir()) / "arfada_v0610_fixture" / "ToR_south_darfur.pdf"
    if not p.exists():
        SDP.build(p)
    return p


def _mv(tor, key):
    return ((tor.get("metadata") or {}).get(key) or {}).get("value", "")


# ---------------------------------------------------------------------------
# 1. title detection (block level, no PDF needed)
# ---------------------------------------------------------------------------

class TestTitleDetection(unittest.TestCase):
    def _lines(self, items):
        return [(t, bt) for t, bt in items]

    def test_table_pairs_are_never_titles(self):
        from engine.tor.tor_metadata import detect_title
        for pair in ("Indicator: Baseline", "Indicator: Endline", "Location: Sudan",
                     "Baseline: Target", "Indicator: Final Evaluation"):
            for bt in ("TABLE_PAIR", "TABLE_CELL", "PARAGRAPH", "HEADING"):
                self.assertEqual(detect_title([(pair, bt)]), ("", ""), (pair, bt))

    def test_keyword_alone_is_not_a_title(self):
        from engine.tor.tor_metadata import detect_title
        for word in ("Baseline", "Evaluation", "Endline", "Final Evaluation"):
            self.assertEqual(detect_title([(word, "PARAGRAPH")]), ("", ""), word)

    def test_title_embedded_in_long_paragraph(self):
        from engine.tor.tor_metadata import detect_title
        merged = ("Final Evaluation for “ Support to War Affected Communities in South Darfur "
                  "Project” Terms of Reference (ToR) Background ZOA is seeking an independent "
                  "Consultant(s), Specialist(s), or a Company to conduct a final evaluation for "
                  "its Food Assistance Project in South Darfur.")
        lines = [("Indicator", "TABLE_CELL"), ("Indicator: Baseline", "TABLE_PAIR"),
                 ("Baseline", "TABLE_CELL"), ("Baseline: Target", "TABLE_PAIR"),
                 (merged, "PARAGRAPH")]
        self.assertEqual(detect_title(lines)[0], TITLE)

    def test_text_heading_preferred_over_table_cells(self):
        from engine.tor.tor_metadata import detect_title
        lines = [("Baseline survey of livelihoods", "TABLE_CELL"),
                 ("Endline Evaluation of the WASH Resilience Project", "HEADING")]
        self.assertEqual(detect_title(lines)[0],
                         "Endline Evaluation of the WASH Resilience Project")

    def test_explicit_label_still_wins(self):
        from engine.tor.tor_metadata import detect_title
        lines = [("Indicator: Baseline", "TABLE_PAIR"),
                 ("Assignment title: Final evaluation of the Livelihoods Project", "PARAGRAPH")]
        self.assertEqual(detect_title(lines), ("Final evaluation of the Livelihoods Project",
                                               "LABEL"))


# ---------------------------------------------------------------------------
# 2. assignment type robust to a lost / suspicious title
# ---------------------------------------------------------------------------

class TestAssignmentTypeRobust(unittest.TestCase):
    TEXT_REQS = [
        {"text": "The end line evaluation aims to assess progress, efficiency and impact based "
                 "on established baseline information, targets and indicators.",
         "category": "general"},
        {"text": "The baseline assessment conducted in July 2026 set baseline figures for food "
                 "insecurity.", "category": "general"},
        {"text": "In the baseline the proposed target number of HHs was 243.",
         "category": "sampling"},
        {"text": "Data on food acquisition will be collected to evaluate progress in the "
                 "benchmarks established in the baseline.", "category": "general"},
        {"text": "At least 5 years of experience in conducting baseline surveys / evaluations "
                 "related to FSL programs.", "category": "team"},
        {"text": "Respect local customs while applying Baseline Survey methods and tools.",
         "category": "ethics"},
        {"text": "Risk Mitigation Plan: Address potential challenges and risks during the "
                 "baseline survey process.", "category": "submission"},
        {"text": "ZOA is seeking a consultant to conduct a final evaluation for its project.",
         "category": "general"},
    ]

    def _infer(self, title):
        from engine.tor.assignment_type import infer_assignment_type
        meta = {"assignment": {"value": title, "confidence": "MEDIUM"}} if title else {}
        return infer_assignment_type(meta, self.TEXT_REQS, context_aware=True)

    def test_real_title(self):
        r = self._infer(TITLE)
        self.assertEqual((r.assignment_type, r.confidence), ("ENDLINE", "HIGH"))
        self.assertEqual(r.label, "Final (Endline) Evaluation")

    def test_suspicious_title_cannot_dominate(self):
        for bad in ("Indicator: Baseline", "Baseline: Target"):
            r = self._infer(bad)
            self.assertEqual(r.assignment_type, "ENDLINE", bad)
            self.assertNotIn("BASELINE", r.scores, bad)

    def test_no_title(self):
        r = self._infer("")
        self.assertEqual(r.assignment_type, "ENDLINE")

    def test_genuine_baseline_still_baseline(self):
        from engine.tor.assignment_type import infer_assignment_type
        reqs = [{"text": "The organisation is seeking a consultant to conduct a baseline survey "
                         "for its new livelihoods project before implementation starts.",
                 "category": "general"},
                {"text": "The baseline study must establish values for all logframe indicators.",
                 "category": "general"}]
        r = infer_assignment_type({"assignment": {"value": "Baseline Study for the Livelihoods "
                                                           "Project", "confidence": "MEDIUM"}},
                                  reqs, context_aware=True)
        self.assertEqual(r.assignment_type, "BASELINE")


# ---------------------------------------------------------------------------
# 3. numbered submission items (block level)
# ---------------------------------------------------------------------------

class TestSubmissionListItems(unittest.TestCase):
    @staticmethod
    def _b(bt, t):
        return {"block_type": bt, "plain_text": t, "sequence": 0}

    def test_numbered_headings_in_submission_list(self):
        from engine.tor.extractor import _submission_list_items
        b = self._b
        blocks = [b("PARAGRAPH", "Submission Requirements Interested parties must submit the "
                                 "following:"),
                  b("HEADING", "1. Technical Proposal: Detailed methodology."),
                  b("HEADING", "2. Financial Proposal: Detailed budget, including daily rates."),
                  b("HEADING", "3. CVs/Profiles of Team Members: expertise in food security,"),
                  b("PARAGRAPH", "and conflict sensitivity."),
                  b("PARAGRAPH", "Selection Criteria:"),
                  b("HEADING", "1. Technical Approach")]
        items = _submission_list_items(blocks)
        self.assertEqual(sorted(items), [1, 2, 3])
        self.assertTrue(items[2][0].startswith("Financial Proposal"))
        self.assertTrue(items[3][0].endswith("and conflict sensitivity."))
        self.assertEqual(items[3][1], [4])

    def test_headings_outside_submission_list_untouched(self):
        from engine.tor.extractor import _submission_list_items
        b = self._b
        blocks = [b("HEADING", "1. Background"), b("PARAGRAPH", "Some context."),
                  b("HEADING", "2. Objectives"), b("PARAGRAPH", "Selection Criteria:"),
                  b("HEADING", "1. Technical Approach")]
        self.assertEqual(_submission_list_items(blocks), {})


# ---------------------------------------------------------------------------
# 4. full pipeline on a PDF with the real extraction pattern
# ---------------------------------------------------------------------------

@unittest.skipUnless(_pdf_available(), "reportlab/pdfplumber not installed")
class TestRealPdfPattern(unittest.TestCase):
    PDF = None

    def _get(self):
        return _Run.get(self.PDF or _fixture_pdf())

    def test_metadata(self):
        _run, tor, _reqs = self._get()
        self.assertEqual(_mv(tor, "assignment"), TITLE)
        self.assertEqual(_mv(tor, "client"), "ZOA")
        self.assertEqual(_mv(tor, "country"), "Sudan")
        subs = ((tor["metadata"].get("subnational_location") or {}).get("values") or [])
        for place in ("South Darfur", "Nyala Shamal", "Nyala Janoub"):
            self.assertIn(place, subs)

    def test_assignment_type(self):
        _run, tor, _reqs = self._get()
        at = tor["assignment_type"]
        self.assertEqual(at["assignment_type"], "ENDLINE")
        self.assertEqual(at["assignment_type_confidence"], "HIGH")

    def test_submission_items_are_requirements(self):
        _run, _tor, reqs = self._get()
        sub = [r["text"] for r in reqs if r["category"] == "submission"]
        self.assertTrue(any(t.startswith("Financial Proposal") for t in sub), sub)
        self.assertTrue(any(t.startswith("Relevant Experience") for t in sub), sub)
        self.assertFalse(any(t.startswith("Technical Approach") for t in sub))

    def test_checklist_names_items(self):
        from engine.tor.submission import build_submission_checklist
        _run, _tor, reqs = self._get()
        entries = build_submission_checklist(reqs)
        keys = {e["item_key"] for e in entries}
        self.assertTrue({"detailed_budget", "previous_work", "cv_annex"} <= keys, keys)
        for e in entries:
            self.assertNotIn(e["item_label"], ("", "Submission item"), e)

    def test_final_blockers_not_draft_blockers(self):
        from engine.tor.submission_blockers import pending_submission_blockers
        from engine.tor.blockers import classify_blockers, FINAL_SUBMISSION_BLOCKER, DRAFT_BLOCKER
        run, _tor, reqs = self._get()
        pending = pending_submission_blockers(run, reqs)
        keys = {p["item_key"] for p in pending}
        self.assertTrue({"detailed_budget", "previous_work", "registration"} <= keys, keys)
        buckets = classify_blockers({"findings": []}, extra_submission_gaps=pending)
        self.assertEqual(len(buckets[FINAL_SUBMISSION_BLOCKER]), len(pending))
        self.assertEqual(buckets[DRAFT_BLOCKER], [])


@unittest.skipUnless(os.environ.get("ARFADA_REAL_TOR") and _pdf_available(),
                     "set ARFADA_REAL_TOR to the original South Darfur PDF")
class TestRealTor(TestRealPdfPattern):
    PDF = Path(os.environ.get("ARFADA_REAL_TOR", "") or ".")


if __name__ == "__main__":
    unittest.main()
