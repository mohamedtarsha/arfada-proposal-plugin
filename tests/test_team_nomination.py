"""Fast Mode team nomination: CV-likeness guard + evidence-based nomination score.

* supporting documents (certificates, declarations, ...) are never auto-nominated,
  even when their text matched role/years keywords;
* the nomination score separates candidates whose base match_score is equal;
* team_needs_question is raised only for close candidates, weak evidence or an
  unconfirmed mandatory eligibility requirement;
* Fast Mode stays within 5 questions.

Run from the plugin root:
    python -m pytest tests/test_team_nomination.py -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("ARFADA_HOME", tempfile.mkdtemp(prefix="arfada_tn_home_"))

from engine.tor.lknowledge.staff_doctype import classify_document  # noqa: E402
from tests.fixtures import south_darfur as SD                      # noqa: E402


def _p(rel, roles=(), years=None, edu=(), langs=(), conf="MEDIUM", sid=None):
    """An indexed staff profile as the scan stores it (country from the top folder)."""
    from engine.tor.lknowledge.staff_country import apply_country
    prof = {"staff_id": sid or "cv_" + str(abs(hash(rel)))[:10], "name": Path(rel).stem,
            "roles": list(roles), "years_experience": years, "education": list(edu),
            "languages": list(langs), "source_file_id": "f_" + str(abs(hash(rel)))[:8],
            "source_file_name": Path(rel).name, "extraction_confidence": conf,
            "evidence": {"years_experience": f"{years} years of experience" if years else "",
                         "education": ""}}
    return apply_country(prof, rel)


def _knowledge(profiles):
    from engine.tor.knowledge import Knowledge
    k = Knowledge()
    k._live_staff = list(profiles)
    k.staff_pool_info = {"source": "TEST", "count": len(profiles), "considered": []}
    return k


def _rank(profiles, reqs=None, country="Sudan"):
    from engine.tor.autopilot import rank_team
    return rank_team(_knowledge(profiles), reqs or SD.REQUIREMENTS, country=country,
                     tor=SD.TOR)


REAL_CV = _p("Sudan/Senior Evaluation Expert/Ahmed Hassan/Ahmed Hassan CV.pdf",
             roles=["Evaluator", "Team Leader"], years=18, edu=["MSC"],
             langs=["Arabic", "English"])
# keyword-matching training certificate: its text yielded roles + years + languages
CERTIFICATE = _p("Sudan/Senior Evaluation Expert/Ali Musa/Training Certificate - Team "
                 "Leadership in Evaluation - Ali Musa.pdf",
                 roles=["Team Leader", "Evaluator", "Consultant"], years=25, edu=["MSC"],
                 langs=["Arabic", "English"], conf="MEDIUM")
DECLARATION = _p("Sudan/INDEPENDENCE AND AVAILABILITY DECLARATION/Omar Saleh.pdf",
                 roles=["Team Leader"], years=20)


class TestCvLikeness(unittest.TestCase):
    def test_document_types(self):
        self.assertEqual(classify_document(REAL_CV)["document_type"], "CV")
        self.assertEqual(classify_document(CERTIFICATE)["document_type"], "SUPPORTING_DOCUMENT")
        self.assertEqual(classify_document(DECLARATION)["document_type"], "SUPPORTING_DOCUMENT")
        for rel in ("Sudan/X/University Degree Diploma.pdf", "Sudan/X/Passport copy.pdf",
                    "Sudan/X/Recommendation Letter - Huda.pdf",
                    "Sudan/Dana certificates/scan_001.pdf", "Sudan/X/شهادة خبرة.pdf"):
            self.assertEqual(classify_document(_p(rel))["document_type"],
                             "SUPPORTING_DOCUMENT", rel)
        # unnamed file with work history is a CV; with nothing parsed it is UNKNOWN
        self.assertEqual(classify_document(_p("Sudan/X/Mir.pdf", roles=["Consultant", "Researcher"],
                                              years=12))["document_type"], "CV")
        self.assertEqual(classify_document(_p("Sudan/X/Learning Route.pdf"))["document_type"],
                         "UNKNOWN")
        # a job title protects a CV that mentions training in its name
        self.assertEqual(classify_document(_p(
            "Afghanistan/X/AHMADI - Education Expert, Training & Capacity Development.pdf",
            roles=["Consultant"], years=10, edu=["MA"]))["document_type"], "CV")

    def test_provenance_preserved(self):
        from engine.tor.lknowledge.staff_doctype import with_document_type
        out = with_document_type(REAL_CV)
        for k in ("source_file_id", "source_rel_path", "source_file_name", "roles",
                  "years_experience", "country", "source_country_folder"):
            self.assertEqual(out[k], REAL_CV[k])

    def test_certificate_with_matching_keywords_cannot_outrank_real_cv(self):
        res = _rank([CERTIFICATE, DECLARATION, REAL_CV])
        ids = [m["staff_id"] for m in res["team"]]
        self.assertEqual(ids[0], REAL_CV["staff_id"])
        self.assertNotIn(CERTIFICATE["staff_id"], ids)
        self.assertNotIn(DECLARATION["staff_id"], ids)

    def test_supporting_documents_stay_searchable(self):
        k = _knowledge([CERTIFICATE, REAL_CV])
        found = k.search_staff(country="Sudan", strict_country=True, limit=10)
        self.assertEqual(len(found), 2)

    def test_unknown_used_only_when_no_cv(self):
        unknown = _p("Sudan/X/Participatory Extension - Kamal.pdf")
        res = _rank([unknown, REAL_CV])
        self.assertEqual([m["staff_id"] for m in res["team"]][0], REAL_CV["staff_id"])
        only_unknown = _rank([unknown, CERTIFICATE])
        self.assertEqual([m["staff_id"] for m in only_unknown["team"]], [unknown["staff_id"]])
        self.assertTrue(only_unknown["team_needs_question"])      # weak evidence

    def test_duplicate_person_files_collapsed(self):
        a = _p("Sudan/Team Leader/Kamal Idris/CV - Kamal Idris.pdf",
               roles=["Team Leader"], years=15)
        b = _p("Sudan/Team Leader/Kamal Idris/Updated CV 2026 - Kamal Idris.pdf",
               roles=["Team Leader"], years=15)
        res = _rank([a, b, REAL_CV])
        paths = [m["source_rel_path"] for m in res["team"]]
        self.assertEqual(sum("Kamal Idris" in p for p in paths), 1)
        self.assertEqual(len(paths), 2)              # Kamal once + Ahmed Hassan


class TestTeamQuestion(unittest.TestCase):
    STRONG = _p("Sudan/FSL - food security and livelihood/Darfur/Salah Ibrahim CV.pdf",
                roles=["Team Leader", "Evaluator", "Researcher"], years=22, edu=["PHD"],
                langs=["Arabic", "English"])
    MEDIUM = _p("Sudan/Field Coordinator/Musa Adam CV.pdf", roles=["Consultant"])
    TEAM_REQ = [{"req_id": "T1", "category": "team", "mandatory": True,
                 "text": "Team Leader with at least 10 years of experience in evaluation."}]

    def test_equal_base_scores_but_clear_best_is_auto_selected(self):
        res = _rank([self.MEDIUM, self.STRONG], reqs=SD.REQUIREMENTS + self.TEAM_REQ)
        team = res["team"]
        self.assertEqual(team[0]["match_score"], team[1]["match_score"])   # same base score
        self.assertEqual(team[0]["staff_id"], self.STRONG["staff_id"])
        self.assertGreater(team[0]["nomination_score"], team[1]["nomination_score"] + 3)
        self.assertFalse(res["team_needs_question"], res["reason"])

    def test_genuinely_close_candidates_ask(self):
        twin = _p("Sudan/FSL - food security and livelihood/Darfur/Huda Osman CV.pdf",
                  roles=["Team Leader", "Evaluator", "Researcher"], years=22, edu=["PHD"],
                  langs=["Arabic", "English"])
        res = _rank([self.STRONG, twin], reqs=SD.REQUIREMENTS + self.TEAM_REQ)
        self.assertTrue(res["team_needs_question"])
        self.assertIn("closely ranked", res["reason"])

    def test_mandatory_eligibility_ambiguity_asks(self):
        strict = [{"req_id": "T1", "category": "team", "mandatory": True,
                   "text": "Team Leader with at least 25 years of experience."}]
        res = _rank([self.MEDIUM, self.STRONG], reqs=SD.REQUIREMENTS + strict)
        self.assertTrue(res["team_needs_question"])
        self.assertIn("Mandatory requirement", res["reason"])
        # years not evidenced at all → cannot be confirmed → ask
        no_years = dict(self.STRONG, years_experience=None,
                        evidence={"years_experience": "", "education": ""})
        res2 = _rank([self.MEDIUM, no_years], reqs=SD.REQUIREMENTS + self.TEAM_REQ)
        self.assertTrue(res2["team_needs_question"])

    def test_fast_mode_question_limit(self):
        from engine.tor.autopilot import autopilot
        tor = {"run_id": "r", "metadata": SD.METADATA,
               "assignment_type": {"assignment_type": "EVALUATION",
                                   "assignment_type_confidence": "LOW"}}
        reqs = SD.REQUIREMENTS + self.TEAM_REQ + [
            {"req_id": "B1", "category": "submission", "text": "Detailed financial budget."},
            {"req_id": "P1", "category": "submission",
             "text": "Provide an example of previous evaluation work."}]
        twin = dict(self.STRONG, staff_id="cv_twin", source_file_name="Huda Osman CV.pdf",
                    source_rel_path="Sudan/FSL - food security and livelihood/Darfur/Huda Osman CV.pdf")
        res = autopilot(tor, reqs, [], _knowledge([self.STRONG, twin]))
        self.assertLessEqual(res["question_count"], 5)
        self.assertEqual(res["question_count"], len(res["questions"]))
        self.assertIn("team_lead_choice", [q["key"] for q in res["questions"]])
        # and no team question when the best candidate is clear
        res_clear = autopilot(tor, reqs, [], _knowledge([self.STRONG, self.MEDIUM]))
        self.assertNotIn("team_lead_choice", [q["key"] for q in res_clear["questions"]])
        self.assertLessEqual(res_clear["question_count"], 5)


if __name__ == "__main__":
    unittest.main()
