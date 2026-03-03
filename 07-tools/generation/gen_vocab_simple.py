#!/usr/bin/env python3
"""Vocabulary-only ordering tool with configurable ordering and batch policies."""

import argparse
import csv
import math
import re
import unicodedata
from pathlib import Path

import sys
sys.path.insert(0, "02-src")

from lousardzag.database import CardDatabase
from lousardzag.morphology.difficulty import count_syllables_with_context
from lousardzag.phonetics import get_pronunciation_guide, calculate_phonetic_difficulty


PRESETS = {
    # Conservative starter: keep very frequent words, noun-heavy, fixed small batches.
    "l1-core": {
        "max_rank": 2000,
        "order_mode": "difficulty_band",
        "include_pos": "noun,verb",
        "exclude_pos": "unknown,other",
        "band_cutoffs": "100,500,1200,2000",
        "batch_strategy": "fixed",
        "batch_size": 18,
        "batch_step": 0,
        "batch_max_size": 18,
        "proficiency_enabled": False,
    },
    # Expand scope: include adjectives/adverbs, still controlled with moderate growth.
    "l2-expand": {
        "max_rank": 8000,
        "order_mode": "band_pos_frequency",
        "include_pos": "noun,verb,adjective,adverb",
        "exclude_pos": "unknown,other",
        "band_cutoffs": "100,500,2000,5000,8000",
        "batch_strategy": "growth",
        "batch_size": 20,
        "batch_step": 4,
        "batch_max_size": 32,
        "proficiency_enabled": False,
    },
    # Bridge to wider lexicon: allow unknown/other, larger growth batches.
    "l3-bridge": {
        "max_rank": 20000,
        "order_mode": "band_pos_frequency",
        "include_pos": "",
        "exclude_pos": "",
        "band_cutoffs": "100,500,2000,10000,20000",
        "batch_strategy": "growth",
        "batch_size": 24,
        "batch_step": 6,
        "batch_max_size": 44,
        "proficiency_enabled": False,
    },
    # Standards-style progression split: N3 -> N2 -> N1 -> Fluent (7 total blocks).
    "n-standard": {
        "max_rank": 30000,
        "order_mode": "difficulty_band",
        "include_pos": "",
        "exclude_pos": "",
        "band_cutoffs": "100,500,2000,10000,30000",
        "batch_strategy": "growth",
        "batch_size": 24,
        "batch_step": 5,
        "batch_max_size": 42,
        "proficiency_enabled": True,
        "proficiency_labels": "N1,N2,N3,N4,N5,N6,N7",
    },
}


DEFAULT_PROFICIENCY_LABELS = "N1,N2,N3,N4,N5,N6,N7"


