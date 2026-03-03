#!/usr/bin/env python3
"""Map corpus frequency ranks into cached vocabulary and report distribution."""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, "02-src")

from lousardzag.database import CardDatabase


def _normalize_lemma(value: str) -> str:
    """Normalize Armenian lemma for corpus-vocabulary matching."""
    s = (value or "").strip().replace("\xa0", " ").lower()
    # HTML noise from deck export.
    s = s.replace("&nbsp", "")
    # Normalize old/new Armenian conjunction form for better alignment.
    s = s.replace("Õ¥Ö‚", "Ö‡")
    s = unicodedata.normalize("NFC", s)
    # Remove combining marks and punctuation to collapse token variants.
    s = "".join(
        ch for ch in s
        if unicodedata.category(ch) != "Mn" and not unicodedata.category(ch).startswith("P")
    )
    s = re.sub(r"[()\[\]{}'\"â€œâ€ÕÕšÕ›~`Â«Â»]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _bucket_label(rank: int) -> str:
    if rank <= 100:
        return "1-100"
    if rank <= 500:
        return "101-500"
    if rank <= 1000:
        return "501-1k"
    if rank <= 5000:
        return "1k-5k"
    if rank <= 20000:
        return "5k-20k"
    return ">20k"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Map wa_corpus frequency ranks to vocabulary cache"
    )
    parser.add_argument(
        "--deck",
        default="Armenian (Western)",
        help="Deck name in vocabulary cache",
    )
    parser.add_argument(
        "--frequency-csv",
        default="02-src/wa_corpus/data/wa_frequency_list.csv",
        help="Path to frequency CSV produced by wa_corpus aggregator",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and report only; do not write to DB",
    )
    args = parser.parse_args()

    freq_path = Path(args.frequency_csv)
    if not freq_path.exists():
        print(f"ERROR: frequency CSV not found: {freq_path}")
        return 1

    db = CardDatabase()
    vocab = db.get_vocabulary_from_cache(args.deck)
    if not vocab:
        print(f"ERROR: no cached vocabulary for deck '{args.deck}'")
        return 1

    # Keep original vocabulary lemma(s) by normalized form so we can update exact DB keys.
    lemma_by_norm: dict[str, list[str]] = {}
    for entry in vocab:
        raw = entry.get("lemma", "")
        norm = _normalize_lemma(raw)
        if not norm:
            continue
        lemma_by_norm.setdefault(norm, []).append(raw)

    rank_by_lemma: dict[str, int] = {}
    seen_norm: set[str] = set()

    with freq_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            word = (row.get("word") or "")
            norm_word = _normalize_lemma(word)
            if not norm_word or norm_word not in lemma_by_norm or norm_word in seen_norm:
                continue
            rank_raw = (row.get("rank") or "").strip()
            if not rank_raw.isdigit():
                continue
            rank = int(rank_raw)
            for original_lemma in lemma_by_norm[norm_word]:
                rank_by_lemma[original_lemma] = rank
            seen_norm.add(norm_word)

    if args.dry_run:
        stats = {
            "total_vocab": len(vocab),
            "mapped": len(rank_by_lemma),
            "updated": 0,
            "unmapped": len(vocab) - len(rank_by_lemma),
        }
    else:
        stats = db.update_vocabulary_frequency_ranks(rank_by_lemma, source_deck=args.deck)

    mapped_ranks = sorted(rank_by_lemma.values())

    print("=" * 68)
    print("VOCAB FREQUENCY MAPPING")
    print("=" * 68)
    print(f"Deck: {args.deck}")
    print(f"Vocabulary entries: {stats['total_vocab']}")
    print(f"Mapped to corpus ranks: {stats['mapped']}")
    print(f"Unmapped: {stats['unmapped']}")
    if not args.dry_run:
        print(f"DB rows updated: {stats['updated']}")

    coverage = (100.0 * stats["mapped"] / stats["total_vocab"]) if stats["total_vocab"] else 0.0
    print(f"Coverage: {coverage:.1f}%")

    if mapped_ranks:
        n = len(mapped_ranks)
        p25 = mapped_ranks[n // 4]
        p50 = mapped_ranks[n // 2]
        p75 = mapped_ranks[(3 * n) // 4]
        p90 = mapped_ranks[(9 * n) // 10]
        print("\nRank summary (mapped words):")
        print(f"Min: {mapped_ranks[0]}")
        print(f"25th percentile: {p25}")
        print(f"Median: {p50}")
        print(f"75th percentile: {p75}")
        print(f"90th percentile: {p90}")
        print(f"Max: {mapped_ranks[-1]}")

        bucket_order = ["1-100", "101-500", "501-1k", "1k-5k", "5k-20k", ">20k"]
        bucket_counts = {k: 0 for k in bucket_order}
        for rank in mapped_ranks:
            bucket_counts[_bucket_label(rank)] += 1

        print("\nDistribution by rank bucket:")
        for bucket in bucket_order:
            count = bucket_counts[bucket]
            pct = (100.0 * count / n) if n else 0.0
            print(f"{bucket:>8}: {count:4d} ({pct:5.1f}%)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

