#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import sys
import unicodedata
from collections import Counter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, "02-src")
from lousardzag.database import CardDatabase


def normalize(s: str) -> str:
    s = (s or "").strip().replace("\xa0", " ").lower()
    s = s.replace("&nbsp", "")
    s = s.replace("Õ¥Ö‚", "Ö‡")
    s = unicodedata.normalize("NFC", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = re.sub(r"[()\[\]{}'\"â€œâ€ÕÕšÕ›~`Â«Â»]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def reason(raw: str, norm: str) -> str:
    if not norm:
        return "empty-after-normalization"
    if "nbsp" in raw.lower() or "\xa0" in raw:
        return "html-artifact"
    if re.search(r"[A-Za-z]", raw):
        return "latin-mixed-token"
    if re.search(r"[0-9]", raw):
        return "contains-digit"
    if any(ch in raw for ch in ["(", ")", "[", "]", "{", "}"]):
        return "parenthesized-form"
    if any(ch in raw for ch in ["Õ›", "Õš", "Õ", "Â«", "Â»", "'", '"']):
        return "diacritic-or-punct-variant"
    if " " in norm:
        return "multiword"
    return "oov-in-corpus"


def main() -> int:
    db = CardDatabase()
    vocab = db.get_vocabulary_from_cache("Armenian (Western)")

    corpus_set: set[str] = set()
    with open("02-src/wa_corpus/data/wa_frequency_list.csv", "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            w = normalize(row.get("word") or "")
            if w:
                corpus_set.add(w)

    unmatched = []
    for v in vocab:
        raw = v.get("lemma", "")
        norm = normalize(raw)
        if not norm or norm in corpus_set:
            continue
        unmatched.append((raw, norm, reason(raw, norm)))

    counts = Counter(r for _, _, r in unmatched)

    print("=" * 68)
    print("UNMATCHED RANK DIAGNOSTICS")
    print("=" * 68)
    print(f"Total unmatched: {len(unmatched)}")
    print("\nReason breakdown:")
    for k, c in counts.most_common():
        print(f"- {k:28s} {c:4d}")

    print("\nTop unmatched samples:")
    for raw, norm, why in unmatched[:120]:
        print(f"- {raw}  ->  {norm}  [{why}]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

