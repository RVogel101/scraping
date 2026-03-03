"""
Western Armenian Corpus Builder — main pipeline runner.

Orchestrates all three data sources and produces the final frequency list.

Usage:
    python -m wa_corpus.build_corpus [--wiki] [--newspapers] [--nayiri] [--all]
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Build Western Armenian frequency corpus",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m wa_corpus.build_corpus --wiki          # Wikipedia only
  python -m wa_corpus.build_corpus --newspapers    # Newspaper articles
  python -m wa_corpus.build_corpus --ia --list-only # Catalog IA items
  python -m wa_corpus.build_corpus --ia             # Download IA OCR text
  python -m wa_corpus.build_corpus --nayiri        # Nayiri dictionary
  python -m wa_corpus.build_corpus --aggregate     # Combine existing data
  python -m wa_corpus.build_corpus --all           # Everything
        """,
    )

    parser.add_argument("--wiki", action="store_true",
                        help="Download and process hyw Wikipedia dump")
    parser.add_argument("--newspapers", type=int, nargs="?", const=50, default=None,
                        help="Scrape WA newspapers (optional: max listing pages, default 50)")
    parser.add_argument("--ia", type=int, nargs="?", const=100, default=None,
                        help="Scrape Internet Archive (optional: max items per query, default 100)")
    parser.add_argument("--ia-images", action="store_true",
                        help="Also download page images from IA (for OCR)")
    parser.add_argument("--list-only", action="store_true",
                        help="(with --ia) Just catalog IA items, don't download")
    parser.add_argument("--nayiri", action="store_true",
                        help="Scrape Nayiri dictionary")
    parser.add_argument("--aggregate", action="store_true",
                        help="Aggregate frequencies from existing data")
    parser.add_argument("--all", action="store_true",
                        help="Run all sources + aggregation")
    parser.add_argument("--output-dir", type=Path, default=Path("wa_corpus/data"))

    args = parser.parse_args()

    # If nothing specified, show help
    if not any([args.wiki, args.newspapers is not None,
                args.ia is not None, args.nayiri,
                args.aggregate, args.all]):
        parser.print_help()
        return

    run_wiki = args.wiki or args.all
    run_newspapers = args.newspapers is not None or args.all
    run_ia = args.ia is not None or args.all
    run_nayiri = args.nayiri or args.all
    run_aggregate = args.aggregate or args.all

    newspaper_pages = args.newspapers if args.newspapers is not None else 50
    ia_max_items = args.ia if args.ia is not None else 100

    # ── Step 1: Wikipedia ─────────────────────────────────────────────
    if run_wiki:
        logger.info("=" * 60)
        logger.info("  Step 1: Western Armenian Wikipedia")
        logger.info("=" * 60)
        from .wiki_processor import (
            download_dump,
            extract_wiki_texts,
            find_latest_dump_url,
        )
        from .tokenizer import count_frequencies, filter_by_min_length
        import json

        wiki_dir = args.output_dir / "wiki"
        wiki_dir.mkdir(parents=True, exist_ok=True)

        url = find_latest_dump_url()
        dump_path = download_dump(url, wiki_dir)

        logger.info("Extracting articles...")
        texts = extract_wiki_texts(dump_path)
        logger.info("Extracted %d articles", len(texts))

        logger.info("Counting frequencies...")
        freq = count_frequencies(texts)
        freq = filter_by_min_length(freq, min_len=2)
        logger.info("Found %d unique word forms", len(freq))

        output_file = wiki_dir / "wiki_frequencies.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(dict(freq.most_common()), f, ensure_ascii=False, indent=2)
        logger.info("Saved to %s", output_file)

    # ── Step 2: Newspapers (Aztag, Horizon) ───────────────────────────
    if run_newspapers:
        logger.info("=" * 60)
        logger.info("  Step 2: WA Newspapers (Aztag Daily, Horizon Weekly)")
        logger.info("=" * 60)
        from .newspaper_scraper import scrape_newspapers

        news_dir = args.output_dir / "newspapers"
        scrape_newspapers(max_listing_pages=newspaper_pages, output_dir=news_dir)

    # ── Step 3: Internet Archive ──────────────────────────────────────
    if run_ia:
        logger.info("=" * 60)
        logger.info("  Step 3: Internet Archive Armenian Texts")
        logger.info("=" * 60)
        from .ia_scraper import scrape_ia

        ia_dir = args.output_dir / "ia"
        scrape_ia(
            max_items=ia_max_items,
            download_images=args.ia_images,
            download_text=not args.list_only,
            list_only=args.list_only,
            output_dir=ia_dir,
        )

    # ── Step 4: Nayiri Dictionary ─────────────────────────────────────
    if run_nayiri:
        logger.info("=" * 60)
        logger.info("  Step 3: Nayiri Dictionary")
        logger.info("=" * 60)
        from .nayiri_scraper import scrape_nayiri

        nayiri_dir = args.output_dir / "nayiri"
        scrape_nayiri(output_dir=nayiri_dir)

    # ── Step 5: Aggregate ─────────────────────────────────────────────
    if run_aggregate:
        logger.info("=" * 60)
        logger.info("  Step 4: Frequency Aggregation")
        logger.info("=" * 60)
        from .frequency_aggregator import (
            aggregate_frequencies,
            load_ia_frequencies,
            load_newspaper_frequencies,
            load_nayiri_headwords,
            load_nayiri_translations,
            load_wiki_frequencies,
            print_summary,
            save_frequency_list,
        )

        wiki_freq = load_wiki_frequencies()
        news_freq = load_newspaper_frequencies()
        ia_freq = load_ia_frequencies()
        nayiri_headwords = load_nayiri_headwords()
        translations = load_nayiri_translations()

        entries = aggregate_frequencies(wiki_freq, news_freq, nayiri_headwords,
                                        ia_freq=ia_freq)
        save_frequency_list(entries, args.output_dir, translations)
        print_summary(entries)

    logger.info("Done!")


if __name__ == "__main__":
    main()
