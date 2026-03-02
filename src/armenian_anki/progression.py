"""
Phrase-chunking progression system for Armenian Anki card generation.

Implements a linguistically-grounded learning progression based on the
"phrase chunking" methodology:

  - Vocabulary is sorted by frequency (highest-frequency first).
  - Words are packaged into batches of VOCAB_BATCH_SIZE (default 20).
  - Each batch is followed by a phrase/sentence segment cementing that vocab.
  - Batches are grouped into LEVELS (5 batches per level = 100 words per level).

Syllable constraints per level band:
  ┌──────────────────┬───────────────────────────────────┐
  │  Levels 1–5      │  1-syllable words only            │
  │  Levels 6–10     │  1- or 2-syllable words           │
  │  Levels 11–15    │  1-, 2-, or 3-syllable words      │
  │  Levels 16+      │  No syllable restriction          │
  └──────────────────┴───────────────────────────────────┘

Phrase word-count allowance per level band:
  ┌──────────────────┬───────────────────────────────────┐
  │  Levels 1–5      │  1 vocab word per phrase          │
  │  Levels 6–10     │  up to 3 vocab words per phrase   │
  │  Levels 11–15    │  up to 4 vocab words per phrase   │
  │  Levels 16–20    │  up to 5 vocab words per phrase   │
  │  Levels 21+      │  up to 6 vocab words per phrase   │
  └──────────────────┴───────────────────────────────────┘

Grammar type diversity:
  Each phrase batch cycles through grammatical structures in a rotating
  schedule to ensure all types are represented while keeping variety.
  Levels 1–5 only use simple structures (plural, definite, indefinite).
  Later levels add cases, tenses, and multi-word constructions.

Coverage guarantee:
  Every vocab word must appear at least once in a phrase — preferably in
  the phrase segment immediately following the batch in which it was learned.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from itertools import cycle
from typing import Iterator

from .morphology.core import count_syllables
from .morphology.difficulty import score_word_difficulty
from .sentence_generator import generate_noun_sentences, generate_verb_sentences


logger = logging.getLogger(__name__)


# ─── Constants ────────────────────────────────────────────────────────

VOCAB_BATCH_SIZE: int = 20          # words per vocabulary batch
BATCHES_PER_LEVEL: int = 5          # batches per level (5×20 = 100 words/level)


# ─── Grammar Structure Types ─────────────────────────────────────────
# Used to tag phrase cards and rotate structure diversity.

GRAMMAR_SIMPLE = [
    "plural",
    "definite_article",
    "indefinite_article",
]

GRAMMAR_INTERMEDIATE = [
    "nominative_subject",
    "accusative_object",
    "genitive_dative",
    "ablative",
    "instrumental",
    "present_tense",
    "past_tense",
]

GRAMMAR_ADVANCED = [
    "future_tense",
    "imperfect_tense",
    "imperative",
    "adjective_phrase",
    "prepositional_phrase",
    "question_form",
]


# ─── Grammar Type → Sentence Label Filter ────────────────────────────
# Maps each progression grammar_type to a substring filter that matches
# the form labels produced by sentence_generator.py.
#
# Sentence generator noun labels:
#   "nominative", "nominative (indefinite)", "accusative",
#   "genitive-dative", "ablative", "instrumental", "plural nominative"
#
# Sentence generator verb labels:
#   "present 1sg", "present 3sg", "past 1sg", "future 1sg",
#   "imperative 2sg", "present 1pl", "imperfect 1sg"

GRAMMAR_TYPE_TO_FILTER: dict[str, str] = {
    # Simple (levels 1–5)
    "plural":              "plural",
    "definite_article":    "nominative",         # uses nom_sg_def
    "indefinite_article":  "indefinite",         # matches "nominative (indefinite)"
    # Intermediate (levels 6–10)
    "nominative_subject":  "nominative",
    "accusative_object":   "accusative",
    "genitive_dative":     "genitive-dative",
    "ablative":            "ablative",
    "instrumental":        "instrumental",
    "present_tense":       "present",
    "past_tense":          "past",
    # Advanced (levels 11+)
    "future_tense":        "future",
    "imperfect_tense":     "imperfect",
    "imperative":          "imperative",
    "adjective_phrase":    "nominative",         # fallback: use noun in nominative
    "prepositional_phrase": "ablative",          # fallback: ablative conveys "from"
    "question_form":       "accusative",         # fallback: "I see the ___"
}


def _allowed_grammar(level: int) -> list[str]:
    """Return the grammar structure types available at a given level."""
    if level <= 5:
        return GRAMMAR_SIMPLE
    elif level <= 10:
        return GRAMMAR_SIMPLE + GRAMMAR_INTERMEDIATE
    else:
        return GRAMMAR_SIMPLE + GRAMMAR_INTERMEDIATE + GRAMMAR_ADVANCED


# ─── Syllable / Level Band Rules ─────────────────────────────────────

def max_syllables_for_level(level: int) -> int:
    """Return the maximum syllable count allowed for new vocab at this level."""
    if level <= 5:
        return 1
    elif level <= 10:
        return 2
    elif level <= 15:
        return 3
    else:
        return 999  # no restriction


def max_vocab_words_per_phrase(level: int) -> int:
    """Return the maximum number of KNOWN vocab words that may appear in one phrase."""
    if level <= 5:
        return 1
    elif level <= 10:
        return 3
    elif level <= 15:
        return 4
    elif level <= 20:
        return 5
    else:
        return 6


# ─── Word Entry ───────────────────────────────────────────────────────

@dataclass
class WordEntry:
    """A single vocabulary word with its metadata."""
    word: str
    translation: str
    pos: str                       # "noun" | "verb" | "adjective" | etc.
    frequency_rank: int = 9999     # lower = more frequent (1 = most common)
    declension_class: str = ""
    verb_class: str = ""

    # Computed on construction; may be seeded from the Anki Syllable Guide
    syllable_count: int = field(default=0)
    
    # Morphological difficulty score (1.0–10.0, where higher = harder)
    # Computed from phonological and morphological complexity
    difficulty_score: float = field(default=0.0)

    def __post_init__(self):
        if self.syllable_count == 0:
            self.syllable_count = count_syllables(self.word)
        if self.difficulty_score == 0.0:
            self.difficulty_score = score_word_difficulty(
                self.word,
                self.pos,
                self.declension_class if self.declension_class else None,
                self.verb_class if self.verb_class else None,
            )

    def __repr__(self) -> str:
        return (f"WordEntry({self.word!r}, rank={self.frequency_rank}, "
                f"syl={self.syllable_count}, difficulty={self.difficulty_score:.2f}, "
                f"pos={self.pos})")


# ─── Batch / Level Structures ─────────────────────────────────────────

@dataclass
class VocabBatch:
    """A group of VOCAB_BATCH_SIZE words forming one vocabulary segment."""
    batch_index: int               # 0-based global batch number
    level: int                     # which level this batch belongs to
    words: list[WordEntry] = field(default_factory=list)

    @property
    def batch_within_level(self) -> int:
        """1-based position of this batch within its level (1–5)."""
        return (self.batch_index % BATCHES_PER_LEVEL) + 1

    @property
    def anki_position_start(self) -> int:
        """The Anki deck position of the first card in this batch."""
        return self.batch_index * VOCAB_BATCH_SIZE + 1


@dataclass
class PhraseBatch:
    """A group of phrase/sentence cards that follow a VocabBatch."""
    vocab_batch_index: int         # which vocab batch this reinforces
    level: int
    phrases: list[PhraseEntry] = field(default_factory=list)


@dataclass
class PhraseEntry:
    """A single phrase card specification."""
    target_word: str               # the vocab word being reinforced
    grammar_type: str              # e.g. "definite_article", "accusative_object"
    word_count_allowance: int      # max vocab words this phrase may contain
    # Additional words from prior vocab that this phrase may incorporate
    supporting_words: list[str] = field(default_factory=list)
    # Phrase text is filled in by sentence_generator at card-creation time
    armenian_sentence: str = ""
    english_sentence: str = ""


# ─── Progression Engine ───────────────────────────────────────────────

class ProgressionPlan:
    """
    Builds and holds the complete ordering plan for a vocabulary list.

    Usage::

        plan = ProgressionPlan(word_entries)
        for item in plan.ordered_segments():
            if isinstance(item, VocabBatch):
                # push vocab cards in item.words order
                ...
            elif isinstance(item, PhraseBatch):
                # push phrase cards in item.phrases order
                ...
    """

    def __init__(self, words: list[WordEntry]):
        self._raw_words = words
        self._vocab_batches: list[VocabBatch] = []
        self._phrase_batches: list[PhraseBatch] = []
        self._build()

    # ── Public API ────────────────────────────────────────────────────

    def ordered_segments(self) -> Iterator[VocabBatch | PhraseBatch]:
        """Yield (VocabBatch, PhraseBatch) pairs in learning order."""
        for vb, pb in zip(self._vocab_batches, self._phrase_batches):
            yield vb
            yield pb

    @property
    def vocab_batches(self) -> list[VocabBatch]:
        return self._vocab_batches

    @property
    def phrase_batches(self) -> list[PhraseBatch]:
        return self._phrase_batches

    def summary(self) -> str:
        """Return a human-readable summary of the progression plan."""
        lines = [
            "═" * 70,
            "  Armenian Anki — Phrase-Chunking Progression Plan",
            "═" * 70,
            f"  Total words:   {len(self._raw_words)}",
            f"  Total batches: {len(self._vocab_batches)}",
            f"  Total levels:  {self._total_levels()}",
            "",
        ]
        for level in range(1, self._total_levels() + 1):
            batches_in_level = [b for b in self._vocab_batches if b.level == level]
            word_count = sum(len(b.words) for b in batches_in_level)
            syl_limit = max_syllables_for_level(level)
            phrase_limit = max_vocab_words_per_phrase(level)
            syl_str = f"≤{syl_limit} syl" if syl_limit < 999 else "any syl"
            lines.append(
                f"  Level {level:>2}  │  {len(batches_in_level)} batch(es),"
                f" {word_count:>4} words  │  {syl_str:<8}  │  "
                f"≤{phrase_limit} vocab word(s)/phrase"
            )
        lines.append("═" * 70)
        return "\n".join(lines)

    def coverage_report(self) -> dict:
        """Return coverage statistics: which words appear in phrases."""
        all_words = {w.word for b in self._vocab_batches for w in b.words}
        covered = {p.target_word for pb in self._phrase_batches for p in pb.phrases}
        uncovered = all_words - covered
        return {
            "total_vocab": len(all_words),
            "covered_in_phrases": len(covered),
            "uncovered": sorted(uncovered),
            "coverage_pct": round(100 * len(covered) / max(len(all_words), 1), 1),
        }

    # ── Internal Build Logic ──────────────────────────────────────────

    def _build(self) -> None:
        sorted_words = self._sort_words(self._raw_words)
        # Assign syllable-gated level ordering: words that exceed the syl limit
        # for their natural batch level are deferred to the appropriate later level.
        level_sorted = self._gate_by_syllables(sorted_words)
        self._build_vocab_batches(level_sorted)
        self._build_phrase_batches()

    @staticmethod
    def _sort_words(words: list[WordEntry]) -> list[WordEntry]:
        """Primary sort: by frequency rank (ascending = most frequent first).
        Secondary sort: by syllable count (ascending = simplest first) within
        words of equal frequency rank.
        Tertiary sort: by difficulty score (ascending = least complex morphologically)
        within words of equal frequency and syllable count.
        """
        return sorted(words, key=lambda w: (w.frequency_rank, w.syllable_count, w.difficulty_score))

    @staticmethod
    def _gate_by_syllables(words: list[WordEntry]) -> list[WordEntry]:
        """Re-order so that words with more syllables than allowed at their
        natural position are deferred until the appropriate level band opens up.

        This works in passes:
          1. Assign each word a minimum level based on its syllable count.
          2. Within each level band, sort by frequency rank and difficulty score.
        """
        def min_level_for_word(w: WordEntry) -> int:
            syl = w.syllable_count
            if syl <= 1:
                return 1
            elif syl == 2:
                return 6
            elif syl == 3:
                return 11
            else:
                return 16

        # Bucket words by minimum level
        buckets: dict[int, list[WordEntry]] = {}
        for w in words:
            ml = min_level_for_word(w)
            buckets.setdefault(ml, []).append(w)

        # Sort each bucket by frequency rank, then by difficulty score
        for ml in buckets:
            buckets[ml].sort(key=lambda w: (w.frequency_rank, w.difficulty_score))

        # Flatten in level order
        result: list[WordEntry] = []
        for ml in sorted(buckets.keys()):
            result.extend(buckets[ml])
        return result

    def _build_vocab_batches(self, words: list[WordEntry]) -> None:
        """Slice the word list into fixed-size batches and assign levels."""
        self._vocab_batches = []
        for batch_idx in range(0, len(words), VOCAB_BATCH_SIZE):
            chunk = words[batch_idx: batch_idx + VOCAB_BATCH_SIZE]
            global_batch_num = batch_idx // VOCAB_BATCH_SIZE  # 0-based
            level = self._level_for_batch(global_batch_num)
            vb = VocabBatch(
                batch_index=global_batch_num,
                level=level,
                words=chunk,
            )
            self._vocab_batches.append(vb)
            logger.debug(
                f"VocabBatch {global_batch_num} (Level {level}): "
                f"{len(chunk)} words, "
                f"syl range {min(w.syllable_count for w in chunk)}–"
                f"{max(w.syllable_count for w in chunk)}"
            )

    @staticmethod
    def _level_for_batch(batch_index: int) -> int:
        """Convert a 0-based batch index to a 1-based level number."""
        return (batch_index // BATCHES_PER_LEVEL) + 1

    def _build_phrase_batches(self) -> None:
        """For each VocabBatch, build the accompanying PhraseBatch.

        Rules:
          - Every word in the current batch gets at least one phrase.
          - Grammar types rotate through allowed types for this level.
          - Supporting words are drawn from all previously-seen batches
            (up to max_vocab_words_per_phrase - 1 additional words).
          - Grammar diversity: distribute types as evenly as possible.
        """
        self._phrase_batches = []
        seen_words: list[WordEntry] = []   # accumulates as we proceed

        for vb in self._vocab_batches:
            level = vb.level
            allowed_grammar = _allowed_grammar(level)
            max_support = max_vocab_words_per_phrase(level) - 1  # slots for prior words
            grammar_rotator = cycle(allowed_grammar)

            phrases: list[PhraseEntry] = []
            current_batch_words = list(vb.words)

            for target_word in current_batch_words:
                grammar_type = next(grammar_rotator)
                word_allowance = max_vocab_words_per_phrase(level)

                # Choose supporting words from seen_words (not from current batch)
                # to avoid introducing unknown words in the phrase segment.
                support = _pick_support_words(
                    seen_words,
                    count=max_support,
                    exclude=target_word.word,
                )

                phrase = PhraseEntry(
                    target_word=target_word.word,
                    grammar_type=grammar_type,
                    word_count_allowance=word_allowance,
                    supporting_words=[w.word for w in support],
                )
                phrases.append(phrase)

            pb = PhraseBatch(
                vocab_batch_index=vb.batch_index,
                level=level,
                phrases=phrases,
            )
            self._phrase_batches.append(pb)

            # After building phrases for this batch, mark its words as seen
            seen_words.extend(current_batch_words)

    def _total_levels(self) -> int:
        if not self._vocab_batches:
            return 0
        return self._vocab_batches[-1].level


# ─── Helpers ──────────────────────────────────────────────────────────

def _pick_support_words(
    seen: list[WordEntry],
    count: int,
    exclude: str,
) -> list[WordEntry]:
    """Pick up to `count` support words from the pool of already-seen words.

    Prefers high-frequency (low rank) words so the user sees the most useful
    words most often. Excludes the target word itself.
    """
    if count <= 0 or not seen:
        return []
    pool = [w for w in seen if w.word != exclude]
    # Sort pool by frequency rank (most frequent first) then pick first `count`
    pool.sort(key=lambda w: w.frequency_rank)
    return pool[:count]


# ─── Deck Tag Helpers ─────────────────────────────────────────────────

def level_tag(level: int) -> str:
    """Return an Anki tag encoding the level, e.g. 'level::05'."""
    return f"level::{level:02d}"


def batch_tag(batch_index: int) -> str:
    """Return an Anki tag encoding the batch, e.g. 'batch::007'."""
    return f"batch::{batch_index:03d}"


def grammar_tag(grammar_type: str) -> str:
    """Return an Anki tag for a grammar structure type."""
    return f"grammar::{grammar_type}"


def syllable_tag(syllable_count: int) -> str:
    """Return an Anki tag for the syllable count, e.g. 'syl::2'."""
    return f"syl::{syllable_count}"


# ─── Anki Position Setter ─────────────────────────────────────────────

def assign_due_positions(
    plan: ProgressionPlan,
) -> dict[str, int]:
    """Return a mapping of word → Anki due position.

    The due position encodes the intended learning order.
    Vocab cards come first within each batch segment; phrase cards follow.

    Position scheme:
      Batch 0 vocab:   positions 1 – 20
      Batch 0 phrases: positions 21 – 40
      Batch 1 vocab:   positions 41 – 60
      Batch 1 phrases: positions 61 – 80
      ...

    This is used when setting the 'due' field on Anki notes so Anki
    presents them in the correct order when the deck is in 'ordered' mode.
    """
    positions: dict[str, int] = {}
    cursor = 1
    segment_size = VOCAB_BATCH_SIZE  # both vocab and phrase segments are this size

    for vb, pb in zip(plan.vocab_batches, plan.phrase_batches):
        # Vocab cards
        for word in vb.words:
            positions[word.word] = cursor
            cursor += 1
        cursor = vb.batch_index * segment_size * 2 + segment_size + 1  # phrase region

        # Phrase cards
        for phrase in pb.phrases:
            positions.setdefault(f"phrase::{phrase.target_word}", cursor)
            cursor += 1

    return positions


# ─── Phrase Sentence Filling ──────────────────────────────────────────

def sentence_filter_for(grammar_type: str) -> str:
    """Return the sentence-label substring filter for a grammar_type.

    Falls back to the grammar_type itself (with underscores replaced by
    spaces) if no explicit mapping exists.
    """
    return GRAMMAR_TYPE_TO_FILTER.get(grammar_type, grammar_type.replace("_", " "))


def fill_phrase_sentence(
    phrase: PhraseEntry,
    word_entry: WordEntry,
) -> None:
    """Fill a PhraseEntry's armenian_sentence and english_sentence fields.

    Uses sentence_generator to produce a sentence matching the phrase's
    grammar_type, then stores the first matching result in the PhraseEntry.
    """
    label_filter = sentence_filter_for(phrase.grammar_type)
    pos = word_entry.pos.lower()

    if pos in ("noun", "n"):
        sentences = generate_noun_sentences(
            word_entry.word,
            word_entry.declension_class or "i_class",
            word_entry.translation,
        )
    elif pos in ("verb", "v"):
        sentences = generate_verb_sentences(
            word_entry.word,
            word_entry.verb_class or "e_class",
            word_entry.translation,
        )
    else:
        return

    # Pick the first sentence whose label matches the filter
    for lbl, arm, eng in sentences:
        if label_filter.lower() in lbl.lower():
            phrase.armenian_sentence = arm
            phrase.english_sentence = eng
            return

    # Fallback: use the first available sentence
    if sentences:
        _, arm, eng = sentences[0]
        phrase.armenian_sentence = arm
        phrase.english_sentence = eng


def fill_plan_sentences(
    plan: ProgressionPlan,
    word_lookup: dict[str, WordEntry] | None = None,
) -> None:
    """Fill all PhraseEntry sentences in a ProgressionPlan.

    Args:
        plan: The progression plan whose phrases need sentences.
        word_lookup: Optional dict mapping word string → WordEntry.
            If not provided, one is built from the plan's vocab batches.
    """
    if word_lookup is None:
        word_lookup = {
            w.word: w
            for vb in plan.vocab_batches
            for w in vb.words
        }

    for pb in plan.phrase_batches:
        for phrase in pb.phrases:
            entry = word_lookup.get(phrase.target_word)
            if entry is not None:
                fill_phrase_sentence(phrase, entry)
