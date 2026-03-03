"""
TRANSLATION SOURCES IN THE Lousardzag PIPELINE
==================================================

There are TWO sources for verb translations:

1. ANKI DECK (Primary Source)
   ────────────────────────────
   When processing vocabulary words from an Anki deck, translations come from:
   
   → Source Deck: "Armenian Vocabulary" (or custom deck via --source-deck)
   → Field Name: "Translation" (configurable via --field-translation)
   → How it works:
      - AnkiConnect reads notes from the source deck
      - card_generator.py::get_source_words() extracts the "Translation" field
      - Flow: Anki Deck → AnkiConnect → get_source_words() → card_generator.py
      - Example in generate_anki_cards.py line 330:
        translation = entry.get("translation", "")
      - Then passed to generate_verb_card() which passes it to conjugate_verb()

2. IRREGULAR VERB TABLE (Secondary Source - for specific overrides)
   ────────────────────────────────────────────────────────────────
   For built-in example/test code and irregular verb definitions:
   
   → File: lousardzag/morphology/irregular_verbs.py
   → Purpose: Hard-coded translations for the 19 most irregular Armenian verbs
   → When used: When conjugate_verb() encounters an irregular infinitive
   → How overrides work:
      - get_irregular_overrides(infinitive) returns a dict with "translation" key
      - If the infinitive is irregular, this translation can override user input
      - Most of our recent changes were HERE (to add "to" prefix)
   
   → Examples from irregular_verbs.py:
      INF_BE → "to be"
      INF_HAVE → "to have"
      INF_COME → "to come"
      ... (19 total)

3. MANUAL INPUT (For single-word generation)
   ──────────────────────────────────────────
   When running generate_anki_cards.py with command-line args:
   
   python generate_anki_cards.py --word կրել --pos verb --translation "to read"
        ↓
   translation argument → generate_vocab_card() → generate_verb_card()
   
   → See generate_anki_cards.py lines 550-575 for argument parser

FLOW DIAGRAM
============

For Progression Pipeline:
───────────────────────
   Anki Deck (Armenian Vocabulary)
        ↓ AnkiConnect.get_deck_notes()
    CardGenerator.get_source_words()
        ↓ Extract "Translation" field
    WordEntry.translation = "has", "is", "to read", etc.
        ↓
    generate_verb_card(word, translation, verb_class)
        ↓
    conjugate_verb(infinitive, verb_class, translation)
        ↓
    VerbConjugation(translation=translation)
        ↓
    Anki Card: Fields["Translation"] = translation

For Irregular Verbs (Test/Example Code):
─────────────────────────────────────────
   Test code calls:
   conjugate_verb('ունիլ', translation='to have')
        ↓
   conjugate_verb() extracts overrides via:
   get_irregular_overrides('ունիլ')
        ↓
   Irregular table returns:
   {"translation": "to have", "verb_class": "e_class", ...}
        ↓
   conjugate_verb() merges: translation = "to have"
        ↓
   VerbConjugation(translation="to have")

KEY INSIGHTS
============

1. The primary source is YOUR ANKI DECK
   - You must populate the "Translation" field in your source notes
   - The code reads translations FROM YOUR DECK, then generates forms FROM THOSE

2. The irregular_verbs.py table provides:
   - Hard-coded paradigms for conjugation (present, past, etc.)
   - Hard-coded translations for reference/testing
   - These can serve as fallbacks or overrides

3. RECENT CHANGES
   - Updated irregular_verbs.py to use "to" prefix ("to have" not "have")
   - This affects BOTH test code AND reference implementations
   - Does NOT change how translations flow from your Anki deck

4. FOR YOUR CARDS IN ANKI
   - Cards will show whatever translation YOU put in the source deck
   - Our changes to irregular_verbs.py mainly affect internal consistency
     and the default translations when creating example cards

CONFIGURATION
==============

Default configuration in lousardzag/config.py:
   SOURCE_DECK = "Armenian Vocabulary"
   SOURCE_FIELDS = {
       "word": "Word",
       "pos": "PartOfSpeech",
       "translation": "Translation",  ← This field is read
       "pronunciation": "Pronunciation"
   }

Override field detection from command line:
   python generate_anki_cards.py --field-translation "English Meaning"
"""

if __name__ == "__main__":
    print(__doc__)
