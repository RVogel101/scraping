"""
Sentence progression system for Armenian learning.

Implements a scaffolded approach where sentences are introduced in order of
complexity and grammar concept. This ensures learners interact with one
grammar concept at a time, building progressively through levels.

Example progression:
  Level 1, Batch 1-2: Simple articles & copula ("the X is...", "a X is...")
  Level 1, Batch 3-4: Basic transitive verbs ("I see the X", "I have the X")
  Level 1, Batch 5: Simple nominative contexts
  Level 2, Batch 1-2: Introduce accusative case
  Level 2, Batch 3-4: Introduce genitive-dative
  ... etc
"""

from dataclasses import dataclass
from typing import Literal

# ─── Sentence Complexity Tiers ────────────────────────────────────────
#
# Each tier represents a group of related grammar concepts organized by
# cognitive load and pedagogical sequencing.

TIER_SCAFFOLDING = "scaffolding"      # Definite article + simple copula
TIER_ARTICLES = "articles"             # Indefinite article constructions
TIER_BASIC_TRANSITIVE = "basic_transitive"  # Simple action verbs (see, have, want, love)
TIER_NOMINATIVE = "nominative"         # Nominative case contexts
TIER_ACCUSATIVE = "accusative"         # Accusative (object) case
TIER_GENITIVE_DATIVE = "genitive_dative"  # Possessive/recipient contexts
TIER_ABLATIVE = "ablative"             # Source/origin contexts
TIER_INSTRUMENTAL = "instrumental"     # Tool/means contexts
TIER_PLURAL = "plural"                 # Plural nominative
TIER_VERB_PRESENT = "verb_present"     # Present tense conjugations
TIER_VERB_PAST = "verb_past"           # Past tense conjugations
TIER_VERB_FUTURE = "verb_future"       # Future tense conjugations
TIER_VERB_IMPERATIVE = "verb_imperative"  # Imperative mood
TIER_VERB_IMPERFECT = "verb_imperfect"     # Imperfect tense

# Maps from sentence form labels (produced by sentence_generator) to tiers
FORM_LABEL_TO_TIER = {
    # Noun cases (nouns)
    "nominative": TIER_NOMINATIVE,
    "nominative (indefinite)": TIER_ARTICLES,
    "accusative": TIER_ACCUSATIVE,
    "genitive-dative": TIER_GENITIVE_DATIVE,
    "ablative": TIER_ABLATIVE,
    "instrumental": TIER_INSTRUMENTAL,
    "plural nominative": TIER_PLURAL,
    
    # Verb tenses
    "present 1sg": TIER_VERB_PRESENT,
    "present 3sg": TIER_VERB_PRESENT,
    "present 1pl": TIER_VERB_PRESENT,
    "past 1sg": TIER_VERB_PAST,
    "past 3sg": TIER_VERB_PAST,
    "future 1sg": TIER_VERB_FUTURE,
    "imperative 2sg": TIER_VERB_IMPERATIVE,
    "imperfect 1sg": TIER_VERB_IMPERFECT,
}

# Progressive introduction sequence: which tiers become available at each level
# Format: level -> set of available tiers (cumulative)
AVAILABLE_TIERS_BY_LEVEL = {
    1: {TIER_ARTICLES, TIER_NOMINATIVE},
    2: {TIER_ARTICLES, TIER_NOMINATIVE, TIER_ACCUSATIVE},
    3: {TIER_ARTICLES, TIER_NOMINATIVE, TIER_ACCUSATIVE, TIER_GENITIVE_DATIVE},
    4: {TIER_ARTICLES, TIER_NOMINATIVE, TIER_ACCUSATIVE, TIER_GENITIVE_DATIVE, TIER_ABLATIVE},
    5: {TIER_ARTICLES, TIER_NOMINATIVE, TIER_ACCUSATIVE, TIER_GENITIVE_DATIVE, TIER_ABLATIVE, TIER_INSTRUMENTAL, TIER_PLURAL},
}

# Fallback: if tier not explicitly defined for a level, use the highest available
def _fill_missing_tiers() -> dict:
    """Extend AVAILABLE_TIERS_BY_LEVEL to cover all 20 levels."""
    result = dict(AVAILABLE_TIERS_BY_LEVEL)
    last_tiers = AVAILABLE_TIERS_BY_LEVEL.get(5, set())
    
    # Levels 6-10: Add verb tenses
    for level in range(6, 11):
        result[level] = last_tiers | {TIER_VERB_PRESENT, TIER_VERB_PAST}
    
    # Levels 11-15: Add future and imperative
    for level in range(11, 16):
        result[level] = result[10] | {TIER_VERB_FUTURE, TIER_VERB_IMPERATIVE}
    
    # Levels 16-20: Add imperfect and advanced
    for level in range(16, 21):
        result[level] = result[15] | {TIER_VERB_IMPERFECT}
    
    return result

