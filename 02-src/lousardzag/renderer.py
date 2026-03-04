"""Template renderer utilities for Anki model CSS and card templates.

This module externalizes note type presentation (HTML/CSS) so formatting can
be iterated without editing generation logic in ``card_generator.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

TEMPLATES_DIR = Path(__file__).parent / "templates"
TEMPLATE_VERSION = "v2"

LOANWORD_ORIGIN_CLASSES = {
    "unknown": "origin-unknown",
    "arabic": "origin-arabic",
    "turkish": "origin-turkish",
    "french": "origin-french",
    "farsi": "origin-farsi",
}

LOANWORD_ORIGIN_LABELS = {
    "unknown": "Origin Unknown",
    "arabic": "Arabic Loan",
    "turkish": "Turkish Loan",
    "french": "French Loan",
    "farsi": "Farsi Loan",
}

_TRANSLATION_HINTS = {
    "french": {
        "garage", "menu", "bureau", "balcony", "station", "restaurant",
        "hotel", "passport", "parade", "orange", "journal",
    },
    "turkish": {
        "kebab", "baklava", "coffee", "yogurt", "dolma", "pilaf", "pasha",
    },
    "arabic": {
        "sugar", "cotton", "algebra", "admiral", "magazine", "sofa",
        "syrup", "saffron",
    },
    "farsi": {
        "bazaar", "pajama", "shawl", "divan", "caravan", "jasmine",
    },
}

_WORD_HINTS = {
    "french": ("asion", "ment", "aj", "eur"),
    "turkish": ("oghlu", "oglu", "chi", "ji"),
    "arabic": ("allah", "din", "hak", "sultan"),
    "farsi": ("stan", "dar", "nameh"),
}


# Fallbacks keep behavior stable if template files are missing.
_FALLBACK_CSS = """
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
.loanword-chip {
    display: inline-block;
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.4px;
    margin-bottom: 8px;
    border: 1px solid #cfd8dc;
}
.origin-unknown { background: #f5f7fa; color: #455a64; }
.origin-arabic  { background: #fff3e0; color: #8d6e63; border-color: #ffcc80; }
.origin-turkish { background: #e8f5e9; color: #1b5e20; border-color: #a5d6a7; }
.origin-french  { background: #e3f2fd; color: #0d47a1; border-color: #90caf9; }
.origin-farsi   { background: #fce4ec; color: #880e4f; border-color: #f8bbd0; }
""".strip()

_FALLBACK_NOUN_FRONT = """
<div class="loanword-chip {{LoanwordBadgeClass}}">{{LoanwordOriginLabel}}</div>
<div class="case-label">Noun Declension</div>
<div class="armenian">{{Word}}</div>
<div class="translation">{{Translation}}</div>
<br>
<div>Decline this noun (all cases, singular & plural)</div>
""".strip()

_FALLBACK_NOUN_BACK = """
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
""".strip()

_FALLBACK_VERB_FRONT = """
<div class="loanword-chip {{LoanwordBadgeClass}}">{{LoanwordOriginLabel}}</div>
<div class="tense-label">Verb Conjugation</div>
<div class="armenian">{{Infinitive}}</div>
<div class="translation">{{Translation}}</div>
<br>
<div>Conjugate this verb (present, past, future)</div>
""".strip()

_FALLBACK_VERB_BACK = """
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
""".strip()

_FALLBACK_SENTENCES_FRONT = """
<div class="case-label">{{FormLabel}}</div>
<div class="sentence-en">{{EnglishSentence}}</div>
<br>
<div>Translate to Armenian:</div>
""".strip()

_FALLBACK_SENTENCES_BACK = """
{{FrontSide}}
<hr id="answer">
<div class="sentence-arm">{{ArmenianSentence}}</div>
<div class="armenian">{{Word}} - {{Translation}}</div>
<div class="loanword-chip {{LoanwordBadgeClass}}">{{LoanwordOriginLabel}}</div>
""".strip()

_FALLBACK_LETTER_FRONT = """
<div class="letter-display">
    <div class="letter-lowercase">{{Letter}}</div>
    <div class="letter-uppercase">{{LetterUppercase}}</div>
</div>
<div class="letter-name">{{LetterName}}</div>
{{#Audio}}{{Audio}}{{/Audio}}
<div class="prompt">What sound does this letter make?</div>
""".strip()

_FALLBACK_LETTER_BACK = """
{{FrontSide}}
<hr id="answer">
<div class="pronunciation-section">
    <div><strong>IPA:</strong> {{IPA}}</div>
    <div><strong>English sound:</strong> {{EnglishSound}}</div>
    <div><strong>Pronunciation tip:</strong> {{PronunciationTip}}</div>
    {{#WesternNote}}<div><strong>⚠️ Western Armenian:</strong> {{WesternNote}}</div>{{/WesternNote}}
    <div class="difficulty-badge">Difficulty: {{Difficulty}}/5</div>
</div>
<div class="examples-section">
    <div><strong>Example words:</strong></div>
    <div>{{ExampleWords}}</div>
</div>
<div class="letter-info">
    <span class="letter-type">{{LetterType}}</span>
    <span class="position">Position: {{Position}}/38</span>
</div>
{{#DiphthongInfo}}<div class="diphthong-section"><strong>Forms diphthong:</strong> {{DiphthongInfo}}</div>{{/DiphthongInfo}}
""".strip()


@dataclass(frozen=True)
class CardModelAssets:
    """Presentation assets consumed by the card generator."""

    css: str
    template_version: str
    noun_templates: list[dict]
    verb_templates: list[dict]
    sentence_templates: list[dict]
    letter_templates: list[dict]


def _read_or_fallback(path: Path, fallback: str) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return fallback


def load_card_model_assets() -> CardModelAssets:
    """Load Anki note model HTML/CSS from template files."""
    css = _read_or_fallback(TEMPLATES_DIR / "styles" / "base.css", _FALLBACK_CSS)

    noun_front = _read_or_fallback(
        TEMPLATES_DIR / "models" / "noun_declension" / "front.html",
        _FALLBACK_NOUN_FRONT,
    )
    noun_back = _read_or_fallback(
        TEMPLATES_DIR / "models" / "noun_declension" / "back.html",
        _FALLBACK_NOUN_BACK,
    )

    verb_front = _read_or_fallback(
        TEMPLATES_DIR / "models" / "verb_conjugation" / "front.html",
        _FALLBACK_VERB_FRONT,
    )
    verb_back = _read_or_fallback(
        TEMPLATES_DIR / "models" / "verb_conjugation" / "back.html",
        _FALLBACK_VERB_BACK,
    )

    sentences_front = _read_or_fallback(
        TEMPLATES_DIR / "models" / "vocab_sentences" / "front.html",
        _FALLBACK_SENTENCES_FRONT,
    )
    sentences_back = _read_or_fallback(
        TEMPLATES_DIR / "models" / "vocab_sentences" / "back.html",
        _FALLBACK_SENTENCES_BACK,
    )

    letter_front = _read_or_fallback(
        TEMPLATES_DIR / "models" / "letter_cards" / "front.html",
        _FALLBACK_LETTER_FRONT,
    )
    letter_back = _read_or_fallback(
        TEMPLATES_DIR / "models" / "letter_cards" / "back.html",
        _FALLBACK_LETTER_BACK,
    )

    return CardModelAssets(
        css=css,
        template_version=TEMPLATE_VERSION,
        noun_templates=[{
            "Name": "Declension Table",
            "Front": noun_front,
            "Back": noun_back,
        }],
        verb_templates=[{
            "Name": "Conjugation Table",
            "Front": verb_front,
            "Back": verb_back,
        }],
        sentence_templates=[{
            "Name": "Sentence Practice",
            "Front": sentences_front,
            "Back": sentences_back,
        }],
        letter_templates=[{
            "Name": "Letter Recognition",
            "Front": letter_front,
            "Back": letter_back,
        }],
    )


def infer_loanword_origin(word: str, translation: str = "") -> str:
    """Best-effort lightweight origin hint for learner-facing color chips.

    This is intentionally conservative and does not claim full etymological
    certainty; unknown is returned when no weak signal exists.
    """
    text = f"{word} {translation}".lower()
    tokenized = set(re.findall(r"[a-z]+", text))

    for origin, hints in _TRANSLATION_HINTS.items():
        if tokenized.intersection(hints):
            return origin

    lowered_word = (word or "").lower()
    for origin, suffixes in _WORD_HINTS.items():
        if any(lowered_word.endswith(suffix) for suffix in suffixes):
            return origin

    return "unknown"


def build_loanword_metadata(word: str, translation: str = "") -> dict[str, str]:
    """Return stable loanword metadata used by templates and DB rows."""
    origin = infer_loanword_origin(word, translation)
    badge_class = LOANWORD_ORIGIN_CLASSES.get(origin, LOANWORD_ORIGIN_CLASSES["unknown"])
    label = LOANWORD_ORIGIN_LABELS.get(origin, LOANWORD_ORIGIN_LABELS["unknown"])
    return {
        "loanword_origin": origin,
        "loanword_badge_class": badge_class,
        "loanword_origin_label": label,
    }


def render_template_html(template_html: str, fields: Mapping[str, object]) -> str:
    """Render a simple ``{{Field}}`` template string with field values."""
    rendered = template_html
    for key, value in fields.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value if value is not None else ""))
    rendered = re.sub(r"\{\{[^{}]+\}\}", "", rendered)
    return rendered


def render_card_preview(
    card_type: str,
    fields: Mapping[str, object],
    assets: CardModelAssets | None = None,
) -> dict[str, str]:
    """Render front/back HTML preview for a supported card type."""
    assets = assets or load_card_model_assets()
    if card_type == "noun_declension":
        front_tpl = assets.noun_templates[0]["Front"]
        back_tpl = assets.noun_templates[0]["Back"]
    elif card_type == "verb_conjugation":
        front_tpl = assets.verb_templates[0]["Front"]
        back_tpl = assets.verb_templates[0]["Back"]
    elif card_type == "vocab_sentences":
        front_tpl = assets.sentence_templates[0]["Front"]
        back_tpl = assets.sentence_templates[0]["Back"]
    else:
        raise ValueError(f"Unsupported card_type: {card_type}")

    front = render_template_html(front_tpl, fields)
    back_fields = dict(fields)
    back_fields.setdefault("FrontSide", front)
    back = render_template_html(back_tpl, back_fields)
    return {"front": front, "back": back}
