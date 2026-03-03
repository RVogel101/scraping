# Next Session Instructions

**Start here** when resuming work on Lousardzag. This document contains mandatory checklists and common workflows.

## Before You Do ANYTHING Phonetic-Related

**MANDATORY 10-MINUTE CHECKLIST:**

- [ ] Read ARMENIAN_QUICK_REFERENCE.md (2 minutes)
- [ ] Note the voicing reversal pattern (բ=p, պ=b, etc.)
- [ ] Test your understanding with 5 words: պետք, ժամ, ջուր, ոչ, իւր
- [ ] Bookmark /memories/western-armenian-requirement.md (persistent reminder)
- [ ] Check 02-src/lousardzag/phonetics.py line 1 (Western Armenian declaration)

**If you skip this, you will default to Eastern Armenian. This happened repeatedly in the previous session.**

---

## Project State Summary

**What's Working** ✅
- Vocabulary ordering system (5 modes, 3 strategies, 4 presets)
- Western Armenian phonetics module (38-letter map with difficulty scoring)
- Flashcard generation with syllable/sentence controls
- 323 passing tests across unit and integration suites
- Morphological analysis and verb conjugation

**What's Incomplete** ⚠️
- Context-aware phoneme implementation (documented but not fully functional)
- Comprehensive documentation guides (to be created)
- Diphthong coverage (partial, needs expansion)
- Nayiri dictionary scraper (broken, low priority)

**Critical Constraint** 🔴
- Western Armenian has BACKWARDS voicing (letter appearance ≠ pronunciation)
- This is unique to Western dialect and NOT true of Eastern Armenian
- Defaulting to Eastern voicing will silently corrupt phonetic data

---

## Common Commands

### Generate Vocabulary

```bash
# Standard: JLPT-style 7 levels (N1-N7)
python 07-tools/gen_vocab_simple.py --preset n-standard --max-words 140 \
  --csv-output 08-data/vocab_n_standard.csv

# Custom: Difficulty-focused with growth batches
python 07-tools/gen_vocab_simple.py \
  --ordering-mode difficulty_band \
  --batch-strategy growth --batch-base 20 --batch-step 5 --batch-max 30 \
  --max-words 100 \
  --csv-output 08-data/vocab_difficulty.csv
```

### Run Tests

```bash
# Full test suite
python -m pytest 04-tests/ -q

# Specific test category
python -m pytest 04-tests/unit/test_difficulty.py -v

# With coverage
python -m pytest 04-tests/ --cov=lousardzag
```

### Preview Vocabulary

```bash
# Generate with HTML preview
python 07-tools/gen_vocab_simple.py --preset n-standard --max-words 140 \
  --html-output 08-data/vocabulary_preview.html
```

### Check Phonetics

```bash
# Test phonetic module directly
python 02-src/lousardzag/phonetics.py

# Or interactively
python
>>> from lousardzag.phonetics import get_phonetic_transcription
>>> get_phonetic_transcription('պետք')
```

---

## Workflow: Adding a Phonetic Feature

**Scenario**: You need to add/modify Armenian phonetic mappings

### Step 1: Verify Western Armenian (5 min)
```bash
# Read reference materials
cat ARMENIAN_QUICK_REFERENCE.md        # Quick lookup
cat WESTERN_ARMENIAN_PHONETICS_GUIDE.md # Complete phoneme map
```

### Step 2: Find the Letter (2 min)
```python
# 02-src/lousardzag/phonetics.py
ARMENIAN_PHONEMES = {
    'բ': {'ipa': 'p', 'english': 'p', 'difficulty': 1, ...},  # ← Edit here
    'պ': {'ipa': 'b', 'english': 'b', 'difficulty': 1, ...},
    ...
}
```

### Step 3: Update Both IPA and English Fields
```python
# CORRECT - both fields updated
'բ': {'ipa': 'p', 'english': 'p', 'difficulty': 1, 'word': 'pat'},

# WRONG - only partial update
'բ': {'ipa': 'p', 'english': 'b', ...},  # Mismatched!
```

