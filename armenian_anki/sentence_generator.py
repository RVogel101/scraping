"""
Armenian sentence generator.

Creates template-based example sentences using different morphological forms
of a given word. Demonstrates usage of cases (for nouns) and tenses (for verbs)
in context.

Sentence templates use Western Armenian word order (SOV tendency but flexible).

Can generate sentences in multiple styles:
  - With explicit pronouns: "ես կարդամ" (I read)
  - With optional pronouns: "(ես) կարդամ" (I read — pronoun implied by -մ ending)
  - With romanization: "(yes) gardam"
"""

from .morphology.core import ARM, romanize
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

# ─── English Verb Inflection Helpers ─────────────────────────────────
# Irregular English past-tense forms used in sentence templates.
_IRREGULAR_PAST: dict[str, str] = {
    "be": "was", "become": "became", "begin": "began", "break": "broke",
    "bring": "brought", "build": "built", "buy": "bought", "catch": "caught",
    "choose": "chose", "come": "came", "cut": "cut", "dig": "dug",
    "do": "did", "draw": "drew", "drink": "drank", "drive": "drove",
    "eat": "ate", "fall": "fell", "feel": "felt", "fight": "fought",
    "find": "found", "fly": "flew", "forget": "forgot", "get": "got",
    "give": "gave", "go": "went", "grow": "grew", "have": "had",
    "hear": "heard", "hold": "held", "keep": "kept", "know": "knew",
    "leave": "left", "lend": "lent", "let": "let", "lie": "lay",
    "lose": "lost", "make": "made", "mean": "meant", "meet": "met",
    "pay": "paid", "put": "put", "read": "read", "ride": "rode",
    "ring": "rang", "rise": "rose", "run": "ran", "say": "said",
    "see": "saw", "seek": "sought", "sell": "sold", "send": "sent",
    "set": "set", "show": "showed", "sit": "sat", "sleep": "slept",
    "speak": "spoke", "spend": "spent", "stand": "stood", "steal": "stole",
    "swim": "swam", "take": "took", "teach": "taught", "tell": "told",
    "think": "thought", "throw": "threw", "understand": "understood",
    "wake": "woke", "wear": "wore", "win": "won", "write": "wrote",
}

def _en_past(infinitive: str) -> str:
    """Return the English simple past form of an infinitive."""
    v = infinitive.lower()
    if v in _IRREGULAR_PAST:
        return _IRREGULAR_PAST[v]
    # Regular: final -e → +d; final consonant-vowel-consonant (short) → double + ed;
    # otherwise → +ed (good enough for demo sentences)
    if v.endswith("e"):
        return v + "d"
    if (len(v) >= 3 and v[-1] not in "aeiouwy"
            and v[-2] in "aeiou" and v[-3] not in "aeiou"):
        return v + v[-1] + "ed"
    return v + "ed"


def _en_progressive(infinitive: str) -> str:
    """Return the English present-participle (-ing) form of an infinitive."""
    v = infinitive.lower()
    # final silent -e → drop before -ing (write → writing)
    if v.endswith("e") and not v.endswith("ee"):
        return v[:-1] + "ing"
    # short CVC doubling (run → running)
    if (len(v) >= 3 and v[-1] not in "aeiouwy"
            and v[-2] in "aeiou" and v[-3] not in "aeiou"):
        return v + v[-1] + "ing"
    return v + "ing"


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

