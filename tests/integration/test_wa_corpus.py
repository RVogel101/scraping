"""Tests for the Western Armenian tokenizer and corpus pipeline components."""

import pytest
from collections import Counter

from wa_corpus.tokenizer import (
    normalize_armenian,
    tokenize_armenian,
    count_frequencies,
    filter_by_min_length,
    is_armenian_word,
)


# ─── normalize_armenian ──────────────────────────────────────────────

class TestNormalize:
    def test_lowercase_armenian_capitals(self):
        # Ա (U+0531) → ա (U+0561)
        assert normalize_armenian("\u0531\u0532\u0533") == "\u0561\u0562\u0563"

    def test_preserves_lowercase(self):
        text = "\u0561\u0562\u0563"  # ադdelays already lowercase
        assert normalize_armenian(text) == text

    def test_mixed_case(self):
        # Բdelays (capital Բ) → բdelays (lowercase)
        result = normalize_armenian("\u0532\u0561\u057c")
        assert result == "\u0562\u0561\u057c"

    def test_ligature_decomposition(self):
        # ﬓ (U+FB13) → մն
        assert normalize_armenian("\uFB13") == "\u0574\u0576"

    def test_non_armenian_passthrough(self):
        assert normalize_armenian("hello 123") == "hello 123"

    def test_mixed_scripts(self):
        result = normalize_armenian("Hello \u0531\u0561 world")
        assert result == "Hello \u0561\u0561 world"


# ─── tokenize_armenian ───────────────────────────────────────────────

class TestTokenize:
    def test_simple_armenian_text(self):
        # "ես բdelays եdelays" (I word am)
        tokens = tokenize_armenian("\u0565\u057d \u0562\u0561\u057c \u0565\u0574")
        assert tokens == ["\u0565\u057d", "\u0562\u0561\u057c", "\u0565\u0574"]

    def test_strips_latin(self):
        tokens = tokenize_armenian("The word \u0562\u0561\u057c means word")
        assert tokens == ["\u0562\u0561\u057c"]

    def test_strips_digits(self):
        tokens = tokenize_armenian("123 \u0562\u0561\u057c 456")
        assert tokens == ["\u0562\u0561\u057c"]

    def test_strips_punctuation(self):
        tokens = tokenize_armenian("\u0562\u0561\u057c\u0589 \u0565\u0574\u055d")
        # Armenian full stop (։ U+0589) and comma (՝ U+055D) stripped
        assert tokens == ["\u0562\u0561\u057c", "\u0565\u0574"]

    def test_uppercase_normalized(self):
        # Capital Ε → lowercase
        tokens = tokenize_armenian("\u0531\u0576\u056f\u056b")
        assert tokens == ["\u0561\u0576\u056f\u056b"]

    def test_empty_input(self):
        assert tokenize_armenian("") == []

    def test_no_armenian(self):
        assert tokenize_armenian("Hello world 123!") == []


# ─── count_frequencies ────────────────────────────────────────────────

class TestCountFrequencies:
    def test_single_document(self):
        texts = ["\u0562\u0561\u057c \u0562\u0561\u057c \u0565\u0574"]
        freq = count_frequencies(texts)
        assert freq["\u0562\u0561\u057c"] == 2
        assert freq["\u0565\u0574"] == 1

    def test_multiple_documents(self):
        texts = [
            "\u0562\u0561\u057c \u0565\u0574",
            "\u0562\u0561\u057c \u056f\u0561\u0574",
        ]
        freq = count_frequencies(texts)
        assert freq["\u0562\u0561\u057c"] == 2
        assert freq["\u0565\u0574"] == 1
        assert freq["\u056f\u0561\u0574"] == 1

    def test_empty_input(self):
        freq = count_frequencies([])
        assert len(freq) == 0

    def test_returns_counter(self):
        freq = count_frequencies(["\u0562\u0561\u057c"])
        assert isinstance(freq, Counter)


# ─── filter_by_min_length ─────────────────────────────────────────────

class TestFilterMinLength:
    def test_removes_single_char(self):
        freq = Counter({"\u0561": 100, "\u0562\u0561\u057c": 50})
        filtered = filter_by_min_length(freq, min_len=2)
        assert "\u0561" not in filtered
        assert "\u0562\u0561\u057c" in filtered

    def test_custom_min_length(self):
        freq = Counter({"\u0561\u0562": 10, "\u0561\u0562\u0563": 5})
        filtered = filter_by_min_length(freq, min_len=3)
        assert "\u0561\u0562" not in filtered
        assert "\u0561\u0562\u0563" in filtered


