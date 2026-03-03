# Vocabulary Ordering System Guide

**Complete documentation of the Lousardzag vocabulary ordering, batching, and proficiency system.**

---

## Quick Start

Generate vocabulary with N1-N7 proficiency levels:
```bash
python 07-tools/gen_vocab_simple.py --preset n-standard --max-words 140 \
  --proficiency-enabled --csv-output 08-data/vocab_n_standard.csv
```

Output: CSV with 140 words organized into 7 proficiency blocks (N1-N7), 20 words each.

---

## Architecture Overview

The vocabulary system has **three independent dimensions** that can be combined:

1. **Ordering Mode** — How vocabulary is ranked (5 options)
2. **Batch Strategy** — How ranked words are grouped (3 options)
3. **Proficiency System** — How batches are labeled/leveled (1 system: N1-N7)

These are orthogonal—any combination is valid.

---

## Ordering Modes (5 Total)

Ordering determines the sequence in which vocabulary is selected and ranked.

### 1. Frequency-Based Ordering

```bash
python gen_vocab_simple.py --ordering-mode frequency --max-words 100
```

**How it works:**
- Ranks by `frequency_rank` from wa_frequency_list.csv
- 1 = most common, 1,471,689 = rarest
- Produces natural Zipfian distribution

**Source data**: wa_frequency_list.csv (1.47M entries)

**Coverage**: ~3,084 vocabulary items matched to frequency data (95% of typical vocab)

**Use case**: Natural language exposure, authentic word prioritization

**Advantages**:
- Real corpus-based priorities
- Follows language statistics
- No artificial reordering

**Disadvantages**:
- May front-load abstract/frequent words (articles, pronouns)
- No consideration for difficulty
- No POS balance in early sections

**Example output snippet**:
```
1. հայ (hay) - rank 1, "Armenian"
2. մեր (mer) - rank 2, "our"
3. վար (var) - rank 3, "down"
...
100. արժ (arj) - rank 8,923, "worth"
```

### 2. POS-Frequency Ordering

```bash
python gen_vocab_simple.py --ordering-mode pos_frequency --max-words 100
```

**How it works:**
- Groups by Part of Speech: Noun > Verb > Adjective > Adverb > Other
- Within each POS, orders by frequency
- Resets frequency rank at POS boundary

**Use case**: Teach word types progressively, balanced POS exposure

**Advantages**:
- Spreads parts of speech across learning
- Ensures verbs aren't all at the end
- Clear linguistic structure

**Disadvantages**:
- May deprioritize common words of less-frequent POS
- Artificial grouping may not match learning readiness

**Example distribution**:
```
Nouns: words 1-40 (most common nouns first)
Verbs: words 41-65 (most common verbs first, fewer total)
Adjectives: words 66-82
Adverbs: words 83-95
Other: words 96-100
```

### 3. Band-POS-Frequency Ordering

```bash
python gen_vocab_simple.py --ordering-mode band_pos_frequency --max-words 100
```

**How it works:**
- Divides vocabulary into syllable difficulty bands:
  - Band 1: 1-2 syllables (monosyllables, disyllables)
  - Band 2: 2-3 syllables
  - Band 3: 3+ syllables (polysyllables)
- Within each band, orders by POS then frequency

**Use case**: Graduated difficulty with balanced POS at each level

**Advantages**:
- Front-loads easier words (fewer syllables = easier)
- Maintains POS variety at each difficulty level
- Natural progression

**Disadvantages**:
- Syllable count ≠ pronunciation difficulty
- May skip shorter but phonetically hard words

**Example structure**:
```
Band 1 (1-2 syllables):
  - Nouns 1, 3, 5 (short, common)
  - Verbs 2, 4, 6
  - Adjectives 7, 8
  (~40 words)

Band 2 (2-3 syllables):
  - Nouns 1, 3, 5 (medium, common in their band)
  - Verbs 2, 4
  (~35 words)

Band 3 (3+ syllables):
  - Everything else
  (~25 words)
```

