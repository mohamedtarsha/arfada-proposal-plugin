"""South Darfur regression (first real Fast Mode run).

Covers the three issues that run exposed:
1. team ranking must search the full PERSISTED staff index (no raw CV transfer);
2. numeric QA must compare only CURRENT methodology counts (not past-project
   statistics, ARFADA portfolio totals, reference values or breakdown rows);
3. the assignment-type classifier must not call a Final / end line evaluation
   BASELINE just because the TOR keeps citing the existing baseline.

Run from the plugin root:
    python -m pytest tests/test_south_darfur_regression.py -v
"""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("ARFADA_HOME", tempfile.mkdtemp(prefix="arfada_sd_home_"))

from tests.fixtures import south_darfur as SD  # noqa: E402


class _Env:
    """Temporarily set/clear environment variables."""

    def __init__(self, **values):
        self.values = values
        self.saved = {}

    def __enter__(self):
        for k, v in self.values.items():
            self.saved[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return self

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _profiles(n_by_country: dict, prefix="cv") -> list:
    out = []
    i = 0
    for country, n in n_by_country.items():
        for _ in range(n):
            i += 1
            out.append({"staff_id": f"{prefix}_{i}", "name": f"Person {i}",
                        "roles": ["Evaluation Specialist"], "years_experience": 10,
                        "source_file_id": f"{prefix}_{i}",
                        "source_rel_path": f"{country}/Senior Evaluation Expert/p{i}/cv.pdf"})
    return out


def _write_index(path: Path, profiles: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"synced_at": "2026-11-21T00:00:00+00:00",
                                "source": {"type": "local_folder"},
                                "count": len(profiles), "profiles": profiles}),
                    encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. staff retrieval uses the persisted index
# ---------------------------------------------------------------------------

class TestPersistedStaffPool(unittest.TestCase):
    FULL = {"Sudan": 290, "Syria": 185, "Afghanistan": 164, "Turkey": 132, "Jordan": 84,
            "Palistin": 79, "Iraq": 77, "International experts": 28, "Lebanon": 26,
            "Libya": 14, "yemen": 3}            # 1,082 profiles, like the live index
    SUBSET = {"Sudan": 208, "International experts": 28}   # 236: the partial transfer

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="arfada_pool_"))
        self.home = self.tmp / "home"
        self.kroot = self.tmp / "ARFADA Knowledge"     # NOTE: no "Staff CVs" folder at all
        self.kroot.mkdir(parents=True)
        self.full = _profiles(self.FULL)
        self.subset = self.full[:0] + _profiles(self.SUBSET, prefix="sub")

    def _knowledge(self):
        from engine.tor.knowledge import Knowledge
        return Knowledge()

    def test_full_portable_index_beats_partial_cache(self):
        from engine.tor.lknowledge.staff_pool import portable_index_path
        _write_index(portable_index_path(self.kroot), self.full)
        _write_index(self.home / "knowledge" / "staff_index.json", self.subset)
        # the user cache must look like a configured local-folder cache
        (self.home / "knowledge" / "projects.json").write_text(json.dumps(
            {"synced_at": "x", "source": {}, "count": 0, "metrics": {}, "projects": []}),
            encoding="utf-8")
        with _Env(ARFADA_HOME=str(self.home), ARFADA_KNOWLEDGE_ROOT=str(self.kroot),
                  ARFADA_STAFF_INDEX=None):
            k = self._knowledge()
            self.assertEqual(k.staff_pool_size, 1082)
            self.assertEqual(k.staff_pool_info["source"], "KNOWLEDGE_FOLDER_INDEX")
            # no raw CV folder exists: nothing had to be transferred or scanned
            self.assertFalse((self.kroot / "Staff CVs").exists())

    def test_team_ranking_searches_full_pool_with_corrected_country(self):
        from engine.tor.autopilot import autopilot
        _write_index(self.home / "knowledge" / "staff_index.json", self.full)
        with _Env(ARFADA_HOME=str(self.home), ARFADA_KNOWLEDGE_ROOT=str(self.kroot),
                  ARFADA_STAFF_INDEX=None):
            k = self._knowledge()
            res = autopilot(SD.TOR, SD.REQUIREMENTS, [], k)
        team = res["team"]
        self.assertEqual(team["searchable_profiles"], 1082)
        self.assertTrue(team["team"])
        self.assertTrue(all(t["country"] == "Sudan" for t in team["team"]))
        self.assertTrue(all(t["source_rel_path"] for t in team["team"]))
        # FAST MODE still asks at most 5 questions
        self.assertLessEqual(res["question_count"], 5)

    def test_old_index_without_country_fields_is_normalized(self):
        legacy = [{k: v for k, v in p.items()} for p in self.full]
        for p in legacy:
            p["country"] = "Senior Evaluation Expert"      # pre-v0.6.7 label
        _write_index(self.home / "knowledge" / "staff_index.json", legacy)
        with _Env(ARFADA_HOME=str(self.home), ARFADA_KNOWLEDGE_ROOT=str(self.kroot),
                  ARFADA_STAFF_INDEX=None):
            k = self._knowledge()
            sudan = k.search_staff(country="Sudan", strict_country=True, limit=5000)
        self.assertEqual(len(sudan), 290)

    def test_partial_cache_never_shrinks_portable_index(self):
        from engine.tor.gknowledge.cache import Cache
        from engine.tor.lknowledge.staff_pool import (portable_index_path,
                                                      publish_portable_index)
        _write_index(portable_index_path(self.kroot), self.full)
        cache = Cache(base=self.tmp / "partial_cache")
        cache.write_staff(self.subset, {"type": "local_folder"})
        res = publish_portable_index(cache, self.kroot)
        self.assertFalse(res["published"])
        doc = json.loads(portable_index_path(self.kroot).read_text(encoding="utf-8"))
        self.assertEqual(len(doc["profiles"]), 1082)

    def test_scan_publishes_portable_index(self):
        from docx import Document
        from engine.tor.gknowledge.cache import Cache
        from engine.tor.lknowledge.scan import scan_staff
        from engine.tor.lknowledge.staff_pool import portable_index_path
        root = self.tmp / "KB"
        f = root / "Staff CVs" / "Sudan" / "Team Leader" / "cv.docx"
        f.parent.mkdir(parents=True)
        d = Document(); d.add_paragraph("Team Leader. 12 years of experience."); d.save(str(f))
        report = {}
        scan_staff(root, Cache(base=self.tmp / "c2"), {"sources": {}}, report)
        self.assertTrue(report["staff"]["portable_index"])
        doc = json.loads(portable_index_path(root).read_text(encoding="utf-8"))
        self.assertEqual(doc["profiles"][0]["country"], "Sudan")

    def test_cv_text_read_only_for_shortlisted(self):
        from docx import Document
        from engine.tor.lknowledge.staff_pool import shortlist_details
        f = self.kroot / "Staff CVs" / "Sudan" / "Senior Evaluation Expert" / "p1" / "cv.pdf"
        f.parent.mkdir(parents=True)
        docx_path = f.with_suffix(".docx")
        d = Document(); d.add_paragraph("FSL specialist, Nyala."); d.save(str(docx_path))
        shortlisted = [dict(self.full[0], source_rel_path=str(
                           docx_path.relative_to(self.kroot / "Staff CVs"))),
                       dict(self.full[1])]          # second CV is not on disk
        out = shortlist_details(shortlisted, knowledge_root=self.kroot)
        self.assertEqual(out[0]["status"], "AVAILABLE")
        self.assertIn("Nyala", out[0]["text"])
        self.assertEqual(out[1]["status"], "FILE_NOT_AVAILABLE_LOCALLY")


