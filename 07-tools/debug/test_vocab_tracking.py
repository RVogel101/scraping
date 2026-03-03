#!/usr/bin/env python3
"""Categorized launcher. Delegates to canonical script in 07-tools/."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "test_vocab_tracking.py"
    runpy.run_path(str(target), run_name="__main__")