### 4. Difficulty-Based Ordering

```bash
python gen_vocab_simple.py --ordering-mode difficulty --max-words 100
```

**How it works:**
- Ranks by phonetic difficulty score (1-5 scale)
- 1.0 = simple pronunciation
- 5.0 = very difficult (gutturals, complex clusters)
- No syllable grouping; pure difficulty progression

**Source data**: calculate_phonetic_difficulty() from phonetics.py

**Factors boosting difficulty**:
- Guttural consonants (խ, ղ) → +1 automatic boost
- Consonant clusters
- Uncommon phoneme combinations
- Trilled r (ռ)

**Use case**: Pronunciation-focused learning, easing into hard sounds

**Advantages**:
- Learner-friendly pronunciation progression
- Explicit difficulty awareness
- Gradual introduction to gutturals

**Disadvantages**:
- May delay high-frequency but difficult words
- Frequency sacrificed for pedagogy

**Example progression**:
```
1. բան (ban) - difficulty 1.0, common word, "thing"
2. մեր (mer) - difficulty 1.0, "our"
3. շատ (shat) - difficulty 1.0, "much"
...
50. խաղ (khagh) - difficulty 4.0, "game" (has խ guttural)
...
100. ղինդ (ghinc) - difficulty 4.0, "rose" (has ղ guttural)
```

### 5. Difficulty-Band-Based Ordering

```bash
python gen_vocab_simple.py --ordering-mode difficulty_band --max-words 100
```

**How it works:**
- Combines difficulty with syllable banding
- Divides by syllables (like band_pos_frequency)
- Within each band, orders by phonetic difficulty

**Use case**: Graduated difficulty with syllable constraints

**Advantages**:
- Doubly graduated (syllables + phonetics)
- Most structured progression
- Balanced phonetic and length difficulty

**Disadvantages**:
- Complex mental model for users
- May be over-engineered for some use cases

---

## Batch Strategies (3 Total)

Batch strategies determine how ordered words are grouped into batches.

### 1. Fixed Size Strategy

```bash
python gen_vocab_simple.py \
  --batch-strategy fixed \
  --batch-size 20 \
  --max-words 100
```

**How it works:**
- Creates batches of exactly N words
- Last batch may be smaller if not divisible

**Parameters**:
- `--batch-size N`: Batch size (default: 20)

**Example** (100 words, batch-size 20):
```
Batch 1: Words 1-20
Batch 2: Words 21-40
Batch 3: Words 41-60
Batch 4: Words 61-80
Batch 5: Words 81-100
```

**Use case**: Simple, predictable grouping for uniform learning load

**Output**: `Batch` column in CSV = 1, 2, 3, 4, 5

### 2. Growth Strategy

```bash
python gen_vocab_simple.py \
  --batch-strategy growth \
  --batch-base 20 \
  --batch-step 5 \
  --batch-max 30 \
  --max-words 120
```

**How it works:**
- Starts with base-size batch
- Increases by step each batch
- Caps at max size
- Once max reached, stays at max

**Parameters**:
- `--batch-base N`: Starting batch size
- `--batch-step N`: Increment per batch
- `--batch-max N`: Maximum batch size

**Example** (base=20, step=5, max=30):
```
Batch 1: 20 words (base)
Batch 2: 25 words (base + step)
Batch 3: 30 words (base + 2*step, hits max)
Batch 4: 30 words (stays at max)
Batch 5: 30 words (stays at max)
... all subsequent: 30 words
```

**Use case**: Graduated learning load, starting conservatively, ramping up

**Advantages**:
- Accommodates learner growth
- Starts easy, becomes challenging
- User can adjust when overwhelmed

**Disadvantages**:
- May not align with curriculum
- Requires planning for batch transitions

### 3. Banded Strategy

```bash
python gen_vocab_simple.py \
  --batch-strategy banded \
  --max-words 100
```

**How it works:**
- Resets batch count at boundary changes (e.g., syllable band transitions)
- Different batch for each combination of (syllable_band, POS)
- Creates naturally aligned groups

