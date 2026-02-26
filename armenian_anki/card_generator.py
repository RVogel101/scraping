"""
Anki card generation pipeline.

Reads vocabulary from an existing Anki deck, generates morphological forms
(declensions, conjugations, articles, sentences), and creates new Anki cards
via AnkiConnect.
"""

import logging
from typing import Optional

from .anki_connect import AnkiConnect, AnkiConnectError
from .config import (
    SOURCE_DECK, TARGET_DECK,
    NOUN_DECLENSION_MODEL, VERB_CONJUGATION_MODEL, VOCAB_SENTENCES_MODEL,
    SOURCE_FIELDS, TAG_GENERATED, TAG_DECLENSION, TAG_CONJUGATION, TAG_SENTENCES,
    DEFAULT_NOUN_DECLENSION, DEFAULT_VERB_CLASS, SENTENCES_PER_WORD,
)
from .morphology.nouns import decline_noun, NounDeclension, CASE_LABELS_EN
from .morphology.verbs import conjugate_verb, VerbConjugation, PERSONS, PERSON_LABELS
from .morphology.articles import add_definite, add_indefinite
from .sentence_generator import generate_noun_sentences, generate_verb_sentences

logger = logging.getLogger(__name__)


# ─── Note Type CSS ────────────────────────────────────────────────────
ARMENIAN_CSS = """
.card {
    font-family: 'Noto Sans Armenian', 'DejaVu Sans', sans-serif;
    font-size: 20px;
    text-align: center;
    color: #333;
    background-color: #fafafa;
    padding: 20px;
}
.armenian {
    font-size: 28px;
    font-weight: bold;
    color: #1a237e;
    margin: 10px 0;
}
.translation {
    font-size: 18px;
    color: #555;
    font-style: italic;
}
.case-label, .tense-label {
    font-size: 14px;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 1px;
}
table {
    margin: 15px auto;
    border-collapse: collapse;
    font-size: 16px;
}
td, th {
    padding: 8px 16px;
    border: 1px solid #ddd;
}
th {
    background-color: #e8eaf6;
    font-weight: bold;
}
.highlight {
    color: #d32f2f;
    font-weight: bold;
}
.sentence {
    margin: 8px 0;
    font-size: 18px;
}
.sentence-arm {
    font-size: 22px;
    color: #1a237e;
}
.sentence-en {
    font-size: 16px;
    color: #666;
}
"""


# ─── Note Type Definitions ───────────────────────────────────────────

def _noun_declension_templates() -> list[dict]:
    """Card templates for the noun declension model."""
    # Front: show the word and ask for the declension table
    # Back: show the full declension table
    return [{
        "Name": "Declension Table",
        "Front": """
            <div class="case-label">Noun Declension</div>
            <div class="armenian">{{Word}}</div>
            <div class="translation">{{Translation}}</div>
            <br>
            <div>Decline this noun (all cases, singular & plural)</div>
        """,
        "Back": """
            {{FrontSide}}
            <hr id="answer">
            <div class="case-label">{{DeclensionClass}}</div>
            <table>
                <tr><th>Case</th><th>Singular</th><th>Sg Definite</th><th>Plural</th><th>Pl Definite</th></tr>
                <tr><td>Nominative</td><td>{{NomSg}}</td><td>{{NomSgDef}}</td><td>{{NomPl}}</td><td>{{NomPlDef}}</td></tr>
                <tr><td>Accusative</td><td>{{AccSg}}</td><td>{{AccSgDef}}</td><td>{{AccPl}}</td><td>{{AccPlDef}}</td></tr>
                <tr><td>Gen-Dative</td><td>{{GenDatSg}}</td><td>{{GenDatSgDef}}</td><td>{{GenDatPl}}</td><td>{{GenDatPlDef}}</td></tr>
                <tr><td>Ablative</td><td>{{AblSg}}</td><td>{{AblSgDef}}</td><td>{{AblPl}}</td><td>{{AblPlDef}}</td></tr>
                <tr><td>Instrumental</td><td>{{InstrSg}}</td><td>{{InstrSgDef}}</td><td>{{InstrPl}}</td><td>{{InstrPlDef}}</td></tr>
            </table>
            <div class="translation">Indefinite: {{NomSgIndef}}</div>
        """,
    }]


