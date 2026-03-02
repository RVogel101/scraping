#!/usr/bin/env python3

import sys
import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_driver():
    """Set up Chrome WebDriver."""
    options = Options()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

# Updated JavaScript for date extraction
_DATE_JS = """
// Strategy 1: data-utime attributes (Unix timestamp) - common in modern FB
const utimeElements = document.querySelectorAll('[data-utime]');
for (const el of utimeElements) {
    const ts = parseInt(el.getAttribute('data-utime'), 10);
    if (ts && ts > 1000000000) { // Valid Unix timestamp
        return new Date(ts * 1000).toISOString().split('T')[0];
    }
}

// Strategy 2: datetime attributes in time elements
const timeElements = document.querySelectorAll('time[datetime]');
for (const el of timeElements) {
    const dt = el.getAttribute('datetime');
    if (dt) return dt;
}

// Strategy 3: JSON-LD structured data (common in modern Facebook)
const jsonLdScripts = document.querySelectorAll('script[type="application/ld+json"]');
for (const script of jsonLdScripts) {
    try {
        const data = JSON.parse(script.textContent);
        if (data.datePublished) return data.datePublished;
        if (data.dateCreated) return data.dateCreated;
        if (data.uploadDate) return data.uploadDate;
    } catch (e) {}
}

// Strategy 4: Modern Facebook selectors for photo pages
const fbSelectors = [
    'a[href*="/posts/"] span',
    '[data-testid="post_timestamp"]',
    '[data-testid="story-subtitle"]', 
    '[data-testid="photo_viewer_timestamp"]',
    '[role="link"][href*="/posts/"] span',
    '.timestamp',
    'div[dir="ltr"] > span > span',
    'a[href*="fbid="] + div span'
];

for (const selector of fbSelectors) {
    const elements = document.querySelectorAll(selector);
    for (const el of elements) {
        const text = (el.textContent || '').trim();
        // Look for date patterns in the text
        const dateMatch = text.match(/\\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\\s+\\d{1,2},?\\s+\\d{4}|\\d{1,2}\\/\\d{1,2}\\/\\d{2,4}|\\d{4}-\\d{2}-\\d{2}/i);
        if (dateMatch) return dateMatch[0];
    }
}

// Strategy 5: aria-label attributes (Facebook often puts readable dates here)
const ariaElements = document.querySelectorAll('[aria-label]');
for (const el of ariaElements) {
    const label = el.getAttribute('aria-label') || '';
    // Look for dates in aria-labels
    const dateMatch = label.match(/\\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\\s+\\d{1,2},?\\s+\\d{4}|\\d{1,2}\\/\\d{1,2}\\/\\d{2,4}/i);
    if (dateMatch) return dateMatch[0];
    
    // Handle relative dates
    const now = new Date();
    if (/yesterday/i.test(label)) {
        const yesterday = new Date(now);
        yesterday.setDate(yesterday.getDate() - 1);
        return yesterday.toISOString().split('T')[0];
    }
    
    const daysMatch = label.match(/(\\d+)\\s+days?\\s+ago/i);
    if (daysMatch) {
        const days = parseInt(daysMatch[1]);
        const date = new Date(now);
        date.setDate(date.getDate() - days);
        return date.toISOString().split('T')[0];
    }
    
    const weeksMatch = label.match(/(\\d+)\\s+weeks?\\s+ago/i);
    if (weeksMatch) {
        const weeks = parseInt(weeksMatch[1]);
        const date = new Date(now);
        date.setDate(date.getDate() - (weeks * 7));
        return date.toISOString().split('T')[0];
    }
}

// Strategy 6: Look for elements with title attributes
const titledElements = document.querySelectorAll('[title]');
for (const el of titledElements) {
    const title = el.title;
    const dateMatch = title.match(/\\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\\s+\\d{1,2},?\\s+\\d{4}|\\d{1,2}\\/\\d{1,2}\\/\\d{2,4}|\\d{4}-\\d{2}-\\d{2}/i);
    if (dateMatch) return dateMatch[0];
}

// Strategy 7: Broad text search as fallback
const bodyText = document.body.innerText || '';
const textDateMatch = bodyText.match(/\\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\\s+\\d{1,2},?\\s+\\d{4}|\\d{1,2}\\/\\d{1,2}\\/\\d{2,4}/i);
if (textDateMatch) return textDateMatch[0];

return null;
"""

def test_date_extraction_on_facebook_photo():
    """Test date extraction on a Facebook photo page."""
    driver = setup_driver()
    
    try:
        # Load the debug page we saved earlier
        debug_page_path = r"c:\Users\litni\OneDrive\Documents\anki\scraping\debug_page.html"
        if os.path.exists(debug_page_path):
            logging.info("Loading saved debug page for testing...")
            driver.get(f"file:///{debug_page_path}")
            time.sleep(2)
            
            # Try to extract date using our JavaScript
            logging.info("Testing date extraction JavaScript...")
            raw_date = driver.execute_script(_DATE_JS)
            
            if raw_date:
                logging.info(f"✓ Successfully extracted raw date: {raw_date}")
            else:
                logging.warning("✗ No date found with JavaScript")
                
                # Let's see what time-related elements exist
                time_elements = driver.execute_script("""
                    const elements = document.querySelectorAll('time, [datetime], [data-utime], [title], [aria-label]');
                    const results = [];
                    for (let i = 0; i < Math.min(10, elements.length); i++) {
                        const el = elements[i];
                        results.push({
                            tag: el.tagName,
                            datetime: el.getAttribute('datetime'),
                            utime: el.getAttribute('data-utime'),
                            title: el.getAttribute('title'),
                            ariaLabel: el.getAttribute('aria-label'),
                            text: el.textContent ? el.textContent.substring(0, 100) : null
                        });
                    }
                    return results;
                """)
                
                logging.info(f"Found {len(time_elements)} time-related elements:")
                for i, elem in enumerate(time_elements):
                    logging.info(f"  Element {i+1}: {elem}")
        else:
            logging.error(f"Debug page not found at {debug_page_path}")
            
    except Exception as e:
        logging.error(f"Error during test: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    test_date_extraction_on_facebook_photo()