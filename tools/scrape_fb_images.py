"""
Facebook Image Scraper — Full Resolution
Scrapes FULL-RESOLUTION images from the Centre for Western Armenian Studies
Facebook photos page.

Strategy:
  Phase 1 - Scroll the photos grid and collect links to individual photo pages.
  Phase 2 - Visit each photo page, wait for the full-res image to render,
             grab its src URL, and download it via parallel worker threads.

Uses Selenium (Facebook pages are JS-rendered) with threaded parallel downloads.
"""

import os
import json
import re
import time
import logging
import shutil
import tempfile
import requests
import threading
from queue import Queue
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from urllib.parse import urlparse

try:
    import psutil
except ImportError:
    psutil = None

# ─── Configuration ──────────────────────────────────────────────────────────
URL = "https://www.facebook.com/centreforwesternarmenianstudies/photos_by"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FB-UK-CWAS-Content")

# Scrolling
SCROLL_PAUSE = 0.3        # seconds to wait between scrolls
NO_CHANGE_RETRIES = 15    # consecutive unchanged scrolls before stopping
BATCH_SCROLLS = 20        # scrolls per batch (for end-of-scroll detection)
COLLECT_EVERY_N = 3       # collect photo links every N scrolls (low = fewer gaps)
MAX_SCROLLS = 1300         # hard limit on total scrolls

# Downloading
DOWNLOAD_WORKERS = 3      # parallel download threads (reduced to prevent crashes)
DOWNLOAD_RETRIES = 2      # retry failed downloads this many times

# Thumbnail identification (to find photos in the grid during Phase 1)
THUMB_RENDER_W = 169       # rendered width of grid thumbnails
THUMB_RENDER_H = 169       # rendered height of grid thumbnails
THUMB_INTRINSIC_W = 206    # intrinsic (natural) width of thumbnails
THUMB_INTRINSIC_H = 206    # intrinsic (natural) height of thumbnails

# Full-res detection (on the photo viewer page during Phase 2)
MIN_FULL_RES_NAT_WIDTH = 800   # naturalWidth must be at least this
PHOTO_PAGE_TIMEOUT = 15         # seconds to wait for full-res image to load
RESOLVER_TABS = 5             # browser tabs open in parallel for Phase 2

SRC_PREFIX = "https://scontent"  # image src must start with this
BOOKMARK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".last_run_bookmark")
CHECKPOINT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".phase2_checkpoint")
PHASE2_BATCH_SIZE = 25        # save checkpoint every N photos resolved

# ─── Performance Tracking ─────────────────────────────────────────────────
perf_stats = {
    'script_start': 0,
    'browser_start': 0,
    'phase1_start': 0,
    'phase1_end': 0,
    'phase2_start': 0,
    'phase2_end': 0,
    'script_end': 0,
    'peak_memory_mb': 0,
    'total_bytes_downloaded': 0,
    'total_links_collected': 0,
    'total_images_saved': 0,
    'total_dupes_skipped': 0,
    'total_failed': 0,
    'total_timeouts': 0,
    'retry_attempts': 0,
    'retry_successes': 0
}

def _normalize_image_url(url):
    """Normalize image URL to catch slight variations of the same image.
    
    Facebook sometimes serves the same image with different URL parameters
    or slight variations. This function normalizes URLs to improve deduplication.
    """
    if not url:
        return url
    
    # Remove common Facebook URL parameters that don't affect the actual image
    import re
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        # Keep only essential parameters, remove tracking/session params
        essential_params = {}
        for key, values in query_params.items():
            if key.lower() in ['fbid', 'set', 'type', 'size']:
                essential_params[key] = values
        
        # Rebuild URL with normalized parameters
        normalized_query = urlencode(essential_params, doseq=True)
        normalized_parsed = parsed._replace(query=normalized_query)
        normalized_url = urlunparse(normalized_parsed)
        
        return normalized_url
    except Exception:
        # If parsing fails, return original URL
        return url


def _get_existing_cwas_files(output_dir):
    """Get a set of existing CWAS file numbers to avoid re-downloading."""
    existing_numbers = set()
    if not os.path.exists(output_dir):
        return existing_numbers
    
    import re
    cwas_pattern = re.compile(r'CWAS_(\d{4})', re.IGNORECASE)
    
    try:
        for filename in os.listdir(output_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                match = cwas_pattern.match(filename)
                if match:
                    existing_numbers.add(int(match.group(1)))
    except Exception as e:
        logging.warning(f"Error scanning existing files: {e}")
    
    return existing_numbers


# Global list to collect failed downloads for retry
failed_downloads = []
failed_downloads_lock = threading.Lock()


def _track_memory():
    """Update peak memory usage if psutil is available."""
    if psutil:
        try:
            mem_mb = psutil.Process().memory_info().rss / 1024 / 1024
            perf_stats['current_memory_mb'] = mem_mb
            perf_stats['peak_memory_mb'] = max(perf_stats.get('peak_memory_mb', 0), mem_mb)
            
            # Check if memory usage is getting dangerous
            if mem_mb > 2048:  # 2GB threshold
                logging.warning(f"High memory usage detected: {mem_mb:.1f}MB")
                
            # Log memory every 500MB increase
            if mem_mb // 500 > perf_stats.get('last_memory_log_level', 0):
                perf_stats['last_memory_log_level'] = mem_mb // 500
                logging.info(f"Current memory usage: {mem_mb:.1f}MB")
                
        except Exception:
            pass


def _check_system_resources():
    """Check system resources and return warning if low."""
    if not psutil:
        return None
        
    try:
        # Check available memory
        memory = psutil.virtual_memory()
        memory_available_gb = memory.available / 1024 / 1024 / 1024
        
        if memory_available_gb < 1.0:  # Less than 1GB available
            return f"Low memory warning: Only {memory_available_gb:.1f}GB available"
            
        # Check CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 90:
            return f"High CPU usage: {cpu_percent}%"
            
    except Exception as e:
        logging.debug(f"System resource check failed: {e}")
    
    return None

# ─── Chrome Profile (reuse existing login) ──────────────────────────────────
# Copies your cookies to a temp profile so you DON'T need to close Chrome.
CHROME_USER_DATA = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
CHROME_PROFILE = "Default"  # Change to "Profile 1", "Profile 2" etc. if needed
                             # Check chrome://version → "Profile Path" to find yours


def is_browser_responsive(driver, timeout=10):
    """Check if browser is still responsive by trying to get current URL.
    
    Args:
        driver: WebDriver instance
        timeout: Max seconds to wait for response
    
    Returns:
        bool: True if responsive, False if crashed/hung
    """
    try:
        driver.set_page_load_timeout(timeout)
        _ = driver.current_url  # Simple test that requires browser response
        return True
    except Exception as e:
        logging.warning(f"Browser responsiveness check failed: {e}")
        return False


def restart_driver_if_needed(driver):
    """Check browser health and restart if necessary.
    
    Args:
        driver: Current WebDriver instance
    
    Returns:
        WebDriver: Same driver if healthy, new driver if restarted
    """
    if not is_browser_responsive(driver):
        logging.warning("Browser appears unresponsive, restarting...")
        try:
            driver.quit()
        except:
            pass  # May already be dead
        
        # Small delay before restart
        time.sleep(2)
        return setup_driver()
    
    return driver


def setup_driver():
    """Create a Selenium Chrome WebDriver with cookies copied from your real profile.
    
    Copies only the cookie/session files to a temp directory so Chrome
    can stay open while the script runs.
    """
    logging.info("Setting up Chrome WebDriver with profile cookies")
    options = Options()

    profile_src = os.path.join(CHROME_USER_DATA, CHROME_PROFILE)
    logging.debug(f"Looking for Chrome profile at: {profile_src}")
    
    if os.path.isdir(profile_src):
        logging.info(f"Found Chrome profile: {CHROME_PROFILE}")
        # Create a temp profile dir and copy cookie/session files into it
        temp_user_data = tempfile.mkdtemp(prefix="chrome_scraper_")
        temp_profile = os.path.join(temp_user_data, CHROME_PROFILE)
        os.makedirs(temp_profile, exist_ok=True)
        logging.debug(f"Created temp profile directory: {temp_profile}")

        # Files that carry the Facebook login session
        cookie_files = ["Cookies", "Cookies-journal",
                        "Login Data", "Login Data-journal",
                        "Web Data", "Web Data-journal",
                        "Preferences", "Secure Preferences"]
        copied = 0
        for fname in cookie_files:
            src = os.path.join(profile_src, fname)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(temp_profile, fname))
                copied += 1
                logging.debug(f"Copied session file: {fname}")

        # Also copy the Local State file (needed for cookie decryption)
        local_state = os.path.join(CHROME_USER_DATA, "Local State")
        if os.path.isfile(local_state):
            shutil.copy2(local_state, os.path.join(temp_user_data, "Local State"))
            logging.debug("Copied Local State file")

        options.add_argument(f"--user-data-dir={temp_user_data}")
        options.add_argument(f"--profile-directory={CHROME_PROFILE}")
        print(f"  Copied {copied} session files from '{CHROME_PROFILE}' to temp profile")
        print(f"  (Chrome can stay open — no conflict)")
        logging.info(f"Successfully copied {copied} session files to temp profile")
    else:
        print(f"  Chrome profile not found at {profile_src}, using fresh session.")
        logging.warning(f"Chrome profile not found at {profile_src}, will use fresh session")

    # Keep the browser open and prevent auto-close / session loss
    options.add_experimental_option("detach", True)
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--remote-allow-origins=*")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=en-US")
    # Memory management options to prevent crashes
    options.add_argument("--max_old_space_size=4096")
    options.add_argument("--memory-pressure-off")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-ipc-flooding-protection")
    # Limit tabs and processes
    options.add_argument("--max-tabs=4")
    options.add_argument("--process-per-site")
    # Additional stability options for heavy Facebook pages
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    # Network optimizations (removed --disable-images and --disable-javascript)
    options.add_argument("--aggressive-cache-discard")
    
    logging.debug("Initializing Chrome WebDriver with anti-detection options")
    try:
        driver = webdriver.Chrome(options=options)
        logging.info("Chrome WebDriver initialized successfully")

        # Increase the urllib3 connection-pool size so multiple threads
        # can talk to the WebDriver without "Connection pool is full" warnings.
        try:
            import urllib3
            driver.command_executor._conn = urllib3.PoolManager(
                num_pools=10, maxsize=10)
            logging.debug("Increased WebDriver connection pool to 10")
        except Exception:
            pass  # non-critical; warnings are harmless if this fails

    except Exception as e:
        logging.error(f"Failed to initialize Chrome WebDriver: {e}")
        raise
    
    # Hide the webdriver flag from JavaScript detection
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
        logging.debug("Successfully applied webdriver detection bypass")
    except Exception as e:
        logging.warning(f"Could not apply webdriver detection bypass: {e}")
    
    return driver


