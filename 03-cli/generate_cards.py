#!/usr/bin/env python3
"""
Lousardzag Card Generator — Main Entry Point

Reads vocabulary from an existing Anki deck, generates morphological forms
(noun declensions, verb conjugations, definite/indefinite articles, example
sentences) and pushes the results back to Anki via AnkiConnect.

Prerequisites:
  1. Anki desktop running with AnkiConnect plugin (code: 2055492159)
  2. A source deck with Armenian vocabulary (configure in lousardzag/config.py)
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
from pathlib import Path

# Add 02-src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / '02-src'))

# Ensure Armenian Unicode prints correctly on Windows (cp1252 → utf-8)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf-8-sig"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from lousardzag.anki_connect import AnkiConnect, AnkiConnectError
from lousardzag.card_generator import CardGenerator
from lousardzag.morphology.nouns import decline_noun, DECLENSION_CLASSES
from lousardzag.morphology.verbs import conjugate_verb, VERB_CLASSES
from lousardzag.morphology.articles import add_definite, add_indefinite
from lousardzag.sentence_generator import generate_noun_sentences, generate_verb_sentences
from lousardzag.config import SOURCE_DECK, TARGET_DECK
from lousardzag.progression import (
    ProgressionPlan, WordEntry, VocabBatch, PhraseBatch,
    level_tag, batch_tag, grammar_tag, syllable_tag,
    assign_due_positions, sentence_filter_for, fill_plan_sentences,
)
from lousardzag.ocr_vocab_bridge import (
    extract_vocab_from_file, vocab_to_csv, vocab_to_json,
    vocab_to_word_entries,
)

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def run_list_decks():
    """Connect to Anki and print all available deck names."""
    try:
        anki = AnkiConnect()
        if not anki.ping():
            print("✗ Cannot connect to AnkiConnect. Is Anki running?")
            print("  Install AnkiConnect: Tools → Add-ons → Get Add-ons → Code: 2055492159")
            sys.exit(1)
        decks = sorted(anki.deck_names())
        print(f"\nFound {len(decks)} deck(s) in Anki:\n")
        for d in decks:
            print(f"  {d}")
        print()
    except AnkiConnectError as exc:
        print(f"✗ AnkiConnect error: {exc}")
        sys.exit(1)


def run_inspect_deck(deck: str):
    """Show the field names and a sample note from a deck.

    This helps you discover which field names to pass to --field-word,
    --field-pos, and --field-translation.
    """
    try:
        anki = AnkiConnect()
        if not anki.ping():
            print("✗ Cannot connect to AnkiConnect. Is Anki running?")
            sys.exit(1)

        note_ids = anki.find_notes(f'"deck:{deck}"')
        if not note_ids:
            print(f"✗ No notes found in deck '{deck}'")
            print("  Run --list-decks to see available decks.")
            sys.exit(1)

        notes = anki.notes_info(note_ids[:3])  # preview first 3
        first = notes[0]
        field_names = list(first.get("fields", {}).keys())

        print(f"\nDeck: {deck}")
        print(f"Total notes: {len(note_ids)}")
        print(f"Note type: {first.get('modelName', '?')}")
        print(f"\nFields ({len(field_names)}):")
        for name in field_names:
            sample_val = first["fields"][name]["value"]
            # Truncate HTML/long values for display
            if len(sample_val) > 60:
                sample_val = sample_val[:57] + "..."
            print(f"  {name!r:30s}  e.g. {sample_val!r}")

        print(f"\nSample notes ({min(3, len(notes))}):")
        for n in notes:
            fields = {k: v["value"] for k, v in n.get("fields", {}).items()}
            preview = " | ".join(f"{k}: {v[:25]}" for k, v in list(fields.items())[:4] if v)
            print(f"  {preview}")

        print(f"""
Usage hint — to process this deck, run:
  python generate_anki_cards.py \\
    --source-deck "{deck}" \\
    --field-word "<WORD FIELD NAME>" \\
    --field-translation "<TRANSLATION FIELD NAME>"
