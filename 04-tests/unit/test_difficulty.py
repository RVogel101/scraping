"""
Tests for morphological and phonological difficulty analysis.
"""

import unittest

from lousardzag.morphology.core import ARM
from lousardzag.morphology.difficulty import (
    count_syllables_with_context,
    score_noun_difficulty,
    score_verb_difficulty,
    score_word_difficulty,
    analyze_word,
    _score_rare_phonemes,
    _score_consonant_clusters,
)


class TestHiddenVowelCounting(unittest.TestCase):
    """Test syllable counting with grammatical vowels."""

    def test_basic_syllable_count(self):
        """Basic counting without grammatical vowels."""
        # Single syllable
        self.assertEqual(count_syllables_with_context(ARM["a"], with_epenthesis=False), 1)
        # Two syllables
        mama = ARM["m"] + ARM["a"] + ARM["m"] + ARM["a"]
        self.assertEqual(count_syllables_with_context(mama, with_epenthesis=False), 2)

    def test_with_hidden_vowels(self):
        """Test that hidden vowels (ը) count in grammatical contexts."""
        # Word ending in stem + schwa + suffix pattern
        # ե.ր+ք (երք) = "day" + suffix, has hidden vowel context
        word_with_schwa = ARM["ye"] + ARM["r"] + ARM["y_schwa"] + ARM["k"]
        count_base = count_syllables_with_context(word_with_schwa, with_epenthesis=False)
        count_with_grammar = count_syllables_with_context(word_with_schwa, with_epenthesis=True)
        # Should count higher with grammatical vowels
        self.assertGreaterEqual(count_with_grammar, count_base)

    def test_epenthesis_initial_cluster(self):
        """Test epenthesis detection in initial consonant clusters.
        
        Western Armenian requires schwa insertion in initial CC clusters.
        Example: սպասել (usbasel, "to wait") has initial sp cluster
        which in pronunciation becomes սְ-պա-սե-լ (4 syllables instead of 3).
        """
        # Construct simple word with initial sp cluster: սպա (spa)
        # Note: we're testing orthographic input; actual pronunciation would be սə-պա
        word_sp = ARM["s"] + ARM["p"] + ARM["a"]
        # Base count from orthography: 1 syllable (CCV pattern)
        base = count_syllables_with_context(word_sp, with_epenthesis=False)
        # With epenthesis: 2 syllables (C@CV → s@-pa)
        with_epenthesis = count_syllables_with_context(word_sp, with_epenthesis=True)
        # Epenthesis should add one syllable for initial sp
        self.assertEqual(base, 1)
        self.assertEqual(with_epenthesis, 2)

    def test_epenthesis_initial_cluster_kt(self):
        """Test epenthesis with initial kt cluster (կտ)."""
        word_kt = ARM["k"] + ARM["t"] + ARM["a"]
        base = count_syllables_with_context(word_kt, with_epenthesis=False)
        with_epenthesis = count_syllables_with_context(word_kt, with_epenthesis=True)
        self.assertEqual(base, 1)  # Orthographic: կտա = 1 syllable
        self.assertEqual(with_epenthesis, 2)  # Pronounced: կə-տա = 2 syllables

    def test_no_epenthesis_affricates(self):
        """Test that affricates (single units) don't trigger epenthesis."""
        # ծ (ts) is a single affricate, not a cluster
        word = ARM["ts"] + ARM["a"]
        base = count_syllables_with_context(word, with_epenthesis=False)
        with_epenthesis = count_syllables_with_context(word, with_epenthesis=True)
        # No epenthesis needed
        self.assertEqual(base, with_epenthesis)

    def test_epenthesis_medial_rising_sonority(self):
        """Test epenthesis in medial position with rising sonority clusters.
        
        Rising sonority (e.g., stop before nasal) requires epenthesis
        because codas need falling/level sonority.
        Example: tm (t=stop, m=nasal) has rising sonority → requires schwa
        """
        # Build word: ա-տ-մ-ա (a-t-m-a) where tm is medial
        # tm has rising sonority: stop (t, son=1) before nasal (m, son=3)
        word_medial_tm = ARM["a"] + ARM["t"] + ARM["m"] + ARM["a"]
        base = count_syllables_with_context(word_medial_tm, with_epenthesis=False)
        with_epenthesis = count_syllables_with_context(word_medial_tm, with_epenthesis=True)
        # With rising sonority tm in medial position, epenthesis occurs
        self.assertGreater(with_epenthesis, base)

    def test_no_epenthesis_falling_sonority(self):
        """Test that falling sonority clusters don't trigger epenthesis.
        
        Example: rm (r is liquid/high sonority, m is nasal/lower) is valid coda.
        """
        # Build word: ա-ր-մ-ա (a-r-m-a) where rm is medial with falling sonority
        word_falling = ARM["a"] + ARM["r"] + ARM["m"] + ARM["a"]
        base = count_syllables_with_context(word_falling, with_epenthesis=False)
        with_epenthesis = count_syllables_with_context(word_falling, with_epenthesis=True)
        # Falling sonority, no epenthesis needed
        self.assertEqual(base, with_epenthesis)

