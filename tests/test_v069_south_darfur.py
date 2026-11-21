"""v0.6.9 regression — fresh South Darfur v0.6.8 Fast Mode test.

1. TOR metadata (title / client / country / subnational location) from the document;
   team ranking and experience retrieval then use Sudan and ZOA automatically.
2. Unresolved TOR-required budget and previous-work items are FINAL submission
   blockers — never draft blockers.
3. Household survey counts ("248 households", "149 + 99 = 248", …) are extracted;
   baseline / caseload / historical / indicator numbers are not.
4. years_experience only when clearly the candidate's own experience.

Run from the plugin root:
    python -m pytest tests/test_v069_south_darfur.py -v
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

os.environ.setdefault("ARFADA_HOME", tempfile.mkdtemp(prefix="arfada_v069_home_"))

from tests.fixtures import south_darfur_tor as SDT  # noqa: E402


def _analyze(variant="table"):
    from scripts.analyze_tor import analyze
    tmp = Path(tempfile.mkdtemp(prefix="arfada_v069_"))
    analyze(SDT.build(tmp / f"ToR_{variant}.docx", variant=variant), output_root=tmp / "out")
    run = next((tmp / "out").iterdir())
    tor = json.loads((run / "tor_analysis.json").read_text(encoding="utf-8"))
    reqs = json.loads((run / "requirements.json").read_text(encoding="utf-8"))["requirements"]
    return run, tor, reqs


def _mv(tor, key):
    return ((tor.get("metadata") or {}).get(key) or {}).get("value", "")


class _Cached:
    _runs: dict = {}

    @classmethod
    def get(cls, variant="table"):
        if variant not in cls._runs:
            cls._runs[variant] = _analyze(variant)
        return cls._runs[variant]


# ---------------------------------------------------------------------------
# 1. metadata extraction
# ---------------------------------------------------------------------------

class TestMetadata(unittest.TestCase):
    def test_south_darfur_metadata_table_variant(self):
        _run, tor, _reqs = _Cached.get("table")
        self.assertEqual(_mv(tor, "assignment"), SDT.TITLE)
        self.assertEqual(_mv(tor, "client"), "ZOA")
        self.assertEqual(_mv(tor, "country"), "Sudan")
        sub = (tor["metadata"].get("subnational_location") or {}).get("values", [])
        self.assertIn("South Darfur", sub)
        self.assertTrue(any(s.startswith("Nyala") for s in sub))
        at = tor["assignment_type"]
        self.assertEqual(at["assignment_type"], "ENDLINE")
        self.assertEqual(at["assignment_type_confidence"], "HIGH")

    def test_south_darfur_metadata_label_variant(self):
        _run, tor, _reqs = _Cached.get("label")
        self.assertEqual(_mv(tor, "assignment"), SDT.TITLE)
        self.assertEqual(_mv(tor, "client"), "ZOA")
        self.assertEqual(_mv(tor, "country"), "Sudan")

    def test_unsupported_metadata_not_inferred(self):
        from engine.tor.tor_metadata import detect_metadata
        blocks = [{"plain_text": t, "block_type": bt} for t, bt in [
            ("Terms of Reference", "TITLE"),
            ("Background", "HEADING"),
            ("The programme is funded by USAID and reaches 4,000 households.", "PARAGRAPH"),
            ("The consultant will review documents.", "PARAGRAPH")]]
        md = detect_metadata(blocks)
        self.assertEqual(md["client"], "")          # a donor is never the client
        self.assertEqual(md["country"], "")
        self.assertEqual(md["project_title"], "")
        self.assertEqual(md["subnational_location"], [])

    def test_south_sudan_is_not_sudan(self):
        from engine.tor.tor_metadata import detect_metadata
        blocks = [{"plain_text": t, "block_type": "PARAGRAPH"} for t in [
            "Final Evaluation of the WASH Project in Juba, South Sudan",
            "Location: Juba, South Sudan", "NRC is seeking a consultant in South Sudan."]]
        md = detect_metadata(blocks)
        self.assertEqual(md["country"], "South Sudan")
        self.assertEqual(md["client"], "NRC")

    def test_team_ranking_uses_extracted_country(self):
        from engine.tor.autopilot import autopilot
        from engine.tor.knowledge import Knowledge
        from engine.tor.lknowledge.staff_country import apply_country
        _run, tor, reqs = _Cached.get("table")
        profiles = []
        for i, c in enumerate(["International experts"] * 4 + ["Sudan"] * 3 + ["Syria"] * 3):
            profiles.append(apply_country({
                "staff_id": f"cv_{i}", "name": f"P{i}", "roles": ["Evaluator", "Team Leader"],
                "years_experience": 15, "evidence": {"years_experience": "15 years of experience"},
                "education": ["MSC"], "languages": ["English"], "extraction_confidence": "MEDIUM",
                "source_file_name": f"P{i} CV.pdf"}, f"{c}/Senior Evaluation Expert/P{i} CV.pdf"))
        k = Knowledge()
        k._live_staff = profiles
        res = autopilot(tor, reqs, [], k)               # no manual country override
        top3 = [m["country"] for m in res["team"]["team"][:3]]
        self.assertEqual(top3, ["Sudan", "Sudan", "Sudan"])
        self.assertLessEqual(res["question_count"], 5)
        from engine.tor.lknowledge.staff_nominate import tor_context
        ctx = tor_context(tor, reqs, "Sudan")
        self.assertTrue({"darfur", "nyala"} & ctx["places"])

    def test_experience_retrieval_uses_sudan_and_zoa(self):
        from engine.tor.autopilot import rank_experience
        from engine.tor.knowledge import Knowledge
        _run, tor, _reqs = _Cached.get("table")
        k = Knowledge()
        k._live_projects = [
            {"project_id": "212-2026-Final Evalu-Sudan-Triangle",
             "project_name": "Final Evaluation, REFRAME emergency food and nutrition response",
             "country": "Sudan", "client": "Triangle - TGH", "assignment_type": "EVALUATION"},
            {"project_id": "134-2024-Evalu-GOS-ZOA", "project_name": "Endline Evaluation, Joint Response",
             "country": "Syria", "client": "ZOA - ZOA", "assignment_type": "EVALUATION"},
            {"project_id": "300-2025-Market-Iraq", "project_name": "Market Assessment",
             "country": "Iraq", "client": "WFP", "assignment_type": "MARKET_ASSESSMENT"},
        ]
        exp = rank_experience(k, tor)
        by_id = {e["project_id"]: e for e in exp}
        self.assertIn("country", by_id["212-2026-Final Evalu-Sudan-Triangle"]["scored_on"])
        self.assertIn("client", by_id["134-2024-Evalu-GOS-ZOA"]["scored_on"])
        self.assertIn("assignment_type", by_id["134-2024-Evalu-GOS-ZOA"]["scored_on"])
        self.assertNotIn("300-2025-Market-Iraq", [e["project_id"] for e in exp[:2]])


# ---------------------------------------------------------------------------
# 2. submission blockers
# ---------------------------------------------------------------------------

class TestSubmissionBlockers(unittest.TestCase):
    def test_budget_and_previous_work_are_final_blockers_only(self):
        from engine.tor.fast_qa import two_status_report
        run, _tor, reqs = _Cached.get("table")
        rep = two_status_report(run)
        final = [b["message"] for b in rep["final_submission_blockers"]]
        self.assertTrue(any(m.startswith("Financial proposal / detailed budget pending")
                            for m in final))
        self.assertTrue(any(m.startswith("Previous-work example pending") for m in final))
        self.assertEqual(rep["submission_package_status"], "NOT_READY")
        for b in rep["draft_blockers"]:
            self.assertNotIn("pending", str(b.get("message", "")).lower())

    def test_resolved_items_are_not_blockers(self):
        from engine.tor.submission_blockers import pending_submission_blockers
        run, _tor, reqs = _Cached.get("table")
        d = Path(tempfile.mkdtemp(prefix="arfada_v069_res_"))
        (d / "budget.json").write_text(json.dumps({"reconciles": True, "missing_inputs": []}),
                                       encoding="utf-8")
        f = d / "annexes" / "previous_work" / "report.pdf"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"%PDF-1.4")
        # v0.6.12: clearance needs explicit permission wording (a flag alone is not enough)
        (d / "previous_work.json").write_text(json.dumps(
            {"file": str(f), "selected": True,
             "clearance": {"status": "VERIFIED", "evidence": "IRC permission confirmed"}}),
            encoding="utf-8")
        # v0.6.10: required registration evidence is tracked too
        reg = d / "annexes" / "registration" / "certificate.pdf"
        reg.parent.mkdir(parents=True)
        reg.write_bytes(b"%PDF-1.4")
        self.assertEqual(pending_submission_blockers(d, reqs), [])
        # clearance missing → still blocked
        (d / "previous_work.json").write_text(json.dumps(
            {"file": str(f), "clearance_confirmed": False}), encoding="utf-8")
        keys = [b["item_key"] for b in pending_submission_blockers(d, reqs)]
        self.assertEqual(keys, ["previous_work"])

    def test_not_required_not_reported(self):
        from engine.tor.submission_blockers import pending_submission_blockers
        reqs = [{"req_id": "X", "category": "submission", "actor": "BIDDER", "mandatory": True,
                 "text": "Technical proposal with methodology."}]
        self.assertEqual(pending_submission_blockers(Path(tempfile.mkdtemp()), reqs), [])

    def test_examples_of_previous_work_identified(self):
        from engine.tor.submission import identify_item
        self.assertEqual(identify_item(
            "Relevant experience: examples of previous baseline surveys or evaluations")[0],
            "previous_work")


# ---------------------------------------------------------------------------
# 3. numeric QA — household survey count
# ---------------------------------------------------------------------------

def _p(t):
    return {"type": "paragraph", "text": t}


SECTIONS = {
    "EXECUTIVE_SUMMARY": {"blocks": [_p(
        "A household survey of 248 households (225 minimum plus a 10% reserve), 14 FGDs, "
        "20 KIIs and a census of all 40 CAC members will be used.")]},
    "UNDERSTANDING": {"blocks": [
        _p("Change will be measured against the July 2026 baseline for the 1,300 households "
           "that received four voucher rounds; the baseline surveyed 243 households."),
        {"type": "table", "columns": ["Indicator", "Baseline", "Target"], "rows": [
            ["Acceptable FCS", "15.8% (205 HH)", "90% (1,170 HH)"],
            ["rCSI 0-3", "0%", "60% (780 HH)"]]}]},
    "SAMPLING": {"blocks": [
        _p("A 10% non-response reserve is added, giving a target of 248 completed household "
           "interviews: 149 FHH + 99 MHH = 248."),
        {"type": "table", "columns": ["Parameter", "Value"], "rows": [
            ["Minimum sample", "225"], ["Baseline sample", "243"], ["Proposed sample", "248"]]},
        {"type": "table", "columns": ["Method", "Group", "Total"], "rows": [
            ["FGD", "Women", "4"], ["FGD", "Men", "4"], ["FGD", "Youth", "4"],
            ["FGD", "Additional caseload", "2"],
            ["KII", "ZOA", "4"], ["KII", "HOPE", "4"], ["KII", "Vendors", "6"],
            ["KII", "Authorities", "3"], ["KII", "Leaders", "3"],
            ["Census survey", "All CAC members", "40"]]}]},
    "DATA_COLLECTION": {"blocks": [_p("248 sampled households of the original caseload.")]},
    "EXPERIENCE": {"blocks": [
        _p("ARFADA's tracker records 156 assignments, 73,906 surveys, 2,721 KIIs and 1,664 FGDs."),
        {"type": "table", "columns": ["Assignment", "Client", "Year", "Scale"],
         "rows": [["Final Evaluation", "IRC", "2026", "580 surveys, 27 KIIs, 11 FGDs"]]}]},
}


class TestHouseholdSurveyCount(unittest.TestCase):
    def test_south_darfur_counts(self):
        from engine.tor.numeric_claims import current_claims
        cl = current_claims(SECTIONS, exclude_values={156, 73906, 2721, 1664})
        got = {m: sorted({c.value for c in items}) for m, items in cl.items()}
        self.assertEqual(got["survey"], [248])
        self.assertEqual(got["FGD"], [14])
        self.assertEqual(got["KII"], [20])
        self.assertEqual(got["census"], [40])

    def test_common_forms(self):
        from engine.tor.numeric_claims import prose_claims
        def survey(t):
            return [c.value for c in prose_claims(t, "SAMPLING") if c.metric == "survey"]
        for t in ("The survey will cover 248 households.", "Enumerators will interview 248 HH.",
                  "The household survey of 248 will use Kobo.", "A survey sample of 248.",
                  "Sample: 149 + 99 = 248 female- and male-headed households."):
            self.assertEqual(survey(t), [248], t)
        for t in ("The baseline sample was 243 households.",
                  "The survey of the original 1,300 households will not be pooled.",
                  "90% (1,170 HH) acceptable FCS in the survey.",
                  "Survey thresholds: FCS 21/35, rCSI 0-3; survey year 2026."):
            self.assertEqual(survey(t), [], t)

    def test_no_false_contradiction(self):
        from engine.tor.final_qa import run_final_qa
        d = Path(tempfile.mkdtemp(prefix="arfada_v069_qa_"))
        (d / "tor_analysis.json").write_text(json.dumps({"run_id": "r", "metadata": {}}))
        (d / "requirements.json").write_text(json.dumps({"requirements": []}))
        (d / "decision_register.json").write_text(json.dumps({"run_id": "r", "decisions": [
            {"decision_id": "dec_sample_size", "question": "household sample", "selected_value": 248,
             "decision_status": "PROVISIONAL_RECOMMENDATION", "minimum": 225},
            {"decision_id": "dec_fgd", "question": "FGDs", "selected_value": 14,
             "decision_status": "PROVISIONAL_RECOMMENDATION"},
            {"decision_id": "dec_kii", "question": "KIIs", "selected_value": 20,
             "decision_status": "PROVISIONAL_RECOMMENDATION"}]}))
        (d / "knowledge_snapshot").mkdir()
        (d / "knowledge_snapshot" / "projects.json").write_text(json.dumps({"metrics": {
            "total_projects": 156, "total_surveys": 73906, "total_kii": 2721, "total_fgd": 1664}}))
        gs = d / "generated_sections"
        gs.mkdir()
        for sid, s in SECTIONS.items():
            (gs / f"{sid}.json").write_text(json.dumps({"section_id": sid, **s}))
        (d / "generation_status.json").write_text(json.dumps(
            {"sections": {s: {"status": "READY"} for s in SECTIONS}}))
        qa = run_final_qa(d)
        hits = [f for f in qa["findings"] if f["check"] == "CONTRADICTION"
                or f.get("category") == "decision_conflict"]
        self.assertEqual(hits, [])


# ---------------------------------------------------------------------------
# 4. years of experience
# ---------------------------------------------------------------------------

class TestYearsOfExperience(unittest.TestCase):
    VALID = [("Team Leader with 30 years of professional experience in evaluation.", 30),
             ("Over 20 years' experience in MEAL across Sudan.", 20),
             ("I have more than 15 years of relevant field experience.", 15),
             ("Professional experience: 12 years", 12),
             ("A 10-year career in humanitarian research.", 10),
             ("Health systems professional with over 12 years in humanitarian programming.", 12)]
    FALSE = ["an NGO that has been working in Tanzania for over 30 years, and has significant "
             "experience in promoting rights",
             "The organisation has 25 years of experience in Darfur.",
             "Founded in 1995, the agency brings 30 years of expertise.",
             "Managed a 5 years project funded by USAID.",
             "Youth aged 18-30 years and children under 5 years.",
             "The programme ran for 12 years in Nyala.",
             "2014 - 2023 Programme Officer, UNDP Nyala",
             "Years within the firm: 21 years"]

    def test_valid_statements(self):
        from engine.tor.gknowledge.normalize import _experience_years
        for text, want in self.VALID:
            self.assertEqual(_experience_years(text)[0], want, text)

    def test_false_positives_are_null(self):
        from engine.tor.gknowledge.normalize import _experience_years
        for text in self.FALSE:
            self.assertIsNone(_experience_years(text)[0], text)

    def test_existing_index_value_revalidated(self):
        from engine.tor.gknowledge.normalize import revalidate_years
        francesco = {"staff_id": "cv_fs", "years_experience": 30, "evidence": {
            "years_experience": "that has been \nworking in Tanzania for over 30 years , and has "
                                "significant experience in promotin"},
            "source_file_id": "cv_fs", "source_rel_path": "Sudan/Senior Evaluation Expert/CV.pdf"}
        out = revalidate_years(francesco)
        self.assertIsNone(out["years_experience"])
        self.assertEqual(out["years_experience_status"], "UNVERIFIED")
        self.assertEqual(out["years_experience_rejected"]["value"], 30)     # provenance kept
        self.assertEqual(out["source_file_id"], "cv_fs")
        good = revalidate_years({"years_experience": 18, "evidence": {
            "years_experience": "an evaluation specialist with 18 years of experience in MEAL"}})
        self.assertEqual(good["years_experience"], 18)
        self.assertEqual(good["years_experience_status"], "VERIFIED")
        self.assertEqual(revalidate_years(out), out)                        # idempotent
        # structured value that never came from CV text parsing: kept, flagged
        structured = revalidate_years({"years_experience": 12})
        self.assertEqual(structured["years_experience"], 12)
        self.assertEqual(structured["years_experience_status"], "NO_EVIDENCE")


if __name__ == "__main__":
    unittest.main()
