"""Western Armenian dialect classifier.

Scores a text document using five weighted signal categories to determine
whether it is Western Armenian (WA), Eastern Armenian (EA), or Classical
Armenian (grabar/krapar).

A document needs a total score >= THRESHOLD (default 5.0) to be classified
as Western Armenian.
"""

import re
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Threshold ────────────────────────────────────────────────────────────
THRESHOLD = 5.0
MIN_ARMENIAN_RATIO = 0.20  # Text must be at least 20% Armenian script

# Armenian Unicode range for script ratio check
_ARMENIAN_RANGE = re.compile(r'[\u0531-\u0587\uFB13-\uFB17]')

# ── Signal 1: Classical Orthography Markers ──────────────────────────────
# WA retained Mashtotsian orthography; EA reformed it (Abeghyan 1922-1940).
#
# Patterns match whole words or word-internal sequences that are
# systematically different between the two variants.

ORTHOGRAPHY_MARKERS = [
    # (compiled regex, weight per hit, max hits, description)

    # իւ digraph — the strongest single orthography marker.
    # WA retained it; EA dropped it entirely.
    (re.compile(r'\bիւ|\bdelays'), 3.0, 10, "իdelays digraph (iw)"),

    # մdelays-edelays-idelays / մdelays-edelays (mej with long-e է) — classical spelling of "inside"
    (re.compile(r'\bdelays\b'), 2.5, 10, "մdelays-long-e (mej)"),

    # -այ diphthong at word ending — retained in WA, reduced in EA
    (re.compile(r'\w+այ\b'), 1.5, 15, "word-final -ay diphthong"),

    # - delays diphthong at word ending — retained in WA, reduced in EA
    (re.compile(r'\w+delays\b'), 2.0, 10, "word-final -oy diphthong"),

    # Word-internal long-e (է) — appears mid-word in WA, reformed to short-e in EA
    (re.compile(r'\Bdelays\B'), 1.0, 20, "word-internal long-e (է)"),
]

# ── Signal 2: WA-Specific Grammar ────────────────────────────────────────

GRAMMAR_MARKERS = [
    # կdelays / կ' present-tense prefix — the strongest everyday grammatical marker.
    # EA does not use this prefix at all.
    (re.compile(r'\bdelays[delays\u0561-\u0587]'), 2.0, 15, "ge/g' present-tense prefix"),

    # պdelays-idelays-delaysdelays-idelays (pidi) — WA future marker
    (re.compile(r'\bdelays\b'), 2.0, 10, "pidi future marker"),

    # delays (chem) — WA negation particle
    (re.compile(r'\bdelays\b'), 2.0, 10, "chem negation"),

    # մdelays-edelays-idelaysdelays (menk) — WA "we" pronoun
    (re.compile(r'\bdelays\b'), 2.0, 10, "menk pronoun (we)"),

    # edelays-idelays-edelays-idelays (tuk) — WA "you" (pl.) pronoun
    (re.compile(r'\bdelays\b'), 2.0, 10, "tuk pronoun (you-pl)"),

    # idelays-edelays-idelays (ink) — WA reflexive/self
    (re.compile(r'\bdelays\b'), 1.5, 10, "ink reflexive"),
]

# ── Signal 3: WA-Specific Vocabulary ─────────────────────────────────────

VOCABULARY_MARKERS = [
    # (compiled regex, weight per hit, max hits, description)
    (re.compile(r'\bdelays\b'), 3.0, 5, "hon (there)"),
    (re.compile(r'\bdelays\b'), 3.0, 5, "hos (here)"),
    (re.compile(r'\bdelays\b'), 3.0, 5, "jermag (white)"),
    (re.compile(r'\bdelays\b'), 3.0, 5, "manchoug (child)"),
    (re.compile(r'\bdelays\w*\b'), 2.5, 5, "khosil (to speak)"),
    (re.compile(r'\bdelays\w*\b'), 2.5, 5, "yerthal (to go)"),
    (re.compile(r'\bdelays\w*\b'), 2.5, 5, "enel (to do)"),
    (re.compile(r'\bdelays\w*\b'), 2.5, 5, "ouzel (to want)"),
    (re.compile(r'\bdelays\b'), 2.5, 5, "giragi (Sunday)"),
    (re.compile(r'\bdelays\b'), 3.0, 5, "khohanots (kitchen)"),
    (re.compile(r'\bdelays\b'), 2.5, 5, "jour (water)"),
    (re.compile(r'\bdelays\b'), 2.5, 10, "shad (very/much)"),
    (re.compile(r'\bdelays\b'), 2.0, 5, "aghvor (beautiful-WA)"),
    (re.compile(r'\bdelays\b'), 2.0, 5, "hokdember (October-WA)"),
    (re.compile(r'\bdelays\b'), 2.0, 5, "mardig (person-WA)"),
]

