# Sentence Progression System - Implementation Summary

## What Was Built

You requested a fine-tuned sentence generation progression logic that introduces grammar concepts **one at a time**, building gradually through levels. This has been successfully implemented.

---

## Key Components

### 1. **sentence_progression.py** — Core Progression Engine
- Defines 12 sentence tiers (grammar concepts): Articles, Nominative, Accusative, Genitive-Dative, Ablative, Instrumental, Plural, Present Tense, Past Tense, Future Tense, Imperative, Imperfect
- Maps sentence form labels to tiers automatically
- Controls which tiers are available at each level (1-20)
- Selects sentences progressively based on configuration

### 2. **SentenceProgressionConfig** — Configuration Class
Allows fine-tuning how many grammar concepts are introduced and when:

```python
SentenceProgressionConfig(
    enable_progression=True,          # Enable/disable the system
    sentences_per_tier=1,             # How many grammar concepts per word
    sentences_per_concept=3,          # How many example sentences per concept
)
```

### 3. **Integration with CardGenerator**
- Modified `generate_sentence_cards()` to accept `level` and `progression_config` parameters
- Sentences are now filtered based on current level when progression is enabled
- Backward compatible: works without progression if config is not provided

---

## How It Works

### Example: Learning "մեղ" (sin) at Different Levels

**Level 1** (Articles + Nominative available):
```
✓ A sin is here.           ← Indefinite article ("a")
✓ I want a sin.
✓ I have a sin.
```

**Level 2** (Accusative now available, but articles introduced first):
```
✓ I see the sin.           ← Accusative (direct object)
✓ I love the sin.
✓ I want the sin.
```

**Level 3** (Genitive-Dative available):
```
✓ The sin's color is beautiful.  ← Genitive-dative (possessive)
✓ I give to the sin.
✓ The sin's name is beautiful.
```

---

## Progression Modes

### **STRICT** (One concept at a time)
```python
config = SentenceProgressionConfig(
    enable_progression=True,
    sentences_per_tier=1,      # Only 1 grammar concept per word
    sentences_per_concept=3,   # But 3 example sentences
)
```
**Best for:** Beginners, controlled pacing, minimal cognitive load

### **BALANCED** (Two concepts per word)
```python
config = SentenceProgressionConfig(
    enable_progression=True,
    sentences_per_tier=2,      # 2 grammar concepts per word
    sentences_per_concept=2,   # 2 examples each
)
```
**Best for:** Intermediate learners, faster progression, balanced scaffolding

### **RELAXED** (Multiple concepts)
```python config = SentenceProgressionConfig(
    enable_progression=True,
    sentences_per_tier=3,      # 3 grammar concepts per word
    sentences_per_concept=1,   # 1 example each
)
```
**Best for:** Advanced learners, rapid progression, wide exposure

### **NO PROGRESSION** (Original behavior)
```python
config = SentenceProgressionConfig(
    enable_progression=False,  # Use all sentences
)
```
**Best for:** Comprehensive coverage, all examples at once

---

## Progression Timeline

| Level | Available Tiers | Introduction Order |
|-------|-----------------|-------------------|
| 1     | Articles, Nominative | Start with "a X" templates |
| 2     | + Accusative | Add "I see the X" |
| 3     | + Genitive-Dative | Add possessive "X's ..." |
| 4     | + Ablative | Add source "from the X" |
| 5     | + Instrumental, Plural | Add tool "with the X", plurals |
| 6-10  | + Verb Present, Past | Add basic verb conjugations |
| 11-15 | + Verb Future, Imperative | Add future, commands |
| 16-20 | + Imperfect | Add imperfect tense |

---

## Usage in Your Pipeline

### Option 1: Direct Integration with CardGenerator

```python
from lousardzag.card_generator import CardGenerator
from lousardzag.sentence_progression import SentenceProgressionConfig

gen = CardGenerator()
config = SentenceProgressionConfig(
    enable_progression=True,
    sentences_per_tier=2,
)

gen.generate_sentence_cards(
    word="մեղ",
    pos="noun",
    translation="sin",
    level=3,                      # Current level (1-20)
    progression_config=config,    # Enable progression
)
```

### Option 2: Add CLI Flag (Future)

