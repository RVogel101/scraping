#!/usr/bin/env python3
"""
Test and demonstration of sentence progression system.

Shows how the progression system gradually introduces grammar concepts as
learners progress through levels.

Run with:
  python test_sentence_progression.py
"""

import sys
from pathlib import Path

# Add source to path
sys.path.insert(0, str(Path(__file__).parent.parent / "02-src"))

from lousardzag.sentence_progression import (
    SentenceProgressionConfig,
    select_sentences_for_progression,
    get_available_tiers_at_level,
    AVAILABLE_TIERS_BY_LEVEL,
    TIER_INTRODUCTION_ORDER,
)
from lousardzag.sentence_generator import generate_noun_sentences

# ─── Test 1: View available tiers by level ────────────────────────────

print("="*70)
print("AVAILABLE SENTENCE TIERS BY LEVEL")
print("="*70 + "\n")

for level in [1, 2, 3, 4, 5, 10, 15, 20]:
    tiers = get_available_tiers_at_level(level)
    print(f"Level {level:2d}: {len(tiers):2d} tiers")
    for tier in sorted(tiers):
        print(f"  • {tier}")
    print()

# ─── Test 2: Demonstrate sentence selection ───────────────────────────

print("="*70)
print("SENTENCE SELECTION AT DIFFERENT LEVELS")
print("="*70 + "\n")

# Generate sample sentences for a word
sample_word = "մեղ"  # "sin" - noun
sample_sentences = generate_noun_sentences(sample_word, "i_class", "sin", max_sentences=50)

print(f"Total available sentences for '{sample_word}': {len(sample_sentences)}")
print("\nSentences by form label:")
for form_label, arm, eng in sample_sentences:
    print(f"  {form_label:30s} | {eng}")

# Now show what gets selected at different levels with progression
print("\n" + "="*70)
print("WHAT SENTENCES ARE SELECTED AT EACH LEVEL (with progression)")
print("="*70 + "\n")

config = SentenceProgressionConfig(
    enable_progression=True,
    sentences_per_tier=1,  # 1 sentence per tier
    sentences_per_concept=1,  # 1 concept per sentence
)

for level in [1, 2, 3, 4, 5]:
    selected = select_sentences_for_progression(sample_sentences, level, config)
    print(f"\nLevel {level}: {len(selected)} sentences selected")
    for form_label, arm, eng in selected:
        print(f"  • [{form_label:20s}] {eng}")

# ─── Test 3: Compare strict vs relaxed progression ──────────────────

print("\n" + "="*70)
print("COMPARISON: STRICT VS RELAXED PROGRESSION")
print("="*70 + "\n")

# Strict: one grammar concept at a time
strict_config = SentenceProgressionConfig(
    enable_progression=True,
    sentences_per_tier=1,  # One tier per word
)

# Relaxed: multiple concepts per word
relaxed_config = SentenceProgressionConfig(
    enable_progression=True,
    sentences_per_tier=2,  # Two tiers per word
)

print("STRICT (1 grammar concept per word):")
level = 3
strict_selection = select_sentences_for_progression(sample_sentences, level, strict_config)
for form_label, _, eng in strict_selection:
    print(f"  • {eng}")

print("\nRELAXED (2 grammar concepts per word):")
relaxed_selection = select_sentences_for_progression(sample_sentences, level, relaxed_config)
for form_label, _, eng in relaxed_selection:
    print(f"  • {eng}")

print("\n" + "="*70)
print("Configuration complete. Progression system is ready to use.")
print("="*70)
