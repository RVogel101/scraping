"""
Armenian Wikisource dump processor.

Downloads and extracts text from hy.wikisource.org database dump.
Contains proofread Armenian literary texts — poetry, novels, essays,
historical documents — in both Western and Eastern Armenian.

Reuses the wikitext cleaning from wiki_processor.

Usage:
    python -m wa_corpus.wikisource_processor [--output-dir DIR]
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import urljoin

import requests

from .wiki_processor import (
    _SKIP_NS,
    _clean_wikitext,
    download_dump,
)

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────

DUMP_BASE_URL = "https://dumps.wikimedia.org/hywikisource/"
DEFAULT_OUTPUT_DIR = Path("wa_corpus/data/wikisource")

# Wikisource-specific markup to strip before standard wiki cleaning
_WIKISOURCE_PATTERNS = [
    # Remove {{header|...}} / {{Վերնագիր|...}} templates
    (re.compile(r"\{\{\s*(?:header|Վերնdelays|Վերdelays)\s*\|[^}]*\}\}", re.I), ""),
    # Remove page-scan references <pages index="..." />
    (re.compile(r"<pages\s[^>]*/>", re.I), ""),
    # Remove page number markers  {{pagenum|...}}
    (re.compile(r"\{\{\s*pagenum\s*\|[^}]*\}\}", re.I), ""),
    # Remove section markers like <section begin=... /> ... <section end=... />
    (re.compile(r"<section\s[^>]*/>", re.I), ""),
    # Remove poem tags (keep content)
    (re.compile(r"</?poem[^>]*>", re.I), ""),
]


def _clean_wikisource_text(text: str) -> str:
    """Clean Wikisource-specific markup, then apply standard wiki cleaning."""
    for pattern, replacement in _WIKISOURCE_PATTERNS:
        text = pattern.sub(replacement, text)
    return _clean_wikitext(text)


# ─── Dump Discovery ──────────────────────────────────────────────────

def find_latest_dump_url() -> str:
    """Find the URL of the latest hy Wikisource articles dump."""
    headers = {"User-Agent": "WACorpusBuilder/1.0 (research project)"}
    resp = requests.get(DUMP_BASE_URL, timeout=30, headers=headers)
    resp.raise_for_status()

    dates = re.findall(r'href="(\d{8})/"', resp.text)
    if not dates:
        raise RuntimeError("No dump dates found at " + DUMP_BASE_URL)

    latest = sorted(dates)[-1]
    logger.info("Latest Wikisource dump date: %s", latest)

    dump_filename = f"hywikisource-{latest}-pages-articles.xml.bz2"
    dump_url = urljoin(DUMP_BASE_URL, f"{latest}/{dump_filename}")

    head = requests.head(dump_url, timeout=30, allow_redirects=True, headers=headers)
    if head.status_code != 200:
        dump_filename = f"hywikisource-{latest}-pages-articles-multistream.xml.bz2"
        dump_url = urljoin(DUMP_BASE_URL, f"{latest}/{dump_filename}")
        head = requests.head(dump_url, timeout=30, allow_redirects=True, headers=headers)
        head.raise_for_status()

    logger.info("Wikisource dump URL: %s (%.1f MB)", dump_url,
                int(head.headers.get("content-length", 0)) / 1e6)
    return dump_url


def extract_wikisource_texts(dump_path: Path) -> list[str]:
    """Extract all article texts from a Wikisource dump.

    Streams the XML dump, applies Wikisource-specific cleanup first,
    then standard wikitext cleaning.
    """
    import bz2
    import xml.etree.ElementTree as ET

    opener = bz2.open if str(dump_path).endswith(".bz2") else open
    texts = []

    with opener(dump_path, "rt", encoding="utf-8", errors="replace") as f:
        article_count = 0
        ns_prefix = ""

        for event, elem in ET.iterparse(f, events=("end",)):
            if not ns_prefix:
                tag = elem.tag
                if tag.startswith("{"):
                    ns_prefix = tag[:tag.index("}") + 1]
                    logger.info("Detected XML namespace: %s", ns_prefix)

            if elem.tag != f"{ns_prefix}page":
                continue

            ns_elem = elem.find(f"{ns_prefix}ns")
            if ns_elem is not None and ns_elem.text in _SKIP_NS:
                elem.clear()
                continue

            rev = elem.find(f"{ns_prefix}revision")
            if rev is None:
                elem.clear()
                continue

            text_elem = rev.find(f"{ns_prefix}text")
            raw_text = text_elem.text if text_elem is not None else ""

            if not raw_text:
                elem.clear()
                continue

            # Wikisource-specific cleanup first, then standard wiki cleanup
            clean = _clean_wikisource_text(raw_text)
            if len(clean) > 50:
                texts.append(clean)
                article_count += 1
                if article_count % 2000 == 0:
                    logger.info("Processed %d articles", article_count)

            elem.clear()

    logger.info("Done: %d Wikisource articles extracted", len(texts))
    return texts


# ─── CLI ──────────────────────────────────────────────────────────────

def main():
    import argparse
    import json

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Process Armenian Wikisource dump")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dump-url", type=str, default=None)
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()

    from .tokenizer import count_frequencies, filter_by_min_length

    if args.skip_download:
        dumps = list(args.output_dir.glob("*.xml.bz2"))
        if not dumps:
            logger.error("No dump file found in %s", args.output_dir)
            return
        dump_path = dumps[-1]
        logger.info("Using existing dump: %s", dump_path)
    else:
        url = args.dump_url or find_latest_dump_url()
        dump_path = download_dump(url, args.output_dir)

    logger.info("Extracting Wikisource articles...")
    texts = extract_wikisource_texts(dump_path)
    logger.info("Extracted %d articles", len(texts))

    logger.info("Counting frequencies...")
    freq = count_frequencies(texts)
    freq = filter_by_min_length(freq, min_len=2)
    logger.info("Found %d unique word forms", len(freq))

    output_file = args.output_dir / "wikisource_frequencies.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(dict(freq.most_common()), f, ensure_ascii=False, indent=2)
    logger.info("Saved frequencies to %s", output_file)

    total_tokens = sum(freq.values())
    print(f"\nArticles:    {len(texts):,}")
    print(f"Tokens:      {total_tokens:,}")
    print(f"Unique forms: {len(freq):,}")

    print(f"\nTop 30:")
    for i, (word, count) in enumerate(freq.most_common(30), 1):
        print(f"  {i:>3}. {word:<20} {count:>8,}")


if __name__ == "__main__":
    main()
