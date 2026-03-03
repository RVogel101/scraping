#!/usr/bin/env python3
"""
Tests for Western Armenian transliteration and orthography compliance.

Ensures that:
  1. The ARM character map uses Western Armenian (WA) phonology, not Eastern
     Armenian (EA).  The key shift is in ten consonants that are voiced in EA
     but unvoiced in WA (and vice-versa).
  2. Unicode code-points match the expected Armenian letters.
  3. Article formation (definite / indefinite) follows WA rules.
  4. Syllable counting is correct for the ու digraph and standard vowels.
  5. Noun declension produces WA-standard case suffixes.
  6. Verb conjugation uses the WA preverbal particles (կը / bidi) and WA
     person endings.

Run with:  python test_transliteration.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from lousardzag.morphology.core import (
    ARM,
    ARM_UPPER,
    VOWELS,
    DIGRAPH_U,
    is_vowel,
    is_armenian,
    ends_in_vowel,
    count_syllables,
)
from lousardzag.morphology.articles import (
    add_definite,
    add_indefinite,
    DEF_AFTER_CONSONANT,
    DEF_AFTER_VOWEL,
    INDEF_ARTICLE,
)
from lousardzag.morphology.nouns import decline_noun, DECLENSION_CLASSES
from lousardzag.morphology.verbs import (
    conjugate_verb,
    VERB_CLASSES,
    PRESENT_PARTICLE,
    FUTURE_PARTICLE,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _reverse_arm():
    """Return {unicode_char: transliteration_key} for the ARM map."""
    return {v: k for k, v in ARM.items()}


# ─── 1. ARM Map — Unicode Code Points ────────────────────────────────────────

class TestARMCodePoints(unittest.TestCase):
    """Each ARM key must resolve to the correct Unicode code point."""

    def _assert_cp(self, key, expected_cp):
        char = ARM[key]
        self.assertEqual(
            ord(char), expected_cp,
            f"ARM[{key!r}] expected U+{expected_cp:04X}, got U+{ord(char):04X}",
        )

    # Vowels
    def test_a(self):   self._assert_cp("a",      0x0561)  # ա
    def test_ye(self):  self._assert_cp("ye",     0x0565)  # ե
    def test_e(self):   self._assert_cp("e",      0x0567)  # է
    def test_i(self):   self._assert_cp("i",      0x056B)  # ի
    def test_vo(self):  self._assert_cp("vo",     0x0578)  # ո
    def test_yiwn(self):self._assert_cp("yiwn",   0x0582)  # ւ
    def test_o(self):   self._assert_cp("o",      0x0585)  # օ

    # Unshifted consonants
    def test_z(self):   self._assert_cp("z",      0x0566)  # զ
    def test_l(self):   self._assert_cp("l",      0x056C)  # լ
    def test_kh(self):  self._assert_cp("kh",     0x056D)  # խ
    def test_h(self):   self._assert_cp("h",      0x0570)  # հ
    def test_gh(self):  self._assert_cp("gh",     0x0572)  # ղ
    def test_m(self):   self._assert_cp("m",      0x0574)  # մ
    def test_y(self):   self._assert_cp("y",      0x0575)  # յ
    def test_n(self):   self._assert_cp("n",      0x0576)  # ն
    def test_sh(self):  self._assert_cp("sh",     0x0577)  # շ
    def test_r(self):   self._assert_cp("r",      0x0580)  # ր
    def test_s(self):   self._assert_cp("s",      0x057D)  # ս
    def test_v(self):   self._assert_cp("v",      0x057E)  # վ
    def test_f(self):   self._assert_cp("f",      0x0586)  # փ… wait — checked below


# ─── 2. Western Armenian Consonant Shift ─────────────────────────────────────

class TestWesternArmenianConsonantShift(unittest.TestCase):
    """
    Western Armenian differs from Eastern Armenian in ten consonant pairs.
    This test suite verifies that each letter is mapped to its WA sound,
    not the EA sound.

    The canonical WA shift (EA → WA):
      բ (U+0562): EA=b  → WA=p   (ARM key must be "p", NOT "b")
      գ (U+0563): EA=g  → WA=k   (ARM key must be "k", NOT "g")
      դ (U+0564): EA=d  → WA=t   (ARM key must be "t", NOT "d")
      ծ (U+056E): EA=ts → WA=dz  (ARM key must be "dz", NOT "ts")
      կ (U+056F): EA=k  → WA=g   (ARM key must be "g", NOT "k")
      ձ (U+0571): EA=dz → WA=ts  (ARM key must be "ts", NOT "dz")
      ջ (U+0573): EA=j  → WA=j   (same — but see ch/ch_asp)
      պ (U+057A): EA=p  → WA=b   (ARM key must be "b", NOT "p")
      ч (U+057B): EA=ch → WA=ch  (ARM key must be "ch", NOT "j")  — variant
      տ (U+057F): EA=t  → WA=d   (ARM key must be "d", NOT "t")
    """

    REV = _reverse_arm()

    def _assert_wa_key(self, codepoint, expected_key, letter_name=""):
        char = chr(codepoint)
        actual_key = self.REV.get(char)
        self.assertEqual(
            actual_key, expected_key,
            f"{letter_name} (U+{codepoint:04X}) should map to WA key {expected_key!r}, "
            f"got {actual_key!r}",
        )

    def test_bet_is_p_not_b(self):
        """բ (U+0562) is WA /p/, not EA /b/."""
        self._assert_wa_key(0x0562, "p", "բ")

    def test_gim_is_k_not_g(self):
        """գ (U+0563) is WA /k/, not EA /g/."""
        self._assert_wa_key(0x0563, "k", "գ")

    def test_da_is_t_not_d(self):
        """դ (U+0564) is WA /t/, not EA /d/."""
        self._assert_wa_key(0x0564, "t", "դ")

    def test_ca_is_dz_not_ts(self):
        """ծ (U+056E) is WA /dz/, not EA /ts/."""
        self._assert_wa_key(0x056E, "dz", "ծ")

    def test_ken_is_g_not_k(self):
        """կ (U+056F) is WA /g/, not EA /k/."""
        self._assert_wa_key(0x056F, "g", "կ")

    def test_co_is_ts_not_dz(self):
        """ձ (U+0571) is WA /ts/, not EA /dz/."""
        self._assert_wa_key(0x0571, "ts", "ձ")

    def test_peh_is_b_not_p(self):
        """պ (U+057A) is WA /b/, not EA /p/."""
        self._assert_wa_key(0x057A, "b", "պ")

    def test_jwn_is_ch_not_j(self):
        """ч (U+057B) is WA /ch/, not EA /j/."""
        self._assert_wa_key(0x057B, "ch", "ч")

    def test_tiwn_is_d_not_t(self):
        """տ (U+057F) is WA /d/, not EA /t/."""
        self._assert_wa_key(0x057F, "d", "տ")

    def test_jeh_is_j_not_ch(self):
        """ջ (U+0573) is WA /j/ (as in 'measure')."""
        self._assert_wa_key(0x0573, "j", "ջ")

    # ── Aspirated consonants are NOT shifted ──────────────────────────────
    def test_t_asp_unchanged(self):
        """թ (U+0569) is /t'/ in both WA and EA."""
        self._assert_wa_key(0x0569, "t_asp", "թ")

    def test_k_asp_unchanged(self):
        """փ / ք (U+0584) is /k'/ in both WA and EA."""
        self._assert_wa_key(0x0584, "k_asp", "ք")

    def test_p_asp_unchanged(self):
        """փ (U+0583) is /p'/ in both WA and EA."""
        self._assert_wa_key(0x0583, "p_asp", "փ")

    def test_ch_asp_unchanged(self):
        """չ (U+0579) is /ch'/ in both WA and EA."""
        self._assert_wa_key(0x0579, "ch_asp", "չ")


