"""Generate ordered flashcards with prerequisite-aware sentence generation.

This tool generates cards in proper difficulty order, ensuring that sentence
cards only use vocabulary that has already been taught in previous word cards.
"""
import sys
import json
import html
import re
import math
from pathlib import Path

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, '02-src')

from lousardzag.database import CardDatabase
from lousardzag.progression import ProgressionPlan, WordEntry, max_syllables_for_level
from lousardzag.sentence_generator import (
    generate_noun_sentences,
    generate_verb_sentences,
    extract_vocabulary
)
from lousardzag.morphology.difficulty import count_syllables_with_context
from lousardzag.morphology.detect import detect_noun_class, detect_verb_class


ARMENIAN_WORD_RE = re.compile(r"^[\u0531-\u0556\u0561-\u0587]+$")

# Targeted correction for known noisy deck glosses.
LEMMA_TRANSLATION_OVERRIDES = {
    "է": "being, existence",
}


def _sanitize_text(value: str) -> str:
    """Decode HTML entities and normalize spacing."""
    if not value:
        return ""
    cleaned = html.unescape(value).replace("\xa0", " ")
    cleaned = " ".join(cleaned.split())
    return cleaned.strip()


def _infer_pos(raw_pos: str, translation: str) -> str:
    """Infer POS conservatively when source data is noisy."""
    pos = (raw_pos or "").strip().lower()
    trans = (translation or "").strip().lower()

    if pos in ("noun", "n", "verb", "v"):
        if trans.startswith("to "):
            return "verb"
        return "noun" if pos in ("noun", "n") else "verb"

    if trans.startswith("to "):
        return "verb"
    return "noun"


def _is_usable_lemma(lemma: str) -> bool:
    """Keep only single-word Armenian lemmas for controlled progression."""
    if not lemma:
        return False
    if " " in lemma:
        return False
    return bool(ARMENIAN_WORD_RE.fullmatch(lemma))


def _looks_adjectival_gloss(translation: str) -> bool:
    """Heuristic to suppress noun templates for adjective-like glosses."""
    t = (translation or "").strip().lower()
    if not t:
        return False

    # Common adjective endings and known problematic glosses from deck imports.
    adjective_endings = ("y", "ful", "less", "ive", "al", "ous", "able", "ible", "ic")
    known_adjectives = {
        "free", "honest", "sunny", "medical", "new", "good", "beautiful", "secured",
    }

    first = t.split(",")[0].strip().split()[0]
    if first in known_adjectives:
        return True
    return any(first.endswith(suffix) for suffix in adjective_endings)


def _use_english_sentences(translation: str, pos: str) -> bool:
    """Enable English sentence lines only when gloss looks reliable."""
    t = (translation or "").strip().lower()
    if not t:
        return False

    # Suppress ambiguous or noisy glosses.
    if any(ch in t for ch in (",", "/", "(", ")", ";", ":")):
        return False

    tokens = t.split()
    if not tokens:
        return False

    # Verb glosses should be infinitival and short (e.g., "to read").
    if pos.lower() in ("verb", "v"):
        return t.startswith("to ") and len(tokens) <= 3

    # Be conservative for nouns/adjectives: show Armenian-only examples.
    return False


def _normalize_translation_for_lemma(lemma: str, translation: str) -> str:
    """Apply lemma-specific translation corrections when source data is noisy."""
    return LEMMA_TRANSLATION_OVERRIDES.get(lemma, translation)


def _max_syllables_for_word_at_level(
    level: int,
    pos: str,
    level_default_limit: int,
    level1_nonverb_max_syllables: int = 1,
    level1_verb_max_syllables: int = 2,
) -> int:
    """Return a POS-aware syllable ceiling for a word at a given level.

    Level 1 policy:
      - Verbs: up to 2 syllables.
      - Non-verbs (nouns/adjectives/etc.): 1 syllable.
    Later levels fall back to progression's global band limits.
    """
    if level == 1:
        if (pos or "").lower() in ("verb", "v"):
            return level1_verb_max_syllables
        return level1_nonverb_max_syllables
    return level_default_limit


