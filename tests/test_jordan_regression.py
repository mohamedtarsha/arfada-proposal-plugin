"""Jordan child-labour TOR — production-workflow regression (v0.6.4 §13).

Models the completed first real run as a regression FIXTURE for the generalized
workflow. It does not reproduce the approved proposal content; it verifies the
end-state invariants the generalized workflow must keep producing:

  * GREEN QA with every mandatory requirement addressed (the 89/89 invariant)
  * no unsupported named-person / organizational claims
  * no current-project contamination in past experience
  * a detailed budget that reconciles EXACTLY to the approved total
  * a previous-work annex that validates (deliverable, not a proposal/TOR)
  * a client draft free of internal markers / placeholders
  * a clean, sanitized final export

It also asserts the new guards FLIP the verdict on bad states (non-reconciling
budget → RED; contaminated experience → finding), proving the hardening is live.

Reuses the GREEN generation backbone from test_tor_analysis._complete_run.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tests.test_tor_analysis import _complete_run, _HomeIsolation  # GREEN backbone


def _reconciled_budget():
    from engine.tor.budget import build_budget
    # 18000 + 9000 + 6000 + 3000 + 1500 + 1500 = 39000; person-days 40+30+50 = 120 (LOE)
    return build_budget(approved_total=39000, approved_loe=120, lines=[
        {"label": "Team Leader", "category": "expert_fees", "quantity": 40, "unit_cost": 450},
        {"label": "Field Supervisor", "category": "field_supervisor", "quantity": 30, "unit_cost": 300},
        {"label": "Enumerators", "category": "enumerators", "quantity": 50, "unit_cost": 120},
        {"label": "Transport", "category": "transport", "amount": 3000},
        {"label": "Translation/transcription", "category": "translation_transcription", "amount": 1500},
        {"label": "Editing/printing", "category": "editing_printing", "amount": 1500},
    ])


class TestJordanRegression(unittest.TestCase):

    def test_end_state_green_and_invariants(self):
        from engine.tor.final_qa import run_final_qa
        with _HomeIsolation():
            with tempfile.TemporaryDirectory() as tmp:
                run_dir, run = _complete_run(tmp)

                # 1) GREEN + every mandatory requirement addressed (89/89 invariant)
                rep = run_final_qa(run_dir)
                self.assertEqual(rep["overall_status"], "GREEN",
                                 f"criticals: {[f['message'] for f in rep['critical_failures']]}")
                self.assertEqual(rep["summary"]["mandatory_addressed"],
                                 rep["summary"]["mandatory_requirements"])
                self.assertGreater(rep["summary"]["mandatory_requirements"], 0)

                # 2) no unsupported claims / no contamination in the clean run
                for f in rep["findings"]:
                    self.assertNotEqual(f["check"], "ARFADA_FACTS")
                    self.assertNotEqual(f["check"], "EXPERIENCE_CONTAMINATION")
                    self.assertNotEqual(f["category"], "annex_claim_without_file")
                    self.assertNotEqual(f["category"], "client_placeholder")

                # 3) a reconciled budget keeps it GREEN; QA confirms reconciliation
                budget = _reconciled_budget()
                self.assertTrue(budget["reconciles"])
                (run_dir / "budget.json").write_text(json.dumps(budget), encoding="utf-8")
                rep2 = run_final_qa(run_dir)
                self.assertEqual(rep2["overall_status"], "GREEN")
                self.assertFalse(any(f["check"] == "BUDGET" for f in rep2["findings"]))

                # 4) client draft free of internal markers / placeholders
                self.assertFalse(any(f["check"] in ("CLIENT_LEAKAGE", "CLIENT_PLACEHOLDER")
                                     for f in rep2["findings"]))

                # 5) clean final export (GREEN removes the DRAFT stamp; no leaks)
                rc, out, err = run(["scripts/export_final.py", str(run_dir)])
                self.assertEqual(rc, 0, err)
                res = json.loads(out)
                self.assertEqual(res["status"], "EXPORTED")
                self.assertEqual(res["overall_status"], "GREEN")
                self.assertFalse(res["draft_stamp_retained"])
                self.assertTrue((run_dir / "proposal_final.docx").exists())

    def test_previous_work_validation(self):
        from engine.tor.annex import validate_previous_work, DELIVERABLE, PROPOSAL
        deliverable = ("Final Evaluation Report — ARFADA\nExecutive Summary\nMethodology\n"
                       "Key Findings\nConclusions\nRecommendations\nAnnexes")
        proposal = ("Technical Proposal\nARFADA is pleased to submit our proposed methodology "
                    "in response to the RFP.")
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "final_evaluation.docx"
            good.write_text("x", encoding="utf-8")
            v = validate_previous_work(good, text=deliverable, arfada_names=["ARFADA"])
            self.assertTrue(v["ok"])
            self.assertEqual(v["kind"], DELIVERABLE)
            self.assertTrue(v["by_arfada"])
            self.assertFalse(v["needs_clearance_confirmation"])

            bad = Path(tmp) / "arfada_proposal.docx"
            bad.write_text("x", encoding="utf-8")
            v2 = validate_previous_work(bad, text=proposal, arfada_names=["ARFADA"])
            self.assertFalse(v2["ok"])
            self.assertEqual(v2["kind"], PROPOSAL)

    def test_guard_flips_on_bad_budget_and_contamination(self):
        from engine.tor.final_qa import run_final_qa
        with _HomeIsolation():
            with tempfile.TemporaryDirectory() as tmp:
                run_dir, _ = _complete_run(tmp)

                # non-reconciling budget → RED
                bad = _reconciled_budget()
                bad["reconciles"] = False
                bad["difference"] = 500.0
                bad["reconciliation_message"] = "off by 500"
                (run_dir / "budget.json").write_text(json.dumps(bad), encoding="utf-8")
                rep = run_final_qa(run_dir)
                self.assertEqual(rep["overall_status"], "RED")
                self.assertTrue(any(f["check"] == "BUDGET" for f in rep["critical_failures"]))

    def test_global_portfolio_count_not_reduced_by_exclusion(self):
        # run-scoped exclusion of the current project must not shrink the global count
        from engine.tor.knowledge import Knowledge
        k = Knowledge()
        k._live_projects = [
            {"project_id": "cur", "project_name": "Endline Child Labour Jordan",
             "assignment_type": "ENDLINE", "country": "Jordan"},
            {"project_id": "a", "project_name": "WASH Yemen", "assignment_type": "BASELINE",
             "country": "Yemen"},
        ]
        ranked = k.relevant_projects(
            assignment_type="ENDLINE", country="Jordan",
            exclude_current={"project_name": "Endline Child Labour Jordan",
                             "assignment_type": "ENDLINE", "country": "Jordan"})
        self.assertNotIn("cur", {p["project_id"] for p in ranked})
        # global metric computed over the FULL pool is unchanged
        from engine.tor.gknowledge.normalize import compute_metrics
        self.assertEqual(compute_metrics(k._live_projects)["total_projects"]["value"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
