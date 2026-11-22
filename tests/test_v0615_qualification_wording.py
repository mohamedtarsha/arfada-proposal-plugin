"""v0.6.15 regression — confirmed fresh v0.6.14 South Darfur run.

1. client-facing qualification claims never stronger than EVIDENCE_STATUS /
   QUALIFICATION_READINESS (no blanket "met by the team collectively"; a methodological
   commitment is never shown as prior personnel experience; no internal labels);
2. table-column-aware source semantics (Baseline column → OBSERVED_BASELINE, Target
   column → TARGET; nearby target language never decides a table value).

    python -m pytest tests/test_v0615_qualification_wording.py -v
Optional: ARFADA_REAL_TOR=<original South Darfur PDF> runs the real-table checks.
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

os.environ.setdefault("ARFADA_HOME", tempfile.mkdtemp(prefix="arfada_v0615_home_"))

from engine.tor import requirement_evidence as RE  # noqa: E402
from engine.tor import qualification_wording as QW  # noqa: E402
from engine.tor import source_semantics as SS  # noqa: E402

SADD = {"req_id": "r_sadd", "category": "team", "mandatory": True, "actor": "BIDDER",
        "text": "Ability to collect and analyse Sex, Age, and Disability Disaggregated Data."}
CHS = {"req_id": "r_chs", "category": "team", "mandatory": True, "actor": "BIDDER",
       "text": "Strong understanding of Core Humanitarian Standards (CHS), Sphere Standards, and "
               "safeguarding principles."}
CLUSTER = {"req_id": "r_cl", "category": "team", "mandatory": True, "actor": "BIDDER",
           "text": "Technical expertise in survey design and analysis, including cluster sampling, "
                   "and random sampling."}
MIXED = {"req_id": "r_mm", "category": "team", "mandatory": True, "actor": "BIDDER",
         "text": "Expertise in designing and implementing mixed-methods evaluations and data "
                 "triangulation."}


def _member(sid, role, text):
    prof = {"staff_id": sid, "evidence": {"summary": text}}
    return {"staff_id": sid, "staff_profile_id": sid, "canonical_name": sid.title(), "role": role,
            "claims": {"years_experience": {"status": "UNVERIFIED", "value": None}},
            "qualification_evidence": RE.member_topic_evidence(prof)}


TEAM = [_member("g", "Gender, Protection & Safeguarding Specialist",
                "CHS-aligned case handling; safeguarding and PSEA training of 500+ staff."),
        _member("d", "Data Analyst / Statistician",
                "Designed sampling methodologies for baselines; mixed-methods research and "
                "triangulation across surveys, FGDs and KIIs.")]


def _state(reqs=(SADD, CHS, CLUSTER, MIXED), team=TEAM):
    return {"claims": {}, "places": ["South Darfur"],
            "requirement_evidence": RE.evidence_matrix(list(reqs), team)}


INTRO_PARA = {"block_id": "b83", "type": "paragraph",
              "text": "The TOR’s qualification requirements can be met by the team collectively. "
                      "The table below shows how each requirement is covered and separates what "
                      "the CVs show from what the evaluation design commits to."}
QUAL_TABLE = {"block_id": "b84", "type": "table",
              "columns": ["TOR qualification", "How the team covers it"],
              "rows": [
                  ["Survey design and analysis, including cluster sampling and random sampling",
                   "Data Analyst: sampling design for baselines, PDM and final evaluations. This "
                   "evaluation uses stratified systematic random sampling; if a cluster design is "
                   "chosen at inception, it will be applied with a design effect."],
                  ["Collection and analysis of sex-, age- and disability-disaggregated data",
                   "Applied in the design: every household record captures sex and age of household "
                   "members and disability using the Washington Group short set."],
                  ["Understanding of CHS, Sphere Standards and safeguarding principles",
                   "Gender, Protection & Safeguarding Specialist: CHS-aligned case handling and "
                   "safeguarding and PSEA training. Sphere minimum standards will be used in the "
                   "design as a reference."],
                  ["Mixed-methods evaluations and data triangulation",
                   "Data Analyst (mixed-methods research, triangulation across surveys, FGDs and KIIs)."]]}
CAND = {"section_id": "TEAM", "blocks": [INTRO_PARA, QUAL_TABLE]}


class TestEvidenceStates(unittest.TestCase):
    def test_states_match_the_run(self):
        rows = {r["req_id"]: r for r in QW.qualification_rows(_state())}
        self.assertEqual((rows["r_sadd"]["evidence_status"], rows["r_sadd"]["qualification_readiness"]),
                         (RE.EV_GAP, RE.AT_RISK))
        self.assertEqual(rows["r_chs"]["evidence_status"], RE.EV_PARTIAL)
        self.assertEqual(rows["r_chs"]["not_evidenced"], ["sphere"])
        self.assertEqual(rows["r_cl"]["evidence_status"], RE.EV_PARTIAL)
        self.assertEqual(rows["r_mm"]["evidence_status"], RE.EV_VERIFIED)


class TestClientWording(unittest.TestCase):
    def setUp(self):
        self.new, self.changes, self.residual = QW.sanitize_qualifications(CAND, _state(), section_id="TEAM")
        self.rows = {r[0][:12]: r[1] for r in self.new["blocks"][1]["rows"]}

    def test_no_blanket_claim(self):
        text = self.new["blocks"][0]["text"]
        self.assertNotIn("met by the team collectively", text)
        self.assertNotIn("is covered", text)
        self.assertEqual(text, "The table below shows how each requirement is addressed and separates "
                               "what the CVs show from what the evaluation design commits to.")

    def test_neutral_intro_when_no_table_sentence(self):
        cand = {"blocks": [{"type": "paragraph", "text": "The TOR’s qualification requirements can "
                                                         "be met by the team collectively."}]}
        new, _c, _r = QW.sanitize_qualifications(cand, _state())
        self.assertEqual(new["blocks"][0]["text"], QW.INTRO)

    def test_header_is_neutral(self):
        self.assertEqual(self.new["blocks"][1]["columns"][1], QW.TABLE_HEADER)

    def test_sadd_is_a_methodological_provision_not_experience(self):
        sadd = self.rows["Collection a"]
        self.assertTrue(sadd.startswith("Methodological provision: Every household record"))
        self.assertNotIn("Applied in the design", sadd)

    def test_sphere_and_cluster_partial(self):
        chs = self.rows["Understandin"]
        self.assertIn("Specialist: CHS-aligned case handling", chs)          # evidenced part kept
        self.assertIn("Methodological provision: Sphere minimum standards", chs)
        cl = self.rows["Survey desig"]
        self.assertTrue(cl.startswith("Data Analyst: sampling design"))       # evidenced part kept
        self.assertIn("Methodological provision: This evaluation uses stratified", cl)

    def test_verified_row_untouched(self):
        self.assertEqual(self.rows["Mixed-method"], QUAL_TABLE["rows"][3][1])

    def test_source_untouched_and_idempotent(self):
        self.assertEqual(CAND["blocks"][1]["columns"][1], "How the team covers it")
        again, changes, _r = QW.sanitize_qualifications(self.new, _state())
        self.assertEqual(changes, [])
        self.assertEqual(again, self.new)

    def test_all_verified_needs_no_rewrite(self):
        _n, changes, _r = QW.sanitize_qualifications(CAND, _state(reqs=(MIXED,)))
        self.assertEqual(changes, [])

    def test_attribution_of_unevidenced_element_is_residual(self):
        cand = {"blocks": [{"type": "table", "columns": ["TOR qualification", "Team"],
                            "rows": [["Collection and analysis of sex-, age- and disability-"
                                      "disaggregated data",
                                      "Data Analyst: extensive experience of disaggregated SADD "
                                      "analysis."]]}]}
        _n, _c, residual = QW.sanitize_qualifications(cand, _state())
        self.assertEqual([r["kind"] for r in residual], ["UNEVIDENCED_PERSONNEL_CLAIM"])

    def test_non_qualification_tables_untouched(self):
        for cols in (["Ethical requirement", "How ARFADA will apply it"],
                     ["TOR submission requirement", "Where it is addressed / status"]):
            cand = {"blocks": [{"type": "table", "columns": cols, "rows": [
                ["Impartial analysis and reporting", "Findings reported as evidenced, including "
                                                     "negative results; neutral question wording."]]}]}
            _n, changes, _r = QW.sanitize_qualifications(cand, _state(reqs=(SADD, CHS, CLUSTER, {
                "req_id": "r_neu", "category": "team", "mandatory": True, "actor": "BIDDER",
                "text": "Neutrality and cultural sensitivity to navigate ethnic tensions."})))
            self.assertEqual(changes, [], cols)
        # a v0.6.12-style "Requirement in the TOR | How the team will meet it" table is one
        self.assertTrue(QW._is_qualification_table(["Requirement in the TOR", "How the team will meet it"]))

    def test_internal_labels_flagged(self):
        cand = {"blocks": [{"type": "paragraph", "text": "SADD is AT_RISK for this team."}]}
        kinds = [i["kind"] for i in QW.find_qualification_issues(cand, _state())]
        self.assertIn("INTERNAL_LABEL_IN_CLIENT_TEXT", kinds)

    def test_wired_into_final_language_sanitizer(self):
        from engine.tor.claim_language import sanitize_candidate
        new, changes, _res = sanitize_candidate(CAND, _state(), section_id="TEAM")
        self.assertEqual(new["blocks"][1]["columns"][1], QW.TABLE_HEADER)
        self.assertTrue(any(c["kind"] == "COMMITMENT_AS_QUALIFICATION" for c in changes))

    def test_generation_policy(self):
        from engine.tor.claim_state import generation_policy
        pol = generation_policy(_state())["qualification_rendering"]
        rules = {q["req_id"]: q for q in pol["qualifications"]}
        self.assertIn("Never say the team demonstrates", rules["r_sadd"]["client_rule"])
        self.assertIn("evidenced portion", rules["r_chs"]["client_rule"])
        self.assertEqual(rules["r_chs"]["not_evidenced"], ["Sphere Standards"])
        self.assertEqual(pol["intro_wording"], QW.INTRO)


class TestQa(unittest.TestCase):
    def test_qa_reports_overclaims(self):
        from engine.tor.final_qa import run_final_qa
        d = Path(tempfile.mkdtemp(prefix="arfada_v0615_qa_"))
        (d / "tor_analysis.json").write_text(json.dumps({"run_id": "r", "metadata": {
            "country": {"value": "Sudan"}, "subnational_location": {"values": ["South Darfur"]}}}))
        (d / "requirements.json").write_text(json.dumps({"requirements": [SADD, CHS, CLUSTER, MIXED]}))
        (d / "proposed_setup.json").write_text(json.dumps({"team": [
            {"staff_id": "g", "role": "Gender, Protection & Safeguarding Specialist",
             "evidence": {"s": "CHS-aligned case handling; safeguarding and PSEA training."}},
            {"staff_id": "d", "role": "Data Analyst / Statistician",
             "evidence": {"s": "Designed sampling methodologies for baselines; mixed-methods "
                               "research and triangulation across surveys."}}]}))
        gs = d / "generated_sections"
        gs.mkdir()
        (gs / "TEAM.json").write_text(json.dumps({**CAND, "requirement_response_ledger": [
            {"requirement_id": r["req_id"], "block_ids": ["b84"], "status": "ADDRESSED"}
            for r in (SADD, CHS, CLUSTER, MIXED)]}))
        (d / "generation_status.json").write_text(json.dumps({"sections": {"TEAM": {"status": "READY"}}}))
        qa = run_final_qa(d)
        kinds = sorted({f["category"] for f in qa["findings"] if f["check"] == "QUALIFICATION_CLAIM"})
        self.assertEqual(kinds, ["blanket_qualification_claim", "commitment_as_qualification",
                                 "qualification_table_header"])
        self.assertEqual(qa["summary"]["content_coverage"]["addressed"], 4)   # unchanged


class TestTableSemantics(unittest.TestCase):
    def test_cell_tables(self):
        table = {"rows": [["Indicator", "Baseline", "Target"],
                          ["Reduced coping strategy index", "508 HHs, 39.1%\n685 HHs, 52.7%\n20 HHs, 8.2%",
                           "60% =780 HH of all households (468 FHH, and 312 MHH)"]]}
        m = {(x["value"], x["label"]): x["semantics"] for x in SS.cell_table_mentions([table])}
        for v in (508, 685, 20):
            self.assertEqual(m[(v, "households")], SS.OBSERVED_BASELINE, v)
        self.assertEqual(m[(780, "households")], SS.TARGET)
        self.assertEqual((m[(468, "FHH")], m[(312, "MHH")]), (SS.TARGET, SS.TARGET))

    def test_table_column_overrides_nearby_target_language(self):
        text = "Target (468 FHH, and 312 MHH) 508 HHs, 39.1% planned targets"
        table = {"rows": [["Indicator", "Baseline", "Target"], ["rCSI", "508 HHs, 39.1%", "312 MHH"]]}
        reg = SS.build_register(text, table_mentions=SS.cell_table_mentions([table]))
        f = {x["value"]: x for x in reg["figures"]}
        self.assertEqual(f[508]["semantics"], [SS.OBSERVED_BASELINE])

    def test_no_table_keeps_text_cues(self):
        reg = SS.build_register("In the baseline the proposed target number of HHs was 243.")
        self.assertEqual({x["value"]: x["semantics"] for x in reg["figures"]}[243], [SS.OBSERVED_BASELINE])


@unittest.skipUnless(os.environ.get("ARFADA_REAL_TOR"), "set ARFADA_REAL_TOR to the original PDF")
class TestRealSouthDarfurTable(unittest.TestCase):
    def test_rcsi_columns(self):
        from scripts.analyze_tor import analyze
        tmp = Path(tempfile.mkdtemp(prefix="arfada_v0615_real_"))
        analyze(Path(os.environ["ARFADA_REAL_TOR"]), output_root=tmp / "out")
        run = next((tmp / "out").iterdir())
        f = {x["value"]: x for x in json.loads((run / SS.SEMANTICS_FILE).read_text(encoding="utf-8"))["figures"]}
        for v in (508, 685, 20):
            self.assertEqual(f[v]["semantics"], [SS.OBSERVED_BASELINE], v)
        for v in (780, 468, 312, 1170, 520):
            self.assertEqual(f[v]["semantics"], [SS.TARGET], v)
        self.assertEqual(f[243]["semantics"], [SS.OBSERVED_BASELINE])
        self.assertTrue(f[1300]["registered_supported"])           # "selected and verified"
        incon = json.loads((run / "source_inconsistencies.json").read_text(encoding="utf-8"))["items"]
        self.assertTrue(incon)                                     # TOR figures not "fixed"


if __name__ == "__main__":
    unittest.main()