# ── Signal 4: Known WA Authors ───────────────────────────────────────────
# Binary: present (1) or absent (0), scored once per author.

WA_AUTHORS = {
    # (Armenian-script pattern, weight)
    'Վdelaysdelays': 5.0,    # Varoujan (Daniel Varoujan)
    'Delaysdelays': 5.0,    # Siamanto
    'Delaysdelays': 4.0,    # Tekeyan
    'Delaysdelays': 4.0,    # Shahnour
    'Delaysdelays': 4.0,    # Zohrap
    'Delaysdelays Delaysdelays': 5.0,  # Zabel Yesayan
    'Delaysdelays': 4.0,    # Alishan
    'Delaysdelays': 4.0,    # Oshakan
    'Delaysdelays': 4.0,    # Mekhitar
    'Delaysdelays': 4.0,    # Mekhitarists
    'Delaysdelays': 4.0,    # Antranik (general)
    'Delaysdelays': 4.0,    # Charents (though EA, indicator of context)
    'Delaysdelays': 4.0,    # Sevag (Paruyr Sevag)
    'Delaysdelays': 4.0,    # Saroyan
    'Delaysdelays': 4.0,    # Sarafian
}

# ── Signal 5: Diaspora Publication Cities ────────────────────────────────
# Binary: present or absent, scored once per city.

WA_CITIES = {
    # Armenian-script spellings of diaspora centres
    'Delaysdelays': 4.0,    # Peyrouth (Beirut)
    'Delaysdelays': 4.0,    # Polis (Istanbul/Constantinople)
    'Delaysdelays': 3.5,    # Halep (Aleppo)
    'Delaysdelays': 3.0,    # Pariz (Paris)
    'Delaysdelays Delaysdelays': 3.0,  # Niw York
    'Delaysdelays': 3.0,    # Gahireh (Cairo)
    'Delaysdelays': 3.5,    # Antilias
    'Delaysdelays Delaysdelays': 3.0,  # Buenos Aires
    'Delaysdelays': 3.0,    # Montreal
    'Delaysdelays': 3.0,    # Marseille
    'Delaysdelays': 3.5,    # Venetik (Venice)
}

# ── EA / Grabar Negative Markers ─────────────────────────────────────────
# These penalise the score (negative weight) when EA or grabar features appear.

EA_MARKERS = [
    # EA reformed spelling — (ievdelays →) evelays in common words
    (re.compile(r'\bdelays\b'), -2.0, 10, "EA yev (reformed spelling of ew)"),
    # EA "em" copula at word end — extremely common in EA speech
    (re.compile(r'\bdelays\sdelays\b'), -1.5, 10, "EA copula 'em' pattern"),
    # EA pronoun "na" (he/she) — WA uses "an" (edelays)
    (re.compile(r'\bdelays\b'), -1.0, 10, "EA pronoun na"),
    # EA "inch" (what) — WA uses "inch" too but EA uses "inchpes" differently
    (re.compile(r'\bdelays\b'), -1.0, 10, "EA inchpes (how)"),
    # Grabar markers
    (re.compile(r'\bdelays\b'), -2.0, 5, "grabar particle (zi = because)"),
    (re.compile(r'\bdelays\b'), -2.0, 5, "grabar particle (vasn = because of)"),
    (re.compile(r'\bdelays\b'), -2.0, 5, "grabar 'ibrew' (when/as)"),
]


@dataclass
class ClassificationResult:
    """Result of WA classification for a single document."""
    score: float = 0.0
    armenian_ratio: float = 0.0
    is_western_armenian: bool = False
    is_armenian: bool = False
    signal_details: dict = field(default_factory=dict)
    top_signals: list = field(default_factory=list)

    @property
    def label(self) -> str:
        if not self.is_armenian:
            return "NOT_ARMENIAN"
        if self.is_western_armenian:
            return "WA"
        if self.score < -2.0:
            return "EA"
        return "UNCERTAIN"