def _noun_sentence_templates(
    decl: NounDeclension,
    pronoun_style: str = "explicit",
) -> list[tuple[str, str, str]]:
    """Generate sentences using different case forms of a noun.

    Args:
        decl: NounDeclension object with all declined forms.
        pronoun_style: "explicit", "optional", or "none" for pronouns.

    Returns list of (case_name, armenian_sentence, english_translation).
    """
    word = decl.word
    trans = decl.translation or "___"
    sentences = []

    # ── Nominative ────────────────────────────────────────────────────
    # 1. "The ___ is beautiful"
    _gegh = _k + _ye + _gh + _ye + _dz + _i + _g  # keghedzig
    arm_sent = decl.nom_sg_def + " " + _gegh + " " + COPULA
    sentences.append((
        "nominative",
        arm_sent,
        f"The {trans} is beautiful.",
    ))

    # 2. "The ___ is new"
    arm_sent = decl.nom_sg_def + " " + NEW + " " + COPULA
    sentences.append((
        "nominative",
        arm_sent,
        f"The {trans} is new.",
    ))

    # 3. "This __ is good"
    arm_sent = THIS + " " + decl.nom_sg_def + " " + GOOD + " " + COPULA
    sentences.append((
        "nominative",
        arm_sent,
        f"This {trans} is good.",
    ))

    # ── Nominative indefinite ─────────────────────────────────────────
    # 4. "A ___ is here"
    _hso = _h + _vo + _s
    arm_sent = decl.nom_sg_indef + " " + _hso + " " + COPULA
    sentences.append((
        "nominative (indefinite)",
        arm_sent,
        f"A {trans} is here.",
    ))

    # 5. "I want a ___"
    arm_sent = PRON_I + " " + decl.nom_sg_indef + " " + VERB_WANT
    sentences.append((
        "nominative (indefinite)",
        arm_sent,
        f"I want a {trans}.",
    ))

    # 6. "I have a ___"
    arm_sent = PRON_I + " " + decl.nom_sg_indef + " " + VERB_HAVE
    sentences.append((
        "nominative (indefinite)",
        arm_sent,
        f"I have a {trans}.",
    ))

    # ── Accusative ────────────────────────────────────────────────────
    # 7. "I see the ___"
    _tes = _g + _schwa + " " + _d + _ye + _s + _n + _ye + _m  # gə desnem
    arm_sent = PRON_I + " " + decl.acc_sg_def + " " + _tes
    sentences.append((
        "accusative",
        arm_sent,
        f"I see the {trans}.",
    ))

    # 8. "I love the ___"
    arm_sent = PRON_I + " " + decl.acc_sg_def + " " + VERB_LOVE
    sentences.append((
        "accusative",
        arm_sent,
        f"I love the {trans}.",
    ))

    # 9. "I want the ___"
    arm_sent = PRON_I + " " + decl.acc_sg_def + " " + VERB_WANT
    sentences.append((
        "accusative",
        arm_sent,
        f"I want the {trans}.",
    ))

    # ── Genitive-Dative ──────────────────────────────────────────────
    # 10. "The ___'s color is beautiful"
    _kounk = _k + _vo + _yiwn + _n + _k_asp + _schwa  # kounk'ə (color-DEF)
    arm_sent = decl.gen_dat_sg_def + " " + _kounk + " " + _gegh + " " + COPULA
    sentences.append((
        "genitive-dative",
        arm_sent,
        f"The {trans}'s color is beautiful.",
    ))

    # 11. "I give to the ___"
    _gdam = _g + _schwa + " " + _d + _a + _m  # gə dam (I give)
    arm_sent = PRON_I + " " + decl.gen_dat_sg_def + " " + _gdam
    sentences.append((
        "genitive-dative",
        arm_sent,
        f"I give to the {trans}.",
    ))

    # 12. "The ___'s name is beautiful"
    _anounk = _a + _n + _vo + _yiwn + _n + _schwa  # anounə (name-DEF)
    arm_sent = decl.gen_dat_sg_def + " " + _anounk + " " + _gegh + " " + COPULA
    sentences.append((
        "genitive-dative",
        arm_sent,
        f"The {trans}'s name is beautiful.",
    ))

    # ── Ablative ──────────────────────────────────────────────────────
    # 13. "I come from the ___"
    _gam = _g + _schwa + " " + _k + _a + _m  # gə kam (I come)
    arm_sent = PRON_I + " " + decl.abl_sg_def + " " + _gam
    sentences.append((
        "ablative",
        arm_sent,
        f"I come from the {trans}.",
    ))

    # 14. "He/she comes from the ___"
    _ga = _g + _schwa + " " + _k + _a  # gə ka (he/she comes)
    arm_sent = PRON_HE + " " + decl.abl_sg_def + " " + _ga
    sentences.append((
        "ablative",
        arm_sent,
        f"He/she comes from the {trans}.",
    ))

    # 15. "I am far from the ___"
    _herou = _h + _ye + _rr + _vo + _yiwn  # heṙou (far)
    arm_sent = PRON_I + " " + decl.abl_sg_def + " " + _herou + " " + _ye + _m
    sentences.append((
        "ablative",
        arm_sent,
        f"I am far from the {trans}.",
    ))

    # ── Instrumental ──────────────────────────────────────────────────
    # 16. "I write with the ___"
    _grem = _g + _schwa + " " + _k + _r + _ye + _m  # gə krem (I write)
    arm_sent = PRON_I + " " + decl.instr_sg_def + " " + _grem
    sentences.append((
        "instrumental",
        arm_sent,
        f"I write with the {trans}.",
    ))

    # 17. "He/she comes with the ___"
    arm_sent = PRON_HE + " " + decl.instr_sg_def + " " + WITH_WORD + " " + _ga
    sentences.append((
        "instrumental",
        arm_sent,
        f"He/she comes with the {trans}.",
    ))

    # 18. "We go with the ___"
    arm_sent = PRON_WE + " " + decl.instr_sg_def + " " + WITH_WORD + " " + VERB_GO
    sentences.append((
        "instrumental",
        arm_sent,
        f"We go with the {trans}.",
    ))

    # ── Plural nominative ────────────────────────────────────────────
    # 19. "The ___s are big"
    _medz = _m + _ye + _dz  # medz (big)
    arm_sent = decl.nom_pl_def + " " + _medz + " " + _ye + _n
    sentences.append((
        "plural nominative",
        arm_sent,
        f"The {trans}s are big.",
    ))

    # 20. "The ___s are good"
    arm_sent = decl.nom_pl_def + " " + GOOD + " " + _ye + _n
    sentences.append((
        "plural nominative",
        arm_sent,
        f"The {trans}s are good.",
    ))

    # 21. "The ___s are beautiful"
    arm_sent = decl.nom_pl_def + " " + _gegh + " " + _ye + _n
    sentences.append((
        "plural nominative",
        arm_sent,
        f"The {trans}s are beautiful.",
    ))

    return sentences