# ─── 3. ARM Map Completeness ─────────────────────────────────────────────────

class TestARMMapCompleteness(unittest.TestCase):
    """Sanity checks that cover the full set of transliteration keys."""

    EXPECTED_KEYS = {
        "a", "p", "k", "t", "ye", "z", "e", "y_schwa", "t_asp", "zh",
        "i", "l", "kh", "dz", "g", "h", "ts", "gh", "j", "m", "y", "n",
        "sh", "vo", "ch_asp", "b", "ch", "rr", "s", "v", "d", "r",
        "c_asp", "yiwn", "p_asp", "k_asp", "o", "f",
    }

    def test_all_keys_present(self):
        missing = self.EXPECTED_KEYS - set(ARM.keys())
        self.assertEqual(missing, set(), f"Missing ARM keys: {missing}")

    def test_all_values_are_armenian(self):
        for key, char in ARM.items():
            self.assertTrue(
                is_armenian(char),
                f"ARM[{key!r}] = {char!r} (U+{ord(char):04X}) is not Armenian",
            )

    def test_no_duplicate_characters(self):
        chars = list(ARM.values())
        self.assertEqual(len(chars), len(set(chars)), "Duplicate characters in ARM map")

    def test_uppercase_map_has_same_keys(self):
        lower_keys = set(ARM.keys())
        upper_keys = {k.lower() for k in ARM_UPPER.keys()}
        self.assertEqual(lower_keys, upper_keys)