def _verb_conjugation_templates() -> list[dict]:
    """Card templates for the verb conjugation model."""
    return [{
        "Name": "Conjugation Table",
        "Front": """
            <div class="tense-label">Verb Conjugation</div>
            <div class="armenian">{{Infinitive}}</div>
            <div class="translation">{{Translation}}</div>
            <br>
            <div>Conjugate this verb (present, past, future)</div>
        """,
        "Back": """
            {{FrontSide}}
            <hr id="answer">
            <div class="tense-label">{{VerbClass}}</div>
            <table>
                <tr><th>Person</th><th>Present</th><th>Past</th><th>Future</th><th>Imperfect</th></tr>
                <tr><td>I</td><td>{{Pres1sg}}</td><td>{{Past1sg}}</td><td>{{Fut1sg}}</td><td>{{Imp1sg}}</td></tr>
                <tr><td>you</td><td>{{Pres2sg}}</td><td>{{Past2sg}}</td><td>{{Fut2sg}}</td><td>{{Imp2sg}}</td></tr>
                <tr><td>he/she</td><td>{{Pres3sg}}</td><td>{{Past3sg}}</td><td>{{Fut3sg}}</td><td>{{Imp3sg}}</td></tr>
                <tr><td>we</td><td>{{Pres1pl}}</td><td>{{Past1pl}}</td><td>{{Fut1pl}}</td><td>{{Imp1pl}}</td></tr>
                <tr><td>you(pl)</td><td>{{Pres2pl}}</td><td>{{Past2pl}}</td><td>{{Fut2pl}}</td><td>{{Imp2pl}}</td></tr>
                <tr><td>they</td><td>{{Pres3pl}}</td><td>{{Past3pl}}</td><td>{{Fut3pl}}</td><td>{{Imp3pl}}</td></tr>
            </table>
            <div class="translation">
                Imperative (sg): {{ImperSg}} &nbsp;|&nbsp; Imperative (pl): {{ImperPl}}<br>
                Past Participle: {{PastPart}} &nbsp;|&nbsp; Present Participle: {{PresPart}}
            </div>
        """,
    }]


def _vocab_sentences_templates() -> list[dict]:
    """Card templates for vocab sentence cards."""
    return [{
        "Name": "Sentence Practice",
        "Front": """
            <div class="case-label">{{FormLabel}}</div>
            <div class="sentence-en">{{EnglishSentence}}</div>
            <br>
            <div>Translate to Armenian:</div>
        """,
        "Back": """
            {{FrontSide}}
            <hr id="answer">
            <div class="sentence-arm">{{ArmenianSentence}}</div>
            <div class="armenian">{{Word}} — {{Translation}}</div>
        """,
    }]


# ─── Model Field Lists ───────────────────────────────────────────────

NOUN_FIELDS = [
    "Word", "Translation", "DeclensionClass",
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
    "Pres1sg", "Pres2sg", "Pres3sg", "Pres1pl", "Pres2pl", "Pres3pl",
    "Past1sg", "Past2sg", "Past3sg", "Past1pl", "Past2pl", "Past3pl",
    "Fut1sg", "Fut2sg", "Fut3sg", "Fut1pl", "Fut2pl", "Fut3pl",
    "Imp1sg", "Imp2sg", "Imp3sg", "Imp1pl", "Imp2pl", "Imp3pl",
    "ImperSg", "ImperPl", "PastPart", "PresPart",
]

SENTENCE_FIELDS = [
    "Word", "Translation", "FormLabel", "ArmenianSentence", "EnglishSentence",
]


# ─── Card Generator ──────────────────────────────────────────────────