**Example** (if using band_pos_frequency ordering):
```
Band 1 Nouns: Batch 1 (20 words)
Band 1 Verbs: Batch 2 (15 words)
Band 1 Adjectives: Batch 3 (8 words)
Band 2 Nouns: Batch 4 (20 words)
Band 2 Verbs: Batch 5 (12 words)
... etc
```

**Use case**: Linguistically-aware grouping aligned with difficulty progression

**Advantages**:
- Natural boundaries at difficulty/POS transitions
- Each batch is coherent set
- Works well with banded ordering

**Disadvantages**:
- Batch sizes may vary significantly
- Harder to plan curriculum

---

## Proficiency Block System

### Overview

Proficiency blocks are labels assigned to contiguous groups of vocabulary, representing language proficiency levels.

Currently only supports **N-standard** (JLPT-inspired, 7 levels).

### N-Standard System (N1-N7)

```bash
python gen_vocab_simple.py \
  --preset n-standard \
  --max-words 140 \
  --proficiency-enabled
```

**Levels**: 7 total (N1 through N7)

**Distribution**: Contiguous split of ordered vocabulary

**Mapping** (140 words):
```
N1: Words 1-20     (Advanced, most common/easiest)
N2: Words 21-40
N3: Words 41-60
N4: Words 61-80    (Intermediate)
N5: Words 81-100
N6: Words 101-120
N7: Words 121-140  (Beginner, least common/hardest)
```

**Naming Convention** (like JLPT):
- N1 = Advanced
- N2 = Upper-intermediate
- N3 = Intermediate
- N4 = Lower-intermediate
- N5 = Elementary
- N6 = Pre-elementary (Lousardzag extension)
- N7 = Complete beginner (Lousardzag extension, for very large vocabularies)

**Usage**:
- `StdBlock` column = 1-7 (numeric)
- `StdLabel` column = "N1"-"N7" (text label)

**Scaling**: Works with any vocabulary size
- 70 words: 10 per level
- 140 words: 20 per level (default)
- 280 words: 40 per level

---

## Presets (Pre-Configured Combinations)

### Preset: l1-core (Level 1 - Core Vocabulary)

```bash
python gen_vocab_simple.py --preset l1-core --max-words 60
```

**Configuration**:
- Size: 60 words (default)
- Ordering: pos_frequency (nouns then verbs)
- Batches: Fixed, ~20 words each (3 batches)
- POS Filter: Nouns and verbs only

**Purpose**: Complete beginners, essential vocabulary

**Output columns**: Word, Definition, POS, Syllables, Rank, IPA, English_Approx, Phonetic_Difficulty, Batch

**Example flow**:
```
Batch 1: Common nouns (մարդ, տուն, ջուր, ...)
Batch 2: More nouns (գաղտնիք, ...) + easy verbs (եմ, ես, ...)
Batch 3: Medium verbs (լինել, հասկանալ, ...)
```

### Preset: l2-expand (Level 2 - Expand)

```bash
python gen_vocab_simple.py --preset l2-expand --max-words 80
```

**Configuration**:
- Size: 80 words (default)
- Ordering: band_pos_frequency (by syllables, then POS, then frequency)
- Batches: Growth (base=20, step=4, max=24)
- POS Filter: All types

**Purpose**: Early intermediate, expanding to adjectives/adverbs

**Output columns**: Includes all (POS variety, phonetic data)

**Stage progression**:
```
Batch 1: Short words, mixed POS (monosyllables) - 20 words
Batch 2: Short + medium - 24 words
Batch 3: Medium + longer - 24 words
Batch 4: Longer words - 12 remaining
```

### Preset: l3-bridge (Level 3 - Bridge)

```bash
python gen_vocab_simple.py --preset l3-bridge --max-words 100
```

**Configuration**:
- Size: 100 words (default)
- Ordering: difficulty_band (difficulty within syllable bands)
- Batches: Growth (base=24, step=6, max=36)
- POS Filter: All types

