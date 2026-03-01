#!/usr/bin/env python3
"""
Tests for armenian_anki.card_generator — card generation with mocked Anki.

Uses a mock AnkiConnect client so tests run without a live Anki instance.
Covers:
  - Noun declension card generation
  - Verb conjugation card generation
  - Sentence card generation
  - POS detection
  - HTML field extraction (word, translation, syllable count)
  - Source deck reading (mocked)
  - Full process_all pipeline (mocked)

Run with:  python test_card_generator.py
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

from armenian_anki.card_generator import CardGenerator
from armenian_anki.database import CardDatabase
from armenian_anki.morphology.core import ARM


# ─── Mock AnkiConnect ─────────────────────────────────────────────────

def _mock_anki():
    """Return a mock AnkiConnect that records calls and returns plausible IDs."""
    anki = MagicMock()
    anki.ping.return_value = True
    anki.model_names.return_value = []
    anki.create_model.return_value = {}
    anki.create_deck.return_value = 1
    anki.ensure_deck.return_value = 1
    anki.deck_names.return_value = ["Default", "Armenian Vocabulary"]

    _note_counter = {"id": 1000}

    def fake_add_note(**kwargs):
        _note_counter["id"] += 1
        return _note_counter["id"]

    anki.add_note.side_effect = fake_add_note
    anki.find_notes.return_value = []
    anki.notes_info.return_value = []
    return anki


# ─── Armenian Test Words ──────────────────────────────────────────────

_WORD_BOOK = ARM["k"] + ARM["i"] + ARM["r"] + ARM["k_asp"]     # գirk' (book)
_WORD_WRITE = ARM["k"] + ARM["r"] + ARM["ye"] + ARM["l"]       # krel (write)
_WORD_SPEAK = ARM["kh"] + ARM["vo"] + ARM["s"] + ARM["ye"] + ARM["l"]  # khosel (speak)
_WORD_HOUSE = ARM["d"] + ARM["vo"] + ARM["yiwn"] + ARM["n"]    # dun (house)


# ─── POS Detection ───────────────────────────────────────────────────

class TestPOSDetection(unittest.TestCase):

    def test_verb_el_ending(self):
        self.assertEqual(CardGenerator._detect_pos(_WORD_WRITE), "verb")

    def test_verb_al_ending(self):
        word_al = ARM["kh"] + ARM["a"] + ARM["gh"] + ARM["a"] + ARM["l"]  # -al
        self.assertEqual(CardGenerator._detect_pos(word_al), "verb")

    def test_noun_default(self):
        self.assertEqual(CardGenerator._detect_pos(_WORD_BOOK), "noun")

    def test_noun_house(self):
        self.assertEqual(CardGenerator._detect_pos(_WORD_HOUSE), "noun")


# ─── HTML Extraction ─────────────────────────────────────────────────

class TestHTMLExtraction(unittest.TestCase):

    def test_extract_word_simple(self):
        html = '<div style="font-family: Arial">WORD</div>'
        self.assertEqual(CardGenerator._extract_word_from_front(html), "WORD")

    def test_extract_word_strips_spans(self):
        html = '<div style="font-family: Arial"><span style="color:green">W</span>ORD</div>'
        self.assertEqual(CardGenerator._extract_word_from_front(html), "WORD")

    def test_extract_word_comma_takes_first(self):
        html = '<div style="font-family: Arial">WORD1, WORD2</div>'
        self.assertEqual(CardGenerator._extract_word_from_front(html), "WORD1")

    def test_extract_word_strips_sound(self):
        html = '<div style="font-family: Arial">WORD[sound:file.mp3]</div>'
        self.assertEqual(CardGenerator._extract_word_from_front(html), "WORD")

    def test_extract_translation_after_hr(self):
        html = '<div>Front stuff</div><hr><div>Translation here</div>'
        self.assertEqual(
            CardGenerator._extract_translation_from_back(html),
            "Translation here",
        )

    def test_extract_translation_skips_images(self):
        html = '<div>Front</div><hr><div><img src="pic.jpg"></div><div>Answer</div>'
        self.assertEqual(
            CardGenerator._extract_translation_from_back(html),
            "Answer",
        )

    def test_extract_translation_empty(self):
        html = '<div>No HR here</div>'
        self.assertEqual(CardGenerator._extract_translation_from_back(html), "")

    def test_extract_syllable_count(self):
        html = "<div class='toggle-content'>Pat-ker</div>"
        self.assertEqual(CardGenerator._extract_syllable_count(html), 2)

    def test_extract_syllable_count_single(self):
        html = "<div class='toggle-content'>Kirk</div>"
        self.assertEqual(CardGenerator._extract_syllable_count(html), 1)

    def test_extract_syllable_count_missing(self):
        html = "<div>No toggle here</div>"
        self.assertEqual(CardGenerator._extract_syllable_count(html), 0)

    def test_clean_html_text(self):
        html = '<div>Hello &amp; <b>world</b>[sound:x.mp3]</div>'
        self.assertEqual(CardGenerator._clean_html_text(html), "Hello & world")


# ─── Noun Card Generation ────────────────────────────────────────────

class TestNounCardGeneration(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.anki = _mock_anki()
        self.gen = CardGenerator(anki=self.anki, db_path=self._tmp.name)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_generate_noun_card_returns_note_id(self):
        note_id = self.gen.generate_noun_card(_WORD_BOOK, "book")
        self.assertIsNotNone(note_id)
        self.assertIsInstance(note_id, int)

    def test_generate_noun_card_calls_anki(self):
        self.gen.generate_noun_card(_WORD_BOOK, "book")
        self.anki.add_note.assert_called_once()
        call_kwargs = self.anki.add_note.call_args
        self.assertEqual(call_kwargs.kwargs["model"], "Armenian Noun Declension")

    def test_generate_noun_card_fields_complete(self):
        self.gen.generate_noun_card(_WORD_BOOK, "book")
        call_kwargs = self.anki.add_note.call_args
        fields = call_kwargs.kwargs["fields"]
        self.assertEqual(fields["Word"], _WORD_BOOK)
        self.assertEqual(fields["Translation"], "book")
        self.assertIn("NomSg", fields)
        self.assertIn("GenDatSg", fields)
        self.assertIn("AblSg", fields)
        self.assertIn("InstrSg", fields)
        self.assertIn("NomPl", fields)

    def test_generate_noun_card_persists_to_db(self):
        self.gen.generate_noun_card(_WORD_BOOK, "book")
        db = CardDatabase(self._tmp.name)
        card = db.get_card_by_word(_WORD_BOOK, "noun_declension")
        assert card is not None
        self.assertEqual(card["translation"], "book")

    def test_generate_noun_card_with_tags(self):
        self.gen.generate_noun_card(_WORD_BOOK, "book", extra_tags=["level::01"])
        call_kwargs = self.anki.add_note.call_args
        tags = call_kwargs.kwargs["tags"]
        self.assertIn("level::01", tags)
        self.assertIn("auto-generated", tags)
        self.assertIn("declension", tags)

    def test_generate_noun_card_different_class(self):
        note_id = self.gen.generate_noun_card(_WORD_HOUSE, "house", "u_class")
        self.assertIsNotNone(note_id)
        call_kwargs = self.anki.add_note.call_args
        fields = call_kwargs.kwargs["fields"]
        self.assertEqual(fields["DeclensionClass"], "u_class")


# ─── Verb Card Generation ────────────────────────────────────────────

class TestVerbCardGeneration(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.anki = _mock_anki()
        self.gen = CardGenerator(anki=self.anki, db_path=self._tmp.name)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_generate_verb_card_returns_note_id(self):
        note_id = self.gen.generate_verb_card(_WORD_WRITE, "write")
        self.assertIsNotNone(note_id)
        self.assertIsInstance(note_id, int)

    def test_generate_verb_card_calls_anki(self):
        self.gen.generate_verb_card(_WORD_WRITE, "write")
        self.anki.add_note.assert_called_once()
        call_kwargs = self.anki.add_note.call_args
        self.assertEqual(call_kwargs.kwargs["model"], "Armenian Verb Conjugation")

    def test_generate_verb_card_fields_complete(self):
        self.gen.generate_verb_card(_WORD_WRITE, "write")
        call_kwargs = self.anki.add_note.call_args
        fields = call_kwargs.kwargs["fields"]
        self.assertEqual(fields["Infinitive"], _WORD_WRITE)
        self.assertEqual(fields["Translation"], "write")
        # Check all tense/person slots exist
        for tense in ["Pres", "Past", "Fut", "Imp"]:
            for person in ["1sg", "2sg", "3sg", "1pl", "2pl", "3pl"]:
                self.assertIn(f"{tense}{person}", fields,
                              f"Missing field: {tense}{person}")
        self.assertIn("ImperSg", fields)
        self.assertIn("ImperPl", fields)
        self.assertIn("PastPart", fields)
        self.assertIn("PresPart", fields)

    def test_generate_verb_card_persists_to_db(self):
        self.gen.generate_verb_card(_WORD_WRITE, "write")
        db = CardDatabase(self._tmp.name)
        card = db.get_card_by_word(_WORD_WRITE, "verb_conjugation")
        assert card is not None
        self.assertEqual(card["translation"], "write")

    def test_generate_verb_a_class(self):
        word_play = ARM["kh"] + ARM["a"] + ARM["gh"] + ARM["a"] + ARM["l"]
        note_id = self.gen.generate_verb_card(word_play, "play", "a_class")
        self.assertIsNotNone(note_id)
        call_kwargs = self.anki.add_note.call_args
        fields = call_kwargs.kwargs["fields"]
        self.assertEqual(fields["VerbClass"], "a_class")


# ─── Sentence Card Generation ────────────────────────────────────────

class TestSentenceCardGeneration(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.anki = _mock_anki()
        self.gen = CardGenerator(anki=self.anki, db_path=self._tmp.name)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_noun_sentences_generated(self):
        note_ids = self.gen.generate_sentence_cards(
            _WORD_BOOK, "noun", "book", "i_class",
        )
        self.assertGreater(len(note_ids), 0)

    def test_verb_sentences_generated(self):
        note_ids = self.gen.generate_sentence_cards(
            _WORD_WRITE, "verb", "write", verb_class="e_class",
        )
        self.assertGreater(len(note_ids), 0)

    def test_sentence_card_model(self):
        self.gen.generate_sentence_cards(_WORD_BOOK, "noun", "book")
        call_kwargs = self.anki.add_note.call_args
        self.assertEqual(call_kwargs.kwargs["model"], "Armenian Vocab Sentences")

    def test_sentence_card_fields(self):
        self.gen.generate_sentence_cards(_WORD_BOOK, "noun", "book")
        call_kwargs = self.anki.add_note.call_args
        fields = call_kwargs.kwargs["fields"]
        self.assertIn("Word", fields)
        self.assertIn("ArmenianSentence", fields)
        self.assertIn("EnglishSentence", fields)
        self.assertIn("FormLabel", fields)

    def test_max_sentences_limit(self):
        note_ids = self.gen.generate_sentence_cards(
            _WORD_BOOK, "noun", "book", max_sentences=2,
        )
        self.assertLessEqual(len(note_ids), 2)

    def test_grammar_filter(self):
        note_ids = self.gen.generate_sentence_cards(
            _WORD_BOOK, "noun", "book", "i_class",
            grammar_filter="nominative",
        )
        # Should produce at least 1 sentence matching "nominative"
        self.assertGreater(len(note_ids), 0)

    def test_unsupported_pos_returns_empty(self):
        note_ids = self.gen.generate_sentence_cards(
            _WORD_BOOK, "adjective", "beautiful",
        )
        self.assertEqual(note_ids, [])


# ─── Setup Models and Decks ──────────────────────────────────────────

class TestSetup(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.anki = _mock_anki()
        self.gen = CardGenerator(anki=self.anki, db_path=self._tmp.name)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_setup_models_creates_three_models(self):
        self.gen.setup_models()
        # create_model should be called 3 times (noun, verb, sentence)
        self.assertEqual(self.anki.create_model.call_count, 3)

    def test_setup_decks_creates_target(self):
        self.gen.setup_decks()
        self.anki.ensure_deck.assert_called_once()


# ─── Source Word Reading (Mocked) ─────────────────────────────────────

class TestGetSourceWords(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.anki = _mock_anki()
        self.gen = CardGenerator(anki=self.anki, db_path=self._tmp.name)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_empty_deck_returns_empty(self):
        self.anki.get_deck_notes.return_value = []
        result = self.gen.get_source_words("Empty Deck")
        self.assertEqual(result, [])

    def test_reads_notes_with_word_field(self):
        word = _WORD_BOOK
        notes = [{
            "fields": {
                "Front": {"value": f'<div style="font-family: Arial">{word}</div>'},
                "Back": {"value": f'<div>stuff</div><hr><div>book</div>'},
            }
        }]
        self.anki.get_deck_notes.return_value = notes
        result = self.gen.get_source_words(
            "Test Deck",
            field_overrides={"word": "Front", "translation": "Back"},
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["word"], word)
        self.assertEqual(result[0]["translation"], "book")

    def test_skips_phrase_cards(self):
        """Cards with spaces (phrases) should be skipped."""
        self.anki.get_deck_notes.return_value = [{
            "fields": {
                "Word": {"value": '<div style="font-family: Arial">two words</div>'},
                "Translation": {"value": "some phrase"},
            }
        }]
        result = self.gen.get_source_words("Test Deck")
        self.assertEqual(len(result), 0)

    def test_auto_detects_pos(self):
        """Verb ending should auto-detect as verb."""
        self.anki.get_deck_notes.return_value = [{
            "fields": {
                "Word": {"value": f'<div style="font-family: Arial">{_WORD_WRITE}</div>'},
                "Translation": {"value": f"<hr><div>write</div>"},
            }
        }]
        result = self.gen.get_source_words("Test Deck")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["pos"], "verb")


# ─── process_all (Mocked Full Pipeline) ──────────────────────────────

class TestProcessAll(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.anki = _mock_anki()
        self.gen = CardGenerator(anki=self.anki, db_path=self._tmp.name)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_process_all_empty_deck(self):
        self.anki.get_deck_notes.return_value = []
        stats = self.gen.process_all("Empty Deck")
        self.assertEqual(stats["total"], 0)

    def test_process_all_with_noun(self):
        self.anki.get_deck_notes.return_value = [{
            "fields": {
                "Word": {"value": f'<div style="font-family: Arial">{_WORD_BOOK}</div>'},
                "Translation": {"value": f"<hr><div>book</div>"},
            }
        }]
        stats = self.gen.process_all("Test Deck")
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["nouns"], 1)
        self.assertGreater(stats["sentences"], 0)
        self.assertEqual(stats["errors"], 0)

    def test_process_all_with_verb(self):
        self.anki.get_deck_notes.return_value = [{
            "fields": {
                "Word": {"value": f'<div style="font-family: Arial">{_WORD_WRITE}</div>'},
                "Translation": {"value": f"<hr><div>write</div>"},
            }
        }]
        stats = self.gen.process_all("Test Deck")
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["verbs"], 1)
        self.assertGreater(stats["sentences"], 0)
        self.assertEqual(stats["errors"], 0)


if __name__ == "__main__":
    unittest.main()
