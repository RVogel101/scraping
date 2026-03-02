# Western Armenian Text Corpus — Source Documentation

## Overview

We built a Western Armenian (WA) frequency corpus by scraping and processing text from four distinct sources: Western Armenian Wikipedia, diaspora newspaper websites, Internet Archive scanned books, and the Nayiri online dictionary. These were aggregated into a unified frequency list of **798,403 unique word forms** used for Anki flashcard generation.

The corpus was built specifically to get **Western Armenian** text, which is the diaspora dialect spoken in Lebanon, Syria, Turkey, France, the Americas, etc. — as opposed to Eastern Armenian (the official language of the Republic of Armenia). WA has distinct orthography, grammar, and vocabulary from EA, making it critical to source text from the right dialect.

---

## Source 1: Western Armenian Wikipedia (hyw.wikipedia.org)

### What it is
The Western Armenian Wikipedia (`hyw.wikipedia.org`) is a separate Wikipedia edition written in Western Armenian using classical/Mashtotsian orthography. It is distinct from the Eastern Armenian Wikipedia (`hy.wikipedia.org`).

### How it was scraped
- Downloaded the full database dump (compressed XML `.bz2` file) from `dumps.wikimedia.org/hywwiki/`
- The scraper auto-discovers the latest available dump date
- The XML dump is streamed and decompressed, extracting article text from `<text>` elements within the MediaWiki namespace
- Wikitext markup is cleaned via regex: templates `{{...}}`, file/image links, categories, external links, HTML tags, `<ref>` citations, heading markers, bold/italic markup, list markers, and table markup are all stripped
- Redirect pages are detected and skipped
- Only article namespace content is kept (talk pages, user pages, etc. are filtered by namespace ID)
- Text is then tokenized: NFC Unicode normalization, Armenian ligature decomposition (ﬓ→մն, ﬔ→մե, etc.), Armenian uppercase→lowercase conversion, then Armenian-script words extracted via regex `[\u0531-\u0556\u0561-\u0587\uFB13-\uFB17]+`

### Results
- **Dump size**: 22.76 MB (bz2 compressed)
- **Unique word forms**: 300,624
- **Words appearing in final corpus from this source**: 164,892
- Saved to `wa_corpus/data/wiki/wiki_frequencies.json`

