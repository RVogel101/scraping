"""
Nayiri.com dictionary scraper for Western Armenian headwords and definitions.

Scrapes the Hayerēn-Hayerēn (Armenian-Armenian) and Hayerēn-Angleren
(Armenian-English) dictionaries from nayiri.com to build a headword list
with definitions/translations.

Uses Selenium since nayiri.com renders content dynamically.
Rate-limited to respect the server.

Usage:
    python -m wa_corpus.nayiri_scraper [--output-dir DIR] [--start-letter LETTER]
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from pathlib import Path
from urllib import robotparser

from selenium.webdriver.chrome.options import Options
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────

DEFAULT_OUTPUT_DIR = Path("wa_corpus/data/nayiri")

# Dictionary types on nayiri.com (confirmed via site scraping)
DICT_TYPES = {
    "explanatory": "HY_HY",     # Armenian-Armenian explanatory (WA)
    "arm_eng": "HY_EN",          # Armenian → English
}

# Base search URL — HTTP only; HTTPS has SSL issues
NAYIRI_SEARCH_URL = "http://nayiri.com/search?l=hy_LB&dt={dict_type}&query={query}"
NAYIRI_BROWSE_URL = "http://nayiri.com/imagepage.php?dt={dict_type}&p={page}"

# Armenian lowercase alphabet via Unicode range: ա (U+0561) through ֆ (U+0586)
ARMENIAN_LOWER = [chr(c) for c in range(0x0561, 0x0587)]  # 38 letters

# Conservative defaults to reduce request pressure and ban risk.
REQUEST_DELAY_MIN = 2.5
REQUEST_DELAY_MAX = 4.5
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0
COOLDOWN_EVERY = 60
COOLDOWN_SECONDS = 20.0
USER_AGENT = "ArmenianCorpusResearchBot/1.0 (respectful scraping for linguistic research)"


# ─── Browser Setup ───────────────────────────────────────────────────

def _create_driver() -> Chrome:
    """Create a headless Chrome driver."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(f"--user-agent={USER_AGENT}")

    driver = Chrome(options=options)  # type: ignore[operator]
    return driver


def _is_allowed_by_robots() -> bool:
    """Check whether Nayiri allows crawling via robots.txt."""
    parser = robotparser.RobotFileParser()
    parser.set_url("http://nayiri.com/robots.txt")
    try:
        parser.read()
    except Exception as exc:
        logger.warning("Could not read robots.txt (%s); continuing cautiously", exc)
        return True

    allowed = parser.can_fetch(USER_AGENT, "/search")
    if not allowed:
        allowed = parser.can_fetch("*", "/search")
    return allowed


class PoliteNavigator:
    """Coordinates request pacing, cooldown, and retries."""

    def __init__(
        self,
        driver: Chrome,
        delay_min: float,
        delay_max: float,
        max_retries: int,
        retry_backoff: float,
        cooldown_every: int,
        cooldown_seconds: float,
    ):
        self.driver = driver
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.cooldown_every = cooldown_every
        self.cooldown_seconds = cooldown_seconds
        self.request_count = 0

    def _sleep_between_requests(self) -> None:
        delay = random.uniform(self.delay_min, self.delay_max)
        time.sleep(delay)

        if self.cooldown_every > 0 and self.request_count % self.cooldown_every == 0:
            logger.info(
                "Polite cooldown after %d requests: %.1fs",
                self.request_count,
                self.cooldown_seconds,
            )
            time.sleep(self.cooldown_seconds)

    def get(self, url: str) -> bool:
        for attempt in range(1, self.max_retries + 1):
            try:
                self.driver.get(url)
                self.request_count += 1
                self._sleep_between_requests()
                return True
            except Exception as exc:
                if attempt == self.max_retries:
                    logger.warning("Request failed after %d attempts: %s", attempt, url)
                    logger.debug("Last request error: %s", exc)
                    return False
                backoff = self.retry_backoff ** attempt
                logger.info(
                    "Transient fetch failure (%s). Retrying in %.1fs (%d/%d)",
                    type(exc).__name__,
                    backoff,
                    attempt,
                    self.max_retries,
                )
                time.sleep(backoff)
        return False


# ─── Dictionary Entry Extraction ─────────────────────────────────────

