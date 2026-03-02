"""Build rendered sample cards from real data for preview surfaces."""

from __future__ import annotations

import html
import re
from typing import Any

from .database import CardDatabase
from .morphology.detect import detect_noun_class, detect_verb_class
from .morphology.nouns import decline_noun
from .morphology.verbs import PERSONS, conjugate_verb
from .renderer import build_loanword_metadata, load_card_model_assets, render_card_preview
from .sentence_generator import generate_noun_sentences, generate_verb_sentences


def _first_vocab_by_pos(
    db: CardDatabase,
    pos: str,
    source_deck: str | None = None,
) -> dict[str, Any] | None:
    entries = db.get_vocabulary_from_cache(source_deck)
    for entry in entries:
        if (entry.get("pos") or "").lower() != pos:
            continue
        lemma = _normalize_text(entry.get("lemma", ""))
        if lemma:
            entry = dict(entry)
            entry["lemma"] = lemma
            entry["translation"] = _normalize_text(entry.get("translation", ""))
            return entry
    return None


def _normalize_text(value: str) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _fallback_from_cards(db: CardDatabase, card_type: str) -> dict[str, Any] | None:
    cards = db.list_cards(card_type=card_type)
    for card in cards:
        lemma = _normalize_text(card.get("word", ""))
        if lemma:
            card = dict(card)
            card["word"] = lemma
            card["translation"] = _normalize_text(card.get("translation", ""))
            return card
    return None


def _noun_fields(word: str, translation: str) -> dict[str, str]:
    decl_class = detect_noun_class(word)
    decl = decline_noun(word, decl_class, translation)
    loan = build_loanword_metadata(word, translation)
    return {
        "Word": decl.word,
        "Translation": decl.translation,
        "DeclensionClass": decl_class,
        "LoanwordOrigin": loan["loanword_origin"],
        "LoanwordOriginLabel": loan["loanword_origin_label"],
        "LoanwordBadgeClass": loan["loanword_badge_class"],
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


def _verb_fields(word: str, translation: str) -> dict[str, str]:
    verb_class = detect_verb_class(word)
    conj = conjugate_verb(word, verb_class, translation)
    loan = build_loanword_metadata(word, translation)

    fields: dict[str, str] = {
        "Infinitive": conj.infinitive,
        "Translation": conj.translation,
        "VerbClass": verb_class,
        "Root": conj.root,
        "LoanwordOrigin": loan["loanword_origin"],
        "LoanwordOriginLabel": loan["loanword_origin_label"],
        "LoanwordBadgeClass": loan["loanword_badge_class"],
    }

    for person in PERSONS:
        fields[f"Pres{person}"] = conj.present.get(person, "")
        fields[f"Past{person}"] = conj.past_aorist.get(person, "")
        fields[f"Fut{person}"] = conj.future.get(person, "")
        fields[f"Imp{person}"] = conj.imperfect.get(person, "")

    fields["ImperSg"] = conj.imperative_sg
    fields["ImperPl"] = conj.imperative_pl
    fields["PastPart"] = conj.past_participle
    fields["PresPart"] = conj.present_participle
    return fields


def _sentence_fields(word: str, translation: str, pos: str) -> dict[str, str]:
    loan = build_loanword_metadata(word, translation)
    if pos == "verb":
        label, arm, eng = generate_verb_sentences(
            word,
            detect_verb_class(word),
            translation,
            max_sentences=1,
        )[0]
    else:
        label, arm, eng = generate_noun_sentences(
            word,
            detect_noun_class(word),
            translation,
            max_sentences=1,
        )[0]

    return {
        "Word": word,
        "Translation": translation,
        "FormLabel": label,
        "ArmenianSentence": arm,
        "EnglishSentence": eng,
        "LoanwordOrigin": loan["loanword_origin"],
        "LoanwordOriginLabel": loan["loanword_origin_label"],
        "LoanwordBadgeClass": loan["loanword_badge_class"],
    }


def build_preview_payload(db: CardDatabase, source_deck: str | None = None) -> dict[str, Any]:
    """Build rendered noun, verb, and sentence previews from local real data."""
    assets = load_card_model_assets()

    noun_entry = _first_vocab_by_pos(db, "noun", source_deck)
    if not noun_entry:
        noun_card = _fallback_from_cards(db, "noun_declension")
        if noun_card:
            noun_entry = {
                "lemma": noun_card.get("word", "մայր"),
                "translation": noun_card.get("translation", ""),
            }
    noun_word = (noun_entry or {}).get("lemma") or "մայր"
    noun_translation = (noun_entry or {}).get("translation") or "mother"
    noun_fields = _noun_fields(noun_word, noun_translation)

    verb_entry = _first_vocab_by_pos(db, "verb", source_deck)
    if not verb_entry:
        verb_card = _fallback_from_cards(db, "verb_conjugation")
        if verb_card:
            verb_entry = {
                "lemma": verb_card.get("word", "գրել"),
                "translation": verb_card.get("translation", ""),
            }
    verb_word = (verb_entry or {}).get("lemma") or "գրել"
    verb_translation = (verb_entry or {}).get("translation") or "to write"
    verb_fields = _verb_fields(verb_word, verb_translation)

    sentence_source_word = noun_word if noun_word else verb_word
    sentence_source_translation = noun_translation if noun_word else verb_translation
    sentence_source_pos = "noun" if noun_word else "verb"
    sentence_fields = _sentence_fields(
        sentence_source_word,
        sentence_source_translation,
        sentence_source_pos,
    )

    noun_rendered = render_card_preview("noun_declension", noun_fields, assets)
    verb_rendered = render_card_preview("verb_conjugation", verb_fields, assets)
    sentence_rendered = render_card_preview("vocab_sentences", sentence_fields, assets)

    return {
        "template_version": assets.template_version,
        "cards": {
            "noun": {
                "card_type": "noun_declension",
                "fields": noun_fields,
                "rendered": noun_rendered,
                "source": {
                    "word": noun_word,
                    "translation": noun_translation,
                },
            },
            "verb": {
                "card_type": "verb_conjugation",
                "fields": verb_fields,
                "rendered": verb_rendered,
                "source": {
                    "word": verb_word,
                    "translation": verb_translation,
                },
            },
            "sentence": {
                "card_type": "vocab_sentences",
                "fields": sentence_fields,
                "rendered": sentence_rendered,
                "source": {
                    "word": sentence_source_word,
                    "translation": sentence_source_translation,
                    "pos": sentence_source_pos,
                },
            },
        },
    }