# ─── 4. Vowel Set and Digraph ─────────────────────────────────────────────────

class TestVowelSet(unittest.TestCase):

    def test_all_vowels_in_set(self):
        """Standard Armenian vowels must be classified as vowels."""
        for key in ("a", "ye", "e", "y_schwa", "i", "vo", "o", "yiwn"):
            self.assertIn(ARM[key], VOWELS, f"ARM[{key!r}] should be a vowel")

    def test_consonants_not_vowels(self):
        for key in ("p", "k", "t", "z", "l", "kh", "g", "h", "m", "n", "s", "v"):
            self.assertNotIn(ARM[key], VOWELS, f"ARM[{key!r}] should not be a vowel")

    def test_digraph_u_composition(self):
        """DIGRAPH_U must be ո (vo) + ւ (yiwn)."""
        self.assertEqual(DIGRAPH_U, ARM["vo"] + ARM["yiwn"])

    def test_ends_in_vowel_simple(self):
        self.assertTrue(ends_in_vowel(ARM["a"]))
        self.assertFalse(ends_in_vowel(ARM["n"]))

    def test_ends_in_vowel_digraph(self):
        word = ARM["t"] + DIGRAPH_U  # ends in ու
        self.assertTrue(ends_in_vowel(word))

    def test_ends_in_vowel_empty(self):
        self.assertFalse(ends_in_vowel(""))


# ─── 5. Syllable Counting ─────────────────────────────────────────────────────

class TestSyllableCount(unittest.TestCase):

    def test_single_vowel_word(self):
        # ա (a) — 1 syllable
        self.assertEqual(count_syllables(ARM["a"]), 1)

    def test_digraph_counts_as_one(self):
        # ու (ou/u digraph) — 1 syllable
        self.assertEqual(count_syllables(DIGRAPH_U), 1)

    def test_two_syllable_word(self):
        # ARM["k"]+ի+ր+ք = գիրք (girk', "book") — 1 vowel → 1 syllable
        # (ARM["k"] = գ in WA transliteration)
        girk = ARM["k"] + ARM["i"] + ARM["r"] + ARM["k_asp"]
        self.assertEqual(count_syllables(girk), 1)

    def test_two_vowel_word(self):
        # մ+ա+մ+ա = մամա ("mama") — 2 vowels → 2 syllables
        mama = ARM["m"] + ARM["a"] + ARM["m"] + ARM["a"]
        self.assertEqual(count_syllables(mama), 2)

    def test_word_with_digraph_u(self):
        # տ+ո+ւ+ն = տOUN ("tun", "house") — ու counts as 1 vowel → 1 syllable
        tun = ARM["d"] + DIGRAPH_U + ARM["n"]
        self.assertEqual(count_syllables(tun), 1)