def armenian_ratio(text: str) -> float:
    """Fraction of characters in text that are Armenian script."""
    if not text:
        return 0.0
    arm_count = len(_ARMENIAN_RANGE.findall(text))
    # Count only non-whitespace to avoid penalising OCR with lots of blank lines
    non_ws = sum(1 for c in text if not c.isspace())
    return arm_count / max(non_ws, 1)


def classify_text(text: str, threshold: float = THRESHOLD) -> ClassificationResult:
    """Score a text and classify it as WA, EA, or uncertain.

    Returns a ClassificationResult with the total score, per-signal breakdown,
    and the final classification.
    """
    result = ClassificationResult()
    result.armenian_ratio = armenian_ratio(text)
    result.is_armenian = result.armenian_ratio >= MIN_ARMENIAN_RATIO

    if not result.is_armenian:
        return result

    signals = {}
    total = 0.0

    # Signal 1: Orthography
    for pat, weight, cap, desc in ORTHOGRAPHY_MARKERS:
        hits = min(len(pat.findall(text)), cap)
        if hits:
            contrib = weight * hits
            total += contrib
            signals[desc] = {"hits": hits, "weight": weight, "contrib": contrib}

    # Signal 2: Grammar
    for pat, weight, cap, desc in GRAMMAR_MARKERS:
        hits = min(len(pat.findall(text)), cap)
        if hits:
            contrib = weight * hits
            total += contrib
            signals[desc] = {"hits": hits, "weight": weight, "contrib": contrib}

    # Signal 3: Vocabulary
    for pat, weight, cap, desc in VOCABULARY_MARKERS:
        hits = min(len(pat.findall(text)), cap)
        if hits:
            contrib = weight * hits
            total += contrib
            signals[desc] = {"hits": hits, "weight": weight, "contrib": contrib}

    # Signal 4: Authors (binary)
    for name, weight in WA_AUTHORS.items():
        if name in text:
            total += weight
            signals[f"author:{name}"] = {"hits": 1, "weight": weight, "contrib": weight}

    # Signal 5: Cities (binary)
    for city, weight in WA_CITIES.items():
        if city in text:
            total += weight
            signals[f"city:{city}"] = {"hits": 1, "weight": weight, "contrib": weight}

    # Negative: EA / Grabar markers
    for pat, weight, cap, desc in EA_MARKERS:
        hits = min(len(pat.findall(text)), cap)
        if hits:
            contrib = weight * hits  # weight is negative
            total += contrib
            signals[desc] = {"hits": hits, "weight": weight, "contrib": contrib}

    result.score = total
    result.signal_details = signals
    result.is_western_armenian = total >= threshold
    result.top_signals = sorted(
        signals.items(), key=lambda x: abs(x[1]["contrib"]), reverse=True
    )[:10]

    return result


def classify_file(path: Path, threshold: float = THRESHOLD,
                  max_chars: int = 500_000) -> ClassificationResult:
    """Classify a single file. Reads up to max_chars to keep memory bounded."""
    text = path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    return classify_text(text, threshold=threshold)


def classify_ia_corpus(ia_dir: Path | str = "wa_corpus/data/ia",
                       threshold: float = THRESHOLD) -> dict:
    """Classify all DjVu text files in the IA corpus directory.

    Returns a dict keyed by file path with ClassificationResult values,
    plus a summary.
    """
    ia_dir = Path(ia_dir)
    files = sorted(ia_dir.rglob("*_djvu.txt"))
    logger.info("Classifying %d IA text files for WA dialect...", len(files))

    results = {}
    wa_count = ea_count = uncertain_count = not_arm_count = 0

    for f in files:
        r = classify_file(f, threshold=threshold)
        results[str(f)] = r

        if not r.is_armenian:
            not_arm_count += 1
        elif r.is_western_armenian:
            wa_count += 1
        elif r.label == "EA":
            ea_count += 1
        else:
            uncertain_count += 1

    logger.info(
        "Classification complete: %d WA, %d EA, %d uncertain, %d not-Armenian "
        "(of %d total files)",
        wa_count, ea_count, uncertain_count, not_arm_count, len(files),
    )
    return {
        "files": results,
        "summary": {
            "total": len(files),
            "wa": wa_count,
            "ea": ea_count,
            "uncertain": uncertain_count,
            "not_armenian": not_arm_count,
        },
    }
