"""Audit vocabulary usage across all generated sentences.

This tool helps identify which words are introduced in sentences before
they've been explicitly taught, allowing you to reorder curriculum or
flag prerequisites.
"""
import sys
import json
from collections import defaultdict, Counter

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, '02-src')

from lousardzag.database import CardDatabase


def audit_vocabulary_prerequisites(db_path: str | None = None):
    """Analyze vocabulary usage across all sentences in the database."""
    db = CardDatabase(db_path) if db_path else CardDatabase()
    
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    conn.row_factory = sqlite3.Row
    
    # Get all sentences with their vocabulary
    sentences = conn.execute("""
        SELECT s.*, c.word as card_word, c.translation as card_translation
        FROM sentences s
        JOIN cards c ON s.card_id = c.id
        ORDER BY s.id
    """).fetchall()
    
    print(f"\n{'='*70}")
    print(f"VOCABULARY PREREQUISITE AUDIT")
    print(f"{'='*70}\n")
    print(f"Total sentences analyzed: {len(sentences)}\n")
    
    # Track which words appear in sentences for other words
    vocab_usage = defaultdict(set)  # word -> set of (sentence_id, context_word)
    all_vocab_used = Counter()
    
    for row in sentences:
        vocab_json = row['vocabulary_used']
        if not vocab_json:
            continue
            
        vocab_list = json.loads(vocab_json)
        card_word = row['card_word'].lower()
        
        for word in vocab_list:
            word_lower = word.lower()
            all_vocab_used[word_lower] += 1
            
            # Track if this word appears in a sentence for a DIFFERENT word
            if not word_lower.startswith(card_word[:3]):  # Rough check for different roots
                vocab_usage[word_lower].add((row['id'], card_word, row['card_translation']))
    
    # Print most frequently used "helper" vocabulary
    print("Most Frequently Used Helper Vocabulary:")
    print("(Words that appear in sentences for other words)\n")
    
    for word, count in all_vocab_used.most_common(30):
        contexts = vocab_usage.get(word, set())
        if contexts:
            print(f"  {word:15s} — used {count:3d} times in {len(contexts):3d} different word contexts")
    
    print(f"\n{'-'*70}")
    print("Vocabulary Prerequisites Report:")
    print(f"{'-'*70}\n")
    
    # Show which words appear in sentences before being taught
    for word in sorted(vocab_usage.keys()):
        contexts = vocab_usage[word]
        if len(contexts) >= 3:  # Only show if used frequently
            print(f"\n'{word}' appears in sentences for:")
            for sent_id, context_word, context_trans in sorted(contexts)[:10]:
                print(f"    - {context_word} ({context_trans})")
            if len(contexts) > 10:
                print(f"    ... and {len(contexts) - 10} more")
    
    conn.close()
    
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Audit vocabulary prerequisites in generated sentences")
    parser.add_argument("--db-path", help="Path to SQLite database (optional)")
    args = parser.parse_args()
    
    audit_vocabulary_prerequisites(args.db_path)

