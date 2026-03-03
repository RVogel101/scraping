# Sentence Progression System — User Guide

## Overview

The **Sentence Progression System** gradually introduces grammar concepts as learners progress through levels. Instead of overwhelming students with all sentence types at once, it presents one grammar concept at a time, building progressively.

---

## How It Works

### 1. **Sentence Tiers** (Grammar Concepts)

Sentences are organized into tiers representing different grammar concepts:

```
Articles:        "a sin is here", "I want a sin", "I have a sin"
Nominative:      "the sin is beautiful", "the sin is new", "this sin is good"
Accusative:      "I see the sin", "I love the sin", "I want the sin"
Genitive-Dative: "the sin's color is...", "I give to the sin"
Ablative:        "I come from the sin", "He comes from the sin"
Instrumental:    "I write with the sin", "We go with the sin"
Plural:          "the sins are big", "the sins are good"
Verb Present:    "I read", "he reads", "we read"
Verb Past:       "I read", "he read"
Verb Future:     "I will read"
…and more
```

### 2. **Progressive Unlocking by Level**

New tiers become available as learners progress:

| Level | Available Tiers |
|-------|-----------------|
| 1     | Articles, Nominative |
| 2     | + Accusative |
| 3     | + Genitive-Dative |
| 4     | + Ablative |
| 5     | + Instrumental, Plural |
| 6-10  | + Verb Present, Verb Past |
| 11-15 | + Verb Future, Imperative |
| 16-20 | + Imperfect, Advanced |

### 3. **Sentence Selection at Each Word**

When generating sentences for a word at a given level, the system:

1. **Identifies available tiers** for that level
2. **Selects N tiers in introduction order** (configured via `sentences_per_tier`)
3. **Picks 1-M sentences** from each selected tier (configured via `sentences_per_concept`)

Example at Level 3 with `sentences_per_tier=1`:
- Word: "մեղ" (sin)
- Available tiers: Articles, Nominative, Accusative, Genitive-Dative
- Selected: First available = "Articles"
- Sentences shown: "A sin is here", "I want a sin", "I have a sin"

---

## Configuration

### Using `SentenceProgressionConfig`

```python
from lousardzag.sentence_progression import SentenceProgressionConfig

# Strict: One grammar concept per word (recommended for beginners)
config = SentenceProgressionConfig(
    enable_progression=True,
    sentences_per_tier=1,        # Only 1 grammar concept per word
    sentences_per_concept=3,     # But show 3 example sentences from that concept
)

# Relaxed: Multiple concepts per word (faster progression)
config = SentenceProgressionConfig(
    enable_progression=True,
    sentences_per_tier=2,        # Show 2 different grammar concepts per word
    sentences_per_concept=1,     # 1 example per concept
)

# No progression: Use all sentences (original behavior)
config = SentenceProgressionConfig(
    enable_progression=False,
)
```

### Using with Card Generation

```python
from lousardzag.card_generator import CardGenerator
from lousardzag.sentence_progression import SentenceProgressionConfig

gen = CardGenerator()
config = SentenceProgressionConfig(
    enable_progression=True,
    sentences_per_tier=1,
)

gen.generate_sentence_cards(
    word="մեղ",
    pos="noun",
    translation="sin",
    level=3,                      # Current level
    progression_config=config,    # Enable progression
)
```

---

## Example Output

### Level 1 (Articles + Nominative available)
```
Word: մեղ (sin)
✓ A sin is here.                   ← Article (indefinite)
✓ I want a sin.
✓ I have a sin.
```

### Level 2 (Accusative now available)
```
Word: մեղ (sin)  
✓ I see the sin.                   ← Accusative (object case)
✓ I love the sin.
✓ I want the sin.
```

### Level 3 (Genitive-Dative now available)
```
Word: մեղ (sin)
✓ The sin's color is beautiful.   ← Genitive-Dative (possessive)
✓ I give to the sin.
✓ The sin's name is beautiful.
```

---

## Key Features

✓ **One concept at a time** - Cognitive load stays manageable
✓ **Scaffolded learning** - Articles before cases, cases before tenses
✓ **Configurable pacing** - Adjust `sentences_per_tier` for faster/slower progression
✓ **Level-aware** - Different content at each level (1-20)
✓ **Backward compatible** - Disable with `enable_progression=False` to use original behavior

---

## Testing

Run the test to see the progression system in action:

```bash
python 04-tests/test_sentence_progression.py
```

This will show:
1. Which tiers are available at each level
2. What sentences get selected at different levels
3. Comparison between strict and relaxed progression

---

## Next Steps

To fine-tune the progression for your learning goals:

1. **Adjust tier ordering** in `TIER_INTRODUCTION_ORDER` if you want different concepts introduced in a different sequence

2. **Modify availability by level** in `AVAILABLE_TIERS_BY_LEVEL` if you want some grammar concepts earlier/later

3. **Change pacing** via `sentences_per_tier` in the `SentenceProgressionConfig`:
   - Set to 1 for maximum scaffolding (one concept per word)
   - Set to 2-3 for balanced progression
   - Set to 4+ for aggressive progression

4. **Control sentence density** via `sentences_per_concept`:
   - Smaller number = fewer examples per concept
   - Larger number = more examples to master the concept