**Purpose**: Mid through advanced, pronunciation awareness

**Stage progression**:
```
Batch 1: Easy pronunciation - 24 words
Batch 2: Medium pronunciation - 30 words
Batch 3: Hard pronunciation (includes gutturals) - 36 words
Batch 4: Remaining - 10 words
```

### Preset: n-standard (Standards-Aligned, JLPT-Style)

```bash
python gen_vocab_simple.py \
  --preset n-standard \
  --max-words 140 \
  --proficiency-enabled
```

**Configuration**:
- Size: Flexible (default 140, can go to 280+)
- Ordering: frequency (pure frequency from corpus)
- Batches: Banded (resets at boundaries)
- Proficiency: N1-N7 labels enabled

**Purpose**: Standards-aligned progression, JLPT-style levels

**Output columns**:
```
Word | Definition | POS | Syllables | Rank | IPA | English_Approx | 
Phonetic_Difficulty | Batch | StdBlock | StdLabel
```

**Proficiency levels**:
- N1 (words 1-20): Most frequent, should learn first
- N2 (words 21-40): Second tier
- ...
- N7 (words 121-140): Least frequent, learn last

**Flexibility**:
- Scale to any size: `--max-words 280` gives 40 words per level
- Maintains frequency ordering
- Proficiency labels scale proportionally

---

## Output CSV Format

### Column Specifications

All CSV outputs include these columns (may vary by preset):

| Column | Type | Source | Example |
|--------|------|--------|---------|
| Word | str | Input | `պետք` |
| Definition | str | CardDatabase | "he/she/it needs" |
| POS | str | Inference | "verb" |
| Syllables | int | Phonetics | 2 |
| Rank | int | wa_frequency_list.csv | 12,345 |
| Frequency_Band | str | Computed | "2-3 syllables" |
| IPA | str | Phonetics module | "bedk" |
| English_Approx | str | Phonetics module | "bet + ik" |
| Phonetic_Difficulty | float | calculate_phonetic_difficulty() | 1.5 |
| Batch | int | Batch strategy | 2 |
| StdBlock | int | Proficiency system | 1-7 (only if proficiency enabled) |
| StdLabel | str | Proficiency system | "N2" (only if proficiency enabled) |

---

## Common Use Cases

### Use Case 1: "I want the 100 most common words"

```bash
python 07-tools/gen_vocab_simple.py \
  --preset l1-core \
  --max-words 100 \
  --csv-output my_vocab.csv
```

Result: Frequency ordering, nouns/verbs only, 5 batches of 20

### Use Case 2: "I want JLPT-style 7 proficiency levels"

```bash
python 07-tools/gen_vocab_simple.py \
  --preset n-standard \
  --max-words 280 \
  --proficiency-enabled \
  --csv-output n_level_vocab.csv
```

Result: 280 words (40 per level N1-N7), frequency ordered, with StdLabel column

### Use Case 3: "Pronunciation difficulty matters to my learners"

```bash
python 07-tools/gen_vocab_simple.py \
  --preset l3-bridge \
  --max-words 150 \
  --csv-output difficulty_aware.csv
```

Result: Difficulty-banded ordering, growth batches ramping to 36 words, phonetic columns prominent

### Use Case 4: "Custom: frequency order, growth batches, 200 words"

```bash
python 07-tools/gen_vocab_simple.py \
  --ordering-mode frequency \
  --batch-strategy growth \
  --batch-base 25 \
  --batch-step 5 \
  --batch-max 50 \
  --max-words 200 \
  --csv-output my_custom.csv
```

Result: 200 words in frequency order, batch sizes: 25, 30, 35, 40, 45, 50, 50, ...

---

## Data Quality & Filtering

### Sentence/Phrase Detection

The system filters out **sentence-like translations** to keep vocabulary atomic:

**Heuristics**:
1. **Question marks**: Removes entries where definition contains "?"
2. **Long definitions**: Removes if definition > 4 words (likely phrase)
3. **Pronoun starters**: Removes if definition starts with pronouns (he, she, to be, etc.)

