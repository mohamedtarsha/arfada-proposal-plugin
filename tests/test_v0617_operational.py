"""v0.6.17 operational hardening — confirmed by the fresh v0.6.16 run.

1. portable Staff CV paths (Windows / Linux / synced roots; never outside the root);
2. TEST_REPLAY: SUBMISSION_PACKAGE_STATUS = NOT_ASSESSED_TEST_REPLAY, live gaps not blockers;
3. relevant experience auto-selected from the Master Tracker (provenance, no invention);
4. governance confirmation classified by meaning (no magic phrase; wrapping-invariant).

    python -m pytest tests/test_v0617_operational.py -v
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

os.environ.setdefault("ARFADA_HOME", tempfile.mkdtemp(prefix="arfada_v0617_home_"))

from engine.tor.lknowledge import staff_pool as SP  # noqa: E402
from engine.tor import relevant_experience as RX  # noqa: E402
from engine.tor import governance as G  # noqa: E402


class TestPortablePaths(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="arfada_v0617_kb_")) / "ARFADA Knowledge"
        self.cv = self.root / "Staff CVs" / "Sudan" / "Senior Evaluation Expert" / "Vincent CV.pdf"
        self.cv.parent.mkdir(parents=True)
        self.cv.write_bytes(b"%PDF-1.4 cv")

    def test_parts(self):
        P = SP.portable_rel_parts
        self.assertEqual(P(r"Sudan\Senior Evaluation Expert\Vincent CV.pdf"),
                         ["Sudan", "Senior Evaluation Expert", "Vincent CV.pdf"])
        self.assertEqual(P("Sudan/Senior Evaluation Expert/Vincent CV.pdf"),
                         ["Sudan", "Senior Evaluation Expert", "Vincent CV.pdf"])
        self.assertEqual(P(r"E:\work\ARFADA Knowledge\Staff CVs\Sudan\x.pdf"), ["Sudan", "x.pdf"])
        self.assertEqual(P("/home/claude/kb/Staff CVs/Sudan/x.pdf"), ["Sudan", "x.pdf"])
        for bad in (r"..\..\secret.txt", "Sudan/../../x", "/etc/passwd", r"C:\Windows\x.pdf", ""):
            self.assertIsNone(P(bad), bad)
        for parts in (P(r"a\b\c.pdf"), P("a/b/c.pdf")):        # no separator survives
            self.assertFalse(any("\\" in x or "/" in x for x in parts))

    def test_resolution_all_forms(self):
        for stored in (r"Sudan\Senior Evaluation Expert\Vincent CV.pdf",
                       "Sudan/Senior Evaluation Expert/Vincent CV.pdf",
                       r"E:\old machine\ARFADA Knowledge\Staff CVs\Sudan\Senior Evaluation Expert\Vincent CV.pdf",
                       "/home/claude/kb/Staff CVs/Sudan/Senior Evaluation Expert/Vincent CV.pdf",
                       "sudan/senior evaluation expert/vincent cv.pdf"):          # case differs
            f = SP.cv_file_for({"source_rel_path": stored}, self.root)
            self.assertIsNotNone(f, stored)
            self.assertEqual(f.read_bytes(), b"%PDF-1.4 cv")

    def test_linux_safe_by_construction(self):
        """On Linux a backslash is a literal filename character: the v0.6.16 failure was
        joining 'Sudan\\Expert\\cv.pdf' as ONE name. The resolver must only ever join single
        segments, whatever the host OS."""
        seen = []
        orig = SP._match_segment

        def spy(directory, name):
            seen.append(name)
            return orig(directory, name)
        SP._match_segment = spy
        try:
            for stored in (r"Sudan\Senior Evaluation Expert\Vincent CV.pdf",
                           "/home/claude/kb/Staff CVs/Sudan/Senior Evaluation Expert/Vincent CV.pdf"):
                seen.clear()
                self.assertIsNotNone(SP.cv_file_for({"source_rel_path": stored}, self.root))
                self.assertEqual(seen, ["Sudan", "Senior Evaluation Expert", "Vincent CV.pdf"])
                self.assertFalse(any("\\" in s or "/" in s for s in seen))
        finally:
            SP._match_segment = orig

    def test_never_outside_root(self):
        (self.root / "secret.txt").write_text("x")
        self.assertIsNone(SP.cv_file_for({"source_rel_path": r"..\secret.txt"}, self.root))
        self.assertIsNone(SP.cv_file_for({"source_rel_path": "Sudan/missing.pdf"}, self.root))

    def test_index_not_modified(self):
        prof = {"source_rel_path": r"Sudan\Senior Evaluation Expert\Vincent CV.pdf"}
        SP.cv_file_for(prof, self.root)
        self.assertEqual(prof["source_rel_path"], r"Sudan\Senior Evaluation Expert\Vincent CV.pdf")


PROJECTS = [
    {"project_id": "211-2026-Endline Study-Sudan-SCI", "project_name": "Endline Study",
     "assignment_type": "EVALUATION", "country": "Sudan", "sector": "Food Security, Cash Assistance",
     "client": "Save the Children", "surveys": 500, "kii": 10, "fgd": 8, "source_sheet": "Master Tracker.xlsx", "source_row": 5},
    {"project_id": "223-2026-Final Evalu-Sudan-IRC", "project_name": "Final External Evaluation",
     "assignment_type": "EVALUATION", "country": "Sudan", "sector": "MPCA / Cash, Protection",
     "client": "International Rescue Committee", "surveys": 580, "kii": 27, "fgd": 11, "source_row": 9},
    {"project_id": "212-2026-Final Evalu-Sudan-TGH", "project_name": "Final Evaluation",
     "assignment_type": "EVALUATION", "country": "Sudan", "sector": "Food Security, Agriculture",
     "client": "Triangle", "surveys": 197, "kii": 10, "fgd": 4, "source_row": 7},
    {"project_id": "134-2024-Evalu-GOS-ZOA", "project_name": "Endline Evaluation",
     "assignment_type": "EVALUATION", "country": "Syria", "sector": "Food Security, Protection",
     "client": "ZOA - ZOA", "surveys": 766, "kii": 25, "fgd": 10, "source_row": 30},
    {"project_id": "150-2024-Value Chain-Turkey-WVI", "project_name": "Value Chain Assessment",
     "assignment_type": "ASSESSMENT", "country": "Turkey", "sector": "Agriculture",
     "client": "World Vision", "surveys": 91, "kii": 20, "fgd": 2, "source_row": 40},
    {"project_id": "300-2026-Final Evalu-Sudan-ZOA", "project_name": "Final Evaluation Support to War "
     "Affected Communities South Darfur", "assignment_type": "EVALUATION", "country": "Sudan",
     "sector": "Food Security", "client": "ZOA", "source_row": 99},          # the current assignment
]
TOR = {"metadata": {"assignment": {"value": "Final Evaluation for Support to War Affected Communities "
                                            "in South Darfur Project"},
                    "client": {"value": "ZOA"}, "country": {"value": "Sudan"},
                    "subnational_location": {"values": ["South Darfur", "Nyala Shamal"]}},
       "assignment_type": {"assignment_type": "ENDLINE"}}
REQS = [{"text": "Household surveys applying the Food Consumption Score; FGDs and KIIs; voucher "
                 "assistance; protection risks."}]


class TestRelevantExperience(unittest.TestCase):
    def test_auto_selection(self):
        import datetime as dt
        r = RX.select(PROJECTS, TOR, REQS, today=dt.date(2026, 11, 22))
        self.assertEqual(r["status"], RX.AUTO_SELECTED)
        ids = [c["project_id"] for c in r["selected"]]
        self.assertTrue(3 <= len(ids) <= 5)
        self.assertNotIn("300-2026-Final Evalu-Sudan-ZOA", ids)              # current excluded
        self.assertIn("134-2024-Evalu-GOS-ZOA", ids)                         # client familiarity
        self.assertEqual(ids[0][:3], "211")
        self.assertTrue(all(c["provenance"]["source"] == "Master Tracker" for c in r["selected"]))
        self.assertIn("none is claimed", " ".join(r["notes"]))                # no Darfur invented
        self.assertTrue(all("location" not in c["scored_on"] for c in r["selected"]))

    def test_insufficient(self):
        r = RX.select(PROJECTS[4:5], TOR, REQS)
        self.assertEqual(r["status"], RX.INSUFFICIENT)
        self.assertFalse(RX.resolved(r))

    def test_tie_question(self):
        twins = [dict(PROJECTS[0], project_id=f"2{i}0-2026-Endline-Sudan-X{i}", client=f"Client {i}",
                      country="Sudan" if i % 2 else "Chad") for i in range(7)]
        for t in twins:
            t["country"] = "Sudan"
        twins[5]["client"], twins[4]["client"] = "Client A", "Client B"
        r = RX.select(twins, TOR, REQS, limit=5)
        self.assertEqual(r["status"], RX.NEEDS_DECISION)
        self.assertEqual(r["question"]["key"], "relevant_experience")

    def test_placeholder_replaced_with_table(self):
        r = RX.select(PROJECTS, TOR, REQS)
        cand = {"blocks": [{"block_id": "b1", "type": "paragraph", "text": "Intro."},
                           {"block_id": "b2", "type": "evidence_placeholder",
                            "text": "NEEDS_ARFADA_EVIDENCE: user selection of 3–5 featured relevant "
                                    "assignments (Master Tracker ranking) before they are described"}]}
        new, changes = RX.apply_selection(cand, r, section_id="SUBMISSION")
        self.assertEqual(changes[0]["kind"], "RELEVANT_EXPERIENCE_TABLE")
        table = new["blocks"][2]
        self.assertEqual(table["columns"], RX.TABLE_COLUMNS)
        self.assertEqual(len(table["rows"]), len(r["selected"]))
        self.assertFalse(any(RX.is_placeholder(b) for b in new["blocks"]))
        self.assertTrue(RX.is_placeholder(cand["blocks"][1]))                # copy, not mutation
        self.assertEqual(RX.presented({"S": new}, r), len(r["selected"]))

    def test_other_evidence_placeholders_untouched(self):
        honest = {"type": "evidence_placeholder",
                  "text": "NEEDS_ARFADA_EVIDENCE: firm-level record of ARFADA assignments delivered in "
                          "South Darfur — the Master Tracker does not record a South Darfur location"}
        self.assertFalse(RX.is_placeholder(honest))
        r = RX.select(PROJECTS, TOR, REQS)
        new, changes = RX.apply_selection({"blocks": [honest]}, r)
        self.assertEqual(changes, [])
        self.assertEqual(new["blocks"][0], honest)

    def test_override_and_qa(self):
        from engine.tor.final_qa import run_final_qa
        d = Path(tempfile.mkdtemp(prefix="arfada_v0617_rx_"))
        (d / "tor_analysis.json").write_text(json.dumps({"run_id": "r", **TOR}))
        (d / "requirements.json").write_text(json.dumps({"requirements": []}))
        RX.write(d, RX.select(PROJECTS, TOR, REQS))
        bad = RX.override(d, ["nope", "211-2026-Endline Study-Sudan-SCI"])
        self.assertFalse(bad["ok"])
        ok = RX.override(d, ["211-2026-Endline Study-Sudan-SCI", "223-2026-Final Evalu-Sudan-IRC",
                             "134-2024-Evalu-GOS-ZOA"], note="employee choice")
        self.assertEqual(ok["status"], RX.USER_SELECTED)
        gs = d / "generated_sections"
        gs.mkdir()
        (gs / "SUBMISSION.json").write_text(json.dumps({"section_id": "SUBMISSION", "blocks": [
            {"block_id": "p", "type": "evidence_placeholder",
             "text": "NEEDS_ARFADA_EVIDENCE: featured relevant assignments from the Master Tracker"}]}))
        (d / "generation_status.json").write_text(json.dumps({"sections": {"SUBMISSION": {"status": "READY"}}}))
        f = [x for x in run_final_qa(d)["findings"] if x["check"] == "RELEVANT_EXPERIENCE"]
        self.assertEqual([(x["severity"], x["category"]) for x in f], [("INFO", "placeholder_filled_at_export")])
        # unresolved selection is surfaced, never hidden
        doc = RX.load(d)
        doc["status"] = RX.NEEDS_DECISION
        (d / RX.FILE).write_text(json.dumps(doc))
        f = [x for x in run_final_qa(d)["findings"] if x["check"] == "RELEVANT_EXPERIENCE"]
        self.assertEqual([(x["severity"], x["category"]) for x in f], [("WARNING", "selection_unresolved")])

    def test_previous_work_is_separate(self):
        from engine.tor.claim_state import _relevant_experience_policy
        pol = _relevant_experience_policy({"relevant_experience": RX.select(PROJECTS, TOR, REQS)})
        self.assertIn("separate from the previous-work report", pol["instruction"])


class TestTestReplayStatus(unittest.TestCase):
    def _run(self, purpose):
        from engine.tor import run_decisions as RD
        d = Path(tempfile.mkdtemp(prefix="arfada_v0617_tr_"))
        (d / "tor_analysis.json").write_text(json.dumps({"run_id": "r", "metadata": {},
            "submission_instructions": ["Proposals must be submitted via [submission platform/email] "
                                        "by 12:00 AM (Sudan Time), 21 November 2026."]}))
        (d / "requirements.json").write_text(json.dumps({"requirements": [
            {"req_id": "f", "category": "submission", "mandatory": True, "actor": "BIDDER",
             "text": "Financial Proposal: Detailed budget, including daily rates and expenses."},
            {"req_id": "dl", "category": "submission", "mandatory": True, "actor": "BIDDER",
             "text": "Proposals must be submitted via [submission platform/email] by 12:00 AM (Sudan "
                     "Time), 21 November 2026."}]}))
        RD.record(d, "run_purpose", purpose)
        return d

    def test_replay_not_assessed(self):
        from engine.tor.fast_qa import two_status_report, PKG_NOT_ASSESSED
        rep = two_status_report(self._run("TEST_REPLAY"))
        self.assertEqual(rep["submission_package_status"], PKG_NOT_ASSESSED)
        self.assertEqual(rep["canonical_blockers"], [])
        self.assertEqual(rep["final_submission_blockers"], [])
        self.assertEqual(sorted(rep["live_submission_gaps_if_applicable"]),
                         ["FINANCIAL_PROPOSAL", "SUBMISSION_CHANNEL"])
        md = rep["internal_gaps_md"]
        self.assertNotIn("Final-submission blockers", md)
        self.assertIn("Live-submission gaps (only if this TOR were submitted live)", md)
        self.assertIn("has passed", md)

    def test_live_unchanged(self):
        from engine.tor.fast_qa import two_status_report, PKG_NOT_READY
        rep = two_status_report(self._run("LIVE_SUBMISSION"))
        self.assertEqual(rep["submission_package_status"], PKG_NOT_READY)
        self.assertEqual(sorted(rep["canonical_blockers"]),
                         ["DEADLINE_CONFIRMATION", "FINANCIAL_PROPOSAL", "SUBMISSION_CHANNEL"])
        self.assertEqual(rep["live_submission_gaps_if_applicable"], [])
        self.assertIn("Final-submission blockers", rep["internal_gaps_md"])


class TestGovernanceConfirmation(unittest.TestCase):
    def setUp(self):
        self._old = G._store
        p = Path(tempfile.mkdtemp(prefix="arfada_v0617_gov_")) / "policies.json"
        G._store = lambda: p

    def tearDown(self):
        G._store = self._old

    def test_classification(self):
        C = G.classify_confirmation
        for s in ("Yes", "Approved.", "ARFADA's organisation-level previous-work sharing approval applies",
                  "ARFADA has permission from its clients to share previous evaluation reports.",
                  "No restrictions — sharing is approved."):
            self.assertEqual(C(s), G.AFFIRMATIVE, s)
        for s in ("I think so, but check with the client", "Some clients allow it", "Is it approved?",
                  "Probably yes", ""):
            self.assertEqual(C(s), G.AMBIGUOUS, s)
        for s in ("No, not for all clients", "Sharing is not approved", "The policy is revoked"):
            self.assertEqual(C(s), G.NEGATIVE, s)

    def test_wrapping_does_not_change_result(self):
        core = "ARFADA's organisation-level previous-work sharing approval applies."
        for wrapped in (core, f"Note for the record: {core}", f"{core} Recorded by the proposal team."):
            self.assertEqual(G.classify_confirmation(wrapped), G.AFFIRMATIVE, wrapped)
            res = G.set_previous_work_sharing_policy(wrapped)
            self.assertTrue(res["ok"], wrapped)
            self.assertEqual(res["policy"]["confirmation"], wrapped)          # exact wording kept

    def test_ambiguous_needs_explicit_confirmation(self):
        res = G.set_previous_work_sharing_policy("Probably fine for most clients")
        self.assertEqual(res["status"], "NEEDS_CONFIRMATION")
        self.assertIn("Yes / No", res["question"])
        self.assertIsNone(G.previous_work_sharing_policy())
        res = G.set_previous_work_sharing_policy("Probably fine for most clients", confirmed=True)
        self.assertEqual(res["policy"]["confirmation_state"], "EXPLICITLY_CONFIRMED")
        self.assertFalse(G.set_previous_work_sharing_policy("not approved", confirmed=True)["ok"])

    def test_restriction_still_overrides(self):
        G.set_previous_work_sharing_policy("Yes")
        from docx import Document
        p = Path(tempfile.mkdtemp(prefix="arfada_v0617_r_")) / "Evaluation.docx"
        d = Document()
        d.sections[0].header.paragraphs[0].text = "STRICTLY CONFIDENTIAL - do not distribute"
        d.add_paragraph("Final Evaluation Report")
        d.save(str(p))
        clr = G.policy_clearance({"kind": "EVALUATION_DELIVERABLE", "by_arfada": True, "original": str(p)})
        self.assertEqual(clr["status"], "RESTRICTED")


if __name__ == "__main__":
    unittest.main()
