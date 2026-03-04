#!/usr/bin/env python3
"""
Generate Armenian Letter Cards for Anki

Creates flashcards for all 38 letters of the Western Armenian alphabet
with pronunciation, IPA transcription, examples, and difficulty ratings.

Usage:
    python generate_letter_cards.py                    # Generate all letters
    python generate_letter_cards.py --difficulty 3     # Only difficult letters (3+)
    python generate_letter_cards.py --vowels-only      # Only vowel letters
    python generate_letter_cards.py --consonants-only  # Only consonant letters
    python generate_letter_cards.py --local-only       # Save to DB only, don't push to Anki
    python generate_letter_cards.py --deck "Armenian::Letters::Basic"  # Custom deck

Prerequisites:
  1. Anki desktop running with AnkiConnect plugin (if pushing to Anki)
  2. Python packages: requests (for AnkiConnect)

Examples:
    # Generate all letter cards
    python generate_letter_cards.py

    # Generate only difficult pronunciation letters (ղ, խ, ռ, etc.)
    python generate_letter_cards.py --difficulty 3

    # Test locally without Anki
    python generate_letter_cards.py --local-only
"""

import argparse
import logging
import sys
from pathlib import Path

# Add 02-src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / '02-src'))

# Ensure Armenian Unicode prints correctly on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf-8-sig"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from lousardzag.card_generator import CardGenerator
from lousardzag import letter_data
from lousardzag.anki_connect import AnkiConnectError
from lousardzag.config import LETTER_CARDS_DECK

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Generate Armenian letter flashcards",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--difficulty",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="Only generate cards for letters with difficulty >= this value (1-5)"
    )
    parser.add_argument(
        "--vowels-only",
        action="store_true",
        help="Generate cards only for vowel letters"
    )
    parser.add_argument(
        "--consonants-only",
        action="store_true",
        help="Generate cards only for consonant letters"
    )
    parser.add_argument(
        "--deck",
        type=str,
        default=LETTER_CARDS_DECK,
        help=f"Target Anki deck (default: {LETTER_CARDS_DECK})"
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Save to local database only, don't push to Anki"
    )
    parser.add_argument(
        "--letters",
        type=str,
        help="Specific letters to generate (e.g., 'ա,բ,գ' or 'աբգդ')"
    )
    parser.add_argument(
        "--list-letters",
        action="store_true",
        help="List all Armenian letters with their properties and exit"
    )
    
    args = parser.parse_args()
    
    # Handle --list-letters option
    if args.list_letters:
        print_letter_list()
        return 0
    
    # Validate conflicting options
    if args.vowels_only and args.consonants_only:
        logger.error("Cannot specify both --vowels-only and --consonants-only")
        return 1
    
    # Initialize card generator
    try:
        generator = CardGenerator()
        
        if not args.local_only:
            logger.info("Setting up Anki models and decks...")
            generator.setup_models()
            generator.setup_decks()
            logger.info("✓ Anki setup complete")
        else:
            logger.info("Running in local-only mode (no Anki connection)")
        
    except AnkiConnectError as e:
        logger.error(f"Failed to connect to Anki: {e}")
        logger.error("Make sure Anki is running with the AnkiConnect add-on")
        return 1
    
    # Determine which letters to generate
    if args.letters:
        # Parse specific letters
        letters_input = args.letters.replace(",", "").replace(" ", "")
        letters_to_generate = list(letters_input)
        logger.info(f"Generating cards for {len(letters_to_generate)} specific letters")
    elif args.vowels_only:
        letters_to_generate = letter_data.get_all_vowels()
        logger.info(f"Generating cards for {len(letters_to_generate)} vowel letters")
    elif args.consonants_only:
        letters_to_generate = letter_data.get_all_consonants()
        logger.info(f"Generating cards for {len(letters_to_generate)} consonant letters")
    else:
        letters_to_generate = letter_data.get_all_letters_ordered()
        logger.info(f"Generating cards for all {len(letters_to_generate)} Armenian letters")
    
    # Apply difficulty filter if specified
    if args.difficulty:
        original_count = len(letters_to_generate)
        letters_to_generate = [
            letter for letter in letters_to_generate
            if letter_data.get_letter_info(letter)["difficulty"] >= args.difficulty
        ]
        logger.info(f"Filtered to {len(letters_to_generate)}/{original_count} letters with difficulty >= {args.difficulty}")
    
    # Generate cards
    logger.info("\n" + "="*60)
    logger.info("Starting letter card generation...")
    logger.info("="*60 + "\n")
    
    note_ids = []
    success_count = 0
    failed_letters = []
    
    for letter in letters_to_generate:
        letter_info = letter_data.get_letter_info(letter)
        if not letter_info:
            logger.warning(f"No data found for letter: {letter}")
            failed_letters.append(letter)
            continue
        
        try:
            note_id = generator.generate_letter_card(
                letter=letter,
                deck=args.deck,
                push_to_anki=not args.local_only,
            )
            
            if note_id:
                note_ids.append(note_id)
                success_count += 1
                logger.info(
                    f"✓ {letter} ({letter_info['name']}) — "
                    f"Difficulty: {letter_info['difficulty']}/5, "
                    f"Type: {letter_info['type']}"
                )
            else:
                logger.warning(f"✗ Failed to create card for: {letter}")
                failed_letters.append(letter)
                
        except Exception as e:
            logger.error(f"✗ Error generating card for {letter}: {e}")
            failed_letters.append(letter)
    
    # Print summary
    logger.info("\n" + "="*60)
    logger.info("GENERATION COMPLETE")
    logger.info("="*60)
    logger.info(f"✓ Successfully created: {success_count} cards")
    if failed_letters:
        logger.warning(f"✗ Failed: {len(failed_letters)} letters: {', '.join(failed_letters)}")
    logger.info(f"Deck: {args.deck}")
    if args.local_only:
        logger.info("Mode: Local database only (not pushed to Anki)")
    else:
        logger.info("Mode: Pushed to Anki")
    logger.info("="*60 + "\n")
    
    return 0 if not failed_letters else 1