# ---------------------------------------------------------------------------
# 2. numeric QA is section- and entity-aware
# ---------------------------------------------------------------------------

def _make_run(sections, register=SD.REGISTER) -> Path:
    d = Path(tempfile.mkdtemp(prefix="arfada_sd_run_"))
    (d / "tor_analysis.json").write_text(json.dumps(SD.TOR), encoding="utf-8")
    (d / "requirements.json").write_text(json.dumps({"requirements": SD.REQUIREMENTS}),
                                         encoding="utf-8")
    (d / "decision_register.json").write_text(
        json.dumps({"run_id": SD.TOR["run_id"], **register}), encoding="utf-8")
    (d / "knowledge_snapshot").mkdir()
    (d / "knowledge_snapshot" / "projects.json").write_text(
        json.dumps({"metrics": SD.SNAPSHOT_METRICS, "projects": []}), encoding="utf-8")
    gs = d / "generated_sections"
    gs.mkdir()
    status = {"sections": {}}
    for sid, cand in sections.items():
        (gs / f"{sid}.json").write_text(json.dumps(cand, ensure_ascii=False), encoding="utf-8")
        status["sections"][sid] = {"status": "READY"}
    (d / "generation_status.json").write_text(json.dumps(status), encoding="utf-8")
    return d


def _numeric_findings(run_dir: Path) -> list:
    from engine.tor.final_qa import run_final_qa
    qa = run_final_qa(run_dir)
    return [f for f in qa["findings"]
            if f["check"] == "CONTRADICTION" or f.get("category") == "decision_conflict"]


