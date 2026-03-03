"""
Frequency aggregator — combines all Western Armenian corpus sources
into a unified, ranked frequency list.

Merges token counts from:
  - Western Armenian Wikipedia (hyw)
  - Diaspora newspaper articles (Aztag Daily, Horizon Weekly)
  - Internet Archive scanned book OCR text (DjVuTXT)
  - Nayiri dictionary headwords (for validation, not frequency)

Outputs:
  - Ranked frequency JSON (word → rank + count)
  - CSV for easy inspection
  - Validated headword list (words confirmed in Nayiri dictionary)

Usage:
    python -m wa_corpus.frequency_aggregator [--output-dir DIR]
"""

from __future__ import annotations

import csv
import json
import logging
from collections import Counter
from pathlib import Path

from .tokenizer import count_frequencies, filter_by_min_length

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────

DEFAULT_OUTPUT_DIR = Path("wa_corpus/data")
WIKI_FREQ_FILE = Path("wa_corpus/data/wiki/wiki_frequencies.json")
NEWSPAPER_DATA_DIR = Path("wa_corpus/data/newspapers")
IA_DATA_DIR = Path("wa_corpus/data/ia")
NAYIRI_DATA_DIR = Path("wa_corpus/data/nayiri")

# Source weighting: Wikipedia text is encyclopedic (formal),
# Newspaper text is journalistic (closer to daily use). Weight newspapers higher.
# IA books are historical/literary — weight similar to newspapers.
SOURCE_WEIGHTS = {
    "wiki": 1.0,
    "news": 1.5,
    "ia": 1.2,
}

# Minimum corpus appearances to include in final list
MIN_CORPUS_COUNT = 2

# Armenian function words / stopwords to flag (not remove — still useful for frequency)
# These are extremely high-frequency but low learning-value.
# Populated dynamically after first corpus build — the top ~20 most frequent
# function words (articles, conjunctions, prepositions) will be auto-detected.
WA_STOPWORDS: set[str] = set()
# Placeholder — actual stopwords need expert curation from corpus output.
# We keep them in the frequency list but tag them.


# ─── Loading Sources ──────────────────────────────────────────────────

