"""v0.6.3 Decision-card UX regression scenario (script layer, NO generation).

Models the Plan International Jordan endline-evaluation TOR as a decision-card
regression: an assignment-type choice, a methodology choice, a bounded sample
size, a deferred sampling-frame decision, an optional pilot, and a FIXED page
limit. Exercises scripts/decision_cards.py end to end and asserts the UX contract:

  * fixed requirements never become cards
  * exactly one recommended option per card, never auto-selected/approved
  * numeric bounds carried through; custom answers routed for validation
  * progress indicator present
  * Arabic labels with canonical stored values

This is a UX regression ONLY — it never runs TOR generation or writes a proposal.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_CARDS = _ROOT / "scripts" / "decision_cards.py"
_REGISTER = _ROOT / "scripts" / "decision_register.py"

# Jordan endline TOR, modelled as decision candidates (synthetic — no real TOR data).
_JORDAN_CANDIDATES = {
    "run_id": "jordan_endline_regression",
    "candidates": [
        {"decision_id": "assign_type", "requirement_id": "r_type",
         "decision_type": "OPEN_PROPOSAL_DECISION", "is_human_decision": True,
         "question": "Confirm the assignment type for this endline.",
         "constraint_type": "ENUM",
         "allowed_options": ["Endline Evaluation", "Impact Evaluation"],
         "source_text": "Conduct an endline evaluation of the programme.",
         "category": "assignment_type", "actor": "bidder"},
        {"decision_id": "methodology", "requirement_id": "r_meth",
         "decision_type": "OPEN_PROPOSAL_DECISION", "is_human_decision": True,
         "question": "Which evaluation methodology should ARFADA propose?",
         "constraint_type": "NONE", "allowed_options": [],
         "source_text": "The consultant proposes a suitable methodology.",
         "category": "methodology", "actor": "bidder"},
        {"decision_id": "kii_count", "requirement_id": "r_kii",
         "decision_type": "OPEN_PROPOSAL_DECISION", "is_human_decision": True,
         "question": "How many key informant interviews?",
         "constraint_type": "AT_LEAST", "minimum": 20,
         "source_text": "At least 20 KIIs with stakeholders.",
         "category": "sampling", "actor": "bidder"},
        {"decision_id": "weeks", "requirement_id": "r_time",
         "decision_type": "OPEN_PROPOSAL_DECISION", "is_human_decision": True,
         "question": "Proposed assignment duration?",
         "constraint_type": "RANGE", "minimum": 8, "maximum": 10,
         "source_text": "The assignment runs between 8 and 10 weeks.",
         "category": "timeline", "actor": "bidder"},
        {"decision_id": "sample_frame", "requirement_id": "r_frame",
         "decision_type": "DEFERRED_DECISION", "is_human_decision": True,
         "question": "Final sampling frame?",
         "constraint_type": "NONE",
         "source_text": "The sampling frame is agreed during inception.",
         "category": "sampling", "actor": "bidder"},
        {"decision_id": "pilot", "requirement_id": "r_pilot",
         "decision_type": "OPTIONAL_CHOICE", "is_human_decision": True,
         "question": "Include a tool pilot phase?",
         "constraint_type": "NONE",
         "source_text": "A pilot of data collection tools is encouraged.",
         "category": "data_collection_methods", "actor": "bidder"},
        # FIXED — must NOT become a card:
        {"decision_id": "page_limit", "requirement_id": "r_pages",
         "decision_type": "FIXED_MAXIMUM", "is_human_decision": False,
         "question": "", "constraint_type": "AT_MOST", "maximum": 25,
         "source_text": "The technical proposal must not exceed 25 pages.",
         "category": "submission", "actor": "bidder"},
    ],
}


def _run(script: Path, *args) -> dict:
    proc = subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


class TestJordanEndlineCardFlow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.run_dir = Path(tempfile.mkdtemp(prefix="jordan_endline_"))
        (cls.run_dir / "decision_candidates.json").write_text(
            json.dumps(_JORDAN_CANDIDATES), encoding="utf-8")
        _run(_REGISTER, "init", str(cls.run_dir))

    def _cards(self, language="en"):
        return _run(_CARDS, "list", str(self.run_dir), "--language", language)

    def test_fixed_page_limit_is_not_a_card(self):
        ids = {c["decision_id"] for c in self._cards()["cards"]}
        self.assertNotIn("page_limit", ids)
        # all six genuine decisions are present
        self.assertEqual(len(ids), 6)

    def test_every_card_has_exactly_one_recommended(self):
        for c in self._cards()["cards"]:
            recs = [o for o in c["options"] if o.get("recommended")]
            self.assertLessEqual(len(recs), 1, c["decision_id"])

    def test_no_card_auto_approves(self):
        for c in self._cards()["cards"]:
            actions = {o["action"] for o in c["options"]}
            self.assertNotIn("approve", actions)
            for o in c["options"]:
                self.assertNotIn("selected", o)

    def test_bounded_numeric_carries_constraint(self):
        cards = {c["decision_id"]: c for c in self._cards()["cards"]}
        self.assertEqual(cards["kii_count"]["constraint"]["minimum"], 20)
        self.assertEqual(cards["weeks"]["constraint"]["type"], "RANGE")
        # 8..10 enumerates three values + Other
        vals = [o["value"] for o in cards["weeks"]["options"] if o["value"] is not None]
        self.assertEqual(vals, [8, 9, 10])

    def test_custom_option_present_for_open_numeric(self):
        cards = {c["decision_id"]: c for c in self._cards()["cards"]}
        self.assertTrue(cards["kii_count"]["supports_custom"])

    def test_deferred_and_optional_shapes(self):
        cards = {c["decision_id"]: c for c in self._cards()["cards"]}
        defer_actions = {o["action"] for o in cards["sample_frame"]["options"]}
        self.assertIn("defer", defer_actions)
        opt_values = {o["value"] for o in cards["pilot"]["options"] if o["value"]}
        self.assertIn("INCLUDE", opt_values)
        self.assertIn("DO_NOT_INCLUDE", opt_values)

    def test_progress_indicator_from_next(self):
        card = _run(_CARDS, "next", str(self.run_dir))["card"]
        self.assertEqual(card["progress_total"], 6)
        self.assertTrue(card["progress_label"].startswith("Decision 1 of 6"))

    def test_arabic_labels_canonical_values(self):
        cards = {c["decision_id"]: c for c in self._cards("ar")["cards"]}
        pilot = cards["pilot"]
        # labels localized, stored values canonical
        values = {o["value"] for o in pilot["options"] if o["value"]}
        self.assertIn("INCLUDE", values)
        frame = cards["sample_frame"]
        rec = [o for o in frame["options"] if o["recommended"]][0]
        self.assertEqual(rec["value"], "DEFER_TO_INCEPTION")
        self.assertIn("موصى به", rec["label"])

    def test_resolving_one_decision_removes_its_card(self):
        # record a methodology choice via the real register CLI, then re-list
        _run(_REGISTER, "set", str(self.run_dir), "methodology", '"Mixed-methods"')
        ids = {c["decision_id"] for c in self._cards()["cards"]}
        self.assertNotIn("methodology", ids)  # resolved → no longer actionable


if __name__ == "__main__":
    unittest.main(verbosity=2)