def _select_with_first_batch_policy(
    entries: list[WordEntry],
    max_words: int,
    first_batch_size: int = 20,
    force_word: str = "է",
    mono_ratio: float = 0.7,
    two_syllable_verbs_target: int = 3,
    first_batch_max_syllables: int | None = 2,
    level1_nonverb_max_syllables: int = 1,
    level1_verb_max_syllables: int = 2,
) -> tuple[list[WordEntry], bool]:
    """Select words while enforcing first-batch composition constraints.

    Policy for first batch (up to 20 words):
      - Force inclusion of `force_word` when available.
      - Keep a majority mono-syllable words.
      - Include a few 2-syllable verbs.
    """
    if not entries or max_words <= 0:
        return [], False

    limit = min(max_words, len(entries))
    batch_target = min(first_batch_size, limit)
    mono_target = min(batch_target, math.ceil(batch_target * mono_ratio))

    selected: list[WordEntry] = []
    selected_ids: set[int] = set()

    def _add_entry(entry: WordEntry) -> bool:
        if len(selected) >= limit:
            return False
        eid = id(entry)
        if eid in selected_ids:
            return False
        selected.append(entry)
        selected_ids.add(eid)
        return True

    force_added = False

    def _is_first_batch_eligible(entry: WordEntry) -> bool:
        level_default = first_batch_max_syllables if first_batch_max_syllables is not None else 999
        word_limit = _max_syllables_for_word_at_level(
            1,
            entry.pos,
            level_default,
            level1_nonverb_max_syllables=level1_nonverb_max_syllables,
            level1_verb_max_syllables=level1_verb_max_syllables,
        )
        return entry.syllable_count <= word_limit

    # 1) Force "է" into the first batch if present.
    for entry in entries:
        if entry.word == force_word and _is_first_batch_eligible(entry):
            _add_entry(entry)
            force_added = True
            break

    # 2) Add a few 2-syllable verbs early.
    two_syl_verb_added = 0
    for entry in entries:
        if len(selected) >= batch_target:
            break
        if not _is_first_batch_eligible(entry):
            continue
        if entry.syllable_count == 2 and entry.pos.lower() in ("verb", "v"):
            if _add_entry(entry):
                two_syl_verb_added += 1
                if two_syl_verb_added >= two_syllable_verbs_target:
                    break

    # 3) Fill majority with mono-syllable words.
    mono_added = sum(1 for e in selected if e.syllable_count == 1)
    if mono_added < mono_target:
        for entry in entries:
            if len(selected) >= batch_target:
                break
            if not _is_first_batch_eligible(entry):
                continue
            if entry.syllable_count == 1 and _add_entry(entry):
                mono_added += 1
                if mono_added >= mono_target:
                    break

    # 4) Fill remaining first-batch slots by original order.
    for entry in entries:
        if len(selected) >= batch_target:
            break
        if not _is_first_batch_eligible(entry):
            continue
        _add_entry(entry)

    # Fallback if strict first-batch eligibility underfills.
    for entry in entries:
        if len(selected) >= batch_target:
            break
        if not _is_first_batch_eligible(entry):
            continue
        _add_entry(entry)

    # 5) Fill remainder up to max_words by original order.
    for entry in entries:
        if len(selected) >= limit:
            break
        if not _is_first_batch_eligible(entry):
            continue
        _add_entry(entry)

    return selected, force_added


def check_prerequisites(sentence_armenian: str, taught_words: set[str]) -> tuple[bool, list[str]]:
    """Check if all vocabulary in a sentence has been previously taught.
    
    Args:
        sentence_armenian: Armenian sentence text.
        taught_words: Set of Armenian words that have been taught (normalized lowercase).
    
    Returns:
        (all_known, unknown_words) where all_known is True if all words are known.
    """
    vocab_used = extract_vocabulary(sentence_armenian)
    unknown = [w for w in vocab_used if w not in taught_words]
    return (len(unknown) == 0, unknown)