# ─── Verb Sentence Templates ─────────────────────────────────────────

def _verb_sentence_templates(
    conj: VerbConjugation,
    pronoun_style: str = "explicit",
    supporting_words: list[str] | None = None,
) -> list[tuple[str, str, str]]:
    """Generate sentences using different tense forms of a verb.

    Args:
        conj: VerbConjugation object with all conjugated forms.
        pronoun_style: "explicit", "optional", or "none" for pronouns.
        supporting_words: Optional list of other vocabulary words to use in phrases.

    Returns list of (tense_person, armenian_sentence, english_translation).
    """
    trans = conj.translation or "___"
    supporting_words = supporting_words or []
    sentences = []

    # ── Present tense ────────────────────────────────────────────────
    # 1. Present 1sg — "I ___"
    if "1sg" in conj.present:
        arm_sent = _build_sentence(PRON_I, conj.present["1sg"], pronoun_style)
        sentences.append((
            "present 1sg",
            arm_sent,
            f"I {trans}.",
        ))

    # 2. Present 3sg — "He/she ___s"
    if "3sg" in conj.present:
        arm_sent = _build_sentence(PRON_HE, conj.present["3sg"], pronoun_style)
        sentences.append((
            "present 3sg",
            arm_sent,
            f"He/she {trans}s.",
        ))

    # 3. Present 2sg — "You ___"
    if "2sg" in conj.present:
        arm_sent = _build_sentence(PRON_YOU_SG, conj.present["2sg"], pronoun_style)
        sentences.append((
            "present 2sg",
            arm_sent,
            f"You {trans}.",
        ))

    # 4. Present 1pl — "We ___"
    if "1pl" in conj.present:
        arm_sent = _build_sentence(PRON_WE, conj.present["1pl"], pronoun_style)
        sentences.append((
            "present 1pl",
            arm_sent,
            f"We {trans}.",
        ))

    # 5. Present 3pl — "They ___"
    if "3pl" in conj.present:
        arm_sent = _build_sentence(PRON_THEY, conj.present["3pl"], pronoun_style)
        sentences.append((
            "present 3pl",
            arm_sent,
            f"They {trans}.",
        ))

    # ── Past tense ───────────────────────────────────────────────────
    # 6. Past 1sg — "I ___ed"
    if "1sg" in conj.past_aorist:
        arm_sent = _build_sentence(PRON_I, conj.past_aorist["1sg"], pronoun_style)
        sentences.append((
            "past 1sg",
            arm_sent,
            f"I {_en_past(trans)}.",
        ))

    # 7. Past 3sg — "He/she ___ed"
    if "3sg" in conj.past_aorist:
        arm_sent = _build_sentence(PRON_HE, conj.past_aorist["3sg"], pronoun_style)
        sentences.append((
            "past 3sg",
            arm_sent,
            f"He/she {_en_past(trans)}.",
        ))

    # 8. Past 1pl — "We ___ed"
    if "1pl" in conj.past_aorist:
        arm_sent = _build_sentence(PRON_WE, conj.past_aorist["1pl"], pronoun_style)
        sentences.append((
            "past 1pl",
            arm_sent,
            f"We {_en_past(trans)}.",
        ))

    # ── Future tense ─────────────────────────────────────────────────
    # 9. Future 1sg — "I will ___"
    if "1sg" in conj.future:
        arm_sent = _build_sentence(PRON_I, conj.future["1sg"], pronoun_style)
        sentences.append((
            "future 1sg",
            arm_sent,
            f"I will {trans}.",
        ))

    # 10. Future 3sg — "He/she will ___"
    if "3sg" in conj.future:
        arm_sent = _build_sentence(PRON_HE, conj.future["3sg"], pronoun_style)
        sentences.append((
            "future 3sg",
            arm_sent,
            f"He/she will {trans}.",
        ))

    # 11. Future 1pl — "We will ___"
    if "1pl" in conj.future:
        arm_sent = _build_sentence(PRON_WE, conj.future["1pl"], pronoun_style)
        sentences.append((
            "future 1pl",
            arm_sent,
            f"We will {trans}.",
        ))

    # ── Imperative ───────────────────────────────────────────────────
    # 12. Imperative 2sg — "___!"
    if conj.imperative_sg:
        arm_sent = conj.imperative_sg + "!"
        sentences.append((
            "imperative 2sg",
            arm_sent,
            f"{trans.capitalize()}!",
        ))

    # 13. Imperative 2pl — "___! (plural)"
    if conj.imperative_pl:
        arm_sent = conj.imperative_pl + "!"
        sentences.append((
            "imperative 2pl",
            arm_sent,
            f"{trans.capitalize()}! (you all)",
        ))

    # ── Imperfect ────────────────────────────────────────────────────
    # 14. Imperfect 1sg — "I was ___ing"
    if "1sg" in conj.imperfect:
        arm_sent = _build_sentence(PRON_I, conj.imperfect["1sg"], pronoun_style)
        sentences.append((
            "imperfect 1sg",
            arm_sent,
            f"I was {_en_progressive(trans)}.",
        ))

    # 15. Imperfect 3sg — "He/she was ___ing"
    if "3sg" in conj.imperfect:
        arm_sent = _build_sentence(PRON_HE, conj.imperfect["3sg"], pronoun_style)
        sentences.append((
            "imperfect 3sg",
            arm_sent,
            f"He/she was {_en_progressive(trans)}.",
        ))

    # 16. Imperfect 1pl — "We were ___ing"
    if "1pl" in conj.imperfect:
        arm_sent = _build_sentence(PRON_WE, conj.imperfect["1pl"], pronoun_style)
        sentences.append((
            "imperfect 1pl",
            arm_sent,
            f"We were {_en_progressive(trans)}.",
        ))

    return sentences