### Status: ✅ Fully working
This was the cleanest, most reliable source. The text is guaranteed to be Western Armenian (it's the whole point of the hyw Wikipedia edition). Formal/encyclopedic register — good for vocabulary breadth but less representative of everyday speech.

---

## Source 2: Diaspora Newspapers (Aztag Daily, Horizon Weekly)

### What they are
- **Aztag Daily** (`aztagdaily.com`) — a Beirut-based Western Armenian daily newspaper, one of the oldest Armenian-language dailies still publishing
- **Horizon Weekly** (`horizonweekly.ca`) — a Montreal-based Western Armenian weekly newspaper

### How they were scraped
- Uses **Selenium** with headless Chrome (JavaScript-rendered pages require a real browser)
- For each source, the scraper paginates through listing pages (e.g., `/archives/category/featured/page/{N}`) collecting article URLs
- CSS selectors are configured per-source for: article link extraction, body content, title, and date
- For each article URL, the page is loaded, and text is extracted from `<p>` tags within the content container
- Articles are filtered to contain at least 30 Armenian characters (to skip English-only or empty pages)
- URL fragments (`#respond`, etc.) are stripped to prevent duplicates
- Articles are saved incrementally to a JSONL checkpoint file (`articles.jsonl`) for resume capability
- Rate-limited with 2-second delays between requests
- Anti-detection measures: custom user-agent, webdriver property spoofed, automation flags suppressed

### Results — Aztag Daily
- **Articles scraped**: 990
- **Total text**: ~1.93 million characters (3.85 MB JSONL)
- **Unique word forms contributing to corpus**: 23,449
- Scraped across 50 listing pages, 20 articles per page
- Some articles were deduplicated (URL fragments causing duplicates were cleaned)

### Results — Horizon Weekly
- **Articles scraped**: 0
- The listing page (`horizonweekly.ca/en/category/armenian/`) returned **0 article links** — the CSS selectors (`h2 a, .entry-title a, .post-title a, article a`) did not match any elements on the page
- Likely cause: the site redesigned or uses a different DOM structure than expected; the Armenian-language section may use different URL paths or the content is loaded via JavaScript in a way the selectors don't capture
- The scraper gracefully stopped after finding no links on page 1

### Status: ⚠️ Partially working
- **Aztag**: ✅ Working well — 990 articles of modern journalistic WA text
- **Horizon**: ❌ Did not work — 0 articles extracted due to selector mismatch / site structure change

---

## Source 3: Internet Archive (archive.org)

### What it is
The Internet Archive hosts thousands of scanned Armenian-language books, periodicals, and manuscripts from diaspora publishers. Many of these have existing OCR text in DjVuTXT format generated by IA's automated processing.

### How it was scraped
- Uses the **IA Advanced Search API** (`archive.org/advancedsearch.php`) — no authentication required
- Five search queries target WA content:
  1. `language:arm AND mediatype:texts` (broad Armenian-language texts)
  2. `(armenian AND beirut) AND mediatype:texts` (Beirut publishers — strong WA signal)
  3. `(armenian AND (istanbul OR constantinople)) AND mediatype:texts` (Istanbul diaspora)
  4. `(mechitarist OR mekhitarist) AND mediatype:texts` (Venice Mechitarist congregation — WA literary tradition)
  5. `(armenian AND (periodical OR journal)) AND mediatype:texts AND language:arm` (periodicals)
- Results are deduplicated across queries by IA identifier
- For each cataloged item, the **Metadata API** (`archive.org/metadata/{id}/files`) is queried to discover available file formats
- **DjVuTXT** files (plain text OCR output, typically ~100KB each) are downloaded by default
- hOCR and chOCR were initially downloaded but later deleted (multi-MB HTML files with layout coordinates we don't need)
- Files are downloaded with resume capability (skips already-downloaded files)
- Rate-limited with 1-second delays between API calls
- A checkpoint catalog (`catalog.json`) tracks all cataloged items and download status

### Important caveat: WA vs EA vs multilingual
The IA collection is **not exclusively Western Armenian**. The search queries cast a wide net:
- Many items are **Eastern Armenian** or even **Classical Armenian (grabar)**
- Some are multilingual (Armenian + Russian, Armenian + English, Armenian + Ottoman Turkish, etc.)
- A `wa_classifier.py` module exists that scores texts using five signal categories (orthography markers like the իdelays digraph, WA-specific grammar like the կdelays present-tense prefix, WA vocabulary, known WA authors, and diaspora publication cities) but this classifier was not applied as a filter during the IA download — all Armenian-language OCR text was downloaded and included in the frequency counts
- This means the IA frequency data is a mix of WA, EA, and grabar text, which dilutes the WA-specificity of that source

### Results
- **Cataloged items**: 342
- **Downloaded items**: 342 (all attempted)
- **Items with OCR text**: 320 (22 had no DjVuTXT available)
- **DjVu text files**: 2,640 individual files
- **Total OCR text**: 783.16 MB
- **Unique word forms contributing to corpus**: 723,132 (the largest source by far)
- 57 different file formats observed across the collection (DjVuTXT, EPUB, PDF, JP2 images, etc.)
- Example items include: historical periodicals ("Արեւելdelays" 1890), dictionaries ("Baṛaran angghierēn, hayerēn ew hayataṛ tʻurkʻerēn"), scholarly works, Soviet-era publications, etc.

### Status: ✅ Working, but with caveats
- The download pipeline works reliably
- The OCR quality varies enormously — some texts have excellent OCR, others are garbled (especially older scans with degraded print)
- **The big caveat**: no WA/EA classification filter was applied, so the IA data includes significant Eastern Armenian and Classical Armenian content mixed in with the WA text. The WA classifier module exists but was not integrated into the download/aggregation pipeline.
- This is the largest source by volume (783 MB of text) and dominates the frequency counts (IA contributes counts to 723K of the 798K total word forms)

---

## Source 4: Nayiri Dictionary (nayiri.com)

### What it is
Nayiri.com is an online Armenian dictionary platform hosting several dictionaries including:
- **Hayerēn-Hayerēn** (Armenian-Armenian explanatory dictionary, WA)
- **Hayerēn-Angleren** (Armenian-English dictionary)

The goal was to scrape headwords and definitions to build a validated word list and get English translations.

### How it was scraped
- Uses **Selenium** with headless Chrome (nayiri.com renders content dynamically via JavaScript)
- HTTP-only (HTTPS has SSL issues with the site)
- The scraper iterates through all 38 Armenian lowercase letters (ա through ֆ)
- For each letter, it performs two-letter prefix searches (letter + each second letter = 38×38 = 1,444 queries) to get more complete results than single-letter searches which may be truncated
- On each search results page, it attempts to extract entries using multiple CSS selectors (`.dict-result`, `.search-result`, `.result-entry`, etc.)
- Falls back to parsing bold/strong headwords from page text if no structured selectors match
- English translations are enriched by querying the Armenian-English dictionary for each headword
- Checkpoint file (`dictionary.jsonl`) enables resume

### Results
- **Entries extracted**: 148 (extremely low)
- **With definitions**: 148
- **With English translations**: stored in `dictionary_enriched.json` (0.15 MB)
- Only 147 of the 798K final frequency list entries were confirmed in Nayiri

### Why the yield was so low
The Nayiri scraper produced very poor results for several likely reasons:
1. **Dynamic rendering**: Nayiri heavily relies on JavaScript to render dictionary results. The CSS selectors used (`.dict-result`, `.search-result`, `.result-entry`) likely don't match Nayiri's actual DOM structure
2. **Page layout**: The fallback heuristic (parse bold headwords from body text) may not have matched the page's actual format
3. **Anti-scraping**: The site may employ measures that prevent automated extraction
4. **Single-letter search behavior**: Nayiri may not return paginated word lists for single-letter queries the way the scraper expects

The Nayiri data was used primarily for **validation** (marking words as `in_nayiri: true/false` in the frequency list) rather than frequency counting, but with only 148 entries extracted, this validation is nearly useless.

### Status: ❌ Effectively failed
The scraper runs without crashing, but extracts almost no data. 148 entries from what should be a dictionary of tens of thousands of words is a near-total failure of extraction.

---

## Aggregation Pipeline

### How sources are combined
The `frequency_aggregator.py` module merges all sources:

1. **Source weighting**: Each source has a weight applied to its raw counts:
   - Wikipedia: 1.0× (formal, encyclopedic)
   - Newspapers: 1.5× (closer to daily usage)
   - Internet Archive: 1.2× (historical/literary)

2. **Formula**: `total_count = (wiki × 1.0) + (news × 1.5) + (ia × 1.2)`

3. **Nayiri headwords** are used for boolean validation only (`in_nayiri: true/false`), not frequency

4. **Minimum threshold**: Words must appear at least 2 times across all sources (effectively no filter given the volumes involved)

5. **Output**: Each entry in the final list contains:
   - `word`, `rank`, `total_count` (weighted), `wiki_count`, `news_count`, `ia_count`, `in_nayiri`, `sources` (number of sources the word appears in)

### Final output
- **798,403 unique word forms** in `wa_corpus/data/wa_frequency_list.json` (157.64 MB) and `.csv` (35.48 MB)
- **98,673 words** appear in 2+ sources (multi-source confirmation)
- IA dominates: 723K words from IA vs 165K from Wiki vs 23K from newspapers

### Tokenizer
All sources use the same tokenizer:
- NFC Unicode normalization
- Armenian ligature decomposition (5 Armenian ligatures U+FB13–U+FB17)
- Uppercase→lowercase for Armenian characters
- Word extraction via regex matching contiguous Armenian script characters
- Minimum word length filter of 2 characters

---

## WA/EA Classifier (built but not integrated)

A `wa_classifier.py` module was built that scores text across five signal categories:

1. **Classical orthography markers** — WA retained Mashtotsian spellings (e.g., the իdelays digraph, word-final -այ diphthong) that EA reformed
2. **WA-specific grammar** — present-tense prefix կdelays/կ', future marker պdelays, negation particle, WA pronouns (մdelays = "we", edelays = "you-pl")
3. **WA-specific vocabulary** — words like հdelays (there), delays (here), edelays (white), edelays (child)
4. **Known WA authors** — presence of diaspora literary figures (Varoujan, Siamanto, Zabel Yesayan, etc.)
5. **Diaspora publication cities** — Beirut, Istanbul, Aleppo, Paris, Cairo, Venice, etc.
6. **EA/grabar negative markers** — penalize EA features (reformed spellings, EA pronouns, grabar particles)

A score ≥ 5.0 classifies text as WA. This module was **not used** to filter the IA or newspaper downloads — it exists as infrastructure for potential future filtering.

---

## Summary Table

| Source | Method | Status | Volume | WA Purity |
|--------|--------|--------|--------|-----------|
| **hyw Wikipedia** | XML dump download + wikitext cleanup | ✅ Working | 300K word forms, 22.76 MB dump | **High** — hyw edition is WA by definition |
| **Aztag Daily** | Selenium scraping of article pages | ✅ Working | 990 articles, 1.93M chars | **High** — Beirut-based WA newspaper |
| **Horizon Weekly** | Selenium scraping of article pages | ❌ Failed | 0 articles | N/A — no data extracted |
| **Internet Archive** | IA Search API + DjVuTXT download | ✅ Working (with caveats) | 342 items, 2,640 files, 783 MB text | **Mixed** — contains WA, EA, and grabar |
| **Nayiri Dictionary** | Selenium scraping of search results | ❌ Effectively failed | 148 entries | **High** — WA dictionary, but near-zero yield |

### What worked well
- Wikipedia dump processing — clean, reliable, guaranteed WA
- Aztag newspaper scraping — good volume of modern journalistic WA
- IA cataloging and DjVuTXT download — massive volume, reliable API

### What didn't work
- **Horizon Weekly** — CSS selectors didn't match the site's DOM, producing 0 results
- **Nayiri Dictionary** — CSS selectors for dictionary entries didn't match, producing only 148/~50,000+ expected entries
- **IA WA filtering** — the WA classifier was built but never integrated, so IA data includes substantial non-WA content

### Known issues in the final corpus
1. **IA dominance**: The IA's 783 MB of text dwarfs the other sources, so the frequency list is heavily weighted toward historical/scanned book vocabulary (which includes EA and grabar)
2. **Nayiri validation gap**: With only 148 Nayiri headwords, the `in_nayiri` field is nearly meaningless
3. **OCR noise**: IA DjVuTXT quality varies — some entries in the frequency list are likely OCR artifacts rather than real words
4. **No WA/EA filtering on IA**: Words that are exclusively EA or grabar are present in the frequency list
