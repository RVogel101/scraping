"""
Configuration for the Armenian Anki card generation pipeline.
"""

# ─── AnkiConnect Settings ─────────────────────────────────────────────
ANKI_CONNECT_URL = "http://localhost:8765"
ANKI_CONNECT_VERSION = 6

# ─── Deck Settings ────────────────────────────────────────────────────
# Source deck containing the vocabulary words to process
SOURCE_DECK = "Armenian Vocabulary"

# Target deck for generated morphology cards (declensions, conjugations, etc.)
TARGET_DECK = "Armenian Vocabulary::Morphology"

# ─── Note Type (Model) Names ─────────────────────────────────────────
NOUN_DECLENSION_MODEL = "Armenian Noun Declension"
VERB_CONJUGATION_MODEL = "Armenian Verb Conjugation"
VOCAB_SENTENCES_MODEL = "Armenian Vocab Sentences"

# ─── Field Names ──────────────────────────────────────────────────────
# Fields expected in the source vocabulary notes
SOURCE_FIELDS = {
    "word": "Word",           # The Armenian word
    "pos": "PartOfSpeech",    # noun, verb, adjective, etc.
    "translation": "Translation",  # English translation
    "pronunciation": "Pronunciation",  # Transliteration
}

# ─── Tags ─────────────────────────────────────────────────────────────
TAG_GENERATED = "auto-generated"
TAG_DECLENSION = "declension"
TAG_CONJUGATION = "conjugation"
TAG_SENTENCES = "sentences"

# ─── Morphology Settings ─────────────────────────────────────────────
# Default declension class for nouns when not specified
DEFAULT_NOUN_DECLENSION = "i_class"

# Default verb class when not specified
DEFAULT_VERB_CLASS = "e_class"

# Number of example sentences to generate per word
SENTENCES_PER_WORD = 5
# ─── Phrase-Chunking Progression Settings ───────────────────────────
# Number of vocabulary words per batch segment
PROGRESSION_VOCAB_BATCH_SIZE = 20

# Number of batches that make up one level (5 batches × 20 words = 100 words/level)
PROGRESSION_BATCHES_PER_LEVEL = 5

# Syllable ceiling per level band (words exceeding this are deferred to the next band)
# Format: {max_level_in_band: max_syllables_allowed}
PROGRESSION_SYLLABLE_BANDS = {
    5:  1,   # Levels  1–5:  1-syllable words only
    10: 2,   # Levels  6–10: up to 2 syllables
    15: 3,   # Levels 11–15: up to 3 syllables
}            # Levels 16+:   no restriction

# Maximum number of known vocab words per phrase, per level band
# Format: {max_level_in_band: max_vocab_words_allowed_in_phrase}
PROGRESSION_PHRASE_WORD_ALLOWANCE = {
    5:  1,   # Levels  1–5:  1 vocab word per phrase (simple structures only)
    10: 3,   # Levels  6–10: up to 3 vocab words per phrase
    15: 4,   # Levels 11–15: up to 4 vocab words per phrase
    20: 5,   # Levels 16–20: up to 5 vocab words per phrase
}            # Levels 21+:   up to 6 vocab words per phrase

# Target deck for progression-ordered cards
PROGRESSION_DECK = "Armenian Vocabulary::Progression"