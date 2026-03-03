#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path


def normalize(s: str) -> str:
    s = (s or "").strip().replace("\xa0", " ").lower()
    s = s.replace("&nbsp", "")
    s = s.replace("Õ¥Ö‚", "Ö‡")
    s = unicodedata.normalize("NFC", s)
    s = "".join(
        ch for ch in s
        if unicodedata.category(ch) != "Mn" and not unicodedata.category(ch).startswith("P")
    )
    s = re.sub(r"[()\[\]{}'\"â€œâ€ÕÕšÕ›~`Â«Â»]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def main() -> int:
    report = json.loads(Path("08-data/unmatched_rank_report.json").read_text(encoding="utf-8"))
    unmatched = report.get("sample", [])

    corpus_set = set()
    with open("02-src/wa_corpus/data/wa_frequency_list.csv", "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            w = normalize(row.get("word") or "")
            if w:
                corpus_set.add(w)

    suffixes = ["Õ¶Õ¥Ö€", "Õ¶Õ¥Ö€Õ¨", "Õ¶", "Õ¨", "Õ«Õ¶", "Õ§Õ½", "Õ«Õ½", "Õ¸Ö‚Õ½", "Õ¸Õ¾", "Õ§Õ¶", "Õ¸Ö‚Õ´", "Õ¥Õ¡Õ¬", "Õ¸Ö‚Õ©Õ«Ö‚Õ¶"]

    recoverable = []
    unrecoverable = []
    for item in unmatched:
        w = item["normalized"]
        hit = None
        for suf in suffixes:
            if w.endswith(suf) and len(w) > len(suf) + 2:
                stem = w[: -len(suf)]
                if stem in corpus_set:
                    hit = (suf, stem)
                    break
        if hit:
            recoverable.append({
                "raw": item["raw"],
                "normalized": w,
                "suffix": hit[0],
                "stem": hit[1],
            })
        else:
            unrecoverable.append({
                "raw": item["raw"],
                "normalized": w,
            })

    payload = {
        "total_unmatched_analyzed": len(unmatched),
        "recoverable_suffix_strip": len(recoverable),
        "still_unrecoverable": len(unrecoverable),
        "recoverable_examples": recoverable[:80],
    }
    out_path = Path("08-data/unmatched_fallbacks.json")
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

