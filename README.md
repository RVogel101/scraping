# Lousardzag (Լուսարձակ)

**Western Armenian Language Learning Platform**

Lousardzag ("Light-spreading" or "Dawn-bringer") is a comprehensive platform for Western Armenian language learning, featuring morphological analysis, vocabulary progression, and intelligent flashcard generation.

## Overview

Lousardzag combines computational linguistics with pedagogical progression to create an effective Western Armenian learning experience:

- **Morphological Analysis** — Advanced noun declension, verb conjugation, and irregular verb handling
- **Intelligent Progression** — Syllable-based difficulty progression with prerequisite tracking
- **Corpus Building** — Automated scraping from newspapers, Internet Archive, and dictionaries
- **Flashcard Generation** — Context-aware sentence generation with vocabulary dependency management

## Project Structure

```
lousardzag/
├── 01-docs/          Documentation and references
├── 02-src/           Source code
│   ├── lousardzag/   Core learning platform (morphology, progression, card generation)
│   └── wa_corpus/    Western Armenian corpus tools (scrapers, tokenization, frequency analysis)
├── 03-cli/           Command-line interfaces
├── 04-tests/         Test suite
├── 05-config/        Configuration files
├── 06-notebooks/     Jupyter notebooks for analysis
├── 07-tools/         Utility scripts
└── 08-data/          Data outputs (gitignored)
```

## Requirements

- **Python 3.10+**
- **Conda environment** (Python 3.12.3 recommended)
- **Anki desktop** with AnkiConnect add-on (for Anki integration)

### Installation

```bash
pip install -r requirements.txt
```

## Usage

### Generate Vocabulary Lists

**Generate N-standard proficiency vocabulary (N1-N7):**
```bash
python 07-tools/gen_vocab_simple.py --preset n-standard --max-words 140 --csv-output 08-data/vocab_n_standard.csv
```

**Generate custom vocabulary with proficiency blocks:**
```bash
python 07-tools/gen_vocab_simple.py --preset l1-core --max-words 60 --proficiency-enabled
```

Options:
- `--preset`: l1-core | l2-expand | l3-bridge | n-standard (default: n-standard)
- `--max-words`: Maximum vocabulary size
- `--csv-output`: Output CSV file path
- `--proficiency-enabled`: Enable N1-N7 block assignment

### Generate Flashcards

```bash
python 07-tools/generate_ordered_cards.py --max-words 40 --english-mode strict
```

Options:
- `--max-words`: Number of cards to generate
- `--english-mode`: strict | fallback | off (default: strict)
- `--level1-nonverb-max-syllables`: Syllable limit for Level 1 non-verbs (default: 1)
- `--level1-verb-max-syllables`: Syllable limit for Level 1 verbs (default: 2)

### Build Western Armenian Corpus

**Newspapers** (Asbarez, Aztag, Nor Gyank):
```bash
python -m wa_corpus.build_corpus --newspapers
```

**Internet Archive** (historical documents):
```bash
python -m wa_corpus.build_corpus --ia
```

**Nayiri Dictionary** (polite scraping):
```bash
python -m wa_corpus.nayiri_scraper --delay-min 3.0 --delay-max 6.0
```

### Development Server

```bash
python 03-cli/preview_server.py --pretty
```

Launches FastAPI server at http://127.0.0.1:8000 for flashcard preview with phonetic data.

## Key Features

### Western Armenian Phonetics
- **IPA Transcription**: 38 phonemes with proper Western Armenian voicing (reversed letter-shape convention)
- **Pronunciation Difficulty**: 1-5 scale for English speakers (guttural consonants highlighted)
- **Diphthong Support**: ու (oo), իւ (yoo) with contextual vowel handling
- **Integration**: Difficulty scores feed into vocabulary ordering
- **Reference**: See `.github/copilot-instructions.md` for critical voicing rules

### Vocabulary Ordering System
- **5 Ordering Modes**: frequency, pos_frequency, band_pos_frequency, difficulty, difficulty_band
- **3 Batch Strategies**: fixed size, growth (with step), banded by difficulty
- **4 Presets**: l1-core (60), l2-expand (80), l3-bridge (100), n-standard (flexible with N1-N7 levels)
- **Proficiency Blocks**: N1-N7 standards-style progression (like JLPT)
- **Filtering**: Automatic removal of phrases/sentences (>4 words, questions, sentence starters)
- **CSV + HTML Outputs**: Include IPA, English approximations, phonetic difficulty

### Sentence Progression Framework
- **Morphological Analysis**: Syllable count, verb conjugations, rare word tracking
- **Progression Strategies**: Linear and adaptive (based on vocabulary difficulty)
- **Prerequisite Tracking**: Ensures introduced vocabulary is already taught
- **Difficulty Filtering**: Prevents grammatically complex sentences early in progression
- **Comprehensive Tests**: Full test suite in `04-tests/test_sentence_progression.py`

### Morphological Analysis
- Noun declension (8 cases: nominative, accusative, genitive, dative, ablative, instrumental, locative)
- Verb conjugation (15 tenses, 6 persons, irregular verb support)
- Schwa epenthesis detection
- Syllable counting with epenthesis support

### Corpus Tools
- Multi-source newspaper scraping with deduplication
- Internet Archive catalog management and PDF text extraction
- Western Armenian tokenization and frequency analysis
- Corpus analysis utilities for vocabulary mapping and unmatched word reports

## Testing

```bash
python -m pytest
```

Run full test suite including vocabulary ordering, sentence progression, phonetics, and morphological analysis.

## Project Name

**Lousardzag** (Լուսարձակ) — Western Armenian transliteration of "light-spreading" or "dawn-bringer", reflecting the project's mission to illuminate and spread Western Armenian language knowledge.

## License

MIT

The CWAS "Word of the Day" images fall into these categories:

| Category | Description |
|---|---|
| Etymology | Word origin and history |
| Word Breakdown | Morphological analysis of a single word |
| Phrasal Breakdown | Analysis of a phrase or expression |
| Example | Usage example with Armenian sentence + English translation |
| Declension | Noun/adjective declension table (singular & plural) |
| Conjugation | Verb conjugation table |
| Conjunction | Conjunction usage patterns |

## Notes

- The scraper uses a temporary Chrome profile copy to avoid locking your main profile.
- Facebook login is handled via existing session cookies — no credentials are stored.
- OCR includes Armenian-specific corrections (e.g. fixing `ուdelays` → ` delays oundsv` misreads).
- Images are deduplicated by URL hash during scraping.
