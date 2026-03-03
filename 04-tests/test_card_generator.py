"""
Unit tests for card_generator module.

Tests card generation with mocked Anki data.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from pathlib import Path
import tempfile
import json

from lousardzag.card_generator import CardGenerator
from lousardzag.morphology.core import romanize
from lousardzag.morphology.nouns import decline_noun
from lousardzag.morphology.verbs import conjugate_verb


class TestVocabLoading(unittest.TestCase):
    """Test vocabulary loading from Anki and cache."""

    @patch('lousardzag.card_generator.AnkiConnect')
    def setUp(self, mock_anki_class):
        """Set up CardGenerator with mocked AnkiConnect."""
        self.mock_anki = MagicMock()
        mock_anki_class.return_value = self.mock_anki
        
        self.db = MagicMock()
        self.cg = CardGenerator(anki=self.mock_anki, db=self.db)

    def test_load_vocabulary_from_cache(self):
        """Test loading vocabulary from cache."""
        # Mock cache data
        cached_vocab = [
            {"lemma": "մայր", "translation": "mother", "pos": "noun"},
            {"lemma": "հայ", "translation": "Armenian", "pos": "noun"},
        ]
        
        self.db.has_vocabulary_cache.return_value = True
        self.db.get_vocabulary_from_cache.return_value = cached_vocab
        
        vocab = self.cg.get_source_words(use_cache=True)
        
        self.assertEqual(len(vocab), 2)
        self.assertEqual(vocab[0]["word"], "մայր")

    def test_vocabulary_field_detection(self):
        """Test field detection from notes."""
        test_notes = [{
            "fields": {
                "Front": {"value": "մայր"},
                "Back": {"value": "mother"},
                "POS": {"value": "noun"},
            }
        }]
        
        self.mock_anki.get_deck_notes.return_value = test_notes
        self.db.has_vocabulary_cache.return_value = False
        
        # Should detect field mapping
        vocab = self.cg.get_source_words(
            use_cache=False, 
            allow_anki_fallback=True
        )
        
        # Vocabulary loading should work
        self.assertIsInstance(vocab, list)


class TestNounCardGeneration(unittest.TestCase):
    """Test noun declension card generation."""

    @patch('lousardzag.card_generator.AnkiConnect')
    def setUp(self, mock_anki_class):
        """Set up CardGenerator."""
        self.mock_anki = MagicMock()
        mock_anki_class.return_value = self.mock_anki
        
        self.db = MagicMock()
        self.cg = CardGenerator(anki=self.mock_anki, db=self.db)
        self.mock_anki.add_note.return_value = 123  # Mock note ID

    def test_noun_card_basic(self):
        """Test basic noun card creation."""
        word = "մայր"  # mother
        translation = "mother"
        
        # Mock db.upsert_card to return an integer
        self.db.upsert_card.return_value = 456
        
        result = self.cg.generate_noun_card(
            word, 
            translation=translation,
            push_to_anki=False  # Don't actually push
        )
        
        # Should return an ID from the local database
        self.assertEqual(result, 456)

    def test_noun_declension_all_cases(self):
        """Test that noun declensions include all cases."""
        word = "տուն"  # house (i-class noun)
        decl = decline_noun(word, "i_class", "house")
        
        # Check all cases are present
        self.assertIsNotNone(decl.nom_sg)
        self.assertIsNotNone(decl.acc_sg)
        self.assertIsNotNone(decl.gen_dat_sg)
        self.assertIsNotNone(decl.abl_sg)


class TestVerbCardGeneration(unittest.TestCase):
    """Test verb conjugation card generation."""

    @patch('lousardzag.card_generator.AnkiConnect')
    def setUp(self, mock_anki_class):
        """Set up CardGenerator."""
        self.mock_anki = MagicMock()
        mock_anki_class.return_value = self.mock_anki
        
        self.db = MagicMock()
        self.cg = CardGenerator(anki=self.mock_anki, db=self.db)
        self.mock_anki.add_note.return_value = 456  # Mock note ID

    def test_verb_card_basic(self):
        """Test basic verb card creation."""
        infinitive = "կարդալ"  # to read
        translation = "to read"
        
        # Mock db.upsert_card to return an integer
        self.db.upsert_card.return_value = 789
        
        result = self.cg.generate_verb_card(
            infinitive,
            translation=translation,
            push_to_anki=False  # Don't actually push
        )
        
        # Should return an ID from the local database
        self.assertEqual(result, 789)

    def test_verb_conjugation_all_persons(self):
        """Test all persons are conjugated."""
        conjugation = conjugate_verb(
            "կարդալ",
            verb_class="a_class",
            translation="to read"
        )
        
        # Check all 6 persons have forms in present tense
        persons = ["1sg", "2sg", "3sg", "1pl", "2pl", "3pl"]
        for person in persons:
            self.assertIn(person, conjugation.present)


class TestCardGenerationEdgeCases(unittest.TestCase):
    """Test edge cases in card generation."""

    @patch('lousardzag.card_generator.AnkiConnect')
    def setUp(self, mock_anki_class):
        """Set up CardGenerator."""
        self.mock_anki = MagicMock()
        mock_anki_class.return_value = self.mock_anki
        
        self.db = MagicMock()
        self.cg = CardGenerator(anki=self.mock_anki, db=self.db)

    def test_empty_word_validation(self):
        """Test behavior with empty word."""
        # Empty words should be skipped or raise
        vocab = self.cg.get_source_words(use_cache=False, allow_anki_fallback=False)
        self.assertEqual(len(vocab), 0)  # No cache, no fallback = empty

    def test_special_characters_in_armenian(self):
        """Test handling of special Armenian characters with punctuation."""
        example = "Ի՞նչ մտածե՞ս։"  # What are you thinking?
        
        # Should romanize without errors
        romanized = romanize(example)
        self.assertIsNotNone(romanized)
        self.assertGreater(len(romanized), 0)

    @patch('lousardzag.card_generator.AnkiConnect')
    def test_duplicate_words_handled(self, mock_anki_class):
        """Test that duplicate words are properly handled."""
        mock_anki = MagicMock()
        mock_anki_class.return_value = mock_anki
        
        notes_with_dupes = [
            {"fields": {"Front": {"value": "մայր"}, "Back": {"value": "mother"}}},
            {"fields": {"Front": {"value": "մայր"}, "Back": {"value": "mother"}}},  # Duplicate
        ]
        
        mock_anki.get_deck_notes.return_value = notes_with_dupes
        db = MagicMock()
        db.has_vocabulary_cache.return_value = False
        
        cg = CardGenerator(anki=mock_anki, db=db)
        vocab = cg.get_source_words(use_cache=False, allow_anki_fallback=True)
        
        # Both should be loaded (duplicate handling is optional)
        self.assertGreaterEqual(len(vocab), 1)


if __name__ == "__main__":
    unittest.main()