def get_run_mode():
    """Ask user whether to do a complete refresh or update mode.
    
    Returns:
        str: 'refresh' for complete refresh, 'update' for bookmark-based update
    """
    print("\n" + "="*60)
    print("  RUN MODE SELECTION")
    print("="*60)
    print("  [1] COMPLETE REFRESH - Start from beginning, ignore bookmark")
    print("      → Downloads all photos from scratch")
    print("      → Overwrites existing bookmark")
    print("      → Use this for a clean slate")
    print()
    print("  [2] UPDATE MODE - Resume from bookmark, get new photos only")
    print("      → Starts from last run's bookmark")
    print("      → Downloads only newer photos")
    print("      → Use this for regular updates")
    print("="*60)
    
    while True:
        choice = input("\nSelect mode [1 for refresh, 2 for update]: ").strip()
        if choice == '1':
            print("  → Selected: COMPLETE REFRESH")
            return 'refresh'
        elif choice == '2':
            print("  → Selected: UPDATE MODE")
            return 'update'
        else:
            print("  Please enter 1 or 2")


def load_bookmark():
    """Load the first href from the previous run, or None if no bookmark exists."""
    if os.path.isfile(BOOKMARK_FILE):
        with open(BOOKMARK_FILE, "r", encoding="utf-8") as f:
            url = f.read().strip()
            if url:
                print(f"  Bookmark from last run: {url[:80]}...")
                return url
    print("  No bookmark found — this looks like a first run.")
    return None


def save_bookmark(url):
    """Save the first href from this run as the bookmark for next time."""
    with open(BOOKMARK_FILE, "w", encoding="utf-8") as f:
        f.write(url)
    print(f"  Bookmark saved for next run: {url[:80]}...")


