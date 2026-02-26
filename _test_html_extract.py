# -*- coding: utf-8 -*-
"""Smoke-test for CardGenerator HTML extraction helpers."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from armenian_anki.card_generator import CardGenerator

# ── build sample HTML matching the real deck format ───────────────────
_SQ = "'"   # single-quote alias to avoid nesting issues

# Front field for "պatker" (image / picture)
FRONT = (
    "\n<div style=" + _SQ + 'font-family: "Arial"; font-size: 20px;' + _SQ + ">պatker</div>\n"
    .replace("patker", "պatker")
)
# insert syllable guide
FRONT = FRONT.replace("patker", "պatker")

# Build it properly using chr() for the tricky quote characters
def _div(text):
    return "<div style='font-family: \"Arial\"; font-size: 20px;'>" + text + "</div>\n"

WORD = "պatker"
WORD = "պatker"

# Actually just use concatenation with explicit Armenian chars
FRONT = (
    "\n" + _div("paword") + "\n"
    + "<div class=\"toggle-section\">\n"
    + "  <label>Syllable Guide</label>\n"
    + "  <div class=\"toggle-content\">"
    + "Pword<span style=\"color: rgb(0, 170, 0);\">avowel</span>tsyl-ksyl<span style=\"color: rgb(0, 170, 0);\">evowel</span>rer"
    + "</div>\n</div>\n<hr>\n"
)

# Replace placeholders with Armenian chars to avoid encoding escape issues
FRONT = (
    FRONT
    .replace("paword", "պatker")
    .replace("patker", "պatker")
    .replace("Pword", "Պ")
    .replace("avowel", "պ")
    .replace("tsyl", "տ")
    .replace("ksyl", "կ")
    .replace("evowel", "ե")
    .replace("rer", "ր")
)
FRONT = FRONT.replace("Պ", "Պ")   # no-op, just testing
# Just build clean HTML directly:
import re

PATKER = chr(0x057a) + chr(0x0561) + chr(0x0569) + chr(0x056f) + chr(0x0565) + chr(0x580)
# պ=057a ա=0561 տ=0569 կ=056f ե=0565 ր=0580

PRON_I = chr(0x0535)   # Պ uppercase

FRONT = (
    "\n<div style='font-family: \"Arial\"; font-size: 20px;'>"
    + PATKER
    + "</div>\n"
    + "<div class=\"toggle-section\">\n"
    + "  <div class=\"toggle-content\">"
    + chr(0x0535) + "<span>" + chr(0x0561) + "</span>" + chr(0x0569) + "-"
    + chr(0x056f) + "<span>" + chr(0x0565) + "</span>" + chr(0x0580)
    + "</div>\n</div>\n<hr>\n"
)

BACK = (
    FRONT
    + "<div style='font-family: \"Arial\"; font-size: 20px;'>image, picture</div>\n"
    + "<div style='font-family: \"Arial\"; font-size: 20px;'><img src=\"Painting.jpg\"></div>\n"
)

# ── test 1: basic extraction ──────────────────────────────────────────
word        = CardGenerator._extract_word_from_front(FRONT)
translation = CardGenerator._extract_translation_from_back(BACK)
pos         = CardGenerator._detect_pos(word)
syllables   = CardGenerator._extract_syllable_count(FRONT)

print(f"word:        {word!r}")
print(f"translation: {translation!r}")
print(f"pos:         {pos!r}")
print(f"syllables:   {syllables}")

assert word == PATKER,              f"word mismatch: {word!r}"
assert translation == "image, picture", f"translation mismatch: {translation!r}"
assert pos == "noun",               f"pos mismatch"
assert syllables == 2,              f"syllables: {syllables}"

# ── test 2: verb suffix detection ────────────────────────────────────
el = chr(0x0565) + chr(0x056C)   # -el  (e-class verb ending)
il = chr(0x056B) + chr(0x056C)   # -il  (reflexive verb ending)
al = chr(0x0561) + chr(0x056C)   # -al  (a-class verb ending)

for suffix, label in [(el, "-el"), (il, "-il"), (al, "-al")]:
    v = "abc" + suffix
    r = CardGenerator._detect_pos(v)
    print(f"  detect_pos(stem+{label!r}) = {r!r}")
    assert r == "verb", f"Expected verb for suffix {label}"

noun_word = "abc"
assert CardGenerator._detect_pos(noun_word) == "noun"
print("  detect_pos('noun-ish') = 'noun'  OK")

# ── test 3: comma-separated alternates — take first ──────────────────
BUTHAMAT = (chr(0x562) + chr(0x578) + chr(0x582) + chr(0x569) + chr(0x561)
            + chr(0x574) + chr(0x561) + chr(0x569))  # բuthaamat
# Simpler: use "word1, word2" literal
front_comma = "<div style='font-family: \"Arial\";'>First, Second</div>"
w2 = CardGenerator._extract_word_from_front(front_comma)
print(f"comma test:  {w2!r}")
assert w2 == "First", f"Expected 'First', got {w2!r}"
assert "," not in w2 and " " not in w2

# ── test 4: phrase cards contain space — should be skipped ───────────
front_phrase = "<div style='font-family: \"Arial\";'>hello world</div>"
w3 = CardGenerator._extract_word_from_front(front_phrase)
print(f"phrase skip: {w3!r}  space={' ' in w3}")
assert " " in w3, "phrase card must contain a space so caller skips it"

# ── test 5: no syllable guide → 0 ────────────────────────────────────
no_guide = "<div style='font-family:\"Arial\"'>word</div>"
assert CardGenerator._extract_syllable_count(no_guide) == 0
print("  no-guide syllable count = 0  OK")

# ── test 6: 3-syllable guide ──────────────────────────────────────────
three_syl = ("other content "
             "<div class=\"toggle-content\">A<span>b</span>c-D<span>e</span>f-G<span>h</span>i</div>"
             " more")
assert CardGenerator._extract_syllable_count(three_syl) == 3
print("  3-syllable guide = 3  OK")

print("\nAll assertions passed.")
