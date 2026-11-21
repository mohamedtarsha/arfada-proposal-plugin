"""v0.6.12 regression — confirmed v0.6.11 South Darfur output.

1. previous-work SELECTION is not SHARING CLEARANCE;
2. stable staff identity (staff_profile_id + full canonical name, no token merges);
3. a TOR requirement is a physical annex only when the TOR asks for a separate file;
4. typed numeric tokens, sampling provenance, TOR duration wording;
5. role-specific staff ranking from evidence.

    python -m pytest tests/test_v0612_regression.py -v
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

os.environ.setdefault("ARFADA_HOME", tempfile.mkdtemp(prefix="arfada_v0612_home_"))

from engine.tor import claim_language as CL  # noqa: E402


# ---------------------------------------------------------------------------
# 1. previous work: selection ≠ clearance
# ---------------------------------------------------------------------------

def _pw_run(note=None):
    from engine.tor.previous_work_state import record_selection, record_clearance
    d = Path(tempfile.mkdtemp(prefix="arfada_pw_"))
    f = d / "annexes" / "previous_work" / "IRC_BHA_Sudan_Final_Evaluation.pdf"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"%PDF-1.4")
    record_selection(d, file=f, original=f, verdict={"kind": "evaluation_report", "by_arfada": True})
    res = record_clearance(d, note) if note else None
    return d, res


class TestPreviousWorkClearance(unittest.TestCase):
    def test_permission_wording(self):
        from engine.tor.previous_work_state import is_explicit_permission as ok
        for t in ("IRC cleared to share", "Permission confirmed by IRC",
                  "Yes, it may be shared externally", "Clearance granted by the IRC country office",
                  "IRC has given consent to share"):
            self.assertTrue(ok(t), t)
        for t in ("Use the IRC report", "yes, use the IRC one", "the IRC report is our pick",
                  "Before sending, check that IRC permits sharing it",
                  "it may be shared once IRC agrees", "not cleared to share yet", ""):
            self.assertFalse(ok(t), t)

    def test_selecting_does_not_clear(self):
        from engine.tor.previous_work_state import previous_work_states
        run, _ = _pw_run()
        st = previous_work_states(run)
        self.assertEqual(st["selected"]["status"], "VERIFIED")
        self.assertEqual(st["clearance"]["status"], "UNVERIFIED")
        # ARFADA authorship (by_arfada=True) is not clearance either
        run2, res = _pw_run("Use the IRC report")
        self.assertEqual(res["status"], "NOT_EXPLICIT_PERMISSION")
        self.assertEqual(previous_work_states(run2)["clearance"]["status"], "UNVERIFIED")
        # legacy flag without explicit permission is not clearance
        rec = json.loads((run / "previous_work.json").read_text())
        rec["clearance_confirmed"] = True
        (run / "previous_work.json").write_text(json.dumps(rec))
        self.assertEqual(previous_work_states(run)["clearance"]["status"], "UNVERIFIED")

    def test_explicit_permission_clears(self):
        from engine.tor.previous_work_state import previous_work_states
        run, res = _pw_run("IRC confirmed: yes, it may be shared externally")
        self.assertTrue(res["ok"])
        self.assertEqual(previous_work_states(run)["clearance"]["status"], "VERIFIED")

    def test_unique_clearance_blocker(self):
        from engine.tor.canonical_blockers import canonicalize
        state = {"claims": {"previous_work_selected": {"status": "VERIFIED", "required": True},
                            "previous_work_clearance": {"status": "UNVERIFIED", "required": True,
                                                        "detail": "sharing clearance not confirmed"},
                            "previous_work_sample": {"status": "PROVISIONAL", "required": True}}}
        items = [{"check": "SUBMISSION_PENDING", "item_key": "previous_work",
                  "message": "Previous-work example pending — sharing clearance not confirmed"},
                 {"message": "Mandatory submission item missing: Example of previous work"},
                 {"message": "Proposal claims 'Previous-work example' is annexed/attached, but no "
                             "such file exists"}]
        keys = [b["blocker"] for b in canonicalize(items, claim_state=state)]
        self.assertEqual(keys, ["PREVIOUS_WORK_CLEARANCE"])

    def test_draft_cannot_say_attached_but_may_name_report(self):
        st = {"claims": {"previous_work_sample": {"status": "PROVISIONAL"}}}
        bad = ["The final external evaluation report prepared for IRC (2026) accompanies this "
               "proposal as a separate annex.",
               "The example report accompanies this proposal as a separate annex.",
               "Addressed: example report as a separate annex",
               "The example report is attached."]
        for t in bad:
            self.assertEqual([i.claim for i in CL.find_claim_issues(t, st)],
                             ["previous_work_sample"], t)
        ok = "ARFADA proposes its IRC/BHA Sudan final evaluation (2026) as the example of previous work."
        self.assertEqual(CL.find_claim_issues(ok, st), [])


# ---------------------------------------------------------------------------
# 2. stable staff identity
# ---------------------------------------------------------------------------

def _p(rel, sid=None, **kw):
    return {"staff_id": sid or "cv_" + str(abs(hash(rel)))[:10], "source_rel_path": rel,
            "source_file_name": Path(rel).name, "source_file_id": "f_" + str(abs(hash(rel)))[:6],
            **kw}


class TestStaffIdentity(unittest.TestCase):
    def test_canonical_name_from_person_folder_not_topic_folder(self):
        from engine.tor.lknowledge.staff_identity import canonical_identity as ci
        a = ci(_p("Sudan/Agri-economy/Ahmed Mahmoud Ahmed Elamin/Ahmed thematic CV May 2025 - "
                  "Ahmed Elamin.docx"))
        self.assertEqual((a["canonical_name"], a["canonical_name_status"]),
                         ("Ahmed Mahmoud Ahmed Elamin", "PROVISIONAL"))
        b = ci(_p("Sudan/Cash-Based Intervention (CBI) Expert/Final NGO CV Ishag Siddig, A., 3rd "
                  "Draft Update April 2025.pdf"))
        self.assertEqual(b["canonical_name"], "Ishag Siddig")
        c = ci(_p("Sudan/Romisa Elsheikh - Gender  SEA-SH Specialist.pdf"))
        self.assertEqual(c["canonical_name"], "Romisa Elsheikh")
        verified = ci(_p("Sudan/X/CV.pdf", sid="cv_1"), staff_facts=[
            {"staff_id": "cv_1", "attribute": "full_name", "value": "Abdelmonim Ishag Siddig",
             "verified": True}])
        self.assertEqual((verified["canonical_name"], verified["canonical_name_status"]),
                         ("Abdelmonim Ishag Siddig", "VERIFIED"))

    def test_shared_tokens_never_merge(self):
        from engine.tor.lknowledge.staff_identity import same_person
        people = [_p("Sudan/A/CV - Ahmed Mohamed Ali.pdf"), _p("Sudan/B/CV - Ali Ahmed Mohamed.pdf"),
                  _p("Sudan/C/CV - Ahmed Ibrahim.pdf"), _p("Sudan/D/CV - Ahmed Ibrahim Hassan.pdf"),
                  _p("Sudan/E/CV - Ali Ishag Mohamed.pdf"), _p("Sudan/F/CV - Ishag Siddig.pdf"),
                  _p("Sudan/G/CV - Salaheldeen Abdelkarim.pdf"), _p("Sudan/H/CV - Abdelkarim Ishag.pdf")]
        for i, a in enumerate(people):
            for b in people[i + 1:]:
                self.assertFalse(same_person(a, b), (a["source_file_name"], b["source_file_name"]))
        # two files in one person-named folder are the same person
        self.assertTrue(same_person(_p("Sudan/X/Ahmed Mohammed Morjab/Learning Route - Ahmed Morjab.pdf"),
                                    _p("Sudan/X/Ahmed Mohammed Morjab/CV - Ahmed Morjab.pdf")))

    def test_personnel_checks_never_cross_match(self):
        state = {"team": [
            {"canonical_name": "Ali Ishag Mohamed", "claims": {"fsl": {"status": "UNVERIFIED"}}},
            {"canonical_name": "Ishag Siddig", "claims": {"fsl": {"status": "VERIFIED"}}}]}
        # a sentence about Ishag Siddig must not be attributed to Ali Ishag Mohamed
        self.assertEqual(CL.find_personnel_issues(
            "Ishag Siddig has extensive food security experience.", state), [])
        self.assertTrue(CL.find_personnel_issues(
            "Ali Ishag Mohamed has extensive food security experience.", state))

    def test_full_canonical_name_rendered(self):
        state = {"claims": {}, "team": [{"canonical_name": "Ahmed Mahmoud Ahmed Elamin",
                                         "canonical_name_status": "PROVISIONAL", "claims": {}}]}
        cand = {"blocks": [{"type": "table", "columns": ["Role", "Expert"],
                            "rows": [["Team Leader", "Ahmed M. A. Elamin"]]},
                           {"type": "paragraph", "text": "Ahmed M. A. Elamin leads the evaluation."}]}
        new, changes, _res = CL.sanitize_candidate(cand, state)
        self.assertEqual(new["blocks"][0]["rows"][0][1], "Ahmed Mahmoud Ahmed Elamin")
        self.assertIn("Ahmed Mahmoud Ahmed Elamin leads", new["blocks"][1]["text"])
        self.assertTrue(any(c["kind"] == "STAFF_NAME_NOT_CANONICAL" for c in changes))


# ---------------------------------------------------------------------------
# 3. submission requirement vs physical annex
# ---------------------------------------------------------------------------

def _req(text, cat="submission"):
    return {"req_id": "r" + str(abs(hash(text)))[:8], "category": cat, "actor": "BIDDER",
            "mandatory": True, "text": text}


SUB_REQS = [_req("Technical Proposal: Detailed methodology, work plan and team composition."),
            _req("Financial Proposal: Detailed budget, including daily rates and expenses."),
            _req("CVs/Profiles of Team Members: relevant expertise."),
            _req("Risk Mitigation Plan: Address potential challenges and risks during the survey."),
            _req("Submission deadline: Proposals must be submitted via [submission platform/email] "
                 "by 12:00 AM (Sudan Time), 21 November 2026."),
            _req("Provide a clear timeline and time frame for the activities.")]


class TestPhysicalAnnex(unittest.TestCase):
    def test_only_real_files_expected(self):
        from engine.tor.submission import physical_annex_keys
        keys = physical_annex_keys(SUB_REQS)
        self.assertEqual(sorted(keys), ["cv_annex", "detailed_budget"])
        explicit = physical_annex_keys(SUB_REQS + [_req(
            "Submit a signed declaration of independence as a separate attachment.")])
        self.assertIn("signature", explicit)

    def test_no_generic_annex_other(self):
        from engine.tor.package import check_submission_package
        from engine.tor.submission import physical_annex_keys
        d = Path(tempfile.mkdtemp())
        pkg = check_submission_package(d, item_keys=physical_annex_keys(SUB_REQS) + ["other"])
        self.assertFalse(any("other" in m.lower() for m in pkg["missing"]), pkg["missing"])

    def test_risk_plan_inside_proposal_satisfies(self):
        from engine.tor.final_qa import run_final_qa
        d = Path(tempfile.mkdtemp(prefix="arfada_risk_"))
        (d / "tor_analysis.json").write_text(json.dumps({"run_id": "r", "metadata": {}}))
        (d / "requirements.json").write_text(json.dumps({"requirements": SUB_REQS}))
        gs = d / "generated_sections"
        gs.mkdir()
        (gs / "DATA_COLLECTION.json").write_text(json.dumps({"section_id": "DATA_COLLECTION", "blocks": [
            {"type": "paragraph", "text": "Risk mitigation plan: access, security and data risks are "
                                          "managed through daily security checks. The work plan "
                                          "and timeline follow the TOR schedule."}]}))
        (d / "generation_status.json").write_text(json.dumps({"sections": {"DATA_COLLECTION": {"status": "READY"}}}))
        msgs = [f["message"] for f in run_final_qa(d)["findings"] if f["check"] == "SUBMISSION"]
        self.assertFalse(any("Risk Mitigation" in m for m in msgs), msgs)
        self.assertFalse(any("deadline" in m.lower() for m in msgs), msgs)
        self.assertFalse(any("timeline" in m.lower() for m in msgs), msgs)
        self.assertTrue(any("budget" in m.lower() for m in msgs))      # physical item still due


# ---------------------------------------------------------------------------
# 4. numeric tokens, sampling provenance, duration wording
# ---------------------------------------------------------------------------

class TestNumericTokens(unittest.TestCase):
    def test_token_types(self):
        from engine.tor.numeric_tokens import tokenize
        got = {(t.raw, t.kind) for t in tokenize(
            "ARFADA's portfolio of 156 projects includes 73,906 household surveys. ARFADA will report "
            "the CFGB 3350 PMF within 30 days, with a 10% reserve, as in 2026.")}
        for exp in [("156", "PORTFOLIO_METRIC"), ("73,906", "PORTFOLIO_METRIC"),
                    ("3350", "IDENTIFIER"), ("30", "DURATION"), ("10", "PERCENTAGE"),
                    ("2026", "YEAR")]:
            self.assertIn(exp, got)
        self.assertNotIn(("73", "PORTFOLIO_METRIC"), got)
        self.assertNotIn(("906", "PORTFOLIO_METRIC"), got)

    def _qa(self, text):
        from engine.tor.final_qa import run_final_qa
        d = Path(tempfile.mkdtemp(prefix="arfada_num_"))
        (d / "tor_analysis.json").write_text(json.dumps({"run_id": "r", "metadata": {}}))
        (d / "requirements.json").write_text(json.dumps({"requirements": []}))
        (d / "knowledge_snapshot").mkdir()
        (d / "knowledge_snapshot" / "projects.json").write_text(json.dumps({"metrics": {
            "total_projects": 156, "total_surveys": 73906, "total_kii": 2721, "total_fgd": 1664}}))
        gs = d / "generated_sections"
        gs.mkdir()
        (gs / "SAMPLING.json").write_text(json.dumps({"section_id": "SAMPLING", "blocks": [
            {"type": "paragraph", "text": text}]}))
        (d / "generation_status.json").write_text(json.dumps({"sections": {"SAMPLING": {"status": "READY"}}}))
        return run_final_qa(d)["findings"]

    def test_no_false_arfada_numbers(self):
        f = self._qa("ARFADA's portfolio of 156 projects includes 73,906 household surveys, 2,721 KIIs "
                     "and 1,664 FGDs. ARFADA will report every CFGB 3350 PMF indicator within 30 days.")
        self.assertEqual([x for x in f if x["check"] == "ARFADA_FACT"], [])
        f2 = self._qa("ARFADA has delivered 999 projects across the region.")
        self.assertTrue(any(x["check"] == "ARFADA_FACT" and "999" in x["message"] for x in f2))

    def test_validation_duration_is_not_an_org_claim(self):
        from engine.tor.generation import validate_candidate
        packet = {"section_id": "WORKPLAN", "mandatory_slots": [], "applied_decisions": [],
                  "output_contract": {}, "verified_arfada_facts": []}

        def errs(text):
            return [e for e in validate_candidate(packet, {
                "section_id": "WORKPLAN", "blocks": [{"block_id": "b1", "type": "paragraph",
                                                      "text": text}],
                "requirement_response_ledger": []})["errors"] if "UNSUPPORTED_ARFADA" in e]
        self.assertEqual(errs("ARFADA has completed fieldwork over 30 days in each locality."), [])
        self.assertTrue(errs("ARFADA has completed over 200 evaluations across the region."))

    def test_sampling_provenance(self):
        from engine.tor.numeric_claims import sampling_provenance, prose_claims
        t = ("A finite population correction gives a minimum sample of 225 households. Adding about "
             "10% for non-response gives 247.5, rounded up to 250 households; the proposed sample is "
             "250. The baseline sample was 243 households.")
        p = sampling_provenance(t)
        self.assertEqual((p["minimum"], p["allowance_pct"], p["adjusted"], p["proposed"],
                          p["rounding"], p["baseline"]), (225, 10, 247.5, 250, "upward", 243))
        # v0.6.13: 247.5 is n × (1 + r); non-response inflation is n / (1 − r) = 250
        self.assertFalse(p["consistent"])
        self.assertEqual((p["draft_formula"], p["required_initial"]), ("n * (1 + r)", 250))
        self.assertEqual(sorted({c.value for c in prose_claims(t, "SAMPLING")
                                 if c.metric == "survey"}), [250])      # 247.5 and 243 separate
        f = self._qa(t)
        self.assertEqual([x for x in f if x["check"] == "CONTRADICTION"], [])
        self.assertEqual(len([x for x in f if x["check"] == "SAMPLING_PROVENANCE"]), 1)
        t13 = ("A finite population correction gives a minimum sample of 225 households. Allowing "
               "for 10% non-response, the required initial sample is 225 / 0.90 = 250 households; the "
               "proposed sample is 250. The baseline sample was 243 households.")
        self.assertTrue(sampling_provenance(t13)["consistent"])
        self.assertEqual([x for x in self._qa(t13)
                          if x["check"] in ("SAMPLING_PROVENANCE", "CONTRADICTION")], [])
        bad = sampling_provenance("Minimum sample 225; 10% reserve; proposed sample 240.")
        self.assertFalse(bad["consistent"])

    def test_baseline_sentence_not_current(self):
        from engine.tor.numeric_claims import prose_claims
        self.assertEqual([c.value for c in prose_claims(
            "This is slightly larger than the baseline round, which interviewed 243 households.",
            "SAMPLING") if c.metric == "survey"], [])

    def test_duration_wording_kept(self):
        st = {"tor_durations": ["30||day", "4||day"]}
        issues = CL.find_duration_issues("The evaluation takes 30 working days.", st)
        self.assertEqual([(i.match, i.replacement) for i in issues], [("30 working days", "30 days")])
        new, changes, _r = CL.sanitize_candidate(
            {"blocks": [{"type": "paragraph", "text": "Within 30 working days."}]},
            {"claims": {}, **st})
        self.assertEqual(new["blocks"][0]["text"], "Within 30 days.")
        # when the TOR itself says working days, nothing is changed
        self.assertEqual(CL.find_duration_issues("30 working days", {"tor_durations": ["30|working|day"]}), [])


# ---------------------------------------------------------------------------
# 5. role-specific ranking
# ---------------------------------------------------------------------------

def _cv(rel, evidence=(), roles=(), years=None, sid=None):
    from engine.tor.lknowledge.staff_country import apply_country
    from engine.tor.lknowledge.staff_doctype import with_document_type
    p = {"staff_id": sid or "cv_" + str(abs(hash(rel)))[:10], "name": Path(rel).stem,
         "roles": list(roles), "years_experience": years,
         "years_experience_status": "VERIFIED" if years else "NOT_STATED",
         "evidence": {"years_experience": f"{years} years of experience" if years else ""},
         "source_file_name": Path(rel).name, "extraction_confidence": "MEDIUM",
         "role_evidence": list(evidence)}
    return with_document_type(apply_country(p, rel))


TEAM_REQS = [_req("Proven experience in insecure environments with conflict-sensitive approaches.", "team"),
             _req("Familiarity with humanitarian food security indicators (FCS, rCSI).", "team"),
             _req("Technical expertise in survey design and analysis, including sampling.", "team"),
             _req("Gender-sensitive assessments and understanding of protection and safeguarding.", "team"),
             _req("Familiarity with the operational environment in South Darfur.", "team")]
TOR = {"metadata": {"country": {"value": "Sudan"},
                    "subnational_location": {"values": ["South Darfur", "Nyala"]},
                    "assignment": {"value": "Final Evaluation of a food voucher project in South Darfur"}},
       "assignment_type": {"assignment_type": "ENDLINE"}}

POOL = [
    _cv("Sudan/X/Amal Osman CV.pdf", ["Team Leader of 12 final evaluations in Darfur and Nyala",
                                      "Led mixed-methods evaluations in conflict-affected areas",
                                      "Food security evaluation for WFP"], roles=["Team Leader"], years=18),
    _cv("Sudan/X/Badr Hassan CV.pdf", ["Food security and livelihoods specialist: voucher programmes",
                                       "Designed FCS and rCSI modules for the FSL assessment",
                                       "Market assessment of cereal prices"], years=11),
    _cv("Sudan/X/Huda Saleh CV.pdf", ["Safeguarding focal point; PSEA and GBV referral training",
                                      "Protection and gender mainstreaming in Darfur"], years=9),
    _cv("Sudan/X/Omar Bashir CV.pdf", ["Statistician: sampling design and analysis in SPSS and Stata",
                                       "KoboToolbox data collection for evaluations"], years=8),
    _cv("Sudan/X/Yasir Adam CV.pdf", ["Field coordinator in Nyala, South Darfur",
                                      "Supervised enumerators and liaison with local authorities",
                                      "Voucher distribution monitoring"], years=10),
    # decoys: a job title with no evidence, and a certificate full of keywords
    _cv("Sudan/Food Security Specialist/Sami Noor CV.pdf", roles=["Team Leader", "Consultant"]),
    _cv("Sudan/X/Training Certificate - Food Security Team Leader - Ali Musa.pdf",
        ["Team Leader certificate: food security evaluation in Darfur, vouchers, FCS, rCSI"],
        roles=["Team Leader"], years=20),
]


class TestRoleFit(unittest.TestCase):
    def _rank(self):
        from engine.tor.autopilot import rank_team
        from engine.tor.knowledge import Knowledge
        k = Knowledge()
        k._live_staff = list(POOL)
        return rank_team(k, TEAM_REQS, country="Sudan", tor=TOR)

    def test_roles_detected(self):
        from engine.tor.lknowledge.staff_role_fit import detect_roles
        self.assertEqual(detect_roles(TEAM_REQS), ["TEAM_LEADER", "FSL", "GENDER_PROTECTION",
                                                    "DATA_ANALYST", "FIELD_COORDINATOR"])

    def test_tor_fit_candidates_per_role(self):
        res = self._rank()
        by_role = {m["role"]: m["canonical_name"] for m in res["team"] if m["role"]}
        self.assertEqual(by_role, {
            "Team Leader": "Amal Osman",
            "Food Security & Livelihoods Specialist": "Badr Hassan",
            "Gender, Protection & Safeguarding Specialist": "Huda Saleh",
            "Data Analyst / Statistician": "Omar Bashir",
            "Field Coordinator": "Yasir Adam"})
        names = [m["canonical_name"] for m in res["team"]]
        self.assertEqual(len(names), len(set(names)))                     # distinct people
        self.assertNotIn("Ali Musa", names)                               # certificate ineligible
        for m in res["team"]:
            self.assertTrue(m["staff_profile_id"].startswith("cv_"))

    def test_job_title_alone_is_not_role_fit(self):
        from engine.tor.lknowledge.staff_role_fit import role_fit_score
        from engine.tor.lknowledge.staff_nominate import tor_context
        ctx = tor_context(TOR, TEAM_REQS, "Sudan")
        s_title, b = role_fit_score(POOL[5], "FSL", ctx)
        self.assertEqual(b.get("food_security"), 3.0)        # filing folder only → half credit…
        self.assertNotIn("vouchers_cash", b)
        self.assertNotIn("fsl_indicators", b)
        s_real, b_real = role_fit_score(POOL[1], "FSL", ctx)
        self.assertEqual(b_real.get("food_security"), 6)     # CV evidence → full credit
        self.assertGreater(s_real, s_title + 10)             # …far below CV evidence

    def test_fast_mode_question_cap(self):
        from engine.tor.autopilot import autopilot
        from engine.tor.knowledge import Knowledge
        k = Knowledge()
        k._live_staff = list(POOL)
        res = autopilot(TOR, TEAM_REQS + SUB_REQS, [], k)
        self.assertLessEqual(res["question_count"], 5)

    def test_writing_dna_classifier_unchanged(self):
        from engine.tor.assignment_type import infer_assignment_type
        from tests.fixtures import south_darfur as SD
        self.assertEqual(infer_assignment_type(SD.METADATA, SD.REQUIREMENTS).assignment_type,
                         "BASELINE")       # legacy (exemplar-scan) scoring, frozen


class TestSecondTor(unittest.TestCase):
    """Unrelated TOR (Iraq WASH baseline): no team roles → generic ranking path; only
    real files expected in the package; TOR wording kept."""

    @classmethod
    def setUpClass(cls):
        from scripts.analyze_tor import analyze
        from tests.fixtures import iraq_wash_tor as IQ
        tmp = Path(tempfile.mkdtemp(prefix="arfada_v0612_iq_"))
        analyze(IQ.build(tmp / "iq.docx"), output_root=tmp / "out")
        cls.run_dir = next((tmp / "out").iterdir())
        cls.reqs = json.loads((cls.run_dir / "requirements.json").read_text())["requirements"]

    def test_physical_annexes_only(self):
        from engine.tor.submission import physical_annex_keys
        from engine.tor.submission_blockers import required_items
        keys = set(physical_annex_keys(self.reqs)) | set(required_items(self.reqs))
        self.assertEqual(keys, {"cv_annex", "detailed_budget"})

    def test_no_roles_generic_ranking(self):
        from engine.tor.lknowledge.staff_role_fit import detect_roles
        self.assertEqual(detect_roles(self.reqs), [])

    def test_duration_mentions_recorded(self):
        tor = json.loads((self.run_dir / "tor_analysis.json").read_text())
        self.assertIn("45||day", tor["duration_mentions"])


if __name__ == "__main__":
    unittest.main()
