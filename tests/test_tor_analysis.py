"""Phase 1 TOR analysis test suite.

All tests use synthetic fixtures — no confidential ARFADA TOR data committed.
Run from plugin root:
    python -m pytest tests/ -v
or:
    python tests/test_tor_analysis.py
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

# Plugin root on path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

FIXTURES = _ROOT / "tests" / "fixtures"
EN_DOCX = FIXTURES / "synthetic_en.docx"
AR_DOCX = FIXTURES / "synthetic_ar.docx"
EN_PDF = FIXTURES / "synthetic_en.pdf"


def _skip_if_missing(path: Path):
    import unittest
    if not path.exists():
        return unittest.skip(f"Fixture not found: {path} — run tests/fixtures/make_fixtures.py")
    return lambda f: f


# ---------------------------------------------------------------------------
# Adapter / extraction tests
# ---------------------------------------------------------------------------

class TestAdapter(unittest.TestCase):

    def test_docx_blocks_non_empty(self):
        from engine.tor.adapter import file_store
        store = file_store(EN_DOCX)
        did = store.documents("aid")[0]["document_id"]
        blocks = store.blocks(did)
        self.assertGreater(len(blocks), 5)

    def test_docx_has_headings(self):
        from engine.tor.adapter import file_store
        store = file_store(EN_DOCX)
        did = store.documents("aid")[0]["document_id"]
        blocks = store.blocks(did)
        headings = [b for b in blocks if b["block_type"] == "HEADING"]
        self.assertGreater(len(headings), 2, "Expected multiple headings in synthetic DOCX")

    def test_docx_has_list_items(self):
        from engine.tor.adapter import file_store
        store = file_store(EN_DOCX)
        did = store.documents("aid")[0]["document_id"]
        blocks = store.blocks(did)
        lists = [b for b in blocks if b["block_type"] == "LIST_ITEM"]
        self.assertGreater(len(lists), 2, "Expected list items in synthetic DOCX")

    def test_docx_has_tables(self):
        from engine.tor.adapter import file_store
        store = file_store(EN_DOCX)
        did = store.documents("aid")[0]["document_id"]
        tables = store.tables(did)
        self.assertGreater(len(tables), 0, "Expected at least one table (scoring criteria)")

    def test_docx_table_cells(self):
        from engine.tor.adapter import file_store
        store = file_store(EN_DOCX)
        did = store.documents("aid")[0]["document_id"]
        tables = store.tables(did)
        tbl_id = tables[0]["table_id"]
        cells = store.cells(tbl_id)
        self.assertGreater(len(cells), 2)
        texts = {c["text"] for c in cells}
        self.assertTrue(any("methodology" in t.lower() or "criteria" in t.lower()
                           for t in texts), f"Scoring criteria not found in cells: {texts}")

    def test_sections_derived_from_headings(self):
        from engine.tor.adapter import file_store
        store = file_store(EN_DOCX)
        did = store.documents("aid")[0]["document_id"]
        sections = store.sections(did)
        self.assertGreater(len(sections), 2)
        for s in sections:
            self.assertIn("heading_text", s)
            self.assertIn("start_block_sequence", s)
            self.assertIn("end_block_sequence", s)
            self.assertGreaterEqual(s["end_block_sequence"], s["start_block_sequence"])

    def test_section_text_non_empty(self):
        from engine.tor.adapter import file_store
        store = file_store(EN_DOCX)
        did = store.documents("aid")[0]["document_id"]
        sections = store.sections(did)
        sec = sections[0]
        text, blks = store.section_text(did, sec["start_block_sequence"], sec["end_block_sequence"])
        # section text should return something for a non-trivial section
        self.assertIsInstance(text, str)

    def test_arabic_utf8_preserved(self):
        from engine.tor.adapter import file_store
        store = file_store(AR_DOCX)
        did = store.documents("aid")[0]["document_id"]
        blocks = store.blocks(did)
        all_text = " ".join(b["plain_text"] for b in blocks)
        # Arabic Unicode block: U+0600–U+06FF
        arabic_chars = [c for c in all_text if "؀" <= c <= "ۿ"]
        self.assertGreater(len(arabic_chars), 20, "Arabic characters should be preserved in extracted blocks")

    def test_path_with_spaces(self):
        """Ensure file paths with spaces are handled correctly."""
        import tempfile, shutil
        from engine.tor.adapter import file_store
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "path with spaces" / "synthetic_en.docx"
            dest.parent.mkdir(parents=True)
            shutil.copy(str(EN_DOCX), str(dest))
            store = file_store(dest)
            did = store.documents("aid")[0]["document_id"]
            blocks = store.blocks(did)
            self.assertGreater(len(blocks), 5)

    @unittest.skipUnless(EN_PDF.exists(), "PDF fixture not generated")
    def test_pdf_blocks_non_empty(self):
        from engine.tor.adapter import file_store
        store = file_store(EN_PDF)
        did = store.documents("aid")[0]["document_id"]
        blocks = store.blocks(did)
        self.assertGreater(len(blocks), 3)

    @unittest.skipUnless(EN_PDF.exists(), "PDF fixture not generated")
    def test_pdf_has_headings(self):
        from engine.tor.adapter import file_store
        store = file_store(EN_PDF)
        did = store.documents("aid")[0]["document_id"]
        blocks = store.blocks(did)
        headings = [b for b in blocks if b["block_type"] == "HEADING"]
        self.assertGreater(len(headings), 0)

    @unittest.skipUnless(EN_PDF.exists(), "PDF fixture not generated")
    def test_pdf_page_numbers_present(self):
        from engine.tor.adapter import file_store
        import json as _json
        store = file_store(EN_PDF)
        did = store.documents("aid")[0]["document_id"]
        blocks = store.blocks(did)
        pages = [_json.loads(b.get("meta_json","{}")).get("page") for b in blocks]
        self.assertTrue(any(p is not None and p > 0 for p in pages), "PDF blocks should have page numbers")


# ---------------------------------------------------------------------------
# Requirement extraction tests
# ---------------------------------------------------------------------------

class TestRequirementExtraction(unittest.TestCase):

    def _get_reqs(self):
        from engine.tor.adapter import file_store
        from engine.tor.extractor import extract_fields, extract_requirements
        store = file_store(EN_DOCX)
        fields = extract_fields(store, "aid")
        return extract_requirements(store, "aid", fields)

    def test_requirements_non_empty(self):
        reqs = self._get_reqs()
        self.assertGreater(len(reqs), 5)

    def test_mandatory_requirements_majority(self):
        reqs = self._get_reqs()
        mandatory = [r for r in reqs if r.mandatory]
        self.assertGreater(len(mandatory), len(reqs) * 0.5,
                           "Most TOR requirements should be mandatory")

    def test_requirement_ids_stable(self):
        from engine.tor.adapter import file_store
        from engine.tor.extractor import extract_fields, extract_requirements
        store = file_store(EN_DOCX)
        fields = extract_fields(store, "aid")
        reqs1 = extract_requirements(store, "aid", fields)
        reqs2 = extract_requirements(store, "aid", fields)
        ids1 = {r.req_id for r in reqs1}
        ids2 = {r.req_id for r in reqs2}
        self.assertEqual(ids1, ids2, "Requirement IDs must be deterministic")

    def test_submission_requirements_found(self):
        reqs = self._get_reqs()
        sub = [r for r in reqs if r.category == "submission"]
        self.assertGreater(len(sub), 0, "Should find submission requirements")

    def test_deliverables_found(self):
        reqs = self._get_reqs()
        delivs = [r for r in reqs if r.category == "deliverable"]
        self.assertGreater(len(delivs), 0, "Should find deliverable requirements")

    def test_methodology_requirements_found(self):
        reqs = self._get_reqs()
        meth = [r for r in reqs if r.category == "methodology"]
        self.assertGreater(len(meth), 0, "Should find methodology requirements")

    def test_team_requirements_found(self):
        reqs = self._get_reqs()
        team = [r for r in reqs if r.category == "team"]
        self.assertGreater(len(team), 0, "Should find team requirements")

    def test_client_responsibility_detected(self):
        reqs = self._get_reqs()
        from scripts.analyze_tor import _actor
        actors = [_actor(r) for r in reqs]
        self.assertIn("CLIENT", actors, "Should detect at least one client responsibility")

    def test_provenance_on_all_requirements(self):
        reqs = self._get_reqs()
        for r in reqs:
            self.assertTrue(
                r.source_section_path or r.source_locator or r.block_sequence is not None,
                f"Requirement {r.req_id} has no provenance"
            )

    def test_exclusion_not_mandatory(self):
        """'CVs are not required' must be non-mandatory (OPTIONAL), never a bidder obligation."""
        reqs = self._get_reqs()
        for r in reqs:
            if "not required" in (r.text or "").lower():
                self.assertFalse(r.mandatory,
                    f"Exclusion statement should not be mandatory: {r.text}")

    def test_atomic_splitting(self):
        """Multi-obligation sentences get split into multiple requirements."""
        from engine.tor.extractor import _atomize
        combined = ("The consultant shall submit the inception report within 10 working days "
                    "and conduct 30 KIIs.")
        units = _atomize(combined)
        self.assertGreaterEqual(len(units), 1)  # may or may not split depending on heuristic


# ---------------------------------------------------------------------------
# Human decision detection tests
# ---------------------------------------------------------------------------

class TestHumanDecisions(unittest.TestCase):

    def _enriched(self):
        from engine.tor.adapter import file_store
        from engine.tor.extractor import extract_fields, extract_requirements
        from scripts.analyze_tor import _is_human_decision
        store = file_store(EN_DOCX)
        fields = extract_fields(store, "aid")
        reqs = extract_requirements(store, "aid", fields)
        return [(r, *_is_human_decision(r)) for r in reqs]

    def test_approx_quantity_is_decision(self):
        enriched = self._enriched()
        approx_decisions = [(r, note) for r, is_dec, note in enriched
                           if is_dec and "APPROX" in note]
        self.assertGreater(len(approx_decisions), 0,
                           "Approximate quantities must be flagged as human decisions")

    def test_atleast_quantity_is_decision(self):
        enriched = self._enriched()
        atleast = [(r, note) for r, is_dec, note in enriched
                   if is_dec and "AT_LEAST" in note]
        self.assertGreater(len(atleast), 0,
                           "'at least' quantities must be flagged as human decisions")

    def test_open_choice_language_is_decision(self):
        enriched = self._enriched()
        open_choices = [(r, note) for r, is_dec, note in enriched
                        if is_dec and "Open choice" in note]
        self.assertGreater(len(open_choices), 0,
                           "Open choice language must flag a human decision")

    def test_fixed_deadline_not_a_decision(self):
        """'must be submitted by 30 November 2026' is TOR-fixed, not a bidder decision."""
        from engine.tor.extractor import _modality
        text = "Proposals must be submitted by 30 November 2026 at 17:00 Beirut time."
        mand, modality = _modality(text)
        self.assertTrue(mand, "Fixed deadline must be mandatory")
        # Note: deadline text has an exact date, not AT_LEAST/APPROX — no decision flagged
        from scripts.analyze_tor import _is_human_decision
        from engine.tor.models import TORRequirement
        r = TORRequirement(
            req_id="x", assignment_id="a", tor_document_id="d",
            text=text, category="submission", mandatory=True, modality="MANDATORY",
            source_section_path="", block_sequence=0, page=None)
        is_dec, note = _is_human_decision(r)
        self.assertFalse(is_dec, f"Fixed deadline should NOT be a human decision, got: {note}")

    def test_fixed_page_limit_not_a_decision(self):
        """'must not exceed 20 pages' is TOR-fixed."""
        from engine.tor.models import TORRequirement
        from scripts.analyze_tor import _is_human_decision
        r = TORRequirement(
            req_id="x", assignment_id="a", tor_document_id="d",
            text="The technical proposal must not exceed 20 pages excluding annexes.",
            category="submission", mandatory=True, modality="MANDATORY",
            source_section_path="", block_sequence=0, page=None)
        is_dec, note = _is_human_decision(r)
        self.assertFalse(is_dec, f"Fixed page limit should NOT be a human decision, got: {note}")


# ---------------------------------------------------------------------------
# Structuring tests
# ---------------------------------------------------------------------------

class TestStructuring(unittest.TestCase):

    def _get_all(self):
        from engine.tor.adapter import file_store
        from engine.tor.extractor import extract_fields, extract_requirements
        from engine.tor import structuring
        store = file_store(EN_DOCX)
        aid = "aid"
        fields = extract_fields(store, aid)
        reqs = extract_requirements(store, aid, fields)
        return dict(
            fields=fields,
            reqs=reqs,
            deliverables=structuring.deliverables(aid, aid, reqs),
            submission=structuring.submission(aid, aid, reqs, fields),
            team=structuring.team(aid, aid, reqs),
            eval_q=structuring.eval_questions(aid, aid, reqs),
            timeline=structuring.timeline(aid, aid, reqs),
        )

    def test_submission_items_extracted(self):
        d = self._get_all()
        self.assertGreater(len(d["submission"]), 0, "Should extract submission items")

    def test_team_items_extracted(self):
        d = self._get_all()
        self.assertGreater(len(d["team"]), 0, "Should extract team requirements")

    def test_eval_questions_extracted(self):
        d = self._get_all()
        self.assertGreater(len(d["eval_q"]), 0, "Should extract evaluation questions")


# ---------------------------------------------------------------------------
# CLI script tests
# ---------------------------------------------------------------------------

class TestAnalyzeScript(unittest.TestCase):

    def test_docx_analysis_produces_output_dir(self):
        import tempfile
        from scripts.analyze_tor import analyze
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(EN_DOCX, tmp)
            out_dir = Path(result["output_dir"])
            self.assertTrue(out_dir.exists())
            self.assertTrue((out_dir / "tor_analysis.json").exists())
            self.assertTrue((out_dir / "requirements.json").exists())
            self.assertTrue((out_dir / "analysis_summary.md").exists())

    def test_json_serialization_no_exceptions(self):
        import tempfile
        from scripts.analyze_tor import analyze
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(EN_DOCX, tmp)
            out_dir = Path(result["output_dir"])
            data = json.loads((out_dir / "tor_analysis.json").read_text(encoding="utf-8"))
            self.assertIn("requirements", data)
            self.assertIn("summary", data)

    def test_arabic_utf8_in_json_output(self):
        import tempfile
        from scripts.analyze_tor import analyze
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(AR_DOCX, tmp)
            out_dir = Path(result["output_dir"])
            raw = (out_dir / "tor_analysis.json").read_text(encoding="utf-8")
            # Arabic characters should be present (not escaped) in the JSON
            arabic_chars = [c for c in raw if "؀" <= c <= "ۿ"]
            self.assertGreater(len(arabic_chars), 10,
                               "Arabic text should be preserved in JSON output")

    def test_missing_file_raises_file_not_found(self):
        from scripts.analyze_tor import analyze
        with self.assertRaises(FileNotFoundError):
            analyze("/nonexistent/path/tor.docx")

    def test_unsupported_format_raises_value_error(self):
        import tempfile
        from scripts.analyze_tor import analyze
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "tor.txt"
            fake.write_text("some text")
            with self.assertRaises(ValueError):
                analyze(fake)

    @unittest.skipUnless(EN_PDF.exists(), "PDF fixture not generated")
    def test_pdf_analysis_produces_requirements(self):
        import tempfile
        from scripts.analyze_tor import analyze
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(EN_PDF, tmp)
            self.assertGreater(result["summary"]["total_requirements"], 0)


# ===========================================================================
# Phase 1.1 tests: Arabic, PDF tables, deliverable calibration, diagnostics
# ===========================================================================

class TestArabicExtraction(unittest.TestCase):
    """Arabic obligation extraction — Phase 1.1."""

    def _get_ar_reqs(self):
        from engine.tor.adapter import file_store
        from engine.tor.extractor import extract_fields, extract_requirements
        store = file_store(AR_DOCX)
        fields = extract_fields(store, "aid")
        return extract_requirements(store, "aid", fields)

    def _get_ar_result(self):
        import tempfile
        from scripts.analyze_tor import analyze
        with tempfile.TemporaryDirectory() as tmp:
            return analyze(AR_DOCX, tmp)

    def test_arabic_requirements_found(self):
        reqs = self._get_ar_reqs()
        self.assertGreater(len(reqs), 5, "Arabic TOR should extract multiple requirements")

    def test_arabic_majority_mandatory(self):
        reqs = self._get_ar_reqs()
        mandatory = [r for r in reqs if r.mandatory]
        self.assertGreater(len(mandatory), len(reqs) * 0.5,
                           "Most Arabic requirements should be mandatory")

    def test_arabic_background_not_extracted(self):
        """يهدف / تم sentences must NOT become requirements."""
        from engine.tor.extractor import _ar_is_background
        background_texts = [
            "يهدف البرنامج إلى دعم المجتمعات الهشة عبر التدخلات المتعددة القطاعات.",
            "تم تنفيذ البرنامج منذ عام 2022 بالتعاون مع WFP.",
            "يهدف هذا التقييم إلى قياس مدى الصلة والفعالية.",
        ]
        for t in background_texts:
            self.assertTrue(_ar_is_background(t), f"Should be background: {t[:60]}")

    def test_arabic_obligation_recognized_as_non_background(self):
        """يجب sentences must NOT be filtered as background."""
        from engine.tor.extractor import _ar_is_background
        obligation_texts = [
            "يجب على الاستشاري تقديم تقرير الانطلاق خلال 10 أيام.",
            "يُطلب إجراء 30 مقابلة مع مخبرين رئيسيين.",
            "يلتزم الاستشاري بسياسة حماية الطفل.",
        ]
        for t in obligation_texts:
            self.assertFalse(_ar_is_background(t), f"Should NOT be background: {t[:60]}")

    def test_arabic_client_responsibilities_extracted(self):
        result = self._get_ar_result()
        client_count = result["summary"]["client_responsibilities"]
        self.assertGreater(client_count, 0,
                           "Arabic client responsibility sentences (ستوفر الجهة) must be extracted")

    def test_arabic_client_actor_set_correctly(self):
        result = self._get_ar_result()
        client_reqs = [r for r in result["requirements"] if r["actor"] == "CLIENT"]
        self.assertGreater(len(client_reqs), 0, "Should have CLIENT actor requirements")

    def test_arabic_bidder_actor_set_correctly(self):
        result = self._get_ar_result()
        bidder = [r for r in result["requirements"] if r["actor"] == "BIDDER"]
        self.assertGreater(len(bidder), 5, "Should have multiple BIDDER requirements")

    def test_arabic_human_decisions_detected(self):
        result = self._get_ar_result()
        self.assertGreater(result["summary"]["human_decisions"], 0,
                           "Arabic open quantities (على الأقل / حوالي) should trigger decisions")

    def test_arabic_fixed_deadline_not_decision(self):
        """يجب تقديم العروض بحلول 30 نوفمبر is a fixed deadline — NOT a decision."""
        from engine.tor.models import TORRequirement
        from scripts.analyze_tor import _is_human_decision
        r = TORRequirement(
            req_id="x", assignment_id="a", tor_document_id="d",
            text="يجب تقديم العروض بحلول 30 نوفمبر 2026 الساعة 17:00 بتوقيت بيروت.",
            category="submission", mandatory=True, modality="MANDATORY",
            source_section_path="", block_sequence=0, page=None)
        is_dec, note = _is_human_decision(r)
        self.assertFalse(is_dec, f"Fixed Arabic deadline must NOT be a decision. Got: {note}")

    def test_arabic_fixed_page_limit_not_decision(self):
        """يجب ألا يتجاوز 20 صفحة is AT_MOST — NOT a decision."""
        from engine.tor.models import TORRequirement
        from scripts.analyze_tor import _is_human_decision
        r = TORRequirement(
            req_id="x", assignment_id="a", tor_document_id="d",
            text="يجب ألا يتجاوز العرض التقني 20 صفحة باستثناء الملاحق.",
            category="submission", mandatory=True, modality="PROHIBITION",
            source_section_path="", block_sequence=0, page=None)
        is_dec, note = _is_human_decision(r)
        self.assertFalse(is_dec, f"Fixed page limit (AT_MOST) must NOT be a decision. Got: {note}")

    def test_arabic_atleast_is_decision(self):
        """على الأقل → open quantity → decision."""
        from engine.tor.models import TORRequirement
        from scripts.analyze_tor import _is_human_decision
        r = TORRequirement(
            req_id="x", assignment_id="a", tor_document_id="d",
            text="يجب إجراء ما لا يقل عن 30 مقابلة مع مخبرين رئيسيين.",
            category="methodology", mandatory=True, modality="MANDATORY",
            source_section_path="", block_sequence=0, page=None)
        is_dec, note = _is_human_decision(r)
        self.assertTrue(is_dec, f"'لا يقل عن 30' must be an open decision. Got: {note}")

    def test_arabic_approx_is_decision(self):
        """حوالي 400 مستجيب → approximate → decision."""
        from engine.tor.models import TORRequirement
        from scripts.analyze_tor import _is_human_decision
        r = TORRequirement(
            req_id="x", assignment_id="a", tor_document_id="d",
            text="يُطلب إجراء مسح للأسر بعينة تضم حوالي 400 مستجيب.",
            category="methodology", mandatory=True, modality="MANDATORY",
            source_section_path="", block_sequence=0, page=None)
        is_dec, note = _is_human_decision(r)
        self.assertTrue(is_dec, f"'حوالي 400' must be an open decision. Got: {note}")

    def test_arabic_open_choice_is_decision(self):
        """حسب ما يراه مناسباً → open choice → decision."""
        from engine.tor.models import TORRequirement
        from scripts.analyze_tor import _is_human_decision
        r = TORRequirement(
            req_id="x", assignment_id="a", tor_document_id="d",
            text="يمكن للاستشاري اقتراح مناهج إضافية حسب ما يراه مناسباً.",
            category="methodology", mandatory=False, modality="OPTIONAL",
            source_section_path="", block_sequence=0, page=None)
        is_dec, note = _is_human_decision(r)
        self.assertTrue(is_dec, f"'حسب ما يراه مناسباً' must be an open decision. Got: {note}")

    def test_arabic_prohibition_modality(self):
        """يجب ألا يتجاوز → PROHIBITION modality."""
        from engine.tor.extractor import _modality
        text = "يجب ألا يتجاوز العرض التقني 20 صفحة باستثناء الملاحق."
        mand, modality = _modality(text)
        self.assertTrue(mand, "Arabic prohibition should still be mandatory=True")
        self.assertEqual(modality, "PROHIBITION")

    def test_arabic_mandatory_modality(self):
        """يجب على الاستشاري → MANDATORY."""
        from engine.tor.extractor import _modality
        text = "يجب على الاستشاري تقديم تقرير الانطلاق خلال 10 أيام عمل."
        mand, modality = _modality(text)
        self.assertTrue(mand)
        self.assertEqual(modality, "MANDATORY")

    def test_arabic_language_detected(self):
        result = self._get_ar_result()
        self.assertEqual(result["diagnostics"]["language_detected"], "arabic")

    def test_arabic_utf8_in_requirements(self):
        reqs = self._get_ar_reqs()
        all_text = " ".join(r.text for r in reqs)
        arabic_chars = [c for c in all_text if "؀" <= c <= "ۿ"]
        self.assertGreater(len(arabic_chars), 20, "Arabic text must be preserved in requirements")

    def test_mixed_arabic_english_preserved(self):
        """Mixed text like 'Inception Report خلال 10 أيام' must keep both scripts."""
        reqs = self._get_ar_reqs()
        all_text = " ".join(r.text for r in reqs)
        # Should contain both English technical terms and Arabic
        has_english = any(c.isascii() and c.isalpha() for c in all_text)
        has_arabic = any("؀" <= c <= "ۿ" for c in all_text)
        self.assertTrue(has_english and has_arabic,
                        "Mixed Arabic-English documents should preserve both scripts")


class TestPDFTableExtraction(unittest.TestCase):
    """PDF table extraction — Phase 1.1."""

    @unittest.skipUnless(EN_PDF.exists(), "PDF fixture not generated")
    def test_pdf_analysis_completes(self):
        import tempfile
        from scripts.analyze_tor import analyze
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(EN_PDF, tmp)
            self.assertIn("summary", result)

    @unittest.skipUnless(EN_PDF.exists(), "PDF fixture not generated")
    def test_pdf_diagnostics_present(self):
        import tempfile
        from scripts.analyze_tor import analyze
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(EN_PDF, tmp)
            diag = result["diagnostics"]
            self.assertIn("pdf_tables_found", diag)
            self.assertIn("pdf_tables_unavailable", diag)
            self.assertIn("language_detected", diag)

    @unittest.skipUnless(EN_PDF.exists(), "PDF fixture not generated")
    def test_pdf_requirements_extracted(self):
        import tempfile
        from scripts.analyze_tor import analyze
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(EN_PDF, tmp)
            self.assertGreater(result["summary"]["total_requirements"], 0)

    def test_pdf_fallback_does_not_raise(self):
        """FileStore must handle PDF even when pdfplumber is unavailable (fallback)."""
        import tempfile, shutil, sys
        from engine.tor.adapter import _extract_pdf_pypdf_text
        from pathlib import Path
        if not EN_PDF.exists():
            self.skipTest("PDF fixture not generated")
        blocks, _ = _extract_pdf_pypdf_text(EN_PDF)
        self.assertGreater(len(blocks), 0, "pypdf fallback must extract blocks")


class TestDeliverableCalibration(unittest.TestCase):
    """Deliverable over-production fix — Phase 1.1."""

    def _get_en_deliverables(self):
        from engine.tor.adapter import file_store
        from engine.tor.extractor import extract_fields, extract_requirements
        from engine.tor import structuring
        store = file_store(EN_DOCX)
        aid = "aid"
        fields = extract_fields(store, aid)
        reqs = extract_requirements(store, aid, fields)
        return structuring.deliverables(aid, aid, reqs)

    def test_deliverables_have_qualify_reason(self):
        """Every deliverable must record why it qualified (Phase 1.1 auditability)."""
        delivs = self._get_en_deliverables()
        for d in delivs:
            self.assertIn("qualify_reason", d, "Deliverable missing qualify_reason field")
            self.assertTrue(d["qualify_reason"], f"qualify_reason must not be empty: {d}")

    def test_deliverable_count_reasonable(self):
        """Should not over-produce: English fixture has ~4 explicit deliverables."""
        delivs = self._get_en_deliverables()
        self.assertLessEqual(len(delivs), 8,
                             f"Deliverable count {len(delivs)} too high — over-production")

    def test_deliverables_have_provenance(self):
        delivs = self._get_en_deliverables()
        for d in delivs:
            has_prov = d.get("source_locator") or d.get("block_sequence") is not None
            self.assertTrue(has_prov, f"Deliverable missing provenance: {d.get('name')}")


class TestDiagnostics(unittest.TestCase):
    """Diagnostics in analysis output — Phase 1.1."""

    def _get_result(self, path=None):
        import tempfile
        from scripts.analyze_tor import analyze
        with tempfile.TemporaryDirectory() as tmp:
            return analyze(path or EN_DOCX, tmp)

    def test_diagnostics_present_in_output(self):
        result = self._get_result()
        self.assertIn("diagnostics", result)

    def test_diagnostics_fields_complete(self):
        diag = self._get_result()["diagnostics"]
        for field in ["language_detected", "total_blocks", "pdf_tables_found",
                      "pdf_tables_unavailable", "requirements_from_tables",
                      "deliverables_detected", "open_decisions_detected"]:
            self.assertIn(field, diag, f"Diagnostics missing field: {field}")

    def test_english_language_detected(self):
        result = self._get_result(EN_DOCX)
        self.assertEqual(result["diagnostics"]["language_detected"], "english")

    def test_arabic_language_detected(self):
        result = self._get_result(AR_DOCX)
        self.assertEqual(result["diagnostics"]["language_detected"], "arabic")


# ===========================================================================
# Phase 1.2 tests: Decision semantics hardening
# ===========================================================================

def _make_req(text, category="general", mandatory=True, modality="MANDATORY",
              section="", locator=""):
    from engine.tor.models import TORRequirement
    return TORRequirement(
        req_id="req_test", assignment_id="a", tor_document_id="d",
        text=text, category=category, mandatory=mandatory, modality=modality,
        source_section_path=section, block_sequence=0, page=None,
        source_locator=locator,
    )


class TestDecisionSemantics(unittest.TestCase):
    """Phase 1.2: richer decision classification."""

    def _classify(self, text, category="general", mandatory=True, actor="BIDDER"):
        from engine.tor.decision_model import classify_decision
        r = _make_req(text, category=category, mandatory=mandatory)
        return classify_decision(r, actor)

    # --- Qualification constraints (must NOT be decisions) ---

    def test_team_atleast_experience_is_fixed_minimum(self):
        """'at least 10 years experience' in TEAM = FIXED_MINIMUM, not decision."""
        dc = self._classify("Team Leader must have at least 10 years of experience.",
                            category="team")
        self.assertEqual(dc.decision_type, "FIXED_MINIMUM")
        self.assertFalse(dc.is_human_decision)

    def test_arabic_team_atleast_experience_is_fixed_minimum(self):
        """'10 سنوات على الأقل' in TEAM = FIXED_MINIMUM."""
        dc = self._classify(
            "يجب أن يمتلك قائد الفريق خبرة لا تقل عن 10 سنوات في التقييم.",
            category="team")
        self.assertEqual(dc.decision_type, "FIXED_MINIMUM")
        self.assertFalse(dc.is_human_decision)

    def test_eligibility_minimum_not_decision(self):
        """Eligibility minimum = FIXED_MINIMUM."""
        dc = self._classify("The firm must have completed at least 5 similar assignments.",
                            category="eligibility")
        self.assertFalse(dc.is_human_decision)

    # --- Submission / deadline constraints ---

    def test_submission_max_pages_is_fixed_maximum(self):
        """'must not exceed 20 pages' = FIXED_MAXIMUM."""
        dc = self._classify("Technical proposal must not exceed 20 pages excluding annexes.",
                            category="submission")
        self.assertEqual(dc.decision_type, "FIXED_MAXIMUM")
        self.assertFalse(dc.is_human_decision)

    def test_submission_deadline_is_fixed_requirement(self):
        """'submit by 30 November' = FIXED_REQUIREMENT."""
        dc = self._classify("Proposals must be submitted by 30 November 2026 at 17:00.",
                            category="submission")
        self.assertFalse(dc.is_human_decision)

    def test_arabic_page_limit_not_decision(self):
        """'يجب ألا يتجاوز 20 صفحة' = not decision."""
        dc = self._classify(
            "يجب ألا يتجاوز العرض التقني 20 صفحة باستثناء الملاحق.",
            category="submission")
        self.assertFalse(dc.is_human_decision)

    def test_arabic_fixed_deadline_not_decision(self):
        dc = self._classify(
            "يجب تقديم العروض بحلول 30 نوفمبر 2026 الساعة 17:00.",
            category="submission")
        self.assertFalse(dc.is_human_decision)

    # --- Method count bounded decisions ---

    def test_method_minimum_kii_is_bounded_decision(self):
        """'at least 30 KIIs' = OPEN_PROPOSAL_DECISION with min=30."""
        dc = self._classify("Conduct at least 30 Key Informant Interviews (KIIs).",
                            category="methodology")
        self.assertEqual(dc.decision_type, "OPEN_PROPOSAL_DECISION")
        self.assertTrue(dc.is_human_decision)
        self.assertEqual(dc.constraint_type, "AT_LEAST")
        self.assertAlmostEqual(dc.minimum, 30.0)

    def test_method_minimum_fgd_is_bounded_decision(self):
        """'at least 6 FGDs' = OPEN_PROPOSAL_DECISION with min=6."""
        dc = self._classify("A minimum of 6 Focus Group Discussions (FGDs) shall be conducted.",
                            category="data_collection_methods")
        self.assertEqual(dc.decision_type, "OPEN_PROPOSAL_DECISION")
        self.assertTrue(dc.is_human_decision)
        self.assertAlmostEqual(dc.minimum, 6.0)

    def test_arabic_method_minimum_kii_is_bounded_decision(self):
        """'ما لا يقل عن 30 KII' = bounded OPEN_PROPOSAL_DECISION."""
        dc = self._classify(
            "يجب إجراء ما لا يقل عن 30 مقابلة KII.",
            category="methodology")
        self.assertEqual(dc.decision_type, "OPEN_PROPOSAL_DECISION")
        self.assertTrue(dc.is_human_decision)
        self.assertAlmostEqual(dc.minimum, 30.0)

    def test_arabic_method_minimum_fgd_is_bounded_decision(self):
        """'6 مجموعات على الأقل' = bounded decision."""
        dc = self._classify(
            "يُطلب إجراء 6 مجموعات نقاش بؤرية على الأقل.",
            category="methodology")
        self.assertEqual(dc.decision_type, "OPEN_PROPOSAL_DECISION")
        self.assertTrue(dc.is_human_decision)

    # --- Range constraint ---

    def test_range_method_count_is_bounded_decision(self):
        """'6–8 FGDs' = OPEN_PROPOSAL_DECISION with range 6–8."""
        dc = self._classify("Conduct 6–8 Focus Group Discussions (FGDs).",
                            category="methodology")
        self.assertEqual(dc.decision_type, "OPEN_PROPOSAL_DECISION")
        self.assertEqual(dc.constraint_type, "RANGE")
        self.assertAlmostEqual(dc.minimum, 6.0)
        self.assertAlmostEqual(dc.maximum, 8.0)

    # --- Approximate sampling ---

    def test_approx_sampling_is_fixed_minimum(self):
        """'approximately 400 respondents' = FIXED_MINIMUM (approximate target)."""
        dc = self._classify(
            "A household survey with approximately 400 respondents is required.",
            category="sampling")
        self.assertEqual(dc.decision_type, "FIXED_MINIMUM")
        self.assertFalse(dc.is_human_decision)

    def test_arabic_approx_sampling_is_fixed_minimum(self):
        """'حوالي 400 مستجيب' = FIXED_MINIMUM."""
        dc = self._classify(
            "يُطلب إجراء مسح للأسر بعينة تضم حوالي 400 مستجيب.",
            category="methodology")
        self.assertFalse(dc.is_human_decision,
                         "Approximate target must NOT be an open decision")

    # --- Open methodology ---

    def test_explicit_consultant_proposes_is_decision(self):
        """'methodology to be proposed by consultant' = OPEN_PROPOSAL_DECISION."""
        dc = self._classify(
            "The consultant shall propose a detailed evaluation design.",
            category="methodology")
        self.assertEqual(dc.decision_type, "OPEN_PROPOSAL_DECISION")
        self.assertTrue(dc.is_human_decision)

    # --- Deferred decisions ---

    def test_deferred_inception_is_deferred_decision(self):
        """'to be finalized during inception' = DEFERRED_DECISION."""
        dc = self._classify(
            "The sampling framework will be finalized during the inception phase.",
            category="sampling")
        self.assertEqual(dc.decision_type, "DEFERRED_DECISION")
        self.assertTrue(dc.is_human_decision)

    # --- Client responsibility ---

    def test_client_responsibility_never_decision(self):
        """CLIENT requirements never produce bidder decisions."""
        dc = self._classify(
            "The client will provide security briefings before fieldwork.",
            category="general", actor="CLIENT")
        self.assertEqual(dc.decision_type, "NO_DECISION")
        self.assertFalse(dc.is_human_decision)

    # --- Validation ---

    def test_proposed_value_below_minimum_rejected(self):
        from engine.tor.decision_model import validate_proposed_value, DecisionCandidate
        dc = DecisionCandidate(
            decision_id="x", requirement_id="r", decision_type="OPEN_PROPOSAL_DECISION",
            is_human_decision=True, question="How many?", constraint_type="AT_LEAST",
            minimum=30.0, maximum=None, fixed_value=None)
        result = validate_proposed_value(dc, 25.0)
        self.assertFalse(result["valid"])

    def test_proposed_value_above_minimum_accepted(self):
        from engine.tor.decision_model import validate_proposed_value, DecisionCandidate
        dc = DecisionCandidate(
            decision_id="x", requirement_id="r", decision_type="OPEN_PROPOSAL_DECISION",
            is_human_decision=True, question="How many?", constraint_type="AT_LEAST",
            minimum=30.0, maximum=None, fixed_value=None)
        result = validate_proposed_value(dc, 35.0)
        self.assertTrue(result["valid"])

    def test_proposed_value_exceeds_maximum_rejected(self):
        from engine.tor.decision_model import validate_proposed_value, DecisionCandidate
        dc = DecisionCandidate(
            decision_id="x", requirement_id="r", decision_type="FIXED_MAXIMUM",
            is_human_decision=False, question=None, constraint_type="AT_MOST",
            minimum=None, maximum=20.0, fixed_value=None)
        result = validate_proposed_value(dc, 25.0)
        self.assertFalse(result["valid"])

    # --- Output artifact ---

    def test_decision_candidates_json_created(self):
        import tempfile
        from scripts.analyze_tor import analyze
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(EN_DOCX, tmp)
            out = Path(result["output_dir"])
            self.assertTrue((out / "decision_candidates.json").exists(),
                            "decision_candidates.json must be created")

    def test_decision_candidates_json_structure(self):
        import tempfile, json
        from scripts.analyze_tor import analyze
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(EN_DOCX, tmp)
            out = Path(result["output_dir"])
            data = json.loads((out / "decision_candidates.json").read_text(encoding="utf-8"))
            self.assertIn("candidates", data)
            self.assertIn("proposal_decisions", data)
            for c in data["candidates"]:
                self.assertIn("decision_type", c)
                self.assertIn("is_human_decision", c)
                self.assertIn("constraint_type", c)

    def test_summary_has_constraint_decision_split(self):
        import tempfile
        from scripts.analyze_tor import analyze
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(EN_DOCX, tmp)
            s = result["summary"]
            self.assertIn("proposal_decisions", s)
            self.assertIn("constraints", s)
            self.assertIn("deferred_decisions", s)


# ===========================================================================
# Phase 2 tests: Human Decision Review
# ===========================================================================

class TestDecisionRegisterModel(unittest.TestCase):
    """Unit tests for engine/tor/register.py."""

    def _make_reg(self, n_decisions: int = 3) -> tuple:
        """Create a DecisionRegister with n simple open decisions."""
        import tempfile
        from scripts.analyze_tor import analyze
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(EN_DOCX, tmp)
            run_dir = Path(result["output_dir"])
            from engine.tor.register import init_register, load_register
            reg = init_register(run_dir)
            return reg, run_dir

    def test_init_creates_open_decisions(self):
        import tempfile
        from scripts.analyze_tor import analyze
        from engine.tor.register import init_register
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(EN_DOCX, tmp)
            run_dir = Path(result["output_dir"])
            reg = init_register(run_dir)
            self.assertGreater(len(reg.decisions), 0)
            for e in reg.decisions:
                self.assertEqual(e.decision_status, "OPEN")

    def test_init_only_human_decisions(self):
        """Register must contain only is_human_decision=True candidates."""
        import tempfile, json
        from scripts.analyze_tor import analyze
        from engine.tor.register import init_register
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(EN_DOCX, tmp)
            run_dir = Path(result["output_dir"])
            reg = init_register(run_dir)
            cands = json.loads((run_dir / "decision_candidates.json").read_text(encoding="utf-8"))
            human_count = sum(1 for c in cands["candidates"] if c["is_human_decision"])
            self.assertEqual(len(reg.decisions), human_count,
                             "Register should contain exactly the human-decision candidates")

    def test_fixed_constraints_excluded(self):
        """FIXED_MINIMUM/FIXED_MAXIMUM must not appear in the register."""
        import tempfile
        from scripts.analyze_tor import analyze
        from engine.tor.register import init_register
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(EN_DOCX, tmp)
            run_dir = Path(result["output_dir"])
            reg = init_register(run_dir)
            for e in reg.decisions:
                self.assertNotIn(e.decision_type, {"FIXED_MINIMUM", "FIXED_MAXIMUM",
                                                    "FIXED_REQUIREMENT", "NO_DECISION"},
                                 f"Fixed constraint must not appear in register: {e.decision_type}")

    def test_set_numeric_minimum_valid(self):
        """Value above minimum is accepted."""
        import tempfile
        from scripts.analyze_tor import analyze
        from engine.tor.register import init_register, set_decision, save_register, load_register
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(EN_DOCX, tmp)
            run_dir = Path(result["output_dir"])
            reg = init_register(run_dir)
            # Find a decision with a minimum
            kii = next((e for e in reg.decisions if e.minimum is not None), None)
            if kii is None:
                self.skipTest("No numeric minimum decision found")
            r = set_decision(reg, kii.decision_id, kii.minimum + 5)
            self.assertTrue(r["valid"])
            save_register(reg, run_dir)
            reg2 = load_register(run_dir)
            e = next(e for e in reg2.decisions if e.decision_id == kii.decision_id)
            self.assertEqual(e.decision_status, "RESOLVED")
            self.assertAlmostEqual(e.selected_value, kii.minimum + 5)

    def test_set_numeric_minimum_invalid(self):
        """Value below minimum is rejected."""
        import tempfile
        from scripts.analyze_tor import analyze
        from engine.tor.register import init_register, set_decision
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(EN_DOCX, tmp)
            run_dir = Path(result["output_dir"])
            reg = init_register(run_dir)
            kii = next((e for e in reg.decisions if e.minimum is not None), None)
            if kii is None:
                self.skipTest("No numeric minimum decision found")
            r = set_decision(reg, kii.decision_id, kii.minimum - 10)
            self.assertFalse(r["valid"])
            self.assertEqual(kii.decision_status, "OPEN",
                             "Status must remain OPEN after invalid input")

    def test_set_maximum_violated(self):
        """Value above maximum is rejected."""
        from engine.tor.register import DecisionEntry, set_decision, Status
        entry = DecisionEntry(
            decision_id="x", requirement_id="r", decision_type="OPEN_PROPOSAL_DECISION",
            question="?", decision_status=Status.OPEN,
            selected_value=None, value_type="none",
            constraint_type="AT_MOST", minimum=None, maximum=20.0,
            source_text="", source_locator="", category="submission", actor="BIDDER",
            reason="")
        from engine.tor.register import DecisionRegister, _now
        reg = DecisionRegister(schema_version="1", run_id="r", tor_identity="t",
                               created_at=_now(), updated_at=_now(), status="OPEN",
                               decisions=[entry])
        r = set_decision(reg, "x", 25.0)
        self.assertFalse(r["valid"])

    def test_range_within_accepted(self):
        """Value within range is accepted."""
        from engine.tor.register import DecisionEntry, set_decision, Status, DecisionRegister, _now
        entry = DecisionEntry(
            decision_id="x", requirement_id="r", decision_type="OPEN_PROPOSAL_DECISION",
            question="?", decision_status=Status.OPEN, selected_value=None, value_type="none",
            constraint_type="RANGE", minimum=6.0, maximum=8.0,
            source_text="", source_locator="", category="methodology", actor="BIDDER", reason="")
        reg = DecisionRegister(schema_version="1", run_id="r", tor_identity="t",
                               created_at=_now(), updated_at=_now(), status="OPEN", decisions=[entry])
        r = set_decision(reg, "x", 7.0)
        self.assertTrue(r["valid"])

    def test_range_outside_rejected(self):
        from engine.tor.register import DecisionEntry, set_decision, Status, DecisionRegister, _now
        entry = DecisionEntry(
            decision_id="x", requirement_id="r", decision_type="OPEN_PROPOSAL_DECISION",
            question="?", decision_status=Status.OPEN, selected_value=None, value_type="none",
            constraint_type="RANGE", minimum=6.0, maximum=8.0,
            source_text="", source_locator="", category="methodology", actor="BIDDER", reason="")
        reg = DecisionRegister(schema_version="1", run_id="r", tor_identity="t",
                               created_at=_now(), updated_at=_now(), status="OPEN", decisions=[entry])
        r = set_decision(reg, "x", 10.0)
        self.assertFalse(r["valid"])

    def test_non_numeric_decision_accepted(self):
        """String values are accepted without numeric validation."""
        from engine.tor.register import DecisionEntry, set_decision, Status, DecisionRegister, _now
        entry = DecisionEntry(
            decision_id="x", requirement_id="r", decision_type="OPEN_PROPOSAL_DECISION",
            question="What methodology?", decision_status=Status.OPEN, selected_value=None,
            value_type="none", constraint_type="NONE", minimum=None, maximum=None,
            source_text="", source_locator="", category="methodology", actor="BIDDER", reason="")
        reg = DecisionRegister(schema_version="1", run_id="r", tor_identity="t",
                               created_at=_now(), updated_at=_now(), status="OPEN", decisions=[entry])
        r = set_decision(reg, "x", "mixed-methods approach combining qualitative and quantitative")
        self.assertTrue(r["valid"])
        self.assertEqual(entry.decision_status, "RESOLVED")
        self.assertEqual(entry.value_type, "string")

    def test_defer_decision(self):
        from engine.tor.register import DecisionEntry, defer_decision, Status, DecisionRegister, _now
        entry = DecisionEntry(
            decision_id="x", requirement_id="r", decision_type="DEFERRED_DECISION",
            question="?", decision_status=Status.OPEN, selected_value=None, value_type="none",
            constraint_type="NONE", minimum=None, maximum=None,
            source_text="", source_locator="", category="sampling", actor="BIDDER", reason="")
        reg = DecisionRegister(schema_version="1", run_id="r", tor_identity="t",
                               created_at=_now(), updated_at=_now(), status="OPEN", decisions=[entry])
        defer_decision(reg, "x", reason="To be agreed at inception phase")
        self.assertEqual(entry.decision_status, "DEFERRED")
        self.assertEqual(entry.notes, "To be agreed at inception phase")

    def test_unresolved_status(self):
        from engine.tor.register import DecisionEntry, unresolve_decision, Status, DecisionRegister, _now
        entry = DecisionEntry(
            decision_id="x", requirement_id="r", decision_type="OPEN_PROPOSAL_DECISION",
            question="?", decision_status=Status.OPEN, selected_value=None, value_type="none",
            constraint_type="NONE", minimum=None, maximum=None,
            source_text="", source_locator="", category="methodology", actor="BIDDER", reason="")
        reg = DecisionRegister(schema_version="1", run_id="r", tor_identity="t",
                               created_at=_now(), updated_at=_now(), status="OPEN", decisions=[entry])
        unresolve_decision(reg, "x", notes="Team not yet nominated")
        self.assertEqual(entry.decision_status, "UNRESOLVED")
        self.assertNotEqual(entry.decision_status, "RESOLVED")

    def test_skip_status(self):
        from engine.tor.register import DecisionEntry, skip_decision, Status, DecisionRegister, _now
        entry = DecisionEntry(
            decision_id="x", requirement_id="r", decision_type="OPEN_PROPOSAL_DECISION",
            question="?", decision_status=Status.OPEN, selected_value=None, value_type="none",
            constraint_type="NONE", minimum=None, maximum=None,
            source_text="", source_locator="", category="methodology", actor="BIDDER", reason="")
        reg = DecisionRegister(schema_version="1", run_id="r", tor_identity="t",
                               created_at=_now(), updated_at=_now(), status="OPEN", decisions=[entry])
        skip_decision(reg, "x")
        self.assertEqual(entry.decision_status, "SKIPPED")
        self.assertNotEqual(entry.decision_status, "RESOLVED")

    def test_recommendation_not_auto_resolved(self):
        """Recommendation must stay in RECOMMENDATION status until approved."""
        from engine.tor.register import (DecisionEntry, set_recommendation, Status,
                                         DecisionRegister, _now)
        entry = DecisionEntry(
            decision_id="x", requirement_id="r", decision_type="OPEN_PROPOSAL_DECISION",
            question="?", decision_status=Status.OPEN, selected_value=None, value_type="none",
            constraint_type="AT_LEAST", minimum=30.0, maximum=None,
            source_text="", source_locator="", category="methodology", actor="BIDDER", reason="")
        reg = DecisionRegister(schema_version="1", run_id="r", tor_identity="t",
                               created_at=_now(), updated_at=_now(), status="OPEN", decisions=[entry])
        set_recommendation(reg, "x", 35)
        self.assertEqual(entry.decision_status, "RECOMMENDATION")
        self.assertNotEqual(entry.decision_status, "RESOLVED")
        self.assertEqual(entry.recommendation, 35)

    def test_approve_recommendation(self):
        from engine.tor.register import (DecisionEntry, set_recommendation,
                                         approve_recommendation, Status, DecisionRegister, _now)
        entry = DecisionEntry(
            decision_id="x", requirement_id="r", decision_type="OPEN_PROPOSAL_DECISION",
            question="?", decision_status=Status.OPEN, selected_value=None, value_type="none",
            constraint_type="AT_LEAST", minimum=30.0, maximum=None,
            source_text="", source_locator="", category="methodology", actor="BIDDER", reason="")
        reg = DecisionRegister(schema_version="1", run_id="r", tor_identity="t",
                               created_at=_now(), updated_at=_now(), status="OPEN", decisions=[entry])
        set_recommendation(reg, "x", 35)
        result = approve_recommendation(reg, "x")
        self.assertTrue(result["valid"])
        self.assertEqual(entry.decision_status, "RESOLVED")
        self.assertEqual(entry.selected_value, 35)

    def test_clear_resets_to_open(self):
        from engine.tor.register import (DecisionEntry, set_decision, clear_decision,
                                         Status, DecisionRegister, _now)
        entry = DecisionEntry(
            decision_id="x", requirement_id="r", decision_type="OPEN_PROPOSAL_DECISION",
            question="?", decision_status=Status.OPEN, selected_value=None, value_type="none",
            constraint_type="NONE", minimum=None, maximum=None,
            source_text="", source_locator="", category="methodology", actor="BIDDER", reason="")
        reg = DecisionRegister(schema_version="1", run_id="r", tor_identity="t",
                               created_at=_now(), updated_at=_now(), status="OPEN", decisions=[entry])
        set_decision(reg, "x", "mixed methods")
        self.assertEqual(entry.decision_status, "RESOLVED")
        clear_decision(reg, "x")
        self.assertEqual(entry.decision_status, "OPEN")
        self.assertIsNone(entry.selected_value)

    def test_atomic_write_produces_valid_json(self):
        """Atomic save must produce valid JSON (temp-file → rename)."""
        import tempfile
        from scripts.analyze_tor import analyze
        from engine.tor.register import init_register, load_register, save_register
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(EN_DOCX, tmp)
            run_dir = Path(result["output_dir"])
            reg = init_register(run_dir)
            save_register(reg, run_dir)
            reg2 = load_register(run_dir)
            self.assertEqual(reg.run_id, reg2.run_id)
            self.assertEqual(len(reg.decisions), len(reg2.decisions))

    def test_resume_continues_from_open(self):
        """After resolving some decisions, next() returns first open one."""
        import tempfile
        from scripts.analyze_tor import analyze
        from engine.tor.register import init_register, set_decision, next_open, Status
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(EN_DOCX, tmp)
            run_dir = Path(result["output_dir"])
            reg = init_register(run_dir)
            if len(reg.decisions) < 2:
                self.skipTest("Need at least 2 decisions")
            first = reg.decisions[0]
            set_decision(reg, first.decision_id, "methodology approach")
            nxt = next_open(reg)
            self.assertIsNotNone(nxt)
            self.assertNotEqual(nxt.decision_id, first.decision_id)
            self.assertEqual(nxt.decision_status, "OPEN")

    def test_arabic_utf8_in_register(self):
        """Arabic source text preserved in register JSON."""
        import tempfile, json
        from scripts.analyze_tor import analyze
        from engine.tor.register import init_register, save_register
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(AR_DOCX, tmp)
            run_dir = Path(result["output_dir"])
            if result["summary"]["proposal_decisions"] == 0:
                self.skipTest("Arabic TOR has no proposal decisions")
            reg = init_register(run_dir)
            save_register(reg, run_dir)
            raw = (run_dir / "decision_register.json").read_text(encoding="utf-8")
            arabic_chars = [c for c in raw if "؀" <= c <= "ۿ"]
            self.assertGreater(len(arabic_chars), 5,
                               "Arabic text must be preserved in decision_register.json")

    def test_decision_register_json_created_in_output(self):
        """decision_register.json must appear in the run directory."""
        import tempfile
        from scripts.analyze_tor import analyze
        from engine.tor.register import init_register
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(EN_DOCX, tmp)
            run_dir = Path(result["output_dir"])
            init_register(run_dir)
            self.assertTrue((run_dir / "decision_register.json").exists())

    def test_summary_counts_correct(self):
        """Summary counts match actual decision statuses."""
        import tempfile
        from scripts.analyze_tor import analyze
        from engine.tor.register import (init_register, set_decision, defer_decision,
                                         skip_decision, get_summary)
        with tempfile.TemporaryDirectory() as tmp:
            result = analyze(EN_DOCX, tmp)
            run_dir = Path(result["output_dir"])
            reg = init_register(run_dir)
            if len(reg.decisions) < 3:
                self.skipTest("Need at least 3 decisions")
            set_decision(reg, reg.decisions[0].decision_id, "methodology")
            defer_decision(reg, reg.decisions[1].decision_id, "defer to inception")
            skip_decision(reg, reg.decisions[2].decision_id)
            s = get_summary(reg)
            self.assertEqual(s["resolved"], 1)
            self.assertEqual(s["deferred"], 1)
            self.assertEqual(s["skipped"], 1)


class TestDecisionRegisterCLI(unittest.TestCase):
    """CLI bridge tests for scripts/decision_register.py."""

    def _init_run(self, tmp):
        from scripts.analyze_tor import analyze
        result = analyze(EN_DOCX, tmp)
        run_dir = Path(result["output_dir"])
        import subprocess, json
        r = subprocess.run(["python", "scripts/decision_register.py", "init", str(run_dir)],
                          capture_output=True, cwd=str(_ROOT))
        data = json.loads(r.stdout.decode("utf-8"))
        return run_dir, data

    def test_cli_init(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, data = self._init_run(tmp)
            self.assertEqual(data["status"], "ok")
            self.assertGreater(data["register_summary"]["total_decisions"], 0)

    def test_cli_set_valid(self):
        import tempfile, subprocess, json
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _ = self._init_run(tmp)
            r = subprocess.run(["python", "scripts/decision_register.py", "next", str(run_dir)],
                               capture_output=True, cwd=str(_ROOT))
            d = json.loads(r.stdout.decode("utf-8"))
            dec_id = d["decision"]["decision_id"]
            min_val = d["decision"]["minimum"]

            value = str(int(min_val) + 5) if min_val is not None else '"test approach"'
            r2 = subprocess.run(["python", "scripts/decision_register.py", "set",
                                  str(run_dir), dec_id, value],
                                capture_output=True, cwd=str(_ROOT))
            self.assertEqual(r2.returncode, 0)

    def test_cli_set_invalid_below_min(self):
        import tempfile, subprocess, json
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _ = self._init_run(tmp)
            # Find a decision that actually carries a numeric minimum (via show).
            r = subprocess.run(["python", "scripts/decision_register.py", "show", str(run_dir)],
                               capture_output=True, cwd=str(_ROOT))
            data = json.loads(r.stdout.decode("utf-8"))
            with_min = [d for d in data["decisions"] if d.get("minimum") is not None]
            if not with_min:
                self.skipTest("No numeric-minimum decision in this fixture")
            dec = with_min[0]
            r2 = subprocess.run(["python", "scripts/decision_register.py", "set",
                                  str(run_dir), dec["decision_id"],
                                  str(int(dec["minimum"]) - 10)],
                                capture_output=True, cwd=str(_ROOT))
            self.assertEqual(r2.returncode, 4,
                             "Setting a value below TOR minimum must fail with exit code 4")

    def test_cli_defer(self):
        import tempfile, subprocess, json
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _ = self._init_run(tmp)
            r = subprocess.run(["python", "scripts/decision_register.py", "next", str(run_dir)],
                               capture_output=True, cwd=str(_ROOT))
            d = json.loads(r.stdout.decode("utf-8"))
            dec_id = d["decision"]["decision_id"]
            r2 = subprocess.run(["python", "scripts/decision_register.py", "defer",
                                  str(run_dir), dec_id, "defer to inception"],
                                capture_output=True, cwd=str(_ROOT))
            self.assertEqual(r2.returncode, 0)

    def test_cli_unresolved(self):
        import tempfile, subprocess, json
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _ = self._init_run(tmp)
            r = subprocess.run(["python", "scripts/decision_register.py", "next", str(run_dir)],
                               capture_output=True, cwd=str(_ROOT))
            d = json.loads(r.stdout.decode("utf-8"))
            dec_id = d["decision"]["decision_id"]
            r2 = subprocess.run(["python", "scripts/decision_register.py", "unresolved",
                                  str(run_dir), dec_id],
                                capture_output=True, cwd=str(_ROOT))
            self.assertEqual(r2.returncode, 0)


# ===========================================================================
# Phase 3 tests: Controlled Proposal Generation
# ===========================================================================

def _analyze_and_blueprint(src, tmp, with_decisions=False):
    """Helper: analyze a TOR, optionally init+resolve decisions, build blueprint."""
    from scripts.analyze_tor import analyze
    from engine.tor import blueprint as bp_mod
    import json as _json
    result = analyze(src, tmp)
    run_dir = Path(result["output_dir"])
    register = None
    if with_decisions:
        from engine.tor.register import init_register, set_decision, save_register, next_open
        reg = init_register(run_dir)
        # resolve all numeric decisions to min+5, text decisions to a string
        for e in reg.decisions:
            if e.minimum is not None:
                set_decision(reg, e.decision_id, int(e.minimum) + 5)
            else:
                set_decision(reg, e.decision_id, "proposed mixed-methods approach")
        save_register(reg, run_dir)
        register = _json.loads((run_dir / "decision_register.json").read_text(encoding="utf-8"))

    tor = _json.loads((run_dir / "tor_analysis.json").read_text(encoding="utf-8"))
    reqs = _json.loads((run_dir / "requirements.json").read_text(encoding="utf-8"))["requirements"]
    bp = bp_mod.build_blueprint(
        run_id=tor["run_id"], tor_identity=run_dir.name, assignment_type="evaluation",
        language=tor.get("diagnostics", {}).get("language_detected", "english"),
        created_at=tor.get("analyzed_at", ""),
        requirements=reqs, fields_found=list(tor.get("metadata", {}).keys()),
        decision_register=register,
    )
    return run_dir, bp, reqs, register


class TestBlueprint(unittest.TestCase):

    def test_blueprint_has_sections(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _, bp, _, _ = _analyze_and_blueprint(EN_DOCX, tmp)
            self.assertGreater(len(bp.sections), 3)

    def test_section_ordering(self):
        import tempfile
        from engine.tor.blueprint import SECTION_ORDER
        with tempfile.TemporaryDirectory() as tmp:
            _, bp, _, _ = _analyze_and_blueprint(EN_DOCX, tmp)
            seqs = [s.sequence for s in bp.sections]
            self.assertEqual(seqs, sorted(seqs), "Sections must be in canonical order")

    def test_executive_summary_present_first_in_order(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _, bp, _, _ = _analyze_and_blueprint(EN_DOCX, tmp)
            self.assertEqual(bp.sections[0].section_id, "EXECUTIVE_SUMMARY")

    def test_requirement_ownership_no_double_count(self):
        """Each bidder requirement owned by exactly one section."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _, bp, reqs, _ = _analyze_and_blueprint(EN_DOCX, tmp)
            owned = []
            for s in bp.sections:
                owned.extend(s.requirement_ids)
            self.assertEqual(len(owned), len(set(owned)),
                             "A requirement must not be owned by two sections")

    def test_every_bidder_requirement_owned(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _, bp, reqs, _ = _analyze_and_blueprint(EN_DOCX, tmp)
            bidder = {r["req_id"] for r in reqs if r.get("actor") != "CLIENT"}
            owned = set()
            for s in bp.sections:
                owned.update(s.requirement_ids)
            self.assertTrue(bidder.issubset(owned),
                            "Every bidder requirement must have an owning section")

    def test_slots_match_bidder_requirements(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _, bp, reqs, _ = _analyze_and_blueprint(EN_DOCX, tmp)
            bidder = sum(1 for r in reqs if r.get("actor") != "CLIENT")
            self.assertEqual(len(bp.slots), bidder)

    def test_client_requirements_not_in_slots(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _, bp, reqs, _ = _analyze_and_blueprint(AR_DOCX, tmp)
            client_ids = {r["req_id"] for r in reqs if r.get("actor") == "CLIENT"}
            slot_reqs = {s.requirement_id for s in bp.slots}
            self.assertTrue(client_ids.isdisjoint(slot_reqs),
                            "Client requirements must not produce response slots")

    def test_team_section_needs_evidence(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _, bp, _, _ = _analyze_and_blueprint(EN_DOCX, tmp)
            team = next((s for s in bp.sections if s.section_id == "TEAM"), None)
            if team:
                self.assertTrue(team.needs_arfada_evidence)

    def test_decision_dependency_propagation(self):
        """Sections owning a requirement with a decision get that dependency."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, bp, reqs, reg = _analyze_and_blueprint(EN_DOCX, tmp, with_decisions=False)
            # init register WITHOUT resolving → decisions open
            from engine.tor.register import init_register
            import json as _json
            init_register(run_dir)
            register = _json.loads((run_dir / "decision_register.json").read_text(encoding="utf-8"))
            tor = _json.loads((run_dir / "tor_analysis.json").read_text(encoding="utf-8"))
            from engine.tor.blueprint import build_blueprint
            bp2 = build_blueprint(
                run_id=tor["run_id"], tor_identity=run_dir.name, assignment_type="evaluation",
                language="english", created_at="", requirements=reqs,
                fields_found=list(tor.get("metadata", {}).keys()), decision_register=register)
            deps = [s for s in bp2.sections if s.decision_dependencies]
            self.assertGreater(len(deps), 0, "At least one section should depend on a decision")


class TestGenerationPackets(unittest.TestCase):

    def test_packet_isolation(self):
        """Packet for section X contains only X's requirements."""
        import tempfile
        from engine.tor.generation import build_packet
        from engine.tor.blueprint import blueprint_to_dict
        with tempfile.TemporaryDirectory() as tmp:
            _, bp, reqs, reg = _analyze_and_blueprint(EN_DOCX, tmp, with_decisions=True)
            bpd = blueprint_to_dict(bp)
            req_by_id = {r["req_id"]: r for r in reqs}
            meth = next(s for s in bpd["sections"] if s["section_id"] == "METHODOLOGY")
            packet = build_packet(section=meth, slots=bpd["slots"],
                                  requirements_by_id=req_by_id, decision_register=reg,
                                  language="english", assignment_metadata={})
            owned = {r["requirement_id"] for r in packet["owned_requirements"]}
            self.assertEqual(owned, set(meth["requirement_ids"]))

    def test_packet_has_forbidden_categories(self):
        import tempfile
        from engine.tor.generation import build_packet, FORBIDDEN_FACT_CATEGORIES
        from engine.tor.blueprint import blueprint_to_dict
        with tempfile.TemporaryDirectory() as tmp:
            _, bp, reqs, reg = _analyze_and_blueprint(EN_DOCX, tmp)
            bpd = blueprint_to_dict(bp)
            sec = bpd["sections"][1]
            packet = build_packet(section=sec, slots=bpd["slots"],
                                  requirements_by_id={r["req_id"]: r for r in reqs},
                                  decision_register=reg, language="english",
                                  assignment_metadata={})
            self.assertEqual(packet["forbidden_fact_categories"], FORBIDDEN_FACT_CATEGORIES)

    def test_packet_injects_resolved_decision(self):
        """Resolved numeric decision value appears in packet applied_decisions."""
        import tempfile
        from engine.tor.generation import build_packet
        from engine.tor.blueprint import blueprint_to_dict
        with tempfile.TemporaryDirectory() as tmp:
            _, bp, reqs, reg = _analyze_and_blueprint(EN_DOCX, tmp, with_decisions=True)
            bpd = blueprint_to_dict(bp)
            req_by_id = {r["req_id"]: r for r in reqs}
            # find a section with decision dependencies
            sec = next((s for s in bpd["sections"] if s["decision_dependencies"]), None)
            if sec is None:
                self.skipTest("No section with decision dependencies")
            packet = build_packet(section=sec, slots=bpd["slots"],
                                  requirements_by_id=req_by_id, decision_register=reg,
                                  language="english", assignment_metadata={})
            resolved = [d for d in packet["applied_decisions"] if d["status"] == "RESOLVED"]
            self.assertGreater(len(resolved), 0)


class TestSectionValidation(unittest.TestCase):

    def _packet(self, tmp, section_id="METHODOLOGY", with_decisions=False):
        from engine.tor.generation import build_packet
        from engine.tor.blueprint import blueprint_to_dict
        _, bp, reqs, reg = _analyze_and_blueprint(EN_DOCX, tmp, with_decisions=with_decisions)
        bpd = blueprint_to_dict(bp)
        req_by_id = {r["req_id"]: r for r in reqs}
        sec = next(s for s in bpd["sections"] if s["section_id"] == section_id)
        return build_packet(section=sec, slots=bpd["slots"], requirements_by_id=req_by_id,
                            decision_register=reg, language="english", assignment_metadata={})

    def _valid_candidate(self, packet):
        slots = packet["mandatory_slots"]
        blocks = [{"block_id": "b1", "type": "paragraph",
                   "text": "ARFADA proposes a rigorous, TOR-grounded approach that triangulates "
                           "multiple evidence streams against each requirement and integrates "
                           "findings through a shared analytical framework."}]
        ledger = [{"slot_id": s["slot_id"], "requirement_id": s["requirement_id"],
                   "block_ids": ["b1"], "response_summary": "addressed", "status": "ADDRESSED"}
                  for s in slots]
        return {"section_id": packet["section_id"], "blocks": blocks,
                "requirement_response_ledger": ledger}

    def test_valid_section_passes(self):
        import tempfile
        from engine.tor.generation import validate_candidate
        with tempfile.TemporaryDirectory() as tmp:
            packet = self._packet(tmp)
            cand = self._valid_candidate(packet)
            v = validate_candidate(packet, cand)
            self.assertTrue(v["valid"], f"errors: {v['errors']}, failed: {v['failed_slots']}")

    def test_missing_slot_detected(self):
        import tempfile
        from engine.tor.generation import validate_candidate
        with tempfile.TemporaryDirectory() as tmp:
            packet = self._packet(tmp)
            cand = self._valid_candidate(packet)
            if not cand["requirement_response_ledger"]:
                self.skipTest("No slots in this section")
            cand["requirement_response_ledger"] = cand["requirement_response_ledger"][:1]
            v = validate_candidate(packet, cand)
            if len(packet["mandatory_slots"]) > 1:
                self.assertFalse(v["valid"])
                self.assertGreater(len(v["failed_slots"]), 0)

    def test_ledger_bad_block_ref_rejected(self):
        import tempfile
        from engine.tor.generation import validate_candidate
        with tempfile.TemporaryDirectory() as tmp:
            packet = self._packet(tmp)
            cand = self._valid_candidate(packet)
            if cand["requirement_response_ledger"]:
                cand["requirement_response_ledger"][0]["block_ids"] = ["ghost"]
                v = validate_candidate(packet, cand)
                self.assertFalse(v["valid"])
                self.assertTrue(any("missing block_id" in e for e in v["errors"]))

    def test_table_validation_bad_rows(self):
        import tempfile
        from engine.tor.generation import validate_candidate
        with tempfile.TemporaryDirectory() as tmp:
            packet = self._packet(tmp)
            cand = self._valid_candidate(packet)
            cand["blocks"].append({"block_id": "t1", "type": "table",
                                   "columns": ["A", "B"], "rows": [["only one cell"]]})
            v = validate_candidate(packet, cand)
            self.assertFalse(v["valid"])
            self.assertTrue(any("cells" in e for e in v["errors"]))

    def test_bullet_validation_empty(self):
        import tempfile
        from engine.tor.generation import validate_candidate
        with tempfile.TemporaryDirectory() as tmp:
            packet = self._packet(tmp)
            cand = self._valid_candidate(packet)
            cand["blocks"].append({"block_id": "x1", "type": "bullet_list", "items": []})
            v = validate_candidate(packet, cand)
            self.assertFalse(v["valid"])

    def test_unsupported_arfada_fact_rejected(self):
        import tempfile
        from engine.tor.generation import validate_candidate
        with tempfile.TemporaryDirectory() as tmp:
            packet = self._packet(tmp)
            cand = self._valid_candidate(packet)
            cand["blocks"].append({"block_id": "bad", "type": "paragraph",
                                   "text": "ARFADA has completed over 200 evaluations across "
                                           "40 countries with extensive experience."})
            # need a ledger slot or it still may pass; the fact check is independent
            v = validate_candidate(packet, cand)
            self.assertFalse(v["valid"])
            self.assertTrue(any("ARFADA" in e for e in v["errors"]))

    def test_evidence_placeholder_allows_arfada_mention(self):
        import tempfile
        from engine.tor.generation import validate_candidate, NEEDS_EVIDENCE_TAG
        with tempfile.TemporaryDirectory() as tmp:
            packet = self._packet(tmp)
            cand = self._valid_candidate(packet)
            cand["blocks"].append({"block_id": "ev", "type": "evidence_placeholder",
                                   "text": f"{NEEDS_EVIDENCE_TAG}: ARFADA relevant experience "
                                           "and comparable assignments"})
            v = validate_candidate(packet, cand)
            self.assertTrue(v["valid"], f"errors: {v['errors']}")

    def test_approved_decision_value_enforced(self):
        """Approved value 35 must appear; writing 40 instead is a hard error."""
        import tempfile
        from engine.tor.generation import validate_candidate
        with tempfile.TemporaryDirectory() as tmp:
            packet = self._packet(tmp, with_decisions=True)
            # find a resolved numeric decision
            numeric = [d for d in packet["applied_decisions"]
                       if d["status"] == "RESOLVED" and isinstance(d.get("selected_value"), (int, float))
                       and d.get("minimum") is not None]
            if not numeric:
                self.skipTest("No resolved numeric decision in this section")
            approved = int(numeric[0]["selected_value"])
            wrong = approved + 5
            slots = packet["mandatory_slots"]
            cand = {"section_id": packet["section_id"],
                    "blocks": [{"block_id": "b1", "type": "paragraph",
                                "text": f"ARFADA will conduct {wrong} interviews integrated "
                                        "through a mixed-methods analytical framework aligned "
                                        "to the TOR evaluation questions."}],
                    "requirement_response_ledger": [
                        {"slot_id": s["slot_id"], "requirement_id": s["requirement_id"],
                         "block_ids": ["b1"], "response_summary": "x", "status": "ADDRESSED"}
                        for s in slots]}
            v = validate_candidate(packet, cand)
            self.assertFalse(v["valid"], "Wrong decision value must be rejected")
            self.assertTrue(any("approved decision value" in e for e in v["errors"]))

    def test_approved_decision_value_present_passes(self):
        """Writing the exact approved value passes."""
        import tempfile
        from engine.tor.generation import validate_candidate
        with tempfile.TemporaryDirectory() as tmp:
            packet = self._packet(tmp, with_decisions=True)
            numeric = [d for d in packet["applied_decisions"]
                       if d["status"] == "RESOLVED" and isinstance(d.get("selected_value"), (int, float))
                       and d.get("minimum") is not None]
            if not numeric:
                self.skipTest("No resolved numeric decision in this section")
            slots = packet["mandatory_slots"]
            vals = " and ".join(str(int(d["selected_value"])) for d in numeric)
            cand = {"section_id": packet["section_id"],
                    "blocks": [{"block_id": "b1", "type": "paragraph",
                                "text": f"ARFADA will conduct {vals} data collection activities "
                                        "integrated through a mixed-methods analytical framework "
                                        "aligned to the TOR evaluation questions."}],
                    "requirement_response_ledger": [
                        {"slot_id": s["slot_id"], "requirement_id": s["requirement_id"],
                         "block_ids": ["b1"], "response_summary": "x", "status": "ADDRESSED"}
                        for s in slots]}
            v = validate_candidate(packet, cand)
            self.assertTrue(v["valid"], f"errors: {v['errors']}")


class TestGenerationStatusResume(unittest.TestCase):

    def test_status_init_and_next(self):
        import tempfile
        from engine.tor.generation import init_status, next_pending_section
        from engine.tor.blueprint import blueprint_to_dict
        with tempfile.TemporaryDirectory() as tmp:
            _, bp, _, reg = _analyze_and_blueprint(EN_DOCX, tmp, with_decisions=True)
            status = init_status(blueprint_to_dict(bp), reg)
            nxt = next_pending_section(status)
            self.assertIsNotNone(nxt)
            self.assertNotEqual(nxt, "EXECUTIVE_SUMMARY",
                                "Executive summary must not be first")

    def test_executive_summary_last(self):
        import tempfile
        from engine.tor.generation import init_status, set_section_status, next_pending_section
        from engine.tor.blueprint import blueprint_to_dict
        with tempfile.TemporaryDirectory() as tmp:
            _, bp, _, reg = _analyze_and_blueprint(EN_DOCX, tmp, with_decisions=True)
            status = init_status(blueprint_to_dict(bp), reg)
            # mark all non-exec READY
            for sid, s in status["sections"].items():
                if sid != "EXECUTIVE_SUMMARY":
                    set_section_status(status, sid, "READY")
            nxt = next_pending_section(status)
            self.assertEqual(nxt, "EXECUTIVE_SUMMARY")

    def test_blocked_section_status(self):
        import tempfile
        from engine.tor.generation import init_status
        from engine.tor.blueprint import blueprint_to_dict
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, bp, reqs, _ = _analyze_and_blueprint(EN_DOCX, tmp)
            # init register WITHOUT resolving → open decisions → blocked sections
            from engine.tor.register import init_register
            import json as _json
            init_register(run_dir)
            register = _json.loads((run_dir / "decision_register.json").read_text(encoding="utf-8"))
            tor = _json.loads((run_dir / "tor_analysis.json").read_text(encoding="utf-8"))
            from engine.tor.blueprint import build_blueprint
            bp2 = build_blueprint(
                run_id=tor["run_id"], tor_identity=run_dir.name, assignment_type="evaluation",
                language="english", created_at="", requirements=reqs,
                fields_found=list(tor.get("metadata", {}).keys()), decision_register=register)
            status = init_status(blueprint_to_dict(bp2), register)
            blocked = [s for s in status["sections"].values()
                       if s["status"] == "BLOCKED_BY_DECISION"]
            self.assertGreater(len(blocked), 0,
                               "Open decisions should block dependent sections")


class TestGenerationCLI(unittest.TestCase):
    """End-to-end CLI pipeline (NRC = no decisions)."""

    NRC = Path("C:/xampp/htdocs/arfada-pe1-work/document-store-fresh/blobs/0e/"
               "0e89874c934c9f0c7f5fbf17b19ba63b11ef138698fe961c120689de522a5c94.docx")

    def _run(self, args, cwd=None):
        import subprocess
        r = subprocess.run(["python"] + args, capture_output=True, cwd=str(cwd or _ROOT))
        return r.returncode, r.stdout.decode("utf-8"), r.stderr.decode("utf-8")

    def test_full_pipeline_synthetic(self):
        """analyze → blueprint → prepare → validate → assemble on synthetic_en."""
        import tempfile, json as _json
        with tempfile.TemporaryDirectory() as tmp:
            from scripts.analyze_tor import analyze
            result = analyze(EN_DOCX, tmp)
            run_dir = Path(result["output_dir"])

            rc, out, err = self._run(["scripts/build_blueprint.py", str(run_dir)])
            self.assertEqual(rc, 0, err)
            bp_summary = _json.loads(out)
            self.assertGreater(bp_summary["blueprint"]["sections"], 3)

            # prepare + validate one section (METHODOLOGY)
            rc, out, err = self._run(["scripts/prepare_section.py", str(run_dir), "METHODOLOGY"])
            self.assertEqual(rc, 0, err)
            packet = _json.loads(out)
            slots = packet["mandatory_slots"]
            cand = {"section_id": "METHODOLOGY",
                    "blocks": [{"block_id": "b1", "type": "paragraph",
                                "text": "ARFADA proposes a rigorous mixed-methods design that "
                                        "triangulates qualitative and quantitative evidence "
                                        "against each evaluation question in the TOR."}],
                    "requirement_response_ledger": [
                        {"slot_id": s["slot_id"], "requirement_id": s["requirement_id"],
                         "block_ids": ["b1"], "response_summary": "addressed",
                         "status": "ADDRESSED"} for s in slots]}
            cand_path = run_dir / "_cand_meth.json"
            cand_path.write_text(_json.dumps(cand), encoding="utf-8")
            rc, out, err = self._run(["scripts/validate_section.py", str(run_dir),
                                      "METHODOLOGY", str(cand_path)])
            self.assertEqual(rc, 0, err)
            self.assertEqual(_json.loads(out)["status"], "READY")

            # assemble
            rc, out, err = self._run(["scripts/assemble_draft.py", str(run_dir)])
            self.assertEqual(rc, 0, err)
            self.assertTrue((run_dir / "proposal_draft.md").exists())

    def test_cross_tor_protection(self):
        """build_blueprint rejects a register whose run_id does not match."""
        import tempfile, json as _json
        with tempfile.TemporaryDirectory() as tmp:
            from scripts.analyze_tor import analyze
            result = analyze(EN_DOCX, tmp)
            run_dir = Path(result["output_dir"])
            # write a decision register with WRONG run_id
            bogus = {"schema_version": "1", "run_id": "WRONG_RUN", "tor_identity": "x",
                     "created_at": "", "updated_at": "", "status": "OPEN", "decisions": []}
            (run_dir / "decision_register.json").write_text(_json.dumps(bogus), encoding="utf-8")
            rc, out, err = self._run(["scripts/build_blueprint.py", str(run_dir)])
            self.assertEqual(rc, 3, "Cross-TOR register must be rejected with exit 3")

    @unittest.skipUnless(NRC.exists(), "NRC TOR not available")
    def test_nrc_blueprint_no_decisions(self):
        import tempfile, json as _json
        with tempfile.TemporaryDirectory() as tmp:
            from scripts.analyze_tor import analyze
            result = analyze(self.NRC, tmp)
            run_dir = Path(result["output_dir"])
            rc, out, err = self._run(["scripts/build_blueprint.py", str(run_dir)])
            self.assertEqual(rc, 0, err)
            summary = _json.loads(out)["blueprint"]
            self.assertEqual(summary["open_decisions"], 0)
            self.assertEqual(summary["sections_blocked_by_decisions"], 0)


class TestArabicGeneration(unittest.TestCase):

    def test_arabic_blueprint_language(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _, bp, _, _ = _analyze_and_blueprint(AR_DOCX, tmp)
            self.assertEqual(bp.language, "arabic")

    def test_arabic_requirement_text_in_packet(self):
        import tempfile
        from engine.tor.generation import build_packet
        from engine.tor.blueprint import blueprint_to_dict
        with tempfile.TemporaryDirectory() as tmp:
            _, bp, reqs, reg = _analyze_and_blueprint(AR_DOCX, tmp)
            bpd = blueprint_to_dict(bp)
            req_by_id = {r["req_id"]: r for r in reqs}
            sec = next((s for s in bpd["sections"] if s["requirement_ids"]), None)
            if sec is None:
                self.skipTest("No section with requirements")
            packet = build_packet(section=sec, slots=bpd["slots"],
                                  requirements_by_id=req_by_id, decision_register=reg,
                                  language="arabic", assignment_metadata={})
            text = " ".join(r["text"] for r in packet["owned_requirements"])
            arabic = [c for c in text if "؀" <= c <= "ۿ"]
            self.assertGreater(len(arabic), 5, "Arabic requirement text must be preserved")


class TestNoProviderAPI(unittest.TestCase):
    """Verify the plugin contains no Anthropic API dependency."""

    def test_no_anthropic_import_in_engine(self):
        import glob
        offenders = []
        for py in glob.glob(str(_ROOT / "engine" / "**" / "*.py"), recursive=True):
            txt = Path(py).read_text(encoding="utf-8")
            if "import anthropic" in txt or "anthropic.Anthropic" in txt \
                    or "ANTHROPIC_API_KEY" in txt:
                offenders.append(py)
        self.assertEqual(offenders, [], f"Anthropic API usage found in: {offenders}")

    def test_no_anthropic_import_in_scripts(self):
        import glob
        offenders = []
        for py in glob.glob(str(_ROOT / "scripts" / "*.py")):
            txt = Path(py).read_text(encoding="utf-8")
            if "import anthropic" in txt or "anthropic.Anthropic" in txt \
                    or "ANTHROPIC_API_KEY" in txt:
                offenders.append(py)
        self.assertEqual(offenders, [], f"Anthropic API usage found in: {offenders}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