def generate_ordered_cards(
    source_deck: str,
    max_words: int = 20,
    include_sentences: bool = True,
    output_html: str | None = None,
    max_syllables_level_1: int = 2,
    level1_nonverb_max_syllables: int = 1,
    level1_verb_max_syllables: int = 2,
    english_mode: str = "strict",
    sentence_start_after_vocab: int = 20,
):
    """Generate flashcards in proper difficulty order with prerequisite checking.
    
    Args:
        source_deck: Anki deck name to source vocabulary from.
        max_words: Maximum number of words to generate cards for.
        include_sentences: Whether to include sentence cards.
        output_html: Optional path to save HTML preview file.
        max_syllables_level_1: Max syllables for level 1 words (default: 2).
        english_mode: Sentence English rendering mode: off|strict|full.
    """
    db = CardDatabase()
    
    print(f"\n{'='*70}")
    print(f"ORDERED CARD GENERATION")
    print(f"{'='*70}\n")
    print(f"Source deck: {source_deck}")
    print(f"Max words: {max_words}")
    print(f"Include sentences: {include_sentences}\n")
    print(f"English sentence mode: {english_mode}\n")
    print(f"Sentence start threshold: {sentence_start_after_vocab} vocab word(s)\n")
    print(
        f"Level 1 POS syllable policy: non-verbs <= {level1_nonverb_max_syllables}, "
        f"verbs <= {level1_verb_max_syllables}\n"
    )
    
    # Get vocabulary from cache
    vocab_entries = db.get_vocabulary_from_cache(source_deck)
    if not vocab_entries:
        print(f"❌ No vocabulary found in cache for deck: {source_deck}")
        print(f"   Run with --sync-vocabulary first to cache deck vocabulary.")
        return
    
    print(f"Found {len(vocab_entries)} vocabulary entries in cache\n")
    
    # Convert to WordEntry format for progression sorting
    candidate_entries = []
    skipped_invalid = 0
    skipped_non_armenian = 0
    for entry in vocab_entries:
        lemma = _sanitize_text(entry.get('lemma', ''))
        translation = _sanitize_text(entry.get('translation', ''))
        translation = _normalize_translation_for_lemma(lemma, translation)

        if not lemma or not translation:
            skipped_invalid += 1
            continue

        if not _is_usable_lemma(lemma):
            skipped_non_armenian += 1
            continue

        pos = _infer_pos(entry.get('pos', 'noun'), translation)

        word_entry = WordEntry(
            word=lemma,
            translation=translation,
            pos=pos,
            frequency_rank=entry.get('frequency_rank', 9999),
            declension_class=entry.get('declension_class', ''),
            verb_class=entry.get('verb_class', ''),
            syllable_count=count_syllables_with_context(lemma, with_epenthesis=True),
        )
        candidate_entries.append(word_entry)

    word_entries, force_e_added = _select_with_first_batch_policy(
        candidate_entries,
        max_words=max_words,
        first_batch_size=20,
        force_word='է',
        mono_ratio=0.7,
        two_syllable_verbs_target=3,
        first_batch_max_syllables=max_syllables_level_1,
        level1_nonverb_max_syllables=level1_nonverb_max_syllables,
        level1_verb_max_syllables=level1_verb_max_syllables,
    )

    print(
        f"Selected {len(word_entries)} usable entries "
        f"(skipped {skipped_invalid} empty/invalid, {skipped_non_armenian} non-single-word/non-Armenian)\n"
    )
    if force_e_added:
        print("First-batch policy: forced inclusion of 'է' when available")
    else:
        print("First-batch policy: 'է' not found in usable candidate pool")
    
    # Build progression (sorts by difficulty)
    print("Building progression order...")
    progression = ProgressionPlan(word_entries)
    
    # Bootstrap vocabulary: Common grammatical words assumed to be pre-known
    # These are essential function words that appear in almost every sentence
    bootstrap_vocab = {
        # Copula and auxiliaries
        'է', 'էր', 'եմ', 'ես', 'ենք', 'էին',  # to be (present/past)
        'կը', 'պիտի', 'կու',  # auxiliary particles
        # Pronouns
        'ես', 'դուն', 'ան', 'մենք', 'դուք', 'անոնք',  # personal pronouns
        # Articles and determiners
        'ը', 'մը', 'ն',  # definite/indefinite articles
        'աս', 'անիկա', 'այս', 'այդ',  # demonstratives
        # Common prepositions/particles
        'ին', 'ով', 'է',  
        # Common adjectives used in templates
        'գեղեծիկ', 'գեղեցիկ', 'լավ', 'նոր', 'մեծ',  # beautiful, good, new, big
        # Common verbs used in templates
        'ունիմ', 'սիրեմ', 'ուզեմ', 'գամ',  # have, love, want, come
        # Other function words
        'հոս', 'հան', 'միայն',  # here, there, only
        'գունքը',  # color (common template word)
    }
    
    # Track taught words for prerequisite checking
    taught_words = set(bootstrap_vocab)  # Start with bootstrap vocabulary
    taught_vocab_count = 0
    print(f"Bootstrap vocabulary: {len(bootstrap_vocab)} common grammatical words\n")
    
    # Generate cards in order
    generated_cards = []
    
    for segment in progression.ordered_segments():
        if hasattr(segment, 'words'):  # VocabBatch
            # Determine base syllable limit for this level.
            if segment.level == 1:
                syllable_limit = max_syllables_level_1
            else:
                syllable_limit = max_syllables_for_level(segment.level)
            
            print(f"\n{'─'*70}")
            print(f"📚 LEVEL {segment.level} | Batch {segment.batch_within_level + 1} | Max {syllable_limit} syllable(s)")
            print(f"{'─'*70}\n")
            
            for word_entry in segment.words:
                # Level 1 is POS-aware: only verbs may be disyllabic.
                word_limit = _max_syllables_for_word_at_level(
                    segment.level,
                    word_entry.pos,
                    syllable_limit,
                    level1_nonverb_max_syllables=level1_nonverb_max_syllables,
                    level1_verb_max_syllables=level1_verb_max_syllables,
                )
                if word_entry.syllable_count > word_limit:
                    print(f"  ⊗ {word_entry.word:15s} ({word_entry.translation:20s}) [SKIPPED: {word_entry.syllable_count} syllables > {word_limit}]")
                    continue
                word = word_entry.word
                translation = word_entry.translation
                pos = word_entry.pos
                
                # Normalize and add to taught words
                normalized_word = word.lower()
                taught_words.add(normalized_word)
                taught_vocab_count += 1
                
                # Determine card type and class
                if pos.lower() in ('noun', 'n'):
                    declension_class = word_entry.declension_class or detect_noun_class(word)
                    card_type = 'noun_declension'
                else:
                    verb_class = word_entry.verb_class or detect_verb_class(word)
                    card_type = 'verb_conjugation'
                
                syllables = word_entry.syllable_count
                print(f"  ✓ {word:15s} ({translation:20s}) [{syllables} syl | Level {segment.level}]")
                
                card_info = {
                    'word': word,
                    'translation': translation,
                    'pos': pos,
                    'card_type': card_type,
                    'level': segment.level,
                    'syllables': syllables,
                    'frequency_rank': word_entry.frequency_rank,
                    'difficulty_score': word_entry.difficulty_score,
                    'show_english_sentences': (
                        english_mode == 'full'
                        or (
                            english_mode == 'strict'
                            and _use_english_sentences(translation, pos)
                        )
                    ),
                    'has_prerequisite_sentences': False,
                    'sentences': []
                }
                
                # Generate sentence cards if enabled
                if include_sentences and taught_vocab_count >= sentence_start_after_vocab:
                    if pos.lower() in ('noun', 'n') and _looks_adjectival_gloss(translation):
                        print("    ⊘ Skipped sentence generation (adjective-like gloss for noun template)")
                        generated_cards.append(card_info)
                        continue

                    # Generate candidate sentences
                    if pos.lower() in ('noun', 'n'):
                        sentences = generate_noun_sentences(
                            word,
                            declension_class,
                            translation,
                            max_sentences=10
                        )
                    else:
                        sentences = generate_verb_sentences(
                            word,
                            verb_class,
                            translation,
                            max_sentences=10
                        )
                    
                    # Filter sentences by prerequisite checking
                    valid_sentences = []
                    for form_label, arm_sent, eng_sent in sentences:
                        all_known, unknown = check_prerequisites(arm_sent, taught_words)
                        if all_known:
                            eng_value = eng_sent if card_info['show_english_sentences'] else ""
                            valid_sentences.append((form_label, arm_sent, eng_value))
                        else:
                            # Skip sentence with unknown words
                            unknown_str = ', '.join(unknown[:3])
                            if len(unknown) > 3:
                                unknown_str += f', ... ({len(unknown)} total)'
                            print(f"    ⊘ Skipped sentence (unknown words: {unknown_str})")
                    
                    if valid_sentences:
                        card_info['has_prerequisite_sentences'] = True
                        card_info['sentences'] = valid_sentences
                        print(f"    ✓ Generated {len(valid_sentences)} prerequisite-safe sentences")
                        if english_mode == 'off':
                            print("    • English disabled (mode=off); showing Armenian-only examples")
                        elif english_mode == 'strict' and not card_info['show_english_sentences']:
                            print("    • English hidden (low-confidence gloss); showing Armenian-only examples")
                elif include_sentences:
                    print(
                        f"    ⊘ Delayed sentence generation "
                        f"(taught {taught_vocab_count}/{sentence_start_after_vocab} vocab words)"
                    )
                
                generated_cards.append(card_info)
    
    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}\n")
    print(f"Total cards generated: {len(generated_cards)}")
    print(f"Unique words taught: {len(taught_words)}")
    
    cards_with_sentences = sum(1 for c in generated_cards if c['has_prerequisite_sentences'])
    print(f"Cards with valid sentences: {cards_with_sentences}")
    
    # Generate HTML preview if requested
    if output_html:
        generate_html_preview(generated_cards, taught_words, output_html)
        print(f"\n✓ HTML preview saved to: {output_html}")
    
    return generated_cards, taught_words


