#!/usr/bin/env python3
"""
Armenian Anki Card Generator — Main Entry Point

Reads vocabulary from an existing Anki deck, generates morphological forms
(noun declensions, verb conjugations, definite/indefinite articles, example
sentences) and pushes the results back to Anki via AnkiConnect.

Prerequisites:
  1. Anki desktop running with AnkiConnect plugin (code: 2055492159)
  2. A source deck with Armenian vocabulary (configure in armenian_anki/config.py)
  3. Each note should have fields: Word, PartOfSpeech, Translation

Usage:
  python generate_anki_cards.py                    # process full deck
  python generate_anki_cards.py --word գիրք --pos noun --translation book
  python generate_anki_cards.py --word գրել --pos verb --translation write
  python generate_anki_cards.py --demo             # run demo without Anki
"""

import argparse
import logging
import sys

from armenian_anki.anki_connect import AnkiConnect, AnkiConnectError
from armenian_anki.card_generator import CardGenerator
from armenian_anki.morphology.nouns import decline_noun, DECLENSION_CLASSES
from armenian_anki.morphology.verbs import conjugate_verb, VERB_CLASSES
from armenian_anki.morphology.articles import add_definite, add_indefinite
from armenian_anki.sentence_generator import generate_noun_sentences, generate_verb_sentences
from armenian_anki.config import SOURCE_DECK, TARGET_DECK
from armenian_anki.progression import (
    ProgressionPlan, WordEntry, VocabBatch, PhraseBatch,
    level_tag, batch_tag, grammar_tag, syllable_tag,
    assign_due_positions,
)

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def run_demo():
    """Run a demonstration of the morphology engine without requiring Anki."""
    print("=" * 80)
    print("  Armenian Morphology Engine — Demo")
    print("=" * 80)

    # ── Noun Declension Demo ──
    # Using common Western Armenian words
    from armenian_anki.morphology.core import ARM
    _k = ARM["k"]         # dles (WA: k)
    _i = ARM["i"]         # dles
    _r = ARM["r"]         # dles
    _k_asp = ARM["k_asp"] # dles (k')
    _d = ARM["d"]         # dles (WA: d)
    _vo = ARM["vo"]       # dles
    _yiwn = ARM["yiwn"]   # dles
    _n = ARM["n"]         # dles
    _t = ARM["t"]         # dles (WA: t)

    word_book = _k + _i + _r + _k_asp               # delays (kirk' = book)
    word_house = _t + _vo + _yiwn + _n               # delays (tun = house)

    print("\n--- Noun Declension ---")
    for word, trans in [(word_book, "book"), (word_house, "house")]:
        decl = decline_noun(word, "i_class", trans)
        print(f"\n{decl.summary_table()}")

    # ── Article Demo ──
    print("\n--- Article Formation ---")
    for word, trans in [(word_book, "book"), (word_house, "house")]:
        print(f"  {word} ({trans}):")
        print(f"    Definite:   {add_definite(word)}")
        print(f"    Indefinite: {add_indefinite(word)}")

    # ── Verb Conjugation Demo ──
    _ye = ARM["ye"]
    _l = ARM["l"]
    _s = ARM["s"]
    _a = ARM["a"]
    _kh = ARM["kh"]
    _g = ARM["g"]         # dles (WA: g)

    word_write = _k + _r + _ye + _l                  # delays (krel = to write)
    word_speak = _kh + _vo + _s + _ye + _l           # delays (khosel = to speak)

    print("\n--- Verb Conjugation ---")
    for word, trans in [(word_write, "write"), (word_speak, "speak")]:
        conj = conjugate_verb(word, "e_class", trans)
        print(f"\n{conj.summary_table()}")

    # ── Sentence Generation Demo ──
    print("\n--- Example Sentences (Noun) ---")
    sentences = generate_noun_sentences(word_book, "i_class", "book", max_sentences=7)
    for case_label, arm_sent, en_sent in sentences:
        print(f"  [{case_label}]")
        print(f"    ARM: {arm_sent}")
        print(f"    ENG: {en_sent}")

    print("\n--- Example Sentences (Verb) ---")
    sentences = generate_verb_sentences(word_write, "e_class", "write", max_sentences=7)
    for tense_label, arm_sent, en_sent in sentences:
        print(f"  [{tense_label}]")
        print(f"    ARM: {arm_sent}")
        print(f"    ENG: {en_sent}")

    print("\n" + "=" * 80)
    print("Available declension classes:", list(DECLENSION_CLASSES.keys()))
    print("Available verb classes:", list(VERB_CLASSES.keys()))
    print("=" * 80)


