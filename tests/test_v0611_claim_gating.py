"""v0.6.11 production hardening — claim state, claim gating, canonical blockers,
final-language sanitizer, semantic QA, TOR source-inconsistency register.

Generic tests first; South Darfur is ONE real-world regression; a second, unrelated
TOR (Iraq WASH baseline, NRC) proves the behaviour is generic.

Optional: ARFADA_REAL_TOR=<original South Darfur PDF> also runs the claim-state
checks on the real document (never committed).

    python -m pytest tests/test_v0611_claim_gating.py -v
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("ARFADA_HOME", tempfile.mkdtemp(prefix="arfada_v0611_home_"))

from engine.tor import claim_language as CL      # noqa: E402
from engine.tor.claim_state import SAFE_WORDING  # noqa: E402


def _state(**statuses):
    return {"claims": {k: {"status": v, "required": True} for k, v in statuses.items()}}


def _issues(text, state):
    return [i.claim for i in CL.find_claim_issues(text, state)]


# ---------------------------------------------------------------------------
# generic claim gating
# ---------------------------------------------------------------------------

class TestClaimGating(unittest.TestCase):
    def test_missing_registration_cannot_be_attached(self):
        st = _state(registration_evidence="MISSING")
        for t in ("Evidence of registration is attached to this proposal.",
                  "ARFADA's registration certificate has been provided.",
                  "Attached is a copy of our registration."):
            self.assertEqual(_issues(t, st), ["registration_evidence"], t)
        # provisional / future wording is allowed
        self.assertEqual(_issues(SAFE_WORDING["registration_evidence"], st), [])
        self.assertEqual(_issues("Evidence of ARFADA's registration will be provided in the "
                                 "submission package.", st), [])
        # 'registered households' is not a registration claim
        self.assertEqual(_issues("The 1,300 registered households form the frame.", st), [])
        # once the file is in the package, the statement is fine
        self.assertEqual(_issues("Evidence of registration is attached.",
                                 _state(registration_evidence="VERIFIED")), [])

    def test_pending_budget_cannot_be_included(self):
        st = _state(financial_proposal="MISSING")
        for t in ("The submission package comprises a technical proposal and a financial proposal.",
                  "The financial proposal is attached.",
                  "Enclosed is the detailed budget."):
            self.assertEqual(_issues(t, st), ["financial_proposal"], t)
        self.assertEqual(_issues(SAFE_WORDING["financial_proposal"], st), [])

    def test_unknown_channel_cannot_be_specified(self):
        st = _state(submission_channel="MISSING")
        for t in ("The proposal is submitted through the channel specified by the client.",
                  "The proposal will be submitted through the channel specified by ZOA before "
                  "the deadline."):
            self.assertEqual(_issues(t, st), ["submission_channel"], t)
        self.assertEqual(_issues(SAFE_WORDING["submission_channel"], st), [])

    def test_unconfirmed_availability(self):
        st = _state(team_availability="UNVERIFIED")
        self.assertEqual(_issues("The proposed experts are available for the assignment.", st),
                         ["team_availability"])
        self.assertEqual(_issues("Availability will be confirmed prior to final submission.", st), [])

    def test_sanitizer_rewrites_deterministically(self):
        st = _state(registration_evidence="MISSING", team_cv_package="MISSING")
        cand = {"section_id": "SUBMISSION", "blocks": [
            {"block_id": "b1", "type": "paragraph",
             "text": "Evidence of registration is attached. CVs of all core team members are "
                     "provided with the proposal."},
            {"block_id": "b2", "type": "table", "columns": ["Item", "Status"],
             "rows": [["Registration", "Evidence of registration is attached."]]}]}
        new, changes, residual = CL.sanitize_candidate(cand, st, section_id="SUBMISSION")
        text = new["blocks"][0]["text"]
        self.assertIn(SAFE_WORDING["registration_evidence"], text)
        self.assertIn(SAFE_WORDING["team_cv_package"], text)
        self.assertNotIn("is attached", text)
        self.assertIn(SAFE_WORDING["registration_evidence"], new["blocks"][1]["rows"][0][1])
        self.assertEqual(residual, [])
        self.assertEqual(cand["blocks"][0]["text"].count("attached"), 1)   # input untouched

    def test_non_rewritable_claim_is_reported(self):
        st = _state(registration_evidence="MISSING")
        _new, _ch, residual = CL.sanitize_candidate(
            {"blocks": [{"type": "paragraph", "text": "ARFADA is a legally registered firm."}]}, st)
        self.assertEqual([r["claim"] for r in residual], ["registration_evidence"])


# ---------------------------------------------------------------------------
# staff evidence gating + field roster
# ---------------------------------------------------------------------------

def _profile(rel, roles=(), snippet="", years=None, **kw):
    from engine.tor.lknowledge.staff_country import apply_country
    from engine.tor.lknowledge.staff_doctype import with_document_type
    p = {"staff_id": "cv_" + str(abs(hash(rel)))[:8], "name": Path(rel).stem,
         "roles": list(roles), "years_experience": years,
         "years_experience_status": "VERIFIED" if years else "NOT_STATED",
         "evidence": {"years_experience": snippet, "education": ""},
         "source_file_name": Path(rel).name, "extraction_confidence": "MEDIUM", **kw}
    return with_document_type(apply_country(p, rel))


class TestStaffEvidence(unittest.TestCase):
    def test_job_title_alone_is_not_expertise(self):
        from engine.tor.lknowledge.staff_evidence import profile_claims
        title_only = _profile("Sudan/Team Leader/Amina Yusuf CV.pdf", roles=["Evaluator"])
        c = profile_claims(title_only)
        self.assertEqual(c["fsl"]["status"], "UNVERIFIED")
        self.assertEqual(c["evaluation"]["status"], "UNVERIFIED")
        self.assertEqual(c["years_experience"]["status"], "UNVERIFIED")
        folder = _profile("Sudan/FSL - food security and livelihood/Amina Yusuf CV.pdf")
        self.assertEqual(profile_claims(folder)["fsl"]["status"], "PROVISIONAL")
        cv_text = _profile("Sudan/X/Amina Yusuf CV.pdf", years=12,
                           snippet="12 years of experience in food security evaluations")
        c3 = profile_claims(cv_text)
        self.assertEqual((c3["fsl"]["status"], c3["evaluation"]["status"],
                          c3["years_experience"]["status"]), ("VERIFIED", "VERIFIED", "VERIFIED"))

    def test_unverified_personnel_claim_rejected(self):
        st = {"claims": {}, "team": [{"name": "Amina Yusuf CV", "claims": {
            "fsl": {"status": "UNVERIFIED"}, "years_experience": {"status": "UNVERIFIED"},
            "gender": {"status": "VERIFIED"}}}]}
        bad = ["Amina Yusuf has extensive food security experience across Darfur.",
               "Amina Yusuf brings 15 years of experience."]
        for t in bad:
            self.assertTrue(CL.find_personnel_issues(t, st), t)
        self.assertEqual(CL.find_personnel_issues("Amina Yusuf has gender expertise.", st), [])
        # validation rejects it, so the writer must repair the section
        from engine.tor.generation import validate_candidate
        packet = {"section_id": "TEAM", "mandatory_slots": [], "applied_decisions": [],
                  "output_contract": {}, "claim_state": st}
        cand = {"section_id": "TEAM", "blocks": [{"block_id": "b1", "type": "paragraph",
                                                  "text": bad[0]}],
                "requirement_response_ledger": []}
        v = validate_candidate(packet, cand)
        self.assertTrue(any(e.startswith("UNVERIFIED_PERSONNEL_CLAIM") for e in v["errors"]))

    def test_weak_roster_cannot_be_definitive(self):
        from engine.tor.lknowledge.staff_evidence import field_roster_readiness
        weak = [_profile(f"Sudan/Field data collectors in sudan/Darfur/E{i} CV.pdf",
                         roles=["Enumerator"]) for i in range(2)]
        weak += [_profile(f"Sudan/Senior Evaluation Expert/X{i} CV.pdf") for i in range(10)]
        r = field_roster_readiness(weak, country="Sudan", places=["Darfur"])
        self.assertNotEqual(r["status"], "VERIFIED")
        st = {"claims": {"field_roster": {"status": r["status"]}}}
        claim = "ARFADA has an established field roster of enumerators in Darfur."
        self.assertEqual(_issues(claim, st), ["field_roster"])
        strong = [_profile(f"Sudan/Field data collectors in sudan/Darfur/E{i} CV.pdf",
                           roles=["Enumerator"]) for i in range(6)]
        r2 = field_roster_readiness(strong, country="Sudan", places=["Darfur"])
        self.assertEqual(r2["status"], "VERIFIED")
        self.assertEqual(_issues(claim, {"claims": {"field_roster": {"status": "VERIFIED"}}}), [])

    def test_ranking_unchanged_except_evidence_gating(self):
        from engine.tor.lknowledge.staff_nominate import nomination_score
        ctx = {"country": "Sudan", "roles": [], "themes": {"FSL"}, "places": set()}
        role_only = _profile("Sudan/Team Leader/A CV.pdf", roles=["Evaluator"])
        folder = _profile("Sudan/Senior Evaluation Expert/B CV.pdf", roles=["Evaluator"])
        _s1, b1 = nomination_score(role_only, ctx)
        _s2, b2 = nomination_score(folder, ctx)
        self.assertNotIn("evaluation", b1)          # job title alone: no credit
        self.assertIn("evaluation", b2)             # evidenced by filing / CV text
        for b in (b1, b2):                          # the other factors are unchanged
            self.assertEqual(b["country"], 30)
            self.assertEqual(b["cv_document"], 15)


# ---------------------------------------------------------------------------
# canonical blockers + TOR source register + semantic QA
# ---------------------------------------------------------------------------

class TestCanonicalBlockers(unittest.TestCase):
    def test_duplicates_collapse_and_final_docx_is_not_a_blocker(self):
        from engine.tor.canonical_blockers import canonicalize
        items = [
            {"check": "SUBMISSION_PENDING", "item_key": "detailed_budget",
             "message": "Financial proposal / detailed budget pending — no budget built"},
            {"message": "Package item missing: Financial offer / detailed budget"},
            {"message": "Proposal claims 'Financial offer / detailed budget' is annexed/attached, "
                        "but no such file exists"},
            {"message": "Package item missing: proposal_final.docx"},
            {"message": "Package item missing: Required CVs"},
            {"message": "Mandatory submission item missing: CV annex (team CVs)"},
            {"message": "Proposal claims 'Required CVs' is annexed/attached, but no such file exists"},
        ]
        out = canonicalize(items, claim_state=_state(registration_evidence="MISSING",
                                                     team_cv_package="MISSING"))
        keys = [b["blocker"] for b in out]
        self.assertEqual(sorted(keys), ["FINANCIAL_PROPOSAL", "REGISTRATION_EVIDENCE",
                                        "TEAM_CV_PACKAGE"])
        self.assertEqual(len(keys), len(set(keys)))
        fin = next(b for b in out if b["blocker"] == "FINANCIAL_PROPOSAL")
        self.assertTrue(fin["message"].startswith("Financial proposal / detailed budget pending"))
        self.assertEqual(len(fin["sources"]), 3)
        self.assertNotIn("EXPORT_STEP", keys)


class TestSourceInconsistency(unittest.TestCase):
    def test_logged_not_corrected(self):
        from engine.tor.source_consistency import scan_text
        text = ("Food consumption score Poor: # 556 and % 42.8 Borderline: # 577 and % 44.4 "
                "Acceptable: # 205 and 15.8 % for the 1,300 households. Hunger scale Little or no "
                "hunger: 0-3 = 23.9% Moderate hunger: 2-3 = 70.8% Severe hunger: 4-6 = 5.3%")
        types = sorted(i["type"] for i in scan_text(text))
        self.assertEqual(types, ["OVERLAPPING_RANGES", "PARTS_EXCEED_TOTAL", "PERCENT_SUM"])
        pct = next(i for i in scan_text(text) if i["type"] == "PERCENT_SUM")
        self.assertEqual(pct["values"], [42.8, 44.4, 15.8])     # reproduced, not fixed
        self.assertIn("42.8", text)

    def test_consistent_figures_not_flagged(self):
        from engine.tor.source_consistency import scan_text
        self.assertEqual(scan_text("Access to water Low: 35%, Medium: 40%, High: 25% of 4,000 "
                                   "households. Bands Low: 0-3, Medium: 4-6, High: 7-9."), [])


class TestSemanticQA(unittest.TestCase):
    def test_impact_label_vs_contribution(self):
        texts = {"METHODOLOGY": "The design uses contribution analysis; there is no causal "
                                "attribution and no counterfactual."}
        issues = CL.find_semantic_issues(texts, labels=["Endline / Impact Evaluation"])
        self.assertEqual([i.kind for i in issues], ["SEMANTIC_IMPACT_VS_CONTRIBUTION"])
        self.assertEqual(CL.rewrite_impact("Endline / Impact Evaluation"), "Endline Evaluation")
        # an impact evaluation with a counterfactual design is not flagged
        self.assertEqual(CL.find_semantic_issues(
            {"M": "A difference-in-differences design estimates causal impact."},
            labels=["Impact Evaluation"]), [])


# ---------------------------------------------------------------------------
# run-level: draft still produced, final NOT_READY, client export gated
# ---------------------------------------------------------------------------

def _analyze(builder, name):
    from scripts.analyze_tor import analyze
    tmp = Path(tempfile.mkdtemp(prefix=f"arfada_v0611_{name}_"))
    analyze(builder(tmp / f"{name}.docx"), output_root=tmp / "out")
    return next((tmp / "out").iterdir())


def _add_sections(run, sections, *, label=None):
    tor = json.loads((run / "tor_analysis.json").read_text(encoding="utf-8"))
    if label:
        tor["assignment_type"]["label"] = label
        (run / "tor_analysis.json").write_text(json.dumps(tor), encoding="utf-8")
    bp = {"run_id": tor["run_id"], "assignment_type": tor["assignment_type"]["assignment_type"],
          "sections": [{"section_id": sid, "title": sid.title(), "sequence": i}
                       for i, sid in enumerate(sections)], "slots": []}
    (run / "proposal_blueprint.json").write_text(json.dumps(bp), encoding="utf-8")
    gs = run / "generated_sections"
    gs.mkdir(exist_ok=True)
    for sid, text in sections.items():
        (gs / f"{sid}.json").write_text(json.dumps({"section_id": sid, "blocks": [
            {"block_id": "b1", "type": "paragraph", "text": text}]}), encoding="utf-8")
    (run / "generation_status.json").write_text(json.dumps(
        {"run_id": tor["run_id"], "sections": {s: {"status": "READY"} for s in sections}}),
        encoding="utf-8")
    return tor, bp


def _docx_text(path):
    from docx import Document
    d = Document(str(path))
    return "\n".join(p.text for p in d.paragraphs)


SD_SECTIONS = {
    "METHODOLOGY": "ARFADA proposes a contribution-focused endline design: contribution analysis "
                   "against the results chain, with no causal attribution.",
    "TEAM": "CVs of all core team members are provided with the proposal.",
    "SUBMISSION": "The proposal will be submitted through the channel specified by ZOA before "
                  "the stated deadline. Evidence of registration is attached.",
}


class TestSouthDarfurRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.fixtures import south_darfur_tor as SDT
        cls.run_dir = _analyze(SDT.build, "south_darfur")
        cls.tor, cls.bp = _add_sections(cls.run_dir, SD_SECTIONS, label="Endline / Impact Evaluation")

    def test_claim_state(self):
        from engine.tor.claim_state import build_claim_state
        c = build_claim_state(self.run_dir)["claims"]
        self.assertEqual(c["financial_proposal"]["status"], "MISSING")
        self.assertEqual(c["previous_work_sample"]["status"], "MISSING")
        self.assertEqual(c["registration_evidence"]["status"], "MISSING")
        self.assertEqual(c["team_cv_package"]["status"], "MISSING")
        self.assertIn(c["submission_channel"]["status"], ("UNVERIFIED", "MISSING"))
        self.assertEqual(c["deadline"]["status"], "PROVISIONAL")     # 12:00 AM is ambiguous

    def test_status_canonical_and_draft_not_blocked_by_package(self):
        from engine.tor.fast_qa import two_status_report
        rep = two_status_report(self.run_dir)
        keys = rep["canonical_blockers"]
        self.assertEqual(len(keys), len(set(keys)))
        for k in ("FINANCIAL_PROPOSAL", "PREVIOUS_WORK_SAMPLE", "REGISTRATION_EVIDENCE",
                  "TEAM_CV_PACKAGE", "SUBMISSION_CHANNEL", "DEADLINE_CONFIRMATION"):
            self.assertIn(k, keys)
        self.assertFalse(any("proposal_final" in b["message"] for b in rep["final_submission_blockers"]))
        self.assertEqual(rep["submission_package_status"], "NOT_READY")
        for b in rep["draft_blockers"]:
            self.assertNotIn(b.get("check"), ("CLAIM_CONSISTENCY", "SEMANTIC_CONSISTENCY",
                                               "SOURCE_INCONSISTENCY", "SUBMISSION_PENDING"))

    def test_qa_findings(self):
        from engine.tor.final_qa import run_final_qa
        f = run_final_qa(self.run_dir)["findings"]
        claims = {x["evidence"] for x in f if x["check"] == "CLAIM_CONSISTENCY"}
        self.assertTrue(any("CVs of all core team" in c for c in claims), claims)
        self.assertTrue(any("submitted through the channel" in c for c in claims), claims)
        self.assertTrue(any(x["check"] == "SEMANTIC_CONSISTENCY" for x in f))

    def test_draft_v1_produced_and_sanitized(self):
        from engine.tor.docx_render import render_docx
        res = render_docx(run_dir=self.run_dir, blueprint=self.bp,
                          status_doc=json.loads((self.run_dir / "generation_status.json").read_text()),
                          tor=self.tor, internal=False, draft_version=1)
        self.assertTrue(Path(res["path"]).exists())
        text = _docx_text(res["path"])
        self.assertNotIn("provided with the proposal", text)
        self.assertNotIn("channel specified by", text)
        self.assertNotIn("Impact Evaluation", text)
        self.assertIn(SAFE_WORDING["team_cv_package"], text)
        self.assertIn(SAFE_WORDING["submission_channel"], text)
        self.assertIn(SAFE_WORDING["registration_evidence"], text)
        self.assertGreaterEqual(len(res["claim_rewrites"]), 4)

    def test_fast_mode_question_cap(self):
        from engine.tor.autopilot import autopilot
        from engine.tor.knowledge import Knowledge
        reqs = json.loads((self.run_dir / "requirements.json").read_text())["requirements"]
        res = autopilot(self.tor, reqs, [], Knowledge())
        self.assertLessEqual(res["question_count"], 5)

    def test_writing_dna_classifier_unchanged(self):
        from engine.tor.assignment_type import infer_assignment_type
        from tests.fixtures import south_darfur as SD
        self.assertEqual(infer_assignment_type(SD.METADATA, SD.REQUIREMENTS).assignment_type,
                         "BASELINE")      # legacy (exemplar-scan) scoring, frozen


class TestSecondTorRegression(unittest.TestCase):
    """Unrelated TOR (Iraq WASH baseline, NRC): explicit e-mail channel, clear deadline,
    no registration requirement, consistent figures."""

    @classmethod
    def setUpClass(cls):
        from tests.fixtures import iraq_wash_tor as IQ
        cls.run_dir = _analyze(IQ.build, "iraq_wash")
        cls.tor, cls.bp = _add_sections(cls.run_dir, {
            "METHODOLOGY": "A household survey will establish baseline values for the logframe.",
            "TEAM": "CVs of the proposed team members are attached.",
            "SUBMISSION": "The proposal will be submitted by e-mail to iq.tenders@nrc.example.org "
                          "before the deadline."})

    def test_claim_state_generic(self):
        from engine.tor.claim_state import build_claim_state
        c = build_claim_state(self.run_dir, today=dt.date(2026, 11, 21))["claims"]
        self.assertEqual(c["submission_channel"]["status"], "VERIFIED")
        self.assertEqual(c["deadline"]["status"], "VERIFIED")
        self.assertEqual(c["registration_evidence"]["status"], "NOT_APPLICABLE")
        self.assertEqual(c["team_cv_package"]["status"], "MISSING")
        self.assertEqual(c["financial_proposal"]["status"], "MISSING")

    def test_no_source_inconsistency(self):
        data = json.loads((self.run_dir / "source_inconsistencies.json").read_text())
        self.assertEqual(data["items"], [])

    def test_only_real_contradictions_flagged(self):
        from engine.tor.final_qa import run_final_qa
        f = [x for x in run_final_qa(self.run_dir)["findings"] if x["check"] in
             ("CLAIM_CONSISTENCY", "SEMANTIC_CONSISTENCY")]
        self.assertEqual(len(f), 1)
        self.assertIn("CVs of the proposed team", f[0]["evidence"])

    def test_client_export_blocks_only_unsafe_residuals(self):
        import shutil
        from engine.tor.docx_render import render_docx
        run = Path(tempfile.mkdtemp(prefix="arfada_v0611_copy_")) / "run"
        shutil.copytree(self.run_dir, run)      # never mutate the shared run
        st = json.loads((run / "generation_status.json").read_text())
        res = render_docx(run_dir=run, blueprint=self.bp, status_doc=st, tor=self.tor,
                          internal=False)                 # client draft: CV claim rewritten
        self.assertNotIn("are attached", _docx_text(res["path"]))
        # a claim with no deterministic rewrite blocks the client export
        p = run / "generated_sections" / "TEAM.json"
        p.write_text(json.dumps({"section_id": "TEAM", "blocks": [
            {"block_id": "b1", "type": "paragraph",
             "text": "ARFADA is a legally registered firm."}]}))
        cs = json.loads((run / "requirements.json").read_text())
        cs["requirements"].append({"req_id": "REG", "category": "submission", "actor": "BIDDER",
                                   "mandatory": True, "text": "Evidence of registration."})
        (run / "requirements.json").write_text(json.dumps(cs))
        with self.assertRaises(ValueError):
            render_docx(run_dir=run, blueprint=self.bp, status_doc=st, tor=self.tor,
                        internal=False)
        # the working draft still renders
        res2 = render_docx(run_dir=run, blueprint=self.bp, status_doc=st, tor=self.tor,
                           internal=False, draft_version=2)
        self.assertTrue(Path(res2["path"]).exists())
        self.assertTrue(res2["claim_residual"])


@unittest.skipUnless(os.environ.get("ARFADA_REAL_TOR"), "set ARFADA_REAL_TOR to the original PDF")
class TestRealSouthDarfurTor(unittest.TestCase):
    def test_real_tor_claim_state_and_register(self):
        from scripts.analyze_tor import analyze
        from engine.tor.claim_state import build_claim_state
        tmp = Path(tempfile.mkdtemp(prefix="arfada_v0611_real_"))
        analyze(Path(os.environ["ARFADA_REAL_TOR"]), output_root=tmp / "out")
        run = next((tmp / "out").iterdir())
        c = build_claim_state(run)["claims"]
        self.assertEqual(c["submission_channel"]["status"], "MISSING")      # placeholder
        self.assertEqual(c["deadline"]["status"], "PROVISIONAL")
        for k in ("financial_proposal", "previous_work_sample", "registration_evidence",
                  "team_cv_package"):
            self.assertEqual(c[k]["status"], "MISSING", k)
        types = {i["type"] for i in json.loads((run / "source_inconsistencies.json").read_text())["items"]}
        self.assertTrue({"PERCENT_SUM", "PARTS_EXCEED_TOTAL", "OVERLAPPING_RANGES"} <= types)


if __name__ == "__main__":
    unittest.main()
