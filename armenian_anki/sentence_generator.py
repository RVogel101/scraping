"""
Armenian sentence generator.

Creates template-based example sentences using different morphological forms
of a given word. Demonstrates usage of cases (for nouns) and tenses (for verbs)
in context.

Sentence templates use Western Armenian word order (SOV tendency but flexible).
"""

from .morphology.core import ARM
from .morphology.nouns import decline_noun, NounDeclension
from .morphology.verbs import conjugate_verb, VerbConjugation
from .morphology.articles import add_definite, add_indefinite

# ─── Character shortcuts (WA transliteration) ────────────────────────
_ye  = ARM["ye"]
_a   = ARM["a"]
_i   = ARM["i"]
_e   = ARM["e"]
_n   = ARM["n"]
_r   = ARM["r"]
_m   = ARM["m"]
_s   = ARM["s"]
_g   = ARM["g"]        # dles (WA: g — EA "k")
_k_asp = ARM["k_asp"]
_d   = ARM["d"]        # dles (WA: d — EA "t")
_l   = ARM["l"]
_vo  = ARM["vo"]
_v   = ARM["v"]
_schwa = ARM["y_schwa"]
_yiwn = ARM["yiwn"]
_t   = ARM["t"]        # dles (WA: t — EA "d")
_h   = ARM["h"]
_b   = ARM["b"]        # dles (WA: b — EA "p")
_k   = ARM["k"]        # dles (WA: k — EA "g")
_sh  = ARM["sh"]
_t_asp = ARM["t_asp"]
_j   = ARM["j"]        # dles (WA: j — EA "ch")
_ch_asp = ARM["ch_asp"]
_dz  = ARM["dz"]       # dles (WA: dz — EA "ts")
_p_asp = ARM["p_asp"]
_z   = ARM["z"]
_kh  = ARM["kh"]
_gh  = ARM["gh"]
_rr  = ARM["rr"]
_ch  = ARM["ch"]       # dles (WA: ch — EA "j")

# ─── Common Words for Templates ──────────────────────────────────────
# Pronouns (WA transliteration)
PRON_I = _ye + _s                                    # եdelays (yes = I)
PRON_YOU_SG = _t + _vo + _yiwn + _n                  # delays (tun = you sg)
PRON_HE = _a + _n                                    # delays (an = he/she/it)
PRON_WE = _m + _ye + _n + _k_asp                     # delays (menk' = we)
PRON_YOU_PL = _t + _vo + _yiwn + _k_asp              # delays (tuk' = you pl)
PRON_THEY = _a + _n + _vo + _n + _k_asp              # delays (anonk' = they)

# Common verbs as helpers (WA transliteration: preverbal particle is գdelays gə)
VERB_SEE = _g + _schwa + " " + _d + _ye + _s + _n + _ye + _m      # delays (gə desnem = I see)
VERB_HAVE = _vo + _yiwn + _n + _i + _m                              # delays (ounim = I have)
VERB_LOVE = _g + _schwa + " " + _s + _i + _r + _ye + _m            # delays (gə sirem = I love)
VERB_WANT = _g + _schwa + " " + _vo + _yiwn + _z + _ye + _m        # delays (gə uzem = I want)
VERB_GO = _g + _schwa + " " + _ye + _r + _t_asp + _a + _m          # delays (gə ert'am = I go)

# Prepositions and common words (WA transliteration)
WITH_WORD = _h + _ye + _d                             # delays (hed = with/together)
FROM_WORD = ""  # ablative case handles "from" — no separate word needed
IN_WORD = _m + _e + _ch                                # delays (mēch = inside/in)
ON_WORD = _v + _r + _a                                # delays (vra = on)
THIS = _a + _s                                         # delays (as = this)
THAT = _a + _n                                         # delays (an = that)
VERY = _sh + _a + _d                                   # delays (shad = very)
BEAUTIFUL = _k + _ye + _gh + _ye + _dz + _i + _g      # delays (keghedzig = beautiful)
BIG = _m + _ye + _dz                                   # delays (medz = big)
GOOD = _l + _a + _v                                    # delays (lav = good)
NEW = _n + _vo + _r                                    # delays (nor = new)

# Copula: delays (ē = is)
COPULA = _e                                            # delays (ē = is)


# ─── Noun Sentence Templates ─────────────────────────────────────────
# Each template is (case_used, template_func, english_template)
# template_func receives the NounDeclension object and returns the Armenian sentence