# ─── 6. Article Formation (WA Rules) ─────────────────────────────────────────

class TestArticles(unittest.TestCase):
    """
    WA definite article:
      - After consonant → append ը (y_schwa / schwa)
      - After vowel     → append ն (n)
    WA indefinite: postposed մը (mə, separate word)
    """

    def test_definite_after_consonant(self):
        # կ+ի+ր+ք (girk', "book") ends in ք (consonant)
        girk = ARM["k"] + ARM["i"] + ARM["r"] + ARM["k_asp"]
        result = add_definite(girk)
        self.assertTrue(
            result.endswith(DEF_AFTER_CONSONANT),
            f"Definite of consonant-final word should end with ը; got {result!r}",
        )

    def test_definite_after_vowel(self):
        # մ+ա+մ+ա (mama) ends in ա (vowel)
        mama = ARM["m"] + ARM["a"] + ARM["m"] + ARM["a"]
        result = add_definite(mama)
        self.assertTrue(
            result.endswith(DEF_AFTER_VOWEL),
            f"Definite of vowel-final word should end with ն; got {result!r}",
        )

    def test_definite_after_n_appends_schwa(self):
        # ն (n) is a consonant → definite form appends ը (schwa)
        # e.g. տ+ո+ւ+ն (tun, "house") → տ+ո+ւ+ն+ը (tunə)
        tun = ARM["d"] + ARM["vo"] + ARM["yiwn"] + ARM["n"]
        result = add_definite(tun)
        self.assertTrue(
            result.endswith(DEF_AFTER_CONSONANT),
            f"Word ending in ն (consonant) should get ը appended; got {result!r}",
        )

    def test_indefinite_article_format(self):
        # Indefinite should be "word + space + մը"
        girk = ARM["k"] + ARM["i"] + ARM["r"] + ARM["k_asp"]
        result = add_indefinite(girk)
        self.assertEqual(result, girk + " " + INDEF_ARTICLE)

    def test_indefinite_article_is_mə(self):
        """INDEF_ARTICLE must be մ (m) + ը (y_schwa) = մը"""
        self.assertEqual(INDEF_ARTICLE, ARM["m"] + ARM["y_schwa"])

    def test_definite_suffix_after_consonant_is_schwa(self):
        """DEF_AFTER_CONSONANT must be ը (y_schwa)."""
        self.assertEqual(DEF_AFTER_CONSONANT, ARM["y_schwa"])

    def test_definite_suffix_after_vowel_is_n(self):
        """DEF_AFTER_VOWEL must be ն (n)."""
        self.assertEqual(DEF_AFTER_VOWEL, ARM["n"])


# ─── 7. Noun Declension — WA Case Suffixes ────────────────────────────────────