# ─── Pronoun Styling Helpers ──────────────────────────────────────────

def _format_pronoun(pronoun: str, style: str = "explicit") -> str:
    """Format a pronoun according to the desired style.

    Args:
        pronoun: Armenian pronoun (e.g., "ես", "նա").
        style: "explicit" (always shown), "optional" (in parentheses), "none" (omitted).

    Returns:
        Formatted pronoun string.
    """
    if style == "optional":
        return f"({pronoun}) "
    elif style == "none":
        return ""
    else:  # explicit (default)
        return pronoun + " "


def _build_sentence(pronoun: str, verb: str, pronoun_style: str = "explicit") -> str:
    """Build a verb sentence with pronoun styling.

    Args:
        pronoun: Armenian pronoun.
        verb: Armenian verb form.
        pronoun_style: "explicit", "optional", or "none".

    Returns:
        Complete Armenian sentence.
    """
    pron_part = _format_pronoun(pronoun, pronoun_style)
    return (pron_part + verb).rstrip()


def _romanize_sentence(armenian_sentence: str) -> str:
    """Romanize an Armenian sentence to Latin-based transliteration.

    Args:
        armenian_sentence: Armenian text (may include spaces, punctuation).

    Returns:
        Romanized Latin transliteration.
    """
    # Split on spaces to preserve structure
    words = armenian_sentence.split(" ")
    romanized_words = [romanize(w) if w else "" for w in words]
    return " ".join(romanized_words)


