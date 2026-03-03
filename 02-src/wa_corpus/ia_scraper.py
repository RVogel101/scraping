"""
Internet Archive scraper for Western Armenian scanned books and periodicals.

Searches archive.org for Armenian-language texts from diaspora publishers
(Beirut, Istanbul, Venice Mechitarists, etc.) and downloads:
  - Page images (JP2/JPEG) for OCR processing
  - Existing OCR text (DjVuTXT, hOCR) when available

Uses the IA Advanced Search API and Metadata API (no authentication needed).

Usage:
    python -m wa_corpus.ia_scraper [--max-items N] [--download-images]
    python -m wa_corpus.ia_scraper --list-only   # Just catalog, no download
"""

from __future__ import annotations

import json
import logging
import time
import zipfile
from pathlib import Path
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────

DEFAULT_OUTPUT_DIR = Path("wa_corpus/data/ia")
SEARCH_API = "https://archive.org/advancedsearch.php"
METADATA_API = "https://archive.org/metadata"
DOWNLOAD_BASE = "https://archive.org/download"
REQUEST_DELAY = 1.0
USER_AGENT = "WACorpusBuilder/1.0 (Western Armenian research corpus)"

# Search queries targeting WA content from diaspora publishers
# WA indicators: Beirut, Istanbul/Constantinople, Venice Mechitarists,
# Cairo, Aleppo, Paris, Buenos Aires diaspora publishers
WA_SEARCH_QUERIES = [
    # Broad Armenian language texts
    "language:arm AND mediatype:texts",
    # Diaspora city publishers (strong WA signal)
    "(armenian AND beirut) AND mediatype:texts",
    "(armenian AND (istanbul OR constantinople)) AND mediatype:texts",
    "(mechitarist OR mekhitarist) AND mediatype:texts",
    # Armenian periodicals (many are WA diaspora journals)
    "(armenian AND (periodical OR journal)) AND mediatype:texts AND language:arm",
]

# Formats we want to download, in priority order
IMAGE_FORMATS = ["Single Page Processed JP2 ZIP", "Single Page Original JP2 Tar"]
# Only DjVuTXT by default — it's plain text, ~100KB per file.
# hOCR/chOCR are multi-MB HTML with layout coordinates we don't need.
TEXT_FORMATS_DEFAULT = ["DjVuTXT"]
TEXT_FORMATS_ALL = ["DjVuTXT", "OCR Search Text", "hOCR", "chOCR"]


# ─── Catalog ──────────────────────────────────────────────────────────

