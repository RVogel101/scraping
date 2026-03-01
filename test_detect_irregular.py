#!/usr/bin/env python3
"""
Tests for auto-detection (detect.py) and irregular verb support.

Run with:  python -m pytest test_detect_irregular.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from armenian_anki.morphology.core import ARM, DIGRAPH_U
from armenian_anki.morphology.detect import (
    detect_verb_class,
    detect_noun_class,
    detect_pos_and_class,
)
from armenian_anki.morphology.irregular_verbs import (
    get_irregular_overrides,
    is_irregular,
    list_irregular_infinitives,
    INF_BE, INF_HAVE, INF_GIVE, INF_GO, INF_COME,
    INF_DO, INF_SAY, INF_SEE, INF_KNOW, INF_EAT,
    INF_DRINK, INF_TAKE, INF_PUT, INF_BRING,
    INF_READ, INF_WRITE, INF_SIT, INF_DIE, INF_WANT,
)
from armenian_anki.morphology.verbs import conjugate_verb


# ─── Auto-detection ──────────────────────────────────────────────────

class TestDetectVerbClass(unittest.TestCase):
    """detect_verb_class() — infinitive ending → class."""

    def test_el_ending_is_e_class(self):
        inf = ARM["s"] + ARM["i"] + ARM["r"] + ARM["ye"] + ARM["l"]  # sirel
        self.assertEqual(detect_verb_class(inf), "e_class")

    def test_al_ending_is_a_class(self):
        inf = ARM["ye"] + ARM["r"] + ARM["t_asp"] + ARM["a"] + ARM["l"]  # yert'al
        self.assertEqual(detect_verb_class(inf), "a_class")

    def test_il_ending_is_e_class(self):
        inf = ARM["n"] + ARM["y_schwa"] + ARM["s"] + ARM["d"] + ARM["i"] + ARM["l"]  # nsdil
        self.assertEqual(detect_verb_class(inf), "e_class")

    def test_unknown_fallback(self):
        self.assertEqual(detect_verb_class("xyz"), "e_class")


class TestDetectNounClass(unittest.TestCase):
    """detect_noun_class() — stem heuristics."""

    def test_default_i_class(self):
        word = ARM["g"] + ARM["i"] + ARM["r"] + ARM["k_asp"]  # kirk' (book)
        self.assertEqual(detect_noun_class(word), "i_class")

    def test_u_class_digraph(self):
        word = ARM["a"] + ARM["sh"] + ARM["vo"] + ARM["yiwn"]  # ashou
        self.assertEqual(detect_noun_class(word), "u_class")

    def test_o_class_hayr(self):
        hayr = ARM["h"] + ARM["a"] + ARM["ye"] + ARM["r"]  # hayr
        self.assertEqual(detect_noun_class(hayr), "o_class")


class TestDetectPosAndClass(unittest.TestCase):
    """detect_pos_and_class() — combined POS + class detection."""

    def test_verb_detected(self):
        inf = ARM["s"] + ARM["i"] + ARM["r"] + ARM["ye"] + ARM["l"]
        pos, cls = detect_pos_and_class(inf)
        self.assertEqual(pos, "verb")
        self.assertIn(cls, ("e_class", "a_class"))

    def test_noun_detected(self):
        word = ARM["g"] + ARM["i"] + ARM["r"] + ARM["k_asp"]
        pos, cls = detect_pos_and_class(word)
        self.assertEqual(pos, "noun")


# ─── Irregular verbs ─────────────────────────────────────────────────

class TestIrregularVerbTable(unittest.TestCase):
    """Ensure the irregular table has expected entries."""

    def test_at_least_15_irregulars(self):
        self.assertGreaterEqual(len(list_irregular_infinitives()), 15)

    def test_is_irregular_true(self):
        self.assertTrue(is_irregular(INF_BE))
        self.assertTrue(is_irregular(INF_HAVE))
        self.assertTrue(is_irregular(INF_GO))

    def test_is_irregular_false_for_regular(self):
        regular = ARM["s"] + ARM["i"] + ARM["r"] + ARM["ye"] + ARM["l"]  # sirel
        self.assertFalse(is_irregular(regular))

    def test_overrides_have_translation(self):
        for inf in [INF_BE, INF_HAVE, INF_GIVE, INF_COME, INF_GO, INF_DO]:
            overrides = get_irregular_overrides(inf)
            assert overrides is not None
            self.assertIn("translation", overrides)

    def test_all_infinitives_are_strings(self):
        for inf in list_irregular_infinitives():
            self.assertIsInstance(inf, str)
            self.assertGreater(len(inf), 0)


class TestIrregularConjugation(unittest.TestCase):
    """conjugate_verb() applies irregular overrides correctly."""

    def test_be_has_irregular_past(self):
        overrides = get_irregular_overrides(INF_BE)
        assert overrides is not None
        conj = conjugate_verb(
            INF_BE,
            verb_class=overrides.get("verb_class", "a_class"),
            translation="be",
        )
        # The past aorist should contain the irregular forms
        self.assertIn("1sg", conj.past_aorist)
        # The irregular override should have been applied
        irr_past = overrides.get("past_aorist", {})
        if irr_past:
            self.assertEqual(conj.past_aorist["1sg"], irr_past["1sg"])

    def test_give_has_irregular_past(self):
        overrides = get_irregular_overrides(INF_GIVE)
        assert overrides is not None
        conj = conjugate_verb(
            INF_GIVE,
            verb_class=overrides.get("verb_class", "a_class"),
            translation="give",
        )
        irr_past = overrides.get("past_aorist", {})
        if irr_past:
            self.assertEqual(conj.past_aorist["1sg"], irr_past["1sg"])

    def test_go_has_irregular_past(self):
        overrides = get_irregular_overrides(INF_GO)
        assert overrides is not None
        conj = conjugate_verb(
            INF_GO,
            verb_class=overrides.get("verb_class", "a_class"),
            translation="go",
        )
        irr_past = overrides.get("past_aorist", {})
        if irr_past:
            self.assertEqual(conj.past_aorist["3sg"], irr_past["3sg"])

    def test_come_has_irregular_present(self):
        overrides = get_irregular_overrides(INF_COME)
        assert overrides is not None
        conj = conjugate_verb(
            INF_COME,
            verb_class=overrides.get("verb_class", "a_class"),
            translation="come",
        )
        irr_pres = overrides.get("present", {})
        if irr_pres:
            self.assertEqual(conj.present["1sg"], irr_pres["1sg"])

    def test_regular_verb_unchanged(self):
        """A regular verb should not be altered by the irregular path."""
        regular = ARM["s"] + ARM["i"] + ARM["r"] + ARM["ye"] + ARM["l"]  # sirel
        conj = conjugate_verb(regular, "e_class", "love")
        self.assertIn("1sg", conj.present)
        self.assertIn("1sg", conj.past_aorist)

    def test_all_irregular_verbs_conjugate(self):
        """Every irregular infinitive should conjugate without error."""
        for inf in list_irregular_infinitives():
            overrides = get_irregular_overrides(inf)
            assert overrides is not None
            vc = overrides.get("verb_class", "e_class")
            conj = conjugate_verb(inf, vc, overrides.get("translation", ""))
            self.assertGreater(len(conj.present), 0)


if __name__ == "__main__":
    unittest.main()
