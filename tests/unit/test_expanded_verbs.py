#!/usr/bin/env python3
"""
Tests for expanded verb templates (conditional, perfect, pluperfect).

Run with: python -m pytest test_expanded_verbs.py -v
"""

import unittest
from armenian_anki.morphology.verbs import conjugate_verb, TENSES


class TestExpandedVerbTenses(unittest.TestCase):
    """Test the newly expanded verb tenses."""

    def setUp(self):
        """Set up test fixtures."""
        self.verb_el = conjugate_verb("բերել", verb_class="e_class", translation="to bring")
        self.verb_al = conjugate_verb("տալ", verb_class="a_class", translation="to give")

    def test_tenses_list_updated(self):
        """Verify TENSES constant includes new tenses."""
        expected_new_tenses = ["conditional", "perfect", "pluperfect"]
        for tense in expected_new_tenses:
            self.assertIn(tense, TENSES, f"Tense '{tense}' missing from TENSES list")

    def test_conditional_has_all_persons(self):
        """Test conditional forms are generated for all persons."""
        for person in ["1sg", "2sg", "3sg", "1pl", "2pl", "3pl"]:
            self.assertIn(
                person,
                self.verb_el.conditional,
                f"Conditional missing for person {person}",
            )
            self.assertGreater(
                len(self.verb_el.conditional[person]),
                0,
                f"Conditional empty for person {person}",
            )

    def test_conditional_is_distinct_from_subjunctive(self):
        """Conditional should be different from subjunctive (has prefix)."""
        for person in ["1sg", "3sg"]:
            cond = self.verb_el.conditional[person]
            subj = self.verb_el.subjunctive[person]
            # Conditional includes the 'կա' prefix
            self.assertNotEqual(
                cond, subj, f"Conditional and subjunctive identical for {person}"
            )

    def test_perfect_has_all_persons(self):
        """Test perfect forms are generated for all persons."""
        for person in ["1sg", "2sg", "3sg", "1pl", "2pl", "3pl"]:
            self.assertIn(
                person,
                self.verb_el.perfect,
                f"Perfect missing for person {person}",
            )

    def test_perfect_contains_past_participle(self):
        """Perfect should reference the past participle as a component."""
        for person in ["1sg", "3sg"]:
            perfect_form = self.verb_el.perfect[person]
            # Perfect forms show the past participle + auxiliary construction
            self.assertIn(
                "auxiliary",
                perfect_form,
                f"Auxiliary reference missing from perfect for {person}",
            )

    def test_pluperfect_has_all_persons(self):
        """Test pluperfect forms are generated for all persons."""
        for person in ["1sg", "2sg", "3sg", "1pl", "2pl", "3pl"]:
            self.assertIn(
                person,
                self.verb_el.pluperfect,
                f"Pluperfect missing for person {person}",
            )

    def test_pluperfect_contains_past_participle(self):
        """Pluperfect should reference the past participle as a component."""
        for person in ["1sg", "3sg"]:
            pluperfect_form = self.verb_el.pluperfect[person]
            # Pluperfect forms show the past participle + past "to be" construction
            self.assertIn(
                "was",
                pluperfect_form,
                f"Past auxiliary reference missing from pluperfect for {person}",
            )

    def test_verb_conjugation_as_dict_includes_all_tenses(self):
        """VerbConjugation.as_dict() should include all new tenses."""
        conj_dict = self.verb_el.as_dict()
        for tense in ["conditional", "perfect", "pluperfect"]:
            self.assertIn(tense, conj_dict, f"Tense '{tense}' missing from as_dict()")
            self.assertIsInstance(conj_dict[tense], dict)

    def test_summary_table_includes_new_tenses(self):
        """summary_table() should display all new tenses."""
        summary = self.verb_el.summary_table()
        for tense_name in ["Conditional", "Perfect", "Pluperfect"]:
            self.assertIn(
                tense_name, summary, f"Tense '{tense_name}' missing from summary_table()"
            )

    def test_a_class_verb_conditional(self):
        """Test conditional for a_class verb."""
        for person in ["1sg", "3sg"]:
            self.assertIn(person, self.verb_al.conditional)
            self.assertGreater(len(self.verb_al.conditional[person]), 0)

    def test_irregular_verb_with_new_tenses(self):
        """Test that irregular verbs still work with new tenses."""
        be = conjugate_verb("ըլլալ", translation="to be")
        # "to be" has specific overrides for present/past
        self.assertGreater(len(be.present), 0)
        self.assertGreater(len(be.past_aorist), 0)
        # Even with overrides, new tenses should exist
        self.assertGreater(len(be.conditional), 0)
        self.assertGreater(len(be.perfect), 0)
        self.assertGreater(len(be.pluperfect), 0)


if __name__ == "__main__":
    unittest.main()