def search_items(
    query: str,
    max_items: int = 100,
    sort: str = "downloads desc",
) -> list[dict]:
    """Search Internet Archive for items matching query.

    Returns list of item metadata dicts with keys:
      identifier, title, language, date, creator, imagecount
    """
    headers = {"User-Agent": USER_AGENT}
    all_items: list[dict] = []
    page = 1
    rows_per_page = min(max_items, 100)

    while len(all_items) < max_items:
        params = {
            "q": query,
            "output": "json",
            "rows": str(rows_per_page),
            "page": str(page),
            "fl[]": ["identifier", "title", "language", "date",
                     "creator", "imagecount", "description"],
            "sort[]": sort,
        }

        try:
            resp = requests.get(SEARCH_API, params=params,
                                headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("Search API error (page %d): %s", page, e)
            break

        docs = data.get("response", {}).get("docs", [])
        if not docs:
            break

        all_items.extend(docs)
        total = data["response"].get("numFound", 0)
        logger.info("Search page %d: got %d items (total available: %d)",
                     page, len(docs), total)

        if len(all_items) >= total:
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    return all_items[:max_items]


def _contains_armenian(text) -> bool:
    """Return True if the input (usually a string) has any Armenian characters.

    The IA metadata sometimes has lists or other non-str values in the title/
    description fields, so we coerce to str first and then scan character-by-
    character.  This avoids the 'ord() expected a character' TypeError.
    """
    if not text:
        return False
    s = str(text)
    for c in s:
        code = ord(c)
        if 0x0531 <= code <= 0x0587:
            return True
    return False


def catalog_all_armenian(max_per_query: int = 200) -> list[dict]:
    """Run all WA search queries and deduplicate results.

    Applies a basic Armenian-script filter on titles/descriptions so that
    items without any Armenian characters are dropped early.  This helps reduce
    the chance of Eastern-Armenian or non‑Armenian results slipping through the
    query.

    Returns deduplicated list of item metadata.
    """
    seen_ids: set[str] = set()
    all_items: list[dict] = []

    for query in WA_SEARCH_QUERIES:
        logger.info("Searching: %s", query)
        items = search_items(query, max_items=max_per_query)

        new_count = 0
        for item in items:
            # basic filter: require Armenian characters in title or description
            title = item.get("title", "") or ""
            desc = item.get("description", "") or ""
            if not (_contains_armenian(title) or _contains_armenian(desc)):
                # skip non‑Armenian items returned by the broad query
                continue

            ident = item["identifier"]
            if ident not in seen_ids:
                seen_ids.add(ident)
                all_items.append(item)
                new_count += 1

        logger.info("  Found %d items (%d new)", len(items), new_count)
        time.sleep(REQUEST_DELAY)

    logger.info("Total unique items: %d", len(all_items))
    return all_items


# ─── Item File Discovery ─────────────────────────────────────────────

def get_item_files(identifier: str) -> list[dict]:
    """Get file listing for an IA item."""
    headers = {"User-Agent": USER_AGENT}
    url = f"{METADATA_API}/{identifier}/files"

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json().get("result", [])
    except Exception as e:
        logger.warning("Failed to get files for %s: %s", identifier, e)
        return []


def classify_item_files(files: list[dict], text_formats: list[str] | None = None) -> dict:
    """Classify available files by type.

    Args:
        files: Raw file list from IA metadata API.
        text_formats: Which OCR text formats to include. Defaults to DjVuTXT only.

    Returns dict with keys: 'images', 'ocr_text', 'pdf', 'formats'
    """
    if text_formats is None:
        text_formats = TEXT_FORMATS_DEFAULT

    result = {"images": [], "ocr_text": [], "pdf": [], "formats": set()}

    for f in files:
        fmt = f.get("format", "")
        name = f.get("name", "")
        size = int(f.get("size", 0))
        result["formats"].add(fmt)

        entry = {"name": name, "format": fmt, "size": size}

        if fmt in IMAGE_FORMATS:
            result["images"].append(entry)
        elif fmt in text_formats:
            result["ocr_text"].append(entry)
        elif "PDF" in fmt:
            result["pdf"].append(entry)

    result["formats"] = sorted(result["formats"])
    return result


# ─── Download ─────────────────────────────────────────────────────────

def download_file(identifier: str, filename: str, output_dir: Path) -> Path | None:
    """Download a single file from an IA item."""
    headers = {"User-Agent": USER_AGENT}
    url = f"{DOWNLOAD_BASE}/{identifier}/{quote(filename)}"
    output_path = output_dir / filename

    if output_path.exists():
        logger.debug("Already downloaded: %s", output_path)
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        resp = requests.get(url, headers=headers, timeout=300, stream=True)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=256 * 1024):
                f.write(chunk)
                downloaded += len(chunk)

        logger.info("Downloaded %s (%.1f MB)", filename, downloaded / 1e6)
        return output_path

    except Exception as e:
        logger.warning("Failed to download %s/%s: %s", identifier, filename, e)
        if output_path.exists():
            output_path.unlink()
        return None


def download_ocr_text(identifier: str, files: dict, output_dir: Path) -> list[Path]:
    """Download existing OCR text files for an item."""
    downloaded = []
    item_dir = output_dir / identifier

    for entry in files["ocr_text"]:
        path = download_file(identifier, entry["name"], item_dir)
        if path:
            downloaded.append(path)
        time.sleep(REQUEST_DELAY)

    return downloaded


def download_page_images(identifier: str, files: dict, output_dir: Path) -> list[Path]:
    """Download page image archives (JP2 ZIPs) for an item."""
    downloaded = []
    item_dir = output_dir / identifier

    for entry in files["images"]:
        path = download_file(identifier, entry["name"], item_dir)
        if path:
            downloaded.append(path)
        time.sleep(REQUEST_DELAY)

    return downloaded


# ─── Checkpoint / Resume ─────────────────────────────────────────────

def _load_catalog(output_dir: Path) -> dict:
    """Load the saved catalog."""
    catalog_file = output_dir / "catalog.json"
    if catalog_file.exists():
        with open(catalog_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"items": [], "downloaded": {}}


def _save_catalog(output_dir: Path, catalog: dict) -> None:
    """Save the catalog."""
    catalog_file = output_dir / "catalog.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(catalog_file, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)


# ─── Main Pipeline ───────────────────────────────────────────────────

