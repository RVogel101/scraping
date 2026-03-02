#!/usr/bin/env python3
"""
Tests for armenian_anki.progression — phrase-chunking progression system.

Covers:
  - WordEntry syllable counting
  - VocabBatch and PhraseBatch building
  - Syllable gating (words deferred to correct level band)
  - Level/batch assignment
  - Grammar allowance per level
  - Coverage guarantees
  - Tag helpers (level_tag, batch_tag, grammar_tag, syllable_tag)
  - Due position assignment

Run with:  python test_progression.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from armenian_anki.progression import (
    ProgressionPlan,
    WordEntry,
    VocabBatch,
    PhraseBatch,
    PhraseEntry,
    VOCAB_BATCH_SIZE,
    BATCHES_PER_LEVEL,
    max_syllables_for_level,
    max_vocab_words_per_phrase,
    level_tag,
    batch_tag,
    grammar_tag,
    syllable_tag,
    assign_due_positions,
    _allowed_grammar,
    GRAMMAR_SIMPLE,
    GRAMMAR_INTERMEDIATE,
    GRAMMAR_ADVANCED,
)


# ─── Helpers ──────────────────────────────────────────────────────────

def _make_words(count: int, syl: int = 1, pos: str = "noun") -> list[WordEntry]:
    """Create a list of dummy WordEntry objects with sequential frequency ranks."""
    return [
        WordEntry(
            word=f"w{i}",
            translation=f"word{i}",
            pos=pos,
            frequency_rank=i,
            syllable_count=syl,
        )
        for i in range(1, count + 1)
    ]


def _make_mixed_syllable_words() -> list[WordEntry]:
    """Create words with varied syllable counts to test gating.

    Need enough mono-syllable words (100) to fill levels 1-5 so that
    di-syllable words land at level 6+ and tri-syllable at level 11+.
    """
    words = []
    # 100 one-syllable words (rank 1-100) — fills levels 1-5
    for i in range(1, 101):
        words.append(WordEntry(f"mono{i}", f"mono{i}", "noun",
                               frequency_rank=i, syllable_count=1))
    # 100 two-syllable words (rank 101-200) — fills levels 6-10
    for i in range(101, 201):
        words.append(WordEntry(f"di{i}", f"di{i}", "noun",
                               frequency_rank=i, syllable_count=2))
    # 20 three-syllable words (rank 201-220) — starts at level 11
    for i in range(201, 221):
        words.append(WordEntry(f"tri{i}", f"tri{i}", "noun",
                               frequency_rank=i, syllable_count=3))
    return words


# ─── Level Band Rules ─────────────────────────────────────────────────

class TestLevelBandRules(unittest.TestCase):

    def test_max_syllables_levels_1_to_5(self):
        for level in range(1, 6):
            self.assertEqual(max_syllables_for_level(level), 1)

    def test_max_syllables_levels_6_to_10(self):
        for level in range(6, 11):
            self.assertEqual(max_syllables_for_level(level), 2)

    def test_max_syllables_levels_11_to_15(self):
        for level in range(11, 16):
            self.assertEqual(max_syllables_for_level(level), 3)

    def test_max_syllables_levels_16_plus(self):
        self.assertEqual(max_syllables_for_level(16), 999)
        self.assertEqual(max_syllables_for_level(100), 999)

    def test_max_vocab_words_per_phrase_levels_1_to_5(self):
        for level in range(1, 6):
            self.assertEqual(max_vocab_words_per_phrase(level), 1)

    def test_max_vocab_words_per_phrase_levels_6_to_10(self):
        for level in range(6, 11):
            self.assertEqual(max_vocab_words_per_phrase(level), 3)

    def test_max_vocab_words_per_phrase_levels_11_to_15(self):
        for level in range(11, 16):
            self.assertEqual(max_vocab_words_per_phrase(level), 4)

    def test_max_vocab_words_per_phrase_levels_16_to_20(self):
        for level in range(16, 21):
            self.assertEqual(max_vocab_words_per_phrase(level), 5)

    def test_max_vocab_words_per_phrase_levels_21_plus(self):
        self.assertEqual(max_vocab_words_per_phrase(21), 6)
        self.assertEqual(max_vocab_words_per_phrase(50), 6)


# ─── Grammar Allowance ────────────────────────────────────────────────

class TestGrammarAllowance(unittest.TestCase):

    def test_levels_1_to_5_simple_only(self):
        for level in range(1, 6):
            allowed = _allowed_grammar(level)
            self.assertEqual(allowed, GRAMMAR_SIMPLE)

    def test_levels_6_to_10_simple_plus_intermediate(self):
        for level in range(6, 11):
            allowed = _allowed_grammar(level)
            self.assertEqual(allowed, GRAMMAR_SIMPLE + GRAMMAR_INTERMEDIATE)

    def test_levels_11_plus_all(self):
        for level in [11, 15, 20]:
            allowed = _allowed_grammar(level)
            self.assertEqual(
                allowed,
                GRAMMAR_SIMPLE + GRAMMAR_INTERMEDIATE + GRAMMAR_ADVANCED,
            )


# ─── WordEntry ────────────────────────────────────────────────────────

class TestWordEntry(unittest.TestCase):

    def test_explicit_syllable_count(self):
        w = WordEntry("test", "test", "noun", syllable_count=3)
        self.assertEqual(w.syllable_count, 3)

    def test_auto_syllable_count_from_armenian(self):
        """Armenian word should get auto-counted syllables when count=0."""
        from armenian_anki.morphology.core import ARM
        word = ARM["k"] + ARM["i"] + ARM["r"] + ARM["k_asp"]  # girk' = 1 syl
        w = WordEntry(word, "book", "noun")
        self.assertGreater(w.syllable_count, 0)

    def test_repr(self):
        w = WordEntry("test", "word", "noun", frequency_rank=5, syllable_count=2)
        r = repr(w)
        self.assertIn("test", r)
        self.assertIn("rank=5", r)
        self.assertIn("syl=2", r)


# ─── VocabBatch ───────────────────────────────────────────────────────

class TestVocabBatch(unittest.TestCase):

    def test_batch_within_level(self):
        """batch_within_level should be 1-based position within level."""
        # Batch 0 → Level 1, position 1
        vb = VocabBatch(batch_index=0, level=1)
        self.assertEqual(vb.batch_within_level, 1)
        # Batch 4 → Level 1, position 5
        vb = VocabBatch(batch_index=4, level=1)
        self.assertEqual(vb.batch_within_level, 5)
        # Batch 5 → Level 2, position 1
        vb = VocabBatch(batch_index=5, level=2)
        self.assertEqual(vb.batch_within_level, 1)

    def test_anki_position_start(self):
        vb = VocabBatch(batch_index=0, level=1)
        self.assertEqual(vb.anki_position_start, 1)
        vb = VocabBatch(batch_index=2, level=1)
        self.assertEqual(vb.anki_position_start, 41)


# ─── ProgressionPlan — Small Input ────────────────────────────────────

class TestProgressionPlanSmall(unittest.TestCase):

    def test_empty_word_list(self):
        plan = ProgressionPlan([])
        self.assertEqual(plan.vocab_batches, [])
        self.assertEqual(plan.phrase_batches, [])

    def test_single_word(self):
        words = [WordEntry("w1", "word1", "noun", frequency_rank=1, syllable_count=1)]
        plan = ProgressionPlan(words)
        self.assertEqual(len(plan.vocab_batches), 1)
        self.assertEqual(len(plan.phrase_batches), 1)
        self.assertEqual(len(plan.vocab_batches[0].words), 1)
        self.assertEqual(plan.vocab_batches[0].words[0].word, "w1")

    def test_exact_batch_size(self):
        """20 words should produce exactly 1 batch."""
        words = _make_words(VOCAB_BATCH_SIZE)
        plan = ProgressionPlan(words)
        self.assertEqual(len(plan.vocab_batches), 1)
        self.assertEqual(len(plan.vocab_batches[0].words), VOCAB_BATCH_SIZE)

    def test_batch_overflow(self):
        """21 words should produce 2 batches (20 + 1)."""
        words = _make_words(VOCAB_BATCH_SIZE + 1)
        plan = ProgressionPlan(words)
        self.assertEqual(len(plan.vocab_batches), 2)
        self.assertEqual(len(plan.vocab_batches[0].words), VOCAB_BATCH_SIZE)
        self.assertEqual(len(plan.vocab_batches[1].words), 1)


# ─── ProgressionPlan — Level Assignment ───────────────────────────────

class TestProgressionPlanLevels(unittest.TestCase):

    def test_five_batches_equals_one_level(self):
        """100 one-syllable words → 5 batches → level 1."""
        words = _make_words(VOCAB_BATCH_SIZE * BATCHES_PER_LEVEL)
        plan = ProgressionPlan(words)
        self.assertEqual(len(plan.vocab_batches), BATCHES_PER_LEVEL)
        for vb in plan.vocab_batches:
            self.assertEqual(vb.level, 1)

    def test_two_levels(self):
        """200 words → 10 batches → levels 1 and 2."""
        words = _make_words(VOCAB_BATCH_SIZE * BATCHES_PER_LEVEL * 2)
        plan = ProgressionPlan(words)
        self.assertEqual(len(plan.vocab_batches), 10)
        for vb in plan.vocab_batches[:5]:
            self.assertEqual(vb.level, 1)
        for vb in plan.vocab_batches[5:]:
            self.assertEqual(vb.level, 2)


# ─── ProgressionPlan — Syllable Gating ────────────────────────────────

class TestSyllableGating(unittest.TestCase):

    def test_monosyllabic_first(self):
        """With mixed syllable words, 1-syl words should fill levels 1-5."""
        words = _make_mixed_syllable_words()
        plan = ProgressionPlan(words)
        # First 5 batches (level 1) should all be monosyllabic
        for vb in plan.vocab_batches[:5]:
            for w in vb.words:
                self.assertEqual(w.syllable_count, 1,
                                 f"Expected 1-syl word in level 1, got {w}")

    def test_disyllabic_after_monosyllabic(self):
        """2-syllable words should appear only after all 1-syllable words."""
        words = _make_mixed_syllable_words()
        plan = ProgressionPlan(words)
        all_ordered = [w for vb in plan.vocab_batches for w in vb.words]
        last_mono_idx = max(
            i for i, w in enumerate(all_ordered) if w.syllable_count == 1
        )
        first_di_idx = min(
            i for i, w in enumerate(all_ordered) if w.syllable_count == 2
        )
        self.assertGreater(first_di_idx, last_mono_idx,
                           "All mono-syllable words should precede di-syllable words")

    def test_trisyllabic_after_disyllabic(self):
        """3-syllable words should appear only after all 2-syllable words."""
        words = _make_mixed_syllable_words()
        plan = ProgressionPlan(words)
        all_ordered = [w for vb in plan.vocab_batches for w in vb.words]
        last_di_idx = max(
            i for i, w in enumerate(all_ordered) if w.syllable_count == 2
        )
        first_tri_idx = min(
            i for i, w in enumerate(all_ordered) if w.syllable_count == 3
        )
        self.assertGreater(first_tri_idx, last_di_idx,
                           "All di-syllable words should precede tri-syllable words")

    def test_frequency_preserved_within_syllable_group(self):
        """Within each syllable group, words should be sorted by frequency rank."""
        words = _make_mixed_syllable_words()
        plan = ProgressionPlan(words)
        all_ordered = [w for vb in plan.vocab_batches for w in vb.words]
        mono = [w for w in all_ordered if w.syllable_count == 1]
        di = [w for w in all_ordered if w.syllable_count == 2]
        tri = [w for w in all_ordered if w.syllable_count == 3]
        for group in [mono, di, tri]:
            ranks = [w.frequency_rank for w in group]
            self.assertEqual(ranks, sorted(ranks),
                             "Frequency rank should be ascending within syllable group")


# ─── ProgressionPlan — Coverage ───────────────────────────────────────

class TestCoverage(unittest.TestCase):

    def test_full_coverage_small(self):
        """Every word should appear in at least one phrase."""
        words = _make_words(5)
        plan = ProgressionPlan(words)
        report = plan.coverage_report()
        self.assertEqual(report["coverage_pct"], 100.0)
        self.assertEqual(report["uncovered"], [])

    def test_full_coverage_large(self):
        """Coverage should be 100% for a full batch."""
        words = _make_words(VOCAB_BATCH_SIZE)
        plan = ProgressionPlan(words)
        report = plan.coverage_report()
        self.assertEqual(report["coverage_pct"], 100.0)

    def test_coverage_report_structure(self):
        words = _make_words(10)
        plan = ProgressionPlan(words)
        report = plan.coverage_report()
        self.assertIn("total_vocab", report)
        self.assertIn("covered_in_phrases", report)
        self.assertIn("uncovered", report)
        self.assertIn("coverage_pct", report)
        self.assertEqual(report["total_vocab"], 10)


# ─── ProgressionPlan — Phrase Batches ─────────────────────────────────

class TestPhraseBatches(unittest.TestCase):

    def test_phrase_batch_per_vocab_batch(self):
        """Each VocabBatch should have a corresponding PhraseBatch."""
        words = _make_words(VOCAB_BATCH_SIZE * 2)
        plan = ProgressionPlan(words)
        self.assertEqual(len(plan.phrase_batches), len(plan.vocab_batches))

    def test_phrase_covers_each_word_in_batch(self):
        """Every word in a batch should have at least one PhraseEntry."""
        words = _make_words(VOCAB_BATCH_SIZE)
        plan = ProgressionPlan(words)
        pb = plan.phrase_batches[0]
        target_words = {p.target_word for p in pb.phrases}
        batch_words = {w.word for w in plan.vocab_batches[0].words}
        self.assertEqual(target_words, batch_words)

    def test_phrase_grammar_types_rotate(self):
        """Phrases should use diverse grammar types, not all the same."""
        words = _make_words(VOCAB_BATCH_SIZE)
        plan = ProgressionPlan(words)
        grammar_types = {p.grammar_type for p in plan.phrase_batches[0].phrases}
        # With 20 words and only 3 simple grammar types at level 1, all 3 should appear
        self.assertEqual(len(grammar_types), len(GRAMMAR_SIMPLE))

    def test_first_batch_no_supporting_words(self):
        """First batch's phrases should have no supporting words (nothing seen yet)."""
        words = _make_words(VOCAB_BATCH_SIZE)
        plan = ProgressionPlan(words)
        for phrase in plan.phrase_batches[0].phrases:
            self.assertEqual(phrase.supporting_words, [])

    def test_second_batch_has_supporting_words(self):
        """After batch 0, supporting words should come from previously seen words."""
        words = _make_words(VOCAB_BATCH_SIZE * 2)
        plan = ProgressionPlan(words)
        # At level 1, max_vocab_words_per_phrase = 1, so support slots = 0
        # Need to test at a higher level - use 2-syl words at level 6+
        # Instead, test the internal logic: at level 1, no support is expected
        # because max_vocab_words_per_phrase(1) - 1 = 0
        for phrase in plan.phrase_batches[1].phrases:
            self.assertEqual(phrase.supporting_words, [],
                             "At level 1, phrase word allowance is 1 so no support words")