def run_single_word(word: str, pos: str, translation: str,
                    declension_class: str = None, verb_class: str = None,
                    no_anki: bool = False):
    """Process a single word and optionally push to Anki."""
    print(f"\nProcessing: {word} ({pos}) — {translation}")
    print("-" * 60)

    if pos.lower() in ("noun", "n"):
        cls = declension_class or "i_class"
        decl = decline_noun(word, cls, translation)
        print(decl.summary_table())

        print("\nSentences:")
        for label, arm, en in generate_noun_sentences(word, cls, translation):
            print(f"  [{label}] {arm}")
            print(f"           {en}")

        if not no_anki:
            _push_to_anki_single(word, pos, translation, declension_class, verb_class)

    elif pos.lower() in ("verb", "v"):
        cls = verb_class or "e_class"
        conj = conjugate_verb(word, cls, translation)
        print(conj.summary_table())

        print("\nSentences:")
        for label, arm, en in generate_verb_sentences(word, cls, translation):
            print(f"  [{label}] {arm}")
            print(f"           {en}")

        if not no_anki:
            _push_to_anki_single(word, pos, translation, declension_class, verb_class)

    else:
        print(f"Unsupported part of speech: {pos}")
        print("Supported: noun, verb")


def _push_to_anki_single(word, pos, translation, declension_class, verb_class):
    """Push a single word's cards to Anki."""
    try:
        anki = AnkiConnect()
        if not anki.ping():
            print("\n⚠ Cannot connect to AnkiConnect. Is Anki running?")
            return

        gen = CardGenerator(anki)
        gen.setup_models()
        gen.setup_decks()

        if pos.lower() in ("noun", "n"):
            gen.generate_noun_card(word, translation, declension_class)
        elif pos.lower() in ("verb", "v"):
            gen.generate_verb_card(word, translation, verb_class)

        gen.generate_sentence_cards(word, pos, translation, declension_class, verb_class)
        print("\n✓ Cards pushed to Anki successfully")

    except AnkiConnectError as exc:
        print(f"\n✗ AnkiConnect error: {exc}")


def run_full_pipeline(source_deck: str = None):
    """Process all words in the source deck."""
    try:
        anki = AnkiConnect()
        if not anki.ping():
            print("✗ Cannot connect to AnkiConnect. Is Anki running with the AnkiConnect plugin?")
            print("  Install AnkiConnect: Tools → Add-ons → Get Add-ons → Code: 2055492159")
            sys.exit(1)

        gen = CardGenerator(anki)
        stats = gen.process_all(source_deck)

        print("\n" + "=" * 60)
        print("  Card Generation Complete")
        print("=" * 60)
        print(f"  Total words processed: {stats['total']}")
        print(f"  Noun declension cards: {stats['nouns']}")
        print(f"  Verb conjugation cards: {stats['verbs']}")
        print(f"  Sentence cards:         {stats['sentences']}")
        print(f"  Errors:                 {stats['errors']}")
        print("=" * 60)

    except AnkiConnectError as exc:
        print(f"✗ AnkiConnect error: {exc}")
        sys.exit(1)


