"""v0.6.6 ARFADA Writing DNA layer tests (style only; never facts).

Covers persistence/retrieval ranking, section-specific exemplars, the generic-AI
style QA (filler / uniformity / divergence / copy), the anti-copy long-phrase check,
and the measurable criterion that ARFADA-styled prose out-scores generic templated
prose. A synthetic exemplar corpus is built in a temp cache (the real confidential
corpus is never needed or committed).

Run from plugin root:  python -m pytest tests/test_writing_dna.py -v
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

os.environ.setdefault("ARFADA_HOME", tempfile.mkdtemp(prefix="arfada_dna_home_"))

_ARFADA_STYLE = (
    "ARFADA will interview 30 key informants across four localities in South Darfur. "
    "Enumerators recruited locally administer the household tool in Arabic. Where "
    "access is constrained by insecurity, the team adapts with remote telephone "
    "interviews and community focal points agreed with the client at inception. "
    "Data is triangulated across sources before findings are drafted.")
_GENERIC = (
    "This comprehensive and robust approach ensures a holistic, rigorous and seamless "
    "methodology. This approach ensures tailored delivery. This will ensure robust "
    "outcomes. Our methodology will ensure comprehensive and holistic results across "
    "all components of this important assignment.")


def _build_corpus(cache_dir: Path):
    """Write a synthetic exemplar index + section files."""
    exemplars = [
        {"exemplar_id": "ex1", "country": "Jordan", "region": "MENA",
         "project_folder": "SCI_ChildLabour_Endline_Jordan", "assignment_type": "ENDLINE",
         "tor_file": "ToR.docx"},
        {"exemplar_id": "ex2", "country": "Sudan", "region": "MENA",
         "project_folder": "NRC_FoodSecurity_NeedsAssessment_Darfur_humanitarian",
         "assignment_type": "NEEDS_ASSESSMENT", "tor_file": "ToR.pdf"},
        {"exemplar_id": "ex3", "country": "Lebanon", "region": "MENA",
         "project_folder": "UNICEF_Education_Evaluation_Lebanon", "assignment_type": "EVALUATION",
         "tor_file": "ToR.docx"},
    ]
    index = {"exemplars": exemplars,
             "writing_dna": {"paragraph_word_median": 45, "bullets_per_doc": 4,
                             "tables_per_doc": 2, "dominant_voice": "organizational"}}
    (cache_dir / "exemplar_index.json").write_text(json.dumps(index), encoding="utf-8")
    sdir = cache_dir / "sections"
    sdir.mkdir(parents=True, exist_ok=True)
    for ex in exemplars:
        secs = [{"type": "METHODOLOGY", "heading": "Methodology", "text": _ARFADA_STYLE},
                {"type": "CONTEXT", "heading": "Understanding", "text": _ARFADA_STYLE}]
        (sdir / f"{ex['exemplar_id']}.json").write_text(
            json.dumps({"sections": secs}), encoding="utf-8")


class TestRetrievalRanking(unittest.TestCase):
    def setUp(self):
        self.cache = Path(tempfile.mkdtemp(prefix="dna_cache_"))
        _build_corpus(self.cache)

    def test_relevant_proposals_ranked(self):
        from engine.tor.exemplars import retrieval
        rel = retrieval.relevant_proposals(
            assignment_type="NEEDS_ASSESSMENT", country="Sudan", sector="food security",
            context="humanitarian", thematic="Darfur food security needs assessment",
            cache_dir=self.cache)
        self.assertGreaterEqual(len(rel), 2)
        self.assertLessEqual(len(rel), 4)
        self.assertEqual(rel[0]["project_label"], "NRC_FoodSecurity_NeedsAssessment_Darfur_humanitarian")

    def test_section_specific_exemplars(self):
        from engine.tor.exemplars import retrieval
        ex = retrieval.retrieve_for_section(
            "METHODOLOGY", assignment_type="ENDLINE", country="Jordan", cache_dir=self.cache)
        self.assertTrue(ex)
        self.assertTrue(all(e["section_type"] == "METHODOLOGY" for e in ex))
        self.assertEqual(ex[0]["assignment_type"], "ENDLINE")  # Jordan endline ranks top

    def test_retrieval_summary_counts(self):
        from engine.tor.exemplars import retrieval
        s = retrieval.retrieval_summary(assignment_type="EVALUATION", country="Lebanon",
                                        cache_dir=self.cache)
        self.assertTrue(s["writing_dna_active"])
        self.assertEqual(s["historical_pairs"], 3)
        self.assertGreaterEqual(s["relevant_proposals_retrieved"], 2)


class TestStyleConformance(unittest.TestCase):
    def test_arfada_style_outscores_generic(self):
        from engine.tor.style_qa import conformance
        dna = {"paragraph_word_median": 45}
        self.assertGreater(conformance(_ARFADA_STYLE, dna), conformance(_GENERIC, dna))

    def test_generic_scores_low(self):
        from engine.tor.style_qa import conformance
        self.assertLess(conformance(_GENERIC, {"paragraph_word_median": 45}), 0.6)


class TestStyleQAChecks(unittest.TestCase):
    def test_filler_flagged(self):
        from engine.tor.style_qa import filler_findings
        f = filler_findings(_GENERIC)
        cats = {x["category"] for x in f}
        self.assertIn("generic_filler", cats)

    def test_clean_text_not_flagged_as_filler(self):
        from engine.tor.style_qa import filler_findings
        self.assertEqual(filler_findings(_ARFADA_STYLE), [])

    def test_uniform_paragraphs_flagged(self):
        from engine.tor.style_qa import uniformity_findings
        para = "word " * 20
        cand = {"blocks": [{"type": "paragraph", "text": para} for _ in range(5)]}
        cats = {x["category"] for x in uniformity_findings(cand)}
        self.assertIn("uniform_paragraphs", cats)

    def test_excessive_bullets_flagged(self):
        from engine.tor.style_qa import uniformity_findings
        cand = {"blocks": [{"type": "paragraph", "text": "Short intro."},
                           {"type": "bullet_list", "items": [f"item {i}" for i in range(12)]}]}
        cats = {x["category"] for x in uniformity_findings(cand)}
        self.assertIn("excessive_bullets", cats)

    def test_divergence_from_dna(self):
        from engine.tor.style_qa import divergence_findings
        cand = {"blocks": [{"type": "paragraph", "text": "word " * 150}]}
        f = divergence_findings(cand, {"paragraph_word_median": 40})
        self.assertTrue(any(x["category"] == "style_divergence" for x in f))

    def test_copy_findings_flag_reuse(self):
        from engine.tor.style_qa import copy_findings
        reused = ("The consultant will conduct a detailed inception phase and desk "
                  "review of all programme documents provided by the client before fieldwork.")
        f = copy_findings(reused, [reused])
        self.assertTrue(any(x["category"] == "suspicious_copy" for x in f))

    def test_style_qa_only_rewrites_wording(self):
        # findings never carry fact/number mutations; severity is WARNING/IMPROVEMENT
        from engine.tor.style_qa import style_qa_section
        cand = {"section_id": "METHODOLOGY",
                "blocks": [{"type": "paragraph", "text": _GENERIC}]}
        for f in style_qa_section(cand, {"paragraph_word_median": 45}, []):
            self.assertIn(f["severity"], ("WARNING", "IMPROVEMENT"))


class TestAntiCopy(unittest.TestCase):
    def test_long_shared_phrase_detected(self):
        from engine.tor.exemplars.anticopy import long_shared_phrases
        a = "we will conduct a detailed inception phase and desk review of all documents"
        b = "the team will conduct a detailed inception phase and desk review of all documents today"
        self.assertTrue(long_shared_phrases(a, [b]))

    def test_short_standard_phrase_acceptable(self):
        from engine.tor.exemplars.anticopy import long_shared_phrases
        self.assertEqual(long_shared_phrases("mixed methods approach", ["a mixed methods approach"]), [])


class TestStyleQAReport(unittest.TestCase):
    def test_report_on_run(self):
        from engine.tor.style_qa import style_qa_report
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            sd = run_dir / "generated_sections"
            sd.mkdir()
            (sd / "METHODOLOGY.json").write_text(json.dumps({
                "section_id": "METHODOLOGY",
                "blocks": [{"type": "paragraph", "text": _GENERIC}]}), encoding="utf-8")
            rep = style_qa_report(run_dir)
            self.assertEqual(rep["check"], "WRITING_DNA_STYLE_QA")
            self.assertEqual(rep["sections_checked"], 1)
            self.assertIn("WORDING ONLY", rep["note"])
            self.assertTrue(any(f["category"] == "generic_filler" for f in rep["findings"]))


class TestRegressionScenarios(unittest.TestCase):
    def test_south_darfur_style_beats_generic(self):
        from engine.tor.style_qa import conformance
        dna = {"paragraph_word_median": 45}
        self.assertGreater(conformance(_ARFADA_STYLE, dna), conformance(_GENERIC, dna) + 0.1)

    def test_jordan_draft_style_qa_runs(self):
        from tests.test_tor_analysis import _complete_run, _HomeIsolation
        from engine.tor.style_qa import style_qa_report
        with _HomeIsolation():
            with tempfile.TemporaryDirectory() as tmp:
                run_dir, _ = _complete_run(tmp)
                rep = style_qa_report(run_dir)
                self.assertEqual(rep["check"], "WRITING_DNA_STYLE_QA")
                self.assertGreaterEqual(rep["sections_checked"], 1)
                # style QA is advisory only — never CRITICAL/ERROR
                for f in rep["findings"]:
                    self.assertIn(f["severity"], ("WARNING", "IMPROVEMENT"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