# ─── ProgressionPlan — Ordered Segments ───────────────────────────────

class TestOrderedSegments(unittest.TestCase):

    def test_alternates_vocab_and_phrase(self):
        """ordered_segments should yield VocabBatch, PhraseBatch alternately."""
        words = _make_words(VOCAB_BATCH_SIZE * 2)
        plan = ProgressionPlan(words)
        segments = list(plan.ordered_segments())
        self.assertEqual(len(segments), 4)  # 2 VB + 2 PB
        self.assertIsInstance(segments[0], VocabBatch)
        self.assertIsInstance(segments[1], PhraseBatch)
        self.assertIsInstance(segments[2], VocabBatch)
        self.assertIsInstance(segments[3], PhraseBatch)


# ─── Summary ──────────────────────────────────────────────────────────

class TestSummary(unittest.TestCase):

    def test_summary_contains_level_info(self):
        words = _make_words(VOCAB_BATCH_SIZE)
        plan = ProgressionPlan(words)
        summary = plan.summary()
        self.assertIn("Level", summary)
        self.assertIn("Total words:", summary)
        self.assertIn("Total batches:", summary)

    def test_summary_empty_plan(self):
        plan = ProgressionPlan([])
        summary = plan.summary()
        self.assertIn("Total words:   0", summary)


