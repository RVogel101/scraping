#!/usr/bin/env python3
"""
Extract clean Armenian words from Anki export, removing HTML/markup.
"""

import json
import re
from pathlib import Path
from html.parser import HTMLParser

class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = []
        self.skip_content = False

    def handle_starttag(self, tag, attrs):
        # Skip content inside style tags
        if tag in ['style', 'script']:
            self.skip_content = True

    def handle_endtag(self, tag):
        if tag in ['style', 'script']:
            self.skip_content = False

    def handle_data(self, d):
        if not self.skip_content:
            self.text.append(d)

    def get_data(self):
        return ''.join(self.text)


def strip_html(text):
    """Remove HTML tags and entities from text."""
    if not text:
        return ""
    
    # Decode HTML entities
    text = text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&amp;', '&')
    
    # Remove <img> tags
    text = re.sub(r'<img[^>]*?>', '', text)
    
    # Remove <span> tags
    text = re.sub(r'<span[^>]*?>(.*?)</span>', r'\1', text)
    
    # Remove <a> tags but keep content
    text = re.sub(r'<a[^>]*?>(.*?)</a>', r'\1', text)
    
    # Remove [sound:...] audio tags
    text = re.sub(r'\[sound:[^\]]*?\]', '', text)
    
    # Remove any remaining HTML tags
    text = re.sub(r'<[^>]*?>', '', text)
    
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def extract_armenian_words_clean():
    """Extract clean Armenian words from Anki export."""
    
    ANKI_EXPORT = Path(__file__).parent.parent / "08-data" / "anki_export.json"
    
    print("Extracting Armenian words from Anki export...")
    print(f"Source: {ANKI_EXPORT}")
    
    with open(ANKI_EXPORT, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    words_by_group = {}
    all_words = set()
    
    for group_name, notes in data.items():
        group_words = set()
        
        for note in notes:
            armenian_field_raw = note['fields'].get('Armenian', '').strip()
            
            if armenian_field_raw:
                # Strip HTML
                armenian_field_clean = strip_html(armenian_field_raw)
                
                # Split by commas or slashes
                for variant in re.split(r'[,/]', armenian_field_clean):
                    word = variant.strip()
                    
                    # Only keep pure Armenian (no latin mixed)
                    if word and not re.search(r'^[a-z]|[a-z]$', word, re.IGNORECASE):
                        # Additional check: must have at least one Armenian letter
                        if re.search(r'[\u0530-\u0589]', word):
                            group_words.add(word)
                            all_words.add(word)
        
        if group_words:
            words_by_group[group_name] = sorted(group_words)
    
    print(f"\nResults:")
    print(f"  Total groups: {len(words_by_group)}")
    print(f"  Total unique words: {len(all_words)}")
    
    # Show breakdown by group
    print(f"\nWords by group:")
    for group, words in sorted(words_by_group.items(), key=lambda x: -len(x[1]))[:10]:
        print(f"  {group}: {len(words)} words")
    
    # Sample cleaned words
    print(f"\nSample cleaned words:")
    for word in sorted(all_words)[:20]:
        print(f"  {word}")
    
    # Check for remaining HTML/mixed content
    suspicious = [w for w in all_words if '<' in w or '&' in w or w[0].isascii() or w[-1].isascii()]
    if suspicious:
        print(f"\nâš ï¸  Words with remaining HTML/ASCII ({len(suspicious)}):")
        for word in suspicious[:20]:
            print(f"  {word}")
    
    # Save cleaned words
    output_file = Path(__file__).parent.parent / "08-data" / "anki_words_cleaned.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total_words': len(all_words),
            'words_by_group': words_by_group,
            'all_words': sorted(all_words)
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\nâœ“ Saved cleaned words to: {output_file}")
    
    return all_words, words_by_group


if __name__ == "__main__":
    extract_armenian_words_clean()

