# CHANGELOG

All notable changes to this project are documented here. This follows the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.

## [0.3.0] - 2026-03-02 (Lousardzag Rebrand)

### ✨ Changed (Major)

- **Project Renamed**: "Armenian Anki Note Generation Pipelines" → "**Lousardzag**" (Լուսարձակ)
  - New package name: `lousardzag` (formerly `armenian_anki`)
  - New CLI scripts: `lousardzag-*` (formerly `anki-*`)
  - Better reflects expanded scope as a comprehensive Western Armenian learning platform
  - Meaning: "Light-spreading" or "Dawn-bringer" in Western Armenian

### 📝 Documentation

- **New**: [REBRANDING.md](01-docs/REBRANDING.md) — Technical implementation details of rebrand
- **New**: [NAME-HISTORY.md](01-docs/NAME-HISTORY.md) — Decision process, name research, and historical context
- **New**: [SESSION-SUMMARY.md](01-docs/SESSION-SUMMARY.md) — Complete work log for March 2, 2026 session
- **Updated**: [README.md](README.md) — Comprehensive rewrite with new name and unified feature list
- **Updated**: [.github/copilot-instructions.md](.github/copilot-instructions.md) — Project name and references

### 🔄 Migration Guide

**For users with existing installations:**

```bash
# Update imports
from armenian_anki.morphology import ...   # OLD
from lousardzag.morphology import ...      # NEW

# Update CLI commands
anki-generate-cards ...      # OLD
lousardzag-generate-cards ... # NEW

anki-preview-server          # OLD
lousardzag-preview-server    # NEW
```

**For GitHub users:**

When the repository is renamed to `lousardzag`, update your clone:
```bash
git remote set-url origin https://github.com/yourusername/lousardzag.git
```

### 🎯 No Functionality Changes

- All 323 tests passing
- No breaking changes in library API
- Only package name, imports, and documentation affected
- Completely backward-compatible after import updates

---

## [0.2.0] - 2026-02-18 (Project Restructuring)

### ✨ Added

- **Directory Structure**: 8-part organization system (01-docs through 08-data)
  - `01-docs/` — Documentation and references
  - `02-src/` — Source packages (armenian_anki, wa_corpus)
  - `03-cli/` — Command-line interfaces
  - `04-tests/` — Test suite
  - `05-config/` — Configuration files
  - `06-notebooks/` — Jupyter notebooks
  - `07-tools/` — Utility scripts
  - `08-data/` — Data outputs

- **Build System**: Modern pyproject.toml with setuptools configuration
  - Package discovery
  - Dependency management
  - Tool configurations (pytest, black, isort, mypy)

- **Documentation**: PROJECT-RESTRUCTURING.md explaining new layout

### 🔧 Changed

- All path references updated across 7+ configuration files
- CLI scripts updated to use new directory structure
- Test configuration updated to reflect new locations

### ✅ Validated

- All tests passing (323 total) with new structure
- CLI scripts working correctly with new paths
- Complete git history preserved

---

## [0.1.0] - 2025-12-01 (Initial Release)

### ✨ Features

- **Morphological Analysis**
  - Noun declension (8 cases)
  - Verb conjugation (15 tenses)
  - Irregular verb handling
  - Schwa epenthesis detection
  - Syllable counting

- **Progression System**
  - Vocabulary batching (20 words/batch)
  - Level-based difficulty (20 levels)
  - Syllable constraints by level
  - Prerequisite tracking
  - Bootstrap vocabulary (36 core words)

- **Corpus Tools**
  - Newspaper scraper (Asbarez, Aztag, Nor Gyank)
  - Internet Archive scraper (PDF → text extraction)
  - Nayiri dictionary scraper (polite rate limiting)
  - Frequency analysis and tokenization

- **Flashcard Generation**
  - Context-aware sentence generation
  - Vocabulary dependency management
  - Ordered card progression
  - HTML preview generation
  - Multiple export formats

- **Anki Integration**
  - AnkiConnect API support
  - Read-only card import
  - Deck management
  - Profile support

- **Testing**
  - 323 comprehensive tests
  - Unit and integration test coverage
  - Pytest with conftest configuration

### 📚 Documentation

- README.md with usage instructions
- Inline code documentation
- corpus-sources.md documenting translation sources
- Configuration examples

---

## Documentation

- See individual `.md` files in `01-docs/` for detailed documentation
- Latest session work: [SESSION-SUMMARY.md](01-docs/SESSION-SUMMARY.md)
- Rebranding details: [REBRANDING.md](01-docs/REBRANDING.md)
- Name decision process: [NAME-HISTORY.md](01-docs/NAME-HISTORY.md)

---

## Support

For issues, questions, or contributions related to this project, see the documentation in `01-docs/`.

---

**Current Version**: 0.3.0 (Lousardzag Rebrand)  
**Last Updated**: March 2, 2026  
**Package Name**: `lousardzag`  
**Python**: 3.10+  
**License**: MIT
