"""v0.6.3 interactive Decision-Review descriptor tests (UX layer only).

These tests cover the descriptor BUILDER (engine/tor/decision_ui.py) — the shape
of the native option cards — not decision semantics, validation, or persistence
(those are covered by the Phase 2 register tests and remain unchanged).

Run from plugin root:
    python -m pytest tests/test_decision_ui.py -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.tor import decision_ui as dui


def _dec(**kw):
    base = {
        "decision_id": "d1", "requirement_id": "r1",
        "decision_type": "OPEN_PROPOSAL_DECISION", "question": "What to propose?",
        "constraint_type": "NONE", "minimum": None, "maximum": None,
        "source_text": "", "category": "methodology", "actor": "bidder",
        "is_human_decision": True, "allowed_options": [],
    }
    base.update(kw)
    return base


def _rec_options(desc):
    return [o for o in desc["options"] if o.get("recommended")]


class TestFixedExcluded(unittest.TestCase):

    def test_fixed_requirement_is_not_a_question(self):
        for dt in ("FIXED_REQUIREMENT", "FIXED_MINIMUM", "FIXED_MAXIMUM",
                   "FIXED_RANGE", "NO_DECISION"):
            d = _dec(decision_type=dt, is_human_decision=False)
            self.assertFalse(dui.is_question(d), dt)
            self.assertIsNone(dui.build_question_descriptor(d), dt)

    def test_open_decision_is_a_question(self):
        self.assertTrue(dui.is_question(_dec()))
        self.assertIsNotNone(dui.build_question_descriptor(_dec()))


class TestRecommendedNotAutoApproved(unittest.TestCase):

    def test_at_most_one_recommended_and_flagged(self):
        d = _dec(constraint_type="ENUM",
                 allowed_options=["Mixed-methods", "Qualitative", "Quantitative"])
        desc = dui.build_question_descriptor(d)
        recs = _rec_options(desc)
        self.assertEqual(len(recs), 1)
        self.assertIn("Recommended", recs[0]["label"])

    def test_recommended_is_a_marker_not_a_selection(self):
        # The descriptor never carries a "selected"/"default" field — selection is
        # always the user's act. Recommended is only a label marker.
        d = _dec(constraint_type="ENUM", allowed_options=["A", "B"])
        desc = dui.build_question_descriptor(d)
        for o in desc["options"]:
            self.assertNotIn("selected", o)
            self.assertNotIn("default", o)

    def test_recommendation_action_routes_through_recommend(self):
        desc = dui.build_question_descriptor(_dec())  # open → has recommend option
        actions = {o["action"] for o in desc["options"]}
        self.assertIn("recommend", actions)
        # no option auto-approves
        self.assertNotIn("approve", actions)


class TestEnumOptions(unittest.TestCase):

    def test_enum_builds_options_plus_other(self):
        d = _dec(constraint_type="ENUM", allowed_options=["Panel", "Cohort"])
        desc = dui.build_question_descriptor(d)
        labels = [o["label"] for o in desc["options"]]
        self.assertTrue(any("Panel" in l for l in labels))
        self.assertTrue(desc["supports_custom"])
        self.assertEqual(desc["options"][-1]["action"], "custom")

    def test_enum_first_is_recommended(self):
        d = _dec(constraint_type="ENUM", allowed_options=["First", "Second"])
        desc = dui.build_question_descriptor(d)
        self.assertTrue(desc["options"][0]["recommended"])
        self.assertFalse(desc["options"][1]["recommended"])


class TestNumericBoundedOptions(unittest.TestCase):

    def test_small_range_enumerates_values_with_midpoint_recommended(self):
        d = _dec(constraint_type="RANGE", minimum=6, maximum=8, category="timeline",
                 source_text="between 6 and 8 weeks")
        desc = dui.build_question_descriptor(d)
        values = [o["value"] for o in desc["options"] if o["value"] is not None]
        self.assertEqual(values, [6, 7, 8])
        recs = _rec_options(desc)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["value"], 7)  # midpoint

    def test_large_range_collapses_to_recommended_plus_custom(self):
        d = _dec(constraint_type="RANGE", minimum=10, maximum=40, category="sampling",
                 source_text="between 10 and 40 KIIs")
        desc = dui.build_question_descriptor(d)
        # recommended midpoint + custom exact
        self.assertEqual(len(desc["options"]), 2)
        self.assertTrue(desc["options"][0]["recommended"])
        self.assertEqual(desc["options"][0]["value"], 25)
        self.assertTrue(desc["supports_custom"])

    def test_at_least_recommends_minimum_and_allows_more(self):
        d = _dec(constraint_type="AT_LEAST", minimum=30, category="sampling",
                 source_text="at least 30 KIIs")
        desc = dui.build_question_descriptor(d)
        self.assertEqual(desc["options"][0]["value"], 30)
        self.assertTrue(desc["options"][0]["recommended"])
        self.assertTrue(desc["supports_custom"])
        self.assertEqual(desc["constraint"]["minimum"], 30)

    def test_units_surface_in_labels(self):
        d = _dec(constraint_type="AT_LEAST", minimum=6, category="timeline",
                 source_text="at least 6 weeks")
        desc = dui.build_question_descriptor(d)
        self.assertIn("weeks", desc["options"][0]["label"])


class TestDeferredAndOptional(unittest.TestCase):

    def test_deferred_decision_card(self):
        d = _dec(decision_type="DEFERRED_DECISION", constraint_type="NONE",
                 question="Final sample frame?")
        desc = dui.build_question_descriptor(d)
        actions = {o["action"] for o in desc["options"]}
        self.assertEqual(actions, {"defer", "custom", "recommend", "unresolved"})
        # defer is the recommended one
        rec = _rec_options(desc)[0]
        self.assertEqual(rec["action"], "defer")

    def test_optional_choice_card(self):
        d = _dec(decision_type="OPTIONAL_CHOICE", constraint_type="NONE",
                 question="Include a pilot phase?")
        desc = dui.build_question_descriptor(d)
        values = {o["value"] for o in desc["options"] if o["value"]}
        self.assertIn("INCLUDE", values)
        self.assertIn("DO_NOT_INCLUDE", values)

    def test_open_decision_supports_custom_and_defer(self):
        desc = dui.build_question_descriptor(_dec())
        actions = [o["action"] for o in desc["options"]]
        self.assertIn("custom", actions)
        self.assertIn("defer", actions)
        self.assertIn("recommend", actions)


class TestArabic(unittest.TestCase):

    def test_arabic_labels_but_canonical_values(self):
        d = _dec(constraint_type="ENUM", allowed_options=["Mixed", "Qual"])
        desc = dui.build_question_descriptor(d, language="arabic")
        # the "Other" label is Arabic
        self.assertEqual(desc["options"][-1]["label"], "أخرى")
        # recommended marker is Arabic
        self.assertIn("موصى به", desc["options"][0]["label"])
        # canonical stored values stay ASCII/uppercased
        self.assertEqual(desc["options"][0]["value"], "MIXED")

    def test_arabic_defer_value_is_canonical(self):
        d = _dec(decision_type="DEFERRED_DECISION", constraint_type="NONE")
        desc = dui.build_question_descriptor(d, language="arabic")
        rec = _rec_options(desc)[0]
        self.assertEqual(rec["value"], "DEFER_TO_INCEPTION")
        self.assertIn("يُحدد", rec["label"])

    def test_arabic_tor_context_prefix(self):
        d = _dec(source_text="يجب إجراء 30 مقابلة")
        desc = dui.build_question_descriptor(d, language="arabic")
        self.assertTrue(desc["tor_context"].startswith("الـTOR:"))


class TestFallback(unittest.TestCase):

    def test_fallback_is_short_numbered_list(self):
        d = _dec(constraint_type="ENUM", allowed_options=["A", "B", "C"])
        desc = dui.build_question_descriptor(d)
        fb = desc["fallback_numbered"]
        self.assertIn("1.", fb)
        self.assertIn("2.", fb)
        # question first line, then numbered options, then reply hint
        lines = fb.splitlines()
        self.assertEqual(lines[0], desc["question"])
        self.assertIn("number", lines[-1].lower())

    def test_fallback_question_is_short(self):
        long_q = "Why? " * 100
        d = _dec(question=long_q)
        desc = dui.build_question_descriptor(d)
        self.assertLessEqual(len(desc["question"]), 160)


class TestExpiredDateCard(unittest.TestCase):

    def test_past_dates_trigger_one_card(self):
        tor = {"metadata": {"submission_requirements":
                            {"value": "Proposals due 15 March 2019."}}}
        desc = dui.expired_date_descriptor(tor, today_year=2026)
        self.assertIsNotNone(desc)
        self.assertEqual(desc["kind"], "META")
        self.assertEqual(len(desc["options"]), 3)
        self.assertTrue(any(o["recommended"] for o in desc["options"]))

    def test_future_dates_no_card(self):
        tor = {"metadata": {"timeline": {"value": "Submit by 2030-01-01."}}}
        self.assertIsNone(dui.expired_date_descriptor(tor, today_year=2026))

    def test_no_dates_no_card(self):
        tor = {"metadata": {"timeline": {"value": "No fixed date."}}}
        self.assertIsNone(dui.expired_date_descriptor(tor, today_year=2026))


class TestDescriptorShape(unittest.TestCase):

    def test_descriptor_has_required_keys(self):
        desc = dui.build_question_descriptor(_dec())
        for key in ("decision_id", "requirement_id", "kind", "header", "question",
                    "tor_context", "options", "supports_custom", "constraint",
                    "fallback_numbered"):
            self.assertIn(key, desc)

    def test_header_within_chip_limit(self):
        desc = dui.build_question_descriptor(_dec(category="data_collection_methods"))
        self.assertLessEqual(len(desc["header"]), 12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