def generate_html_preview(cards: list[dict], taught_words: set[str], output_path: str):
    """Generate an HTML file with card previews."""
    html_parts = [
        "<!DOCTYPE html>",
        "<html><head>",
        "<meta charset='utf-8'>",
        "<title>Armenian Flashcard Preview</title>",
        "<style>",
        "body { font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto; padding: 20px; background: #f5f5f5; }",
        ".card { background: white; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
        ".card-header { border-bottom: 2px solid #4CAF50; padding-bottom: 10px; margin-bottom: 15px; }",
        ".word { font-size: 32px; font-weight: bold; color: #333; }",
        ".translation { font-size: 18px; color: #666; margin-top: 5px; }",
        ".meta { font-size: 14px; color: #999; margin-top: 5px; }",
        ".sentences { margin-top: 20px; }",
        ".sentence { background: #f9f9f9; padding: 10px; margin: 10px 0; border-left: 3px solid #4CAF50; }",
        ".armenian { font-size: 18px; margin-bottom: 5px; }",
        ".english { font-size: 16px; color: #666; }",
        ".vocab-badge { display: inline-block; background: #e8f5e9; color: #2e7d32; padding: 2px 8px; border-radius: 3px; font-size: 12px; margin-right: 5px; }",
        ".level-badge { display: inline-block; background: #e3f2fd; color: #1565c0; padding: 4px 12px; border-radius: 4px; font-size: 14px; font-weight: bold; }",
        ".summary { background: #fff3e0; border-left: 4px solid #ff9800; padding: 15px; margin-bottom: 30px; }",
        "</style>",
        "</head><body>",
        "<h1>🇦🇲 Armenian Flashcard Preview</h1>",
        f"<div class='summary'>",
        f"<strong>Summary:</strong> {len(cards)} cards generated | {len(taught_words)} unique words taught",
        "</div>",
    ]
    
    for i, card in enumerate(cards, 1):
        # Decode HTML entities in Armenian text
        word_decoded = html.unescape(card['word'])
        translation_decoded = html.unescape(card['translation'])
        
        html_parts.extend([
            f"<div class='card'>",
            f"<div class='card-header'>",
            f"<span class='level-badge'>Level {card['level']}</span>",
            f"<div class='word'>{word_decoded}</div>",
            f"<div class='translation'>{translation_decoded}</div>",
            f"<div class='meta'>Card {i} | {card['syllables']} syl | Freq Rank: {card['frequency_rank']} | Difficulty: {card['difficulty_score']:.1f}/10 | {card['pos']} | {card['card_type']}</div>",
            f"</div>",
        ])
        
        if card['sentences']:
            html_parts.append("<div class='sentences'>")
            html_parts.append(f"<strong>{len(card['sentences'])} Prerequisite-Safe Sentences:</strong>")
            for form_label, arm_sent, eng_sent in card['sentences'][:5]:  # Show first 5
                # Decode HTML entities in sentences
                arm_sent_decoded = html.unescape(arm_sent)
                eng_sent_decoded = html.unescape(eng_sent)
                vocab = extract_vocabulary(arm_sent)
                vocab_badges = ''.join(f"<span class='vocab-badge'>{html.unescape(w)}</span>" for w in vocab)
                html_parts.extend([
                    "<div class='sentence'>",
                    f"<div class='armenian'>{arm_sent_decoded}</div>",
                ])
                if eng_sent_decoded:
                    html_parts.append(f"<div class='english'>{eng_sent_decoded}</div>")
                html_parts.extend([
                    f"<div style='margin-top: 5px;'>{vocab_badges}</div>",
                    "</div>",
                ])
            html_parts.append("</div>")
        
        html_parts.append("</div>")
    
    html_parts.extend(["</body></html>"])
    
    Path(output_path).write_text('\n'.join(html_parts), encoding='utf-8')


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate ordered flashcards with prerequisite-aware sentences"
    )
    parser.add_argument(
        "--source-deck",
        default="Armenian (Western)",
        help="Anki deck to source vocabulary from"
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=20,
        help="Maximum number of words to generate (default: 20)"
    )
    parser.add_argument(
        "--max-syllables-level-1",
        type=int,
        default=2,
        help="Maximum syllables for level 1 words (default: 2, strict mode: 1)"
    )
    parser.add_argument(
        "--no-sentences",
        action="store_true",
        help="Skip sentence card generation"
    )
    parser.add_argument(
        "--output-html",
        default="08-data/flashcard_preview.html",
        help="Path to save HTML preview (default: 08-data/flashcard_preview.html)"
    )
    parser.add_argument(
        "--english-mode",
        choices=("off", "strict", "full"),
        default="strict",
        help=(
            "English sentence rendering mode: "
            "off (Armenian-only), strict (only confident glosses), full (always show)"
        ),
    )
    parser.add_argument(
        "--sentence-start-after-vocab",
        type=int,
        default=20,
        help="Only generate sentence/phrase cards after this many vocab words are taught (default: 20)",
    )
    parser.add_argument(
        "--level1-nonverb-max-syllables",
        type=int,
        default=1,
        help="Max syllables for level-1 non-verbs (nouns/adjectives/etc), default: 1",
    )
    parser.add_argument(
        "--level1-verb-max-syllables",
        type=int,
        default=2,
        help="Max syllables for level-1 verbs, default: 2",
    )
    
    args = parser.parse_args()
    
    generate_ordered_cards(
        source_deck=args.source_deck,
        max_words=args.max_words,
        include_sentences=not args.no_sentences,
        output_html=args.output_html,
        max_syllables_level_1=args.max_syllables_level_1,
        level1_nonverb_max_syllables=args.level1_nonverb_max_syllables,
        level1_verb_max_syllables=args.level1_verb_max_syllables,
        english_mode=args.english_mode,
        sentence_start_after_vocab=args.sentence_start_after_vocab,
    )
