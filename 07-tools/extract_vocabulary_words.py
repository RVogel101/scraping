#!/usr/bin/env python3
"""
Extract ONLY vocabulary words from Anki export, filtering out examples/sentences.

A word is considered "vocabulary" if:
- It's a single word (no spaces or very few)
- It doesn't contain grammatical context labels
- It doesn't contain example sentences
- It's pure Armenian (no latin mixed in)

Also validates against corpus using optional stemming/lemmatization.
"""

import json
import re
import sys
from pathlib import Path
from collections import defaultdict

# Avoid UnicodeEncodeError on Windows cp1252 consoles by escaping unsupported chars.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="backslashreplace")

# Add 02-src to path for morphology imports
SRC_DIR = Path(__file__).parent.parent / "02-src"
sys.path.insert(0, str(SRC_DIR))

try:
    import csv
    from lousardzag.stemmer import match_word_with_stemming
    STEMMING_AVAILABLE = True
except ImportError:
    STEMMING_AVAILABLE = False
    print("Note: Stemming not available - using exact match only")


def is_vocabulary_word(text):
    """Determine if text is a actual vocabulary word vs. example/context."""
    
    # Skip if contains parentheses with context
    if re.search(r'^\(', text):
        return False
    
    # Skip if too long (likely a sentence)
    if len(text) > 100:
        return False
    
    # Skip if contains multiple spaces (likely a sentence)
    if text.count(' ') > 2:
        return False
    
    # Skip if looks like grammar note
    if any(x in text.lower() for x in ['noun', 'verb', 'adjective', 'adverb', 'present', 'past']):
        return False
    
    # Skip if contains sentence-ending punctuation in middle (Armenian full stop, etc.)
    if '\u0589' in text[:-1]:  # Armenian full stop not at end
        return False
    
    # Keep if it's pure Armenian letters (allowing diacritics, punctuation at edges)
    # Must be at least 2 chars
    if len(text) >= 2 and re.search(r'[\u0530-\u0589]', text):
        # Remove trailing punctuation
        clean = re.sub(r'[\u0589\u055D\u06D4\u066B.!?\u00BB\s]+$', '', text).strip()
        # Must still have Armenian content
        if len(clean) >= 2 and re.search(r'[\u0530-\u0589]', clean):
            return True
    
    return False


