"""
Demo script showing the component analysis system in action.

Demonstrates:
  1. Hidden vowel (ը) syllable counting in grammatical contexts
  2. Phonological complexity scoring (rare phonemes, clusters)
  3. Morphological difficulty analysis for nouns and verbs
  4. Integration with progression system sorting
"""

from lousardzag.morphology.core import ARM
from lousardzag.morphology.difficulty import (
    count_syllables_with_context,
    score_word_difficulty,
    analyze_word,
)
from lousardzag.progression import WordEntry, ProgressionPlan

# ─── Hidden Vowel Demo ────────────────────────────────────────────────

print("=" * 70)
print("  HIDDEN VOWEL (ը) SYLLABLE COUNTING")
print("=" * 70)

# Word: երք (erq) — "day"
# Base: ե-ր (ye-r) = 2 syllables
# With grammar: ե-ր-ք (ye-r-y_schwa-k) = 3 syllables
erq = ARM["ye"] + ARM["r"] + ARM["y_schwa"] + ARM["k"]
count_base = count_syllables_with_context(erq, with_epenthesis=False)
count_grammar = count_syllables_with_context(erq, with_epenthesis=True)
print(f"\nExample: երք (erq — 'day')")
print(f"  Base syllables:       {count_base}")
print(f"  With grammatical ը:   {count_grammar}")
print(f"  Hidden vowel context: When used in oblique cases (gen-dat, abla, instr)")

# ─── Difficulty Scoring Demo ──────────────────────────────────────────

print("\n" + "=" * 70)
print("  MORPHOLOGICAL DIFFICULTY SCORING")
print("=" * 70)

test_words = [
    # (armenian word, pos, declension/verb_class, english_meaning)
    (ARM["m"] + ARM["a"], "noun", "i_class", "մա — 'mother'"),
    (ARM["m"] + ARM["ye"] + ARM["gh"], "noun", "i_class", "մեղ — 'sin'"),
    (ARM["h"] + ARM["a"] + ARM["y"] + ARM["r"], "noun", "a_class", "հայր — 'father'"),
    (ARM["g"] + ARM["a"] + ARM["l"], "verb", "weak", "գալ — 'to come'"),
    (ARM["g"] + ARM["n"] + ARM["a"] + ARM["l"], "verb", "weak", "գնալ — 'to go'"),
]

print("\nWord Difficulty Scores (1.0–10.0, higher = harder):\n")
for word, pos, cls, meaning in test_words:
    score = score_word_difficulty(word, pos, declension_class=cls if pos == "noun" else None,
                                  verb_class=cls if pos == "verb" else None)
    print(f"  {meaning:30} | difficulty = {score:.2f}")

# ─── Component Analysis Demo ──────────────────────────────────────────

print("\n" + "=" * 70)
print("  DETAILED COMPONENT ANALYSIS")
print("=" * 70)

word = ARM["m"] + ARM["ye"] + ARM["gh"]
analysis = analyze_word(word, pos="noun", declension_class="i_class")
print(f"\nWord: {word} (մեղ — 'sin')")
print(f"{analysis.summary()}\n")
print(f"  Detailed breakdown:")
print(f"    • Syllables (base):    {analysis.syllables_base}")
print(f"    • Syllables (w/ grammar): {analysis.syllables_with_grammar}")
print(f"    • Phonological score:  {analysis.phonological_score:.2f}")
print(f"    • Cluster score:       {analysis.cluster_score:.2f}")
print(f"    • Affix count:         {analysis.affix_count:.2f}")
print(f"    • Declension class:    {analysis.declension_class}")

# ─── Progression Integration Demo ─────────────────────────────────────

print("\n" + "=" * 70)
print("  PROGRESSION SYSTEM INTEGRATION")
print("=" * 70)

# Create sample word list
sample_words = [
    WordEntry(ARM["m"] + ARM["a"], "mother", "noun", frequency_rank=1, declension_class="i_class"),
    WordEntry(ARM["m"] + ARM["ye"] + ARM["gh"], "sin", "noun", frequency_rank=2, declension_class="i_class"),
    WordEntry(ARM["h"] + ARM["a"] + ARM["y"] + ARM["r"], "father", "noun", frequency_rank=3, declension_class="a_class"),
    WordEntry(ARM["g"] + ARM["a"] + ARM["l"], "to come", "verb", frequency_rank=4, verb_class="weak"),
]

print(f"\nInput word list (by frequency rank):")
for w in sample_words:
    print(f"  {w.word:10} | rank={w.frequency_rank} | syl={w.syllable_count} | difficulty={w.difficulty_score:.2f}")

# Build progression plan
plan = ProgressionPlan(sample_words)
print(f"\n{plan.summary()}")

print(f"\nOrdered learning sequence:")
for batch in plan.vocab_batches:
    print(f"  Batch {batch.batch_index} (Level {batch.level}):")
    for word_entry in batch.words:
        print(f"    • {word_entry.word:10} | difficulty={word_entry.difficulty_score:.2f} | syl={word_entry.syllable_count}")

print("\n" + "=" * 70)
print("Component analysis integrated into progression system ✓")
print("=" * 70)
