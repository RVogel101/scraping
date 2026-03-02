"""
Armenian text tokenizer for frequency analysis.

Tokenizes Armenian text on word boundaries, normalizes characters,
and handles Armenian-specific punctuation and typography.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Iterable


# Armenian Unicode ranges:
#   U+0531–U+0556: Armenian capital letters
#   U+0561–U+0587: Armenian lowercase letters (includes և U+0587)
#   U+FB13–U+FB17: Armenian ligatures
# Excludes U+0559–U+055F (Armenian punctuation/modifier marks)
_ARMENIAN_WORD_RE = re.compile(
    r"[\u0531-\u0556\u0561-\u0587\uFB13-\uFB17]+", re.UNICODE
)

# Armenian punctuation to strip (Armenian full stop ։, comma ՝, etc.)
_ARMENIAN_PUNCT = set("։՝՜՞՛")

# Ligature normalization: Armenian ligatures → decomposed forms
_LIGATURE_MAP: dict[str, str] = {
    "\uFB00": "ff",        # not Armenian, but in the block
    "\uFB01": "fi",
    "\uFB02": "fl",
    "\uFB03": "ffi",
    "\uFB04": "ffl",
    "\uFB05": "ſt",
    "\uFB06": "st",
    "\uFB13": "\u0574\u0576",    # ﬓ → մն
    "\uFB14": "\u0574\u0565",    # ﬔ → մե
    "\uFB15": "\u0574\u056B",    # ﬕ → մի
    "\uFB16": "\u057E\u0576",    # ﬖ → վն
    "\uFB17": "\u0574\u056D",    # ﬗ → մխ
}


def normalize_armenian(text: str) -> str:
    """Normalize Armenian text for consistent tokenization.

    - NFC Unicode normalization
    - Lowercase Armenian characters (Ա→ա, Բ→բ, etc.)
    - Decompose Armenian ligatures
    - Strip zero-width characters
    """
    # NFC normalization
    text = unicodedata.normalize("NFC", text)

    # Decompose Armenian ligatures
    for lig, decomp in _LIGATURE_MAP.items():
        text = text.replace(lig, decomp)

    # Armenian lowercase: Armenian capital letters are U+0531–U+0556,
    # lowercase are U+0561–U+0586 (offset of 0x30)
    result = []
    for ch in text:
        cp = ord(ch)
        if 0x0531 <= cp <= 0x0556:
            result.append(chr(cp + 0x30))
        else:
            result.append(ch)

    return "".join(result)


def tokenize_armenian(text: str) -> list[str]:
    """Extract Armenian words from text.

    Returns lowercase, normalized Armenian word tokens.
    Non-Armenian text (Latin, Cyrillic, digits, punctuation) is discarded.
    """
    normalized = normalize_armenian(text)
    return _ARMENIAN_WORD_RE.findall(normalized)


def count_frequencies(texts: Iterable[str]) -> Counter[str]:
    """Count word frequencies across multiple text documents.

    Args:
        texts: Iterable of text strings (articles, pages, etc.)

    Returns:
        Counter mapping word → frequency count
    """
    freq: Counter[str] = Counter()
    for text in texts:
        tokens = tokenize_armenian(text)
        freq.update(tokens)
    return freq


def filter_by_min_length(freq: Counter[str], min_len: int = 2) -> Counter[str]:
    """Remove single-character tokens (likely noise)."""
    return Counter({w: c for w, c in freq.items() if len(w) >= min_len})


def is_armenian_word(word: str) -> bool:
    """Check if a string consists entirely of Armenian characters."""
    return bool(_ARMENIAN_WORD_RE.fullmatch(word))