def _noun_sentence_templates(decl: NounDeclension) -> list[tuple[str, str, str]]:
    """Generate sentences using different case forms of a noun.

    Returns list of (case_name, armenian_sentence, english_translation).
    """
    word = decl.word
    trans = decl.translation or "___"
    sentences = []

    # 1. Nominative — subject of sentence
    # "The ___ is beautiful"
    _gegh = _k + _ye + _gh + _ye + _dz + _i + _g  # keghedzig
    arm_sent = decl.nom_sg_def + " " + _gegh + " " + COPULA
    sentences.append((
        "nominative",
        arm_sent,
        f"The {trans} is beautiful.",
    ))

    # 2. Nominative indefinite — with indefinite article
    # "A ___ is here"
    _hso = _h + _vo + _s
    arm_sent = decl.nom_sg_indef + " " + _hso + " " + COPULA
    sentences.append((
        "nominative (indefinite)",
        arm_sent,
        f"A {trans} is here.",
    ))

    # 3. Accusative definite — direct object
    # "I see the ___"
    _tes = _g + _schwa + " " + _d + _ye + _s + _n + _ye + _m  # gə desnem
    arm_sent = PRON_I + " " + decl.acc_sg_def + " " + _tes
    sentences.append((
        "accusative",
        arm_sent,
        f"I see the {trans}.",
    ))

    # 4. Genitive-Dative — possession
    # "The ___'s color is beautiful" / "I give to the ___"
    _kounk = _k + _vo + _yiwn + _n + _k_asp + _schwa  # kounk'ə (color-DEF)
    arm_sent = decl.gen_dat_sg_def + " " + _kounk + " " + _gegh + " " + COPULA
    sentences.append((
        "genitive-dative",
        arm_sent,
        f"The {trans}'s color is beautiful.",
    ))

    # 5. Ablative — origin/source
    # "I come from the ___"
    _gam = _g + _schwa + " " + _k + _a + _m  # gə kam (I come)
    arm_sent = PRON_I + " " + decl.abl_sg_def + " " + _gam
    sentences.append((
        "ablative",
        arm_sent,
        f"I come from the {trans}.",
    ))

    # 6. Instrumental — means
    # "I write with the ___"
    _grem = _g + _schwa + " " + _k + _r + _ye + _m  # gə krem (I write)
    arm_sent = PRON_I + " " + decl.instr_sg_def + " " + _grem
    sentences.append((
        "instrumental",
        arm_sent,
        f"I write with the {trans}.",
    ))

    # 7. Plural nominative
    # "The ___s are big"
    _medz = _m + _ye + _dz  # medz (big)
    arm_sent = decl.nom_pl_def + " " + _medz + " " + _ye + _n
    sentences.append((
        "plural nominative",
        arm_sent,
        f"The {trans}s are big.",
    ))

    return sentences


# ─── Verb Sentence Templates ─────────────────────────────────────────

def _verb_sentence_templates(conj: VerbConjugation) -> list[tuple[str, str, str]]:
    """Generate sentences using different tense forms of a verb.

    Returns list of (tense_person, armenian_sentence, english_translation).
    """
    trans = conj.translation or "___"
    sentences = []

    # 1. Present 1sg — "I ___"
    if "1sg" in conj.present:
        arm_sent = PRON_I + " " + conj.present["1sg"]
        sentences.append((
            "present 1sg",
            arm_sent,
            f"I {trans}.",
        ))

    # 2. Present 3sg — "He/she ___s"
    if "3sg" in conj.present:
        arm_sent = PRON_HE + " " + conj.present["3sg"]
        sentences.append((
            "present 3sg",
            arm_sent,
            f"He/she {trans}s.",
        ))

    # 3. Past 1sg — "I ___ed"
    if "1sg" in conj.past_aorist:
        arm_sent = PRON_I + " " + conj.past_aorist["1sg"]
        sentences.append((
            "past 1sg",
            arm_sent,
            f"I {trans}ed.",
        ))

    # 4. Future 1sg — "I will ___"
    if "1sg" in conj.future:
        arm_sent = PRON_I + " " + conj.future["1sg"]
        sentences.append((
            "future 1sg",
            arm_sent,
            f"I will {trans}.",
        ))

    # 5. Imperative — "___!"
    if conj.imperative_sg:
        arm_sent = conj.imperative_sg + "!"
        sentences.append((
            "imperative 2sg",
            arm_sent,
            f"{trans.capitalize()}!",
        ))

    # 6. Present 1pl — "We ___"
    if "1pl" in conj.present:
        arm_sent = PRON_WE + " " + conj.present["1pl"]
        sentences.append((
            "present 1pl",
            arm_sent,
            f"We {trans}.",
        ))

    # 7. Imperfect 1sg — "I was ___ing"
    if "1sg" in conj.imperfect:
        arm_sent = PRON_I + " " + conj.imperfect["1sg"]
        sentences.append((
            "imperfect 1sg",
            arm_sent,
            f"I was {trans}ing.",
        ))

    return sentences


# ─── Public API ───────────────────────────────────────────────────────

def generate_noun_sentences(
    word: str,
    declension_class: str = "i_class",
    translation: str = "",
    max_sentences: int = 7,
) -> list[tuple[str, str, str]]:
    """Generate example sentences demonstrating case usage for a noun.

    Args:
        word: Armenian noun (nominative singular).
        declension_class: Declension class key.
        translation: English translation.
        max_sentences: Maximum number of sentences to generate.

    Returns:
        List of (case_label, armenian_sentence, english_sentence) tuples.
    """
    decl = decline_noun(word, declension_class, translation)
    sentences = _noun_sentence_templates(decl)
    return sentences[:max_sentences]


def generate_verb_sentences(
    infinitive: str,
    verb_class: str = "e_class",
    translation: str = "",
    max_sentences: int = 7,
) -> list[tuple[str, str, str]]:
    """Generate example sentences demonstrating tense usage for a verb.

    Args:
        infinitive: Armenian verb infinitive.
        verb_class: Verb class key.
        translation: English translation.
        max_sentences: Maximum number of sentences to generate.

    Returns:
        List of (tense_label, armenian_sentence, english_sentence) tuples.
    """
    conj = conjugate_verb(infinitive, verb_class, translation)
    sentences = _verb_sentence_templates(conj)
    return sentences[:max_sentences]
