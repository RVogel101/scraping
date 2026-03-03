"""
OCR-to-Vocabulary Bridge.

Parses extracted OCR text (JSON/CSV) from CWAS Word-of-the-Day images
and produces a structured vocabulary list suitable for the card generation
pipeline.

Each CWAS word typically spans multiple images:
  - Title card:  ArmenianWord transliteration (POS) Translation
  - Etymology / Word breakdown / Example / Declension / Conjugation cards

This module extracts vocabulary entries from the title cards and enriches
them from companion cards when possible.
"""

import csv
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# The boilerplate suffix found in title cards
_BOILERPLATE = (
    "The \u00abWord of the Day\u00bb is the intellectual property of the "
    "Centre for Western Armenian Studies"
)

# CWAS header text to strip
_CWAS_HEADER = "Centre for Western Armenian Studies"
_CWAS_HEADER_HY = "\u0531\u0580\u0565\u0582\u0574\u057f\u0561\u0570\u0561\u0575\u0561\u0563\u056b\u057f\u0561\u056f\u0561\u0576 \u0548\u0582\u057d\u0574\u0561\u0576\u0581 \u053f\u0565\u0564\u0580\u0578\u0576"

# Armenian Unicode range
_ARM_RANGE = "\u0531-\u058a\u0561-\u0587\ufb13-\ufb17"

# Matches an Armenian word (one or more Armenian characters)
_RE_ARM_WORD = re.compile(rf"[{_ARM_RANGE}]+")

# POS patterns (case-insensitive) — matches "(Noun)", "[Verb]", "{Adjective}", etc.
_RE_POS = re.compile(
    r"[\(\[\{]\s*(Noun|Verb|Adjective|Adverb|Noun and verb|"
    r"Noun and proper noun|Adjective and noun|Adjective and adverb|"
    r"Noun and adjective|Proper noun)\s*[\)\]\}]",
    re.IGNORECASE,
)

# Transliteration: hyphenated lowercase Latin syllables like "gay-lag", "ar-ha-virk", "a-del"
_RE_TRANSLIT = re.compile(r"\b([a-z][a-z']*(?:-[a-z']+)+)\b")


@dataclass
class VocabEntry:
    """A single vocabulary item parsed from OCR output."""
    armenian_word: str
    transliteration: str = ""
    pos: str = ""
    translation: str = ""
    cwas_number: str = ""
    date: str = ""
    confidence: float = 0.0
    source_files: list[str] = field(default_factory=list)