class TestNounDeclension(unittest.TestCase):
    """
    Verify that the i-class declension of գ+ի+ր+ք (girk', "book") produces
    the expected Western Armenian forms.
    """

    def setUp(self):
        # գ+ի+ր+ք = girk' ("book"), i_class
        self.girk = ARM["k"] + ARM["i"] + ARM["r"] + ARM["k_asp"]
        self.decl = decline_noun(self.girk, "i_class", "book")

    def test_nominative_sg_is_base_form(self):
        self.assertEqual(self.decl.nom_sg, self.girk)

    def test_genitive_dative_sg_has_i_suffix(self):
        expected = self.girk + ARM["i"]
        self.assertEqual(self.decl.gen_dat_sg, expected)

    def test_ablative_sg_has_e_suffix(self):
        expected = self.girk + ARM["e"]
        self.assertEqual(self.decl.abl_sg, expected)

    def test_instrumental_sg_has_ov_suffix(self):
        ov = ARM["vo"] + ARM["v"]
        expected = self.girk + ov
        self.assertEqual(self.decl.instr_sg, expected)

    def test_nominative_pl_has_ner_suffix(self):
        ner = ARM["n"] + ARM["ye"] + ARM["r"]
        expected = self.girk + ner
        self.assertEqual(self.decl.nom_pl, expected)

    def test_genitive_dative_pl_has_neri_suffix(self):
        neri = ARM["n"] + ARM["ye"] + ARM["r"] + ARM["i"]
        expected = self.girk + neri
        self.assertEqual(self.decl.gen_dat_pl, expected)

    def test_nom_sg_def_uses_schwa_after_consonant(self):
        self.assertTrue(self.decl.nom_sg_def.endswith(ARM["y_schwa"]))

    def test_nom_sg_indef_contains_mə(self):
        self.assertIn(INDEF_ARTICLE, self.decl.nom_sg_indef)

    def test_unknown_class_raises(self):
        with self.assertRaises(ValueError):
            decline_noun(self.girk, "nonexistent_class")

    def test_all_four_declension_classes_exist(self):
        for cls in ("i_class", "u_class", "a_class", "o_class"):
            self.assertIn(cls, DECLENSION_CLASSES)


# ─── 8. Verb Conjugation — WA Particles and Endings ──────────────────────────

