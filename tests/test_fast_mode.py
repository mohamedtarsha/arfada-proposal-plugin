"""v0.6.5 Fast Proposal Mode tests (workflow only; engines unchanged).

Covers the provisional-decision status, the autopilot auto-recommender + <=5
questions, the blocker taxonomy + internal gaps, the two-status QA, provisional
usability in generation, and the working-draft renderer. Regression scenarios use a
synthetic South Darfur conflict-context TOR and the Jordan GREEN backbone.

Run from plugin root:
    python -m pytest tests/test_fast_mode.py -v
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

os.environ.setdefault("ARFADA_HOME", tempfile.mkdtemp(prefix="arfada_fast_home_"))


# ---------------------------------------------------------------------------
# §4 provisional-decision status
# ---------------------------------------------------------------------------

class TestProvisionalStatus(unittest.TestCase):
    def _reg(self):
        from engine.tor.register import DecisionRegister, DecisionEntry, Status
        e = DecisionEntry(
            decision_id="d_kii", requirement_id="r1", decision_type="OPEN_PROPOSAL_DECISION",
            question="How many KIIs?", decision_status=Status.OPEN, selected_value=None,
            value_type="none", constraint_type="AT_LEAST", minimum=30, maximum=None,
            source_text="at least 30 KIIs", source_locator="", category="sampling",
            actor="bidder", reason="")
        reg = DecisionRegister(schema_version="1", run_id="r", tor_identity="t",
                               created_at="", updated_at="", status="OPEN", decisions=[e])
        return reg

    def test_provisional_recommend_sets_status_and_value(self):
        from engine.tor.register import provisional_recommend, Status
        reg = self._reg()
        r = provisional_recommend(reg, "d_kii", 30, rationale="TOR minimum")
        self.assertTrue(r["valid"])
        self.assertEqual(reg.decisions[0].decision_status, Status.PROVISIONAL)
        self.assertEqual(reg.decisions[0].selected_value, 30)

    def test_provisional_respects_tor_minimum(self):
        from engine.tor.register import provisional_recommend
        reg = self._reg()
        r = provisional_recommend(reg, "d_kii", 10)  # below TOR minimum 30
        self.assertFalse(r["valid"])

    def test_approve_provisional_promotes_to_resolved(self):
        from engine.tor.register import provisional_recommend, approve_provisional, Status
        reg = self._reg()
        provisional_recommend(reg, "d_kii", 35)
        r = approve_provisional(reg, "d_kii")
        self.assertTrue(r["valid"])
        self.assertEqual(reg.decisions[0].decision_status, Status.RESOLVED)

    def test_provisional_not_actionable_as_card(self):
        from engine.tor.register import Status
        self.assertNotIn(Status.PROVISIONAL, Status.actionable())
        self.assertIn(Status.PROVISIONAL, Status.usable())


# ---------------------------------------------------------------------------
# §3/§2 autopilot
# ---------------------------------------------------------------------------

class TestAutopilot(unittest.TestCase):
    def _tor(self, confidence="HIGH"):
        return {"assignment_type": {"assignment_type": "EVALUATION", "confidence": confidence},
                "metadata": {"country": {"value": "Jordan"},
                             "assignment": {"value": "Endline Evaluation of X"}}}

    def _cands(self):
        return [
            {"decision_id": "d_kii", "requirement_id": "r2", "is_human_decision": True,
             "decision_type": "OPEN_PROPOSAL_DECISION", "constraint_type": "AT_LEAST",
             "minimum": 30, "question": "KIIs?", "category": "sampling",
             "source_text": "at least 30 KIIs"},
            {"decision_id": "d_meth", "requirement_id": "r3", "is_human_decision": True,
             "decision_type": "OPEN_PROPOSAL_DECISION", "constraint_type": "ENUM",
             "allowed_options": ["Mixed-methods", "Qualitative"], "question": "Method?",
             "category": "methodology", "source_text": "methodology"},
        ]

    def test_auto_recommends_each_decision(self):
        from engine.tor import autopilot
        recs = autopilot.recommend_decisions(self._cands())
        by = {r["decision_id"]: r["value"] for r in recs}
        self.assertEqual(by["d_kii"], 30)
        self.assertEqual(by["d_meth"], "MIXED-METHODS")

    def test_max_five_questions(self):
        from engine.tor import autopilot
        reqs = [{"req_id": "r1", "category": "submission", "mandatory": True,
                 "text": "detailed budget and financial offer required"}]
        q = autopilot.build_questions(self._tor(), reqs)
        self.assertLessEqual(len(q), 5)

    def test_ambiguous_assignment_type_raises_question(self):
        from engine.tor import autopilot
        q = autopilot.build_questions(self._tor(confidence="LOW"), [])
        self.assertTrue(any(x["key"] == "assignment_type_ambiguous" for x in q))

    def test_high_confidence_no_type_question(self):
        from engine.tor import autopilot
        q = autopilot.build_questions(self._tor(confidence="HIGH"), [])
        self.assertFalse(any(x["key"] == "assignment_type_ambiguous" for x in q))

    def test_budget_question_only_without_rates(self):
        from engine.tor import autopilot
        reqs = [{"req_id": "r1", "category": "submission", "mandatory": True,
                 "text": "financial proposal with detailed budget"}]
        self.assertTrue(any(x["key"] == "budget_ceiling"
                            for x in autopilot.build_questions(self._tor(), reqs)))
        self.assertFalse(any(x["key"] == "budget_ceiling"
                             for x in autopilot.build_questions(self._tor(), reqs,
                                                                knowledge_has_rates=True)))

    def test_full_autopilot_shape(self):
        from engine.tor import autopilot
        r = autopilot.autopilot(self._tor(), [], self._cands(), knowledge=None)
        for key in ("recommendations", "questions", "team", "experience", "proposed_setup"):
            self.assertIn(key, r)


# ---------------------------------------------------------------------------
# §5/§6 blockers + internal gaps
# ---------------------------------------------------------------------------

class TestBlockers(unittest.TestCase):
    def test_submission_critical_is_final_not_draft(self):
        from engine.tor.blockers import classify_finding, FINAL_SUBMISSION_BLOCKER
        f = {"check": "SUBMISSION", "severity": "CRITICAL",
             "category": "mandatory_submission_missing"}
        self.assertEqual(classify_finding(f), FINAL_SUBMISSION_BLOCKER)

    def test_technical_critical_is_draft_blocker(self):
        from engine.tor.blockers import classify_finding, DRAFT_BLOCKER
        f = {"check": "CONTRADICTION", "severity": "CRITICAL", "category": "x"}
        self.assertEqual(classify_finding(f), DRAFT_BLOCKER)

    def test_scoring_is_improvement(self):
        from engine.tor.blockers import classify_finding, IMPROVEMENT
        f = {"check": "SUBMISSION", "severity": "WARNING",
             "category": "scoring_submission_missing"}
        self.assertEqual(classify_finding(f), IMPROVEMENT)

    def test_internal_gaps_render(self):
        from engine.tor.blockers import classify_blockers, render_internal_gaps
        qa = {"findings": [
            {"check": "SUBMISSION", "severity": "CRITICAL",
             "category": "mandatory_submission_missing",
             "message": "Mandatory submission item missing: Registration certificate",
             "recommended_action": "Provide it"}]}
        md = render_internal_gaps(classify_blockers(qa),
                                  extra_notes=["Ahmed availability not confirmed"])
        self.assertIn("Final-submission blockers", md)
        self.assertIn("Registration certificate", md)
        self.assertIn("Ahmed availability", md)
        # the file is explicitly marked internal-only (not for the client draft)
        self.assertIn("NOT for the client draft", md.splitlines()[0])


# ---------------------------------------------------------------------------
# §12 two-status QA
# ---------------------------------------------------------------------------

class TestTwoStatus(unittest.TestCase):
    def _mkrun(self, tmp, requirements=None, sections=None, tor=None):
        run_dir = Path(tmp)
        (run_dir / "tor_analysis.json").write_text(json.dumps(tor or {"run_id": "r1"}))
        if requirements is not None:
            (run_dir / "requirements.json").write_text(
                json.dumps({"requirements": requirements}))
        if sections is not None:
            sd = run_dir / "generated_sections"
            sd.mkdir(exist_ok=True)
            status = {"sections": {}}
            for sid, cand in sections.items():
                (sd / f"{sid}.json").write_text(json.dumps(cand))
                status["sections"][sid] = {"status": "READY"}
            (run_dir / "generation_status.json").write_text(json.dumps(status))
        return run_dir

    def test_missing_package_is_not_ready_but_technical_ready(self):
        from engine.tor.fast_qa import two_status_report, TECH_READY, PKG_NOT_READY
        with tempfile.TemporaryDirectory() as tmp:
            self._mkrun(tmp, requirements=[
                {"req_id": "s1", "category": "submission", "mandatory": True,
                 "text": "A registration certificate must be submitted."}])
            rep = two_status_report(tmp)
            self.assertEqual(rep["submission_package_status"], PKG_NOT_READY)
            self.assertEqual(rep["technical_draft_status"], TECH_READY)
            self.assertTrue(rep["final_submission_blockers"])
            self.assertFalse(rep["draft_blockers"])

    def test_technical_contradiction_blocks_draft(self):
        from engine.tor.fast_qa import two_status_report, TECH_BLOCKED
        with tempfile.TemporaryDirectory() as tmp:
            # two conflicting KII counts across sections → CONTRADICTION (draft blocker)
            self._mkrun(tmp, sections={
                "METHODOLOGY": {"section_id": "METHODOLOGY", "requirement_response_ledger": [],
                                "blocks": [{"type": "paragraph",
                                            "text": "We will conduct 30 KIIs."}]},
                "DATA_COLLECTION": {"section_id": "DATA_COLLECTION",
                                    "requirement_response_ledger": [],
                                    "blocks": [{"type": "paragraph",
                                                "text": "A total of 50 KIIs will be held."}]}})
            rep = two_status_report(tmp)
            self.assertEqual(rep["technical_draft_status"], TECH_BLOCKED)


# ---------------------------------------------------------------------------
# §4 provisional usable in generation
# ---------------------------------------------------------------------------

class TestProvisionalInGeneration(unittest.TestCase):
    def test_provisional_decision_value_used_in_packet(self):
        from engine.tor.generation import build_packet
        section = {"section_id": "METHODOLOGY", "title": "Methodology", "purpose": "",
                   "requirement_ids": ["r1"], "preferred_modes": ["PROSE"],
                   "decision_dependencies": ["d_kii"], "needs_arfada_evidence": False}
        register = {"decisions": [{"decision_id": "d_kii", "requirement_id": "r1",
                                   "decision_status": "PROVISIONAL_RECOMMENDATION",
                                   "selected_value": 30, "constraint_type": "AT_LEAST",
                                   "minimum": 30, "maximum": None}]}
        pk = build_packet(section=section, slots=[], requirements_by_id={},
                          decision_register=register, language="english",
                          assignment_metadata={}, verified_arfada_facts=[],
                          historical_exemplars=[], writing_dna={})
        applied = pk["applied_decisions"]
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0]["status"], "PROVISIONAL_RECOMMENDATION")
        self.assertEqual(applied[0]["selected_value"], 30)


# ---------------------------------------------------------------------------
# Regression: South Darfur (synthetic) + Jordan (GREEN backbone)
# ---------------------------------------------------------------------------

class TestSouthDarfurScenario(unittest.TestCase):
    """Conflict-context TOR → fast setup with few questions; package gaps don't block."""

    def test_autopilot_few_questions_and_full_setup(self):
        from engine.tor import autopilot
        tor = {"assignment_type": {"assignment_type": "NEEDS_ASSESSMENT", "confidence": "HIGH"},
               "metadata": {"country": {"value": "Sudan"},
                            "assignment": {"value": "South Darfur multi-sector needs assessment"},
                            "sector": {"value": "Food security"}}}
        reqs = [{"req_id": "r1", "category": "methodology", "mandatory": True,
                 "text": "Mixed-methods assessment across conflict-affected localities."},
                {"req_id": "r2", "category": "submission", "mandatory": True,
                 "text": "Registration certificate and tax clearance required."}]
        cands = [{"decision_id": "d_hh", "requirement_id": "r1", "is_human_decision": True,
                  "decision_type": "OPEN_PROPOSAL_DECISION", "constraint_type": "RANGE",
                  "minimum": 400, "maximum": 600, "question": "Household sample?",
                  "category": "sampling", "source_text": "between 400 and 600 households"}]
        result = autopilot.autopilot(tor, reqs, cands, knowledge=None)
        self.assertLessEqual(result["question_count"], 5)
        self.assertEqual(result["recommendations"][0]["value"], 500)  # midpoint
        self.assertEqual(result["proposed_setup"]["assignment_type"], "NEEDS_ASSESSMENT")

    def test_registration_gap_does_not_block_draft(self):
        from engine.tor.fast_qa import two_status_report, TECH_READY, PKG_NOT_READY
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "tor_analysis.json").write_text(json.dumps({"run_id": "sd"}))
            (run_dir / "requirements.json").write_text(json.dumps({"requirements": [
                {"req_id": "s1", "category": "submission", "mandatory": True,
                 "text": "Company registration certificate must be included."}]}))
            rep = two_status_report(run_dir)
            self.assertEqual(rep["technical_draft_status"], TECH_READY)
            self.assertEqual(rep["submission_package_status"], PKG_NOT_READY)


