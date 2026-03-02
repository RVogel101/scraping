"""
Western Armenian Wikipedia dump processor.

Downloads and extracts text from the hyw.wikipedia.org database dump,
producing clean Armenian text for frequency analysis.

Usage:
    python -m wa_corpus.wiki_processor [--output-dir DIR] [--dump-date YYYYMMDD]
"""

from __future__ import annotations

import bz2
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────

DUMP_BASE_URL = "https://dumps.wikimedia.org/hywwiki/"
DEFAULT_OUTPUT_DIR = Path("wa_corpus/data/wiki")

# Namespace prefixes to skip (talk pages, user pages, etc.)
_SKIP_NS = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11",
            "12", "13", "14", "15", "100", "101", "118", "119", "710", "711",
            "828", "829", "2300", "2301", "2302", "2303"}

# Wikitext cleanup patterns
_WIKI_MARKUP = [
    # Remove templates {{ ... }}  (greedy, handles most cases)
    (re.compile(r"\{\{[^}]*\}\}"), ""),
    # Remove [[ File: ... ]], [[ Image: ... ]], [[ Պատկեր: ... ]]
    (re.compile(r"\[\[\s*(?:File|Image|Պատկեր|Файл)\s*:[^\]]*\]\]", re.I), ""),
    # Remove categories [[ Կատեգորիա: ... ]]
    (re.compile(r"\[\[\s*(?:Category|Կատեգորիա)\s*:[^\]]*\]\]", re.I), ""),
    # Convert [[link|display]] → display
    (re.compile(r"\[\[[^\]|]*\|([^\]]*)\]\]"), r"\1"),
    # Convert [[link]] → link
    (re.compile(r"\[\[([^\]]*)\]\]"), r"\1"),
    # Remove external links [http://...]
    (re.compile(r"\[https?://[^\]]*\]"), ""),
    # Remove HTML tags
    (re.compile(r"<[^>]+>"), ""),
    # Remove ref tags and contents
    (re.compile(r"<ref[^>]*>.*?</ref>", re.DOTALL), ""),
    (re.compile(r"<ref[^>]*/>"), ""),
    # Remove headings markup (== ... ==)
    (re.compile(r"={2,}([^=]+)={2,}"), r"\1"),
    # Remove bold/italic markup
    (re.compile(r"'{2,5}"), ""),
    # Remove list markers
    (re.compile(r"^[*#:;]+\s*", re.MULTILINE), ""),
    # Remove table markup
    (re.compile(r"\{\|.*?\|\}", re.DOTALL), ""),
    # Collapse whitespace
    (re.compile(r"\s+"), " "),
]

# Redirect pattern
_REDIRECT_RE = re.compile(r"#(?:REDIRECT|Վերաըառաջնորդում)", re.I)


def _clean_wikitext(text: str) -> str:
    """Strip wikitext markup, returning plain text."""
    # Quick check for redirects
    if _REDIRECT_RE.match(text.strip()):
        return ""

    for pattern, replacement in _WIKI_MARKUP:
        text = pattern.sub(replacement, text)

    return text.strip()


# ─── Dump Discovery ──────────────────────────────────────────────────

def find_latest_dump_url() -> str:
    """Find the URL of the latest hyw Wikipedia articles dump.

    Returns the URL for the articles XML dump file (bz2 compressed).
    """
    # List available dumps
    resp = requests.get(DUMP_BASE_URL, timeout=30)
    resp.raise_for_status()

    # Parse dates from directory listing
    dates = re.findall(r'href="(\d{8})/"', resp.text)
    if not dates:
        raise RuntimeError("No dump dates found at " + DUMP_BASE_URL)

    latest = sorted(dates)[-1]
    logger.info("Latest dump date: %s", latest)

    # The articles dump filename pattern
    dump_filename = f"hywwiki-{latest}-pages-articles.xml.bz2"
    dump_url = urljoin(DUMP_BASE_URL, f"{latest}/{dump_filename}")

    # Verify it exists
    head = requests.head(dump_url, timeout=30, allow_redirects=True)
    if head.status_code != 200:
        # Try multistream variant
        dump_filename = f"hywwiki-{latest}-pages-articles-multistream.xml.bz2"
        dump_url = urljoin(DUMP_BASE_URL, f"{latest}/{dump_filename}")
        head = requests.head(dump_url, timeout=30, allow_redirects=True)
        head.raise_for_status()

    logger.info("Dump URL: %s (%.1f MB)", dump_url,
                int(head.headers.get("content-length", 0)) / 1e6)
    return dump_url