def print_letter_list():
    """Print a formatted list of all Armenian letters with their properties."""
    print("\n" + "="*80)
    print("WESTERN ARMENIAN ALPHABET — 38 LETTERS")
    print("="*80 + "\n")
    
    all_letters = letter_data.get_all_letters_ordered()
    
    # Group by type
    vowels = letter_data.get_all_vowels()
    consonants = letter_data.get_all_consonants()
    
    print(f"Total: {len(all_letters)} letters")
    print(f"  - Vowels: {len(vowels)}")
    print(f"  - Consonants: {len(consonants)}")
    print()
    
    # Print header
    print(f"{'#':<4} {'Letter':<8} {'Name':<12} {'IPA':<10} {'English':<12} {'Type':<10} {'Diff':<6}")
    print("-" * 80)
    
    # Print each letter
    for letter in all_letters:
        info = letter_data.get_letter_info(letter)
        if info:
            position = info['position']
            name = info['name']
            ipa = info['ipa']
            english = info['english']
            letter_type = info['type']
            difficulty = info['difficulty']
            
            # Format display
            letter_display = f"{info['uppercase']}/{info['lowercase']}"
            
            print(
                f"{position:<4} "
                f"{letter_display:<8} "
                f"{name:<12} "
                f"{ipa:<10} "
                f"{english:<12} "
                f"{letter_type:<10} "
                f"{difficulty}/5"
            )
    
    print("\n" + "="*80)
    print("\nDifficulty ratings:")
    print("  1 = Easy (similar to English)")
    print("  2 = Moderate (requires practice)")
    print("  3 = Challenging (different from English)")
    print("  4 = Very difficult (no English equivalent)")
    print("  5 = Extremely difficult")
    print("\nWestern Armenian has reversed voicing for: բ, գ, դ, պ, տ, կ, ճ, ջ, ծ")
    print("="*80 + "\n")


if __name__ == "__main__":
    sys.exit(main())