def load_wiki_frequencies() -> Counter[str]:
    """Load Wikipedia frequency counts from pre-processed JSON."""
    if not WIKI_FREQ_FILE.exists():
        logger.warning("Wikipedia frequencies not found at %s", WIKI_FREQ_FILE)
        return Counter()

    with open(WIKI_FREQ_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    logger.info("Loaded %d word forms from Wikipedia", len(data))
    return Counter(data)


def load_newspaper_frequencies() -> Counter[str]:
    """Load newspaper article texts and compute frequencies."""
    articles_file = NEWSPAPER_DATA_DIR / "articles.jsonl"
    if not articles_file.exists():
        logger.warning("Newspaper articles not found at %s", articles_file)
        return Counter()

    texts = []
    with open(articles_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                article = json.loads(line)
                if article.get("text"):
                    texts.append(article["text"])

    if not texts:
        return Counter()

    freq = count_frequencies(texts)
    freq = filter_by_min_length(freq, min_len=2)
    logger.info("Computed %d word forms from %d newspaper articles",
                len(freq), len(texts))
    return freq

def load_ia_frequencies() -> Counter[str]:
    """Load Internet Archive OCR text and compute frequencies."""
    if not IA_DATA_DIR.exists():
        logger.warning("IA data directory not found at %s", IA_DATA_DIR)
        return Counter()

    texts = []
    for txt_path in IA_DATA_DIR.rglob("*_djvu.txt"):
        try:
            text = txt_path.read_text(encoding="utf-8", errors="replace")
            if text.strip():
                texts.append(text)
        except Exception as e:
            logger.warning("Failed to read %s: %s", txt_path, e)

    if not texts:
        return Counter()

    freq = count_frequencies(texts)
    freq = filter_by_min_length(freq, min_len=2)
    logger.info("Computed %d word forms from %d IA text files",
                len(freq), len(texts))
    return freq


def load_nayiri_headwords() -> set[str]:
    """Load Nayiri dictionary headwords for validation."""
    dict_file = NAYIRI_DATA_DIR / "dictionary_full.json"
    if dict_file.exists():
        with open(dict_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        headwords = set(data.keys())
        logger.info("Loaded %d Nayiri headwords", len(headwords))
        return headwords

    # Fallback: JSONL checkpoint
    jsonl_file = NAYIRI_DATA_DIR / "dictionary.jsonl"
    if jsonl_file.exists():
        headwords = set()
        with open(jsonl_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entry = json.loads(line)
                    hw = entry.get("headword", "")
                    if hw:
                        headwords.add(hw)
        logger.info("Loaded %d Nayiri headwords from checkpoint", len(headwords))
        return headwords

    logger.warning("No Nayiri dictionary data found")
    return set()


def load_nayiri_translations() -> dict[str, str]:
    """Load Armenian → English translations from Nayiri data."""
    dict_file = NAYIRI_DATA_DIR / "dictionary_full.json"
    if not dict_file.exists():
        dict_file = NAYIRI_DATA_DIR / "dictionary_enriched.json"
    if not dict_file.exists():
        return {}

    with open(dict_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    translations = {}
    for hw, entry in data.items():
        eng = entry.get("english", "")
        if eng:
            translations[hw] = eng

    logger.info("Loaded %d Armenian-English translations", len(translations))
    return translations


# ─── Aggregation ──────────────────────────────────────────────────────

def aggregate_frequencies(
    wiki_freq: Counter[str],
    news_freq: Counter[str],
    nayiri_headwords: set[str],
    ia_freq: Counter[str] | None = None,
    min_count: int = MIN_CORPUS_COUNT,
) -> list[dict]:
    """Merge frequency counts from all sources into a ranked list.

    Each entry contains:
      - word: the Armenian word form
      - rank: 1-based frequency rank
      - total_count: weighted total count across sources
      - wiki_count: raw count from Wikipedia
      - news_count: raw count from newspapers
      - ia_count: raw count from Internet Archive texts
      - in_nayiri: whether the word appears in Nayiri dictionary
      - sources: number of sources the word appears in

    Returns list sorted by total_count descending.
    """
    if ia_freq is None:
        ia_freq = Counter()

    # Combine all known words
    all_words = set(wiki_freq.keys()) | set(news_freq.keys()) | set(ia_freq.keys())
    logger.info("Total unique word forms across sources: %d", len(all_words))

    entries: list[dict] = []

    for word in all_words:
        wiki_count = wiki_freq.get(word, 0)
        news_count = news_freq.get(word, 0)
        ia_count = ia_freq.get(word, 0)

        # Weighted total
        weighted = (wiki_count * SOURCE_WEIGHTS["wiki"]
                    + news_count * SOURCE_WEIGHTS["news"]
                    + ia_count * SOURCE_WEIGHTS["ia"])

        # Source count
        sources = sum(1 for c in [wiki_count, news_count, ia_count] if c > 0)

        # Skip very rare words unless they're in Nayiri
        raw_total = wiki_count + news_count + ia_count
        in_nayiri = word in nayiri_headwords
        if raw_total < min_count and not in_nayiri:
            continue

        entries.append({
            "word": word,
            "total_count": round(weighted, 1),
            "wiki_count": wiki_count,
            "news_count": news_count,
            "ia_count": ia_count,
            "in_nayiri": in_nayiri,
            "sources": sources,
        })

    # Sort by weighted total descending
    entries.sort(key=lambda e: (-e["total_count"], -e["sources"], e["word"]))

    # Assign ranks
    for rank, entry in enumerate(entries, 1):
        entry["rank"] = rank

    logger.info("Final ranked list: %d entries (min_count=%d)", len(entries), min_count)
    return entries


# ─── Output ───────────────────────────────────────────────────────────

def save_frequency_list(
    entries: list[dict],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    translations: dict[str, str] | None = None,
) -> tuple[Path, Path]:
    """Save the frequency list as both JSON and CSV.

    Returns (json_path, csv_path).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Enrich with translations if available
    if translations:
        for entry in entries:
            eng = translations.get(entry["word"], "")
            if eng:
                entry["english"] = eng

    # JSON
    json_path = output_dir / "wa_frequency_list.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    # CSV
    csv_path = output_dir / "wa_frequency_list.csv"
    fieldnames = ["rank", "word", "english", "total_count", "wiki_count",
                  "news_count", "ia_count", "in_nayiri", "sources"]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(entries)

    logger.info("Saved frequency list: %s, %s", json_path, csv_path)
    return json_path, csv_path


def print_summary(entries: list[dict]) -> None:
    """Print a summary of the frequency list."""
    total_tokens = sum(e["wiki_count"] + e["news_count"] + e.get("ia_count", 0) for e in entries)
    in_nayiri = sum(1 for e in entries if e["in_nayiri"])
    multi_source = sum(1 for e in entries if e["sources"] > 1)

    print(f"\n{'═' * 60}")
    print(f"  Western Armenian Frequency List — Summary")
    print(f"{'═' * 60}")
    print(f"  Total word forms:      {len(entries):>10,}")
    print(f"  Total corpus tokens:   {total_tokens:>10,}")
    print(f"  In Nayiri dictionary:  {in_nayiri:>10,}")
    print(f"  Multi-source words:    {multi_source:>10,}")
    print(f"{'─' * 60}")
    print(f"  Top 30 words:")
    print(f"{'─' * 60}")
    for e in entries[:30]:
        nayiri_mark = "✓" if e["in_nayiri"] else " "
        eng = e.get("english", "")[:25]
        print(f"  {e['rank']:>4}. {e['word']:<20} {e['total_count']:>10,.0f}"
              f"  [{nayiri_mark}] {eng}")
    print(f"{'═' * 60}")


# ─── CLI ──────────────────────────────────────────────────────────────

def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Aggregate WA frequency lists")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--min-count", type=int, default=MIN_CORPUS_COUNT)
    args = parser.parse_args()

    # Load all sources
    wiki_freq = load_wiki_frequencies()
    news_freq = load_newspaper_frequencies()
    ia_freq = load_ia_frequencies()
    nayiri_headwords = load_nayiri_headwords()
    translations = load_nayiri_translations()

    # Aggregate
    entries = aggregate_frequencies(
        wiki_freq, news_freq, nayiri_headwords,
        ia_freq=ia_freq,
        min_count=args.min_count,
    )

    # Save
    save_frequency_list(entries, args.output_dir, translations)
    print_summary(entries)


if __name__ == "__main__":
    main()