**Impact**: Removed 26 entries from 840 Anki deck cards

**Example filtered entries**:
- "he is always talking" (4+ words, pronoun start)
- "Do you understand?" (question mark)
- "What color is this?" (question mark)

### Frequency Matching

**Database coverage**: 3,242 vocabulary entries  
**Frequency matched**: ~3,084 (95%)  
**Fallback**: Unmatched entries get default frequency score (frequency_rank = 999,999)

### POS Filtering (Optional)

```bash
python gen_vocab_simple.py \
  --pos-include "noun,verb" \
  --max-words 100
```

Supported POS values: noun, verb, adjective, adverb, pronoun, etc.

---

## Validation Checklist

After generating vocabulary, verify:

- [ ] Word count matches `--max-words` parameter
- [ ] No duplicate words in output
- [ ] All words have definitions (Definition column non-empty)
- [ ] Frequency ranks present for matched words (Rank < 999,999 for 95%+)
- [ ] Syllable counts reasonable (1-5 range typical)
- [ ] IPA and English_Approx columns populated
- [ ] Phonetic difficulty scores 1-5 range
- [ ] Batch assignments contiguous (1, 2, 3, ...)
- [ ] For proficiency: StdBlock 1-7, StdLabel N1-N7
- [ ] CSV is valid (quotes/escaping correct for parsing)

### Quick Validation Script

```bash
python -c "
import pandas as pd
df = pd.read_csv('vocab_n_standard.csv')
print(f'Words: {len(df)}')
print(f'Duplicates: {df.duplicated(\"Word\").sum()}')
print(f'Missing definitions: {df[\"Definition\"].isna().sum()}')
print(f'IPA blanks: {df[\"IPA\"].isna().sum()}')
print(f'Difficulty distribution:')
print(df['Phonetic_Difficulty'].describe())
print(f'N-level distribution:')
print(df['StdLabel'].value_counts().sort_index())
"
```

---

## Technical Details

### Integration Points

**Database**: lousardzag.database.CardDatabase
- Caches 3,242 entries
- Provides definition enrichment
- POS tag inference

**Phonetics**: lousardzag.phonetics
- get_phonetic_transcription()
- calculate_phonetic_difficulty()
- ARMENIAN_PHONEMES dict
- ARMENIAN_DIGRAPHS dict

**Frequency Data**: wa_frequency_list.csv
- 1,471,689 entries
- Format: lemma, frequency_rank (ascending)
- Coverage varies by input

### Performance

Typical generation (~140 words):
- Database cacheing: < 1 second
- Ordering: < 1 second
- Batch assignment: < 0.5 seconds
- CSV write: < 0.5 seconds
- **Total**: ~ 2-3 seconds

---

## Future Enhancements

Potential improvements (not yet implemented):

1. **Frequency decay**: Newer frequency data, temporal corpus awareness
2. **Contextual relevance**: Based on learner goals/interests
3. **Spaced repetition integration**: Vocabulary timing based on SRS algorithms
4. **Etymology tracking**: Historical word relationships
5. **Synonym grouping**: Learning related words together
6. **Regional variants**: Western vs. Eastern pronunciation variants

---

## Related Documentation

- [PROJECT_ASSESSMENT.md](PROJECT_ASSESSMENT.md) — Current project state
- [ARMENIAN_QUICK_REFERENCE.md](ARMENIAN_QUICK_REFERENCE.md) — Phonetics quick lookup
- [WESTERN_ARMENIAN_PHONETICS_GUIDE.md](WESTERN_ARMENIAN_PHONETICS_GUIDE.md) — Complete phonetic reference
- [NEXT_SESSION_INSTRUCTIONS.md](NEXT_SESSION_INSTRUCTIONS.md) — Workflow guide

---

**Last Updated**: March 3, 2026  
**Implementation**: 07-tools/gen_vocab_simple.py (570+ lines)
