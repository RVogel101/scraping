#!/usr/bin/env python
"""Quick test of new sentence generation features."""

from lousardzag.sentence_generator import generate_verb_sentences, generate_noun_sentences
from lousardzag.morphology.core import romanize

print("=" * 70)
print("Testing New Sentence Generation Features")
print("=" * 70)

# Test 1: Basic romanization
print("\nTest 1: Romanization (Armenian to Latin script)")
print("-" * 70)
test_words = [
    ("ես", "yes (I)"),
    ("կարդամ", "gardam (I read)"),
    ("նա", "na (he/she)"),
    ("հայ", "hay (Armenian)"),
]
for arm, expected in test_words:
    rom = romanize(arm)
    print(f"  {arm:15} → {rom:20} (expected: {expected})")

# Test 2: Verb sentences with different pronoun styles
print("\nTest 2: Verb Sentences with Different Pronoun Styles")
print("-" * 70)
infinitive = "կարդալ"
translation = "read"

print(f"\nVerb: {infinitive} ({translation})")
print()

styles = ["explicit", "optional", "none"]
for style in styles:
    sentences = generate_verb_sentences(
        infinitive, translation=translation, max_sentences=1, pronoun_style=style
    )
    if sentences:
        label, arm, eng = sentences[0]
        print(f"  {style:10}: {arm:30} | {eng}")

# Test 3: Romanized sentences
print("\nTest 3: Sentences with Romanization")
print("-" * 70)
sentences = generate_verb_sentences(infinitive, translation=translation, max_sentences=2, pronoun_style="optional")
for label, arm, eng in sentences:
    rom = romanize(arm)
    print(f"  ARM: {arm}")
    print(f"  ROM: {rom}")
    print(f"  ENG: {eng}")
    print()

# Test 4: Supporting words parameter
print("Test 4: Supporting Words Integration")
print("-" * 70)
sentences_with_support = generate_verb_sentences(
    infinitive,
    translation=translation,
    max_sentences=2,
    supporting_words=["պուստակ", "հատ"],
    pronoun_style="optional",
)
print(f"  Generated {len(sentences_with_support)} sentences with supporting words")
for label, arm, eng in sentences_with_support:
    print(f"    {arm} | {eng}")

# Test 5: Noun sentences with pronoun styles
print("\nTest 5: Noun Sentences with Optional Pronouns")
print("-" * 70)
noun = "պուստակ"  # book
for style in ["explicit", "optional"]:
    sentences = generate_noun_sentences(noun, translation="book", max_sentences=1, pronoun_style=style)
    if sentences:
        label, arm, eng = sentences[0]
        print(f"  {style:10}: {arm:40} | {eng}")

print("\n" + "=" * 70)
print("All tests completed successfully!")
print("=" * 70)