When integrating with your main generation script, you can:

```python
# In your CLI:
parser.add_argument("--enable-progression", action="store_true")
parser.add_argument("--progression-strictness", choices=["strict", "balanced", "relaxed"], default="balanced")

# Then:
if args.enable_progression:
    if args.progression_strictness == "strict":
        config = SentenceProgressionConfig(sentences_per_tier=1, sentences_per_concept=3)
    elif args.progression_strictness == "balanced":
        config = SentenceProgressionConfig(sentences_per_tier=2, sentences_per_concept=2)
    else:  # relaxed
        config = SentenceProgressionConfig(sentences_per_tier=3, sentences_per_concept=1)
else:
    config = SentenceProgressionConfig(enable_progression=False)
```

---

## Testing & Verification

### Run the Test Suite
```bash
# View progression system in action
python 04-tests/test_sentence_progression.py

# Run example with different modes
python 07-tools/example_sentence_progression.py --strict --level 3
python 07-tools/example_sentence_progression.py --relaxed --level 3
python 07-tools/example_sentence_progression.py --level 5
```

### What the Tests Show
1. **Available tiers by level** — Which grammar concepts are taught at each level
2. **Sentence selection** — Exactly which sentences would be shown to a learner
3. **Mode comparison** — Difference between strict/balanced/relaxed progression

---

## Customization Points

### 1. Change Introduction Order
Edit `TIER_INTRODUCTION_ORDER` in `sentence_progression.py`:
```python
TIER_INTRODUCTION_ORDER = [
    TIER_ARTICLES,        # Show articles first
    TIER_NOMINATIVE,      # Then nominative cases
    TIER_ACCUSATIVE,      # Then accusative
    # ... etc
]
```

### 2. Change Level-Based Availability
Edit `AVAILABLE_TIERS_BY_LEVEL` in `sentence_progression.py`:
```python
AVAILABLE_TIERS_BY_LEVEL = {
    1: {TIER_ARTICLES, TIER_NOMINATIVE},
    2: {TIER_ARTICLES, TIER_NOMINATIVE, TIER_ACCUSATIVE},
    # ... customize as needed
}
```

### 3. Change Pacing
Adjust `sentences_per_tier` in your config:
- **1** = Slowest (one concept at a time) → most scaffolding
- **2-3** = Balanced (two-three concepts) → recommended
- **4+** = Fastest (multiple concepts) → less scaffolding

---

## Example Output

With **STRICT mode at Level 3**:

```
Total available sentences for 'մեղ': 21

WHAT SENTENCES ARE SELECTED:
✓ A sin is here.                   ← From Articles tier (first available at level 3)
✓ I want a sin.                    ← Still from Articles tier
✓ I have a sin.                    ← Still from Articles tier

(Other tiers like Nominative, Accusative, etc. available but not shown yet)
```

With **BALANCED mode at Level 3**:

```
✓ A sin is here.                   ← From Articles tier (1st concept shown)
✓ I want a sin.
✓ The sin is beautiful.            ← From Nominative tier (2nd concept shown)
✓ The sin is new.
```

---

## What's Next?

The progression system is now ready to use. To fully integrate it:

1. **Test with your current generation** - Run `example_sentence_progression.py` with different modes
2. **Choose your progression mode** - Decide on strict/balanced/relaxed based on your target audience
3. **Integrate with main CLI** - Add `--enable-progression` and `--progression-strictness` flags
4. **Monitor effectiveness** - Gather feedback on whether learners prefer the scaffolded approach
5. **Fine-tune tiers** - Adjust `sentences_per_tier` and `sentences_per_concept` based on usage

---

## Files Created/Modified

**New Files:**
- `02-src/lousardzag/sentence_progression.py` — Core progression engine
- `04-tests/test_sentence_progression.py` — Test and demonstration script
- `07-tools/example_sentence_progression.py` — Usage example
- `SENTENCE_PROGRESSION.md` — User guide

**Modified Files:**
- `02-src/lousardzag/card_generator.py` — Added progression parameters to `generate_sentence_cards()`

---

**Your sentence progression system is ready to use!** Test it out and let me know if you'd like to adjust the pacing, tiers, or introduction order.