# ─── is_armenian_word ─────────────────────────────────────────────────

class TestIsArmenianWord:
    def test_armenian_word(self):
        assert is_armenian_word("\u0562\u0561\u057c") is True

    def test_latin_word(self):
        assert is_armenian_word("hello") is False

    def test_mixed(self):
        assert is_armenian_word("\u0562\u0561\u057chello") is False

    def test_empty(self):
        assert is_armenian_word("") is False

    def test_single_armenian_char(self):
        assert is_armenian_word("\u0561") is True


# ─── Wiki text cleaning (import and basic test) ──────────────────────

class TestWikiCleaning:
    def test_clean_wikitext_removes_templates(self):
        from wa_corpus.wiki_processor import _clean_wikitext

        text = "Hello {{template|arg}} world"
        assert "template" not in _clean_wikitext(text)

    def test_clean_wikitext_converts_links(self):
        from wa_corpus.wiki_processor import _clean_wikitext

        text = "See [[Page|display text]] here"
        result = _clean_wikitext(text)
        assert "display text" in result
        assert "[[" not in result

    def test_clean_wikitext_strips_bold_italic(self):
        from wa_corpus.wiki_processor import _clean_wikitext

        text = "This is '''bold''' and ''italic''"
        result = _clean_wikitext(text)
        assert "'''" not in result
        assert "bold" in result

    def test_redirect_returns_empty(self):
        from wa_corpus.wiki_processor import _clean_wikitext

        text = "#REDIRECT [[Other page]]"
        assert _clean_wikitext(text) == ""


# ─── Frequency aggregation ───────────────────────────────────────────

class TestAggregation:
    def test_aggregate_basic(self):
        from wa_corpus.frequency_aggregator import aggregate_frequencies

        wiki = Counter({"\u0562\u0561\u057c": 100, "\u0565\u0574": 50})
        news = Counter({"\u0562\u0561\u057c": 200, "\u056f\u0561\u0574": 30})
        nayiri = {"\u0562\u0561\u057c", "\u0565\u0574", "\u056f\u0561\u0574"}

        entries = aggregate_frequencies(wiki, news, nayiri, min_count=1)

        # Should have all 3 words
        words = {e["word"] for e in entries}
        assert "\u0562\u0561\u057c" in words
        assert "\u0565\u0574" in words
        assert "\u056f\u0561\u0574" in words

        # First entry should be the most frequent
        assert entries[0]["word"] == "\u0562\u0561\u057c"

    def test_aggregate_respects_min_count(self):
        from wa_corpus.frequency_aggregator import aggregate_frequencies

        wiki = Counter({"\u0562\u0561\u057c": 1})  # only 1 occurrence
        entries = aggregate_frequencies(wiki, Counter(), set(), min_count=5)
        # Should be filtered out (not in nayiri either)
        assert len(entries) == 0

    def test_nayiri_preserves_rare_words(self):
        from wa_corpus.frequency_aggregator import aggregate_frequencies

        wiki = Counter({"\u0562\u0561\u057c": 1})
        nayiri = {"\u0562\u0561\u057c"}
        entries = aggregate_frequencies(wiki, Counter(), nayiri, min_count=5)
        # Should be kept because it's in nayiri
        assert len(entries) == 1

    def test_ranking_order(self):
        from wa_corpus.frequency_aggregator import aggregate_frequencies

        wiki = Counter({
            "\u0561": 1000,  # single char — but we're testing aggregation, not filtering
            "\u0562\u0561\u057c": 500,
            "\u0565\u0574": 100,
        })
        entries = aggregate_frequencies(wiki, Counter(), set(), min_count=1)

        ranks = {e["word"]: e["rank"] for e in entries}
        assert ranks["\u0561"] < ranks["\u0562\u0561\u057c"]
        assert ranks["\u0562\u0561\u057c"] < ranks["\u0565\u0574"]

    def test_source_weighting(self):
        from wa_corpus.frequency_aggregator import aggregate_frequencies

        # Newspapers have 1.5x weight
        wiki = Counter({"\u0562\u0561\u057c": 100})
        news = Counter({"\u0565\u0574": 100})

        entries = aggregate_frequencies(wiki, news, set(), min_count=1)
        word_counts = {e["word"]: e["total_count"] for e in entries}

        # em (աsb only) should have higher weighted count than bar (wiki only)
        assert word_counts["\u0565\u0574"] > word_counts["\u0562\u0561\u057c"]