class TestVerbConjugation(unittest.TestCase):
    """
    Verify that Western Armenian verb forms use:
      - Present indicative: preverb կը (gə) + subjunctive
      - Future:             preverb պիտի (bidi) + subjunctive
      - Correct WA person endings for e_class and a_class
    """

    def setUp(self):
        # ARM["k"]+ր+ե+լ = գրել (krel, "to write"), e_class
        # (ARM["k"] = գ in WA; the WA pronunciation key is "k" for the letter գ)
        self.krel = ARM["k"] + ARM["r"] + ARM["ye"] + ARM["l"]
        self.conj_e = conjugate_verb(self.krel, "e_class", "write")

        # a_class verb: ARM["k"]+ա+ն+ա+լ = կanalel ("to stand/become"), a_class
        # (ARM["k"] = գ in WA; ARM["g"] = կ in WA)
        self.kanal = ARM["k"] + ARM["a"] + ARM["n"] + ARM["a"] + ARM["l"]
        self.conj_a = conjugate_verb(self.kanal, "a_class", "stand")

    # ── Present particle: կը (g + y_schwa) ───────────────────────────────────

    def test_present_particle_is_wa_ge(self):
        """PRESENT_PARTICLE must be կ (g) + ը (y_schwa) = կը"""
        self.assertEqual(PRESENT_PARTICLE, ARM["g"] + ARM["y_schwa"])

    def test_present_particle_not_ea_ge(self):
        """Present particle must NOT use EA կ pronunciation (which WA calls 'g')."""
        # In WA, կ = ARM["g"]; in EA, կ = 'k'. Check we're using ARM["g"].
        self.assertIn(ARM["g"], PRESENT_PARTICLE)
        # Ensure we do NOT have ARM["k"] (գ) in the particle
        self.assertNotIn(ARM["k"], PRESENT_PARTICLE)

    def test_future_particle_is_bidi(self):
        """FUTURE_PARTICLE must be բ+ի+դ+ի = bidi (WA future marker)."""
        expected = ARM["b"] + ARM["i"] + ARM["d"] + ARM["i"]
        self.assertEqual(FUTURE_PARTICLE, expected)

    def test_future_particle_not_eastern(self):
        """Future particle must use WA /b/ (պ) and /d/ (տ), not EA /p/ and /t/."""
        # WA: բ=ARM["p"]… wait — in WA բ="p" and պ="b". So bidi uses պ (ARM["b"])
        # and տ (ARM["d"]).
        self.assertIn(ARM["b"], FUTURE_PARTICLE)  # պ = WA /b/
        self.assertIn(ARM["d"], FUTURE_PARTICLE)  # տ = WA /d/

    # ── Present tense form ────────────────────────────────────────────────────

    def test_present_1sg_starts_with_present_particle(self):
        form = self.conj_e.present["1sg"]
        self.assertTrue(
            form.startswith(PRESENT_PARTICLE),
            f"Present 1sg should start with կը; got {form!r}",
        )

    def test_present_3sg_starts_with_present_particle(self):
        form = self.conj_e.present["3sg"]
        self.assertTrue(form.startswith(PRESENT_PARTICLE))

    # ── Future tense form ─────────────────────────────────────────────────────

    def test_future_1sg_starts_with_future_particle(self):
        form = self.conj_e.future["1sg"]
        self.assertTrue(
            form.startswith(FUTURE_PARTICLE),
            f"Future 1sg should start with բidи; got {form!r}",
        )

    # ── E-class subjunctive endings ───────────────────────────────────────────

    def test_e_class_subj_1sg_ends_em(self):
        em = ARM["ye"] + ARM["m"]
        self.assertTrue(
            self.conj_e.subjunctive["1sg"].endswith(em),
            f"e_class 1sg subjunctive should end in եմ; got {self.conj_e.subjunctive['1sg']!r}",
        )

    def test_e_class_subj_2sg_ends_es(self):
        es = ARM["ye"] + ARM["s"]
        self.assertTrue(self.conj_e.subjunctive["2sg"].endswith(es))

    def test_e_class_subj_1pl_ends_enk(self):
        enk = ARM["ye"] + ARM["n"] + ARM["k_asp"]
        self.assertTrue(self.conj_e.subjunctive["1pl"].endswith(enk))

    # ── A-class subjunctive endings ───────────────────────────────────────────

    def test_a_class_subj_1sg_ends_am(self):
        am = ARM["a"] + ARM["m"]
        self.assertTrue(
            self.conj_a.subjunctive["1sg"].endswith(am),
            f"a_class 1sg subjunctive should end in am; got {self.conj_a.subjunctive['1sg']!r}",
        )

    def test_a_class_subj_2sg_ends_as(self):
        a_s = ARM["a"] + ARM["s"]
        self.assertTrue(self.conj_a.subjunctive["2sg"].endswith(a_s))

    # ── All persons present ───────────────────────────────────────────────────

    def test_all_persons_in_present(self):
        for person in ("1sg", "2sg", "3sg", "1pl", "2pl", "3pl"):
            self.assertIn(person, self.conj_e.present)

    def test_all_persons_in_past_aorist(self):
        for person in ("1sg", "2sg", "3sg", "1pl", "2pl", "3pl"):
            self.assertIn(person, self.conj_e.past_aorist)

    # ── Unknown class raises ──────────────────────────────────────────────────

    def test_unknown_verb_class_raises(self):
        with self.assertRaises(ValueError):
            conjugate_verb(self.krel, "unknown_class")

    def test_both_verb_classes_exist(self):
        for cls in ("e_class", "a_class"):
            self.assertIn(cls, VERB_CLASSES)


# ─── 9. is_armenian helper ────────────────────────────────────────────────────

class TestIsArmenian(unittest.TestCase):

    def test_lowercase_letters_are_armenian(self):
        for char in ARM.values():
            self.assertTrue(is_armenian(char), f"{char!r} should be Armenian")

    def test_uppercase_letters_are_armenian(self):
        for char in ARM_UPPER.values():
            self.assertTrue(is_armenian(char), f"{char!r} should be Armenian")

    def test_ascii_not_armenian(self):
        for ch in "abcdefghijklmnopqrstuvwxyz0123456789":
            self.assertFalse(is_armenian(ch))


if __name__ == "__main__":
    unittest.main(verbosity=2)