# ─── Sentence Pair Generation (Armenian + Romanized) ───────────────────

def generate_sentence_pair(
    armenian: str,
    english: str,
    encode_variants: bool = False,
) -> tuple[str, str] | list[tuple[str, str]]:
    """Create a sentence pair with optional encoding variants.

    Args:
        armenian: Armenian sentence.
        english: English translation.
        encode_variants: If True, return both Armenian + romanized versions.

    Returns:
        Single (armenian, english) pair, or list of pairs if encode_variants=True.
    """
    if not encode_variants:
        return (armenian, english)

    # Return both Armenian and romanized versions
    romanized = _romanize_sentence(armenian)
    return [
        (armenian, english),
        (romanized, english),
    ]


    return sentences

def generate_noun_sentences(
    word: str,
    declension_class: str = "i_class",
    translation: str = "",
    max_sentences: int = 21,
    pronoun_style: str = "explicit",
) -> list[tuple[str, str, str]]:
    """Generate example sentences demonstrating case usage for a noun.

    Args:
        word: Armenian noun (nominative singular).
        declension_class: Declension class key.
        translation: English translation.
        max_sentences: Maximum number of sentences to generate.
        pronoun_style: "explicit" (default), "optional" (with parentheses), or "none".

    Returns:
        List of (case_label, armenian_sentence, english_sentence) tuples.
    """
    decl = decline_noun(word, declension_class, translation)
    sentences = _noun_sentence_templates(decl, pronoun_style=pronoun_style)
    return sentences[:max_sentences]


def generate_verb_sentences(
    infinitive: str,
    verb_class: str = "e_class",
    translation: str = "",
    max_sentences: int = 16,
    pronoun_style: str = "explicit",
    supporting_words: list[str] | None = None,
) -> list[tuple[str, str, str]]:
    """Generate example sentences demonstrating tense usage for a verb.

    Args:
        infinitive: Armenian verb infinitive.
        verb_class: Verb class key.
        translation: English translation.
        max_sentences: Maximum number of sentences to generate.
        pronoun_style: "explicit" (default), "optional" (with parentheses), or "none".
        supporting_words: Optional list of previously-learned vocabulary to incorporate.

    Returns:
        List of (tense_label, armenian_sentence, english_sentence) tuples.
    """
    conj = conjugate_verb(infinitive, verb_class, translation)
    sentences = _verb_sentence_templates(
        conj,
        pronoun_style=pronoun_style,
        supporting_words=supporting_words or [],
    )
    return sentences[:max_sentences]