def load_extracted_json(path: str | Path) -> list[dict]:
    """Load an OCR extraction JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_extracted_csv(path: str | Path) -> list[dict]:
    """Load an OCR extraction CSV file."""
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "confidence" in row:
                row["confidence"] = float(row["confidence"])
            rows.append(row)
    return rows


def _is_title_card(text: str) -> bool:
    """Check whether the OCR text is a CWAS title card (has boilerplate)."""
    return _BOILERPLATE.lower() in text.lower()


def _strip_cwas_boilerplate(text: str) -> str:
    """Remove CWAS header and boilerplate from the text, returning the payload."""
    # Remove everything after the boilerplate
    idx = text.lower().find(_BOILERPLATE.lower())
    if idx >= 0:
        text = text[:idx].strip()

    # Remove CWAS header and Armenian header
    text = text.replace(_CWAS_HEADER, "").strip()
    text = text.replace(_CWAS_HEADER_HY, "").strip()

    # Remove leading special chars and quotes
    text = text.lstrip('""\u00ab\u00bb@#oO0Nn \t')

    return text.strip()


def _normalise_pos(raw: str) -> str:
    """Normalise a POS string to a standard form."""
    r = raw.strip().lower()
    if "verb" in r and "noun" in r:
        return "noun"  # default to noun for dual-POS words
    if "adjective" in r and "noun" in r:
        return "adjective"
    if "noun" in r:
        return "noun"
    if "verb" in r:
        return "verb"
    if "adjective" in r or "adverb" in r:
        return "adjective"
    return r


def _parse_title_card(text: str) -> dict | None:
    """Parse a CWAS title card and extract vocabulary fields.

    Returns a dict with keys: armenian_word, transliteration, pos, translation.
    Returns None if parsing fails.
    """
    payload = _strip_cwas_boilerplate(text)
    if not payload:
        return None

    result = {
        "armenian_word": "",
        "transliteration": "",
        "pos": "",
        "translation": "",
    }

    # 1. Extract POS
    pos_match = _RE_POS.search(payload)
    if pos_match:
        result["pos"] = _normalise_pos(pos_match.group(1))
        # Split payload around POS tag
        before_pos = payload[:pos_match.start()].strip()
        after_pos = payload[pos_match.end():].strip()
    else:
        before_pos = payload
        after_pos = ""

    # 2. Extract transliteration from the before_pos section
    translit_match = _RE_TRANSLIT.search(before_pos)
    if translit_match:
        result["transliteration"] = translit_match.group(1)
        # Everything before the transliteration might contain the Armenian word
        before_translit = before_pos[:translit_match.start()].strip()
        after_translit = before_pos[translit_match.end():].strip()
    else:
        before_translit = before_pos
        after_translit = ""

    # 3. Extract Armenian word
    arm_words = _RE_ARM_WORD.findall(before_translit)
    if arm_words:
        result["armenian_word"] = arm_words[-1]  # last Armenian word before translit
    elif not translit_match:
        # Try finding Armenian word in the full payload
        arm_words = _RE_ARM_WORD.findall(payload)
        if arm_words:
            result["armenian_word"] = arm_words[0]

    # 4. Extract translation (from after POS, or after translit if no POS)
    translation = after_pos if after_pos else after_translit
    # Clean up translation: remove numbering like "1. xxx 2. yyy" → "xxx"
    translation = re.sub(r"^\d+\.\s*", "", translation).strip()
    # Take up to the first sentence ending or numbered item
    m = re.match(r"^(.+?)(?:\s+\d+\.\s|\s*$)", translation, re.DOTALL)
    if m:
        translation = m.group(1).strip().rstrip(".,;:")
    result["translation"] = translation

    # Reject entries with no useful data
    if not result["armenian_word"] and not result["transliteration"]:
        return None

    return result


def _detect_card_type(text: str) -> str:
    """Classify a CWAS card by its content type."""
    lower = text.lower()
    if _is_title_card(text):
        return "title"
    if lower.startswith("etymology") or "etymology" in lower[:30]:
        return "etymology"
    if lower.startswith("word breakdown") or "word breakdown" in lower[:30]:
        return "word_breakdown"
    if lower.startswith("example") or lower.startswith("examples"):
        return "example"
    if lower.startswith("declension") or "declension" in lower[:30]:
        return "declension"
    if lower.startswith("conjugation") or "conjugation" in lower[:30]:
        return "conjugation"
    return "other"


def extract_vocab_from_records(records: list[dict]) -> list[VocabEntry]:
    """Extract vocabulary entries from a list of OCR records.

    Groups records by CWAS number, finds the title card for each word,
    and parses vocabulary information from it.

    Args:
        records: List of dicts with keys: filename, cwas_number, date,
                 text, confidence (as produced by extract_image_text_simple.py).

    Returns:
        List of VocabEntry objects, sorted by CWAS number.
    """
    # Group records by CWAS number
    groups: dict[str, list[dict]] = {}
    for rec in records:
        cwas = rec.get("cwas_number", "")
        if not cwas:
            continue
        groups.setdefault(cwas, []).append(rec)

    entries: list[VocabEntry] = []

    for cwas_num in sorted(groups.keys()):
        group = groups[cwas_num]
        title_rec = None
        parsed = None

        # Find the title card (has boilerplate) with highest confidence
        title_candidates = [
            r for r in group if _is_title_card(r.get("text", ""))
        ]
        if not title_candidates:
            continue

        title_candidates.sort(key=lambda r: r.get("confidence", 0), reverse=True)
        title_rec = title_candidates[0]
        parsed = _parse_title_card(title_rec["text"])
        if not parsed:
            continue

        # Check for POS hints from word-breakdown cards if POS is missing
        if not parsed["pos"]:
            for rec in group:
                bt = rec.get("text", "").lower()
                if "verb ending" in bt or "group of verbs" in bt:
                    parsed["pos"] = "verb"
                    break
                if "suffix which makes nouns" in bt or "suffix which forms abstract nouns" in bt:
                    parsed["pos"] = "noun"
                    break
            # Check if the card type provides POS clues
            for rec in group:
                card_type = _detect_card_type(rec.get("text", ""))
                if card_type == "declension":
                    parsed["pos"] = parsed["pos"] or "noun"
                elif card_type == "conjugation":
                    parsed["pos"] = parsed["pos"] or "verb"

        entry = VocabEntry(
            armenian_word=parsed["armenian_word"],
            transliteration=parsed["transliteration"],
            pos=parsed["pos"] or "noun",  # default to noun
            translation=parsed["translation"],
            cwas_number=cwas_num,
            date=title_rec.get("date", ""),
            confidence=title_rec.get("confidence", 0.0),
            source_files=[r.get("filename", "") for r in group],
        )
        entries.append(entry)

    logger.info(f"Extracted {len(entries)} vocabulary entries from {len(records)} OCR records")
    return entries


def extract_vocab_from_file(path: str | Path) -> list[VocabEntry]:
    """Load an extracted OCR file (JSON or CSV) and return VocabEntry list."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        records = load_extracted_json(path)
    elif path.suffix.lower() == ".csv":
        records = load_extracted_csv(path)
    else:
        raise ValueError(f"Unsupported file type: {path.suffix}")
    return extract_vocab_from_records(records)