### Step 4: Test with Sample Words (5 min)
```bash
# Test your change
python -c "from lousardzag.phonetics import ARMENIAN_PHONEMES; \
  print(ARMENIAN_PHONEMES['բ']['ipa'])"
# Should print: p (not b)

# Test with full transcription
python -c "from lousardzag.phonetics import get_phonetic_transcription; \
  print(get_phonetic_transcription('պետք'))"
# Should have 'b' sound, not 'p'
```

### Step 5: Regenerate Vocabulary (5 min)
```bash
python 07-tools/gen_vocab_simple.py --preset n-standard --max-words 140 \
  --csv-output 08-data/vocab_n_standard.csv
```

### Step 6: Verify Output (2 min)
```bash
# Check IPA column populated
python -c "import pandas as pd; df = pd.read_csv('08-data/vocab_n_standard.csv'); \
  print('IPA blanks:', df['IPA'].isna().sum())"
# Should print: 0
```

### Step 7: Commit
```bash
git add 02-src/lousardzag/phonetics.py 08-data/vocab_n_standard.csv
git commit -m "fix(phonetics): correct Western Armenian [letter] IPA mapping

- Updated [letter] from [old] to [new]
- Regenerated vocabulary with new mapping
- Verified with test words: պետք, ժամ, ջուր
- All 140 words have phonetic data"
```

---

## Workflow: Implementing Context-Aware Phonemes

**Scenario**: Making ո, ե, յ, or ւ work based on word position

### Background
Four letters change pronunciation by position:
- **ո**: [v] before consonants → [ɔ] as vowel
- **ե**: [jɛ] at word start → [ɛ] in middle
- **յ**: [h] at word start → [j] in middle
- **ւ**: [u] in diphthongs → [v] between vowels

Currently documented but not implemented in get_phonetic_transcription().

### Implementation Steps

1. **Enhance get_phonetic_transcription()**
   - Add word-position detection
   - Apply context rules per letter
   - Return appropriate IPA for position

2. **Add Tests**
   ```python
   test_cases = {
       'եղջ': 'yeghch', # ե at start = ye
       'բե': 'pe',      # ե in middle = e
       'ոչ': 'voch',   # ո + consonant = vo
       'որ': 'vor',    # ո + consonant = vo (before ր)
   }
   ```

3. **Regenerate Vocabulary**
   ```bash
   python 07-tools/gen_vocab_simple.py --preset n-standard --max-words 140
   ```

4. **Verify IPA Quality Improves**
   ```bash
   # Check if phonetic difficulty scores changed appropriately
   python -c "import pandas as pd; df = pd.read_csv('08-data/vocab_n_standard.csv'); \
     print(df[['Word', 'IPA', 'Phonetic_Difficulty']].head(20))"
   ```

---

## Common Mistakes & How to Fix Them

### Mistake 1: Eastern Armenian Voicing

**Symptom**: Phonetic output has wrong voicing (բ=b, պ=p)

**Fix**:
1. Read ARMENIAN_QUICK_REFERENCE.md § "The Wrong Way"
2. Check phonetics.py — you've reversed the mappings
3. Swap all voicing-reversed pairs
4. Regenerate vocabulary
5. Test: պետք should give "bedk" not "petik"

**Prevention**: Always start with voicing checklist before phonetic work

### Mistake 2: Incomplete Context Handling

**Symptom**: ո and ե always pronounced the same regardless of position

**Fix**:
1. Check if get_phonetic_transcription() has position detection
2. If not documented, add docstring explaining context rules
3. Implement position-aware logic
4. Add test cases for each context

**Prevention**: document expected behavior before implementing

### Mistake 3: Missing IPA Updates

**Symptom**: English approximations updated but IPA not updated (or vice versa)

**Fix**:
1. Regenerate vocabulary: `gen_vocab_simple.py ...`
2. Inspect CSV — IPA column should match English sounds
3. If mismatch, update both fields in ARMENIAN_PHONEMES
4. Regenerate again

**Prevention**: Always update IPA and english fields together; use pre-commit hooks if available

### Mistake 4: Forgetting Diphthongs

**Symptom**: Words like իւր transcribed incorrectly (treating ի and ւ separately)

**Fix**:
1. Check if ARMENIAN_DIGRAPHS has the letter pair
2. If missing, add it: `'իւ': {'ipa': 'ju', 'english': 'yoo', ...}`
3. Verify get_phonetic_transcription() checks digraphs before single letters
4. Test: իւր should come out as "yur" not "i-v-ur"

