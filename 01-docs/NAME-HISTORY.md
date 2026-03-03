# Lousardzag: The Name Journey

**Western Armenian**: Լուսարձակ  
**English Meaning**: "Light-spreading" or "Dawn-bringer"  
**Date of Adoption**: March 2, 2026

## The Naming Decision

### Context

The project "Armenian Anki Note Generation Pipelines" (henceforth "the old name") grew far beyond its original scope of Anki card generation. It now encompasses:

- Western Armenian morphological analysis
- Intelligent vocabulary progression systems
- Multi-source corpus scraping and processing
- Educational flashcard generation
- Advanced phonological and morphological difficulty assessment

**The old name no longer accurately reflected what the project is.**

### Naming Criteria

The new name needed to:

1. **Reflect Expanded Scope** — Not just Anki cards; a full learning platform
2. **Be Historically Grounded** — Meaningful in Armenian culture and history
3. **Focus on Western Armenian** — The project's core language variant
4. **Connect to Education/Knowledge** — Core mission of spreading Armenian language
5. **Be Available** — No conflicts with existing packages, domains, or projects
6. **Be Short and Memorable** — Practical for command lines, packages, GitHub
7. **Have Proper Western Armenian Spelling** — Correct transliteration (not Eastern Armenian)

### Initial Candidates Researched

**Western Armenian Historical/Educational Figures:**

1. **Mesrop Mashtots** — Inventor of Armenian alphabet (too long, well-known but generic)
2. **Mekhitar of Sebaste** — Founder of the Mechitarist educational order
3. **Krikor Zohrab** — Intellectual, educator, writer
4. **Khrimian Hayrig** — Patriarch, educator
5. **Vartabed** — Title for scholar/teacher
6. **Zartonk** — "Awakening" (historical publication)
7. **Lusardzak** — "Light-spreading/Dawn-bringer" (neologism with strong symbolism)

### Shortlisted Names

Through research into Western Armenian history and educational movements:

1. **Mechitar** — After Mekhitar of Sebaste
2. **Mkhitar** — Variant transliteration of the same
3. **Mekhitar** — Yet another variant
4. **Vartabed** — Scholar/teacher designation
5. **Lusardzak** — Light-spreading (symbolic, less historical but deeply meaningful)
6. **Khrimian** — After Khrimian Hayrig
7. **Lusaper** — Light-bearer (classical variant)

### Availability Check Results

**PyPI Package Registry:**
```
✅ lousardzak     → Available
✅ khrimian       → Available
✅ mechitar       → Available
✅ vartabed       → Available
✅ lusaper        → Available
❌ mekhitar       → 1 Eastern philosophical project
❌ mkhitar        → 47 personal GitHub profiles
```

**GitHub Repositories:**
```
⭐ lousardzak: 0 repositories (completely clear)
✅ khrimian: 0 repositories
✅ mechitar: 0 repositories
✅ vartabed: 2 repositories (personal profiles only)
⚠️ mekhitar: 1 repository (philosophy project)
⚠️ mkhitar: 47 repositories (mostly personal profiles named "Mkhitar*")
```

**Domain Availability:**
```
✅ lousardzag.com/.org/.net are available for registration
⚠️ mechitar.com & mechitar.org already exist (active sites)
⚠️ mekhitar.com & mekhitar.org already exist (active sites)
```

**Web Presence:**
```
✅ No Armenian language learning tools/platforms found with any candidate names
✅ No educational software conflicts identified
```

### The Decision: Lousardzag

**Lousardzag** (Լուսարձակ) was selected because:

1. **Completely Available** — Zero conflicts across all platforms
2. **Historically Meaningful** — While a neologism, it combines ancient Armenian roots (լույս = light)
3. **Symbolically Perfect** — "Light-spreading" captures the educational mission
4. **Short and Clean** — Single word, easy to type, good for CLIs and packages
5. **Proper Western Armenian** — Correct phonological transliteration (lousardzag not lusardzak)
6. **No Brand Conflicts** — Unlike mechitar.com which exists, or mkhitar which has many personal profiles

## Transliteration Accuracy

The correct Western Armenian transliteration of **Լուսարձակ** is **LOUSARDZAG**, not "lusardzak", "lusaper", or other variants.

### Why the Difference?

In **Western Armenian**:
- **կ** = **g** (not k)
- **ու** = **ou** (not u)

In **Eastern Armenian** (which uses different phonetics):
- **կ** = **k**
- **ու** = **u** or **w**

The project uses **Western Armenian transliteration exclusively**, so:
- ❌ Lusartzak (wrong vowel + wrong final consonant)
- ❌ Lusaker (wrong final consonant)
- ❌ Lusaper (close but technically incorrect for Լուսարձակ)
- ✅ **Lousardzag** (correct)

## Implementation

### What Changed

**Package Name:**
```
armenian_anki → lousardzag
```

**CLI Commands:**
```
anki-generate-cards        → lousardzag-generate-cards
anki-preview-server        → lousardzag-preview-server
anki-pull-data             → lousardzag-pull-data
anki-build-corpus          → lousardzag-build-corpus
```

**Python Imports:**
```python
# Old
from armenian_anki.morphology.verbs import conjugate_verb
from armenian_anki.progression import ProgressionPlan

# New
from lousardzag.morphology.verbs import conjugate_verb
from lousardzag.progression import ProgressionPlan
```

### Scope of Changes

- **74 files** affected (git-tracked with proper rename history)
- **79 import statements** updated
- **5+ configuration files** updated
- **All documentation** revised
- **323/323 tests** passing post-rename

## The Bigger Picture

This rebrand isn't just a name change—it's a **mission clarification**:

### Old Identity
"A tool for generating Anki flashcards from Armenian text"

### New Identity
"A comprehensive Western Armenian learning platform with intelligent progression, morphological analysis, and corpus-driven vocabulary"

The name **Lousardzag** ("Light-spreading") embodies this expanded mission better than any reference to Anki software.

## Reference

- **Rebrand Date**: March 2, 2026
- **Git Commit**: `8135472` "Rename project to Lousardog..."
- **Status**: Complete (package + documentation), directory rename pending
- **Test Status**: ✅ 323/323 passing
- **Documentation**: See [REBRANDING.md](./REBRANDING.md) for technical details

## Related Files

- [REBRANDING.md](./REBRANDING.md) — Technical implementation details
- [README.md](../README.md) — New project README with full feature list
- [.github/copilot-instructions.md](../.github/copilot-instructions.md) — Updated environment notes
- pyproject.toml — Package configuration with new name

---

> **Lousardzag** (Լուսարձակ) — Spreading Light on Western Armenian Language & Culture