class TestJordanFastDraft(unittest.TestCase):
    def test_working_draft_renders_and_two_status(self):
        from tests.test_tor_analysis import _complete_run, _HomeIsolation
        from engine.tor.fast_qa import two_status_report, TECH_READY
        with _HomeIsolation():
            with tempfile.TemporaryDirectory() as tmp:
                run_dir, run = _complete_run(tmp)
                # render a WORKING DRAFT v1 (gap-tolerant, client-style)
                rc, out, err = run(["scripts/render_docx.py", str(run_dir), "--draft"])
                self.assertEqual(rc, 0, err)
                res = json.loads(out)
                self.assertEqual(res["variant"], "draft_v1")
                self.assertTrue((run_dir / "proposal_draft_v1.docx").exists())
                # two-status: technical ready on the clean backbone
                rep = two_status_report(run_dir)
                self.assertEqual(rep["technical_draft_status"], TECH_READY)
                self.assertNotIn("[To be provided", rep["internal_gaps_md"])

    def test_missing_mandatory_submission_item_is_package_not_draft(self):
        from tests.test_tor_analysis import _complete_run, _HomeIsolation
        from engine.tor.fast_qa import two_status_report, TECH_READY, PKG_NOT_READY
        with _HomeIsolation():
            with tempfile.TemporaryDirectory() as tmp:
                run_dir, _ = _complete_run(tmp)
                reqs = json.loads((run_dir / "requirements.json").read_text(encoding="utf-8"))
                reqs["requirements"].append({
                    "req_id": "extra_reg", "category": "submission", "mandatory": True,
                    "actor": "BIDDER",
                    "text": "A company registration certificate must be submitted."})
                (run_dir / "requirements.json").write_text(json.dumps(reqs), encoding="utf-8")
                rep = two_status_report(run_dir)
                self.assertEqual(rep["submission_package_status"], PKG_NOT_READY)
                self.assertEqual(rep["technical_draft_status"], TECH_READY)


if __name__ == "__main__":
    unittest.main(verbosity=2)