def vocab_to_word_entries(entries: list[VocabEntry]) -> list:
    """Convert VocabEntry list to WordEntry list for the progression pipeline.

    Returns a list of lousardzag.progression.WordEntry objects,
    ready to be fed into ProgressionPlan.
    """
    from .progression import WordEntry
    from .morphology.core import count_syllables

    word_entries = []
    for rank, entry in enumerate(entries, start=1):
        if not entry.armenian_word:
            continue
        syl = count_syllables(entry.armenian_word)
        we = WordEntry(
            word=entry.armenian_word,
            translation=entry.translation,
            pos=entry.pos,
            frequency_rank=rank,
            syllable_count=syl if syl > 0 else 1,
        )
        word_entries.append(we)
    return word_entries


def vocab_to_csv(entries: list[VocabEntry], output_path: str | Path) -> None:
    """Write vocabulary entries to a CSV file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "armenian_word", "transliteration", "pos", "translation",
            "cwas_number", "date", "confidence",
        ])
        writer.writeheader()
        for entry in entries:
            writer.writerow({
                "armenian_word": entry.armenian_word,
                "transliteration": entry.transliteration,
                "pos": entry.pos,
                "translation": entry.translation,
                "cwas_number": entry.cwas_number,
                "date": entry.date,
                "confidence": f"{entry.confidence:.1f}",
            })
    logger.info(f"Wrote {len(entries)} vocab entries to {output_path}")


def vocab_to_json(entries: list[VocabEntry], output_path: str | Path) -> None:
    """Write vocabulary entries to a JSON file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = [
        {
            "armenian_word": e.armenian_word,
            "transliteration": e.transliteration,
            "pos": e.pos,
            "translation": e.translation,
            "cwas_number": e.cwas_number,
            "date": e.date,
            "confidence": e.confidence,
            "source_files": e.source_files,
        }
        for e in entries
    ]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Wrote {len(entries)} vocab entries to {output_path}")
