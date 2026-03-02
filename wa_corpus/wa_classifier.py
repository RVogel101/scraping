"""Western Armenian dialect classifier.

Scores a text document using five weighted signal categories to determine
whether it is Western Armenian (WA), Eastern Armenian (EA), or Classical
Armenian (grabar/krapar).

A document needs a total score >= THRESHOLD (default 5.0) to be classified
as Western Armenian.
"""

import re
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

THRESHOLD = 5.0
MIN_ARMENIAN_RATIO = 0.20

_ARMENIAN_RANGE = re.compile(r'[\u0531-\u0587\uFB13-\uFB17]')

# Signal 1: Classical Orthography Markers
ORTHOGRAPHY_MARKERS = [
    (re.compile(r"իւ"), 3.0, 10, 'իւ digraph'),
    (re.compile(r"ութիւն"), 3.0, 10, '-ութիւն suffix'),
    (re.compile(r"\bմէջ\b"), 2.5, 10, 'մէջ (inside)'),
    (re.compile(r"\wայ\b"), 1.5, 15, 'word-final -այ'),
    (re.compile(r"\wոյ\b"), 2.0, 10, 'word-final -ոյ'),
    (re.compile(r"\Bէ\B"), 1.0, 20, 'word-internal է'),
    (re.compile(r"էան\b"), 2.0, 15, '-էան surname suffix'),
    (re.compile(r"\bեւ\b"), 1.5, 15, 'եւ conjunction'),
]

# Signal 2: WA-Specific Grammar
GRAMMAR_MARKERS = [
    (re.compile(r"կը\s[Ա-ֆ]"), 2.0, 15, 'կը present prefix'),
    (re.compile(r"կ[՚\u2019][Ա-ֆ]"), 2.0, 10, 'կ՚ present prefix'),
    (re.compile(r"պիտի"), 2.0, 10, 'պիտի (future)'),
    (re.compile(r"\bչեմ\b"), 2.0, 10, "չեմ (I don't)"),
    (re.compile(r"\bչես\b"), 1.5, 10, "չես (you don't)"),
    (re.compile(r"\bչենք\b"), 2.0, 10, "չենք (we don't)"),
    (re.compile(r"\bմենք\b"), 2.0, 10, 'մենք (we)'),
    (re.compile(r"\bդուք\b"), 2.0, 10, 'դուք (you-pl)'),
    (re.compile(r"\bինք\b"), 1.5, 10, 'ինք (self)'),
    (re.compile(r"\bկոր\b"), 1.5, 10, 'կոր (there is)'),
]

# Signal 3: WA-Specific Vocabulary
VOCABULARY_MARKERS = [
    (re.compile(r"\bհոն\b"), 3.0, 5, 'հոն (there)'),
    (re.compile(r"\bհոս\b"), 3.0, 5, 'հոս (here)'),
    (re.compile(r"\bջերմակ\b"), 3.0, 5, 'ջերմակ (white)'),
    (re.compile(r"\bմանչուկ"), 3.0, 5, 'մանչուկ (child)'),
    (re.compile(r"խօսի[լԱ-ֆ]"), 2.5, 5, 'խօս- (to speak)'),
    (re.compile(r"երթա[լԱ-ֆ]"), 2.5, 5, 'երթա- (to go)'),
    (re.compile(r"\bընել\b"), 2.5, 5, 'ընել (to do)'),
    (re.compile(r"ուզե[լԱ-ֆ]"), 2.5, 5, 'ուզե- (to want)'),
    (re.compile(r"\bկիրակի\b"), 2.5, 5, 'կիրակի (Sunday)'),
    (re.compile(r"\bխոհանոց\b"), 3.0, 5, 'խոհանոց (kitchen)'),
    (re.compile(r"\bջուր\b"), 2.5, 5, 'ջուր (water)'),
    (re.compile(r"\bշատ\b"), 2.5, 10, 'շատ (very)'),
    (re.compile(r"\bաղուոր\b"), 2.0, 5, 'աղուոր (beautiful)'),
    (re.compile(r"\bմարդիկ\b"), 2.0, 5, 'մարդիկ (people)'),
    (re.compile(r"\bպատիւ\b"), 2.0, 5, 'պատիւ (honour)'),
]