def download_dump(url: str, output_dir: Path = DEFAULT_OUTPUT_DIR) -> Path:
    """Download the Wikipedia dump file with progress reporting.

    Returns the path to the downloaded .bz2 file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = url.rsplit("/", 1)[-1]
    output_path = output_dir / filename

    if output_path.exists():
        logger.info("Dump already downloaded: %s", output_path)
        return output_path

    logger.info("Downloading %s ...", url)
    resp = requests.get(url, stream=True, timeout=300)
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    downloaded = 0

    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 256):
            f.write(chunk)
            downloaded += len(chunk)
            if total > 0 and downloaded % (5 * 1024 * 1024) < 1024 * 256:
                pct = 100 * downloaded / total
                logger.info("  %.1f%% (%.1f / %.1f MB)", pct,
                            downloaded / 1e6, total / 1e6)

    logger.info("Download complete: %s (%.1f MB)", output_path,
                output_path.stat().st_size / 1e6)
    return output_path


# ─── XML Parsing ──────────────────────────────────────────────────────

def iter_articles(dump_path: Path) -> Iterator[tuple[str, str]]:
    """Iterate over (title, cleaned_text) pairs from a Wikipedia XML dump.

    Handles bz2-compressed files. Skips non-article namespaces and redirects.
    Auto-detects the MediaWiki XML namespace version.
    """
    opener = bz2.open if str(dump_path).endswith(".bz2") else open

    # Use iterparse for memory efficiency on large dumps
    with opener(dump_path, "rt", encoding="utf-8", errors="replace") as f:
        page_count = 0
        article_count = 0
        ns_prefix = ""  # will be detected from first element

        for event, elem in ET.iterparse(f, events=("end",)):
            # Auto-detect namespace from the first element we see
            if not ns_prefix:
                tag = elem.tag
                if tag.startswith("{"):
                    ns_prefix = tag[:tag.index("}") + 1]
                    logger.info("Detected XML namespace: %s", ns_prefix)

            if elem.tag != f"{ns_prefix}page":
                continue

            page_count += 1

            # Check namespace
            ns_elem = elem.find(f"{ns_prefix}ns")
            if ns_elem is not None and ns_elem.text in _SKIP_NS:
                elem.clear()
                continue

            # Get title
            title_elem = elem.find(f"{ns_prefix}title")
            title = title_elem.text if title_elem is not None else ""

            # Get latest revision text
            rev = elem.find(f"{ns_prefix}revision")
            if rev is None:
                elem.clear()
                continue

            text_elem = rev.find(f"{ns_prefix}text")
            raw_text = text_elem.text if text_elem is not None else ""

            if not raw_text:
                elem.clear()
                continue

            # Clean and yield
            clean = _clean_wikitext(raw_text)
            if len(clean) > 50:  # skip stubs
                article_count += 1
                yield title, clean

                if article_count % 1000 == 0:
                    logger.info("Processed %d articles (%d pages scanned)",
                                article_count, page_count)

            # Free memory
            elem.clear()

        logger.info("Done: %d articles from %d pages", article_count, page_count)


def extract_wiki_texts(dump_path: Path) -> list[str]:
    """Extract all article texts from a dump file. Returns list of clean texts."""
    return [text for _title, text in iter_articles(dump_path)]


# ─── CLI ──────────────────────────────────────────────────────────────

def main():
    """Download and process the latest hyw Wikipedia dump."""
    import argparse
    import json

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Process Western Armenian Wikipedia dump")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dump-url", type=str, default=None,
                        help="Direct URL to dump file (skips auto-discovery)")
    parser.add_argument("--skip-download", action="store_true",
                        help="Skip download, use existing dump file")
    args = parser.parse_args()

    from .tokenizer import count_frequencies, filter_by_min_length

    # Download
    if args.skip_download:
        # Find existing dump
        dumps = list(args.output_dir.glob("*.xml.bz2"))
        if not dumps:
            logger.error("No dump file found in %s", args.output_dir)
            return
        dump_path = dumps[-1]
        logger.info("Using existing dump: %s", dump_path)
    else:
        url = args.dump_url or find_latest_dump_url()
        dump_path = download_dump(url, args.output_dir)

    # Extract and count
    logger.info("Extracting articles...")
    texts = extract_wiki_texts(dump_path)
    logger.info("Extracted %d articles", len(texts))

    logger.info("Counting frequencies...")
    freq = count_frequencies(texts)
    freq = filter_by_min_length(freq, min_len=2)
    logger.info("Found %d unique word forms", len(freq))

    # Save frequency list
    output_file = args.output_dir / "wiki_frequencies.json"
    freq_sorted = dict(freq.most_common())
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(freq_sorted, f, ensure_ascii=False, indent=2)
    logger.info("Saved frequencies to %s", output_file)

    # Print top 50
    print(f"\n{'═' * 50}")
    print(f"  Top 50 Western Armenian words (Wikipedia)")
    print(f"{'═' * 50}")
    for i, (word, count) in enumerate(freq.most_common(50), 1):
        print(f"  {i:>3}. {word:<20} {count:>8,}")
    print(f"{'═' * 50}")
    print(f"  Total tokens: {sum(freq.values()):,}")
    print(f"  Unique forms: {len(freq):,}")


if __name__ == "__main__":
    main()
