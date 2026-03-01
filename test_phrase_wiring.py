#!/usr/bin/env python3
"""
Tests for phrase generation wiring and OCR-to-vocab bridge.

Covers:
  - GRAMMAR_TYPE_TO_FILTER mapping completeness
  - sentence_filter_for() function
  - fill_phrase_sentence() with nouns and verbs
  - fill_plan_sentences() for full plans
  - OCR title card parsing
  - OCR vocab extraction from records
  - vocab_to_word_entries conversion

Run with:  python test_phrase_wiring.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from armenian_anki.progression import (
    ProgressionPlan,
    WordEntry,
    PhraseEntry,
    GRAMMAR_SIMPLE,
    GRAMMAR_INTERMEDIATE,
    GRAMMAR_ADVANCED,
    GRAMMAR_TYPE_TO_FILTER,
    sentence_filter_for,
    fill_phrase_sentence,
    fill_plan_sentences,
    VOCAB_BATCH_SIZE,
)
from armenian_anki.ocr_vocab_bridge import (
    VocabEntry,
    _is_title_card,
    _parse_title_card,
    _detect_card_type,
    _normalise_pos,
    extract_vocab_from_records,
    vocab_to_word_entries,
)


# ─── Helpers ──────────────────────────────────────────────────────────

def _make_noun_entry(word="test", translation="test_word", rank=1):
    """Create a noun WordEntry using i_class characters."""
    from armenian_anki.morphology.core import ARM
    _k = ARM["k"]
    _i = ARM["i"]
    _r = ARM["r"]
    _k_asp = ARM["k_asp"]
    return WordEntry(
        word=_k + _i + _r + _k_asp,  # kirk' (book)
        translation="book",
        pos="noun",
        frequency_rank=rank,
        declension_class="i_class",
    )


def _make_verb_entry(rank=1):
    """Create a verb WordEntry."""
    from armenian_anki.morphology.core import ARM
    _k = ARM["k"]
    _r = ARM["r"]
    _ye = ARM["ye"]
    _l = ARM["l"]
    return WordEntry(
        word=_k + _r + _ye + _l,  # krel (to write)
        translation="write",
        pos="verb",
        frequency_rank=rank,
        verb_class="e_class",
    )


# ═══════════════════════════════════════════════════════════════════════
# Grammar Type Mapping Tests
# ═══════════════════════════════════════════════════════════════════════

class TestGrammarTypeMapping(unittest.TestCase):
    """Tests for GRAMMAR_TYPE_TO_FILTER and sentence_filter_for."""

    def test_all_grammar_types_have_mapping(self):
        """Every grammar type in SIMPLE + INTERMEDIATE + ADVANCED has a filter."""
        all_types = GRAMMAR_SIMPLE + GRAMMAR_INTERMEDIATE + GRAMMAR_ADVANCED
        for gt in all_types:
            self.assertIn(gt, GRAMMAR_TYPE_TO_FILTER,
                          f"Grammar type '{gt}' has no filter mapping")

    def test_sentence_filter_for_known_types(self):
        self.assertEqual(sentence_filter_for("plural"), "plural")
        self.assertEqual(sentence_filter_for("definite_article"), "nominative")
        self.assertEqual(sentence_filter_for("indefinite_article"), "indefinite")
        self.assertEqual(sentence_filter_for("accusative_object"), "accusative")
        self.assertEqual(sentence_filter_for("present_tense"), "present")
        self.assertEqual(sentence_filter_for("past_tense"), "past")
        self.assertEqual(sentence_filter_for("future_tense"), "future")
        self.assertEqual(sentence_filter_for("imperative"), "imperative")

    def test_sentence_filter_for_unknown_type_falls_back(self):
        """Unknown grammar types fall back to underscore→space replacement."""
        self.assertEqual(sentence_filter_for("unknown_type"), "unknown type")

    def test_filter_values_match_sentence_labels(self):
        """Each filter value should be a substring of at least one sentence label."""
        # Noun sentence labels
        noun_labels = [
            "nominative", "nominative (indefinite)", "accusative",
            "genitive-dative", "ablative", "instrumental", "plural nominative",
        ]
        # Verb sentence labels
        verb_labels = [
            "present 1sg", "present 3sg", "past 1sg", "future 1sg",
            "imperative 2sg", "present 1pl", "imperfect 1sg",
        ]
        all_labels = noun_labels + verb_labels

        for gt, filter_val in GRAMMAR_TYPE_TO_FILTER.items():
            matches = [lbl for lbl in all_labels if filter_val.lower() in lbl.lower()]
            self.assertTrue(
                len(matches) > 0,
                f"Filter '{filter_val}' (from '{gt}') matches no sentence label"
            )


# ═══════════════════════════════════════════════════════════════════════
# Phrase Sentence Filling Tests
# ═══════════════════════════════════════════════════════════════════════

class TestFillPhraseSentence(unittest.TestCase):
    """Tests for fill_phrase_sentence."""

    def test_fill_noun_nominative(self):
        entry = _make_noun_entry()
        phrase = PhraseEntry(
            target_word=entry.word,
            grammar_type="definite_article",
            word_count_allowance=1,
        )
        fill_phrase_sentence(phrase, entry)
        self.assertTrue(phrase.armenian_sentence, "Armenian sentence should be filled")
        self.assertTrue(phrase.english_sentence, "English sentence should be filled")
        self.assertIn("book", phrase.english_sentence.lower())

    def test_fill_noun_accusative(self):
        entry = _make_noun_entry()
        phrase = PhraseEntry(
            target_word=entry.word,
            grammar_type="accusative_object",
            word_count_allowance=1,
        )
        fill_phrase_sentence(phrase, entry)
        self.assertIn("see", phrase.english_sentence.lower())

    def test_fill_noun_plural(self):
        entry = _make_noun_entry()
        phrase = PhraseEntry(
            target_word=entry.word,
            grammar_type="plural",
            word_count_allowance=1,
        )
        fill_phrase_sentence(phrase, entry)
        self.assertIn("big", phrase.english_sentence.lower())

    def test_fill_verb_present(self):
        entry = _make_verb_entry()
        phrase = PhraseEntry(
            target_word=entry.word,
            grammar_type="present_tense",
            word_count_allowance=1,
        )
        fill_phrase_sentence(phrase, entry)
        self.assertTrue(phrase.armenian_sentence)
        self.assertIn("write", phrase.english_sentence.lower())

    def test_fill_verb_past(self):
        entry = _make_verb_entry()
        phrase = PhraseEntry(
            target_word=entry.word,
            grammar_type="past_tense",
            word_count_allowance=1,
        )
        fill_phrase_sentence(phrase, entry)
        self.assertIn("wrote", phrase.english_sentence.lower())

    def test_fill_verb_imperative(self):
        entry = _make_verb_entry()
        phrase = PhraseEntry(
            target_word=entry.word,
            grammar_type="imperative",
            word_count_allowance=1,
        )
        fill_phrase_sentence(phrase, entry)
        self.assertIn("write", phrase.english_sentence.lower())

    def test_fill_unknown_pos_does_nothing(self):
        entry = WordEntry("test", "test", "particle", frequency_rank=1)
        phrase = PhraseEntry(
            target_word="test",
            grammar_type="plural",
            word_count_allowance=1,
        )
        fill_phrase_sentence(phrase, entry)
        self.assertEqual(phrase.armenian_sentence, "")
        self.assertEqual(phrase.english_sentence, "")

    def test_fill_falls_back_to_first_sentence(self):
        """When no label matches, falls back to the first available sentence."""
        entry = _make_noun_entry()
        phrase = PhraseEntry(
            target_word=entry.word,
            grammar_type="question_form",  # maps to "accusative"
            word_count_allowance=1,
        )
        fill_phrase_sentence(phrase, entry)
        self.assertTrue(phrase.armenian_sentence)


class TestFillPlanSentences(unittest.TestCase):
    """Tests for fill_plan_sentences."""

    def _make_plan_words(self, count=20):
        """Create noun WordEntry objects for plan building."""
        from armenian_anki.morphology.core import ARM
        words = []
        for i in range(count):
            # Use a simple pattern: alternate between two real word stems
            word = ARM["k"] + ARM["i"] + ARM["r"] + ARM["k_asp"]  # kirk'
            words.append(WordEntry(
                word=word,
                translation=f"word{i}",
                pos="noun",
                frequency_rank=i + 1,
                declension_class="i_class",
                syllable_count=1,
            ))
        return words

    def test_fill_plan_populates_phrases(self):
        words = self._make_plan_words(20)
        plan = ProgressionPlan(words)

        # Before filling: all phrases have empty sentences
        for pb in plan.phrase_batches:
            for phrase in pb.phrases:
                self.assertEqual(phrase.armenian_sentence, "")

        fill_plan_sentences(plan)

        # After filling: all phrases should have sentences
        filled = sum(
            1 for pb in plan.phrase_batches
            for p in pb.phrases if p.armenian_sentence
        )
        total = sum(len(pb.phrases) for pb in plan.phrase_batches)
        self.assertEqual(filled, total, "Not all phrases were filled")


# ═══════════════════════════════════════════════════════════════════════
# OCR Bridge Tests
# ═══════════════════════════════════════════════════════════════════════

class TestTitleCardDetection(unittest.TestCase):
    """Tests for _is_title_card."""

    def test_title_card_detected(self):
        text = (
            "Centre for Western Armenian Studies Արdelays "
            "Կaylag gay-lag (Noun) Drop The \u00abWord of the Day\u00bb "
            "is the intellectual property of the Centre for Western "
            "Armenian Studies, and any use of it..."
        )
        self.assertTrue(_is_title_card(text))

    def test_non_title_card(self):
        text = "Etymology It derives from some root."
        self.assertFalse(_is_title_card(text))


class TestCardTypeDetection(unittest.TestCase):
    """Tests for _detect_card_type."""

    def test_etymology(self):
        self.assertEqual(_detect_card_type("Etymology It derives from..."), "etymology")

    def test_word_breakdown(self):
        self.assertEqual(_detect_card_type("Word breakdown ատ + delays"), "word_breakdown")

    def test_example(self):
        self.assertEqual(_detect_card_type("Example Some sentence here"), "example")

    def test_declension(self):
        self.assertEqual(_detect_card_type("Declension Singular Plural delays"), "declension")

    def test_conjugation(self):
        self.assertEqual(_detect_card_type("Conjugation Present tense delays"), "conjugation")

    def test_title(self):
        text = "delays (Noun) Something The \u00abWord of the Day\u00bb is the intellectual property of the Centre for Western Armenian Studies"
        self.assertEqual(_detect_card_type(text), "title")


class TestNormalisePOS(unittest.TestCase):
    def test_noun(self):
        self.assertEqual(_normalise_pos("Noun"), "noun")

    def test_verb(self):
        self.assertEqual(_normalise_pos("Verb"), "verb")

    def test_adjective(self):
        self.assertEqual(_normalise_pos("Adjective"), "adjective")

    def test_noun_and_verb(self):
        self.assertEqual(_normalise_pos("Noun and verb"), "noun")

    def test_adjective_and_noun(self):
        self.assertEqual(_normalise_pos("Adjective and noun"), "adjective")


class TestParseTitleCard(unittest.TestCase):
    """Tests for _parse_title_card."""

    def test_full_title_card(self):
        text = (
            "Centre for Western Armenian Studies "
            "\u0531\u0580\u0565\u0582\u0574\u057f\u0561\u0570\u0561\u0575\u0561\u0563\u056b\u057f\u0561\u056f\u0561\u0576 "
            "\u0548\u0582\u057d\u0574\u0561\u0576\u0581 \u053f\u0565\u0564\u0580\u0578\u0576 "
            "\u053f\u0561\u0575\u056c\u0561\u056f gay-lag (Noun) Drop (formal) "
            "The \u00abWord of the Day\u00bb is the intellectual property of the "
            "Centre for Western Armenian Studies, and any use of it."
        )
        result = _parse_title_card(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["armenian_word"], "\u053f\u0561\u0575\u056c\u0561\u056f")
        self.assertEqual(result["transliteration"], "gay-lag")
        self.assertEqual(result["pos"], "noun")
        self.assertIn("Drop", result["translation"])

    def test_verb_title_card(self):
        text = (
            "Centre for Western Armenian Studies "
            "\u0531\u0580\u0565\u0582\u0574\u057f\u0561\u0570\u0561\u0575\u0561\u0563\u056b\u057f\u0561\u056f\u0561\u0576 "
            "\u0548\u0582\u057d\u0574\u0561\u0576\u0581 \u053f\u0565\u0564\u0580\u0578\u0576 "
            "\u053f\u0578\u0580\u0566\u0565\u056c gor-zel (Verb) 1. To extort 3. To glean "
            "The \u00abWord of the Day\u00bb is the intellectual property of the "
            "Centre for Western Armenian Studies, and any use of it."
        )
        result = _parse_title_card(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["pos"], "verb")
        self.assertIn("extort", result["translation"].lower())

    def test_no_armenian_word(self):
        text = (
            "Centre for Western Armenian Studies "
            "\u0531\u0580\u0565\u0582\u0574\u057f\u0561\u0570\u0561\u0575\u0561\u0563\u056b\u057f\u0561\u056f\u0561\u0576 "
            "\u0548\u0582\u057d\u0574\u0561\u0576\u0581 \u053f\u0565\u0564\u0580\u0578\u0576 "
            "a-del (Verb) "
            "The \u00abWord of the Day\u00bb is the intellectual property of the "
            "Centre for Western Armenian Studies, and any use of it."
        )
        result = _parse_title_card(text)
        # Should still succeed with transliteration even without Armenian word
        self.assertIsNotNone(result)
        self.assertEqual(result["transliteration"], "a-del")

    def test_empty_text_returns_none(self):
        text = (
            "Centre for Western Armenian Studies "
            "The \u00abWord of the Day\u00bb is the intellectual property of the "
            "Centre for Western Armenian Studies"
        )
        result = _parse_title_card(text)
        # Might return None or a minimal result — should not crash
        # No Armenian word, no transliteration → None
        self.assertIsNone(result)


class TestExtractVocabFromRecords(unittest.TestCase):
    """Tests for extract_vocab_from_records."""

    def _make_records(self):
        """Build sample OCR records mimicking real CWAS data."""
        return [
            # CWAS 0012 — title card
            {
                "filename": "CWAS_0012_2026-02-05.jpg",
                "cwas_number": "0012",
                "date": "2026-02-05",
                "text": (
                    "Centre for Western Armenian Studies "
                    "\u0531\u0580\u0565\u0582\u0574\u057f\u0561\u0570\u0561\u0575\u0561\u0563\u056b\u057f\u0561\u056f\u0561\u0576 "
                    "\u0548\u0582\u057d\u0574\u0561\u0576\u0581 \u053f\u0565\u0564\u0580\u0578\u0576 "
                    "\u053f\u0561\u0575\u056c\u0561\u056f gay-lag (Noun) Drop (formal) "
                    "The \u00abWord of the Day\u00bb is the intellectual property of the "
                    "Centre for Western Armenian Studies, and any use."
                ),
                "confidence": 94.5,
            },
            # CWAS 0012 — etymology card
            {
                "filename": "CWAS_0011_2026-02-06.jpg",
                "cwas_number": "0012",
                "date": "2026-02-06",
                "text": 'Etymology It derives from "\u056f\u0561\u0569\u056c\u0561\u056f"',
                "confidence": 92.0,
            },
            # CWAS 0015 — title card (verb)
            {
                "filename": "CWAS_0015_2026-02-05.jpg",
                "cwas_number": "0015",
                "date": "2026-02-05",
                "text": (
                    "Centre for Western Armenian Studies "
                    "\u0531\u0580\u0565\u0582\u0574\u057f\u0561\u0570\u0561\u0575\u0561\u0563\u056b\u057f\u0561\u056f\u0561\u0576 "
                    "\u0548\u0582\u057d\u0574\u0561\u0576\u0581 \u053f\u0565\u0564\u0580\u0578\u0576 "
                    "a-del (Verb) "
                    "The \u00abWord of the Day\u00bb is the intellectual property of the "
                    "Centre for Western Armenian Studies, and any use."
                ),
                "confidence": 94.9,
            },
            # CWAS 0015 — word breakdown card
            {
                "filename": "CWAS_0014_2026-02-06.jpg",
                "cwas_number": "0015",
                "date": "2026-02-06",
                "text": (
                    'Word breakdown \u0561\u057f + \u0565\u056c '
                    '"\u0531\u057f" derives from Indo-European sources. '
                    '"\u0535\u056c" is the verb ending of the first group of verbs.'
                ),
                "confidence": 95.0,
            },
        ]

    def test_extract_finds_title_cards(self):
        records = self._make_records()
        entries = extract_vocab_from_records(records)
        self.assertEqual(len(entries), 2)

    def test_extract_noun_entry(self):
        records = self._make_records()
        entries = extract_vocab_from_records(records)
        noun_entry = next((e for e in entries if e.cwas_number == "0012"), None)
        self.assertIsNotNone(noun_entry)
        self.assertEqual(noun_entry.armenian_word, "\u053f\u0561\u0575\u056c\u0561\u056f")
        self.assertEqual(noun_entry.pos, "noun")

    def test_extract_verb_entry(self):
        records = self._make_records()
        entries = extract_vocab_from_records(records)
        verb_entry = next((e for e in entries if e.cwas_number == "0015"), None)
        self.assertIsNotNone(verb_entry)
        self.assertEqual(verb_entry.pos, "verb")

    def test_extract_with_empty_records(self):
        entries = extract_vocab_from_records([])
        self.assertEqual(len(entries), 0)


class TestVocabToWordEntries(unittest.TestCase):
    """Tests for vocab_to_word_entries."""

    def test_conversion(self):
        entries = [
            VocabEntry(
                armenian_word="\u053f\u0561\u0575\u056c\u0561\u056f",
                transliteration="gay-lag",
                pos="noun",
                translation="drop",
                cwas_number="0012",
            ),
        ]
        word_entries = vocab_to_word_entries(entries)
        self.assertEqual(len(word_entries), 1)
        self.assertEqual(word_entries[0].word, "\u053f\u0561\u0575\u056c\u0561\u056f")
        self.assertEqual(word_entries[0].translation, "drop")
        self.assertEqual(word_entries[0].pos, "noun")
        self.assertGreater(word_entries[0].syllable_count, 0)

    def test_skips_entries_without_word(self):
        entries = [
            VocabEntry(
                armenian_word="",
                transliteration="a-del",
                pos="verb",
                translation="to hate",
            ),
        ]
        word_entries = vocab_to_word_entries(entries)
        self.assertEqual(len(word_entries), 0)


if __name__ == "__main__":
    unittest.main()