def _extract_entries_from_page(driver: Chrome) -> list[dict]:
    """Extract dictionary entries from the current Nayiri page.

    Returns list of dicts with 'headword', 'definition', 'pos' (if available).
    """
    entries: list[dict] = []

    # Nayiri renders entries in divs with specific classes
    # Try multiple selectors since the layout may vary
    selectors = [
        ".dict-result",
        ".search-result",
        ".result-entry",
        "[class*='result']",
        ".dictionary-entry",
    ]

    result_elements = []
    for sel in selectors:
        result_elements = driver.find_elements(By.CSS_SELECTOR, sel)
        if result_elements:
            break

    if not result_elements:
        # Fallback: look for bold headwords followed by definitions
        # Many dictionary sites use <b> or <strong> for headwords
        page_text = driver.find_element(By.TAG_NAME, "body").text
        # Parse headword-definition pairs from text
        lines = page_text.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Heuristic: headword is typically the first Armenian word
            arm_match = re.match(r"^([\u0561-\u0587]+)\s+(.+)", line)
            if arm_match:
                entries.append({
                    "headword": arm_match.group(1),
                    "definition": arm_match.group(2),
                    "pos": "",
                })
        return entries

    for elem in result_elements:
        try:
            text = elem.text.strip()
            if not text:
                continue

            # Extract headword (typically bold or in a specific sub-element)
            headword = ""
            try:
                hw_elem = elem.find_element(By.CSS_SELECTOR, "b, strong, .headword, .dict-headword")
                headword = hw_elem.text.strip()
            except Exception:
                # First word of the entry
                words = text.split()
                if words:
                    headword = words[0]

            # Extract POS if present (typically in parentheses or italic)
            pos = ""
            try:
                pos_elem = elem.find_element(By.CSS_SELECTOR, "i, em, .pos")
                pos_text = pos_elem.text.strip()
                if pos_text in ("գ.", "ա.", "բ.", "մ.", " delays.", "ածdelays.", "burgh.",
                                "noun", "verb", "adj", "adv"):
                    pos = pos_text
            except Exception:
                pass

            # Definition is everything after the headword
            definition = text
            if headword and headword in text:
                definition = text[text.index(headword) + len(headword):].strip()

            if headword and re.match(r"[\u0561-\u0587]", headword):
                entries.append({
                    "headword": headword,
                    "definition": definition[:500],  # truncate very long defs
                    "pos": pos,
                })
        except Exception:
            continue

    return entries


# ─── Search-Based Scraping ───────────────────────────────────────────

def search_letter(
    navigator: PoliteNavigator,
    letter: str,
    dict_type: str = "HaysttseainBararan",
) -> list[dict]:
    """Search for all words starting with a given Armenian letter.

    Uses the Nayiri search with a single-letter query, which returns
    a paginated list of matching headwords.
    """
    entries: list[dict] = []

    url = NAYIRI_SEARCH_URL.format(dict_type=dict_type, query=letter)
    logger.info("Searching letter '%s': %s", letter, url)

    try:
        if not navigator.get(url):
            logger.warning("Failed to load search for letter '%s'", letter)
            return entries
        driver = navigator.driver
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(1.5)  # Allow dynamic content to render
    except Exception:
        logger.warning("Failed to load search for letter '%s'", letter)
        return entries

    # Extract entries from initial results
    page_entries = _extract_entries_from_page(driver)
    entries.extend(page_entries)
    logger.info("  Letter '%s': %d entries from first page", letter, len(page_entries))

    # Check for word list / suggestion list
    # Nayiri often shows a list of matching headwords on the left
    try:
        word_list_items = driver.find_elements(
            By.CSS_SELECTOR, ".word-list a, .word-list li, #wordlist a, .suggestions a"
        )
        for item in word_list_items:
            word = item.text.strip()
            if word and re.match(r"[\u0561-\u0587]", word):
                # Check if we already have this headword
                existing = {e["headword"] for e in entries}
                if word not in existing:
                    entries.append({
                        "headword": word,
                        "definition": "",
                        "pos": "",
                    })
    except Exception:
        pass

    return entries


def search_two_letter_prefixes(
    navigator: PoliteNavigator,
    letter: str,
    dict_type: str = "HaysttseainBararan",
) -> list[dict]:
    """Search with two-letter prefixes to get more complete results.

    Single-letter searches may be truncated; this iterates through
    all two-letter combinations starting with the given letter.
    """
    entries: list[dict] = []
    seen_headwords: set[str] = set()

    for second_letter in ARMENIAN_LOWER:
        prefix = letter + second_letter
        url = NAYIRI_SEARCH_URL.format(dict_type=dict_type, query=prefix)

        if not navigator.get(url):
            continue

        driver = navigator.driver
        page_entries = _extract_entries_from_page(driver)

        new_count = 0
        for entry in page_entries:
            if entry["headword"] not in seen_headwords:
                seen_headwords.add(entry["headword"])
                entries.append(entry)
                new_count += 1

        if new_count > 0:
            logger.debug("  Prefix '%s': %d new entries", prefix, new_count)

    logger.info("  Letter '%s': %d total entries via 2-letter prefixes",
                letter, len(entries))
    return entries