**Prevention**: Review ARMENIAN_DIGRAPHS at start of phonetics.py

---

## File Navigation Quick Reference

| File | Purpose | Edit When |
|------|---------|-----------|
| ARMENIAN_QUICK_REFERENCE.md | Quick lookup (START HERE) | Never (reference only) |
| WESTERN_ARMENIAN_PHONETICS_GUIDE.md | Complete phoneme reference (TO BE CREATED) | When phonetics change |
| 02-src/lousardzag/phonetics.py | Implementation | Adding/fixing phonemes |
| 07-tools/gen_vocab_simple.py | Vocabulary generation | Changing ordering logic |
| 08-data/vocab_n_standard.csv | Output vocabulary | Generated by gen_vocab_simple.py |
| /memories/western-armenian-requirement.md | Persistent reminder | When updating memory |

---

## Git Workflow

### Branch Strategy
- Work on `pr/copilot-swe-agent/2` or feature branch
- Atomic commits per logical change
- Rebase before pushing to consolidate related commits
- Clear commit messages with scope: `fix(phonetics):`, `feat(ordering):`, `docs:`

### Commit Pattern
```bash
# Good
git commit -m "fix(phonetics): correct Western Armenian բ mapping to p

- Updated ARMENIAN_PHONEMES['բ'] IPA to p (was b)
- English approximation: pat (English p sound)
- Regenerated 08-data/vocab_n_standard.csv
- Tested with պետք: outputs bedk correctly"

# Not good
git commit -m "fixed phonetics"
git commit -m "WIP: testing stuff"
```

---

## Session Template

**At Start:**
1. Read ARMENIAN_QUICK_REFERENCE.md
2. Run tests: `python -m pytest 04-tests/ -q`
3. Check current branch and uncommitted changes

**During Work:**
1. Make small, focused changes
2. Test immediately: `python -m pytest 04-tests/ -q`
3. Commit after each logical unit

**At End:**
1. Run full test suite
2. Regenerate vocabulary if phonetics changed
3. Commit or push
4. Update this document if workflow changed

---

## Quick Decision Tree

**"Should I work on phonetics?"**
1. Do you understand Western Armenian voicing reversal? → NO → Read ARMENIAN_QUICK_REFERENCE.md first
2. Is it context-aware letters (ո, ե, յ, ւ)? → YES → Check if implementation is documented
3. Is it adding a new diphthong? → YES → Add to ARMENIAN_DIGRAPHS, test, commit
4. Is it fixing a voicing pair? → YES → Update both ipa and english fields, regenerate vocab, test

**"Should I work on vocabulary ordering?"**
1. Does gen_vocab_simple.py exist? → YES, it works
2. Do all 4 presets work? → YES (l1-core, l2-expand, l3-bridge, n-standard)
3. Need new mode? → Add to ORDERING_MODES dict, implement logic, test, commit

**"Should I work on card generation?"**
1. Does generate_ordered_cards.py work? → YES
2. Are tests passing? → CHECK: `pytest 04-tests/test_card_generator.py -v`
3. Need new feature? → Implement, test, commit with clear scope

---

## Resources

- 📖 ARMENIAN_QUICK_REFERENCE.md — Start here
- 📖 WESTERN_ARMENIAN_PHONETICS_GUIDE.md — Complete reference (to be created)
- 🔗 /memories/western-armenian-requirement.md — Persistent reminder
- 🧪 04-tests/ — Test examples for any feature
- 💾 08-data/ — Vocabulary outputs and HTML previews
- 🔧 .github/copilot-instructions.md — Project-wide guidelines

---

## Questions?

If you get stuck:
1. **Phonetic questions**: Check ARMENIAN_QUICK_REFERENCE.md test words first
2. **Vocabulary questions**: See 08-data/vocab_n_standard.csv examples
3. **Git questions**: Read recent commits: `git log --oneline -10`
4. **Test failures**: Run failing test with `-v`: `pytest 04-tests/test_x.py -v`

Remember: When in doubt about Armenian phonetics, **verify the voicing pattern** (backwards from appearance).

---

Last Updated: March 3, 2026
Branch: pr/copilot-swe-agent/2