def extract_vocab_words():
    """Extract only vocabulary words."""
    
    ANKI_EXPORT = Path(__file__).parent.parent / "08-data" / "anki_export.json"
    CORPUS_FILE = Path(__file__).parent.parent / "02-src" / "wa_corpus" / "data" / "wa_frequency_list.csv"
    
    print("Loading Anki export...")
    with open(ANKI_EXPORT, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("Loading corpus...")
    corpus_words = set()
    try:
        import csv
        with open(CORPUS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                word = row.get('word', '').strip().lower()
                if word:
                    corpus_words.add(word)
    except Exception as e:
        print(f"Warning: Could not load corpus: {e}")
    
    print(f"Corpus size: {len(corpus_words)} words")
    
    # Extract vocabulary words
    vocab_words = set()
    vocab_stats = {
        'in_corpus': [],
        'not_in_corpus': [],
        'by_group': defaultdict(list)
    }
    
    for group_name, notes in data.items():
        for note in notes:
            armenian_raw = note['fields'].get('Armenian', '').strip()
            
            if not armenian_raw:
                continue
            
            # Try splitting by commas first (multiple vocabulary variants)
            for variant in armenian_raw.split(','):
                variant = variant.strip()
                
                # Remove HTML tags first
                variant = re.sub(r'<[^>]*?>', '', variant)
                variant = variant.replace('&nbsp;', ' ').replace('&amp;', '&')
                
                # Check if this looks like vocabulary
                if is_vocabulary_word(variant):
                    # Clean up
                    clean = re.sub(r'[\u0589\u055D.!?\u00BB\s]+$', '', variant).strip()
                    
                    if len(clean) >= 2:
                        vocab_words.add(clean)
                        
                        # Check corpus match (exact or with stemming)
                        match_type = "no_match"
                        if STEMMING_AVAILABLE:
                            in_corpus, match_type = match_word_with_stemming(clean, corpus_words)
                        else:
                            in_corpus = clean.lower() in corpus_words
                            match_type = "exact" if in_corpus else "no_match"
                        
                        stat_item = {
                            'word': clean,
                            'group': group_name,
                            'in_corpus': in_corpus,
                            'match_type': match_type
                        }
                        
                        if in_corpus:
                            vocab_stats['in_corpus'].append(stat_item)
                        else:
                            vocab_stats['not_in_corpus'].append(stat_item)
                        
                        vocab_stats['by_group'][group_name].append(clean)
    
    # Report
    print(f"\n{'='*70}")
    print(f"VOCABULARY WORD EXTRACTION")
    print(f"{'='*70}")
    
    print(f"\nTotal vocabulary words found: {len(vocab_words)}")
    print(f"  - In corpus: {len(vocab_stats['in_corpus'])}")
    print(f"  - NOT in corpus: {len(vocab_stats['not_in_corpus'])}")
    
    coverage = len(vocab_stats['in_corpus']) / len(vocab_words) * 100 if vocab_words else 0
    print(f"  - Corpus coverage: {coverage:.1f}%")
    
    print(f"\nVocabulary by group:")
    for group, words in sorted(vocab_stats['by_group'].items(), key=lambda x: -len(x[1])):
        in_count = sum(1 for w in words if w.lower() in corpus_words)
        coverage = in_count / len(words) * 100 if words else 0
        group_safe = group.encode('utf-8', errors='replace').decode('utf-8')
        try:
            print(f"  {group_safe}: {len(words)} words ({coverage:.0f}% in corpus)")
        except:
            print(f"  [Group]: {len(words)} words ({coverage:.0f}% in corpus)")
    
    # Stemming analysis
    if STEMMING_AVAILABLE:
        print(f"\n{'='*70}")
        print(f"STEMMING/LEMMATIZATION ANALYSIS")
        print(f"{'='*70}")
        exact_matches = sum(1 for item in vocab_stats['in_corpus'] if item['match_type'] == 'exact')
        lemma_matches = sum(1 for item in vocab_stats['in_corpus'] if item['match_type'] == 'lemma')
        exact_coverage = exact_matches / len(vocab_words) * 100 if vocab_words else 0
        lemma_coverage = (exact_matches + lemma_matches) / len(vocab_words) * 100 if vocab_words else 0
        improvement = lemma_coverage - exact_coverage
        
        print(f"\nExact match:              {exact_matches:,} words ({exact_coverage:.1f}%)")
        print(f"With lemmatization:       {exact_matches + lemma_matches:,} words ({lemma_coverage:.1f}%)")
        print(f"Improvement from lemmas:  +{improvement:.1f}% ({lemma_matches} additional words)")
        
        if improvement > 0.1:
            print(f"\nExamples of lemma matches:")
            lemma_examples = [item for item in vocab_stats['in_corpus'] if item['match_type'] == 'lemma'][:5]
            for ex in lemma_examples:
                word_safe = ex['word'].encode('utf-8', errors='replace').decode('utf-8')
                try:
                    print(f"  {word_safe} [matched via lemmatization]")
                except:
                    print(f"  [word] [matched via lemmatization]")
    
    print(f"\nSample vocabulary words (first 30):")
    for w in sorted(vocab_words)[:30]:
        status = "[+]" if w.lower() in corpus_words else "[-]"
        print(f"  {status} {w}")
    
    print(f"\nTop 30 missing vocabulary words (not in corpus):")
    for i, item in enumerate(sorted(vocab_stats['not_in_corpus'], key=lambda x: x['word'])[:30], 1):
        print(f"  {i:2d}. {item['word']}")
    
    # Save report
    output_file = Path(__file__).parent.parent / "08-data" / "vocab_analysis_report.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total_vocabulary_words': len(vocab_words),
            'in_corpus': len(vocab_stats['in_corpus']),
            'not_in_corpus': len(vocab_stats['not_in_corpus']),
            'coverage_percent': coverage,
            'corpus_size': len(corpus_words),
            'words_in_corpus': sorted([x['word'] for x in vocab_stats['in_corpus']]),
            'words_missing': sorted([x['word'] for x in vocab_stats['not_in_corpus']]),
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n[OK] Report saved to: {output_file}")
    
    return vocab_words, vocab_stats, corpus_words


if __name__ == "__main__":
    extract_vocab_words()

