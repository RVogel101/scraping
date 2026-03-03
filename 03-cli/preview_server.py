#!/usr/bin/env python3
"""Render sample noun/verb/sentence cards from local real data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add 02-src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / '02-src'))

from lousardzag.database import CardDatabase, DEFAULT_DB_PATH
from lousardzag.preview import build_preview_payload


def main() -> None:
    # Windows PowerShell may default to a legacy code page; force UTF-8 output.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Render formatted card previews from local data")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite DB path")
    parser.add_argument("--source-deck", default=None, help="Optional deck filter for vocabulary cache")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = parser.parse_args()

    db = CardDatabase(args.db_path)
    payload = build_preview_payload(db, source_deck=args.source_deck)

    if args.pretty:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
