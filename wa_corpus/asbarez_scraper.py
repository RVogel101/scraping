"""
Asbarez newspaper scraper for Western Armenian text.

Scrapes Armenian-language articles from asbarez.com, the largest
Los Angeles-based Western Armenian daily newspaper.

Uses Selenium to handle JavaScript rendering and Cloudflare protection.
Rate-limited to be respectful of the server.

Usage:
    python -m wa_corpus.asbarez_scraper [--max-pages N] [--output-dir DIR]
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────

ASBAREZ_HAY_URL = "https://asbarez.com/hay/"
ASBAREZ_BASE = "https://asbarez.com"
DEFAULT_OUTPUT_DIR = Path("wa_corpus/data/asbarez")

# Rate limiting: seconds between requests
REQUEST_DELAY = 2.0

# Max pages of article listings to crawl (each page has ~10 articles)
DEFAULT_MAX_LISTING_PAGES = 50


# ─── Browser Setup ───────────────────────────────────────────────────

def _create_driver() -> webdriver.Chrome:
    """Create a headless Chrome driver with stealth-friendly options."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    # Disable automation flags
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    # Remove webdriver flag
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver


# ─── Article Link Collection ─────────────────────────────────────────

def collect_article_urls(
    driver: webdriver.Chrome,
    max_listing_pages: int = DEFAULT_MAX_LISTING_PAGES,
) -> list[str]:
    """Collect article URLs from the Armenian section listing pages.

    Returns deduplicated list of article URLs.
    """
    urls: list[str] = []
    seen: set[str] = set()

    for page_num in range(1, max_listing_pages + 1):
        if page_num == 1:
            url = ASBAREZ_HAY_URL
        else:
            url = f"{ASBAREZ_HAY_URL}page/{page_num}/"

        logger.info("Fetching listing page %d: %s", page_num, url)

        try:
            driver.get(url)
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "article"))
            )
        except Exception:
            logger.warning("Could not load listing page %d, stopping.", page_num)
            break

        # Extract article links - Asbarez uses <article> tags or <h2> with links
        links = driver.find_elements(By.CSS_SELECTOR, "article a, h2.entry-title a")

        new_count = 0
        for link in links:
            href = link.get_attribute("href")
            if href and href.startswith(ASBAREZ_BASE) and href not in seen:
                # Filter: only Armenian articles (typically under /hay/ or contain Armenian text)
                seen.add(href)
                urls.append(href)
                new_count += 1

        logger.info("  Found %d new article links (total: %d)", new_count, len(urls))

        if new_count == 0:
            logger.info("  No new links found, stopping pagination.")
            break

        time.sleep(REQUEST_DELAY)

    return urls


# ─── Article Text Extraction ─────────────────────────────────────────

def extract_article_text(driver: webdriver.Chrome, url: str) -> dict | None:
    """Extract the article title and body text from an Asbarez article page.

    Returns dict with 'url', 'title', 'text', 'date' or None on failure.
    """
    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".entry-content, article"))
        )
    except Exception:
        logger.warning("Failed to load article: %s", url)
        return None

    # Title
    title = ""
    try:
        title_elem = driver.find_element(By.CSS_SELECTOR, "h1.entry-title, h1")
        title = title_elem.text.strip()
    except Exception:
        pass

    # Date
    date_str = ""
    try:
        date_elem = driver.find_element(By.CSS_SELECTOR, "time, .entry-date")
        date_str = date_elem.get_attribute("datetime") or date_elem.text.strip()
    except Exception:
        pass

    # Body text
    body = ""
    try:
        content_elem = driver.find_element(By.CSS_SELECTOR, ".entry-content")
        # Get all paragraph text
        paragraphs = content_elem.find_elements(By.TAG_NAME, "p")
        body = "\n".join(p.text.strip() for p in paragraphs if p.text.strip())
    except Exception:
        # Fallback: get all text from article
        try:
            article = driver.find_element(By.TAG_NAME, "article")
            body = article.text
        except Exception:
            logger.warning("Could not extract text from: %s", url)
            return None

    if not body or len(body) < 50:
        return None

    return {
        "url": url,
        "title": title,
        "date": date_str,
        "text": body,
    }


# ─── Checkpoint / Resume ─────────────────────────────────────────────

def _load_checkpoint(output_dir: Path) -> tuple[set[str], list[dict]]:
    """Load previously scraped articles for resume support."""
    checkpoint_file = output_dir / "articles.jsonl"
    scraped_urls: set[str] = set()
    articles: list[dict] = []

    if checkpoint_file.exists():
        with open(checkpoint_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    article = json.loads(line)
                    scraped_urls.add(article["url"])
                    articles.append(article)
        logger.info("Loaded %d previously scraped articles", len(articles))

    return scraped_urls, articles


def _save_article(output_dir: Path, article: dict) -> None:
    """Append a single article to the JSONL checkpoint file."""
    checkpoint_file = output_dir / "articles.jsonl"
    with open(checkpoint_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(article, ensure_ascii=False) + "\n")


# ─── Main Pipeline ───────────────────────────────────────────────────

def scrape_asbarez(
    max_listing_pages: int = DEFAULT_MAX_LISTING_PAGES,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> list[dict]:
    """Run the full Asbarez scraping pipeline.

    Returns list of article dicts with 'url', 'title', 'text', 'date'.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    scraped_urls, articles = _load_checkpoint(output_dir)

    driver = _create_driver()
    try:
        # Collect article URLs
        logger.info("Collecting article URLs...")
        all_urls = collect_article_urls(driver, max_listing_pages)
        new_urls = [u for u in all_urls if u not in scraped_urls]
        logger.info("%d new articles to scrape (of %d total found)",
                    len(new_urls), len(all_urls))

        # Scrape each article
        for i, url in enumerate(new_urls, 1):
            logger.info("[%d/%d] Scraping: %s", i, len(new_urls), url)
            article = extract_article_text(driver, url)

            if article:
                articles.append(article)
                _save_article(output_dir, article)
                logger.info("  ✓ %d chars extracted", len(article["text"]))
            else:
                logger.info("  ✗ Skipped (no content)")

            time.sleep(REQUEST_DELAY)

    finally:
        driver.quit()

    logger.info("Scraping complete: %d total articles", len(articles))
    return articles


def load_asbarez_texts(output_dir: Path = DEFAULT_OUTPUT_DIR) -> list[str]:
    """Load previously scraped article texts from checkpoint file."""
    _, articles = _load_checkpoint(output_dir)
    return [a["text"] for a in articles if a.get("text")]


# ─── CLI ──────────────────────────────────────────────────────────────

def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Scrape Asbarez Armenian articles")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_LISTING_PAGES,
                        help="Max listing pages to crawl")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    articles = scrape_asbarez(args.max_pages, args.output_dir)

    # Quick stats
    from .tokenizer import count_frequencies, filter_by_min_length

    texts = [a["text"] for a in articles]
    freq = count_frequencies(texts)
    freq = filter_by_min_length(freq, min_len=2)

    print(f"\nArticles scraped: {len(articles)}")
    print(f"Total tokens: {sum(freq.values()):,}")
    print(f"Unique forms: {len(freq):,}")


if __name__ == "__main__":
    main()