class TestPhonologicalScoring(unittest.TestCase):
    """Test phoneme rarity scoring."""

    def test_rare_fricatives(self):
        """Fricatives like ժ (zh) increase difficulty."""
        # ժամ (jam) — "hour"
        jam = ARM["zh"] + ARM["a"] + ARM["m"]
        score = _score_rare_phonemes(jam)
        self.assertGreater(score, 0.0)

    def test_affricates(self):
        """Affricates like ծ (ts) increase difficulty."""
        # ծանուցել — note the ts sound
        word = ARM["ts"] + ARM["a"] + ARM["n"]
        score = _score_rare_phonemes(word)
        self.assertGreater(score, 0.0)

    def test_common_consonants(self):
        """Words with common sounds have low phonological score."""
        # մեր (mer) — "our"
        mer = ARM["m"] + ARM["ye"] + ARM["r"]
        score = _score_rare_phonemes(mer)
        self.assertEqual(score, 0.0)  # No rare phonemes


class TestConsonantClusters(unittest.TestCase):
    """Test consonant cluster complexity scoring."""

    def test_simple_cv(self):
        """Simple CV syllables have no cluster penalty."""
        # մա (ma)
        ma = ARM["m"] + ARM["a"]
        score = _score_consonant_clusters(ma)
        self.assertEqual(score, 0.0)

    def test_double_consonants(self):
        """Double consonants should increase score."""
        # Word with consonant cluster
        word = ARM["m"] + ARM["n"] + ARM["a"]  # mna (consonant cluster)
        score = _score_consonant_clusters(word)
        self.assertGreater(score, 0.0)


class TestNounDifficulty(unittest.TestCase):
    """Test noun difficulty scoring."""

    def test_regular_noun_i_class(self):
        """Regular i-class nouns have lower difficulty."""
        # մեղ (megh) — "sin"
        megh = ARM["m"] + ARM["ye"] + ARM["gh"]
        score = score_noun_difficulty(megh, declension_class="i_class")
        self.assertLess(score, 3.0)  # Should be relatively easy

    def test_irregular_noun_o_class(self):
        """Irregular o-class nouns have higher difficulty."""
        word = ARM["h"] + ARM["a"] + ARM["y"] + ARM["r"]
        score_regular = score_noun_difficulty(word, declension_class="i_class")
        score_irregular = score_noun_difficulty(word, declension_class="o_class")
        self.assertGreater(score_irregular, score_regular)

    def test_multisyllabic_noun(self):
        """Longer words have higher difficulty."""
        # Single syllable
        short = ARM["m"] + ARM["a"]
        score_short = score_noun_difficulty(short, declension_class="i_class")
        # Three syllables
        long = ARM["m"] + ARM["a"] + ARM["m"] + ARM["a"] + ARM["n"] + ARM["a"] + ARM["n"]
        score_long = score_noun_difficulty(long, declension_class="i_class")
        self.assertGreater(score_long, score_short)


class TestVerbDifficulty(unittest.TestCase):
    """Test verb difficulty scoring."""

    def test_weak_verb(self):
        """Weak verbs have low difficulty."""
        word = ARM["g"] + ARM["a"] + ARM["l"]
        score = score_verb_difficulty(word, verb_class="weak")
        # Should be relatively low but > 0
        self.assertGreater(score, 0.0)
        self.assertLess(score, 5.0)

    def test_irregular_verb(self):
        """Irregular verbs have high difficulty."""
        word = ARM["g"] + ARM["a"] + ARM["l"]
        score_weak = score_verb_difficulty(word, verb_class="weak")
        score_irregular = score_verb_difficulty(word, verb_class="irregular")
        self.assertGreater(score_irregular, score_weak)


class TestCompositeScoring(unittest.TestCase):
    """Test overall word difficulty scoring."""

    def test_generic_noun(self):
        """Score generic words by POS."""
        # Simple noun
        word = ARM["m"] + ARM["a"]
        score = score_word_difficulty(word, pos="noun")
        self.assertGreater(score, 0.0)
        self.assertLess(score, 10.0)

    def test_noun_with_class(self):
        """Noun with declension class info."""
        word = ARM["m"] + ARM["a"]
        score = score_word_difficulty(word, pos="noun", declension_class="i_class")
        self.assertGreater(score, 0.0)

    def test_verb_with_class(self):
        """Verb with conjugation class info."""
        word = ARM["g"] + ARM["a"] + ARM["l"]
        score = score_word_difficulty(word, pos="verb", verb_class="weak")
        self.assertGreater(score, 0.0)


class TestWordAnalysis(unittest.TestCase):
    """Test complete word analysis."""

    def test_analysis_creates_record(self):
        """analyze_word() creates a complete analysis record."""
        word = ARM["m"] + ARM["a"]
        analysis = analyze_word(word, pos="noun", declension_class="i_class")

        self.assertEqual(analysis.word, word)
        self.assertEqual(analysis.pos, "noun")
        self.assertGreater(analysis.syllables_base, 0)
        self.assertGreater(analysis.overall_difficulty, 0.0)
        self.assertLessEqual(analysis.overall_difficulty, 10.0)

    def test_analysis_summary(self):
        """analyze_word() produces a readable summary."""
        word = ARM["m"] + ARM["a"]
        analysis = analyze_word(word, pos="noun", declension_class="i_class")
        summary = analysis.summary()
        # Should contain word, POS, and scores
        self.assertIn("noun", summary)
        self.assertIn("difficulty", summary)


if __name__ == "__main__":
    unittest.main()
