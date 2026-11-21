"""v0.6.14 regression — confirmed fresh v0.6.13 South Darfur run.

RESPONSE_STATUS (does the proposal TEXT respond?) and EVIDENCE_STATUS (does ARFADA hold
proof?) are independent. A qualification the text answers but the CVs do not evidence is
ADDRESSED + GAP (QUALIFICATION_READINESS AT_RISK): it never becomes NOT_ADDRESSED and
never blocks the technical draft. RESPONSE_STATUS is computed from the text; the ledger's
status label (or an injected response_status) cannot change it.

    python -m pytest tests/test_v0614_response_vs_evidence.py -v
Optional: ARFADA_V0613_RUN=<run_artifacts of the fresh v0.6.13 South Darfur run>.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("ARFADA_HOME", tempfile.mkdtemp(prefix="arfada_v0614_home_"))

from engine.tor import response_coverage as RC  # noqa: E402
from engine.tor import requirement_evidence as RE  # noqa: E402

SADD = {"req_id": "r_sadd", "category": "team", "mandatory": True, "actor": "BIDDER",
        "text": "Ability to collect and analyse Sex, Age, and Disability Disaggregated Data."}
NEUTRAL = {"req_id": "r_neu", "category": "team", "mandatory": True, "actor": "BIDDER",
           "text": "Neutrality and cultural sensitivity to navigate ethnic, displacement, and "
                   "political tensions that may affect participation."}
DEPLOY = {"req_id": "r_dep", "category": "general", "mandatory": True, "actor": "BIDDER",
          "text": "Capacity to deploy teams in South Darfur quickly."}
METH = {"req_id": "r_meth", "category": "methodology", "mandatory": True, "actor": "BIDDER",
        "constraint_type": "NONE",
        "text": "The consulting firm should describe their approach to data reliability and "
                "quality assurance at all phases."}
TEAM_TEXT = ("Some standards will be applied through the methodology rather than claimed as team "
             "qualifications: sex-, age- and disability-disaggregated data will be collected with "
             "the Washington Group short set, and neutrality will be kept through balanced "
             "enumerator teams and impartial reporting.")
UND_FIRM = ("ARFADA is responding as a firm. Registration evidence will be included in the final "
            "submission package, together with the company profile and portfolio summary.")
UND_DEPLOY = ("For mobilisation in South Darfur, ARFADA will confirm or recruit a locally based "
              "field team prior to mobilization, coordinated by the Field Coordinator.")
METH_TEXT = ("Data reliability is protected at every phase: tools are piloted, enumerators are "
             "trained, 10% of interviews are back-checked and daily data checks flag outliers.")


def _run(*, label="PARTIAL", team_text=TEAM_TEXT, inject=None, cite_deploy="u1", extra=None):
    d = Path(tempfile.mkdtemp(prefix="arfada_v0614_"))
    reqs = [SADD, NEUTRAL, DEPLOY, METH] + (extra or [])
    (d / "tor_analysis.json").write_text(json.dumps({"run_id": "r", "metadata": {
        "country": {"value": "Sudan"},
        "subnational_location": {"values": ["South Darfur", "Nyala Shamal"]}}}))
    (d / "requirements.json").write_text(json.dumps({"requirements": reqs}))
    (d / "proposed_setup.json").write_text(json.dumps({"team": [
        {"staff_id": "cv_g", "role": "Gender Specialist",
         "evidence": {"s": "Upheld safeguarding, PSEA and accountability."}}]}))
    (d / "proposal_blueprint.json").write_text(json.dumps({"run_id": "r", "sections": [
        {"section_id": "TEAM", "requirement_ids": ["r_sadd", "r_neu"]},
        {"section_id": "UNDERSTANDING", "requirement_ids": ["r_dep"]},
        {"section_id": "METHODOLOGY", "requirement_ids": ["r_meth"]}]}))

    def led(rid, bids, lab=label):
        e = {"requirement_id": rid, "block_ids": bids, "status": lab}
        if inject:
            e["response_status"] = inject
        return e
    secs = {
        "TEAM": ([{"block_id": "t1", "type": "paragraph", "text": team_text}],
                 [led("r_sadd", ["t1"]), led("r_neu", ["t1"])]),
        "UNDERSTANDING": ([{"block_id": "u1", "type": "paragraph", "text": UND_FIRM},
                           {"block_id": "u2", "type": "paragraph", "text": UND_DEPLOY}],
                          [led("r_dep", [cite_deploy])] if cite_deploy else []),
        "METHODOLOGY": ([{"block_id": "m1", "type": "paragraph", "text": METH_TEXT}],
                        [led("r_meth", ["m1"], "ADDRESSED")]),
    }
    gs = d / "generated_sections"
    gs.mkdir()
    for sid, (blocks, ledger) in secs.items():
        (gs / f"{sid}.json").write_text(json.dumps({"section_id": sid, "blocks": blocks,
                                                    "requirement_response_ledger": ledger}))
    (d / "generation_status.json").write_text(json.dumps(
        {"sections": {s: {"status": "READY"} for s in secs}}))
    return d


def _rows(qa):
    return {r["req_id"]: r for r in qa["requirement_coverage"]}


class TestTwoDimensions(unittest.TestCase):
    def test_weak_evidence_is_not_a_content_gap(self):
        from engine.tor.final_qa import run_final_qa
        from engine.tor.fast_qa import two_status_report, TECH_READY
        d = _run()                                   # writer labelled the weak ones PARTIAL
        qa = run_final_qa(d)
        r = _rows(qa)
        for rid in ("r_sadd", "r_neu", "r_dep"):
            self.assertEqual(r[rid]["response_status"], RC.ADDRESSED, rid)
        self.assertEqual((r["r_sadd"]["evidence_status"], r["r_sadd"]["qualification_readiness"]),
                         (RE.EV_GAP, RE.AT_RISK))
        self.assertEqual(r["r_meth"]["evidence_status"], RE.EV_NOT_REQUIRED)
        self.assertEqual([f for f in qa["findings"] if f["check"] == "REQUIREMENT_COVERAGE"], [])
        ev = {f["requirement_id"] for f in qa["findings"] if f["check"] == "REQUIREMENT_EVIDENCE"}
        self.assertTrue({"r_sadd", "r_neu"} <= ev)                      # gaps stay visible
        rep = two_status_report(d)
        self.assertEqual(rep["technical_draft_status"], TECH_READY)
        self.assertEqual(rep["qualification_readiness"], RE.AT_RISK)
        self.assertIn("Evidence gaps (text responds", rep["internal_gaps_md"])
        self.assertIn("AT_RISK · evidence GAP · text ADDRESSED", rep["internal_gaps_md"])
        self.assertNotIn("Content gaps", rep["internal_gaps_md"])

    def test_two_separate_summaries(self):
        from engine.tor.final_qa import run_final_qa
        s = run_final_qa(_run())["summary"]
        self.assertEqual(s["content_coverage"], {"addressed": 4, "partially_addressed": 0,
                                                 "not_addressed": 0})
        ev = s["evidence_coverage"]
        self.assertEqual((ev["evidence_required"], ev["not_required"]), (3, 1))
        self.assertEqual(ev["verified"] + ev["partial"] + ev["gaps"], 3)
        self.assertTrue(s["content_line"].startswith("CONTENT COVERAGE — 4/4 mandatory addressed"))
        self.assertTrue(s["evidence_line"].startswith("EVIDENCE COVERAGE"))

    def test_owning_section_text_counts(self):
        # the ledger cites the firm paragraph; the deployment answer is in the same section
        from engine.tor.final_qa import run_final_qa
        r = _rows(run_final_qa(_run(cite_deploy="u1")))["r_dep"]
        self.assertEqual(r["response_status"], RC.ADDRESSED)
        self.assertEqual(r["sections"], ["UNDERSTANDING"])


class TestAntiGaming(unittest.TestCase):
    def test_ledger_label_and_injected_status_are_ignored(self):
        from engine.tor.final_qa import run_final_qa
        sig = lambda qa: {k: (v["response_status"], v["evidence_status"]) for k, v in _rows(qa).items()}
        base = sig(run_final_qa(_run(label="PARTIAL")))
        for label, inject in (("ADDRESSED", None), ("MISSING", None), ("PARTIAL", "NOT_ADDRESSED"),
                              ("MISSING", "ADDRESSED")):
            self.assertEqual(sig(run_final_qa(_run(label=label, inject=inject))), base, label)

    def test_relabelling_cannot_create_coverage(self):
        from engine.tor.final_qa import run_final_qa
        from engine.tor.fast_qa import two_status_report, TECH_BLOCKED, TECH_NEEDS_FIXES
        # the cited text no longer answers SADD / neutrality: labelling it ADDRESSED (and
        # injecting response_status) still cannot make it ADDRESSED
        d = _run(label="ADDRESSED", inject="ADDRESSED",
                 team_text="The team will be confirmed before mobilization.")
        r = _rows(run_final_qa(d))
        self.assertEqual(r["r_sadd"]["response_status"], RC.PARTIALLY_ADDRESSED)
        self.assertEqual(r["r_neu"]["response_status"], RC.PARTIALLY_ADDRESSED)
        self.assertEqual(two_status_report(d)["technical_draft_status"], TECH_NEEDS_FIXES)
        # no text at all (thin citation, nothing in the owning section) → NOT_ADDRESSED → BLOCKED
        d2 = _run(label="ADDRESSED", inject="ADDRESSED", team_text="See CVs.")
        r2 = _rows(run_final_qa(d2))
        self.assertEqual(r2["r_sadd"]["response_status"], RC.NOT_ADDRESSED)
        self.assertEqual(two_status_report(d2)["technical_draft_status"], TECH_BLOCKED)

    def test_partial_text_is_a_warning_not_a_block(self):
        from engine.tor.final_qa import run_final_qa
        from engine.tor.fast_qa import two_status_report, TECH_NEEDS_FIXES
        d = _run(team_text="Sex-, age- and disability-disaggregated data will be collected with the "
                           "Washington Group short set by trained enumerators in every locality.")
        qa = run_final_qa(d)
        self.assertEqual(_rows(qa)["r_neu"]["response_status"], RC.PARTIALLY_ADDRESSED)
        self.assertTrue(any(f["check"] == "REQUIREMENT_COVERAGE" and f["severity"] == "WARNING"
                            for f in qa["findings"]))
        self.assertEqual(two_status_report(d)["technical_draft_status"], TECH_NEEDS_FIXES)

    def test_missing_cited_block_is_not_addressed(self):
        rows = RC.compute_responses([METH], {"METHODOLOGY": {"blocks": [], "requirement_response_ledger": [
            {"requirement_id": "r_meth", "block_ids": ["nope"], "status": "ADDRESSED"}]}},
            section_status={"METHODOLOGY": {"status": "READY"}})
        self.assertEqual(rows["r_meth"]["response_status"], RC.NOT_ADDRESSED)
        thin = RC.compute_responses([METH], {"METHODOLOGY": {
            "blocks": [{"block_id": "m", "type": "paragraph", "text": "Quality assured."}],
            "requirement_response_ledger": [{"requirement_id": "r_meth", "block_ids": ["m"],
                                             "status": "ADDRESSED"}]}},
            section_status={"METHODOLOGY": {"status": "READY"}})
        self.assertEqual(thin["r_meth"]["response_status"], RC.PARTIALLY_ADDRESSED)

    def test_evidence_independent_of_text(self):
        from engine.tor.final_qa import run_final_qa
        a = _rows(run_final_qa(_run()))
        b = _rows(run_final_qa(_run(team_text="The team will be confirmed before mobilization.")))
        for rid in a:
            self.assertEqual(a[rid]["evidence_status"], b[rid]["evidence_status"], rid)


class TestBlockersUnchanged(unittest.TestCase):
    def test_evidence_gap_adds_no_canonical_blocker(self):
        from engine.tor.fast_qa import two_status_report
        good = two_status_report(_run())
        weak = two_status_report(_run(team_text="The team will be confirmed before mobilization."))
        self.assertEqual(good["canonical_blockers"], weak["canonical_blockers"])


@unittest.skipUnless(os.environ.get("ARFADA_V0613_RUN"), "set ARFADA_V0613_RUN to the run_artifacts")
class TestFreshSouthDarfurRun(unittest.TestCase):
    """Replays the confirmed fresh v0.6.13 run from its own artifacts."""

    def test_seven_are_addressed_with_evidence_kept(self):
        from engine.tor.fast_qa import two_status_report, TECH_READY
        src = Path(os.environ["ARFADA_V0613_RUN"])
        run = Path(tempfile.mkdtemp(prefix="arfada_v0614_sd_")) / "run"
        run.mkdir()
        for f in src.glob("*.json"):
            if not f.name.startswith("_") and f.name not in ("claim_state.json",
                                                             "requirement_coverage.json"):
                shutil.copyfile(f, run / f.name)
        (run / "generated_sections").mkdir()
        for f in src.glob("_candidate_*.json"):
            c = json.loads(f.read_text(encoding="utf-8"))
            (run / "generated_sections" / f"{c['section_id']}.json").write_text(
                json.dumps(c), encoding="utf-8")
        (run / "knowledge_snapshot").mkdir()
        (run / "knowledge_snapshot" / "projects.json").write_text(json.dumps({"metrics": {
            "total_projects": 156, "total_surveys": 73906, "total_kii": 2721, "total_fgd": 1664}}))
        rep = two_status_report(run)
        self.assertEqual(rep["technical_draft_status"], TECH_READY)
        self.assertEqual(rep["draft_blockers"], [])
        self.assertEqual(sorted(rep["canonical_blockers"]), sorted([
            "FINANCIAL_PROPOSAL", "PREVIOUS_WORK_SAMPLE", "TEAM_CV_PACKAGE", "REGISTRATION_EVIDENCE",
            "TEAM_AVAILABILITY", "SUBMISSION_CHANNEL", "DEADLINE_CONFIRMATION"]))
        from engine.tor.final_qa import run_final_qa
        rows = {r["text"][:30]: r for r in run_final_qa(run)["requirement_coverage"]}
        sadd = next(r for k, r in rows.items() if k.startswith("Ability to collect and analyse"))
        neu = next(r for k, r in rows.items() if k.startswith("Neutrality and cultural"))
        for r in (sadd, neu):
            self.assertEqual((r["response_status"], r["evidence_status"]), ("ADDRESSED", "GAP"))


if __name__ == "__main__":
    unittest.main()