# Signal 4: Known WA Authors (binary)
WA_AUTHORS = {
    'Վարուժան': 5.0,
    'Սիամանթո': 5.0,
    'Տէկէյեան': 4.0,
    'Շահնուր': 4.0,
    'Զոհրապ': 4.0,
    'Զապէլ Եսայեան': 5.0,
    'Ալիշան': 4.0,
    'Օշական': 4.0,
    'Մխիթար': 4.0,
    'Մխիթարեան': 4.0,
    'Անդրանիկ': 4.0,
    'Սարոյեան': 4.0,
    'Սարաֆեան': 4.0,
    'Նալպանտեան': 4.0,
}

# Signal 5: Diaspora Publication Cities (binary)
WA_CITIES = {
    'Պէյրութ': 4.0,
    'Պոլիս': 4.0,
    'Հալէպ': 3.5,
    'Պարիզ': 3.0,
    'Նիւ Յորք': 3.0,
    'Գահիրէ': 3.0,
    'Անթիլիաս': 3.5,
    'Վենետիկ': 3.5,
    'Մարսէյ': 3.0,
    'Կոստանդնուպոլիս': 4.0,
}

# EA / Grabar Negative Markers
EA_MARKERS = [
    (re.compile(r"և"), -2.0, 15, 'և ligature (EA)'),
    (re.compile(r"ություն"), -3.0, 10, '-ություն suffix (EA)'),
    (re.compile(r"յան\b"), -1.0, 15, '-յան suffix (EA)'),
    (re.compile(r"\bնա\b"), -1.0, 10, 'նա pronoun (EA)'),
    (re.compile(r"\bինչպես\b"), -1.0, 10, 'ինչպես (EA how)'),
    (re.compile(r"սովետական"), -3.0, 5, 'սովետական'),
    (re.compile(r"\bզի\b"), -2.0, 5, 'զի (grabar)'),
    (re.compile(r"\bվասն\b"), -2.0, 5, 'վասն (grabar)'),
    (re.compile(r"\bիբրեւ\b"), -2.0, 5, 'իբրեւ (grabar)'),
]


@dataclass
class ClassificationResult:
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
    if not text:
        return 0.0
    arm_count = len(_ARMENIAN_RANGE.findall(text))
    non_ws = sum(1 for c in text if not c.isspace())
    return arm_count / max(non_ws, 1)


def classify_text(text: str, threshold: float = THRESHOLD) -> ClassificationResult:
    result = ClassificationResult()
    result.armenian_ratio = armenian_ratio(text)
    result.is_armenian = result.armenian_ratio >= MIN_ARMENIAN_RATIO

    if not result.is_armenian:
        return result

    signals = {}
    total = 0.0

    for pat, weight, cap, desc in ORTHOGRAPHY_MARKERS:
        hits = min(len(pat.findall(text)), cap)
        if hits:
            contrib = weight * hits
            total += contrib
            signals[desc] = {"hits": hits, "weight": weight, "contrib": contrib}

    for pat, weight, cap, desc in GRAMMAR_MARKERS:
        hits = min(len(pat.findall(text)), cap)
        if hits:
            contrib = weight * hits
            total += contrib
            signals[desc] = {"hits": hits, "weight": weight, "contrib": contrib}

    for pat, weight, cap, desc in VOCABULARY_MARKERS:
        hits = min(len(pat.findall(text)), cap)
        if hits:
            contrib = weight * hits
            total += contrib
            signals[desc] = {"hits": hits, "weight": weight, "contrib": contrib}

    for name, weight in WA_AUTHORS.items():
        if name in text:
            total += weight
            signals[f"author:{name}"] = {"hits": 1, "weight": weight, "contrib": weight}

    for city, weight in WA_CITIES.items():
        if city in text:
            total += weight
            signals[f"city:{city}"] = {"hits": 1, "weight": weight, "contrib": weight}

    for pat, weight, cap, desc in EA_MARKERS:
        hits = min(len(pat.findall(text)), cap)
        if hits:
            contrib = weight * hits
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
    text = path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    return classify_text(text, threshold=threshold)


def classify_ia_corpus(ia_dir: Path | str = "wa_corpus/data/ia",
                       threshold: float = THRESHOLD) -> dict:
    ia_dir = Path(ia_dir)
    files = sorted(ia_dir.rglob("*_djvu.txt"))
    logger.info("Classifying %d IA text files...", len(files))

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
        "Done: %d WA, %d EA, %d uncertain, %d not-Armenian (of %d)",
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