def run_progression_pipeline(source_deck: str = None, dry_run: bool = False):
    """Build a phrase-chunking progression plan and push ordered cards to Anki.

    Each vocabulary word is assigned to a batch and level based on:
      - Frequency rank (most frequent first)
      - Syllable count gate (1-syl only for levels 1–5, etc.)

    Cards are pushed in interleaved vocab→phrase segments, with Anki due
    positions set so the deck plays back in the correct learning order.

    Pass dry_run=True to print the plan without touching Anki.
    """
    try:
        anki = AnkiConnect()
        if not dry_run and not anki.ping():
            print("✗ Cannot connect to AnkiConnect. Is Anki running with the AnkiConnect plugin?")
            print("  Install AnkiConnect: Tools → Add-ons → Get Add-ons → Code: 2055492159")
            sys.exit(1)

        gen = CardGenerator(anki)

        # ── 1. Load vocabulary from source deck ──────────────────────
        print(f"Loading vocabulary from '{source_deck or SOURCE_DECK}'…")
        raw_words = gen.get_source_words(source_deck)
        if not raw_words:
            print("✗ No words found in source deck.")
            sys.exit(1)

        # Convert to WordEntry objects.
        # frequency_rank is assigned by the order words appear in the source
        # deck (position 1 = most frequent); pass an explicit rank field in the
        # source note's "Frequency" field if available.
        word_entries: list[WordEntry] = []
        for rank, entry in enumerate(raw_words, start=1):
            # Accept an optional "Frequency" or "FrequencyRank" field from the
            # Anki note; fall back to source-deck order if absent.
            freq = int(entry.get("frequency", rank))
            word_entries.append(WordEntry(
                word=entry["word"],
                translation=entry.get("translation", ""),
                pos=entry.get("pos", "noun"),
                frequency_rank=freq,
                declension_class=entry.get("declension_class", ""),
                verb_class=entry.get("verb_class", ""),
            ))

        # ── 2. Build the progression plan ────────────────────────────
        print("Building phrase-chunking progression plan…")
        plan = ProgressionPlan(word_entries)
        print(plan.summary())

        coverage = plan.coverage_report()
        print(f"\n  Phrase coverage: {coverage['coverage_pct']}% "
              f"({coverage['covered_in_phrases']}/{coverage['total_vocab']} words)")
        if coverage["uncovered"]:
            print(f"  ⚠ {len(coverage['uncovered'])} words not yet covered in phrases:")
            for w in coverage["uncovered"][:10]:
                print(f"      {w}")
            if len(coverage["uncovered"]) > 10:
                print(f"      … and {len(coverage['uncovered']) - 10} more")

        if dry_run:
            print("\n[dry-run] Plan printed. No cards pushed to Anki.")
            return

        # ── 3. Setup models and progression deck ─────────────────────
        gen.setup_models()
        from armenian_anki.config import PROGRESSION_DECK
        anki.ensure_deck(PROGRESSION_DECK)

        due_positions = assign_due_positions(plan)
        stats = {"vocab_cards": 0, "phrase_cards": 0, "errors": 0}

        # ── 4. Push cards in progression order ───────────────────────
        for segment in plan.ordered_segments():
            if isinstance(segment, VocabBatch):
                vb = segment
                base_tags = [
                    "auto-generated",
                    level_tag(vb.level),
                    batch_tag(vb.batch_index),
                    "phrase-chunking",
                ]
                for word_entry in vb.words:
                    tags = base_tags + [syllable_tag(word_entry.syllable_count)]
                    try:
                        if word_entry.pos.lower() in ("noun", "n"):
                            note_id = gen.generate_noun_card(
                                word_entry.word,
                                word_entry.translation,
                                word_entry.declension_class or None,
                                extra_tags=tags,
                                deck=PROGRESSION_DECK,
                            )
                        elif word_entry.pos.lower() in ("verb", "v"):
                            note_id = gen.generate_verb_card(
                                word_entry.word,
                                word_entry.translation,
                                word_entry.verb_class or None,
                                extra_tags=tags,
                                deck=PROGRESSION_DECK,
                            )
                        else:
                            note_id = None

                        if note_id:
                            due_pos = due_positions.get(word_entry.word)
                            if due_pos is not None:
                                anki.set_due_position(note_id, due_pos)
                            stats["vocab_cards"] += 1
                    except Exception as exc:
                        logger.error(f"Error pushing vocab card for '{word_entry.word}': {exc}")
                        stats["errors"] += 1

            elif isinstance(segment, PhraseBatch):
                pb = segment
                base_tags = [
                    "auto-generated",
                    level_tag(pb.level),
                    batch_tag(pb.vocab_batch_index),
                    "phrase-chunking",
                    "phrase",
                ]
                for phrase in pb.phrases:
                    tags = base_tags + [grammar_tag(phrase.grammar_type)]
                    try:
                        # Find the word entry for this phrase's target word
                        target_entry = next(
                            (w for b in plan.vocab_batches
                             for w in b.words if w.word == phrase.target_word),
                            None,
                        )
                        if target_entry is None:
                            continue

                        sentence_ids = gen.generate_sentence_cards(
                            target_entry.word,
                            target_entry.pos,
                            target_entry.translation,
                            target_entry.declension_class or None,
                            target_entry.verb_class or None,
                            grammar_filter=phrase.grammar_type,
                            max_sentences=1,
                            extra_tags=tags,
                            deck=PROGRESSION_DECK,
                        )
                        for note_id in sentence_ids:
                            phrase_key = f"phrase::{phrase.target_word}"
                            due_pos = due_positions.get(phrase_key)
                            if due_pos is not None:
                                anki.set_due_position(note_id, due_pos)
                        stats["phrase_cards"] += len(sentence_ids)
                    except Exception as exc:
                        logger.error(
                            f"Error pushing phrase card for '{phrase.target_word}': {exc}"
                        )
                        stats["errors"] += 1

        # ── 5. Summary ────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("  Progression Pipeline Complete")
        print("=" * 60)
        print(f"  Vocabulary cards pushed: {stats['vocab_cards']}")
        print(f"  Phrase cards pushed:     {stats['phrase_cards']}")
        print(f"  Errors:                  {stats['errors']}")
        print(f"  Deck: {PROGRESSION_DECK}")
        print("=" * 60)

    except AnkiConnectError as exc:
        print(f"✗ AnkiConnect error: {exc}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Generate Armenian morphology cards for Anki",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --demo                              Run demo (no Anki needed)
  %(prog)s                                     Process all words in source deck
  %(prog)s --source-deck "My Armenian Deck"    Process a specific deck
  %(prog)s --word գdelayed --pos noun --translation book
  %(prog)s --word գdelayed --pos verb --translation write --no-anki
  %(prog)s --progression                       Build phrase-chunking progression deck
  %(prog)s --progression --dry-run             Preview progression plan without pushing
        """,
    )
    parser.add_argument("--demo", action="store_true",
                        help="Run morphology demo without requiring Anki")
    parser.add_argument("--word", type=str,
                        help="Process a single Armenian word")
    parser.add_argument("--pos", type=str, choices=["noun", "verb", "n", "v"],
                        help="Part of speech for --word")
    parser.add_argument("--translation", type=str, default="",
                        help="English translation for --word")
    parser.add_argument("--declension-class", type=str, default=None,
                        choices=list(DECLENSION_CLASSES.keys()),
                        help="Noun declension class")
    parser.add_argument("--verb-class", type=str, default=None,
                        choices=list(VERB_CLASSES.keys()),
                        help="Verb conjugation class")
    parser.add_argument("--source-deck", type=str, default=None,
                        help=f"Source deck name (default: {SOURCE_DECK})")
    parser.add_argument("--no-anki", action="store_true",
                        help="Display output only, don't push to Anki")
    parser.add_argument("--progression", action="store_true",
                        help="Run the phrase-chunking progression pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="With --progression: print the plan without pushing cards")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable debug logging")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.demo:
        run_demo()
    elif args.progression:
        run_progression_pipeline(args.source_deck, dry_run=args.dry_run)
    elif args.word:
        if not args.pos:
            parser.error("--pos is required when using --word")
        run_single_word(
            args.word, args.pos, args.translation,
            args.declension_class, args.verb_class, args.no_anki,
        )
    else:
        run_full_pipeline(args.source_deck)


if __name__ == "__main__":
    main()