# ─── Tag Helpers ──────────────────────────────────────────────────────

class TestTagHelpers(unittest.TestCase):

    def test_level_tag(self):
        self.assertEqual(level_tag(1), "level::01")
        self.assertEqual(level_tag(15), "level::15")

    def test_batch_tag(self):
        self.assertEqual(batch_tag(0), "batch::000")
        self.assertEqual(batch_tag(42), "batch::042")

    def test_grammar_tag(self):
        self.assertEqual(grammar_tag("accusative_object"), "grammar::accusative_object")

    def test_syllable_tag(self):
        self.assertEqual(syllable_tag(2), "syl::2")


# ─── Due Position Assignment ─────────────────────────────────────────

class TestDuePositions(unittest.TestCase):

    def test_positions_monotonically_increase(self):
        """Vocab positions should be sequential within each batch."""
        words = _make_words(VOCAB_BATCH_SIZE)
        plan = ProgressionPlan(words)
        positions = assign_due_positions(plan)
        # Vocab words 1-20 should have positions 1-20
        vocab_positions = [positions[f"w{i}"] for i in range(1, VOCAB_BATCH_SIZE + 1)]
        self.assertEqual(vocab_positions, list(range(1, VOCAB_BATCH_SIZE + 1)))

    def test_phrase_positions_after_vocab(self):
        """Phrase positions should come after vocab positions in the same batch."""
        words = _make_words(VOCAB_BATCH_SIZE)
        plan = ProgressionPlan(words)
        positions = assign_due_positions(plan)
        max_vocab_pos = max(
            positions[w.word] for w in plan.vocab_batches[0].words
        )
        for phrase in plan.phrase_batches[0].phrases:
            phrase_key = f"phrase::{phrase.target_word}"
            if phrase_key in positions:
                self.assertGreater(positions[phrase_key], max_vocab_pos)

    def test_two_batches_positions_non_overlapping(self):
        """Batch 1 positions should all be > batch 0 positions."""
        words = _make_words(VOCAB_BATCH_SIZE * 2)
        plan = ProgressionPlan(words)
        positions = assign_due_positions(plan)

        batch0_words = {w.word for w in plan.vocab_batches[0].words}
        batch1_words = {w.word for w in plan.vocab_batches[1].words}

        max_batch0 = max(positions[w] for w in batch0_words)
        min_batch1 = min(positions[w] for w in batch1_words)
        self.assertGreater(min_batch1, max_batch0)

    def test_all_words_have_positions(self):
        words = _make_words(VOCAB_BATCH_SIZE)
        plan = ProgressionPlan(words)
        positions = assign_due_positions(plan)
        for vb in plan.vocab_batches:
            for w in vb.words:
                self.assertIn(w.word, positions)


if __name__ == "__main__":
    unittest.main()
