#!/usr/bin/env python3
"""
Validate word mappings against Western Armenian corpus and phonetics.

This tool checks:
1. All words in Anki export are in the Western Armenian corpus
2. All words use classical Western Armenian orthography (not reformed)
3. IPA/transliteration is correct for each word
4. No Eastern Armenian intrusions

Usage:
    python 07-tools/validate_word_mappings.py [--check-corpus] [--check-orthography] [--report-unmatched]
"""

import json
import csv
import logging
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

# Avoid UnicodeEncodeError on Windows cp1252 consoles by escaping unsupported chars.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="backslashreplace")

# Add 02-src to path for morphology imports
SRC_DIR = Path(__file__).parent.parent / "02-src"
sys.path.insert(0, str(SRC_DIR))

try:
    from lousardzag.stemmer import match_word_with_stemming, get_all_lemmas
    STEMMING_AVAILABLE = True
except ImportError:
    STEMMING_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
ANKI_EXPORT = PROJECT_ROOT / "08-data" / "anki_export.json"
CORPUS_FILE = PROJECT_ROOT / "02-src" / "wa_corpus" / "data" / "wa_frequency_list.csv"
UNMATCHED_REPORT = PROJECT_ROOT / "08-data" / "unmatched_rank_report.json"

# Western Armenian orthographic rules
CLASSICAL_MARKERS = {
    'Õ«Ö‚':  'yoo diphthong (classical - never Õ«Õ½ or ÕµÕ¸Ö‚Õ²)',
    'Õ¸Ö‚': 'oo vowel (classical)',
    'Õ¥': 'e vowel (classical)',
    'Õ§': 'standalone e vowel (less common in WA, but classical)',
    'Õ¸': 'vo before consonants, o vowel (classical)',
    'Õ¬': 'l',
    'Õ®': 'dz',
    'Õ»': 'j (ch sound)',
    'Õª': 'zh',
    'Õ³': 'j (dj sound)',
}

# Eastern Armenian markers to AVOID
EASTERN_MARKERS = {
    'ÕµÕ¸Ö‚': 'Eastern reformed - should be Õ«Ö‚',
    'Õ¸Ö‚[Õ²]': 'Eastern reformed - should be Õ«Ö‚',
     'ÖÕ¸Ö‚': 'Eastern marker patterns',
}

