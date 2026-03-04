"""
Anki card generation pipeline.

Reads vocabulary from an existing Anki deck, generates morphological forms
(declensions, conjugations, articles, sentences), and creates new Anki cards
via AnkiConnect.
"""

import logging
import re
from typing import Optional

from .anki_connect import AnkiConnect, AnkiConnectError
from .config import (
    SOURCE_DECK, TARGET_DECK, LETTER_CARDS_DECK, VISUAL_LETTER_CARDS_DECK,
    NOUN_DECLENSION_MODEL, VERB_CONJUGATION_MODEL, VOCAB_SENTENCES_MODEL, LETTER_CARDS_MODEL, VISUAL_LETTER_CARDS_MODEL,
    SOURCE_FIELDS, TAG_GENERATED, TAG_DECLENSION, TAG_CONJUGATION, TAG_SENTENCES, TAG_LETTER, TAG_VISUAL_LETTER,
    DEFAULT_NOUN_DECLENSION, DEFAULT_VERB_CLASS, SENTENCES_PER_WORD,
)
from .database import CardDatabase
from . import letter_data
from .morphology.nouns import decline_noun, NounDeclension, CASE_LABELS_EN
from .morphology.verbs import conjugate_verb, VerbConjugation, PERSONS, PERSON_LABELS
from .morphology.articles import add_definite, add_indefinite
from .morphology.detect import detect_verb_class, detect_noun_class, detect_pos_and_class
from .renderer import load_card_model_assets, build_loanword_metadata
from .sentence_generator import generate_noun_sentences, generate_verb_sentences, extract_vocabulary
from .sentence_progression import (
    SentenceProgressionConfig, select_sentences_for_progression
)

logger = logging.getLogger(__name__)


# ─── Model Field Lists ───────────────────────────────────────────────

NOUN_FIELDS = [
    "Word", "Translation", "DeclensionClass",
    "LoanwordOrigin", "LoanwordOriginLabel", "LoanwordBadgeClass",
    "NomSg", "NomSgDef", "NomSgIndef",
    "AccSg", "AccSgDef",
    "GenDatSg", "GenDatSgDef",
    "AblSg", "AblSgDef",
    "InstrSg", "InstrSgDef",
    "NomPl", "NomPlDef",
    "AccPl", "AccPlDef",
    "GenDatPl", "GenDatPlDef",
    "AblPl", "AblPlDef",
    "InstrPl", "InstrPlDef",
]

VERB_FIELDS = [
    "Infinitive", "Translation", "VerbClass", "Root",
    "LoanwordOrigin", "LoanwordOriginLabel", "LoanwordBadgeClass",
    "Pres1sg", "Pres2sg", "Pres3sg", "Pres1pl", "Pres2pl", "Pres3pl",
    "Past1sg", "Past2sg", "Past3sg", "Past1pl", "Past2pl", "Past3pl",
    "Fut1sg", "Fut2sg", "Fut3sg", "Fut1pl", "Fut2pl", "Fut3pl",
    "Imp1sg", "Imp2sg", "Imp3sg", "Imp1pl", "Imp2pl", "Imp3pl",
    "ImperSg", "ImperPl", "PastPart", "PresPart",
]

SENTENCE_FIELDS = [
    "Word", "Translation", "FormLabel", "ArmenianSentence", "EnglishSentence",
    "LoanwordOrigin", "LoanwordOriginLabel", "LoanwordBadgeClass",
]

LETTER_FIELDS = [
    "Letter", "LetterUppercase", "LetterName", "Position",
    "LetterType", "IPA", "EnglishSound", "PronunciationTip",
    "Difficulty", "ExampleWords", "WesternNote", "DiphthongInfo",
    "Audio",
]

VISUAL_LETTER_FIELDS = [
    "Letter", "LetterUppercase", "LetterName", "Position",
    "LetterType", "ShapeDescription", "KeyFeatures",
    "StrokeSequence", "WritingTips", "CommonMistakes",
    "ShapeVariants", "SimilarLetters", "Distinction",
    "IPA", "EnglishSound", "PronunciationTip",
]


# ─── Card Generator ──────────────────────────────────────────────────

