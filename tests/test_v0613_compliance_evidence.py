"""v0.6.13 regression — confirmed v0.6.12 South Darfur output.

1. requirement types + evidence-aware compliance: a methodology commitment never
   satisfies a personnel / company qualification; team-level coverage matrix;
   the mandatory coverage summary reflects partial / evidence-gap items;
2. non-response inflation n / (1 − r) with stored arithmetic (225 / 0.90 = 250),
   baseline 243 kept separate;
3. source semantics: TOR TARGET figures (780 FHH / 520 MHH) are never called
   "registered"; target-derived allocations (150 / 100) are explicitly provisional.

    python -m pytest tests/test_v0613_compliance_evidence.py -v
Optional: ARFADA_REAL_TOR=<original South Darfur PDF> also runs the real-TOR checks.
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

os.environ.setdefault("ARFADA_HOME", tempfile.mkdtemp(prefix="arfada_v0613_home_"))

from engine.tor import requirement_evidence as RE  # noqa: E402
from engine.tor import source_semantics as SS  # noqa: E402

CHS_REQ = {"req_id": "r_chs", "category": "team", "mandatory": True, "actor": "BIDDER",
           "text": "Strong understanding of Core Humanitarian Standards (CHS), Sphere Standards, "
                   "and safeguarding principles."}
SADD_REQ = {"req_id": "r_sadd", "category": "team", "mandatory": True, "actor": "BIDDER",
            "text": "Ability to collect and analyse Sex, Age, and Disability Disaggregated Data."}
YEARS_REQ = {"req_id": "r_years", "category": "team", "mandatory": True, "actor": "BIDDER",
             "text": "At least 5 years of experience in conducting baseline surveys / evaluations "
                     "related to FSL programmes, preferably in South Darfur."}
DEPLOY_REQ = {"req_id": "r_dep", "category": "general", "mandatory": True, "actor": "BIDDER",
              "text": "Capacity to deploy teams in South Darfur quickly."}
METH_REQ = {"req_id": "r_meth", "category": "data_collection_methods", "mandatory": True,
            "actor": "BIDDER", "constraint_type": "NONE",
            "text": "The evaluation will employ a mixed-methods approach that integrates "
                    "quantitative surveys with qualitative tools."}
TL_REQ = {"req_id": "r_tl", "category": "team", "mandatory": True, "actor": "BIDDER",
          "text": "The Team Leader must have proven experience in gender-sensitive evaluations."}


def _member(sid, role, text, *, years=None, folder=""):
    """A selected expert as the claim state stores it (evidence from CV text)."""
    prof = {"staff_id": sid, "evidence": {"summary": text},
            "source_rel_path": f"Sudan/{folder}/{sid}.pdf" if folder else ""}
    return {"staff_id": sid, "staff_profile_id": sid, "canonical_name": sid.title(), "role": role,
            "claims": {"years_experience": {"status": "VERIFIED" if years else "UNVERIFIED",
                                            "value": years}},
            "qualification_evidence": RE.member_topic_evidence(prof, places=["South Darfur"])}


class TestRequirementTypes(unittest.TestCase):
    def test_classification(self):
        t = RE.requirement_type
        self.assertEqual(t(CHS_REQ), RE.PERSONNEL_QUALIFICATION)
        self.assertEqual(t(SADD_REQ), RE.PERSONNEL_QUALIFICATION)
        self.assertEqual(t(DEPLOY_REQ), RE.COMPANY_QUALIFICATION)
        self.assertEqual(t(METH_REQ), RE.METHODOLOGY_REQUIREMENT)       # 'NONE' ≠ a constraint
        self.assertEqual(t({"category": "deliverable", "text": "Inception report"}),
                         RE.DELIVERABLE_REQUIREMENT)
        self.assertEqual(t({"category": "general", "text": "Evidence of registration as a "
                            "consultant(s) or firm."}), RE.SUBMISSION_ARTIFACT)
        self.assertEqual(t({"category": "submission", "text": "Financial Proposal: Detailed budget"}),
                         RE.SUBMISSION_ARTIFACT)
        self.assertEqual(t({"category": "general", "constraint_type": "AT_LEAST",
                            "text": "A 90% confidence level and a 5% margin of error."}),
                         RE.DESIGN_CONSTRAINT)
        # an indicator target ("At least 90% …") is not a years-of-experience qualification
        self.assertNotIn(t({"category": "general", "text": "At least 90% of food received consumed "
                            "by targeted households."}), RE.QUALIFICATION_TYPES)


class TestEvidenceCoverage(unittest.TestCase):
    def test_methodology_commitment_never_covers_a_qualification(self):
        team = [_member("tl", "Team Leader", "Led baseline and endline evaluations in Darfur.")]
        row = RE.evidence_coverage(CHS_REQ, team)                    # the draft may promise CHS…
        self.assertEqual(row["evidence_status"], RE.EV_GAP)          # …but nobody evidences it
        self.assertEqual(RE.qualification_readiness(row), RE.AT_RISK)
        self.assertIn("commitment", row["basis"])

    def test_partial_and_team_level_coverage(self):
        gender = _member("g", "Gender Specialist", "Upheld safeguarding, PSEA and accountability.")
        stat = _member("s", "Data Analyst", "Certifications: Core Humanitarian Standard (CHS).")
        row = RE.evidence_coverage(CHS_REQ, [gender])
        self.assertEqual(row["evidence_status"], RE.EV_PARTIAL)
        self.assertEqual(set(row["gaps"]), {"Core Humanitarian Standard (CHS)", "Sphere Standards"})
        row2 = RE.evidence_coverage(CHS_REQ, [gender, stat])          # collective
        self.assertEqual(row2["evidence_status"], RE.EV_PARTIAL)
        self.assertEqual(row2["gaps"], ["Sphere Standards"])
        sphere = _member("f", "FSL Specialist", "Applied Sphere minimum standards for food security.")
        full = RE.evidence_coverage(CHS_REQ, [gender, stat, sphere])
        self.assertEqual(full["evidence_status"], RE.EV_VERIFIED)
        self.assertEqual(full["scope"], "TEAM_COLLECTIVE")
        by = {e["element"]: [b["staff_profile_id"] for b in e["by"]] for e in full["elements"]}
        self.assertEqual((by["chs"], by["sphere"], by["safeguarding"]), (["s"], ["f"], ["g"]))

    def test_role_assigned_requirement(self):
        tl = _member("tl", "Team Leader", "Led evaluations of food assistance projects.")
        g = _member("g", "Gender Specialist", "Gender-sensitive evaluations and GBV programming.")
        row = RE.evidence_coverage(TL_REQ, [tl, g])
        self.assertEqual((row["scope"], row["assigned_role"]), ("ROLE_ASSIGNED", "team_leader"))
        self.assertNotEqual(row["evidence_status"], RE.EV_VERIFIED)   # gender only via g

    def test_years_need_one_expert_with_the_experience(self):
        a = _member("a", "Team Leader", "Food security baseline and endline evaluations.", years=20)
        b = _member("b", "Field Coordinator", "Field logistics.", years=3)
        self.assertEqual(RE.evidence_coverage(YEARS_REQ, [a, b])["evidence_status"], RE.EV_VERIFIED)
        self.assertNotEqual(RE.evidence_coverage(YEARS_REQ, [b])["evidence_status"], RE.EV_VERIFIED)
        el = RE.qualification_elements(YEARS_REQ["text"], places=["South Darfur"])
        self.assertEqual((el["min_years"], el["preferred"]), (5, ["local_area"]))   # 'preferably'

    def test_company_deploy_uses_roster(self):
        team = [_member("f", "FSL Specialist", "Head of Office for South Darfur.")]
        row = RE.evidence_coverage(DEPLOY_REQ, team, places=["South Darfur"],
                                   company={"field_roster": "PROVISIONAL"})
        self.assertEqual(row["evidence_status"], RE.EV_PARTIAL)

    def test_no_team_is_an_evidence_gap(self):
        self.assertEqual(RE.evidence_coverage(SADD_REQ, [])["evidence_status"], RE.EV_GAP)

    def test_artifacts_follow_claim_state(self):
        reg = {"req_id": "r_reg", "category": "general", "mandatory": True,
               "text": "Evidence of registration as a consultant(s) or firm."}
        row = RE.evidence_coverage(reg, [], claims={"registration_evidence": {"status": "MISSING"}})
        self.assertEqual(row["evidence_status"], RE.EV_GAP)
        row = RE.evidence_coverage(reg, [], claims={"registration_evidence": {"status": "VERIFIED"}})
        self.assertEqual(row["evidence_status"], RE.EV_VERIFIED)

    def test_summary_counts_evidence_quality(self):
        team = [_member("g", "Gender Specialist", "Safeguarding and PSEA.")]
        m = [RE.evidence_coverage(r, team) for r in (CHS_REQ, SADD_REQ, METH_REQ)]
        from engine.tor.response_coverage import combine, coverage_summary, ADDRESSED
        s = coverage_summary(combine(m, {r: {"response_status": ADDRESSED}
                                         for r in ("r_chs", "r_sadd", "r_meth")}))
        self.assertEqual(s["content"], {"addressed": 3, "partially_addressed": 0,
                                        "not_addressed": 0})                 # text answers all
        self.assertEqual((s["evidence"]["verified"], s["evidence"]["partial"],
                          s["evidence"]["gaps"], s["evidence"]["not_required"]), (0, 1, 1, 1))
        self.assertEqual(s["qualification_readiness"], RE.AT_RISK)


def _qa_run(team_profiles, *, requirements, sections):
    d = Path(tempfile.mkdtemp(prefix="arfada_v0613_qa_"))
    (d / "tor_analysis.json").write_text(json.dumps({"run_id": "r", "metadata": {
        "country": {"value": "Sudan"},
        "subnational_location": {"values": ["South Darfur", "Nyala Shamal"]}}}))
    (d / "requirements.json").write_text(json.dumps({"requirements": requirements}))
    (d / "proposed_setup.json").write_text(json.dumps({"team": team_profiles}))
    gs = d / "generated_sections"
    gs.mkdir()
    status = {}
    for sid, (blocks, ledger) in sections.items():
        (gs / f"{sid}.json").write_text(json.dumps({"section_id": sid, "blocks": blocks,
                                                    "requirement_response_ledger": ledger}))
        status[sid] = {"status": "READY"}
    (d / "generation_status.json").write_text(json.dumps({"sections": status}))
    return d


class TestQaIntegration(unittest.TestCase):
    def test_summary_and_findings(self):
        from engine.tor.final_qa import run_final_qa
        from engine.tor.blockers import classify_blockers, DRAFT_BLOCKER
        team = [{"staff_id": "cv_g", "role": "Gender Specialist",
                 "evidence": {"s": "Upheld safeguarding, PSEA and accountability."}}]
        ledger = [{"requirement_id": r["req_id"], "status": "ADDRESSED", "block_ids": ["t1"]}
                  for r in (CHS_REQ, SADD_REQ, METH_REQ)]
        blocks = [{"block_id": "t1", "type": "paragraph", "text":
                   "Evaluation tools will be referenced to CHS commitments, Sphere standards and "
                   "safeguarding principles; "
                   "the questionnaire records sex, age and disability for disaggregated analysis."}]
        d = _qa_run(team, requirements=[CHS_REQ, SADD_REQ, METH_REQ],
                    sections={"TEAM": (blocks, ledger)})
        qa = run_final_qa(d)
        s = qa["summary"]
        self.assertEqual(s["mandatory_addressed"], 3)                    # all in the text…
        self.assertEqual(s["content_coverage"]["addressed"], 3)
        self.assertEqual((s["evidence_coverage"]["partial"], s["evidence_coverage"]["gaps"]),
                         (1, 1))                                         # …not all evidenced
        rows = {r["req_id"]: r for r in qa["requirement_coverage"]}
        self.assertEqual((rows["r_chs"]["response_status"], rows["r_chs"]["evidence_status"]),
                         ("ADDRESSED", RE.EV_PARTIAL))
        self.assertEqual((rows["r_sadd"]["response_status"], rows["r_sadd"]["evidence_status"]),
                         ("ADDRESSED", RE.EV_GAP))
        ev = [f for f in qa["findings"] if f["check"] == "REQUIREMENT_EVIDENCE"]
        self.assertEqual({f["requirement_id"] for f in ev}, {"r_chs", "r_sadd"})
        self.assertTrue(all(f["severity"] == "INFO" for f in ev))       # never a draft blocker
        self.assertFalse(any(b.get("check") == "REQUIREMENT_EVIDENCE"
                             for b in classify_blockers(qa)[DRAFT_BLOCKER]))
        from engine.tor.final_qa import to_markdown
        md = to_markdown(qa)
        self.assertIn("CONTENT COVERAGE — 3/3 mandatory addressed", md)
        self.assertIn("EVIDENCE COVERAGE — 0/2 requiring evidence verified · 1 partial · 1 gaps", md)

    def test_generation_policy_lists_gaps(self):
        from engine.tor.claim_state import build_claim_state, generation_policy
        d = _qa_run([{"staff_id": "cv_g", "role": "Gender Specialist",
                      "evidence": {"s": "Safeguarding and PSEA."}}],
                    requirements=[CHS_REQ, METH_REQ], sections={})
        pol = generation_policy(build_claim_state(d))
        gaps = {g["req_id"]: g for g in pol["qualification_evidence_gaps"]}
        self.assertEqual(list(gaps), ["r_chs"])
        self.assertIn("Sphere Standards", gaps["r_chs"]["not_evidenced"])
        self.assertIn("n / (1 - r)", pol["sampling_rule"])


class TestNonResponseInflation(unittest.TestCase):
    def test_formula(self):
        from engine.tor.numeric_claims import required_initial_sample
        r = required_initial_sample(225, 10)
        self.assertEqual((r["formula"], r["exact"], r["required_initial"]), ("n / (1 - r)", 250.0, 250))
        self.assertEqual(r["arithmetic"], "225 / (1 - 0.1) = 225 / 0.9 = 250")
        self.assertEqual(required_initial_sample(300, 5)["required_initial"], 316)   # 315.79 → up

    def test_provenance_and_baseline(self):
        from engine.tor.numeric_claims import sampling_provenance
        ok = sampling_provenance(
            "The minimum sample is 225 households. Allowing for 10% non-response, the required "
            "initial sample is 225 / 0.90 = 250 households. The proposed sample is 250 "
            "households. The baseline sample was 243 households.")
        self.assertTrue(ok["consistent"], ok["issues"])
        self.assertEqual((ok["required_initial"], ok["proposed"], ok["baseline"],
                          ok["draft_formula"]), (250, 250, 243, "n / (1 - r)"))
        old = sampling_provenance("Minimum sample 225; a 10% allowance for non-response gives an "
                                  "adjusted value of 247.5, rounded up to 250.")
        self.assertEqual(old["draft_formula"], "n * (1 + r)")
        self.assertFalse(old["consistent"])
        short = sampling_provenance("Minimum sample 225, 10% non-response; proposed sample 248.")
        self.assertTrue(any("below the required initial sample 250" in i for i in short["issues"]))

    def test_table_baseline_and_no_contradiction(self):
        from engine.tor.final_qa import run_final_qa
        blocks = [{"block_id": "b1", "type": "paragraph", "text":
                   "The minimum sample after finite population correction is 225 households. With "
                   "10% non-response the required initial sample is 225 / 0.90 = 250 households."},
                  {"block_id": "b2", "type": "table", "columns": ["Parameter", "Value"], "rows": [
                      ["Expected change in baseline indicators", "6"],
                      ["Proposed household sample", "250"],
                      ["Baseline sample (as stated in the TOR)", "243"]]}]
        d = _qa_run([], requirements=[], sections={"SAMPLING": (blocks, [])})
        qa = run_final_qa(d)
        self.assertEqual(qa["sampling_provenance"]["baseline"], 243)   # not the '6' header cell
        self.assertEqual(qa["sampling_provenance"]["required_initial"], 250)
        self.assertEqual([f for f in qa["findings"]
                          if f["check"] in ("CONTRADICTION", "SAMPLING_PROVENANCE")], [])


TOR_TEXT = (
    "The project provides 4 rounds of food through vouchers to 1,300 selected and verified food "
    "insecure households (HHs).\nIndicator Baseline Target\nIncreased access to nutritious food\n"
    "0 780 female-headed households\nand 520 male-headed\nhouseholds receiving voucher-\nbased food "
    "assistance.\nSatisfaction with distribution\n0 At least 80% (1,040 HH) of\nregistered "
    "participant\nhouseholds (624 FHH and 416\nMHH) report being satisfied.\n"
    "The main purpose of the end line evaluation is to find out to what extent the originally planned "
    "targets are fulfilled.\nIn the baseline the proposed target number of HHs was 243.")

ALLOC_TABLE = {"block_id": "b51", "type": "table",
               "columns": ["Stratum", "Registered households (TOR)", "Proposed sample",
                           "Approximate margin of error at 90%"],
               "rows": [["Female-headed households", "780", "150", "±6 percentage points"],
                        ["Male-headed households", "520", "100", "±7 percentage points"],
                        ["All participant households", "1,300", "250", "±5 percentage points"]]}


class TestSourceSemantics(unittest.TestCase):
    def setUp(self):
        self.reg = SS.build_register(TOR_TEXT)
        self.fig = {f["value"]: f for f in self.reg["figures"]}

    def test_register(self):
        self.assertEqual(self.fig[780]["semantics"], [SS.TARGET])
        self.assertEqual(self.fig[520]["semantics"], [SS.TARGET])
        self.assertFalse(self.fig[780]["registered_supported"])
        self.assertEqual(self.fig[243]["semantics"], [SS.OBSERVED_BASELINE])
        self.assertIn(SS.REGISTERED_CASELOAD, self.fig[1300]["semantics"])   # "selected and verified"
        self.assertEqual(self.fig[1040]["semantics"], [SS.TARGET])           # 'at least' target

    def test_registered_wording_and_provisional_allocation(self):
        cand = {"blocks": [{"block_id": "b50", "type": "paragraph",
                            "text": "The sample is stratified by head of household."}, ALLOC_TABLE]}
        kinds = sorted(i["kind"] for i in SS.find_population_issues(cand, self.reg, section_id="S"))
        self.assertEqual(kinds, ["ALLOCATION_NOT_PROVISIONAL", "REGISTERED_TARGET_FIGURE"])
        new, changes = SS.sanitize_population(cand, self.reg, section_id="SAMPLING")
        cols = new["blocks"][1]["columns"]
        self.assertEqual(cols[1:3], ["TOR target composition", "Provisional allocation"])
        note = new["blocks"][2]["text"]
        self.assertEqual(note, "Provisional allocation based on the TOR target composition: "
                               "150 FHH / 100 MHH. The allocation will be recalculated at "
                               "inception from the registration list.")
        self.assertEqual(SS.find_population_issues(new, self.reg), [])
        self.assertEqual(cand["blocks"][1]["columns"][1], "Registered households (TOR)")  # copy

    def test_sentence_rewrite_and_tor_target_statement(self):
        cand = {"blocks": [{"type": "paragraph", "text":
                            "The 780 registered female-headed households will be sampled first."},
                           {"type": "paragraph", "text":
                            "At least 80% (1,040 HH) of registered participant households report "
                            "satisfaction."}]}
        issues = SS.find_population_issues(cand, self.reg)
        self.assertEqual([i["kind"] for i in issues], ["REGISTERED_TARGET_FIGURE"])  # TOR target kept
        new, _ = SS.sanitize_population(cand, self.reg)
        self.assertEqual(new["blocks"][0]["text"],
                         "The 780 target female-headed households will be sampled first.")
        self.assertIn("registered participant households", new["blocks"][1]["text"])

    def test_project_record_supports_registered(self):
        d = Path(tempfile.mkdtemp(prefix="arfada_v0613_rec_"))
        (d / SS.SEMANTICS_FILE).write_text(json.dumps(self.reg))
        SS.record_project_figure(d, 780, "FHH on the registration list", "ZOA registration list")
        reg = SS.load_register(d)
        f = {x["value"]: x for x in reg["figures"]}
        self.assertTrue(f[780]["registered_supported"])
        self.assertIn(SS.VERIFIED_PROJECT_RECORD, f[780]["semantics"])
        self.assertFalse(f[520]["registered_supported"])         # never promoted silently

    def test_sanitizer_wired_into_final_language(self):
        from engine.tor.claim_language import sanitize_candidate
        state = {"claims": {}, "population_figures": self.reg}
        new, changes, _res = sanitize_candidate({"blocks": [ALLOC_TABLE]}, state, section_id="SAMPLING")
        self.assertIn("TOR target composition", new["blocks"][0]["columns"])
        self.assertTrue(any(c["kind"] == "ALLOCATION_NOT_PROVISIONAL" for c in changes))


class TestSecondTor(unittest.TestCase):
    """Unrelated TOR (Iraq WASH baseline): no qualification rows, 4,000 households is a target."""

    def test_iraq_wash(self):
        from scripts.analyze_tor import analyze
        from engine.tor.claim_state import build_claim_state
        from tests.fixtures import iraq_wash_tor as IQ
        tmp = Path(tempfile.mkdtemp(prefix="arfada_v0613_iq_"))
        analyze(IQ.build(tmp / "iq.docx"), output_root=tmp / "out")
        run = next((tmp / "out").iterdir())
        reg = json.loads((run / SS.SEMANTICS_FILE).read_text(encoding="utf-8"))
        f = {x["value"]: x for x in reg["figures"]}
        self.assertEqual(f[4000]["semantics"], [SS.TARGET])
        st = build_claim_state(run)
        types = {r["requirement_type"] for r in st["requirement_evidence"]}
        self.assertFalse(types & set(RE.QUALIFICATION_TYPES))
        self.assertIn(RE.SUBMISSION_ARTIFACT, types)


@unittest.skipUnless(os.environ.get("ARFADA_REAL_TOR"), "set ARFADA_REAL_TOR to the original PDF")
class TestRealSouthDarfurTor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from scripts.analyze_tor import analyze
        tmp = Path(tempfile.mkdtemp(prefix="arfada_v0613_real_"))
        analyze(Path(os.environ["ARFADA_REAL_TOR"]), output_root=tmp / "out")
        cls.run_dir = next((tmp / "out").iterdir())
        cls.reqs = json.loads((cls.run_dir / "requirements.json").read_text(encoding="utf-8"))["requirements"]

    def test_target_semantics(self):
        reg = json.loads((self.run_dir / SS.SEMANTICS_FILE).read_text(encoding="utf-8"))
        f = {x["value"]: x for x in reg["figures"]}
        for v in (780, 520):
            self.assertEqual(f[v]["semantics"], [SS.TARGET], v)
            self.assertFalse(f[v]["registered_supported"], v)
        self.assertEqual(f[243]["semantics"], [SS.OBSERVED_BASELINE])

    def test_chs_sphere_is_an_evidence_gap_without_cv_evidence(self):
        chs = next(r for r in self.reqs if "Core Humanitarian" in r["text"])
        self.assertEqual(RE.requirement_type(chs), RE.PERSONNEL_QUALIFICATION)
        team = [_member("tl", "Team Leader", "Led baseline, endline and impact evaluations; "
                        "safeguarding and informed consent in data collection.", years=20)]
        row = RE.evidence_coverage(chs, team)
        self.assertNotEqual(row["evidence_status"], RE.EV_VERIFIED)
        self.assertIn("Sphere Standards", row["gaps"])
        self.assertIn("Core Humanitarian Standard (CHS)", row["gaps"])

    def test_requirement_types(self):
        types = {RE.requirement_type(r) for r in self.reqs}
        self.assertTrue({RE.PERSONNEL_QUALIFICATION, RE.COMPANY_QUALIFICATION,
                         RE.METHODOLOGY_REQUIREMENT, RE.SUBMISSION_ARTIFACT,
                         RE.DELIVERABLE_REQUIREMENT} <= types)


if __name__ == "__main__":
    unittest.main()
