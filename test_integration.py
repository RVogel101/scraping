#!/usr/bin/env python3
"""
Integration tests — end-to-end pipeline from word list to card + DB persistence.

Tests the full flow: word list → morphology → card generation → DB storage,
and word list → progression plan → ordered card generation, all with a
mocked AnkiConnect so no live Anki instance is needed.

Run with:  python test_integration.py
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(__file__))

from armenian_anki.card_generator import CardGenerator
from armenian_anki.database import CardDatabase
from armenian_anki.morphology.core import ARM
from armenian_anki.morphology.nouns import decline_noun
from armenian_anki.morphology.verbs import conjugate_verb
from armenian_anki.sentence_generator import generate_noun_sentences, generate_verb_sentences
from armenian_anki.progression import (
    ProgressionPlan, WordEntry, VocabBatch, PhraseBatch,
    level_tag, batch_tag, grammar_tag, syllable_tag,
    assign_due_positions,
)


# ─── Test Words ───────────────────────────────────────────────────────

_WORD_BOOK = ARM["k"] + ARM["i"] + ARM["r"] + ARM["k_asp"]
_WORD_HOUSE = ARM["d"] + ARM["vo"] + ARM["yiwn"] + ARM["n"]
_WORD_WRITE = ARM["k"] + ARM["r"] + ARM["ye"] + ARM["l"]
_WORD_SPEAK = ARM["kh"] + ARM["vo"] + ARM["s"] + ARM["ye"] + ARM["l"]
_WORD_PLAY = ARM["kh"] + ARM["a"] + ARM["gh"] + ARM["a"] + ARM["l"]


def _mock_anki():
    anki = MagicMock()
    anki.ping.return_value = True
    anki.model_names.return_value = []
    anki.create_model.return_value = {}
    anki.ensure_deck.return_value = 1
    _counter = {"id": 5000}

    def fake_add(**kw):
        _counter["id"] += 1
        return _counter["id"]

    anki.add_note.side_effect = fake_add
    return anki


# ─── E2E: Morphology → Cards → DB ────────────────────────────────────

class TestMorphologyToCardToDb(unittest.TestCase):
    """Verify the full morphology → card generation → local DB round-trip."""

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.anki = _mock_anki()
        self.gen = CardGenerator(anki=self.anki, db_path=self._tmp.name)
        self.db = CardDatabase(self._tmp.name)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_noun_roundtrip(self):
        """Generate a noun card and verify morphology persists in DB."""
        note_id = self.gen.generate_noun_card(_WORD_BOOK, "book", "i_class")
        self.assertIsNotNone(note_id)

        card = self.db.get_card_by_word(_WORD_BOOK, "noun_declension")
        self.assertIsNotNone(card)
        self.assertEqual(card["pos"], "noun")
        self.assertEqual(card["declension_class"], "i_class")

        # Morphology JSON should contain case forms
        morph = card["morphology"]
        self.assertIn("NomSg", morph)
        self.assertIn("GenDatSg", morph)
        self.assertIn("AblSg", morph)
        self.assertIn("NomPl", morph)

    def test_verb_roundtrip(self):
        """Generate a verb card and verify conjugation persists in DB."""
        note_id = self.gen.generate_verb_card(_WORD_WRITE, "write", "e_class")
        self.assertIsNotNone(note_id)

        card = self.db.get_card_by_word(_WORD_WRITE, "verb_conjugation")
        self.assertIsNotNone(card)
        self.assertEqual(card["pos"], "verb")
        self.assertEqual(card["verb_class"], "e_class")

        morph = card["morphology"]
        self.assertIn("Pres1sg", morph)
        self.assertIn("Past1sg", morph)
        self.assertIn("Fut1sg", morph)

    def test_sentences_linked_to_card(self):
        """Sentence cards should be linked to the parent card in DB."""
        self.gen.generate_noun_card(_WORD_BOOK, "book", "i_class")
        sent_ids = self.gen.generate_sentence_cards(
            _WORD_BOOK, "noun", "book", "i_class",
        )
        self.assertGreater(len(sent_ids), 0)

        card = self.db.get_card_by_word(_WORD_BOOK, "noun_declension")
        sentences = self.db.get_sentences(card["id"])
        self.assertGreater(len(sentences), 0)
        for s in sentences:
            self.assertTrue(s["armenian_text"])
            self.assertTrue(s["english_text"])

    def test_multiple_words_independent(self):
        """Multiple words should produce separate cards."""
        self.gen.generate_noun_card(_WORD_BOOK, "book")
        self.gen.generate_noun_card(_WORD_HOUSE, "house")
        self.gen.generate_verb_card(_WORD_WRITE, "write")

        cards = self.db.list_cards()
        self.assertEqual(len(cards), 3)
        words = {c["word"] for c in cards}
        self.assertEqual(words, {_WORD_BOOK, _WORD_HOUSE, _WORD_WRITE})

    def test_idempotent_card_generation(self):
        """Re-generating the same card should update, not duplicate."""
        id1 = self.gen.generate_noun_card(_WORD_BOOK, "book")
        id2 = self.gen.generate_noun_card(_WORD_BOOK, "book")
        cards = self.db.list_cards()
        self.assertEqual(len(cards), 1)


# ─── E2E: Progression → Cards ────────────────────────────────────────

class TestProgressionToCards(unittest.TestCase):
    """Test building a progression plan and generating cards in order."""

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.anki = _mock_anki()
        self.gen = CardGenerator(anki=self.anki, db_path=self._tmp.name)
        self.db = CardDatabase(self._tmp.name)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def _make_vocab_entries(self) -> list[WordEntry]:
        """Create a small set of real Armenian words as WordEntry objects."""
        return [
            WordEntry(_WORD_BOOK, "book", "noun", frequency_rank=1,
                      declension_class="i_class", syllable_count=1),
            WordEntry(_WORD_HOUSE, "house", "noun", frequency_rank=2,
                      declension_class="i_class", syllable_count=1),
            WordEntry(_WORD_WRITE, "write", "verb", frequency_rank=3,
                      verb_class="e_class", syllable_count=1),
            WordEntry(_WORD_SPEAK, "speak", "verb", frequency_rank=4,
                      verb_class="e_class", syllable_count=2),
            WordEntry(_WORD_PLAY, "play", "verb", frequency_rank=5,
                      verb_class="a_class", syllable_count=2),
        ]

    def test_progression_plan_from_real_words(self):
        """ProgressionPlan should handle real Armenian words."""
        entries = self._make_vocab_entries()
        plan = ProgressionPlan(entries)
        self.assertGreater(len(plan.vocab_batches), 0)
        self.assertGreater(len(plan.phrase_batches), 0)
        report = plan.coverage_report()
        self.assertEqual(report["coverage_pct"], 100.0)

    def test_progression_generates_ordered_cards(self):
        """Walk through a progression plan and generate cards in order."""
        entries = self._make_vocab_entries()
        plan = ProgressionPlan(entries)
        due_positions = assign_due_positions(plan)

        stats = {"vocab": 0, "phrase": 0}
        for segment in plan.ordered_segments():
            if isinstance(segment, VocabBatch):
                for word_entry in segment.words:
                    tags = [
                        level_tag(segment.level),
                        batch_tag(segment.batch_index),
                        syllable_tag(word_entry.syllable_count),
                    ]
                    if word_entry.pos == "noun":
                        self.gen.generate_noun_card(
                            word_entry.word, word_entry.translation,
                            word_entry.declension_class or None,
                            extra_tags=tags,
                        )
                    elif word_entry.pos == "verb":
                        self.gen.generate_verb_card(
                            word_entry.word, word_entry.translation,
                            word_entry.verb_class or None,
                            extra_tags=tags,
                        )
                    stats["vocab"] += 1

            elif isinstance(segment, PhraseBatch):
                for phrase in segment.phrases:
                    target_entry = next(
                        (w for b in plan.vocab_batches
                         for w in b.words if w.word == phrase.target_word),
                        None,
                    )
                    if target_entry:
                        tags = [
                            level_tag(segment.level),
                            grammar_tag(phrase.grammar_type),
                        ]
                        self.gen.generate_sentence_cards(
                            target_entry.word,
                            target_entry.pos,
                            target_entry.translation,
                            target_entry.declension_class or None,
                            target_entry.verb_class or None,
                            grammar_filter=phrase.grammar_type,
                            max_sentences=1,
                            extra_tags=tags,
                        )
                        stats["phrase"] += 1

        self.assertEqual(stats["vocab"], len(entries))
        self.assertEqual(stats["phrase"], len(entries))  # one phrase per word

        # Verify DB has all cards
        cards = self.db.list_cards()
        self.assertGreater(len(cards), 0)

    def test_due_positions_cover_all_words(self):
        """Every word in the plan should get a due position."""
        entries = self._make_vocab_entries()
        plan = ProgressionPlan(entries)
        positions = assign_due_positions(plan)

        for vb in plan.vocab_batches:
            for w in vb.words:
                self.assertIn(w.word, positions)

    def test_tags_encode_level_and_batch(self):
        """Tags passed to Anki should encode level and batch info."""
        entries = self._make_vocab_entries()
        plan = ProgressionPlan(entries)
        vb = plan.vocab_batches[0]

        self.gen.generate_noun_card(
            vb.words[0].word,
            vb.words[0].translation,
            extra_tags=[level_tag(vb.level), batch_tag(vb.batch_index)],
        )
        call_kwargs = self.anki.add_note.call_args
        tags = call_kwargs.kwargs["tags"]
        self.assertIn("level::01", tags)
        self.assertIn("batch::000", tags)


# ─── E2E: Morphology Consistency ─────────────────────────────────────

class TestMorphologyConsistency(unittest.TestCase):
    """Verify that morphology output matches between direct calls and cards."""

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.anki = _mock_anki()
        self.gen = CardGenerator(anki=self.anki, db_path=self._tmp.name)
        self.db = CardDatabase(self._tmp.name)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_noun_card_matches_direct_declension(self):
        """Card fields should match decline_noun() output."""
        decl = decline_noun(_WORD_BOOK, "i_class", "book")
        self.gen.generate_noun_card(_WORD_BOOK, "book", "i_class")

        call_kwargs = self.anki.add_note.call_args
        fields = call_kwargs.kwargs["fields"]

        self.assertEqual(fields["NomSg"], decl.nom_sg)
        self.assertEqual(fields["NomSgDef"], decl.nom_sg_def)
        self.assertEqual(fields["GenDatSg"], decl.gen_dat_sg)
        self.assertEqual(fields["AblSg"], decl.abl_sg)
        self.assertEqual(fields["InstrSg"], decl.instr_sg)
        self.assertEqual(fields["NomPl"], decl.nom_pl)

    def test_verb_card_matches_direct_conjugation(self):
        """Card fields should match conjugate_verb() output."""
        conj = conjugate_verb(_WORD_WRITE, "e_class", "write")
        self.gen.generate_verb_card(_WORD_WRITE, "write", "e_class")

        call_kwargs = self.anki.add_note.call_args
        fields = call_kwargs.kwargs["fields"]

        self.assertEqual(fields["Pres1sg"], conj.present["1sg"])
        self.assertEqual(fields["Past1sg"], conj.past_aorist["1sg"])
        self.assertEqual(fields["Fut1sg"], conj.future["1sg"])
        self.assertEqual(fields["ImperSg"], conj.imperative_sg)
        self.assertEqual(fields["PastPart"], conj.past_participle)

    def test_sentence_matches_generator_output(self):
        """Sentence card fields should match generate_noun_sentences()."""
        sentences = generate_noun_sentences(_WORD_BOOK, "i_class", "book", 1)
        label, arm, en = sentences[0]

        self.gen.generate_sentence_cards(
            _WORD_BOOK, "noun", "book", "i_class", max_sentences=1,
        )
        call_kwargs = self.anki.add_note.call_args
        fields = call_kwargs.kwargs["fields"]

        self.assertEqual(fields["FormLabel"], label)
        self.assertEqual(fields["ArmenianSentence"], arm)
        self.assertEqual(fields["EnglishSentence"], en)


if __name__ == "__main__":
    unittest.main()