class CardGenerator:
    """Orchestrates reading vocab from Anki and generating morphology cards."""

    def __init__(self, anki: Optional[AnkiConnect] = None):
        self.anki = anki or AnkiConnect()

    def setup_models(self) -> None:
        """Create the Anki note types (models) if they don't exist."""
        logger.info("Setting up Anki note types...")

        self.anki.create_model(
            name=NOUN_DECLENSION_MODEL,
            fields=NOUN_FIELDS,
            card_templates=_noun_declension_templates(),
            css=ARMENIAN_CSS,
        )

        self.anki.create_model(
            name=VERB_CONJUGATION_MODEL,
            fields=VERB_FIELDS,
            card_templates=_verb_conjugation_templates(),
            css=ARMENIAN_CSS,
        )

        self.anki.create_model(
            name=VOCAB_SENTENCES_MODEL,
            fields=SENTENCE_FIELDS,
            card_templates=_vocab_sentences_templates(),
            css=ARMENIAN_CSS,
        )

        logger.info("Note types ready")

    def setup_decks(self) -> None:
        """Create target decks if they don't exist."""
        self.anki.ensure_deck(TARGET_DECK)
        logger.info(f"Target deck ready: {TARGET_DECK}")

    def get_source_words(self, deck: str = None) -> list[dict]:
        """Read vocabulary words from the source Anki deck.

        Returns list of dicts with keys: word, pos, translation, pronunciation.
        """
        deck = deck or SOURCE_DECK
        notes = self.anki.get_deck_notes(deck)
        if not notes:
            logger.warning(f"No notes found in deck '{deck}'")
            return []

        words = []
        for note in notes:
            fields = {k: v["value"] for k, v in note.get("fields", {}).items()}
            entry = {}
            for key, field_name in SOURCE_FIELDS.items():
                entry[key] = fields.get(field_name, "")
            if entry.get("word"):
                words.append(entry)

        logger.info(f"Found {len(words)} vocabulary words in '{deck}'")
        return words

    def generate_noun_card(self, word: str, translation: str = "",
                           declension_class: str = None,
                           extra_tags: list = None,
                           deck: str = None) -> Optional[int]:
        """Generate and add a noun declension card to Anki."""
        cls = declension_class or DEFAULT_NOUN_DECLENSION
        decl = decline_noun(word, cls, translation)

        fields = {
            "Word": decl.word,
            "Translation": decl.translation,
            "DeclensionClass": cls,
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

        tags = [TAG_GENERATED, TAG_DECLENSION] + (extra_tags or [])
        note_id = self.anki.add_note(
            deck=deck or TARGET_DECK,
            model=NOUN_DECLENSION_MODEL,
            fields=fields,
            tags=tags,
        )
        if note_id:
            logger.info(f"Created noun declension card: {word} (ID: {note_id})")
        return note_id

    def generate_verb_card(self, infinitive: str, translation: str = "",
                           verb_class: str = None,
                           extra_tags: list = None,
                           deck: str = None) -> Optional[int]:
        """Generate and add a verb conjugation card to Anki."""
        cls = verb_class or DEFAULT_VERB_CLASS
        conj = conjugate_verb(infinitive, cls, translation)

        fields = {
            "Infinitive": conj.infinitive,
            "Translation": conj.translation,
            "VerbClass": cls,
            "Root": conj.root,
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

        tags = [TAG_GENERATED, TAG_CONJUGATION] + (extra_tags or [])
        note_id = self.anki.add_note(
            deck=deck or TARGET_DECK,
            model=VERB_CONJUGATION_MODEL,
            fields=fields,
            tags=tags,
        )
        if note_id:
            logger.info(f"Created verb conjugation card: {infinitive} (ID: {note_id})")
        return note_id

    def generate_sentence_cards(
        self,
        word: str,
        pos: str,
        translation: str = "",
        declension_class: str = None,
        verb_class: str = None,
        grammar_filter: str = None,
        max_sentences: int = None,
        extra_tags: list = None,
        deck: str = None,
    ) -> list[int]:
        """Generate sentence practice cards for a vocabulary word.

        Args:
            grammar_filter: If set, only generate sentences whose form_label
                            starts with or matches this grammar type string.
                            Used by the progression pipeline to target one
                            grammar structure per phrase slot.
            max_sentences:  Cap on how many sentence cards to create.
                            Defaults to SENTENCES_PER_WORD.
        """
        note_ids = []
        limit = max_sentences if max_sentences is not None else SENTENCES_PER_WORD

        if pos.lower() in ("noun", "n"):
            sentences = generate_noun_sentences(
                word, declension_class or DEFAULT_NOUN_DECLENSION,
                translation, limit * 3 if grammar_filter else limit,
            )
        elif pos.lower() in ("verb", "v"):
            sentences = generate_verb_sentences(
                word, verb_class or DEFAULT_VERB_CLASS,
                translation, limit * 3 if grammar_filter else limit,
            )
        else:
            logger.debug(f"Skipping sentence generation for POS '{pos}': {word}")
            return note_ids

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

        for form_label, arm_sentence, en_sentence in sentences:
            fields = {
                "Word": word,
                "Translation": translation,
                "FormLabel": form_label,
                "ArmenianSentence": arm_sentence,
                "EnglishSentence": en_sentence,
            }
            note_id = self.anki.add_note(
                deck=deck or TARGET_DECK,
                model=VOCAB_SENTENCES_MODEL,
                fields=fields,
                tags=tags,
            )
            if note_id:
                note_ids.append(note_id)

        logger.info(f"Created {len(note_ids)} sentence cards for: {word}")
        return note_ids

    def process_all(self, source_deck: str = None) -> dict:
        """Process all words in the source deck and generate morphology cards.

        Returns a summary dict with counts.
        """
        self.setup_models()
        self.setup_decks()

        words = self.get_source_words(source_deck)
        if not words:
            return {"total": 0, "nouns": 0, "verbs": 0, "sentences": 0, "errors": 0}

        stats = {"total": len(words), "nouns": 0, "verbs": 0, "sentences": 0, "errors": 0}

        for entry in words:
            word = entry["word"]
            pos = entry.get("pos", "").lower()
            translation = entry.get("translation", "")

            try:
                if pos in ("noun", "n"):
                    if self.generate_noun_card(word, translation):
                        stats["nouns"] += 1

                elif pos in ("verb", "v"):
                    if self.generate_verb_card(word, translation):
                        stats["verbs"] += 1

                # Generate sentence cards for both nouns and verbs
                if pos in ("noun", "n", "verb", "v"):
                    sent_ids = self.generate_sentence_cards(word, pos, translation)
                    stats["sentences"] += len(sent_ids)

            except Exception as exc:
                logger.error(f"Error processing '{word}': {exc}")
                stats["errors"] += 1

        return stats