def scrape_ia(
    max_items: int = 100,
    download_images: bool = False,
    download_text: bool = True,
    list_only: bool = False,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict:
    """Run the Internet Archive scraping pipeline.

    Steps:
    1. Search and catalog Armenian-language items
    2. For each item, check available file formats
    3. Download OCR text (always) and/or page images (if requested)

    Args:
        max_items: Maximum items to process per search query
        download_images: Whether to download page image ZIPs for OCR
        download_text: Whether to download existing OCR/DjVu text
        list_only: Just catalog items, don't download anything
        output_dir: Where to save downloaded files

    Returns:
        Catalog dict with item info and download status
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog = _load_catalog(output_dir)

    # Step 1: Catalog
    logger.info("=" * 50)
    logger.info("  Step 1: Cataloging Armenian items on IA")
    logger.info("=" * 50)

    items = catalog_all_armenian(max_per_query=max_items)

    # Merge with existing catalog
    existing_ids = {item["identifier"] for item in catalog["items"]}
    for item in items:
        if item["identifier"] not in existing_ids:
            catalog["items"].append(item)
            existing_ids.add(item["identifier"])

    _save_catalog(output_dir, catalog)
    logger.info("Catalog: %d total items", len(catalog["items"]))

    if list_only:
        _print_catalog_summary(catalog)
        return catalog

    # Step 2: Process each item
    logger.info("=" * 50)
    logger.info("  Step 2: Downloading files")
    logger.info("=" * 50)

    for i, item in enumerate(catalog["items"], 1):
        ident = item["identifier"]

        # Skip already processed
        if ident in catalog.get("downloaded", {}):
            continue

        logger.info("[%d/%d] %s", i, len(catalog["items"]),
                    item.get("title", ident)[:60])

        # Get file listing
        files_raw = get_item_files(ident)
        if not files_raw:
            continue

        files = classify_item_files(files_raw)
        item_dir = output_dir / ident

        result = {"ocr_files": [], "image_files": [], "formats": files["formats"]}

        # Download OCR text
        if download_text and files["ocr_text"]:
            paths = download_ocr_text(ident, files, output_dir)
            result["ocr_files"] = [str(p) for p in paths]

        # Download page images
        if download_images and files["images"]:
            paths = download_page_images(ident, files, output_dir)
            result["image_files"] = [str(p) for p in paths]

        catalog["downloaded"][ident] = result
        _save_catalog(output_dir, catalog)

        time.sleep(REQUEST_DELAY)

    logger.info("Download complete.")
    _print_catalog_summary(catalog)
    return catalog


def _print_catalog_summary(catalog: dict) -> None:
    """Print a summary of the catalog."""
    items = catalog["items"]
    downloaded = catalog.get("downloaded", {})

    with_ocr = sum(1 for d in downloaded.values() if d.get("ocr_files"))
    with_images = sum(1 for d in downloaded.values() if d.get("image_files"))
    total_pages = sum(item.get("imagecount", 0) or 0 for item in items)

    print(f"\n{'=' * 60}")
    print(f"  Internet Archive Armenian Collection")
    print(f"{'=' * 60}")
    print(f"  Cataloged items:  {len(items):>8,}")
    print(f"  Total pages:      {total_pages:>8,}")
    print(f"  Downloaded (OCR): {with_ocr:>8,}")
    print(f"  Downloaded (img): {with_images:>8,}")
    print(f"{'─' * 60}")

    # Show top 15 by page count
    by_pages = sorted(items, key=lambda x: x.get("imagecount", 0) or 0, reverse=True)
    print(f"  Largest items:")
    for item in by_pages[:15]:
        pages = item.get("imagecount", "?")
        title = item.get("title", "?")[:50]
        ident = item["identifier"]
        status = "DL" if ident in downloaded else "  "
        print(f"  {status} [{pages:>6}pg] {title}")
    print(f"{'=' * 60}")


# ─── Extract text from downloaded OCR files ──────────────────────────

def extract_ocr_texts(output_dir: Path = DEFAULT_OUTPUT_DIR) -> list[str]:
    """Load all downloaded OCR text from DjVuTXT files.

    Returns list of text strings, one per item.
    """
    catalog = _load_catalog(output_dir)
    texts = []

    for ident, info in catalog.get("downloaded", {}).items():
        for fpath in info.get("ocr_files", []):
            p = Path(fpath)
            if p.exists() and p.suffix == ".txt":
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                    if text.strip():
                        texts.append(text)
                except Exception as e:
                    logger.warning("Failed to read %s: %s", p, e)

    logger.info("Loaded OCR text from %d files", len(texts))
    return texts


def list_image_archives(output_dir: Path = DEFAULT_OUTPUT_DIR) -> list[Path]:
    """List all downloaded JP2 ZIP archives for OCR processing.

    Returns list of paths to ZIP files containing page images.
    """
    catalog = _load_catalog(output_dir)
    archives = []

    for ident, info in catalog.get("downloaded", {}).items():
        for fpath in info.get("image_files", []):
            p = Path(fpath)
            if p.exists() and p.suffix == ".zip":
                archives.append(p)

    return archives


# ─── CLI ──────────────────────────────────────────────────────────────

def main():
    import argparse

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
                        datefmt="%H:%M:%S")

    parser = argparse.ArgumentParser(
        description="Scrape Internet Archive for Armenian texts and scans",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m wa_corpus.ia_scraper --list-only          # Catalog only
  python -m wa_corpus.ia_scraper --max-items 50       # Download OCR text
  python -m wa_corpus.ia_scraper --download-images    # Also get page images
        """,
    )

    parser.add_argument("--max-items", type=int, default=100,
                        help="Max items per search query (default: 100)")
    parser.add_argument("--download-images", action="store_true",
                        help="Download page image ZIPs for OCR processing")
    parser.add_argument("--no-text", action="store_true",
                        help="Skip downloading existing OCR text")
    parser.add_argument("--list-only", action="store_true",
                        help="Just catalog items, don't download")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    catalog = scrape_ia(
        max_items=args.max_items,
        download_images=args.download_images,
        download_text=not args.no_text,
        list_only=args.list_only,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
