"""v0.6.16 — avoidable final-submission blockers resolved from Knowledge / user decisions.

1. bulk team availability (explicit user confirmation only);
2. CV package auto-built from ARFADA Knowledge/Staff CVs (identity-checked, byte-identical);
3. organisation-level previous-work sharing policy (report-level restriction overrides);
4. submission channel asked as a FAST question (never invented);
5. RUN_PURPOSE: TEST_REPLAY turns a passed deadline into a warning; LIVE_SUBMISSION keeps it;
6. registration certificate auto-discovered in ARFADA Knowledge/Company;
7. budget rule unchanged.

    python -m pytest tests/test_v0616_submission_workflow.py -v
Optional: ARFADA_REAL_TOR=<original South Darfur PDF>.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("ARFADA_HOME", tempfile.mkdtemp(prefix="arfada_v0616_home_"))

from engine.tor import run_decisions as RD  # noqa: E402
from engine.tor import governance as G  # noqa: E402
from engine.tor import package_builder as PB  # noqa: E402

SUB_REQS = [
    {"req_id": "s_cv", "category": "submission", "mandatory": True, "actor": "BIDDER",
     "text": "CVs/Profiles of Team Members: relevant expertise and experience."},
    {"req_id": "s_pw", "category": "submission", "mandatory": True, "actor": "BIDDER",
     "text": "Relevant Experience: Provide examples of previous baseline surveys or evaluations."},
    {"req_id": "s_fin", "category": "submission", "mandatory": True, "actor": "BIDDER",
     "text": "Financial Proposal: Detailed budget, including daily rates and expenses."},
    {"req_id": "s_reg", "category": "general", "mandatory": True, "actor": "BIDDER",
     "text": "Evidence of registration as a consultant(s) or firm."},
    {"req_id": "s_dl", "category": "submission", "mandatory": True, "actor": "BIDDER",
     "text": "Proposals must be submitted via [submission platform/email] by 12:00 AM (Sudan Time), "
             "21 November 2026."},
]
TOR = {"run_id": "r", "metadata": {"country": {"value": "Sudan"}},
       "submission_instructions": ["Proposals must be submitted via [submission platform/email] by "
                                   "12:00 AM (Sudan Time), 21 November 2026."]}


def _docx(path: Path, lines, header=""):
    from docx import Document
    d = Document()
    if header:
        d.sections[0].header.paragraphs[0].text = header
    for t in lines:
        d.add_paragraph(t)
    path.parent.mkdir(parents=True, exist_ok=True)
    d.save(str(path))
    return path


def _run(team=("cv_a", "cv_b")):
    d = Path(tempfile.mkdtemp(prefix="arfada_v0616_run_"))
    (d / "tor_analysis.json").write_text(json.dumps(TOR))
    (d / "requirements.json").write_text(json.dumps({"requirements": SUB_REQS}))
    (d / "proposed_setup.json").write_text(json.dumps({"team": [
        {"staff_id": s, "role": "Expert"} for s in team]}))
    return d


class _PolicyStore(unittest.TestCase):
    def setUp(self):
        self._old = G._store
        p = Path(tempfile.mkdtemp(prefix="arfada_v0616_gov_")) / "policies.json"
        G._store = lambda: p

    def tearDown(self):
        G._store = self._old


class TestRunDecisions(unittest.TestCase):
    def test_channel_values(self):
        n = RD.normalise_channel
        self.assertEqual(n("tenders@zoa.example.org"), "tenders@zoa.example.org")
        self.assertEqual(n("https://etender.example.org/bid/42"), "https://etender.example.org/bid/42")
        self.assertEqual(n("ZOA Tender Portal"), "ZOA Tender Portal")
        self.assertEqual(n("Not known yet"), RD.NOT_KNOWN)
        for bad in ("[submission platform/email]", "TBD", "", "the portal",
                    "We think they will probably tell us later which channel to use next week"):
            self.assertIsNone(n(bad), bad)

    def test_run_purpose(self):
        d = _run()
        self.assertTrue(RD.record(d, "run_purpose", "test_replay")["ok"])
        self.assertEqual(RD.run_purpose(d), RD.TEST_REPLAY)
        self.assertFalse(RD.record(d, "run_purpose", "maybe")["ok"])

    def test_bulk_availability_explicit_only(self):
        d = _run()
        for hedged in ("they should be available", "probably all available", "Are they available?",
                       "not all available yet", ""):
            self.assertFalse(RD.confirm_team_availability(d, hedged)["ok"], hedged)
        res = RD.confirm_team_availability(d, "All selected experts are available")
        self.assertEqual(res["confirmed"], ["cv_a", "cv_b"])
        av = json.loads((d / RD.AVAILABILITY_FILE).read_text())
        self.assertEqual((av["cv_a"], av["cv_b"], av["_provenance"]["decision"]),
                         (True, True, RD.CONFIRMED_BY_USER))


class TestClaimState(_PolicyStore):
    def claims(self, d, today=dt.date(2026, 11, 22)):
        from engine.tor.claim_state import build_claim_state
        return build_claim_state(d, today=today)["claims"]

    def test_availability(self):
        d = _run()
        self.assertEqual(self.claims(d)["team_availability"]["status"], "UNVERIFIED")  # never assumed
        RD.confirm_team_availability(d, "All selected experts are available")
        self.assertEqual(self.claims(d)["team_availability"]["status"], "VERIFIED")
        (d / "proposed_setup.json").write_text(json.dumps({"team": [
            {"staff_id": "cv_a"}, {"staff_id": "cv_b"}, {"staff_id": "cv_new"}]}))
        self.assertEqual(self.claims(d)["team_availability"]["status"], "UNVERIFIED")  # new member

    def test_deadline_by_run_purpose(self):
        d = _run()
        self.assertEqual(self.claims(d)["deadline"]["status"], "PROVISIONAL")         # unknown purpose
        RD.record(d, "run_purpose", "TEST_REPLAY")
        dl = self.claims(d)["deadline"]
        self.assertEqual((dl["status"], dl["required"], dl["warning"]), ("NOT_APPLICABLE", False, True))
        self.assertIn("21 November 2026", dl["detail"])
        self.assertIn("no extension is implied", dl["detail"])
        RD.record(d, "run_purpose", "LIVE_SUBMISSION")
        dl = self.claims(d)["deadline"]
        self.assertEqual(dl["status"], "MISSING")
        self.assertIn("extension", dl["detail"])

    def test_channel_decision(self):
        d = _run()
        self.assertEqual(self.claims(d)["submission_channel"]["status"], "MISSING")
        RD.record(d, "submission_channel", "Not known yet")
        self.assertEqual(self.claims(d)["submission_channel"]["status"], "MISSING")
        RD.record(d, "submission_channel", "tenders@zoa.example.org")
        ch = self.claims(d)["submission_channel"]
        self.assertEqual((ch["status"], ch["value"], ch["source"]),
                         ("VERIFIED", "tenders@zoa.example.org", RD.USER_CONFIRMED))

    def test_budget_rule_unchanged(self):
        self.assertEqual(self.claims(_run())["financial_proposal"]["status"], "MISSING")


def _knowledge(tmp: Path):
    root = tmp / "ARFADA Knowledge"
    _docx(root / "Staff CVs" / "Sudan" / "Amna Hassan CV.docx",
          ["AMNA HASSAN OSMAN", "Senior Evaluation Specialist", "12 years of experience"])
    _docx(root / "Staff CVs" / "Sudan" / "Bakri CV.docx",
          ["CURRICULUM VITAE", "Mohamed Ali Yousif", "Field Coordinator"])     # wrong person
    pool = [{"staff_id": "cv_a", "source_rel_path": "Sudan/Amna Hassan CV.docx",
             "source_file_name": "Amna Hassan CV.docx"},
            {"staff_id": "cv_b", "source_rel_path": "Sudan/Bakri CV.docx",
             "source_file_name": "Bakri CV.docx"},
            {"staff_id": "cv_c", "source_rel_path": "Sudan/missing.docx"}]
    facts = [{"staff_id": "cv_a", "attribute": "full_name", "value": "Amna Hassan Osman", "verified": True},
             {"staff_id": "cv_b", "attribute": "full_name", "value": "Bakri Adam Ishag", "verified": True}]
    return root, SimpleNamespace(_live_staff=pool), facts


class TestCvPackage(_PolicyStore):
    def test_package_identity_and_manifest(self):
        tmp = Path(tempfile.mkdtemp(prefix="arfada_v0616_k_"))
        root, kn, facts = _knowledge(tmp)
        d = _run(team=("cv_a", "cv_b", "cv_c"))
        (d / "team_staff_facts.json").write_text(json.dumps({"facts": facts}))
        doc = PB.package_team_cvs(d, knowledge=kn, knowledge_root=root)
        st = {e["staff_profile_id"]: e for e in doc["entries"]}
        self.assertEqual(st["cv_a"]["status"], "PACKAGED")
        self.assertEqual((d / st["cv_a"]["packaged_cv_path"]).read_bytes(),
                         (root / "Staff CVs" / "Sudan" / "Amna Hassan CV.docx").read_bytes())
        self.assertIn("identity not verified", st["cv_b"]["reason"])        # wrong person's CV
        self.assertIn("unavailable", st["cv_c"]["reason"])
        self.assertEqual(sorted(st["cv_a"]), sorted(["staff_profile_id", "canonical_name", "role",
                                                     "source_cv_path", "packaged_cv_path", "status",
                                                     "reason", "identity_check", "sha256"]))
        from engine.tor.claim_state import build_claim_state
        cv = build_claim_state(d)["claims"]["team_cv_package"]
        self.assertEqual(cv["status"], "MISSING")
        self.assertEqual(cv["packaged"], 1)

    def test_all_resolved_clears_blocker(self):
        tmp = Path(tempfile.mkdtemp(prefix="arfada_v0616_k_"))
        root, kn, facts = _knowledge(tmp)
        d = _run(team=("cv_a",))
        (d / "team_staff_facts.json").write_text(json.dumps({"facts": facts}))
        PB.package_team_cvs(d, knowledge=kn, knowledge_root=root)
        from engine.tor.claim_state import build_claim_state
        self.assertEqual(build_claim_state(d)["claims"]["team_cv_package"]["status"], "VERIFIED")


class TestRegistration(unittest.TestCase):
    def _root(self, files):
        root = Path(tempfile.mkdtemp(prefix="arfada_v0616_reg_")) / "ARFADA Knowledge"
        for name, lines in files.items():
            _docx(root / "Company" / name, lines)
        _docx(root / "Company" / "Policies" / "Data Protection Protocol.docx", ["policy"])
        return root

    def test_one_found_is_packaged(self):
        root = self._root({"Legal/Certificate of Registration.docx": ["Registered NGO", "No. 123"]})
        d = _run()
        res = PB.package_registration(d, knowledge_root=root)
        self.assertEqual(res["status"], "PACKAGED")
        self.assertTrue((d / "annexes" / "registration" / "Certificate of Registration.docx").is_file())
        prov = json.loads((d / PB.REGISTRATION_PROVENANCE).read_text())
        self.assertIn("Certificate of Registration.docx", prov["source_path"])
        from engine.tor.submission_blockers import registration_state
        self.assertTrue(registration_state(d)[0])

    def test_several_ask_none_blocks_expired_skipped(self):
        root = self._root({"Registration Sudan.docx": ["Registration"],
                           "Registration Turkey.docx": ["Registration"],
                           "Old Registration.docx": ["Registration", "Valid until 01/01/2020"]})
        cands = PB.registration_candidates(root)
        self.assertEqual(sorted(p.name for p in cands), ["Registration Sudan.docx",
                                                         "Registration Turkey.docx"])
        d = _run()
        self.assertEqual(PB.package_registration(d, knowledge_root=root)["status"], "CHOOSE")
        from engine.tor.autopilot import build_questions
        qs = build_questions(TOR, SUB_REQS, registration_candidates=cands,
                             decisions={"run_purpose": {"value": "TEST_REPLAY"},
                                        "submission_channel": {"value": "NOT_KNOWN"}})
        self.assertIn("registration_choice", [q["key"] for q in qs])
        RD.record(d, "registration_choice", str(cands[0]))
        self.assertEqual(PB.package_registration(d, knowledge_root=root)["status"], "PACKAGED")
        empty = self._root({})
        self.assertEqual(PB.package_registration(_run(), knowledge_root=empty)["status"], "NONE_FOUND")


class TestPreviousWorkPolicy(_PolicyStore):
    def _select(self, d, path, *, by_arfada=True, kind="EVALUATION_DELIVERABLE"):
        from engine.tor.previous_work_state import record_selection
        dest = d / "annexes" / "previous_work" / path.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(path.read_bytes())
        record_selection(d, file=dest, original=path, verdict={"kind": kind, "by_arfada": by_arfada})

    def test_policy_wording(self):
        self.assertTrue(G.is_explicit_approval("ARFADA has permission from its clients to share previous "
                                               "evaluation reports as examples of previous work."))
        self.assertFalse(G.is_explicit_approval("We should check whether clients allow sharing"))
        self.assertFalse(G.set_previous_work_sharing_policy("maybe ok")["ok"])

    def test_policy_clears_in_scope_report(self):
        from engine.tor.previous_work_state import previous_work_states
        tmp = Path(tempfile.mkdtemp(prefix="arfada_v0616_pw_"))
        rep = _docx(tmp / "Final_Evaluation_Report.docx", ["Final Evaluation Report", "Findings"])
        d = _run()
        self._select(d, rep)
        self.assertEqual(previous_work_states(d)["clearance"]["status"], "UNVERIFIED")   # no policy
        G.set_previous_work_sharing_policy("ARFADA has permission from its clients to share previous "
                                           "evaluation reports as examples of previous work.")
        cl = previous_work_states(d)["clearance"]
        self.assertEqual((cl["status"], cl["source"]), ("VERIFIED", "ORG_POLICY"))
        from engine.tor.submission_blockers import previous_work_state
        self.assertTrue(previous_work_state(d)[0])

    def test_restriction_and_scope_override_policy(self):
        from engine.tor.previous_work_state import previous_work_states
        G.set_previous_work_sharing_policy("ARFADA has permission from its clients to share previous "
                                           "evaluation reports as examples of previous work.")
        tmp = Path(tempfile.mkdtemp(prefix="arfada_v0616_pw_"))
        restricted = _docx(tmp / "Evaluation.docx", ["Final Evaluation Report"],
                           header="STRICTLY CONFIDENTIAL - do not distribute")
        d = _run()
        self._select(d, restricted)
        cl = previous_work_states(d)["clearance"]
        self.assertEqual((cl["status"], cl.get("restricted")), ("UNVERIFIED", True))
        other = _docx(tmp / "Evaluation2.docx", ["Final Evaluation Report"])
        d2 = _run()
        self._select(d2, other, by_arfada=False)                     # not an ARFADA report
        self.assertEqual(previous_work_states(d2)["clearance"]["status"], "UNVERIFIED")
        self.assertEqual(G.report_restriction(other), "")

    def test_register_never_packages_restricted(self):
        import subprocess
        G_store = G._store()
        tmp = Path(tempfile.mkdtemp(prefix="arfada_v0616_pw_"))
        rep = _docx(tmp / "Final_Evaluation_ARFADA.docx",
                    ["Final Evaluation Report", "Prepared by ARFADA", "Executive Summary", "Findings",
                     "Recommendations", "Methodology"], header="Internal use only")
        d = _run()
        r = subprocess.run([sys.executable, str(_ROOT / "scripts" / "previous_work.py"), "register",
                            str(d), str(rep)], capture_output=True,
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        out = json.loads(r.stdout.decode("utf-8"))
        self.assertEqual(out["status"], "REGISTERED_RESTRICTED")
        self.assertFalse((d / "annexes" / "previous_work").exists())
        self.assertTrue(G_store)


class TestFastQuestions(unittest.TestCase):
    def test_purpose_and_channel_questions(self):
        from engine.tor.autopilot import build_questions
        qs = build_questions(TOR, SUB_REQS)
        keys = [q["key"] for q in qs]
        self.assertIn("run_purpose", keys)
        self.assertIn("submission_channel", keys)
        self.assertLessEqual(len(qs), 5)
        q = {x["key"]: x for x in qs}
        self.assertEqual(q["run_purpose"]["question"], "Is this a live submission or a test/replay of an older TOR?")
        self.assertEqual(q["submission_channel"]["question"],
                         "Please enter the submission email or platform specified/confirmed for this "
                         "opportunity.")
        done = build_questions(TOR, SUB_REQS, decisions={"run_purpose": {"value": "TEST_REPLAY"},
                                                         "submission_channel": {"value": "NOT_KNOWN"}})
        self.assertFalse({"run_purpose", "submission_channel"} & {x["key"] for x in done})


class TestStatusReport(_PolicyStore):
    def test_test_replay_warning_not_blocker(self):
        from engine.tor.fast_qa import two_status_report, PKG_NOT_ASSESSED
        d = _run()
        RD.record(d, "run_purpose", "TEST_REPLAY")
        RD.confirm_team_availability(d, "All selected experts are available")
        rep = two_status_report(d)
        # v0.6.17: a replay reports hypothetical live-submission gaps, not blockers
        self.assertEqual(rep["canonical_blockers"], [])
        gaps = rep["live_submission_gaps_if_applicable"]
        self.assertNotIn("DEADLINE_CONFIRMATION", gaps)
        self.assertNotIn("TEAM_AVAILABILITY", gaps)
        self.assertIn("FINANCIAL_PROPOSAL", gaps)                                # rule unchanged
        self.assertIn("SUBMISSION_CHANNEL", gaps)
        self.assertEqual(rep["submission_package_status"], PKG_NOT_ASSESSED)
        self.assertIn("Run purpose", rep["internal_gaps_md"])
        self.assertIn("has passed", rep["internal_gaps_md"])
        live = _run()
        RD.record(live, "run_purpose", "LIVE_SUBMISSION")
        self.assertIn("DEADLINE_CONFIRMATION", two_status_report(live)["canonical_blockers"])


@unittest.skipUnless(os.environ.get("ARFADA_REAL_TOR"), "set ARFADA_REAL_TOR to the original PDF")
class TestRealSouthDarfur(unittest.TestCase):
    def test_questions(self):
        from scripts.analyze_tor import analyze
        from engine.tor.autopilot import build_questions
        tmp = Path(tempfile.mkdtemp(prefix="arfada_v0616_real_"))
        analyze(Path(os.environ["ARFADA_REAL_TOR"]), output_root=tmp / "out")
        run = next((tmp / "out").iterdir())
        tor = json.loads((run / "tor_analysis.json").read_text(encoding="utf-8"))
        reqs = json.loads((run / "requirements.json").read_text(encoding="utf-8"))["requirements"]
        keys = [q["key"] for q in build_questions(tor, reqs)]
        self.assertIn("run_purpose", keys)
        self.assertIn("submission_channel", keys)
        self.assertLessEqual(len(keys), 5)


if __name__ == "__main__":
    unittest.main()
