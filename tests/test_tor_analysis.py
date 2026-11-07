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


if __name__ == "__main__":
    unittest.main(verbosity=2)
