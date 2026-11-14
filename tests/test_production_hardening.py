"""v0.6.4 production-hardening tests (workflow lessons from the first real run).

Covers the new deterministic modules and the Final-QA hardening in isolation. No
proposal is generated here (the Jordan end-to-end regression lives in
test_jordan_regression.py). Run from plugin root:
    python -m pytest tests/test_production_hardening.py -v
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

os.environ.setdefault("ARFADA_HOME", tempfile.mkdtemp(prefix="arfada_ph_home_"))


def _mkrun(tmp: str, **artifacts) -> Path:
    """Create a run dir with just the named JSON artifacts (minimal QA input)."""
    run_dir = Path(tmp)
    (run_dir / "tor_analysis.json").write_text(
        json.dumps(artifacts.get("tor", {"run_id": "r1"})), encoding="utf-8")
    if "requirements" in artifacts:
        (run_dir / "requirements.json").write_text(
            json.dumps({"requirements": artifacts["requirements"]}), encoding="utf-8")
    if "sections" in artifacts:
        sd = run_dir / "generated_sections"
        sd.mkdir(exist_ok=True)
        status = {"sections": {}}
        for sid, cand in artifacts["sections"].items():
            (sd / f"{sid}.json").write_text(json.dumps(cand), encoding="utf-8")
            status["sections"][sid] = {"status": "READY"}
        (run_dir / "generation_status.json").write_text(json.dumps(status), encoding="utf-8")
    if "budget" in artifacts:
        (run_dir / "budget.json").write_text(json.dumps(artifacts["budget"]), encoding="utf-8")
    return run_dir


# ---------------------------------------------------------------------------
# §12 version
# ---------------------------------------------------------------------------

class TestVersion(unittest.TestCase):
    def test_plugin_version_matches_manifest(self):
        from engine.tor.version import plugin_version
        manifest = json.loads((_ROOT / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(plugin_version(), manifest["version"])

    def test_no_hardcoded_old_versions_in_runtime(self):
        import re
        bad = []
        for script in ("scripts/analyze_tor.py", "scripts/final_qa.py",
                       "scripts/export_final.py", "scripts/render_docx.py",
                       "scripts/build_blueprint.py"):
            txt = (_ROOT / script).read_text(encoding="utf-8")
            # a hard-coded version assigned to plugin_version is the smell
            for m in re.finditer(r'plugin_version\s*[=:]\s*"(0\.\d\.\d)"', txt):
                bad.append((script, m.group(1)))
        self.assertEqual(bad, [], f"hard-coded plugin_version literals: {bad}")


# ---------------------------------------------------------------------------
# §4 staff facts
# ---------------------------------------------------------------------------

class TestYearsParsing(unittest.TestCase):
    def setUp(self):
        from engine.tor.gknowledge.normalize import _experience_years
        self.f = _experience_years

    def test_real_experience(self):
        self.assertEqual(self.f("Over 12 years of professional experience in M&E.")[0], 12)

    def test_age_rejected(self):
        self.assertIsNone(self.f("Beneficiaries are children aged 5-17 years old.")[0])

    def test_project_duration_rejected(self):
        self.assertIsNone(self.f("Led a 20-year project under the grant.")[0])

    def test_beneficiary_count_rejected(self):
        self.assertIsNone(self.f("Served households with children 6 years old.")[0])

    def test_date_range_rejected(self):
        self.assertIsNone(self.f("Worked 2018-2020 on the baseline.")[0])

    def test_takes_max_qualified(self):
        self.assertEqual(self.f("8 years experience; later 15 years of evaluation experience.")[0], 15)


class TestPromoteStaffFact(unittest.TestCase):
    def test_structure_and_provenance(self):
        from engine.tor.gknowledge.normalize import promote_staff_fact
        f = promote_staff_fact(name="A. Expert", attribute="years_experience", value=12,
                               source_file="cvs/a_expert.pdf",
                               quote="12 years of professional experience")
        self.assertTrue(f["fact_id"].startswith("stafffact_"))
        self.assertTrue(f["verified"])
        self.assertEqual(f["provenance"]["method"], "cv_read_promoted")
        self.assertEqual(f["provenance"]["source_file"], "cvs/a_expert.pdf")
        self.assertIn("12 years", f["provenance"]["quote"])


# ---------------------------------------------------------------------------
# §5 relevant experience
# ---------------------------------------------------------------------------

class TestRelevantExperience(unittest.TestCase):
    def _k(self, projects):
        from engine.tor.knowledge import Knowledge
        k = Knowledge()
        k._live_projects = projects  # inject pool
        return k

    def test_richer_scoring_client_and_thematic(self):
        k = self._k([
            {"project_id": "p1", "project_name": "Child labour endline Jordan",
             "assignment_type": "ENDLINE", "country": "Jordan", "sector": "Child protection",
             "client": "Save the Children", "description": "child labour survey"},
            {"project_id": "p2", "project_name": "WASH baseline Yemen",
             "assignment_type": "BASELINE", "country": "Yemen", "sector": "WASH",
             "client": "UNICEF"},
        ])
        out = k.relevant_projects(assignment_type="ENDLINE", country="Jordan",
                                  client="Save the Children", thematic="child labour", limit=5)
        self.assertEqual(out[0]["project_id"], "p1")
        self.assertIn("client", out[0]["scored_on"])
        self.assertIn("thematic", out[0]["scored_on"])

    def test_current_project_excluded(self):
        k = self._k([
            {"project_id": "cur", "project_name": "Endline Evaluation Child Labour Jordan",
             "assignment_type": "ENDLINE", "country": "Jordan"},
            {"project_id": "old", "project_name": "Education endline Jordan",
             "assignment_type": "ENDLINE", "country": "Jordan"},
        ])
        out = k.relevant_projects(
            assignment_type="ENDLINE", country="Jordan",
            exclude_current={"project_name": "Endline Evaluation Child Labour Jordan",
                             "assignment_type": "ENDLINE", "country": "Jordan"}, limit=5)
        ids = {p["project_id"] for p in out}
        self.assertNotIn("cur", ids)
        self.assertIn("old", ids)

    def test_exclusion_does_not_change_global_metric(self):
        # global metric comes from compute_metrics over the FULL pool, unaffected.
        from engine.tor.gknowledge.normalize import compute_metrics
        pool = [{"project_id": f"p{i}", "country": "Jordan"} for i in range(10)]
        self.assertEqual(compute_metrics(pool)["total_projects"]["value"], 10)


# ---------------------------------------------------------------------------
# §2 submission classifier
# ---------------------------------------------------------------------------

class TestSubmissionClassifier(unittest.TestCase):
    def test_item_identity_and_obligation(self):
        from engine.tor.submission import build_submission_checklist, MANDATORY, SCORING, OPTIONAL
        reqs = [
            {"req_id": "a", "category": "submission", "mandatory": True,
             "text": "Bidders must submit a detailed budget breakdown."},
            {"req_id": "b", "category": "submission", "mandatory": False,
             "text": "An example of previous work may be included if available."},
            {"req_id": "c", "category": "submission", "mandatory": True,
             "text": "Team CVs will be scored (20 points)."},
            {"req_id": "d", "category": "methodology", "mandatory": True, "text": "Describe methods."},
        ]
        cl = build_submission_checklist(reqs)
        self.assertEqual(len(cl), 3)  # methodology excluded
        by = {e["requirement_id"]: e for e in cl}
        self.assertEqual(by["a"]["item_key"], "detailed_budget")
        self.assertEqual(by["a"]["obligation"], MANDATORY)
        self.assertEqual(by["b"]["item_key"], "previous_work")
        self.assertEqual(by["b"]["obligation"], OPTIONAL)
        self.assertEqual(by["c"]["item_key"], "cv_annex")
        self.assertEqual(by["c"]["obligation"], SCORING)


# ---------------------------------------------------------------------------
# §6 previous-work annex
# ---------------------------------------------------------------------------

class TestAnnexClassification(unittest.TestCase):
    def test_evaluation_deliverable_accepted(self):
        from engine.tor.annex import classify_document, DELIVERABLE
        text = ("Final Evaluation Report\nExecutive Summary\nMethodology\nKey Findings\n"
                "Conclusions\nRecommendations\nAnnexes")
        self.assertEqual(classify_document(text=text, file_name="final_report.docx")["kind"],
                         DELIVERABLE)

    def test_proposal_rejected(self):
        from engine.tor.annex import classify_document, PROPOSAL
        text = "Technical Proposal\nWe are pleased to submit our proposed approach and methodology."
        self.assertEqual(classify_document(text=text, file_name="ARFADA_Proposal.docx")["kind"],
                         PROPOSAL)

    def test_tor_rejected(self):
        from engine.tor.annex import classify_document, TOR
        text = "Terms of Reference\nThe consultant shall deliver... Deadline for submission."
        self.assertEqual(classify_document(text=text, file_name="ToR_endline.pdf")["kind"], TOR)

    def test_branding_rejected(self):
        from engine.tor.annex import classify_document, BRANDING
        text = "Brand Guidelines\nLogo usage and visual identity for all materials."
        self.assertEqual(classify_document(text=text, file_name="brand.pdf")["kind"], BRANDING)

    def test_missing_file_not_ok(self):
        from engine.tor.annex import validate_previous_work
        v = validate_previous_work("/no/such/file_report.docx", text="")
        self.assertFalse(v["ok"])
        self.assertFalse(v["file_exists"])

    def test_clearance_required_when_authorship_absent(self):
        from engine.tor.annex import validate_previous_work
        text = "Final Evaluation Report\nExecutive Summary\nFindings\nRecommendations\nMethodology"
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "report.docx"
            p.write_text("x", encoding="utf-8")
            v = validate_previous_work(p, text=text, arfada_names=["ARFADA"])
            self.assertTrue(v["acceptable"])
            self.assertTrue(v["needs_clearance_confirmation"])


# ---------------------------------------------------------------------------
# §7 budget
# ---------------------------------------------------------------------------

class TestBudget(unittest.TestCase):
    def _lines(self):
        return [
            {"label": "TL", "category": "expert_fees", "quantity": 20, "unit_cost": 300},
            {"label": "Enum", "category": "enumerators", "quantity": 20, "unit_cost": 100},
            {"label": "VAT", "category": "taxes_mandatory", "percent": 25},
        ]

    def test_reconciles_exact(self):
        from engine.tor.budget import build_budget
        b = build_budget(approved_total=10000, approved_loe=40, lines=self._lines())
        self.assertTrue(b["reconciles"])
        self.assertEqual(b["computed_total"], 10000.0)
        self.assertTrue(b["loe_check"]["matches"])

    def test_does_not_reconcile(self):
        from engine.tor.budget import build_budget
        b = build_budget(approved_total=12000, lines=self._lines())
        self.assertFalse(b["reconciles"])
        self.assertNotEqual(b["difference"], 0)

    def test_missing_input_never_invented(self):
        from engine.tor.budget import build_budget
        b = build_budget(approved_total=5000, lines=[{"label": "Transport",
                                                      "category": "transport"}])
        self.assertFalse(b["reconciles"])
        self.assertIn("Transport", b["missing_inputs"])


# ---------------------------------------------------------------------------
# §11 package
# ---------------------------------------------------------------------------

class TestPackage(unittest.TestCase):
    def test_missing_reported_by_identity(self):
        from engine.tor.package import check_submission_package
        with tempfile.TemporaryDirectory() as tmp:
            res = check_submission_package(tmp, item_keys=["cv_annex", "previous_work",
                                                           "detailed_budget"])
            self.assertFalse(res["complete"])
            self.assertIn("Required CVs", res["missing"])
            self.assertIn("Previous-work example", res["missing"])

    def test_present_files_detected(self):
        from engine.tor.package import check_submission_package
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "proposal_final.docx").write_text("x", encoding="utf-8")
            cvs = run_dir / "annexes" / "cvs"
            cvs.mkdir(parents=True)
            (cvs / "a.docx").write_text("x", encoding="utf-8")
            res = check_submission_package(run_dir, item_keys=["cv_annex"], min_cvs=1)
            self.assertTrue(res["complete"])


# ---------------------------------------------------------------------------
# §1 run init
# ---------------------------------------------------------------------------

class TestRunInit(unittest.TestCase):
    def test_summary_keys_and_compact(self):
        from engine.tor import run_init
        s = run_init.gather_init_status()
        for key in ("plugin_version", "knowledge", "master_tracker", "staff_cvs",
                    "company_documents", "previous_work_library", "writing_dna",
                    "historical_pairs", "knowledge_snapshot_version"):
            self.assertIn(key, s)
        compact = run_init.compact_summary(s)
        self.assertIn("Historical pairs:", compact)
        self.assertIn("Plugin: v", compact)


# ---------------------------------------------------------------------------
# §2/§9 Final QA — isolated checks
# ---------------------------------------------------------------------------

class TestQASubmissionIdentity(unittest.TestCase):
    def test_mandatory_missing_is_red_with_item_name(self):
        from engine.tor.final_qa import run_final_qa
        with tempfile.TemporaryDirectory() as tmp:
            _mkrun(tmp, requirements=[
                {"req_id": "s1", "category": "submission", "mandatory": True,
                 "text": "Bidders must submit a detailed budget."}])
            rep = run_final_qa(tmp)
            self.assertEqual(rep["overall_status"], "RED")
            msgs = " ".join(f["message"] for f in rep["critical_failures"])
            self.assertIn("Detailed budget", msgs)

    def test_scoring_missing_is_not_red(self):
        from engine.tor.final_qa import run_final_qa
        with tempfile.TemporaryDirectory() as tmp:
            _mkrun(tmp, requirements=[
                {"req_id": "s1", "category": "submission", "mandatory": True,
                 "text": "Team CVs will be scored (30 points)."}])
            rep = run_final_qa(tmp)
            self.assertNotEqual(rep["overall_status"], "RED")  # competitive → YELLOW at most
            self.assertEqual(rep["summary"]["critical_failures"], 0)


class TestQANewChecks(unittest.TestCase):
    def test_budget_reconciliation_red(self):
        from engine.tor.final_qa import run_final_qa
        with tempfile.TemporaryDirectory() as tmp:
            _mkrun(tmp, budget={"reconciles": False, "missing_inputs": [],
                                "reconciliation_message": "off by 500"})
            rep = run_final_qa(tmp)
            self.assertEqual(rep["overall_status"], "RED")
            self.assertTrue(any(f["check"] == "BUDGET" for f in rep["critical_failures"]))

    def test_current_project_contamination(self):
        from engine.tor.final_qa import run_final_qa
        with tempfile.TemporaryDirectory() as tmp:
            tor = {"run_id": "r1", "metadata": {"assignment": {
                "value": "Endline Evaluation of the Childlabour Response in Zarqa"}}}
            _mkrun(tmp, tor=tor, sections={"EXPERIENCE": {
                "section_id": "EXPERIENCE",
                "blocks": [{"type": "paragraph", "text":
                            "ARFADA delivered the childlabour response in Zarqa previously."}],
                "requirement_response_ledger": []}})
            rep = run_final_qa(tmp)
            self.assertTrue(any(f["check"] == "EXPERIENCE_CONTAMINATION"
                                for f in rep["findings"]))

    def test_claimed_annex_without_file(self):
        from engine.tor.final_qa import run_final_qa
        with tempfile.TemporaryDirectory() as tmp:
            _mkrun(tmp, sections={"TEAM": {
                "section_id": "TEAM",
                "blocks": [{"type": "paragraph", "text":
                            "The CVs of all proposed experts are annexed to this proposal."}],
                "requirement_response_ledger": []}})
            rep = run_final_qa(tmp)
            self.assertTrue(any(f["category"] == "annex_claim_without_file"
                                for f in rep["critical_failures"]))

    def test_sample_arithmetic(self):
        from engine.tor.final_qa import run_final_qa
        with tempfile.TemporaryDirectory() as tmp:
            _mkrun(tmp, sections={"METHODOLOGY": {
                "section_id": "METHODOLOGY",
                "blocks": [{"type": "paragraph", "text":
                            "A total sample of 100 respondents: 40 women, 30 men, 20 youth."}],
                "requirement_response_ledger": []}})
            rep = run_final_qa(tmp)
            self.assertTrue(any(f["check"] == "SAMPLING" for f in rep["findings"]))


class TestExportSanitize(unittest.TestCase):
    def _docx(self, path, lines):
        deps = _ROOT / ".mcp_deps"
        if deps.exists() and str(deps) not in sys.path:
            sys.path.insert(0, str(deps))
        from docx import Document
        d = Document()
        for ln in lines:
            d.add_paragraph(ln)
        d.save(str(path))

    def test_green_removes_draft_and_placeholder(self):
        from scripts.export_final import sanitize_final
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "proposal_final.docx"
            self._docx(p, ["DRAFT — HUMAN REVIEW REQUIRED", "Real content.",
                           "[To be provided: budget]"])
            res = sanitize_final(p, keep_draft_stamp=False)
            self.assertTrue(res["ok"])
            self.assertIn("draft_stamp", res["removed"])
            self.assertIn("placeholder", res["removed"])

    def test_leak_detected(self):
        from scripts.export_final import sanitize_final
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "proposal_final.docx"
            self._docx(p, ["Content references Master Tracker metrics."])
            res = sanitize_final(p, keep_draft_stamp=False)
            self.assertFalse(res["ok"])
            self.assertTrue(res["leaks"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