def load_checkpoint():
    """Load the Phase 2 checkpoint — returns a set of already-processed links."""
    logging.debug(f"Looking for checkpoint file: {CHECKPOINT_FILE}")
    if os.path.isfile(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Support both old format {"processed":[], "next_seq":N} and new
            processed = set(data.get("processed", data) if isinstance(data, dict) else data)
            print(f"  Phase 2 checkpoint found: {len(processed)} already processed.")
            logging.info(f"Loaded checkpoint with {len(processed)} processed links")
            return processed
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logging.warning(f"Failed to load checkpoint file: {e}")
    else:
        logging.debug("No checkpoint file found")
    return set()


def save_checkpoint(processed_set):
    """Write the current Phase 2 progress to disk."""
    try:
        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump(list(processed_set), f)
        logging.debug(f"Checkpoint saved with {len(processed_set)} processed links")
    except Exception as e:
        logging.error(f"Failed to save checkpoint: {e}")


def clear_checkpoint():
    """Remove the checkpoint file (called when Phase 2 finishes completely)."""
    if os.path.isfile(CHECKPOINT_FILE):
        try:
            os.remove(CHECKPOINT_FILE)
            logging.info("Checkpoint file cleared successfully")
        except Exception as e:
            logging.warning(f"Failed to clear checkpoint file: {e}")
    else:
        logging.debug("No checkpoint file to clear")


def _download_worker(download_queue, output_dir, stats, stats_lock):
    """Worker thread that downloads images from the queue with date extraction."""
    global _date_extractor
    thread_name = threading.current_thread().name
    logging.debug(f"[{thread_name}] Download worker started")
    
    while True:
        item = download_queue.get()
        if item is None:  # poison pill — shut down
            logging.debug(f"[{thread_name}] Received shutdown signal")
            download_queue.task_done()
            break
        
        url, seq_num, photo_page_url = item
        logging.debug(f"[{thread_name}] Processing CWAS_{seq_num:04d}: {photo_page_url[:100]}...")
        
        # Check if file already exists (file-system level deduplication)
        base_filename_pattern = f"CWAS_{seq_num:04d}"
        try:
            existing_files = [f for f in os.listdir(output_dir) 
                             if f.startswith(base_filename_pattern) and 
                             f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif'))]
        except OSError as e:
            logging.warning(f"[{thread_name}] Could not list directory {output_dir}: {e}")
            existing_files = []
        
        if existing_files:
            with stats_lock:
                stats["skipped"] += 1
            logging.info(f"[{thread_name}] Skipping CWAS_{seq_num:04d} - file already exists: {existing_files[0]}")
            print(f"    CWAS_{seq_num:04d} already exists as {existing_files[0]} - skipping")
            download_queue.task_done()
            continue
        
        # Extract date from photo page using shared browser pool
        extracted_date = None
        if _date_extractor:
            try:
                extracted_date = _date_extractor.extract_date(photo_page_url)
                if extracted_date:
                    logging.debug(f"[{thread_name}] Extracted date '{extracted_date}' for CWAS_{seq_num:04d}")
                    print(f"    CWAS_{seq_num:04d} - extracted date: {extracted_date}")
                else:
                    logging.debug(f"[{thread_name}] No date extracted for CWAS_{seq_num:04d}")
            except Exception as e:
                logging.debug(f"[{thread_name}] Date extraction failed for CWAS_{seq_num:04d}: {e}")
        
        # Format filename with extracted date
        parsed = urlparse(url)
        _, ext = os.path.splitext(parsed.path)
        if not ext or ext.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            ext = ".jpg"
        
        # Ensure date is included in filename - this was the missing functionality!
        if extracted_date:
            date_part = f"_{extracted_date}"
            logging.info(f"[{thread_name}] Including date in filename: CWAS_{seq_num:04d}{date_part}{ext}")
        else:
            date_part = ""
            logging.warning(f"[{thread_name}] No date available for CWAS_{seq_num:04d}, using sequence only")
        
        filename = f"CWAS_{seq_num:04d}{date_part}{ext}"
        filepath = os.path.join(output_dir, filename)
        
        # Final check if this exact filename exists
        if os.path.exists(filepath):
            with stats_lock:
                stats["skipped"] += 1
            logging.info(f"Skipping {filename} - exact file already exists")
            print(f"    {filename} already exists - skipping")
            download_queue.task_done()
            continue

        success = False
        for attempt in range(1, DOWNLOAD_RETRIES + 2):  # +2 = 1 initial + retries
            try:
                resp = requests.get(url, stream=True, timeout=30)
                resp.raise_for_status()
                bytes_written = 0
                with open(filepath, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                        bytes_written += len(chunk)
                with stats_lock:
                    stats["saved"] += 1
                    perf_stats['total_bytes_downloaded'] += bytes_written
                _track_memory()
                logging.debug(f"Downloaded {filename} ({bytes_written} bytes)")
                success = True
                break
            except Exception as e:
                if attempt <= DOWNLOAD_RETRIES:
                    time.sleep(1 * attempt)  # backoff
                else:
                    with stats_lock:
                        stats["failed"] += 1
                    with failed_downloads_lock:
                        failed_downloads.append((url, seq_num, extracted_date))
                    logging.warning(f"Failed to download {url[:80]}... after {attempt} attempts: {e}")
                    print(f"    FAILED download ({attempt} attempts): {url[:80]}... — {e}")
        download_queue.task_done()


def retry_failed_downloads(output_dir, max_retries=3):
    """Retry downloading failed images with longer timeout and more attempts."""
    global failed_downloads
    
    with failed_downloads_lock:
        retry_items = failed_downloads.copy()
        failed_downloads.clear()
    
    if not retry_items:
        return 0, 0
    
    print(f"\n  Retrying {len(retry_items)} failed downloads...")
    logging.info(f"Starting retry phase for {len(retry_items)} failed downloads")
    
    successes = 0
    final_failures = 0
    
    for i, (url, seq_num, date_str) in enumerate(retry_items, 1):
        parsed = urlparse(url)
        _, ext = os.path.splitext(parsed.path)
        if not ext or ext.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            ext = ".jpg"
        date_part = f"_{date_str}" if date_str else ""
        filename = f"CWAS_{seq_num:04d}{date_part}{ext}"
        filepath = os.path.join(output_dir, filename)
        
        print(f"  [{i}/{len(retry_items)}] Retrying {filename}...", end="", flush=True)
        
        success = False
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.get(url, stream=True, timeout=45)  # longer timeout
                resp.raise_for_status()
                bytes_written = 0
                with open(filepath, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                        bytes_written += len(chunk)
                perf_stats['total_bytes_downloaded'] += bytes_written
                perf_stats['retry_successes'] += 1
                successes += 1
                success = True
                print(f" ✓ success ({bytes_written} bytes)")
                logging.info(f"Retry success: {filename} ({bytes_written} bytes)")
                break
            except Exception as e:
                if attempt < max_retries:
                    time.sleep(2 * attempt)  # longer backoff for retries
                else:
                    final_failures += 1
                    print(f" ✗ failed after {max_retries} attempts")
                    logging.error(f"Final retry failure for {filename}: {e}")
        
        perf_stats['retry_attempts'] += 1
        _track_memory()
        
        # Brief pause between retries to be gentle
        if i < len(retry_items):
            time.sleep(0.5)
    
    print(f"\n  Retry complete: {successes} recovered, {final_failures} permanent failures")
    logging.info(f"Retry phase completed: {successes} successes, {final_failures} failures")
    return successes, final_failures


# ─── Phase 1: Scroll and Collect Photo Links ────────────────────────────────

def extract_photo_links(driver):
    """Extract links to individual photo pages from the visible grid.

    Identifies thumbnails by their rendered/intrinsic dimensions, then
    walks up the DOM to find the parent <a> link.  Only scans near the
    current viewport (±2–3 screen heights) to keep things fast.
    """
    js = """
    const prefix = arguments[0];
    const rw = arguments[1], rh = arguments[2];
    const iw = arguments[3], ih = arguments[4];
    const links = [];
    const seen = new Set();
    const vh = window.innerHeight;
    const scrollY = window.scrollY;
    const top = Math.max(0, scrollY - vh * 2);
    const bottom = scrollY + vh * 3;
    document.querySelectorAll('img').forEach(img => {
        const rect = img.getBoundingClientRect();
        const absTop = rect.top + scrollY;
        if (absTop < top || absTop > bottom) return;
        const src = img.src || '';
        if (!src.startsWith(prefix)) return;
        const w = img.clientWidth || img.width;
        const h = img.clientHeight || img.height;
        const nw = img.naturalWidth;
        const nh = img.naturalHeight;
        if ((w === rw && h === rh) || (nw === iw && nh === ih)) {
            let el = img.parentElement;
            while (el && el.tagName !== 'A') el = el.parentElement;
            if (el && el.href && el.href.includes('/photo') && !seen.has(el.href)) {
                seen.add(el.href);
                links.push(el.href);
            }
        }
    });
    return links;
    """
    return driver.execute_script(
        js, SRC_PREFIX,
        THUMB_RENDER_W, THUMB_RENDER_H,
        THUMB_INTRINSIC_W, THUMB_INTRINSIC_H
    ) or []


def _add_new_links(new_links, seen, collected_links, first_link, previous_bookmark):
    """Add new links to the collection. Returns (first_link, hit_bookmark)."""
    hit_bookmark = False
    
    for lnk in new_links:
        if previous_bookmark and lnk == previous_bookmark:
            print(f"\n  ✅ Hit bookmark from last run — stopping collection.")
            print(f"  Collected {len(collected_links)} new photos since last run.")
            hit_bookmark = True
            break
        if first_link is None:
            first_link = lnk
        seen.add(lnk)
        collected_links.append(lnk)
    
    return first_link, hit_bookmark


def scroll_and_collect_links(driver, previous_bookmark=None,
                              pause=SCROLL_PAUSE, max_retries=NO_CHANGE_RETRIES,
                              batch_size=BATCH_SCROLLS, max_scrolls=MAX_SCROLLS,
                              collect_every=COLLECT_EVERY_N):
    """Scroll the photo grid and collect links to individual photo pages.

    Collects links every `collect_every` scrolls so that Facebook's DOM
    virtualisation doesn't remove images before we can read them.

    Returns (photo_links, first_link):
        photo_links — ordered list of photo-page URLs
        first_link  — the very first link (becomes the bookmark for next run)
    """
    logging.info(f"Starting scroll collection with config: pause={pause}s, max_retries={max_retries}, "
                f"batch_size={batch_size}, max_scrolls={max_scrolls}, collect_every={collect_every}")
    if previous_bookmark:
        logging.info(f"Looking for bookmark: {previous_bookmark[:100]}...")
    
    collected_links = []
    seen = set()
    last_height = driver.execute_script("return document.body.scrollHeight")
    logging.debug(f"Initial page height: {last_height}px")
    
    total_scrolls = 0
    scrolls_since_collect = 0
    stale_count = 0
    report_num = 0
    no_new_rounds = 0
    first_link = None
    hit_bookmark = False
    round_new = 0          # new links found in current batch_size round

    while True:
        # ── Scroll one batch (for end-of-page detection) ──
        round_new = 0
        for i in range(batch_size):
            # Check browser health periodically
            if i % 5 == 0:  # Every 5 scrolls in batch
                if not is_browser_responsive(driver, timeout=5):
                    logging.error("Browser became unresponsive during scrolling")
                    raise Exception("Browser crashed during Phase 1 scrolling")
            
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause)

            if stale_count > 3:
                driver.execute_script(
                    "window.scrollBy(0, -500); "
                    "setTimeout(() => window.scrollTo(0, document.body.scrollHeight), 300);"
                )
                time.sleep(0.5)

            new_height = driver.execute_script("return document.body.scrollHeight")

            if new_height == last_height:
                stale_count += 1
                if stale_count >= max_retries:
                    break
                time.sleep(1)
            else:
                stale_count = 0
                last_height = new_height

            total_scrolls += 1
            scrolls_since_collect += 1

            # ── Collect frequently to avoid virtualisation gaps ──
            if scrolls_since_collect >= collect_every:
                # Check system resources periodically
                if total_scrolls % 50 == 0:  # Every 50 scrolls
                    resource_warning = _check_system_resources()
                    if resource_warning:
                        logging.warning(f"Resource check: {resource_warning}")
                        print(f"  ⚠️  {resource_warning}")
                    _track_memory()
                
                batch_links = extract_photo_links(driver)
                new_links = [lnk for lnk in batch_links if lnk not in seen]
                if new_links:
                    report_num += 1
                    print(f"  Collect #{report_num}: +{len(new_links)} new | "
                          f"{len(seen) + len(new_links)} total "
                          f"(scroll {total_scrolls}, height {last_height}px)")
                    first_link, hit_bookmark = _add_new_links(
                        new_links, seen, collected_links, first_link, previous_bookmark)
                    round_new += len(new_links)
                    if hit_bookmark:
                        break
                scrolls_since_collect = 0

            if total_scrolls >= max_scrolls:
                break
            if hit_bookmark:
                break

        # ── Final collect at end of batch round ──
        if not hit_bookmark:
            batch_links = extract_photo_links(driver)
            new_links = [lnk for lnk in batch_links if lnk not in seen]
            if new_links:
                report_num += 1
                print(f"  Collect #{report_num}: +{len(new_links)} new | "
                      f"{len(seen) + len(new_links)} total "
                      f"(scroll {total_scrolls}, height {last_height}px)")
                first_link, hit_bookmark = _add_new_links(
                    new_links, seen, collected_links, first_link, previous_bookmark)
                round_new += len(new_links)
            scrolls_since_collect = 0

        # Continue scrolling for a bit after hitting bookmark to find newer content
        if hit_bookmark:
            break

        if round_new == 0:
            no_new_rounds += 1
        else:
            no_new_rounds = 0

        # ── End-of-scroll checks ──
        if total_scrolls >= max_scrolls:
            print(f"  Reached scroll limit ({max_scrolls}). Stopping.")
            break
        if stale_count >= max_retries and no_new_rounds >= 5:
            print(f"  Page stable & no new links for {no_new_rounds} rounds. Done.")
            break
        elif stale_count >= max_retries:
            print(f"  Page height stable, still finding links. Continuing...")
            stale_count = max_retries // 2

    print(f"\n  Phase 1 complete: {len(collected_links)} photo links "
          f"collected in {total_scrolls} scrolls.\n")
    return collected_links, first_link


# ─── Phase 2: Resolve Full-Res URLs and Download ────────────────────────────

_FULLRES_JS = """
const prefix = arguments[0];
const minW  = arguments[1];
const imgs  = document.querySelectorAll('img');
let best = null;
let bestArea = 0;
for (const img of imgs) {
    const src = img.src || '';
    if (!src.startsWith(prefix)) continue;
    if (!img.complete || img.naturalWidth < minW) continue;
    const area = img.naturalWidth * img.naturalHeight;
    if (area > bestArea) {
        bestArea = area;
        best = src;
    }
}
return best;
"""


# JS to extract the post date from a Facebook photo page.
# Tries several strategies: <time> tag, aria-label with date pattern,
# and visible text near the photo with date-like content.
_DATE_JS = """
// Strategy 1: <abbr> with data-utime (older FB layouts, very reliable when present)
const abbrEls = document.querySelectorAll('abbr[data-utime]');
for (const el of abbrEls) {
    const ts = parseInt(el.getAttribute('data-utime'), 10);
    if (ts && ts > 1000000000) {
        return 'utime:' + new Date(ts * 1000).toISOString().split('T')[0];
    }
}

// Strategy 2: <time datetime="..."> tags
const timeEls = document.querySelectorAll('time[datetime]');
for (const el of timeEls) {
    const dt = el.getAttribute('datetime');
    if (dt) return 'time:' + dt;
}

// Strategy 3: aria-label on links that contain a date string
//   Facebook photo pages often have an <a> near the timestamp whose
//   aria-label contains the full human-readable date.
const dateRe = /\\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\\s+\\d{1,2},?\\s+\\d{4}/i;
const dateReShort = /\\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\\s+\\d{1,2},?\\s+\\d{4}/i;
const numericDateRe = /\\b\\d{1,2}\\/\\d{1,2}\\/\\d{2,4}\\b/;

const ariaEls = document.querySelectorAll('a[aria-label], span[aria-label]');
for (const el of ariaEls) {
    const label = el.getAttribute('aria-label') || '';
    const m = label.match(dateRe) || label.match(dateReShort) || label.match(numericDateRe);
    if (m) return 'aria:' + m[0];
}

// Strategy 4: aria-labelledby – the referenced element often has clean text
const labelledEls = document.querySelectorAll('[aria-labelledby]');
for (const el of labelledEls) {
    const refId = el.getAttribute('aria-labelledby');
    if (!refId) continue;
    const refEl = document.getElementById(refId);
    if (!refEl) continue;
    const txt = (refEl.textContent || '').trim();
    const m = txt.match(dateRe) || txt.match(dateReShort) || txt.match(numericDateRe);
    if (m) return 'labelledby:' + m[0];
}

// Strategy 5: title attributes on any element
const titledEls = document.querySelectorAll('[title]');
for (const el of titledEls) {
    const title = el.title || '';
    const m = title.match(dateRe) || title.match(dateReShort) || title.match(numericDateRe);
    if (m) return 'title:' + m[0];
}

// Strategy 6: visible text inside the timestamp link area
//   On photo pages the date link is usually an <a> whose href contains
//   the photo's fbid and whose visible text is the date.
const photoLinks = document.querySelectorAll(
    'a[href*="/photo"] span, a[href*="fbid="] span');
for (const el of photoLinks) {
    const txt = (el.innerText || el.textContent || '').trim();
    if (txt.length < 3 || txt.length > 60) continue;
    const m = txt.match(dateRe) || txt.match(dateReShort) || txt.match(numericDateRe);
    if (m) return 'link:' + m[0];
}

// Strategy 7: JSON-LD structured data
const jsonLdScripts = document.querySelectorAll('script[type="application/ld+json"]');
for (const script of jsonLdScripts) {
    try {
        const d = JSON.parse(script.textContent);
        if (d.datePublished) return 'jsonld:' + d.datePublished;
        if (d.dateCreated)   return 'jsonld:' + d.dateCreated;
        if (d.uploadDate)    return 'jsonld:' + d.uploadDate;
    } catch (e) {}
}

// Strategy 8: Find the creation timestamp that belongs to THIS photo
//   by locating the photo's fbid in the script text and grabbing the
//   nearest created_time / publish_time.  This avoids picking up
//   timestamps for the FB page, album, user account, comments, etc.
try {
    // Extract fbid from the current page URL
    const url = window.location.href;
    let fbid = null;
    const fbidMatch = url.match(/fbid=(\d+)/) || url.match(/\/photos\/[^/]+\/(\d+)/);
    if (fbidMatch) fbid = fbidMatch[1];

    const scripts = document.querySelectorAll('script:not([src])');
    const tsFieldRe = /"(?:created_time|creation_time|publish_time|taken_at_timestamp|backdated_time)"\s*:\s*([12]\d{9})/g;

    // 8a: TIGHT search — look for "id":"FBID" (the photo's own JSON
    //     object) and grab created_time within ±300 chars of that match.
    //     This avoids picking up timestamps from comments, related posts,
    //     or other entities that merely reference this fbid.
    if (fbid) {
        const idPattern = '"id":"' + fbid + '"';
        for (const s of scripts) {
            const c = s.textContent || '';
            let searchPos = 0;
            while (true) {
                const idx = c.indexOf(idPattern, searchPos);
                if (idx === -1) break;
                searchPos = idx + 1;
                const windowStart = Math.max(0, idx - 300);
                const windowEnd = Math.min(c.length, idx + idPattern.length + 300);
                const win = c.substring(windowStart, windowEnd);
                const localRe = /"(?:created_time|creation_time|publish_time)"\s*:\s*([12]\d{9})/g;
                let m;
                let closest = null;
                let closestDist = Infinity;
                // The fbid position relative to the window
                const fbidPosInWin = idx - windowStart;
                while ((m = localRe.exec(win)) !== null) {
                    const ts = parseInt(m[1], 10);
                    if (ts > 1000000000) {
                        const dist = Math.abs(m.index - fbidPosInWin);
                        if (dist < closestDist) {
                            closest = ts;
                            closestDist = dist;
                        }
                    }
                }
                if (closest) {
                    return 'script_fbid:' + new Date(closest * 1000).toISOString().split('T')[0]
                         + '|fbid=' + fbid;
                }
            }
        }
    }

    // 8a2: MEDIUM search — look for any occurrence of the fbid and grab
    //      the CLOSEST created_time within ±500 chars (tighter than before).
    if (fbid) {
        for (const s of scripts) {
            const c = s.textContent || '';
            let searchPos = 0;
            while (true) {
                const idx = c.indexOf(fbid, searchPos);
                if (idx === -1) break;
                searchPos = idx + 1;
                const windowStart = Math.max(0, idx - 500);
                const windowEnd = Math.min(c.length, idx + fbid.length + 500);
                const win = c.substring(windowStart, windowEnd);
                const localRe = /"(?:created_time|creation_time|publish_time)"\s*:\s*([12]\d{9})/g;
                let m;
                let closest = null;
                let closestDist = Infinity;
                const fbidPosInWin = idx - windowStart;
                while ((m = localRe.exec(win)) !== null) {
                    const ts = parseInt(m[1], 10);
                    if (ts > 1000000000) {
                        const dist = Math.abs(m.index - fbidPosInWin);
                        if (dist < closestDist) {
                            closest = ts;
                            closestDist = dist;
                        }
                    }
                }
                if (closest) {
                    return 'script_fbid2:' + new Date(closest * 1000).toISOString().split('T')[0]
                         + '|fbid=' + fbid;
                }
            }
        }
    }

    // 8b: Fallback — collect all named timestamps but skip anything
    //     older than 2009 (FB page/account creation artifacts).
    const allTimestamps = [];
    const cutoff2009 = 1230768000;  // 2009-01-01 UTC
    for (const s of scripts) {
        const c = s.textContent || '';
        let match;
        while ((match = tsFieldRe.exec(c)) !== null) {
            const ts = parseInt(match[1], 10);
            if (ts > cutoff2009) {
                allTimestamps.push(ts);
            }
        }
        tsFieldRe.lastIndex = 0;
    }
    if (allTimestamps.length > 0) {
        const oldest = Math.min(...allTimestamps);
        return 'script_all:' + new Date(oldest * 1000).toISOString().split('T')[0]
             + '|found=' + allTimestamps.length
             + '|oldest=' + new Date(oldest * 1000).toISOString().split('T')[0]
             + '|newest=' + new Date(Math.max(...allTimestamps) * 1000).toISOString().split('T')[0];
    }
} catch (e) {}

// Strategy 9: Broad visible-text search as last resort
const bodyText = document.body.innerText || '';
const lastResort = bodyText.match(dateRe);
if (lastResort) return 'body:' + lastResort[0];

return null;
"""

# Month name → number lookup for parsing
_MONTH_MAP = {
    'january': '01', 'february': '02', 'march': '03', 'april': '04',
    'may': '05', 'june': '06', 'july': '07', 'august': '08',
    'september': '09', 'october': '10', 'november': '11', 'december': '12'
}

class SharedDateExtractor:
    """Thread-safe date extractor that uses a tab in the main browser."""

    def __init__(self, driver):
        """Attach to the existing main browser and open one extra tab for
        date extraction.  No new Chrome process is created."""
        logging.info("Initializing SharedDateExtractor (tab in main browser)")
        self.driver = driver
        self.lock = threading.Lock()
        self._date_tab = None       # handle for our dedicated tab
        self._original_tab = None   # handle we should never close
        self._open_date_tab()

    # ── tab helpers ──────────────────────────────────────────────────────

    def _open_date_tab(self):
        """Open a single new tab for date work and switch back to the
        original tab so the main workflow is unaffected."""
        with self.lock:
            try:
                self._original_tab = self.driver.current_window_handle
                self.driver.execute_script("window.open('about:blank','_blank');")
                all_handles = self.driver.window_handles
                self._date_tab = [h for h in all_handles
                                  if h != self._original_tab][-1]
                # Switch back so the caller keeps its context
                self.driver.switch_to.window(self._original_tab)
                logging.info(f"Opened date-extraction tab ({self._date_tab})")
            except Exception as e:
                logging.error(f"Could not open date-extraction tab: {e}")
                self._date_tab = None

    def _ensure_date_tab(self):
        """Make sure our dedicated tab still exists; re-create if needed."""
        if self._date_tab and self._date_tab in self.driver.window_handles:
            return True
        logging.warning("Date-extraction tab gone – reopening")
        try:
            self.driver.execute_script("window.open('about:blank','_blank');")
            all_handles = self.driver.window_handles
            self._date_tab = [h for h in all_handles
                              if h != self._original_tab][-1]
            logging.info(f"Reopened date-extraction tab ({self._date_tab})")
            return True
        except Exception as e:
            logging.error(f"Failed to reopen date-extraction tab: {e}")
            self._date_tab = None
            return False

    # ── public API ───────────────────────────────────────────────────────

    def extract_date(self, photo_page_url):
        """Navigate the date tab to *photo_page_url*, run _DATE_JS, and
        return a 'YYYY-MM-DD' string or None."""
        logging.debug(f"Extracting date from: {photo_page_url[:100]}...")

        with self.lock:
            if not self._ensure_date_tab():
                logging.error("No date-extraction tab available")
                return None

            try:
                # Switch to the date tab, navigate, extract, switch back
                self.driver.switch_to.window(self._date_tab)
                
                # Set a page load timeout so we don't hang on heavy pages
                self.driver.set_page_load_timeout(15)
                try:
                    self.driver.get(photo_page_url)
                except Exception as load_err:
                    # Timeout or renderer crash — stop loading and try to
                    # extract whatever we can from the partial page
                    logging.warning(
                        f"Date tab page load issue on "
                        f"{photo_page_url[:80]}…: {load_err}")
                    try:
                        self.driver.execute_script("window.stop();")
                    except Exception:
                        pass
                
                time.sleep(3)  # let page settle

                # Set a script timeout so execute_script doesn't hang
                self.driver.set_script_timeout(10)
                try:
                    raw_date = self.driver.execute_script(_DATE_JS)
                except Exception as script_err:
                    logging.warning(
                        f"Date extraction script timed out on "
                        f"{photo_page_url[:80]}…: {script_err}")
                    raw_date = None

                if raw_date:
                    # The JS returns "strategy:value" so we can log which
                    # strategy succeeded and strip the prefix before parsing.
                    # The script strategy also appends "|found=N|newest=DATE"
                    # debug info that we strip before parsing.
                    strategy = 'unknown'
                    date_value = raw_date
                    if ':' in raw_date:
                        strategy, date_value = raw_date.split(':', 1)

                    # Strip diagnostic suffixes (e.g. "|found=5|newest=2026-02-13")
                    debug_info = ''
                    if '|' in date_value:
                        parts = date_value.split('|')
                        date_value = parts[0]
                        debug_info = ' [' + ', '.join(parts[1:]) + ']'

                    logging.info(
                        f"Strategy '{strategy}' returned '{date_value}'"
                        f"{debug_info} "
                        f"on {photo_page_url[:100]}...")

                    parsed = _parse_date_to_ymd(date_value)
                    if parsed:
                        logging.info(
                            f"Parsed date: {parsed} "
                            f"(strategy={strategy})")
                        return parsed
                    logging.warning(
                        f"Could not parse '{date_value}' "
                        f"(strategy={strategy}) from "
                        f"{photo_page_url[:100]}...")

                # Fallback: page-source analysis
                if not raw_date:
                    logging.warning(
                        f"No valid JS date on {photo_page_url[:100]}… "
                        "– trying page source")
                    try:
                        self.driver.set_page_load_timeout(10)
                        page_source = self.driver.page_source
                        from datetime import datetime, timedelta

                        utime_matches = re.findall(
                            r'data-utime="(\d+)"', page_source)
                        now_ts = int(datetime.now().timestamp())
                        cutoff = now_ts - 86400

                        for ut in utime_matches:
                            ts = int(ut)
                            if 1_000_000_000 < ts < cutoff:
                                d = datetime.fromtimestamp(ts).strftime(
                                    '%Y-%m-%d')
                                logging.info(
                                    f"Extracted date from data-utime: {d}")
                                return d

                        from datetime import date as _date
                        today_str = _date.today().strftime('%Y-%m-%d')
                        yesterday_str = (
                            _date.today() - timedelta(days=1)
                        ).strftime('%Y-%m-%d')
                        for dt_str in re.findall(
                                r'datetime="([^"]+)"', page_source):
                            p = _parse_date_to_ymd(dt_str)
                            if p and p not in (today_str, yesterday_str):
                                logging.info(
                                    f"Extracted date from datetime attr: {p}")
                                return p

                        logging.debug(
                            "No valid historical dates in page source")
                    except Exception as src_e:
                        logging.debug(
                            f"Page source analysis failed: {src_e}")

            except Exception as e:
                logging.error(
                    f"Exception extracting date from "
                    f"{photo_page_url[:100]}…: {e}")
            finally:
                # Always switch back to the original tab so the main
                # workflow is never disrupted
                try:
                    self.driver.switch_to.window(self._original_tab)
                except Exception:
                    pass

        return None

    def close_all(self):
        """Close the date-extraction tab (but NOT the main browser)."""
        logging.info("Closing date-extraction tab")
        with self.lock:
            if self._date_tab:
                try:
                    self.driver.switch_to.window(self._date_tab)
                    self.driver.close()
                    logging.debug("Closed date-extraction tab")
                except Exception as e:
                    logging.warning(
                        f"Error closing date-extraction tab: {e}")
                finally:
                    self._date_tab = None
                    try:
                        self.driver.switch_to.window(self._original_tab)
                    except Exception:
                        pass
        logging.info("Date-extraction tab closed")

# Global shared date extractor
_date_extractor = None
_date_extractor_lock = threading.Lock()


def _parse_date_to_ymd(raw):
    """Parse a raw date string from Facebook into 'YYYY-MM-DD' or None."""
    if not raw:
        return None
    raw = raw.strip()

    # ISO format: 2024-01-05T... or 2024-01-05
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    # "January 5, 2024" or "January 5 2024"
    m = re.match(r'(\w+)\s+(\d{1,2}),?\s+(\d{4})', raw, re.IGNORECASE)
    if m:
        mon = _MONTH_MAP.get(m.group(1).lower())
        if mon:
            return f"{m.group(3)}-{mon}-{int(m.group(2)):02d}"

    # "5 January, 2024" or "5 January 2024"
    m = re.match(r'(\d{1,2})\s+(\w+),?\s+(\d{4})', raw, re.IGNORECASE)
    if m:
        mon = _MONTH_MAP.get(m.group(2).lower())
        if mon:
            return f"{m.group(3)}-{mon}-{int(m.group(1)):02d}"

    # "1/5/2024" or "01/05/2024"  (assumes M/D/Y — US Facebook locale)
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', raw)
    if m:
        y = m.group(3)
        if len(y) == 2:
            y = '20' + y
        return f"{y}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"

    # "Jan 5, 2024" (abbreviated months)
    abbrev_months = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
        'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
    }
    m = re.match(r'(\w{3})\s+(\d{1,2}),?\s+(\d{4})', raw, re.IGNORECASE)
    if m:
        mon = abbrev_months.get(m.group(1).lower())
        if mon:
            return f"{m.group(3)}-{mon}-{int(m.group(2)):02d}"

    # "5 Jan 2024" (abbreviated, reversed)
    m = re.match(r'(\d{1,2})\s+(\w{3}),?\s+(\d{4})', raw, re.IGNORECASE)
    if m:
        mon = abbrev_months.get(m.group(2).lower())
        if mon:
            return f"{m.group(3)}-{mon}-{int(m.group(1)):02d}"

    logging.debug(f"Could not parse date: '{raw}'")
    return None


def _open_resolver_tabs(driver, count):
    """Ensure we have `count` extra tabs open (besides the original).
    Returns a list of `count` tab handles ready for use."""
    original = driver.window_handles[0]
    while len(driver.window_handles) < count + 1:
        driver.switch_to.window(driver.window_handles[-1])
        driver.execute_script("window.open('about:blank');")
    # Return all handles except the original
    return [h for h in driver.window_handles if h != original][:count]


def _close_resolver_tabs(driver, tab_handles):
    """Close the extra tabs and switch back to the first window."""
    original_handles = driver.window_handles
    original_tab = original_handles[0] if original_handles else None
    
    for h in tab_handles:
        try:
            if h in driver.window_handles:  # Check if handle still exists
                driver.switch_to.window(h)
                driver.close()
                logging.debug(f"Closed resolver tab: {h}")
        except Exception as e:
            logging.warning(f"Error closing tab {h}: {e}")
    
    # Ensure we switch back to a valid tab
    try:
        current_handles = driver.window_handles
        if original_tab and original_tab in current_handles:
            driver.switch_to.window(original_tab)
        elif current_handles:
            driver.switch_to.window(current_handles[0])
        logging.debug(f"Switched back to main tab, {len(current_handles)} tabs remaining")
    except Exception as e:
        logging.warning(f"Error switching back to main tab: {e}")


def resolve_batch_multi_tab(driver, links_batch, tab_handles,
                            timeout=PHOTO_PAGE_TIMEOUT):
    """Resolve full-res URLs for several photo links in parallel tabs.

    Navigates each tab to a different photo page, then polls all tabs
    in round-robin until every image resolves or the timeout expires.

    Returns a list of (link, full_url_or_None) in the same order as links_batch.
    """
    logging.debug(f"Resolving batch of {len(links_batch)} links with timeout {timeout}s")
    n = len(links_batch)
    img_results = [None] * n
    img_resolved = [False] * n

    # Navigate each tab to its photo page
    logging.debug("Navigating tabs to photo pages")
    for i in range(n):
        try:
            driver.switch_to.window(tab_handles[i])
            driver.get(links_batch[i])
            logging.debug(f"Tab {i+1}: navigated to {links_batch[i][:100]}...")
        except Exception as e:
            logging.warning(f"Tab {i+1}: navigation failed: {e}")

    # Poll until all images resolve or timeout
    end_time = time.time() + timeout
    poll_count = 0
    logging.debug(f"Starting polling for image resolution (timeout: {timeout}s)")
    while time.time() < end_time and not all(img_resolved):
        poll_count += 1
        resolved_this_round = 0
        
        # Check browser health every 20 polls
        if poll_count % 20 == 0:
            if not is_browser_responsive(driver, timeout=3):
                logging.warning(f"Browser health check failed during polling (round {poll_count})")
                break  # Exit polling loop gracefully
        
        for i in range(n):
            try:
                driver.switch_to.window(tab_handles[i])
                if not img_resolved[i]:
                    result = driver.execute_script(_FULLRES_JS, SRC_PREFIX,
                                                   MIN_FULL_RES_NAT_WIDTH)
                    if result:
                        img_results[i] = result
                        img_resolved[i] = True
                        resolved_this_round += 1
                        logging.debug(f"Tab {i+1}: resolved image URL")
            except Exception as e:
                logging.warning(f"Tab {i+1}: polling failed: {e}")
        
        if poll_count % 10 == 0:
            resolved_count = sum(img_resolved)
            logging.debug(f"Polling round {poll_count}: {resolved_count}/{n} resolved")
        
        if resolved_this_round == 0:
            time.sleep(0.2)  # Brief pause if no progress
    
    resolved_count = sum(img_resolved)
    logging.info(f"Batch resolution complete: {resolved_count}/{n} resolved in {poll_count} polls")
    
    return list(zip(links_batch, img_results))


def resolve_and_download(driver, photo_links, output_dir):
    """Visit each photo page, grab the full-res image URL, and download.

    Uses RESOLVER_TABS browser tabs in parallel to resolve multiple photo
    pages at once.  Downloads run in background threads.

    Progress is checkpointed to disk every PHASE2_BATCH_SIZE photos so
    the script can resume where it left off after a crash.
    Returns total saved count.
    """
    global failed_downloads, _date_extractor
    
    # Initialize shared date extractor (uses a tab in the main browser)
    with _date_extractor_lock:
        if _date_extractor is None:
            print("  Initializing date extraction tab...")
            _date_extractor = SharedDateExtractor(driver)
            logging.info("Initialized shared date extractor (tab in main browser)")
    
    with failed_downloads_lock:
        failed_downloads.clear()  # Reset for this run
        
    os.makedirs(output_dir, exist_ok=True)
    total = len(photo_links)
    if total == 0:
        return 0

    # Build a map from link → its 1-based position on the webpage
    link_to_page_order = {lnk: i + 1 for i, lnk in enumerate(photo_links)}

    # ── Load checkpoint (resume support) ──
    processed = load_checkpoint()
    remaining_links = [lnk for lnk in photo_links if lnk not in processed]
    skipped_resume = total - len(remaining_links)
    if skipped_resume > 0:
        print(f"  Resuming — skipping {skipped_resume} already-processed photos")
    total_remaining = len(remaining_links)
    if total_remaining == 0:
        print("  All photos already processed. Nothing to do.")
        clear_checkpoint()
        return 0

    print(f"  Resolving & downloading {total_remaining} full-res images ")
    print(f"  ({RESOLVER_TABS} tabs in parallel, "
          f"checkpoint every {PHASE2_BATCH_SIZE})...\n")

    # ── Open parallel resolver tabs ──
    tab_handles = _open_resolver_tabs(driver, RESOLVER_TABS)
    actual_tabs = len(tab_handles)
    print(f"  Opened {actual_tabs} resolver tabs.\n")

    # ── Start download worker threads ──
    download_queue = Queue()
    stats = {"saved": 0, "failed": 0, "skipped": 0, "dupes": 0}
    stats_lock = threading.Lock()
    seen_urls = set()  # dedupe: track normalized full-res URLs already queued
    existing_files = _get_existing_cwas_files(output_dir)  # file-system level deduplication
    
    if existing_files:
        logging.info(f"Found {len(existing_files)} existing CWAS files in output directory")
        print(f"  Found {len(existing_files)} existing CWAS files - will skip these numbers")
    
    workers = []
    for _ in range(DOWNLOAD_WORKERS):
        t = threading.Thread(target=_download_worker,
                             args=(download_queue, output_dir, stats, stats_lock),
                             daemon=True)
        t.start()
        workers.append(t)

    checkpoint_count = 0  # photos resolved since last checkpoint save

    try:
        # Process links in chunks of actual_tabs
        for chunk_start in range(0, total_remaining, actual_tabs):
            # Check browser health before processing each chunk
            driver = restart_driver_if_needed(driver)
            
            chunk = remaining_links[chunk_start:chunk_start + actual_tabs]
            chunk_tabs = tab_handles[:len(chunk)]

            # Resolve this chunk across parallel tabs
            results = resolve_batch_multi_tab(driver, chunk, chunk_tabs)

            for j, (link, full_url) in enumerate(results):
                page_num = link_to_page_order[link]
                with stats_lock:
                    saved_so_far = stats["saved"]
                progress = f"{skipped_resume + chunk_start + j + 1}/{total}"

                if full_url:
                    # Check if this page number already exists as a file
                    if page_num in existing_files:
                        with stats_lock:
                            stats["dupes"] += 1
                        print(f"  [{progress}] CWAS_{page_num:04d} "
                              f"(saved {saved_so_far + skipped_resume}) ∷ file exists")
                        processed.add(link)
                        checkpoint_count += 1
                        continue
                    
                    # Normalize URL for better deduplication
                    normalized_url = _normalize_image_url(full_url)
                    
                    if normalized_url in seen_urls:
                        with stats_lock:
                            stats["dupes"] += 1
                        print(f"  [{progress}] CWAS_{page_num:04d} "
                              f"(saved {saved_so_far + skipped_resume}) ∷ duplicate URL")
                    else:
                        seen_urls.add(normalized_url)
                        download_queue.put((full_url, page_num, link))  # Include photo page URL for date extraction
                        print(f"  [{progress}] CWAS_{page_num:04d} "
                              f"(saved {saved_so_far + skipped_resume}) ✓ queued")
                else:
                    with stats_lock:
                        stats["skipped"] += 1
                    print(f"  [{progress}] CWAS_{page_num:04d} "
                          f"(saved {saved_so_far + skipped_resume}) ✗ timeout")

                processed.add(link)
                checkpoint_count += 1

            # ── Checkpoint periodically ──
            if checkpoint_count >= PHASE2_BATCH_SIZE:
                save_checkpoint(processed)
                print(f"    💾 checkpoint saved ({len(processed)}/{total} processed)")
                checkpoint_count = 0

    finally:
        # ── Save checkpoint on exit (crash or normal) ──
        save_checkpoint(processed)

        # ── Close resolver tabs ──
        _close_resolver_tabs(driver, tab_handles)

        # ── Wait for remaining downloads ──
        remaining = download_queue.qsize()
        if remaining > 0:
            print(f"\n  Resolution done. Waiting for {remaining} remaining downloads...")
        for _ in workers:
            download_queue.put(None)   # poison pill
        download_queue.join()
        for t in workers:
            t.join()

    # ── Retry failed downloads ──
    if failed_downloads:
        retry_successes, retry_failures = retry_failed_downloads(output_dir)
        with stats_lock:
            stats["saved"] += retry_successes
            stats["failed"] = retry_failures  # update to final failure count
    else:
        print("\n  No failed downloads to retry.")

    # ── Clean up checkpoint if everything was processed ──
    if len(processed) >= total:
        clear_checkpoint()
        print("  Checkpoint cleared (all photos processed).")

    # Update global performance stats
    perf_stats['total_dupes_skipped'] = stats['dupes']
    perf_stats['total_failed'] = stats['failed'] 
    perf_stats['total_timeouts'] = stats['skipped']
    
    # Cleanup shared date extractor
    with _date_extractor_lock:
        if _date_extractor:
            print("  Closing date extraction tab...")
            _date_extractor.close_all()
            _date_extractor = None
            logging.info("Closed shared date extractor tab")

    print(f"\n  Phase 2 complete: {stats['saved']} saved, "
          f"{stats['dupes']} dupes skipped, "
          f"{stats['failed']} failed, {stats['skipped']} skipped "
          f"→ {output_dir}")
    return stats["saved"] + skipped_resume


# ─── Main ────────────────────────────────────────────────────────────────────

def _generate_performance_report():
    """Generate and print a comprehensive performance report."""
    total_time = perf_stats['script_end'] - perf_stats['script_start']
    phase1_time = perf_stats['phase1_end'] - perf_stats['phase1_start'] if perf_stats['phase1_end'] > 0 else 0
    phase2_time = perf_stats['phase2_end'] - perf_stats['phase2_start'] if perf_stats['phase2_end'] > 0 else 0
    
    print("\n" + "=" * 70)
    print("  PERFORMANCE REPORT")
    print("=" * 70)
    
    # Timing
    print(f"\n📊 TIMING:")
    print(f"  Total runtime:     {total_time/60:.1f} min ({total_time:.0f}s)")
    if phase1_time > 0:
        print(f"  Phase 1 (scroll):   {phase1_time/60:.1f} min ({phase1_time:.0f}s)")
    if phase2_time > 0:
        print(f"  Phase 2 (resolve):  {phase2_time/60:.1f} min ({phase2_time:.0f}s)")
    
    # Data processing
    print(f"\n📈 DATA PROCESSING:")
    if perf_stats['total_links_collected'] > 0:
        links_per_min = perf_stats['total_links_collected'] / (phase1_time / 60) if phase1_time > 0 else 0
        print(f"  Links collected:    {perf_stats['total_links_collected']} ({links_per_min:.0f}/min)")
    
    if perf_stats['total_images_saved'] > 0:
        images_per_min = perf_stats['total_images_saved'] / (phase2_time / 60) if phase2_time > 0 else 0
        print(f"  Images saved:       {perf_stats['total_images_saved']} ({images_per_min:.1f}/min)")
    
    if perf_stats['total_dupes_skipped'] > 0:
        print(f"  Duplicates skipped: {perf_stats['total_dupes_skipped']}")
    if perf_stats['total_failed'] > 0:
        print(f"  Download failures:  {perf_stats['total_failed']}")
    if perf_stats['total_timeouts'] > 0:
        print(f"  Resolution timeouts: {perf_stats['total_timeouts']}")
    if perf_stats['retry_attempts'] > 0:
        print(f"  Retry attempts:     {perf_stats['retry_attempts']} ({perf_stats['retry_successes']} successful)")
    
    # Network
    if perf_stats['total_bytes_downloaded'] > 0:
        mb_total = perf_stats['total_bytes_downloaded'] / 1024 / 1024
        if total_time > 0:
            mb_per_sec = mb_total / total_time
            print(f"\n🌐 NETWORK:")
            print(f"  Data downloaded:    {mb_total:.1f} MB")
            print(f"  Average speed:      {mb_per_sec:.2f} MB/s")
    
    # Memory
    if perf_stats['peak_memory_mb'] > 0:
        print(f"\n💾 MEMORY:")
        print(f"  Peak usage:         {perf_stats['peak_memory_mb']:.1f} MB")
    elif psutil is None:
        print(f"\n💾 MEMORY:")
        print(f"  Peak usage:         N/A (install 'psutil' for tracking)")
    
    # Configuration summary
    print(f"\n  CONFIG USED:")
    print(f"  Resolver tabs:      {RESOLVER_TABS}")
    print(f"  Download workers:   {DOWNLOAD_WORKERS}")
    print(f"  Page timeout:       {PHOTO_PAGE_TIMEOUT}s")
    print(f"  Scroll pause:       {SCROLL_PAUSE}s")
    
    print("\n" + "=" * 70)


def main(run_mode=None, auto_mode=False):
    # Set up enhanced logging
    try:
        from logging_config import setup_enhanced_logging, log_system_info, create_session_logger
        logger = setup_enhanced_logging("scraper", enable_debug_file=True)
        
        # Log system info for diagnostics
        log_system_info()
        
        # Create session logger for this run
        session_logger, session_id = create_session_logger()
        session_logger.info("Scraper session started")
        
    except ImportError:
        # Fallback to basic logging if logging_config is not available
        log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraper.log")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        logger = logging.getLogger(__name__)
        session_logger = logger
        session_id = "fallback"
    
    logging.info("=" * 80)
    logging.info("Facebook Image Scraper Started")
    logging.info(f"Run mode: {run_mode}, Auto mode: {auto_mode}")
    logging.info(f"Session ID: {session_id}")
    logging.info("=" * 80)
    
    perf_stats['script_start'] = time.time()
    _track_memory()
    
    print("=" * 60)
    print("  Facebook Image Scraper — CWAS Photos (Full Resolution)")
    print("=" * 60)
    logging.info("Script started")

    # 1. Launch browser
    print("\n[1/4] Launching browser...")
    logging.info("Phase 1: Launching browser")
    perf_stats['browser_start'] = time.time()
    try:
        driver = setup_driver()
        browser_time = time.time() - perf_stats['browser_start']
        logging.info(f"Browser launched successfully in {browser_time:.1f}s")
        session_logger.info(f"Browser initialization: {browser_time:.1f}s")
    except Exception as e:
        logging.error(f"Failed to launch browser: {e}")
        session_logger.error(f"Browser launch failed: {e}")
        raise

    try:
        # 2. Navigate to the page
        print(f"[2/4] Loading page: {URL}")
        logging.info(f"Phase 2: Loading target page: {URL}")
        nav_start = time.time()
        
        # Set page load timeout to prevent hanging
        driver.set_page_load_timeout(60)  # 60 second timeout
        
        try:
            driver.get(URL)
            nav_time = time.time() - nav_start
            logging.info(f"Page loaded in {nav_time:.1f}s")
            session_logger.info(f"Page navigation: {nav_time:.1f}s")
        except Exception as e:
            logging.warning(f"Page load timeout or error: {e}")
            # Try to stop loading and continue
            try:
                driver.execute_script("window.stop();")
                logging.info("Stopped page loading, continuing with partial load")
            except:
                pass

        # Wait for the page to be ready (skip in auto mode)
        if not auto_mode:
            print("\n" + "=" * 60)
            print("  The browser is now open.")
            print("  If already logged in, just wait for photos to load.")
            print("  If not, log in first, then wait for photos to appear.")
            print("=" * 60)
            logging.info("Waiting for user confirmation to proceed")
            input("\n>>> Press ENTER when the photos page is visible... ")
            logging.info("User confirmed page is ready")
            session_logger.info("User confirmed page ready")
            print("\nResuming...")
            
            # Post-login stabilization measures
            print("  Applying post-login stabilization...")
            logging.info("Starting post-login stabilization")
            
            # Disable heavy content to prevent crashes
            try:
                # Stop all animations and heavy JavaScript
                driver.execute_script("""
                    // Stop all animations
                    document.querySelectorAll('*').forEach(el => {
                        el.style.animationDuration = '0s';
                        el.style.transitionDuration = '0s';
                    });
                    
                    // Remove video elements that consume memory
                    document.querySelectorAll('video').forEach(v => v.remove());
                    
                    // Pause all timers and intervals
                    var highestTimeoutId = setTimeout(function(){}, 0);
                    for (var i = 0 ; i < highestTimeoutId ; i++) {
                        clearTimeout(i);
                    }
                """)
                logging.debug("Applied JavaScript stabilization")
            except Exception as e:
                logging.warning(f"JavaScript stabilization failed: {e}")
            
            # Additional settle time after login and stabilization
            time.sleep(5)
            
            # Check browser health after login
            if not is_browser_responsive(driver):
                logging.error("Browser became unresponsive after login")
                driver = restart_driver_if_needed(driver)
                driver.get(URL)
                time.sleep(5)
            
            logging.info("Post-login stabilization complete")
        else:
            print("  Auto mode: Waiting for page to load...")
            time.sleep(10)  # Give more time for auto mode
            
            # Check browser health in auto mode too
            if not is_browser_responsive(driver):
                logging.error("Browser became unresponsive during auto mode load")
                driver = restart_driver_if_needed(driver)
                driver.get(URL)
                time.sleep(10)

        # Get user choice for run mode (or use provided mode)
        if run_mode is None:
            run_mode = get_run_mode()
        
        # Handle bookmark based on user choice
        if run_mode == 'refresh':
            print("\n  🔄 COMPLETE REFRESH MODE - Starting fresh, ignoring any existing bookmark")
            previous_bookmark = None
            # Clear existing checkpoint to start fresh
            if os.path.exists(CHECKPOINT_FILE):
                os.remove(CHECKPOINT_FILE)
                print("  Cleared existing checkpoint file")
        else:
            print("\n  📥 UPDATE MODE - Loading bookmark from last run")
            previous_bookmark = load_bookmark()
            if not previous_bookmark:
                print("  No bookmark found - this will work like a complete refresh")

        # Phase 1: Scroll and collect photo-page links
        print("[3/4] Phase 1 — Scrolling and collecting photo links...")
        print(f"  (collecting links every {COLLECT_EVERY_N} scrolls)\n")
        perf_stats['phase1_start'] = time.time()
        logging.info("Phase 1 started - collecting photo links")
        
        # Add crash recovery for Phase 1
        max_phase1_attempts = 3
        for attempt in range(max_phase1_attempts):
            try:
                photo_links, first_link = scroll_and_collect_links(driver, previous_bookmark)
                break  # Success
            except Exception as e:
                logging.error(f"Phase 1 attempt {attempt + 1} failed: {e}")
                if attempt < max_phase1_attempts - 1:
                    print(f"  Phase 1 failed, restarting browser and retrying... (attempt {attempt + 2}/{max_phase1_attempts})")
                    driver = restart_driver_if_needed(driver)
                    # Re-navigate to the page
                    driver.get(URL)
                    time.sleep(5)
                else:
                    raise
                    
        perf_stats['phase1_end'] = time.time()
        perf_stats['total_links_collected'] = len(photo_links)
        phase1_duration = perf_stats['phase1_end'] - perf_stats['phase1_start']
        logging.info(f"Phase 1 completed in {phase1_duration:.1f}s - {len(photo_links)} links collected")
        _track_memory()

        if not photo_links:
            print("\nNo photo links found. Running diagnostics...\n")

            page_source = driver.page_source
            debug_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_page.html")
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(page_source)
            print(f"  Saved full page HTML to: {debug_path}")

            imgs = driver.find_elements(By.TAG_NAME, "img")
            print(f"\n  Total <img> elements on page: {len(imgs)}")
            print("\n  --- Sample of <img> tags (first 30) ---")
            for idx, img in enumerate(imgs[:30]):
                src = img.get_attribute("src") or "(no src)"
                w = img.size.get("width", "?")
                h = img.size.get("height", "?")
                print(f"    [{idx+1}] {w}x{h}  src={src[:100]}")

            scontent_imgs = [img for img in imgs if "scontent" in (img.get_attribute("src") or "")]
            print(f"\n  <img> with 'scontent' in src: {len(scontent_imgs)}")
            for idx, img in enumerate(scontent_imgs[:20]):
                src = img.get_attribute("src") or ""
                w = img.size.get("width", "?")
                h = img.size.get("height", "?")
                print(f"    [{idx+1}] {w}x{h}  src={src[:120]}")

            print("\n  Check debug_page.html and the info above to identify the correct selectors.")
            return

        # 4. Phase 2: Open each photo page and download full-res image
        print(f"[4/4] Phase 2 — Opening each photo for full-resolution download...")
        perf_stats['phase2_start'] = time.time()
        logging.info("Phase 2 started - resolving and downloading images")
        saved_count = resolve_and_download(driver, photo_links, OUTPUT_DIR)
        perf_stats['phase2_end'] = time.time()
        perf_stats['total_images_saved'] = saved_count
        phase2_duration = perf_stats['phase2_end'] - perf_stats['phase2_start']
        logging.info(f"Phase 2 completed in {phase2_duration:.1f}s - {saved_count} images saved")
        _track_memory()

        # 5. Save this run's bookmark for next time (only if we found new content)
        if first_link and run_mode == 'update':
            save_bookmark(first_link)
        elif first_link and run_mode == 'refresh':
            save_bookmark(first_link)
            print(f"  💾 New bookmark saved for future update runs")

        print(f"\n{'=' * 60}")
        print(f"  All done!  {saved_count} full-res images saved to:")
        print(f"  {OUTPUT_DIR}")
        print(f"{'=' * 60}")
        
        perf_stats['script_end'] = time.time()
        logging.info(f"Script completed successfully in {perf_stats['script_end'] - perf_stats['script_start']:.1f}s")
        _generate_performance_report()

    except Exception as e:
        perf_stats['script_end'] = time.time()
        logging.error(f"Script failed: {e}")
        _generate_performance_report()
        raise

    finally:
        driver.quit()
        print("\nBrowser closed.")


def test_date_extraction(photo_url=None):
    """Test date extraction on a specific Facebook photo URL for debugging.
    
    Args:
        photo_url (str): Facebook photo URL to test. If None, prompts for input.
    """
    if not photo_url:
        photo_url = input("Enter a Facebook photo URL to test date extraction: ").strip()
    
    if not photo_url:
        print("No URL provided.")
        return
    
    print(f"Testing date extraction on: {photo_url}")
    
    # Use a single browser instance for testing
    driver = setup_driver()
    try:
        driver.get(photo_url)
        time.sleep(3)  # Wait for page to load
        
        # Execute the date extraction JavaScript
        raw_date = driver.execute_script(_DATE_JS)
        print(f"Raw result: {raw_date}")
        
        if raw_date:
            strategy = 'unknown'
            date_value = raw_date
            if ':' in raw_date:
                strategy, date_value = raw_date.split(':', 1)
            print(f"Strategy: {strategy}")
            print(f"Date value: {date_value}")
            parsed_date = _parse_date_to_ymd(date_value)
            print(f"Parsed date: {parsed_date}")
        else:
            print("No date found. Let's examine the page structure...")
            
            # Check what date-related elements exist
            elements_check = """
            const elements = [];
            
            // Check for time tags
            document.querySelectorAll('time').forEach(el => {
                elements.push(`TIME: ${el.outerHTML.slice(0, 200)}`);
            });
            
            // Check for data-utime attributes
            document.querySelectorAll('[data-utime]').forEach(el => {
                elements.push(`DATA-UTIME: ${el.outerHTML.slice(0, 200)}`);
            });
            
            // Check aria-labels for dates
            document.querySelectorAll('[aria-label]').forEach(el => {
                const label = el.getAttribute('aria-label');
                if (label && /\\d{1,2}.\\d{1,2}.\\d{2,4}|january|february|march|april|may|june|july|august|september|october|november|december|yesterday|ago/i.test(label)) {
                    elements.push(`ARIA-LABEL: ${label}`);
                }
            });
            
            return elements.slice(0, 10);  // Return first 10 matches
            """
            
            elements = driver.execute_script(elements_check)
            if elements:
                print("Found these date-related elements:")
                for elem in elements:
                    print(f"  {elem}")
            else:
                print("No date-related elements found.")
    
    except Exception as e:
        print(f"Error during test: {e}")
    finally:
        driver.quit()
    
    print("Test complete.")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test_date":
        # Run date extraction test
        test_url = sys.argv[2] if len(sys.argv) > 2 else None
        test_date_extraction(test_url)
    else:
        # Run the main scraper
        main()