def normalize_lemma(value):
    """Normalize Armenian lemma for joining frequency and DB metadata."""
    s = (value or "").strip().replace("\xa0", " ").lower()
    s = s.replace("&nbsp", "")
    s = s.replace("եւ", "և")
    s = unicodedata.normalize("NFC", s)
    s = "".join(
        ch for ch in s
        if unicodedata.category(ch) != "Mn" and not unicodedata.category(ch).startswith("P")
    )
    s = re.sub(r"[()\[\]{}'\"“”՝՚՛~`«»]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_csv_list(value):
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_int_list(value):
    return [int(x.strip()) for x in value.split(",") if x.strip()]


def band_index_for_rank(rank, cutoffs):
    for i, cutoff in enumerate(cutoffs):
        if rank <= cutoff:
            return i
    return len(cutoffs)


def band_label(rank, cutoffs):
    if not cutoffs:
        return "all"
    prev = 1
    for cutoff in cutoffs:
        if rank <= cutoff:
            return f"{prev}-{cutoff}"
        prev = cutoff + 1
    return f">{cutoffs[-1]}"


def difficulty_score(rank, syllables, pos, cutoffs):
    """Lower is easier. Mixes syllables + POS + frequency bucket."""
    bidx = band_index_for_rank(rank, cutoffs)
    pos_penalty = {
        "noun": 0.2,
        "verb": 0.5,
        "adjective": 0.35,
        "adverb": 0.35,
        "unknown": 0.45,
        "other": 0.45,
    }.get(pos, 0.45)
    syl_component = min(max(syllables, 0), 6) * 0.9
    freq_component = bidx * 0.8
    return round(syl_component + pos_penalty + freq_component, 2)


def load_db_metadata(deck_name):
    db = CardDatabase()
    rows = db.get_vocabulary_from_cache(deck_name)
    by_norm = {}
    for row in rows:
        lemma = row.get("lemma", "")
        norm = normalize_lemma(lemma)
        if not norm:
            continue
        by_norm[norm] = {
            "pos": (row.get("pos") or "unknown").strip().lower() or "unknown",
            "translation": (row.get("translation") or "").strip(),
            "db_frequency_rank": int(row.get("frequency_rank") or 9999),
        }
    return by_norm


def is_sentence_translation(translation):
    """Check if a translation looks like a sentence rather than a definition."""
    if not translation or translation == "[No definition]":
        return False
    # Skip entries with question marks (sentence cards)
    if '?' in translation:
        return True
    # Skip entries with many words (likely sentences or long phrases)
    word_count = len(translation.split())
    if word_count > 4:
        return True
    # Skip entries starting with pronouns/sentence starters
    lower_trans = translation.lower()
    sentence_starters = ['i ', 'me ', 'we ', 'he ', 'she ', 'they ', 'you ', 'it ', 'this ', 'that ',
                         'what ', 'where ', 'how ', 'when ', 'why ', 'who ', 'there ']
    if any(lower_trans.startswith(s) for s in sentence_starters):
        return True
    return False


def load_vocab(max_words, max_rank, deck_name, cutoffs):
    """Load frequency list and enrich with DB POS and computed difficulty."""
    metadata = load_db_metadata(deck_name)
    vocab_list = []
    skipped_sentences = 0

    with open("02-src/wa_corpus/data/wa_frequency_list.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                rank = int((row.get("rank") or "0").strip())
            except ValueError:
                continue

            if max_rank and rank > max_rank:
                continue

            word = (row.get("word") or "").strip()
            if not word:
                continue

            norm = normalize_lemma(word)
            meta = metadata.get(norm, {})
            # Prefer database translation over CSV english field
            english = meta.get("translation", "").strip() or (row.get("english") or "").strip() or "[No definition]"
            
            # Skip sentence cards (long translations, questions, etc.)
            if is_sentence_translation(english):
                skipped_sentences += 1
                continue
            
            pos = meta.get("pos", "unknown")
            if pos not in ("noun", "verb", "adjective", "adverb", "unknown"):
                pos = "other"

            syllables = count_syllables_with_context(word, with_epenthesis=True)
            band = band_label(rank, cutoffs)
            diff = difficulty_score(rank, syllables, pos, cutoffs)
            phonetic_diff = calculate_phonetic_difficulty(word)
            pronunciation = get_pronunciation_guide(word)

            vocab_list.append({
                "rank": rank,
                "word": word,
                "english": english,
                "pos": pos,
                "syllables": syllables,
                "band": band,
                "difficulty": diff,
                "phonetic_difficulty": phonetic_diff,
                "pronunciation": pronunciation,
            })

            if max_words and len(vocab_list) >= max_words * 6:
                break

    if skipped_sentences > 0:
        print(f"Filtered out {skipped_sentences} sentence/phrase cards")
    return vocab_list


def apply_pos_filters(vocab_list, include_pos, exclude_pos):
    include_set = set(include_pos) if include_pos else None
    exclude_set = set(exclude_pos)
    out = []
    for item in vocab_list:
        pos = item["pos"]
        if include_set is not None and pos not in include_set:
            continue
        if pos in exclude_set:
            continue
        out.append(item)
    return out


def order_vocab(vocab_list, order_mode, pos_order, cutoffs):
    pos_index = {pos: i for i, pos in enumerate(pos_order)}

    def pos_key(item):
        return pos_index.get(item["pos"], len(pos_index))

    def band_key(item):
        return band_index_for_rank(item["rank"], cutoffs)

    if order_mode == "frequency":
        key_fn = lambda x: (x["rank"],)
    elif order_mode == "pos_frequency":
        key_fn = lambda x: (pos_key(x), x["rank"])
    elif order_mode == "band_pos_frequency":
        key_fn = lambda x: (band_key(x), pos_key(x), x["rank"])
    elif order_mode == "difficulty":
        key_fn = lambda x: (x["difficulty"], x["rank"])
    elif order_mode == "difficulty_band":
        key_fn = lambda x: (x["difficulty"], band_key(x), x["rank"])
    else:
        key_fn = lambda x: (x["rank"],)

    return sorted(vocab_list, key=key_fn)


def assign_batches(vocab_list, strategy, batch_size, batch_step, batch_max_size, cutoffs):
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")

    if strategy == "fixed":
        for i, item in enumerate(vocab_list):
            item["batch"] = (i // batch_size) + 1
        return

    if strategy == "growth":
        batch = 1
        cursor = 0
        index = 0
        while index < len(vocab_list):
            target = min(batch_max_size, batch_size + cursor * batch_step)
            if target <= 0:
                target = batch_size
            next_index = min(len(vocab_list), index + target)
            for i in range(index, next_index):
                vocab_list[i]["batch"] = batch
            index = next_index
            batch += 1
            cursor += 1
        return

    if strategy == "banded":
        groups = {}
        for item in vocab_list:
            bidx = band_index_for_rank(item["rank"], cutoffs)
            groups.setdefault(bidx, []).append(item)

        global_batch = 1
        for bidx in sorted(groups.keys()):
            group = groups[bidx]
            for i, item in enumerate(group):
                item["batch"] = global_batch + (i // batch_size)
            global_batch = max(x["batch"] for x in group) + 1
        return

    raise ValueError(f"Unknown batch strategy: {strategy}")


def assign_proficiency_blocks(vocab_list, labels):
    """Assign contiguous proficiency blocks across ordered vocabulary list."""
    if not labels:
        for item in vocab_list:
            item["proficiency_block"] = ""
            item["proficiency_label"] = ""
        return

    n = len(vocab_list)
    block_count = len(labels)
    for idx, item in enumerate(vocab_list):
        block_idx = int(idx * block_count / n) if n else 0
        if block_idx >= block_count:
            block_idx = block_count - 1
        item["proficiency_block"] = block_idx + 1
        item["proficiency_label"] = labels[block_idx]


def apply_preset(args):
    """Apply a named rollout preset to ordering and batching settings."""
    if args.preset == "custom":
        return []

    preset = PRESETS[args.preset]
    changed = []
    for key, value in preset.items():
        setattr(args, key, value)
        changed.append((key, value))
    return changed


def make_html(vocab_list, settings):
    rows = []
    for item in vocab_list:
        pronunciation = item.get("pronunciation", {})
        rows.append(
            "                <tr>"
            f"<td class='pblock'>{item.get('proficiency_block', '')}</td>"
            f"<td>{item.get('proficiency_label', '')}</td>"
            f"<td class='batch'>{item['batch']}</td>"
            f"<td class='rank'>{item['rank']}</td>"
            f"<td class='word'>{item['word']}</td>"
            f"<td>{item['english']}</td>"
            f"<td>{item['pos']}</td>"
            f"<td>{item['syllables']}</td>"
            f"<td>{item['band']}</td>"
            f"<td>{item['difficulty']:.2f}</td>"
            f"<td class='ipa'>{pronunciation.get('ipa', '')}</td>"
            f"<td>{pronunciation.get('english_approx', '')}</td>"
            f"<td>{item.get('phonetic_difficulty', ''):.2f}</td>"
            "</tr>"
        )
    rows_html = "\n".join(rows)

    return f"""<!DOCTYPE html>
<html lang='en'>
<head>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1.0'>
    <title>Vocabulary Ordering Preview</title>
    <style>
        body {{ font-family: Segoe UI, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1500px; margin: 0 auto; background: white; padding: 24px; border-radius: 8px; }}
        h1 {{ margin-top: 0; }}
        .info {{ color: #555; font-size: 14px; margin-bottom: 16px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ background: #1565C0; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        tr:nth-child(even) {{ background: #fafafa; }}
        .batch {{ text-align: center; font-weight: 600; }}
        .pblock {{ text-align: center; font-weight: 600; }}
        .rank {{ text-align: center; }}
        .ipa {{ font-family: 'Arial Unicode MS', sans-serif; font-style: italic; color: #666; }}
        .word {{ direction: rtl; text-align: right; font-size: 18px; }}
        .note {{ margin-top: 16px; font-size: 13px; color: #666; }}
    </style>
</head>
<body>
    <div class='container'>
        <h1>Vocabulary Ordering (No Sentences)</h1>
        <div class='info'>
            <p>Total: {len(vocab_list)} | Order: {settings['order_mode']} | Batch strategy: {settings['batch_strategy']}</p>
            <p>Batch size settings: base={settings['batch_size']}, step={settings['batch_step']}, max={settings['batch_max_size']}</p>
            <p>Proficiency blocks: {settings['proficiency_summary']}</p>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Std Block</th>
                    <th>Std Label</th>
                    <th>Batch</th>
                    <th>Rank</th>
                    <th>Word</th>
                    <th>Definition</th>
                    <th>POS</th>
                    <th>Syl</th>
                    <th>Band</th>
                    <th>Difficulty</th>
                    <th>IPA</th>
                    <th>English Approx</th>
                    <th>Phonetic Diff</th>
                </tr>
            </thead>
            <tbody>
{rows_html}
            </tbody>
        </table>
        <div class='note'>
            Vocabulary-only pipeline. Sentence generation should consume this ordered list as a separate step.
        </div>
    </div>
</body>
</html>"""


def print_batch_summary(vocab_list, preview_batches):
    stats = {}
    for item in vocab_list:
        b = item["batch"]
        stats.setdefault(b, {
            "count": 0,
            "min_rank": math.inf,
            "max_rank": 0,
            "avg_difficulty": 0.0,
        })
        bucket = stats[b]
        bucket["count"] += 1
        bucket["min_rank"] = min(bucket["min_rank"], item["rank"])
        bucket["max_rank"] = max(bucket["max_rank"], item["rank"])
        bucket["avg_difficulty"] += item["difficulty"]

    print("\nBatch summary:")
    shown = 0
    for b in sorted(stats.keys()):
        bucket = stats[b]
        avg_diff = bucket["avg_difficulty"] / bucket["count"]
        print(
            f"  Batch {b:2d}: {bucket['count']:3d} words | "
            f"rank {bucket['min_rank']}-{bucket['max_rank']} | "
            f"avg diff {avg_diff:.2f}"
        )
        shown += 1
        if preview_batches and shown >= preview_batches:
            break


def main():
    parser = argparse.ArgumentParser(description="Generate vocabulary-only ordered lists with batch policies")
    parser.add_argument("--preset", default="custom", choices=["custom", "l1-core", "l2-expand", "l3-bridge", "n-standard"],
                        help="Apply a production ordering/batching preset")
    parser.add_argument("--max-words", type=int, default=80, help="Final number of words to output")
    parser.add_argument("--max-rank", type=int, default=0, help="Optional max frequency rank cutoff (0=off)")
    parser.add_argument("--deck", default="Armenian (Western)", help="Deck name for POS metadata")
    parser.add_argument("--order-mode", default="frequency", choices=[
        "frequency", "pos_frequency", "band_pos_frequency", "difficulty", "difficulty_band"
    ], help="Word ordering strategy")
    parser.add_argument("--pos-order", default="noun,verb,adjective,adverb,other,unknown",
                        help="POS order for pos-based modes")
    parser.add_argument("--include-pos", default="", help="Comma list of POS to keep")
    parser.add_argument("--exclude-pos", default="", help="Comma list of POS to remove")
    parser.add_argument("--band-cutoffs", default="100,500,2000,10000", help="Frequency band rank cutoffs")

    parser.add_argument("--batch-strategy", default="fixed", choices=["fixed", "growth", "banded"],
                        help="Batch sizing strategy")
    parser.add_argument("--batch-size", type=int, default=20, help="Base batch size")
    parser.add_argument("--batch-step", type=int, default=4, help="Growth step for growth strategy")
    parser.add_argument("--batch-max-size", type=int, default=40, help="Max batch size for growth strategy")
    parser.add_argument("--preview-batches", type=int, default=8, help="How many batch summaries to print")

    parser.add_argument("--proficiency-enabled", action="store_true",
                        help="Enable standards-style block labels (N3/N2/N1/Fluent)")
    parser.add_argument(
        "--proficiency-labels",
        default=DEFAULT_PROFICIENCY_LABELS,
        help="Comma-separated proficiency block labels (last label should be fluent)",
    )

    parser.add_argument("--output", default="08-data/vocabulary_preview.html", help="Output HTML file")
    parser.add_argument("--csv-output", default=None, help="Optional CSV export")
    args = parser.parse_args()

    preset_changes = apply_preset(args)
    if preset_changes:
        print(f"Using preset: {args.preset}")
        for key, value in preset_changes:
            print(f"  {key}={value}")

    cutoffs = parse_int_list(args.band_cutoffs)
    pos_order = [p.lower() for p in parse_csv_list(args.pos_order)]
    include_pos = [p.lower() for p in parse_csv_list(args.include_pos)]
    exclude_pos = [p.lower() for p in parse_csv_list(args.exclude_pos)]
    proficiency_labels = parse_csv_list(args.proficiency_labels)

    print("Loading and enriching vocabulary...")
    vocab = load_vocab(args.max_words, args.max_rank, args.deck, cutoffs)
    print(f"Candidate words: {len(vocab)}")

    vocab = apply_pos_filters(vocab, include_pos, exclude_pos)
    print(f"After POS filters: {len(vocab)}")

    vocab = order_vocab(vocab, args.order_mode, pos_order, cutoffs)
    if args.max_words:
        vocab = vocab[:args.max_words]

    assign_batches(vocab, args.batch_strategy, args.batch_size, args.batch_step, args.batch_max_size, cutoffs)
    if args.proficiency_enabled:
        assign_proficiency_blocks(vocab, proficiency_labels)
    else:
        assign_proficiency_blocks(vocab, [])

    settings = {
        "order_mode": args.order_mode,
        "batch_strategy": args.batch_strategy,
        "batch_size": args.batch_size,
        "batch_step": args.batch_step,
        "batch_max_size": args.batch_max_size,
        "proficiency_summary": ", ".join(proficiency_labels) if args.proficiency_enabled else "disabled",
    }

    print(f"Writing {args.output}...")
    Path(args.output).parent.mkdir(exist_ok=True, parents=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(make_html(vocab, settings))
    print(f"OK {args.output}")

    if args.csv_output:
        print(f"Writing {args.csv_output}...")
        Path(args.csv_output).parent.mkdir(exist_ok=True, parents=True)
        with open(args.csv_output, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                "StdBlock", "StdLabel", "Batch", "Rank", "Word", "Definition", "POS", "Syllables", "Band", "Difficulty",
                "IPA", "English_Approx", "Phonetic_Difficulty"
            ])
            for item in vocab:
                pronunciation = item.get("pronunciation", {})
                w.writerow([
                    item.get("proficiency_block", ""), item.get("proficiency_label", ""),
                    item["batch"], item["rank"], item["word"], item["english"],
                    item["pos"], item["syllables"], item["band"], item["difficulty"],
                    pronunciation.get("ipa", ""), pronunciation.get("english_approx", ""),
                    item.get("phonetic_difficulty", "")
                ])
        print(f"OK {args.csv_output}")

    print_batch_summary(vocab, args.preview_batches)

    print("\nSample (first 8):")
    for item in vocab[:8]:
        print(
            f"  S{str(item.get('proficiency_block', '')):>2s} {item.get('proficiency_label', '')[:11]:11s} | "
            f"B{item['batch']:02d} | R{item['rank']:6d} | {item['word'][:14]:14s} | "
            f"{item['pos'][:9]:9s} | syl {item['syllables']} | diff {item['difficulty']:.2f}"
        )


if __name__ == "__main__":
    main()