""")
    except AnkiConnectError as exc:
        print(f"✗ AnkiConnect error: {exc}")
        sys.exit(1)


def run_demo():
    """Run a demonstration of the morphology engine without requiring Anki."""
    print("=" * 80)
    print("  Armenian Morphology Engine — Demo")
    print("=" * 80)

    # ── Noun Declension Demo ──
    # Using common Western Armenian words
    from lousardzag.morphology.core import ARM
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
    word_house = _d + _vo + _yiwn + _n               # տուն (dun = house; WA: տ = ARM["d"])

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


def run_full_pipeline(source_deck: str = None, field_overrides: dict = None,
                      default_pos: str = "noun", local_only: bool = False):
    """Process all words in the source deck."""
    try:
        if local_only:
            print("Running in local-only mode (no Anki connections/writes).")
            gen = CardGenerator()
            stats = gen.process_all(source_deck, field_overrides, default_pos, local_only=True)
            print("\n" + "=" * 60)
            print("  Local-Only Generation Complete")
            print("=" * 60)
            print(f"  Total words processed: {stats['total']}")
            print(f"  Noun declension rows:  {stats['nouns']}")
            print(f"  Verb conjugation rows: {stats['verbs']}")
            print(f"  Sentence rows:         {stats['sentences']}")
            print(f"  Errors:                {stats['errors']}")
            print("=" * 60)
            return

        anki = AnkiConnect()
        if not anki.ping():
            print("✗ Cannot connect to AnkiConnect. Is Anki running with the AnkiConnect plugin?")
            print("  Install AnkiConnect: Tools → Add-ons → Get Add-ons → Code: 2055492159")
            sys.exit(1)

        gen = CardGenerator(anki)
        stats = gen.process_all(source_deck, field_overrides, default_pos)

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


def run_progression_pipeline(source_deck: str = None, dry_run: bool = False,
                             field_overrides: dict = None, default_pos: str = "noun"):
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
        raw_words = gen.get_source_words(source_deck, field_overrides, default_pos)
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
                syllable_count=entry.get("syllable_count", 0),
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
            # Fill phrase sentences so the dry-run output shows actual text
            fill_plan_sentences(plan)
            for segment in plan.ordered_segments():
                if isinstance(segment, PhraseBatch):
                    for phrase in segment.phrases:
                        if phrase.armenian_sentence:
                            print(f"    [{phrase.grammar_type}] {phrase.target_word}")
                            print(f"      ARM: {phrase.armenian_sentence}")
                            print(f"      ENG: {phrase.english_sentence}")
            print("\n[dry-run] Plan printed. No cards pushed to Anki.")
            return

        # ── 3. Setup models and progression deck ─────────────────────
        gen.setup_models()
        from lousardzag.config import PROGRESSION_DECK
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
                            grammar_filter=sentence_filter_for(phrase.grammar_type),
                            max_sentences=1,
                            extra_tags=tags,
                            deck=PROGRESSION_DECK,
                            supporting_words=phrase.supporting_words,
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


def run_ocr_bridge(input_path: str, output_path: str = None, output_format: str = "csv"):
    """Extract vocabulary from OCR output and write a structured vocab list.

    Args:
        input_path: Path to an extracted OCR JSON or CSV file.
        output_path: Where to write the output. If None, auto-generates.
        output_format: "csv" or "json".
    """
    from pathlib import Path

    inp = Path(input_path)
    if not inp.exists():
        print(f"✗ Input file not found: {input_path}")
        sys.exit(1)

    print(f"Extracting vocabulary from: {inp.name}")
    entries = extract_vocab_from_file(inp)

    if not entries:
        print("✗ No vocabulary entries found in the OCR data.")
        sys.exit(1)

    # Filter to entries with both word and translation
    complete = [e for e in entries if e.armenian_word and e.translation]
    partial = [e for e in entries if e.armenian_word and not e.translation]

    print(f"\nExtracted {len(entries)} total entries:")
    print(f"  Complete (word + translation): {len(complete)}")
    print(f"  Partial (word only):           {len(partial)}")

    # Show sample entries
    print(f"\nSample entries (first 10):")
    for entry in complete[:10]:
        pos_str = f" ({entry.pos})" if entry.pos else ""
        translit_str = f" [{entry.transliteration}]" if entry.transliteration else ""
        print(f"  {entry.armenian_word}{translit_str}{pos_str} — {entry.translation}")

    # Write output
    if output_path is None:
        output_path = inp.parent / f"vocab_{inp.stem}.{output_format}"
    else:
        output_path = Path(output_path)

    if output_format == "json":
        vocab_to_json(entries, output_path)
    else:
        vocab_to_csv(entries, output_path)

    print(f"\n✓ Vocabulary list written to: {output_path}")


def run_sync_vocabulary(source_deck: str = None, field_overrides: dict = None):
    """Sync vocabulary from Anki deck to local SQLite cache.
    
    After syncing, the vocabulary cache can be used with --no-anki flag
    or by setting use_cache=True in CardGenerator.
    """
    try:
        anki = AnkiConnect()
        if not anki.ping():
            print("✗ Cannot connect to AnkiConnect. Is Anki running with the AnkiConnect plugin?")
            print("  Install AnkiConnect: Tools → Add-ons → Get Add-ons → Code: 2055492159")
            sys.exit(1)

        from lousardzag.database import CardDatabase
        db = CardDatabase()
        
        source_deck = source_deck or SOURCE_DECK
        print(f"Syncing vocabulary from deck: {source_deck}")
        print("-" * 60)
        
        stats = db.sync_vocabulary_from_anki(
            anki,
            deck=source_deck,
            field_overrides=field_overrides or None,
        )
        
        print("\n" + "=" * 60)
        print("  Vocabulary Sync Complete")
        print("=" * 60)
        print(f"  Added:       {stats['added']}")
        print(f"  Updated:     {stats['updated']}")
        print(f"  Skipped:     {stats['skipped']}")
        print(f"  Total:       {stats['total_processed']}")
        print("=" * 60)
        
        if stats['added'] + stats['updated'] > 0:
            print("\n✓ Vocabulary cache is now ready for offline use!")
            print("  Use --use-cache or use_cache=True to use the local cache instead of AnkiConnect")
        else:
            print("\n⚠ No vocabulary was synced. Check deck name and try again.")
    
    except AnkiConnectError as exc:
        print(f"✗ AnkiConnect error: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"✗ Error: {exc}")
        logger.exception("Vocabulary sync failed")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Generate Armenian morphology cards for Anki",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --demo                              Run demo (no Anki needed)
  %(prog)s --list-decks                        Show all decks in your Anki
  %(prog)s --inspect "My Armenian Deck"        Show fields of notes in a deck
  %(prog)s                                     Process all words in source deck
  %(prog)s --source-deck "My Armenian Deck"    Process a specific deck
  %(prog)s --source-deck "My Deck" --field-word "Front" --field-translation "Back"
  %(prog)s --word գիրք --pos noun --translation book
  %(prog)s --word գրել --pos verb --translation write --no-anki
  %(prog)s --progression                       Build phrase-chunking progression deck
  %(prog)s --progression --dry-run             Preview progression plan without pushing
  %(prog)s --ocr-bridge extracted_text.json    Extract vocab from OCR output
        """,
    )
    parser.add_argument("--demo", action="store_true",
                        help="Run morphology demo without requiring Anki")
    parser.add_argument("--list-decks", action="store_true",
                        help="List all decks available in your Anki app")
    parser.add_argument("--inspect", type=str, metavar="DECK",
                        help="Show field names and sample notes from a deck")
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
    parser.add_argument("--field-word", type=str, default=None, metavar="FIELD",
                        help="Name of the field containing the Armenian word")
    parser.add_argument("--field-translation", type=str, default=None, metavar="FIELD",
                        help="Name of the field containing the English translation")
    parser.add_argument("--field-pos", type=str, default=None, metavar="FIELD",
                        help="Name of the field containing the part of speech")
    parser.add_argument("--default-pos", type=str, default="noun",
                        choices=["noun", "verb"],
                        help="POS to assume when the pos field is missing (default: noun)")
    parser.add_argument("--no-anki", action="store_true",
                        help="Display output only, don't push to Anki")
    parser.add_argument("--local-only", action="store_true",
                        help="Strict local mode: use SQLite cache only and never connect/write to Anki")
    parser.add_argument("--progression", action="store_true",
                        help="Run the phrase-chunking progression pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="With --progression: print the plan without pushing cards")
    parser.add_argument("--ocr-bridge", type=str, metavar="FILE",
                        help="Extract vocabulary from an OCR-extracted JSON or CSV file")
    parser.add_argument("--sync-vocabulary", action="store_true",
                        help="Sync vocabulary from source deck to local SQLite cache for offline access")
    parser.add_argument("--ocr-output", type=str, default=None, metavar="FILE",
                        help="Output path for --ocr-bridge (default: auto-generated)")
    parser.add_argument("--ocr-format", type=str, default="csv",
                        choices=["csv", "json"],
                        help="Output format for --ocr-bridge (default: csv)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable debug logging")

    args = parser.parse_args()
    setup_logging(args.verbose)

    # Build field-override dict from individual flags
    field_overrides = {}
    if args.field_word:
        field_overrides["word"] = args.field_word
    if args.field_translation:
        field_overrides["translation"] = args.field_translation
    if args.field_pos:
        field_overrides["pos"] = args.field_pos

    if args.demo:
        run_demo()
    elif args.sync_vocabulary:
        run_sync_vocabulary(args.source_deck, field_overrides=field_overrides or None)
    elif args.list_decks:
        run_list_decks()
    elif args.inspect:
        run_inspect_deck(args.inspect)
    elif args.ocr_bridge:
        run_ocr_bridge(args.ocr_bridge, args.ocr_output, args.ocr_format)
    elif args.progression:
        run_progression_pipeline(args.source_deck, dry_run=args.dry_run,
                                 field_overrides=field_overrides or None,
                                 default_pos=args.default_pos)
    elif args.word:
        if not args.pos:
            parser.error("--pos is required when using --word")
        run_single_word(
            args.word, args.pos, args.translation,
            args.declension_class, args.verb_class, args.no_anki,
        )
    else:
        run_full_pipeline(args.source_deck,
                          field_overrides=field_overrides or None,
                          default_pos=args.default_pos,
                          local_only=args.local_only)


if __name__ == "__main__":
    main()
