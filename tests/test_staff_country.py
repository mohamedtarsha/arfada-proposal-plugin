"""Regression: staff-CV country attribution with nested folders.

The country of a CV must come from the FIRST folder below "Staff CVs", however
deeply the file is nested — never from a role or person subfolder. Run from the
plugin root:
    python -m pytest tests/test_staff_country.py -v
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

os.environ.setdefault("ARFADA_HOME", tempfile.mkdtemp(prefix="arfada_sc_home_"))

from engine.tor.lknowledge import staff_country as SC  # noqa: E402


def _cv(path: Path, text: str) -> None:
    from docx import Document
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    doc.save(str(path))


_CV_TEXT = ("Team Leader and Evaluation Specialist\n"
            "Master of Public Health. 12 years of experience in evaluation.\n"
            "Languages: Arabic, English")

# (relative path under Staff CVs, expected country, expected pool)
_LAYOUT = [
    ("Sudan/Senior Evaluation Expert/Ahmed/cv.docx", "Sudan", ""),
    ("Sudan/Team Leader/cv2.docx", "Sudan", ""),
    ("Jordan/MEAL/cv.docx", "Jordan", ""),
    ("Jordan/cv_flat.docx", "Jordan", ""),
    ("Syria/Protection/Basel Habib/deep/er/cv.docx", "Syria", ""),
    ("Palistin/Field data collectors/cv.docx", "Palestine", ""),
    ("Turkey/Gaziantep/cv.docx", "Turkey", ""),
    ("yemen/cv.docx", "Yemen", ""),
    ("International experts/Evaluation/cv.docx", "", "International Experts"),
]


class TestAttributionRule(unittest.TestCase):
    def test_first_folder_wins_regardless_of_depth(self):
        for rel, country, pool in _LAYOUT:
            a = SC.attribute_country(rel)
            self.assertEqual(a["country"], country, rel)
            self.assertEqual(a["country_pool"], pool, rel)
            self.assertEqual(a["source_country_folder"], rel.split("/")[0], rel)

    def test_windows_separators(self):
        a = SC.attribute_country(r"Sudan\Senior Evaluation Expert\Ahmed\cv.pdf")
        self.assertEqual(a["country"], "Sudan")

    def test_role_or_person_folder_never_becomes_country(self):
        for rel in ("Senior Evaluation Expert/cv.pdf", "Ahmed Barbour/cv.pdf"):
            a = SC.attribute_country(rel)
            self.assertEqual(a["country"], "")
            self.assertEqual(a["country_status"], "UNRECOGNIZED_FOLDER")

    def test_pool_does_not_invent_country(self):
        a = SC.attribute_country("International Experts/Evaluation/cv.pdf")
        self.assertEqual(a["country"], "")
        self.assertEqual(a["country_pool"], "International Experts")
        self.assertEqual(a["country_status"], "POOL")

    def test_file_directly_in_staff_cvs(self):
        a = SC.attribute_country("loose_cv.pdf")
        self.assertEqual(a["country_status"], "NO_FOLDER")
        self.assertEqual(a["country"], "")

    def test_canonical_names_follow_master_tracker(self):
        self.assertEqual(SC.canonical_country("Türkiye"), "Turkey")
        self.assertEqual(SC.canonical_country("palistin"), "Palestine")
        self.assertEqual(SC.canonical_country("Senior Evaluation Expert"), "")


class TestScanAndRetrieval(unittest.TestCase):
    """End-to-end: nested folders → scan → staff index → search/rank."""

    @classmethod
    def setUpClass(cls):
        from engine.tor.gknowledge.cache import Cache
        from engine.tor.lknowledge.scan import scan_staff
        cls.tmp = tempfile.mkdtemp(prefix="arfada_sc_")
        root = Path(cls.tmp) / "ARFADA Knowledge"
        for rel, _c, _p in _LAYOUT:
            _cv(root / "Staff CVs" / rel, _CV_TEXT)
        cls.cache = Cache(base=Path(cls.tmp) / "cache")
        cls.state = {"sources": {}}
        cls.report = {}
        scan_staff(root, cls.cache, cls.state, cls.report)
        cls.root = root
        cls.profiles = cls.cache.staff()["profiles"]

    def _knowledge(self, profiles=None):
        from engine.tor.knowledge import Knowledge
        k = Knowledge()
        k._live_staff = list(profiles if profiles is not None else self.profiles)
        return k

    def test_scan_assigns_top_folder_country(self):
        by_rel = {p["source_rel_path"].replace("\\", "/"): p for p in self.profiles}
        self.assertEqual(len(by_rel), len(_LAYOUT))
        for rel, country, pool in _LAYOUT:
            p = by_rel[rel]
            self.assertEqual(p["country"], country, rel)
            self.assertEqual(p["country_pool"], pool, rel)
            # parsed facts + provenance preserved
            self.assertTrue(p["source_file_id"].startswith("cv_"))
            self.assertEqual(p["source_file_name"], Path(rel).name)

    def test_unchanged_rescan_reattributes_without_reparse(self):
        """A stale (old-rule) cached profile is corrected on rescan, not re-parsed."""
        from engine.tor.lknowledge.scan import scan_staff
        # marker: survives only if not re-parsed (roles; years are re-checked in v0.6.9)
        stale = [{**p, "country": Path(p["source_rel_path"]).parent.name,
                  "roles": ["Marker Role"]}
                 for p in self.profiles]
        stale = [{k: v for k, v in p.items()
                  if k not in ("country_pool", "country_status", "source_country_folder")}
                 for p in stale]
        self.cache.write_staff(stale, {"type": "local_folder"})
        report = {}
        scan_staff(self.root, self.cache, self.state, report)
        self.assertEqual(report["staff"]["unchanged"], len(_LAYOUT))
        self.assertEqual(report["staff"]["added"], 0)
        for p in self.cache.staff()["profiles"]:
            self.assertEqual(p["roles"], ["Marker Role"])  # cached facts kept
        got = {p["source_rel_path"].replace("\\", "/"): p["country"]
               for p in self.cache.staff()["profiles"]}
        self.assertEqual(got["Sudan/Senior Evaluation Expert/Ahmed/cv.docx"], "Sudan")
        # restore for the other tests
        self.cache.write_staff(self.profiles, {"type": "local_folder"})

    def test_repair_staff_index_fixes_old_labels(self):
        from engine.tor.gknowledge.cache import Cache
        c = Cache(base=Path(self.tmp) / "repair_cache")
        stale = [{"staff_id": "cv_x", "name": "X", "country": "Senior Evaluation Expert",
                  "source_file_id": "cv_x", "source_rel_path":
                  "Sudan/Senior Evaluation Expert/Ahmed/cv.pdf", "roles": ["Team Leader"]}]
        res = SC.repair_staff_index(c)
        self.assertEqual(res["profiles"], 0)  # empty cache is a no-op
        c.write_staff(stale, {"type": "local_folder"})
        res = SC.repair_staff_index(c)
        self.assertEqual(res["changed"], 1)
        p = c.staff()["profiles"][0]
        self.assertEqual(p["country"], "Sudan")
        self.assertEqual(p["roles"], ["Team Leader"])
        self.assertEqual(p["source_rel_path"], "Sudan/Senior Evaluation Expert/Ahmed/cv.pdf")

    def test_country_filtered_search(self):
        k = self._knowledge()
        for query, expected in (("Sudan", 2), ("Jordan", 2), ("Syria", 1),
                                ("Palestine", 1), ("Türkiye", 1),
                                ("International Experts", 1)):
            res = k.search_staff(country=query, strict_country=True, limit=50)
            self.assertEqual(len(res), expected, query)
            for r in res:
                self.assertTrue(SC.matches_country(r, query), query)

    def test_role_folder_query_matches_nothing(self):
        k = self._knowledge()
        self.assertEqual(
            k.search_staff(country="Senior Evaluation Expert", strict_country=True), [])

    def test_fast_mode_team_ranking_uses_corrected_country(self):
        from engine.tor.autopilot import rank_team
        k = self._knowledge()
        team = rank_team(k, [], country="Sudan", limit=6)["team"]
        self.assertTrue(team)
        self.assertEqual(team[0]["country"], "Sudan")
        self.assertEqual(team[1]["country"], "Sudan")
        # in-country candidates rank above everyone else
        sudan = [t for t in team if t["country"] == "Sudan"]
        self.assertEqual(team[:len(sudan)], sudan)


if __name__ == "__main__":
    unittest.main()
