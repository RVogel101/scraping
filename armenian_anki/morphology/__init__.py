"""Armenian morphology sub-package."""

from .core import ARM, VOWELS, is_vowel, ends_in_vowel
from .nouns import decline_noun, NounDeclension, DECLENSION_CLASSES
from .verbs import conjugate_verb, VerbConjugation, VERB_CLASSES
from .articles import add_definite, add_indefinite

__all__ = [
    "ARM", "VOWELS", "is_vowel", "ends_in_vowel",
    "decline_noun", "NounDeclension", "DECLENSION_CLASSES",
    "conjugate_verb", "VerbConjugation", "VERB_CLASSES",
    "add_definite", "add_indefinite",
]