class CardGenerator:
    """Orchestrates reading vocab from Anki and generating morphology cards.

    A ``CardDatabase`` is created automatically (or can be injected) so that
    every generated card and sentence is persisted locally in SQLite
    independent of the AnkiConnect push.  This local store is the foundation
    for the future stand-alone app with FSRS spaced-repetition and A/B testing.
    """

    def __init__(
        self,
        anki: Optional[AnkiConnect] = None,
        db: Optional[CardDatabase] = None,
        db_path: Optional[str] = None,
    ):
        self.anki = anki or AnkiConnect()
        from .database import DEFAULT_DB_PATH
        self.db: CardDatabase = db or CardDatabase(db_path if db_path else DEFAULT_DB_PATH)
        self.assets = load_card_model_assets()

    def setup_models(self) -> None:
        """Create the Anki note types (models) if they don't exist."""
        logger.info("Setting up Anki note types...")
        self.anki.create_model(
            name=NOUN_DECLENSION_MODEL,
            fields=NOUN_FIELDS,
            card_templates=self.assets.noun_templates,
            css=self.assets.css,
        )

        self.anki.create_model(
            name=VERB_CONJUGATION_MODEL,
            fields=VERB_FIELDS,
            card_templates=self.assets.verb_templates,
            css=self.assets.css,
        )

        self.anki.create_model(
            name=VOCAB_SENTENCES_MODEL,
            fields=SENTENCE_FIELDS,
            card_templates=self.assets.sentence_templates,
            css=self.assets.css,
        )

        self.anki.create_model(
            name=LETTER_CARDS_MODEL,
            fields=LETTER_FIELDS,
            card_templates=self.assets.letter_templates,
            css=self.assets.css,
        )

        self.anki.create_model(
            name=VISUAL_LETTER_CARDS_MODEL,
            fields=VISUAL_LETTER_FIELDS,
            card_templates=self.assets.visual_letter_templates,
            css=self.assets.css,
        )

        logger.info("Note types ready")

    def setup_decks(self) -> None:
        """Create target decks if they don't exist."""
        self.anki.ensure_deck(TARGET_DECK)
        self.anki.ensure_deck(LETTER_CARDS_DECK)
        logger.info(f"Target decks ready: {TARGET_DECK}, {LETTER_CARDS_DECK}")

    # ─── HTML Field Extraction Helpers ───────────────────────────────
    # Deck format: Front/Back fields contain HTML like:
    #   Front: <div style='font-family:"Arial"...'>WORD</div>
    #          <div class='toggle-section'><div class='toggle-content'>syl-guide</div>...
    #   Back:  same as Front + <hr> + <div>English</div> + <div><img></div>

    @staticmethod
    def _clean_html_text(html: str) -> str:
        s = re.sub(r'\[sound:[^\]]+\]', '', html, flags=re.IGNORECASE)
        s = re.sub(r'<[^>]+>', ' ', s)
        s = s.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&quot;', '"')
        return re.sub(r'\s+', ' ', s).strip()

    @staticmethod
    def _extract_word_from_front(html: str) -> str:
        """Pull the Armenian word out of the first font-family <div>.

        Strips coloured <span> tags (vowel / stress highlighting).
        For comma-separated alternates returns only the first term.
        Phrase cards (result contains a space) are returned as-is so
        the caller can skip them.
        """
        m = re.search(
            r'<div[^>]*font-family[^>]*>\s*(.*?)\s*</div>',
            html, re.IGNORECASE | re.DOTALL,
        )
        raw = m.group(1) if m else html
        text = re.sub(r'<[^>]+>', '', raw)
        text = re.sub(r'\[sound:[^\]]+\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+', ' ', text).strip()
        if ',' in text:
            text = text.split(',')[0].strip()
        return text

    @staticmethod
    def _extract_word_text_from_front(html: str) -> str:
        """Extract the raw Armenian word field text from Front HTML.

        Unlike ``_extract_word_from_front``, this keeps comma-separated values
        so callers can split one note into multiple vocabulary rows.
        """
        m = re.search(
            r'<div[^>]*font-family[^>]*>\s*(.*?)\s*</div>',
            html, re.IGNORECASE | re.DOTALL,
        )
        raw = m.group(1) if m else html
        text = re.sub(r'<[^>]+>', '', raw)
        text = re.sub(r'\[sound:[^\]]+\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    @staticmethod
    def _split_multi_values(text: str) -> list[str]:
        """Split a many-to-many field into ordered, deduplicated values."""
        if not text:
            return []
        parts = re.split(r'\s*(?:,|;|/|\u0589|\u055d|\n|\|)\s*', text)
        cleaned: list[str] = []
        seen: set[str] = set()
        for part in parts:
            value = re.sub(r'\s+', ' ', part).strip()
            if not value:
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(value)
        return cleaned

    @classmethod
    def _split_armenian_words(cls, html: str) -> list[str]:
        """Return one or more Armenian word candidates from the Front field."""
        return cls._split_multi_values(cls._extract_word_text_from_front(html))

    @classmethod
    def _split_translations(cls, html: str) -> list[str]:
        """Return one or more translation candidates from the translation field."""
        translation = cls._extract_translation_from_back(html)
        if not translation:
            translation = cls._clean_html_text(html)
        return cls._split_multi_values(translation)

    @staticmethod
    def _extract_translation_from_back(html: str) -> str:
        """Extract the English translation from a Back field.

        Translation is the first non-empty, non-image div after <hr>.
        """
        parts = re.split(r'<[hH][rR]\s*/?>', html)
        if len(parts) < 2:
            return ''
        after_hr = parts[-1]
        for m in re.finditer(r'<div[^>]*>(.*?)</div>', after_hr, re.IGNORECASE | re.DOTALL):
            inner = m.group(1).strip()
            if not inner:
                continue
            if re.fullmatch(r'\s*<[iI][mM][gG][^>]*>\s*', inner):
                continue
            text = re.sub(r'<[^>]+>', '', inner)
            text = re.sub(r'\[sound:[^\]]+\]', '', text, flags=re.IGNORECASE)
            text = re.sub(r'\s+', ' ', text).strip()
            if text:
                return text
        return ''

    @staticmethod
    def _detect_pos(word: str) -> str:
        """Heuristically detect POS from an Armenian word's suffix.

        Uses the detect module for accurate verb-class-aware detection.
        """
        pos, _ = detect_pos_and_class(word)
        return pos

    @staticmethod
    def _extract_syllable_count(html: str) -> int:
        """Extract syllable count from the Syllable Guide toggle-content div.

        The guide uses hyphens between syllables with vowels coloured green:
          'Պ<span>a</span>t-k<span>e</span>r' => 2 syllables
        Returns 0 when the guide is absent (fall back to count_syllables).
        """
        m = re.search(
            r'class=["\']toggle-content["\'][^>]*>(.*?)</div>',
            html, re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return 0
        text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not text:
            return 0
        parts = [p for p in text.split('-') if p.strip()]
        return len(parts)

    # Common alternative field names to try when configured names are absent.
    _WORD_FIELD_ALIASES = [
        "Word", "Armenian", "Front", "Expression", "Vocabulary",
        "Հայerén", "Term", "Item", "Headword",
    ]
    _TRANSLATION_FIELD_ALIASES = [
        "Translation", "Meaning", "English", "Back", "Definition",
        "Gloss", "Answer", "Target",
    ]
    _POS_FIELD_ALIASES = [
        "PartOfSpeech", "POS", "Part of Speech", "Type", "WordClass",
        "WordType", "Category", "Class",
    ]

    def _resolve_fields(
        self,
        available: list[str],
        overrides: dict,
    ) -> dict[str, str | None]:
        """Map logical key → actual field name, using override → config → alias fallback."""
        def pick(logical_key: str, aliases: list[str]) -> str | None:
            # 1) Explicit override wins
            if logical_key in overrides and overrides[logical_key] in available:
                return overrides[logical_key]
            # 2) Configured name (case-insensitive)
            configured = SOURCE_FIELDS.get(logical_key, "")
            for f in available:
                if f.lower() == configured.lower():
                    return f
            # 3) Walk through known aliases
            for alias in aliases:
                for f in available:
                    if f.lower() == alias.lower():
                        return f
            return None

        return {
            "word":          pick("word",          self._WORD_FIELD_ALIASES),
            "translation":   pick("translation",   self._TRANSLATION_FIELD_ALIASES),
            "pos":           pick("pos",           self._POS_FIELD_ALIASES),
            "pronunciation": pick("pronunciation", ["Pronunciation", "Romanization",
                                                    "Transliteration", "Reading"]),
        }

    def get_source_words(
        self,
        deck: Optional[str] = None,
        field_overrides: Optional[dict] = None,
        default_pos: str = "noun",
        use_cache: bool = True,
        allow_anki_fallback: bool = True,
    ) -> list[dict]:
        """Read vocabulary words from the source Anki deck.

        If ``use_cache`` is True and the vocabulary cache is populated for
        this deck, returns cached entries. Otherwise falls back to fetching
        from AnkiConnect unless ``allow_anki_fallback`` is False.

        Auto-detects field names when the configured names are not found.
        Pass ``field_overrides`` to force specific field names:
            {"word": "Front", "translation": "Back", "pos": "POS"}

        Returns list of dicts with keys: word, pos, translation, pronunciation.
        """
        deck = deck or SOURCE_DECK
        
        # Try to use cache first if enabled
        if use_cache and self.db.has_vocabulary_cache(deck):
            logger.info(f"Loading vocabulary from cache for deck '{deck}'")
            cached = self.db.get_vocabulary_from_cache(deck)
            if cached:
                # Convert cache format to CardGenerator format
                vocab = []
                for entry in cached:
                    vocab.append({
                        "word": entry["lemma"],
                        "translation": entry.get("translation", ""),
                        "pos": entry.get("pos", default_pos),
                        "pronunciation": entry.get("pronunciation", ""),
                        "syllable_count": entry.get("syllable_count", 0),
                        "declension_class": entry.get("declension_class", ""),
                        "verb_class": entry.get("verb_class", ""),
                    })
                logger.info(f"Loaded {len(vocab)} words from vocabulary cache")
                return vocab
        
        if not allow_anki_fallback:
            logger.warning(
                f"No cache found for '{deck}' and Anki fallback is disabled. "
                "Run vocabulary sync first or disable local-only mode."
            )
            return []

        # Fall back to AnkiConnect
        logger.info(f"Loading vocabulary from Anki deck '{deck}' (cache miss or disabled)")
        notes = self.anki.get_deck_notes(deck)
        if not notes:
            logger.warning(f"No notes found in deck '{deck}'")
            return []

        # Determine the field names from the first note
        sample_fields = list(notes[0].get("fields", {}).keys())
        mapping = self._resolve_fields(sample_fields, field_overrides or {})

        # Warn about what we resolved
        logger.info(
            f"Field mapping for '{deck}': "
            f"word='{mapping['word']}', translation='{mapping['translation']}', "
            f"pos='{mapping['pos']}'"
        )
        if mapping["word"] is None:
            logger.warning(
                f"Could not detect word field in deck '{deck}'. "
                f"Available fields: {sample_fields}. "
                "Use --field-word to specify it explicitly."
            )
            return []
        if mapping["translation"] is None:
            logger.warning(
                f"Could not detect translation field in deck '{deck}'. "
                f"Available fields: {sample_fields}. "
                "Use --field-translation to specify it explicitly."
            )

        words = []
        skipped_phrases = 0
        for note in notes:
            raw = {k: v["value"] for k, v in note.get("fields", {}).items()}

            # Split many-to-many values so each output row maps to one Armenian word.
            word_html = raw.get(mapping["word"] or "", "")
            split_words = self._split_armenian_words(word_html)
            if not split_words:
                continue

            # Translation can also contain multiple values.
            trans_html = raw.get(mapping["translation"] or "", "")
            split_translations = self._split_translations(trans_html)
            full_translation = ", ".join(split_translations) if split_translations else ""

            # POS: field value if present, else auto-detect per word.
            if mapping["pos"]:
                pos_hint = self._clean_html_text(raw.get(mapping["pos"] or "", "")).lower()
            else:
                pos_hint = ""

            pronunciation = self._clean_html_text(
                raw.get(mapping["pronunciation"] or "", "")
            )

            # Syllable count from Syllable Guide is more reliable than the
            # pure-algorithmic counter for words in this deck
            syllable_count = self._extract_syllable_count(word_html)

            # If translation count matches, pair by index; otherwise preserve
            # the full translation text for each Armenian word to avoid bad pairing.
            if len(split_translations) == len(split_words) and len(split_words) > 1:
                paired_translations = split_translations
            elif len(split_translations) == 1:
                paired_translations = split_translations * len(split_words)
            else:
                paired_translations = [full_translation] * len(split_words)

            for idx, word in enumerate(split_words):
                # Phrase cards contain spaces after cleaning (e.g. 'mi vaze'); skip them
                if ' ' in word:
                    skipped_phrases += 1
                    logger.debug(f"Skipping phrase card: {word!r}")
                    continue

                pos = pos_hint or self._detect_pos(word)
                words.append({
                    "word":           word,
                    "translation":    paired_translations[idx] if idx < len(paired_translations) else full_translation,
                    "pos":            pos or default_pos,
                    "pronunciation":  pronunciation,
                    "syllable_count": syllable_count,
                })

        if skipped_phrases:
            logger.info(f"Skipped {skipped_phrases} phrase/imperative cards")
        logger.info(f"Found {len(words)} vocabulary words in '{deck}'")
        return words

    def generate_noun_card(self, word: str, translation: str = "",
                           declension_class: Optional[str] = None,
                           extra_tags: Optional[list] = None,
                           deck: Optional[str] = None,
                           push_to_anki: bool = True) -> Optional[int]:
        """Generate a noun declension card and persist morphology locally."""
        cls = declension_class or detect_noun_class(word)
        decl = decline_noun(word, cls, translation)
        loanword_meta = build_loanword_metadata(word, translation)

        fields = {
            "Word": decl.word,
            "Translation": decl.translation,
            "DeclensionClass": cls,
            "LoanwordOrigin": loanword_meta["loanword_origin"],
            "LoanwordOriginLabel": loanword_meta["loanword_origin_label"],
            "LoanwordBadgeClass": loanword_meta["loanword_badge_class"],
            "NomSg": decl.nom_sg,
            "NomSgDef": decl.nom_sg_def,
            "NomSgIndef": decl.nom_sg_indef,
            "AccSg": decl.acc_sg,
            "AccSgDef": decl.acc_sg_def,
            "GenDatSg": decl.gen_dat_sg,
            "GenDatSgDef": decl.gen_dat_sg_def,
            "AblSg": decl.abl_sg,
            "AblSgDef": decl.abl_sg_def,
            "InstrSg": decl.instr_sg,
            "InstrSgDef": decl.instr_sg_def,
            "NomPl": decl.nom_pl,
            "NomPlDef": decl.nom_pl_def,
            "AccPl": decl.acc_pl,
            "AccPlDef": decl.acc_pl_def,
            "GenDatPl": decl.gen_dat_pl,
            "GenDatPlDef": decl.gen_dat_pl_def,
            "AblPl": decl.abl_pl,
            "AblPlDef": decl.abl_pl_def,
            "InstrPl": decl.instr_pl,
            "InstrPlDef": decl.instr_pl_def,
        }

        note_id = None
        if push_to_anki:
            tags = [TAG_GENERATED, TAG_DECLENSION] + (extra_tags or [])
            note_id = self.anki.add_note(
                deck=deck or TARGET_DECK,
                model=NOUN_DECLENSION_MODEL,
                fields=fields,
                tags=tags,
            )
            if note_id:
                logger.info(f"Created noun declension card: {word} (ID: {note_id})")

        # ── Persist to local SQLite ──────────────────────────────────
        morphology_data = {
            k: v for k, v in fields.items()
            if k not in (
                "Word", "Translation", "DeclensionClass",
                "LoanwordOrigin", "LoanwordOriginLabel", "LoanwordBadgeClass",
            )
        }
        card_id = self.db.upsert_card(
            word=word,
            translation=translation,
            pos="noun",
            card_type="noun_declension",
            declension_class=cls,
            template_version=self.assets.template_version,
            metadata=loanword_meta,
            morphology=morphology_data,
            anki_note_id=note_id,
        )

        return note_id if push_to_anki else card_id
    def generate_verb_card(self, infinitive: str, translation: str = "",
                           verb_class: Optional[str] = None,
                           extra_tags: Optional[list] = None,
                           deck: Optional[str] = None,
                           push_to_anki: bool = True) -> Optional[int]:
        """Generate a verb conjugation card and persist morphology locally."""
        cls = verb_class or detect_verb_class(infinitive)
        conj = conjugate_verb(infinitive, cls, translation)
        loanword_meta = build_loanword_metadata(infinitive, translation)

        fields = {
            "Infinitive": conj.infinitive,
            "Translation": conj.translation,
            "VerbClass": cls,
            "Root": conj.root,
            "LoanwordOrigin": loanword_meta["loanword_origin"],
            "LoanwordOriginLabel": loanword_meta["loanword_origin_label"],
            "LoanwordBadgeClass": loanword_meta["loanword_badge_class"],
        }

        # Present tense
        for person in PERSONS:
            key = f"Pres{person}"
            fields[key] = conj.present.get(person, "")

        # Past aorist
        for person in PERSONS:
            key = f"Past{person}"
            fields[key] = conj.past_aorist.get(person, "")

        # Future
        for person in PERSONS:
            key = f"Fut{person}"
            fields[key] = conj.future.get(person, "")

        # Imperfect
        for person in PERSONS:
            key = f"Imp{person}"
            fields[key] = conj.imperfect.get(person, "")

        # Imperative & participles
        fields["ImperSg"] = conj.imperative_sg
        fields["ImperPl"] = conj.imperative_pl
        fields["PastPart"] = conj.past_participle
        fields["PresPart"] = conj.present_participle

        note_id = None
        if push_to_anki:
            tags = [TAG_GENERATED, TAG_CONJUGATION] + (extra_tags or [])
            note_id = self.anki.add_note(
                deck=deck or TARGET_DECK,
                model=VERB_CONJUGATION_MODEL,
                fields=fields,
                tags=tags,
            )
            if note_id:
                logger.info(f"Created verb conjugation card: {infinitive} (ID: {note_id})")

        # ── Persist to local SQLite ──────────────────────────────────
        morphology_data = {
            k: v for k, v in fields.items()
            if k not in (
                "Infinitive", "Translation", "VerbClass", "Root",
                "LoanwordOrigin", "LoanwordOriginLabel", "LoanwordBadgeClass",
            )
        }
        card_id = self.db.upsert_card(
            word=infinitive,
            translation=translation,
            pos="verb",
            card_type="verb_conjugation",
            verb_class=cls,
            template_version=self.assets.template_version,
            metadata=loanword_meta,
            morphology=morphology_data,
            anki_note_id=note_id,
        )

        return note_id if push_to_anki else card_id
    def generate_sentence_cards(
        self,
        word: str,
        pos: str,
        translation: str = "",
        declension_class: Optional[str] = None,
        verb_class: Optional[str] = None,
        grammar_filter: Optional[str] = None,
        max_sentences: Optional[int] = None,
        extra_tags: Optional[list] = None,
        deck: Optional[str] = None,
        push_to_anki: bool = True,
        supporting_words: Optional[list[str]] = None,
        pronoun_style: str = "explicit",
        level: Optional[int] = None,
        progression_config: Optional[SentenceProgressionConfig] = None,
    ) -> list[int]:
        """Generate sentence practice cards for a vocabulary word.

        Args:
            grammar_filter: If set, only generate sentences whose form_label
                            starts with or matches this grammar type string.
                            Used by the progression pipeline to target one
                            grammar structure per phrase slot.
            max_sentences:  Cap on how many sentence cards to create.
                            Defaults to SENTENCES_PER_WORD.
            supporting_words: Optional list of previously-learned vocabulary words
                             to incorporate into sentence structures.
            pronoun_style: "explicit" (default), "optional" (parentheses), or "none".
            level: Optional level (1-20) for sentence progression control.
            progression_config: Optional SentenceProgressionConfig to control
                               which sentence tiers are available at this level.
                               If provided, sentences will be selected progressively
                               even if grammar_filter is not set.
        """
        note_ids = []
        limit = max_sentences if max_sentences is not None else SENTENCES_PER_WORD
        supporting_words = supporting_words or []

        if pos.lower() in ("noun", "n"):
            sentences = generate_noun_sentences(
                word, declension_class or DEFAULT_NOUN_DECLENSION,
                translation, limit * 3 if grammar_filter else limit,
                pronoun_style=pronoun_style,
            )
        elif pos.lower() in ("verb", "v"):
            sentences = generate_verb_sentences(
                word, verb_class or DEFAULT_VERB_CLASS,
                translation, limit * 3 if grammar_filter else limit,
                pronoun_style=pronoun_style,
                supporting_words=supporting_words,
            )
        else:
            logger.debug(f"Skipping sentence generation for POS '{pos}': {word}")
            return note_ids

        # Apply sentence progression if configured
        if progression_config and level is not None:
            sentences = select_sentences_for_progression(
                sentences, level, progression_config
            )
            limit = min(limit, len(sentences))

        # Apply grammar filter: keep sentences whose label contains the filter key
        if grammar_filter:
            filter_key = grammar_filter.replace("_", " ").lower()
            sentences = [
                (lbl, arm, en) for lbl, arm, en in sentences
                if filter_key in lbl.lower()
            ]
            # Fall back to first available sentence if nothing matches the filter
            if not sentences:
                if pos.lower() in ("noun", "n"):
                    sentences = generate_noun_sentences(
                        word, declension_class or DEFAULT_NOUN_DECLENSION,
                        translation, 1,
                    )
                else:
                    sentences = generate_verb_sentences(
                        word, verb_class or DEFAULT_VERB_CLASS,
                        translation, 1,
                    )

        sentences = sentences[:limit]
        tags = [TAG_GENERATED, TAG_SENTENCES] + (extra_tags or [])
        loanword_meta = build_loanword_metadata(word, translation)

        for form_label, arm_sentence, en_sentence in sentences:
            if push_to_anki:
                fields = {
                    "Word": word,
                    "Translation": translation,
                    "FormLabel": form_label,
                    "ArmenianSentence": arm_sentence,
                    "EnglishSentence": en_sentence,
                    "LoanwordOrigin": loanword_meta["loanword_origin"],
                    "LoanwordOriginLabel": loanword_meta["loanword_origin_label"],
                    "LoanwordBadgeClass": loanword_meta["loanword_badge_class"],
                }
                note_id = self.anki.add_note(
                    deck=deck or TARGET_DECK,
                    model=VOCAB_SENTENCES_MODEL,
                    fields=fields,
                    tags=tags,
                )
                if note_id:
                    note_ids.append(note_id)

            # ── Persist sentence to local SQLite ──────────────────────
            card_type = "noun_declension" if pos.lower() in ("noun", "n") else "verb_conjugation"
            db_card = self.db.get_card_by_word(word, card_type)
            if db_card is None:
                # Ensure a parent card row exists even if Anki push is skipped.
                db_card_id = self.db.upsert_card(
                    word=word,
                    translation=translation,
                    pos=pos,
                    card_type=card_type,
                    template_version=self.assets.template_version,
                    metadata=loanword_meta,
                )
            else:
                db_card_id = db_card["id"]
            
            # Extract vocabulary from the sentence for prerequisite tracking
            vocabulary_used = extract_vocabulary(arm_sentence)
            
            sentence_id = self.db.add_sentence(
                card_id=db_card_id,
                form_label=form_label,
                armenian_text=arm_sentence,
                english_text=en_sentence,
                grammar_type=grammar_filter or "",
                vocabulary_used=vocabulary_used,
            )
            if not push_to_anki:
                note_ids.append(sentence_id)

        logger.info(f"Created {len(note_ids)} sentence cards for: {word}")
        return note_ids

    def generate_letter_card(
        self,
        letter: str,
        deck: Optional[str] = None,
        push_to_anki: bool = True,
        extra_tags: Optional[list[str]] = None,
    ) -> Optional[int]:
        """Generate a flashcard for a single Armenian letter.

        Args:
            letter: Single Armenian letter (lowercase)
            deck: Target deck (defaults to LETTER_CARDS_DECK)
            push_to_anki: Whether to push to Anki via AnkiConnect
            extra_tags: Additional tags to apply

        Returns:
            Note ID if created, None if skipped
        """
        letter_info = letter_data.get_letter_info(letter)
        if not letter_info:
            logger.warning(f"No letter data found for: {letter}")
            return None

        # Format example words as newline-separated list
        example_words_formatted = "<br>".join(letter_info.get("example_words", []))

        # Check if this letter forms diphthongs
        diphthong_info = ""
        for diph, diph_data in letter_data.ARMENIAN_DIPHTHONGS.items():
            if letter in diph_data.get("letters", []):
                diphthong_info = f"{diph} ({diph_data['ipa']}) = {diph_data['english']} — {diph_data['note']}"
                break

        fields = {
            "Letter": letter_info["lowercase"],
            "LetterUppercase": letter_info["uppercase"],
            "LetterName": letter_info["name"],
            "Position": str(letter_info["position"]),
            "LetterType": letter_info["type"],
            "IPA": letter_info["ipa"],
            "EnglishSound": letter_info["english"],
            "PronunciationTip": letter_info.get("pronunciation_tip", ""),
            "Difficulty": str(letter_info["difficulty"]),
            "ExampleWords": example_words_formatted,
            "WesternNote": letter_info.get("western_note", ""),
            "DiphthongInfo": diphthong_info,
            "Audio": "",  # Placeholder for audio file path (future feature)
        }

        tags = [TAG_GENERATED, TAG_LETTER] + (extra_tags or [])

        # Add difficulty-specific tags
        if letter_info["difficulty"] >= 3:
            tags.append("difficult-pronunciation")
        if letter_info["type"] == "vowel":
            tags.append("vowel")
        elif letter_info["type"] == "consonant":
            tags.append("consonant")

        note_id = None
        if push_to_anki:
            note_id = self.anki.add_note(
                deck=deck or LETTER_CARDS_DECK,
                model=LETTER_CARDS_MODEL,
                fields=fields,
                tags=tags,
            )

        # Persist to local database
        db_card_id = self.db.upsert_card(
            word=letter,
            translation=f"{letter_info['name']} ({letter_info['english']})",
            pos="letter",
            card_type="letter",
            template_version=self.assets.template_version,
            metadata={
                "letter_name": letter_info["name"],
                "position": letter_info["position"],
                "letter_type": letter_info["type"],
                "ipa": letter_info["ipa"],
                "difficulty": letter_info["difficulty"],
            },
        )

        if not push_to_anki:
            note_id = db_card_id

        logger.info(f"Created letter card for: {letter} ({letter_info['name']})")
        return note_id

    def generate_all_letter_cards(
        self,
        deck: Optional[str] = None,
        push_to_anki: bool = True,
        difficulty_filter: Optional[int] = None,
    ) -> list[int]:
        """Generate flashcards for all Armenian letters.

        Args:
            deck: Target deck (defaults to LETTER_CARDS_DECK)
            push_to_anki: Whether to push to Anki via AnkiConnect
            difficulty_filter: If set, only generate cards for letters with
                             difficulty >= this value (1-5)

        Returns:
            List of created note IDs
        """
        note_ids = []
        all_letters = letter_data.get_all_letters_ordered()

        for letter in all_letters:
            letter_info = letter_data.get_letter_info(letter)
            if letter_info:
                # Apply difficulty filter if specified
                if difficulty_filter and letter_info["difficulty"] < difficulty_filter:
                    continue

                note_id = self.generate_letter_card(
                    letter=letter,
                    deck=deck,
                    push_to_anki=push_to_anki,
                )
                if note_id:
                    note_ids.append(note_id)

        logger.info(f"Created {len(note_ids)} letter cards (total letters: {len(all_letters)})")
        return note_ids

    def generate_visual_letter_card(
        self,
        letter: str,
        deck: Optional[str] = None,
        push_to_anki: bool = True,
        extra_tags: Optional[list[str]] = None,
    ) -> Optional[int]:
        """Generate a visual/handwriting training card for a single Armenian letter.

        Args:
            letter: Single Armenian letter (lowercase)
            deck: Target deck (defaults to VISUAL_LETTER_CARDS_DECK)
            push_to_anki: Whether to push to Anki via AnkiConnect
            extra_tags: Additional tags to apply

        Returns:
            Note ID if created, None if skipped
        """
        letter_info = letter_data.get_letter_info(letter)
        if not letter_info:
            logger.warning(f"No letter data found for visual card: {letter}")
            return None

        # Build shape description and writing guide
        shape_description = f"{letter_info.get('name', letter)} has a distinctive shape used to write {letter}."
        
        # Simple key features based on letter type and difficulty
        key_features = []
        if letter_info.get("type") == "vowel":
            key_features.append("Vowel")
        else:
            key_features.append("Consonant")
        
        if letter_info.get("difficulty", 1) >= 3:
            key_features.append(f"Difficult pronunciation (level {letter_info['difficulty']}/5)")
        
        key_features_str = ", ".join(key_features)
        
        # Build handwriting guide components
        stroke_sequence = f"Write {letter_info['name']} with careful attention to stroke order (right-to-left for Armenian). Start from the top-right."
        writing_tips = f"Pay attention to proportions and spacing. The letter {letter_info['name']} is composed of {len(letter_info.get('pronunciation_tip', ''))} main strokes."
        
        common_mistakes = f"Common mistakes when writing {letter_info['name']}: incorrect stroke angles, inconsistent sizing, or missing key features. Practice slowly."
        
        shape_variants_str = f"In different contexts, {letter_info['name']} may appear in different positions (initial, medial, final) with slight variations."
        
        similar_letters_str = ""
        distinction_str = ""
        
        # Find similar letters for confusable pairs (western reversals)
        confusable_pairs = {
            'բ': ('պ', 'բ sounds like p, պ sounds like b'),
            'պ': ('բ', 'պ sounds like b, բ sounds like p'),
            'գ': ('կ', 'գ sounds like k, կ sounds like g'),
            'կ': ('գ', 'կ sounds like g, գ sounds like k'),
            'դ': ('տ', 'դ sounds like t, տ sounds like d'),
            'տ': ('դ', 'տ sounds like d, դ sounds like t'),
            'ճ': ('ջ', 'ճ sounds like j (dʒ), ջ sounds like ch (tʃ)'),
            'ջ': ('ճ', 'ջ sounds like ch (tʃ), ճ sounds like j (dʒ)'),
            'ծ': ('ձ', 'ծ is unvoiced dz, ձ is voiced dz'),
            'ձ': ('ծ', 'ձ is voiced dz, ծ is unvoiced dz'),
        }
        
        if letter in confusable_pairs:
            similar_letter, distinction = confusable_pairs[letter]
            similar_letters_str = f"Compare with {similar_letter}: {letter_info['name']} vs {letter_data.get_letter_info(similar_letter).get('name', similar_letter)}"
            distinction_str = distinction

        fields = {
            "Letter": letter_info["lowercase"],
            "LetterUppercase": letter_info["uppercase"],
            "LetterName": letter_info["name"],
            "Position": str(letter_info["position"]),
            "LetterType": letter_info["type"],
            "ShapeDescription": shape_description,
            "KeyFeatures": key_features_str,
            "StrokeSequence": stroke_sequence,
            "WritingTips": writing_tips,
            "CommonMistakes": common_mistakes,
            "ShapeVariants": shape_variants_str,
            "SimilarLetters": similar_letters_str,
            "Distinction": distinction_str,
            "IPA": letter_info["ipa"],
            "EnglishSound": letter_info["english"],
            "PronunciationTip": letter_info.get("pronunciation_tip", ""),
        }

        tags = [TAG_GENERATED, TAG_VISUAL_LETTER] + (extra_tags or [])

        # Add difficulty-specific tags
        if letter_info["difficulty"] >= 3:
            tags.append("difficult-pronunciation")
        if letter_info["type"] == "vowel":
            tags.append("vowel")
        elif letter_info["type"] == "consonant":
            tags.append("consonant")

        note_id = None
        if push_to_anki:
            note_id = self.anki.add_note(
                deck=deck or VISUAL_LETTER_CARDS_DECK,
                model=VISUAL_LETTER_CARDS_MODEL,
                fields=fields,
                tags=tags,
            )

        # Persist to local database
        db_card_id = self.db.upsert_card(
            word=letter,
            translation=f"{letter_info['name']} (visual: {letter_info['english']})",
            pos="letter",
            card_type="letter_visual",
            template_version=self.assets.template_version,
            metadata={
                "letter_name": letter_info["name"],
                "position": letter_info["position"],
                "letter_type": letter_info["type"],
                "ipa": letter_info["ipa"],
                "difficulty": letter_info["difficulty"],
                "visual_training": True,
            },
        )

        if not push_to_anki:
            note_id = db_card_id

        logger.info(f"Created visual letter card for: {letter} ({letter_info['name']})")
        return note_id

    def generate_all_visual_letter_cards(
        self,
        deck: Optional[str] = None,
        push_to_anki: bool = True,
        difficulty_filter: Optional[int] = None,
    ) -> list[int]:
        """Generate visual/handwriting training cards for all Armenian letters.

        Args:
            deck: Target deck (defaults to VISUAL_LETTER_CARDS_DECK)
            push_to_anki: Whether to push to Anki via AnkiConnect
            difficulty_filter: If set, only generate cards for letters with
                             difficulty >= this value (1-5)

        Returns:
            List of created note IDs
        """
        note_ids = []
        all_letters = letter_data.get_all_letters_ordered()

        for letter in all_letters:
            letter_info = letter_data.get_letter_info(letter)
            if letter_info:
                # Apply difficulty filter if specified
                if difficulty_filter and letter_info["difficulty"] < difficulty_filter:
                    continue

                note_id = self.generate_visual_letter_card(
                    letter=letter,
                    deck=deck,
                    push_to_anki=push_to_anki,
                )
                if note_id:
                    note_ids.append(note_id)

        logger.info(f"Created {len(note_ids)} visual letter cards (total letters: {len(all_letters)})")
        return note_ids

    def process_all(self, source_deck: Optional[str] = None, field_overrides: Optional[dict] = None,
                    default_pos: str = "noun", local_only: bool = False) -> dict:
        """Process all words and generate morphology cards.

        In ``local_only`` mode, reads vocabulary from local cache only and
        persists generated morphology/sentences to SQLite without Anki writes.
        """
        if not local_only:
            self.setup_models()
            self.setup_decks()

        words = self.get_source_words(
            source_deck,
            field_overrides,
            default_pos,
            use_cache=True,
            allow_anki_fallback=not local_only,
        )
        if not words:
            return {"total": 0, "nouns": 0, "verbs": 0, "sentences": 0, "errors": 0}

        stats = {"total": len(words), "nouns": 0, "verbs": 0, "sentences": 0, "errors": 0}

        for entry in words:
            word = entry["word"]
            pos = entry.get("pos", "").lower()
            translation = entry.get("translation", "")

            try:
                if pos in ("noun", "n"):
                    if self.generate_noun_card(word, translation, push_to_anki=not local_only):
                        stats["nouns"] += 1

                elif pos in ("verb", "v"):
                    if self.generate_verb_card(word, translation, push_to_anki=not local_only):
                        stats["verbs"] += 1

                # Generate sentence cards for both nouns and verbs
                if pos in ("noun", "n", "verb", "v"):
                    sent_ids = self.generate_sentence_cards(
                        word,
                        pos,
                        translation,
                        push_to_anki=not local_only,
                    )
                    stats["sentences"] += len(sent_ids)

            except Exception as exc:
                logger.error(f"Error processing '{word}': {exc}")
                stats["errors"] += 1

        return stats