AVAILABLE_TIERS_BY_LEVEL = _fill_missing_tiers()


# ─── Tier Ordering (within a level) ──────────────────────────────────
#
# When multiple tiers are available at a level, which order should they
# be introduced? (Lower index = introduced first)

TIER_INTRODUCTION_ORDER = [
    TIER_ARTICLES,
    TIER_NOMINATIVE,
    TIER_ACCUSATIVE,
    TIER_GENITIVE_DATIVE,
    TIER_ABLATIVE,
    TIER_INSTRUMENTAL,
    TIER_PLURAL,
    TIER_VERB_PRESENT,
    TIER_VERB_PAST,
    TIER_VERB_FUTURE,
    TIER_VERB_IMPERATIVE,
    TIER_VERB_IMPERFECT,
]


@dataclass
class SentenceProgressionConfig:
    """Configuration for sentence progression."""
    
    enable_progression: bool = True
    """Whether to enforce sentence progression (True) or use all at once (False)."""
    
    sentences_per_tier: int = 2
    """How many different grammar concepts (tiers) to expose per word.
    
    Examples:
    - 1: Each word teaches one grammar concept (strict)
    - 2: Each word teaches 2 concepts (default, balanced)
    - 3+: More concepts per word (faster progression)
    """
    
    sentences_per_concept: int | None = None
    """How many sentence examples for each grammar concept. 
    Default None means "use all available sentences for that tier."
    """


def get_available_tiers_at_level(level: int) -> set[str]:
    """Return the set of tiers available at a given level."""
    return AVAILABLE_TIERS_BY_LEVEL.get(level, AVAILABLE_TIERS_BY_LEVEL.get(20, set()))


def get_form_tier(form_label: str) -> str | None:
    """Map a sentence form label to its tier, or None if not found."""
    # Normalize the label
    form_lower = form_label.lower().strip()
    
    # Try exact match first
    if form_lower in FORM_LABEL_TO_TIER:
        return FORM_LABEL_TO_TIER[form_lower]
    
    # Try substring match (e.g., "present" in "present 1sg")
    for label, tier in FORM_LABEL_TO_TIER.items():
        if label in form_lower or form_lower in label:
            return tier
    
    return None


def select_sentences_for_progression(
    all_sentences: list[tuple[str, str, str]],  # (form_label, arm, eng)
    level: int,
    progression_config: SentenceProgressionConfig,
) -> list[tuple[str, str, str]]:
    """
    Select sentences to use based on progression rules.
    
    Args:
        all_sentences: All generated sentences from sentence_generator.
        level: The current level (1-20).
        progression_config: Progression settings.
    
    Returns:
        Filtered list of sentences appropriate for this level/stage.
    """
    if not progression_config.enable_progression:
        # No progression: use all sentences
        return all_sentences
    
    # Get available tiers at this level
    available = get_available_tiers_at_level(level)
    
    # Categorize sentences by tier
    sentences_by_tier: dict[str, list[tuple[str, str, str]]] = {}
    untiered: list[tuple[str, str, str]] = []
    
    for form_label, arm, eng in all_sentences:
        tier = get_form_tier(form_label)
        if tier is None:
            untiered.append((form_label, arm, eng))
        else:
            if tier not in sentences_by_tier:
                sentences_by_tier[tier] = []
            sentences_by_tier[tier].append((form_label, arm, eng))
    
    # Select from available tiers, in order of introduction
    selected = []
    tiers_used = 0
    
    for tier in TIER_INTRODUCTION_ORDER:
        if tiers_used >= progression_config.sentences_per_tier:
            break
        if tier not in available:
            continue
        if tier not in sentences_by_tier:
            continue
        
        # Add sentences from this tier
        tier_sentences = sentences_by_tier[tier]
        if progression_config.sentences_per_concept:
            tier_sentences = tier_sentences[:progression_config.sentences_per_concept]
        
        selected.extend(tier_sentences)
        tiers_used += 1
    
    # Always include untiered sentences (fallback)
    selected.extend(untiered)
    
    return selected


def format_tier_for_grammar_type(tier: str) -> str:
    """Convert a tier name to a grammar_type string for progression system."""
    # Simple mapping: tier name to grammar type
    mapping = {
        TIER_ARTICLES: "indefinite_article",
        TIER_NOMINATIVE: "nominative_subject",
        TIER_ACCUSATIVE: "accusative_object",
        TIER_GENITIVE_DATIVE: "genitive_dative",
        TIER_ABLATIVE: "ablative",
        TIER_INSTRUMENTAL: "instrumental",
        TIER_PLURAL: "plural",
        TIER_VERB_PRESENT: "present_tense",
        TIER_VERB_PAST: "past_tense",
        TIER_VERB_FUTURE: "future_tense",
        TIER_VERB_IMPERATIVE: "imperative",
        TIER_VERB_IMPERFECT: "imperfect_tense",
    }
    return mapping.get(tier, tier)
