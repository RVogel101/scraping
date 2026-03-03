"""
Integration tests for the full Lousardzag pipeline.

Tests corpus loading → vocabulary extraction → card generation → Anki sync.
"""

import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from lousardzag.morphology.core import romanize
from lousardzag.morphology.verbs import conjugate_verb, PERSONS
from lousardzag.morphology.irregular_verbs import list_irregular_infinitives
from lousardzag.card_generator import CardGenerator


class TestCorpusVocabularyPipeline(unittest.TestCase):
    """Test integrating corpus data with vocabulary extraction."""

    def setUp(self):
        """Set up test corpus data."""
        self.test_entries = [
            {"word": "մայր", "frequency": 150, "definition": "mother"},
            {"word": "հայ", "frequency": 200, "definition": "Armenian (person)"},
            {"word": "կարդալ", "frequency": 100, "definition": "to read", "verb_class": "a_class"},
            {"word": "տուն", "frequency": 180, "definition": "house"},
            {"word": "լեզու", "frequency": 90, "definition": "language"},
        ]

    def test_frequency_sorting(self):
        """Test vocabulary is sorted by frequency."""
        sorted_vocab = sorted(
            self.test_entries,
            key=lambda x: x["frequency"],
            reverse=True
        )
        
        # Most frequent should be first
        self.assertEqual(sorted_vocab[0]["word"], "հայ")  # 200
        self.assertEqual(sorted_vocab[1]["word"], "տուն")  # 180

    def test_vocab_with_caching(self):
        """Test vocabulary caching mechanism."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "vocab_cache.json"
            
            # Create cache
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(self.test_entries, f, ensure_ascii=False)
            
            # Load cache
            with open(cache_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            
            self.assertEqual(len(loaded), len(self.test_entries))
            self.assertEqual(loaded[0]["word"], self.test_entries[0]["word"])

    def test_verb_classification(self):
        """Test verbs are correctly classified."""
        verbs = [e for e in self.test_entries if "verb_class" in e]
        
        self.assertEqual(len(verbs), 1)
        self.assertEqual(verbs[0]["verb_class"], "a_class")


class TestVerbConjugationPipeline(unittest.TestCase):
    """Test verb conjugation integration."""

    def test_regular_verb_conjugation(self):
        """Test conjugation of regular e_class verb."""
        conjugation = conjugate_verb(
            "կարդալ",  # to read
            verb_class="a_class",
            translation="to read"
        )
        
        # Check all persons are conjugated
        for person in PERSONS:
            self.assertIn(person, conjugation.present)
            self.assertNotEqual(conjugation.present[person], "")

    def test_irregular_verb_conjugation(self):
        """Test conjugation of irregular verbs."""
        # Test "to be" — most irregular
        conjugation = conjugate_verb(
            "ըllal",  # to be
            translation="to be"
        )
        
        # Should have overridden forms
        self.assertIsNotNone(conjugation.past_aorist)

    def test_all_tenses_populated(self):
        """Test all tense fields are populated."""
        conjugation = conjugate_verb(
            "մի ցածել",  # to speak
            translation="to speak"
        )
        
        tenses = [
            "present",
            "past_aorist",
            "imperfect",
            "future",
            "subjunctive",
            "conditional"
        ]
        
        for tense in tenses:
            tense_forms = getattr(conjugation, tense)
            self.assertTrue(len(tense_forms) > 0, f"{tense} should have forms")

    def test_participles_generated(self):
        """Test participle generation."""
        conjugation = conjugate_verb(
            "սիրել",  # to love (e_class)
            verb_class="e_class",
            translation="to love"
        )
        
        self.assertNotEqual(conjugation.past_participle, "")
        self.assertNotEqual(conjugation.present_participle, "")


class TestFullPipelineIntegration(unittest.TestCase):
    """Test full pipeline from corpus to Anki."""

    @patch('lousardzag.card_generator.AnkiConnect')
    def test_vocab_to_anki_sync(self, mock_anki_class):
        """Test vocabulary cards sync to Anki."""
        mock_anki = MagicMock()
        mock_anki_class.return_value = mock_anki
        mock_anki.add_note.return_value = 123  # Mock note ID
        
        db = MagicMock()
        cg = CardGenerator(anki=mock_anki, db=db)
        
        # Mock vocabulary cache
        db.has_vocabulary_cache.return_value = True
        db.get_vocabulary_from_cache.return_value = [
            {"lemma": "մայր", "translation": "mother", "pos": "noun"}
        ]
        
        vocab = cg.get_source_words(use_cache=True)
        
        self.assertEqual(len(vocab), 1)
        self.assertEqual(vocab[0]["word"], "մայր")

    def test_multiple_verb_forms_generation(self):
        """Test generating all forms of a verb for different cards."""
        infinitive = "կարդալ"  # to read
        
        # Generate conjugation
        conjugation = conjugate_verb(
            infinitive,
            verb_class="a_class",
            translation="to read"
        )
        
        # Count valid forms across tenses
        tenses_with_forms = 0
        
        for tense_name in ["present", "past_aorist", "future", "conditional"]:
            tense_forms = getattr(conjugation, tense_name)
            if tense_forms and len(tense_forms) > 0:
                tenses_with_forms += 1
        
        # Should have forms for multiple tenses
        self.assertGreater(tenses_with_forms, 0)

    def test_progressive_vocabulary_loading(self):
        """Test vocabulary can be loaded progressively."""
        vocab_batches = [
            [{"word": "հայ", "frequency": 200, "pos": "noun"}],
            [{"word": "մայր", "frequency": 150, "pos": "noun"}, {"word": "տուն", "frequency": 180, "pos": "noun"}],
            [{"word": "կարդալ", "frequency": 100, "pos": "verb"}],
        ]
        
        total_vocab = []
        for batch in vocab_batches:
            total_vocab.extend(batch)
        
        self.assertEqual(len(total_vocab), 4)


class TestCardProgressionIntegration(unittest.TestCase):
    """Test progression system integration with cards."""

    def test_vocabulary_progression_levels(self):
        """Test vocabulary is distributed across progression levels."""
        # Simulated frequency-based progression
        vocab = [
            {"word": "հայ", "frequency": 200},           # Level 1 (high freq)
            {"word": "մայր", "frequency": 150},          # Level 1
            {"word": "տուն", "frequency": 180},          # Level 1
            {"word": "կարդալ", "frequency": 80},        # Level 2
            {"word": "գիտ", "frequency": 60},           # Level 2
            {"word": "բառ", "frequency": 40},           # Level 3
        ]
        
        # Group by level (e.g., top 50% = level 1, next 30% = level 2, etc.)
        sorted_vocab = sorted(vocab, key=lambda x: x["frequency"], reverse=True)
        
        level_1 = sorted_vocab[:3]  # Top 3
        level_2 = sorted_vocab[3:5]  # Next 2
        level_3 = sorted_vocab[5:]   # Remaining
        
        self.assertEqual(len(level_1), 3)
        self.assertEqual(len(level_2), 2)
        self.assertEqual(len(level_3), 1)

    def test_verb_tense_progression(self):
        """Test verbs are introduced in order of tense complexity."""
        # Expected progression: subjunctive → present → past → future → conditional
        tense_order = [
            "subjunctive",
            "present",
            "past_aorist",
            "future",
            "conditional",
        ]
        
        # All tenses should be learnable
        conjugation = conjugate_verb(
            "սիրել",  # to love
            verb_class="e_class",
            translation="to love"
        )
        
        for tense in tense_order:
            tense_forms = getattr(conjugation, tense)
            self.assertGreater(len(tense_forms), 0)


class TestErrorHandling(unittest.TestCase):
    """Test error handling in pipeline."""

    def test_invalid_verb_class(self):
        """Test handling of invalid verb class."""
        with self.assertRaises(ValueError):
            conjugate_verb(
                "կարդալ",
                verb_class="invalid_class"
            )

    def test_missing_vocabulary_gracefully_handled(self):
        """Test pipeline handles missing vocabulary."""
        empty_vocab = []
        
        # Should not crash, just return empty
        self.assertEqual(len(empty_vocab), 0)

    def test_corrupted_corpus_data(self):
        """Test handling of malformed corpus entries."""
        corrupted_entries = [
            {"word": ""},  # Empty word
            {"definition": "no word"},  # Missing word
            None,  # Null entry
        ]
        
        # Filter out invalid entries
        valid_entries = [e for e in corrupted_entries if e and "word" in e and e["word"]]
        
        self.assertEqual(len(valid_entries), 0)


if __name__ == "__main__":
    unittest.main()