class TestNumericQA(unittest.TestCase):
    def test_current_counts_extracted_per_metric(self):
        from engine.tor.numeric_claims import current_claims
        claims = current_claims(SD.SECTIONS, exclude_values={156, 73906, 2721, 1664})
        got = {m: sorted({c.value for c in items}) for m, items in claims.items()}
        self.assertEqual(got["survey"], [250])     # HH survey
        self.assertEqual(got["FGD"], [14])         # incl. breakdown table summing to 14
        self.assertEqual(got["KII"], [19])         # incl. breakdown table summing to 19
        self.assertEqual(got["census"], [40])      # CAC census

    def test_south_darfur_has_no_numeric_false_positives(self):
        self.assertEqual(_numeric_findings(_make_run(SD.SECTIONS)), [])

    def test_no_false_positive_without_decisions(self):
        self.assertEqual(_numeric_findings(_make_run(SD.SECTIONS, {"decisions": []})), [])

    def test_past_experience_numbers_never_compared(self):
        from engine.tor.numeric_claims import current_claims
        claims = current_claims(SD.SECTIONS)
        values = {c.value for items in claims.values() for c in items}
        # past-project scales, team-bio figures and the "4 FGDs with…" sub-group
        for historical in (197, 580, 766, 10, 27, 25, 11, 400, 30, 4):
            self.assertNotIn(historical, values)

    def test_real_current_contradiction_still_caught(self):
        sections = copy.deepcopy(SD.SECTIONS)
        sections["EXECUTIVE_SUMMARY"]["blocks"][0]["text"] = sections[
            "EXECUTIVE_SUMMARY"]["blocks"][0]["text"].replace("250 household", "260 household")
        found = _numeric_findings(_make_run(sections))
        self.assertTrue(any("survey" in f["message"] and "260" in f["message"] for f in found))

    def test_breakdown_that_does_not_sum_is_caught(self):
        sections = copy.deepcopy(SD.SECTIONS)
        table = sections["SAMPLING"]["blocks"][2]
        table["rows"][5][-1] = "3"                 # FGD rows now sum to 13, not 14
        found = _numeric_findings(_make_run(sections))
        self.assertTrue(any("FGD" in f["message"] and "13" in f["message"] for f in found))

    def test_contradiction_without_decision_still_caught(self):
        sections = copy.deepcopy(SD.SECTIONS)
        sections["EXECUTIVE_SUMMARY"]["blocks"][0]["text"] = sections[
            "EXECUTIVE_SUMMARY"]["blocks"][0]["text"].replace("19 KIIs", "21 KIIs")
        found = _numeric_findings(_make_run(sections, {"decisions": []}))
        self.assertTrue(any("KII" in f["message"] for f in found))

    def test_draft_not_blocked_by_numeric_qa(self):
        from engine.tor.blockers import classify_finding
        from engine.tor.final_qa import run_final_qa
        qa = run_final_qa(_make_run(SD.SECTIONS))
        blockers = [f for f in qa["findings"] if classify_finding(f) == "DRAFT_BLOCKER"
                    and f["check"] in ("CONTRADICTION", "DECISION_COMPLIANCE")]
        self.assertEqual(blockers, [])


# ---------------------------------------------------------------------------
# 3. assignment-type classifier
# ---------------------------------------------------------------------------

class TestAssignmentType(unittest.TestCase):
    def _infer(self, metadata, reqs=None):
        from engine.tor.assignment_type import infer_assignment_type
        return infer_assignment_type(metadata, reqs or [], context_aware=True)

    def test_south_darfur_is_endline_high(self):
        r = self._infer(SD.METADATA, SD.REQUIREMENTS)
        self.assertEqual(r.assignment_type, "ENDLINE")
        self.assertEqual(r.confidence, "HIGH")
        self.assertNotEqual(r.assignment_type, "BASELINE")
        self.assertFalse(r.needs_decision)

    def test_genuine_baseline_study_still_baseline(self):
        meta = {"assignment": {"value": "Terms of Reference: Baseline Study for the WASH project"},
                "objectives": {"value": "The consultant will conduct a baseline study to establish "
                               "indicator values before implementation. The baseline survey will "
                               "cover 400 households. The baseline report will set targets."}}
        self.assertEqual(self._infer(meta).assignment_type, "BASELINE")

    def test_final_evaluation_without_baseline_is_evaluation(self):
        meta = {"assignment": {"value": "Final Evaluation of the Protection Programme"},
                "objectives": {"value": "The final evaluation will assess relevance, "
                               "effectiveness and sustainability using OECD-DAC criteria."}}
        self.assertEqual(self._infer(meta).assignment_type, "EVALUATION")

    def test_midline_not_affected(self):
        meta = {"assignment": {"value": "Midline Evaluation of the Livelihoods Project"},
                "objectives": {"value": "The midline evaluation will compare progress against "
                               "the baseline values."}}
        self.assertEqual(self._infer(meta).assignment_type, "MIDLINE")

    def test_legacy_mode_unchanged_for_writing_dna(self):
        """The Writing DNA exemplar scan uses the legacy scoring (no context_aware)."""
        from engine.tor.assignment_type import infer_assignment_type
        r = infer_assignment_type(SD.METADATA, SD.REQUIREMENTS)
        self.assertEqual(r.assignment_type, "BASELINE")   # legacy behaviour, frozen


if __name__ == "__main__":
    unittest.main()