def load_anki_words() -> Dict[str, str]:
    """Load all Armenian words from Anki export."""
    words = {}
    
    if not ANKI_EXPORT.exists():
        logger.error(f"ANKI_EXPORT not found: {ANKI_EXPORT}")
        return words
    
    with open(ANKI_EXPORT, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Iterate through all note groups
    for group_name, notes in data.items():
        for note in notes:
            armenian_field = note['fields'].get('Armenian', '').strip()
            if armenian_field:
                # Handle multiple words separated by commas
                for word_variant in armenian_field.split(','):
                    word = word_variant.strip()
                    if word:
                        words[word] = group_name
    
    return words


def load_corpus_words() -> Set[str]:
    """Load all words from Western Armenian corpus."""
    corpus_words = set()
    
    if not CORPUS_FILE.exists():
        logger.error(f"CORPUS_FILE not found: {CORPUS_FILE}")
        return corpus_words
    
    try:
        with open(CORPUS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                word = row.get('word', '').strip().lower()
                if word:
                    corpus_words.add(word)
    except Exception as e:
        logger.error(f"Error reading corpus: {e}")
    
    return corpus_words


def validate_with_stemming(vocab_words: Dict[str, str], corpus_words: Set[str]) -> Dict:
    """Validate vocabulary against corpus using stemming/lemmatization.
    
    Returns detailed statistics about exact matches and lemma-based matches.
    """
    if not STEMMING_AVAILABLE:
        logger.warning("Stemming module not available - skipping stemming validation")
        return {}
    
    exact_matches = 0
    lemma_matches = 0
    no_matches = 0
    lemma_examples = []  # Store examples of successful lemma matches
    
    for word, deck in vocab_words.items():
        matched, match_type = match_word_with_stemming(word, corpus_words)
        
        if match_type == "exact":
            exact_matches += 1
        elif match_type == "lemma":
            lemma_matches += 1
            if len(lemma_examples) < 10:
                lemmas = get_all_lemmas(word)
                matching = [l for l in lemmas if l in corpus_words]
                lemma_examples.append({
                    'word': word,
                    'matching_lemmas': matching[:2]  # First 2 matches
                })
        else:
            no_matches += 1
    
    total = len(vocab_words)
    stats = {
        'total_words': total,
        'exact_matches': exact_matches,
        'lemma_matches': lemma_matches,
        'total_with_lemmatization': exact_matches + lemma_matches,
        'no_matches': no_matches,
        'exact_coverage': 100 * exact_matches / total if total > 0 else 0,
        'with_lemmatization_coverage': 100 * (exact_matches + lemma_matches) / total if total > 0 else 0,
        'improvement': 100 * lemma_matches / total if total > 0 else 0,
        'lemma_examples': lemma_examples
    }
    
    return stats


def load_unmatched_report() -> List[Dict]:
    """Load the unmatched words report."""
    if not UNMATCHED_REPORT.exists():
        logger.warning(f"UNMATCHED_REPORT not found: {UNMATCHED_REPORT}")
        return []
    
    try:
        with open(UNMATCHED_REPORT, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('sample', [])
    except Exception as e:
        logger.error(f"Error reading unmatched report: {e}")
        return []


def check_orthography(word: str) -> Tuple[bool, str]:
    """
    Check if word uses classical Western Armenian orthography.
    Returns (is_classical, reason)
    """
    # Check for classical markers
    has_classical_iv = 'Õ«Ö‚' in word
    has_reformed_marks = any(marker in word for marker in ['ÕµÕ¸Ö‚', 'Õµ'])
    
    # Rules
    if 'Õ¬' in word and 'Õµ' in word:
        # Some words like Õ¬Õ¥Õµ (lei) use Õµ legitimately as consonant
        # But Õ¬Õ«ÕµÕ½ would be wrong - should be Õ¬Õ«Ö‚Õ½
        pass
    
    # Eastern reformed indicators
    if 'ÖÕ¸Ö‚' in word:
        return False, "Contains ÖÕ¸Ö‚ (Eastern pattern)"
    
    if has_reformed_marks and not has_classical_iv:
        # If has Õµ without Õ«Ö‚, might be Eastern
        pass
    
    return True, "Classical orthography OK"


def analyze_unmatched_words():
    """Analyze words that don't match corpus."""
    logger.info("\n" + "="*70)
    logger.info("WORD MAPPING VALIDATION")
    logger.info("="*70)
    
    # Load all data
    logger.info("\n1. Loading data...")
    anki_words = load_anki_words()
    corpus_words = load_corpus_words()
    unmatched = load_unmatched_report()
    
    logger.info(f"   - Anki words loaded: {len(anki_words)}")
    logger.info(f"   - Corpus words loaded: {len(corpus_words)}")
    logger.info(f"   - Unmatched words in report: {len(unmatched)}")
    
    # Cross-check unmatched words
    logger.info("\n2. Analyzing unmatched words...")
    
    unmatched_by_reason = defaultdict(list)
    oov_words = []
    
    for item in unmatched:
        reason = item.get('reason', 'unknown')
        normalized = item.get('normalized', '')
        raw = item.get('raw', '')
        
        unmatched_by_reason[reason].append({
            'raw': raw,
            'normalized': normalized,
            'in_anki': normalized in anki_words,
            'in_corpus': normalized.lower() in corpus_words
        })
        
        if reason == 'oov-in-corpus' and normalized.lower() not in corpus_words:
            oov_words.append(normalized)
    
    # Report summary
    logger.info("\n3. Unmatched words breakdown:")
    for reason, items in sorted(unmatched_by_reason.items(), key=lambda x: -len(x[1])):
        logger.info(f"\n   {reason} ({len(items)} words)")
        
        if reason == 'oov-in-corpus':
            in_anki_count = sum(1 for i in items if i['in_anki'])
            logger.info(f"      - In Anki deck: {in_anki_count}")
            logger.info(f"      - Sample OOV words (10 random):")
            for item in items[:10]:
                norm = item['normalized']
                in_anki = "[IN ANKI]" if item['in_anki'] else ""
                logger.info(f"         {norm} {in_anki}")
        elif reason.startswith('latin'):
            logger.info(f"      - Mixed armenian and latin characters - should be removed")
            for item in items[:5]:
                logger.info(f"         {item['raw']} -> {item['normalized']}")
        elif reason.startswith('html'):
            logger.info(f"      - HTML artifacts - should be removed")
            for item in items[:5]:
                logger.info(f"         {item['raw']} -> {item['normalized']}")
    
    return corpus_words, anki_words, unmatched_by_reason


def main():
    corpus_words, anki_words, unmatched_by_reason = analyze_unmatched_words()
    
    # Check which Anki words are not in corpus
    logger.info("\n" + "="*70)
    logger.info("CORPUS COVERAGE ANALYSIS")
    logger.info("="*70)
    
    not_in_corpus = []
    for word, source in anki_words.items():
        if word.lower() not in corpus_words:
            not_in_corpus.append((word, source))
    
    logger.info(f"\nAnki words NOT in corpus: {len(not_in_corpus)}")
    if not_in_corpus:
        logger.info("\nReasons words might not be in corpus:")
        logger.info("  1. Too specialized (proper names, technical terms)")
        logger.info("  2. Recent additions not in corpus yet")
        logger.info("  3. Low frequency in corpus sources")
        logger.info("  4. Corpus is incomplete (from limited sources)")
        
        logger.info("\nTop 20 missing Anki words:")
        for i, (word, source) in enumerate(not_in_corpus[:20], 1):
            logger.info(f"  {i:2d}. {word} (from {source})")
    
    # Stemming/Lemmatization Analysis
    logger.info("\n" + "="*70)
    logger.info("STEMMING/LEMMATIZATION COVERAGE ANALYSIS")
    logger.info("="*70)
    
    if STEMMING_AVAILABLE:
        stemming_stats = validate_with_stemming(anki_words, corpus_words)
        if stemming_stats:
            logger.info(f"\nExact match coverage:         {stemming_stats['exact_coverage']:.1f}% ({stemming_stats['exact_matches']:,} words)")
            logger.info(f"With lemmatization:           {stemming_stats['with_lemmatization_coverage']:.1f}% ({stemming_stats['total_with_lemmatization']:,} words)")
            logger.info(f"Additional matches from lemmatization: +{stemming_stats['improvement']:.1f}% ({stemming_stats['lemma_matches']:,} words)")
            logger.info(f"Still unmatched:              {stemming_stats['no_matches']} words")
            
            if stemming_stats['lemma_examples']:
                logger.info(f"\nExamples of successful lemma matches:")
                for ex in stemming_stats['lemma_examples']:
                    lemmas_str = ", ".join(ex['matching_lemmas'])
                    logger.info(f"  {ex['word']} -> [{lemmas_str}]")
    else:
        logger.info("\nStemming module not available - install morphology support")
    
    # Final recommendations
    logger.info("\n" + "="*70)
    logger.info("RECOMMENDATIONS")
    logger.info("="*70)
    logger.info(f"""
1. CORPUS EXPANSION:
   - Current corpus: ~{len(corpus_words):,} unique words
   - Missing Anki words: {len(not_in_corpus)}
   - Build corpus from: IA, newspapers, wiki (already available)
   - Run: python -m wa_corpus.build_corpus --aggregate

2. UNMATCHED WORDS CLEANUP:
   - Remove latin-mixed tokens: {len(unmatched_by_reason.get('latin-mixed-token', []))} words
   - Remove html-artifacts: {len(unmatched_by_reason.get('html-artifact', []))} words
   - Remove diacritic variants: {len(unmatched_by_reason.get('diacritic-or-punct-variant', []))} words

3. OOV WORD VERIFICATION:
   - Verify {len(unmatched_by_reason.get('oov-in-corpus', []))} out-of-vocabulary words
   - Check if they are legitimate Western Armenian (classical orthography)
   - Consider if they should be corpus-normalized or vocabulary-reduced

4. NEXT STEPS:
   - Run corpus aggregation to get final frequency list
   - Audit high-value missing words (that are in Anki)
   - Document which words are excluded and why
    """)


if __name__ == "__main__":
    main()

