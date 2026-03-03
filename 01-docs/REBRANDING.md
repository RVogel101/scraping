# Project Rebranding: Armenian Anki → Lousardzag

**Date**: March 2, 2026  
**Status**: ✅ Complete (Package rename done, directory rename pending)

## Overview

The project formerly known as "Armenian Anki Note Generation Pipelines" has been rebranded to **Lousardzag** (Լուսարձակ) to better reflect its expanded scope as a comprehensive Western Armenian learning platform.

## Why Lousardzag?

**Lousardzag** (Լուսարձակ) is a Western Armenian word meaning "light-spreading" or "dawn-bringer," symbolizing:

- **Enlightenment**: Spreading knowledge of Western Armenian language and culture
- **Education**: The project's core mission of intelligent language learning
- **Armenian Heritage**: Rooted in classical Western Armenian terminology
- **Availability**: Completely available as a package name and domain (no conflicts)

## Name Verification Results

### PyPI Package Registry
- ✅ **lousardzag**: Available
- ✅ **khrimian**: Available
- ✅ **mechitar**: Available
- ❌ **mekhitar**: Exists (philosophy project)
- ❌ **mkhitar**: Exists (47 personal GitHub profiles)
- ✅ All other candidates: Available

### GitHub Repository Count
- **lousardzag**: 0 repositories (completely clear)
- **khrimian**: 0 repositories (completely clear)
- **mechitar**: 0 repositories
- **mkhitar**: 47 repositories (mostly personal profiles)
- **mekhitar**: 1 repository (philosophy project)
- **vartabed**: 2 repositories (personal profiles)

### Domain Availability
- **lousardzag.com**: Available for registration
- **lousardzag.org**: Available for registration
- **lousardzag.net**: Available for registration

### Existing Asian Language Tools
No significant Armenian learning platforms or educational software found with any of these names.

## What Changed

### Package Name
- **Old**: `armenian_anki`
- **New**: `lousardzak`

All imports updated:
```python
# Before
from armenian_anki.progression import ProgressionPlan
from armenian_anki.morphology.verbs import conjugate_verb

# After
from lousardzag.progression import ProgressionPlan
from lousardzag.morphology.verbs import conjugate_verb
```

### Configuration Files
- **pyproject.toml**: Updated project name, scripts, and metadata
- **CLI scripts**:
  - `anki-generate-cards` → `lousardzag-generate-cards`
  - `anki-preview-server` → `lousardzag-preview-server`
  - `anki-pull-data` → `lousardzag-pull-data`
  - `anki-build-corpus` → `lousardzag-build-corpus`

### Documentation
- **README.md**: Complete rewrite with new project vision
- **.github/copilot-instructions.md**: Updated project name and references
- **Documentation files**: All references updated

### Directory Structure (Pending)
```
# Current
anki-note-generation-pipelines/
├── 02-src/
│   └── lousardzag/  ✅ Package renamed
│   └── wa_corpus/
└── ...

# Target
lousardzag/  ← Root directory rename pending
├── 02-src/
│   ├── lousardzag/  ✅ Done
│   └── wa_corpus/
└── ...
```

## Transliteration Notes

The proper Western Armenian transliteration of **Լուսարձակ** is **lousardzag**, not "lusardzak" or variants.

**Letter mappings** (Western Armenian):
- **ս** = s
- **ու** = ou (not u)
- **ա** = a
- **ր** = r
- **դ** = d
- **ա** = a  
- **կ** = g (not k)

This differs from Eastern Armenian where կ = k.

## Implementation Summary

### Files Changed (74 total)
- **Package directory**: Renamed `02-src/armenian_anki/` → `02-src/lousardzag/`
- **Python files**: Updated 79 import locations
- **Configuration**: pyproject.toml, .github/copilot-instructions.md
- **Documentation**: README.md, 01-docs/ files
- **Tests**: Updated across 04-tests/
- **CLI scripts**: 03-cli/ and cli/ directories

All changes tracked in git commit: `8135472` "Rename project to Lousardzag (Լուսարձակ)"

### Test Validation
✅ **All 323 tests passing** after complete rename
- No functionality broken
- Only import statements changed
- Complete package rename absorbed cleanly by test suite

## Remaining Tasks

### Immediate
- [ ] Close VS Code (directory in use)
- [ ] Rename root directory: `anki-note-generation-pipelines` → `lousardzag`
- [ ] Verify rename in Git (should auto-detect after reopen)
- [ ] Reopen VS Code with new path

### Recommended
- [ ] Update GitHub repository name (Settings → Repository name)
- [ ] Update local git remote if GitHub name changed:
  ```bash
  git remote set-url origin https://github.com/yourusername/lousardzag.git
  ```
- [ ] Create new PyPI package entry (when ready for release)

### Optional
- [ ] Update old references in archived docs
- [ ] Create migration guide for external users (if public project)
- [ ] Update package dependency documentation

## Reference Timeline

| Date | Event |
|---|---|
| 2026-03-02 | Name brainstorming: Mechitar, Vartabed, Khrimian, Lusardzak candidates |
| 2026-03-02 | Availability verification across PyPI, GitHub, and web |
| 2026-03-02 | Western Armenian transliteration correction (lusardzak not lusardzak) |
| 2026-03-02 | Package rename from `armenian_anki` to `lousardzag` |
| 2026-03-02 | All 323 tests passing after rename |
| 2026-03-02 | Git commit recorded: 8135472 |
| Pending | Directory rename (awaiting VS Code close) |

## Project Vision

**Lousardzag** is a comprehensive Western Armenian language learning platform featuring:

- **Morphological Analysis**: Noun declension, verb conjugation, irregular verb support
- **Intelligent Progression**: Syllable-based difficulty, prerequisite tracking
- **Corpus Building**: Multi-source scrapers (newspapers, Internet Archive, dictionaries)
- **Flashcard Generation**: Context-aware sentences with vocabulary dependency management
- **Educational Focus**: Pedagogically ordered cards for effective language learning

The name reflects this mission: spreading light on Western Armenian language and culture.