# ─── Checkpoint / Resume ─────────────────────────────────────────────

def _load_checkpoint(output_dir: Path) -> tuple[set[str], dict[str, dict]]:
    """Load previously scraped dictionary entries."""
    checkpoint_file = output_dir / "dictionary.jsonl"
    seen: set[str] = set()
    entries: dict[str, dict] = {}

    if checkpoint_file.exists():
        with open(checkpoint_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entry = json.loads(line)
                    hw = entry.get("headword", "")
                    if hw:
                        seen.add(hw)
                        entries[hw] = entry

        logger.info("Loaded %d previously scraped entries", len(entries))

    return seen, entries


def _save_entries(output_dir: Path, entries: list[dict]) -> None:
    """Append entries to the checkpoint file."""
    checkpoint_file = output_dir / "dictionary.jsonl"
    with open(checkpoint_file, "a", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ─── English Translation Scraping ────────────────────────────────────

def enrich_with_translations(
    navigator: PoliteNavigator,
    entries: dict[str, dict],
    output_dir: Path,
) -> None:
    """Look up Armenian-English translations for headwords that lack them.

    Queries the Armenian-English dictionary on Nayiri for each headword.
    """
    dict_type = DICT_TYPES["arm_eng"]
    enriched_count = 0

    # Filter to entries without English translations
    to_translate = [
        hw for hw, entry in entries.items()
        if not entry.get("english", "")
    ]

    logger.info("Looking up English translations for %d headwords", len(to_translate))

    for i, hw in enumerate(to_translate, 1):
        if i % 100 == 0:
            logger.info("  Translation progress: %d/%d", i, len(to_translate))

        url = NAYIRI_SEARCH_URL.format(dict_type=dict_type, query=hw)

        try:
            if not navigator.get(url):
                continue
            driver = navigator.driver

            # Look for English text in the result
            body_text = driver.find_element(By.TAG_NAME, "body").text
            # Extract English words/phrases (Latin characters)
            english_parts = re.findall(r"[A-Za-z][A-Za-z\s,;'-]{2,}", body_text)

            if english_parts:
                # Take the first substantial English phrase as the translation
                translation = "; ".join(english_parts[:3]).strip()
                entries[hw]["english"] = translation[:200]
                enriched_count += 1

        except Exception:
            continue

    logger.info("Enriched %d entries with English translations", enriched_count)

    # Save enriched entries
    output_file = output_dir / "dictionary_enriched.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


# ─── Main Pipeline ───────────────────────────────────────────────────

def scrape_nayiri(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    start_letter_idx: int = 0,
    max_letters: int | None = None,
    use_two_letter: bool = True,
    enrich_english: bool = True,
    delay_min: float = REQUEST_DELAY_MIN,
    delay_max: float = REQUEST_DELAY_MAX,
    max_retries: int = MAX_RETRIES,
    cooldown_every: int = COOLDOWN_EVERY,
    cooldown_seconds: float = COOLDOWN_SECONDS,
    check_robots: bool = True,
) -> dict[str, dict]:
    """Run the full Nayiri dictionary scraping pipeline.

    Returns dict mapping headword → entry dict.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    seen, entries = _load_checkpoint(output_dir)

    if check_robots and not _is_allowed_by_robots():
        raise RuntimeError(
            "robots.txt disallows /search for this scraper user-agent; "
            "set check_robots=False only if you have explicit permission"
        )

    driver = _create_driver()
    navigator = PoliteNavigator(
        driver=driver,
        delay_min=delay_min,
        delay_max=delay_max,
        max_retries=max_retries,
        retry_backoff=RETRY_BACKOFF,
        cooldown_every=cooldown_every,
        cooldown_seconds=cooldown_seconds,
    )
    try:
        processed_letters = 0

        # Scrape headwords letter by letter
        for idx, letter in enumerate(ARMENIAN_LOWER):
            if idx < start_letter_idx:
                continue

            if max_letters is not None and processed_letters >= max_letters:
                logger.info("Reached max_letters=%d; stopping this batch", max_letters)
                break

            logger.info("═══ Letter %d/%d: %s ═══", idx + 1, len(ARMENIAN_LOWER), letter)

            if use_two_letter:
                new_entries = search_two_letter_prefixes(navigator, letter)
            else:
                new_entries = search_letter(navigator, letter)

            # Filter to truly new entries
            novel = [e for e in new_entries if e["headword"] not in seen]
            if novel:
                _save_entries(output_dir, novel)
                for e in novel:
                    seen.add(e["headword"])
                    entries[e["headword"]] = e

            logger.info("  New: %d, Total: %d", len(novel), len(entries))
            processed_letters += 1

        # Optionally enrich with English translations
        if enrich_english:
            enrich_with_translations(navigator, entries, output_dir)

    finally:
        driver.quit()

    # Save final consolidated dictionary
    output_file = output_dir / "dictionary_full.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    logger.info("Dictionary scraping complete: %d headwords", len(entries))
    return entries


def load_nayiri_headwords(output_dir: Path = DEFAULT_OUTPUT_DIR) -> set[str]:
    """Load the set of known headwords from a previous scrape."""
    seen, _ = _load_checkpoint(output_dir)
    return seen


def load_nayiri_dictionary(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, dict]:
    """Load the full dictionary from a previous scrape."""
    dict_file = output_dir / "dictionary_full.json"
    if dict_file.exists():
        with open(dict_file, "r", encoding="utf-8") as f:
            return json.load(f)
    # Fall back to checkpoint
    _, entries = _load_checkpoint(output_dir)
    return entries


# ─── CLI ──────────────────────────────────────────────────────────────

def main():
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Scrape Nayiri Armenian dictionary")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--start-letter", type=int, default=0,
                        help="Index of letter to start from (0-based, for resume)")
    parser.add_argument("--max-letters", type=int, default=None,
                        help="Process at most N letters in this run (for small batches)")
    parser.add_argument("--no-two-letter", action="store_true",
                        help="Use single-letter search only (faster, less complete)")
    parser.add_argument("--no-english", action="store_true",
                        help="Skip English translation enrichment")
    parser.add_argument("--delay-min", type=float, default=REQUEST_DELAY_MIN,
                        help="Minimum delay between requests in seconds")
    parser.add_argument("--delay-max", type=float, default=REQUEST_DELAY_MAX,
                        help="Maximum delay between requests in seconds")
    parser.add_argument("--max-retries", type=int, default=MAX_RETRIES,
                        help="Retries for failed page loads")
    parser.add_argument("--cooldown-every", type=int, default=COOLDOWN_EVERY,
                        help="Take a long pause every N requests (0 disables)")
    parser.add_argument("--cooldown-seconds", type=float, default=COOLDOWN_SECONDS,
                        help="Length of periodic cooldown pauses in seconds")
    parser.add_argument("--ignore-robots", action="store_true",
                        help="Skip robots.txt check (only use with explicit permission)")
    args = parser.parse_args()

    if args.delay_min <= 0 or args.delay_max <= 0 or args.delay_max < args.delay_min:
        parser.error("Invalid delay range: require 0 < delay-min <= delay-max")
    if args.max_letters is not None and args.max_letters < 1:
        parser.error("--max-letters must be >= 1")
    if args.max_retries < 1:
        parser.error("--max-retries must be >= 1")
    if args.cooldown_every < 0:
        parser.error("--cooldown-every must be >= 0")
    if args.cooldown_seconds < 0:
        parser.error("--cooldown-seconds must be >= 0")

    entries = scrape_nayiri(
        output_dir=args.output_dir,
        start_letter_idx=args.start_letter,
        max_letters=args.max_letters,
        use_two_letter=not args.no_two_letter,
        enrich_english=not args.no_english,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
        max_retries=args.max_retries,
        cooldown_every=args.cooldown_every,
        cooldown_seconds=args.cooldown_seconds,
        check_robots=not args.ignore_robots,
    )

    print(f"\nTotal headwords: {len(entries):,}")
    # Show sample
    sample = list(entries.values())[:10]
    for e in sample:
        line = f"  {e['headword']}: {e.get('definition', '')[:60]}..."
        encoding = sys.stdout.encoding or "utf-8"
        print(line.encode(encoding, errors="replace").decode(encoding, errors="replace"))


if __name__ == "__main__":
    main()
