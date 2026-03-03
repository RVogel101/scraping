#!/usr/bin/env python3
"""
Clean HTML markup from Anki export Armenian field.

Removes:
- HTML tags (<img>, <span>, <a>, etc.)
- HTML entities (&nbsp;, &amp;, etc.)
- Audio/sound tags ([sound:...])
- Diacritical marks (stress accent, etc.)
- Whitespace normalization

Preserves:
- Multiple word variants (separated by commas)
- Armenian script
- Punctuation at edges only
"""

import json
import re
from pathlib import Path
from typing import Dict, List
from datetime import datetime

def clean_html(text: str) -> str:
    """Remove HTML tags and entities from text."""
    if not text:
        return ""
    
    # Remove <img> tags
    text = re.sub(r'<img[^>]*?>', '', text)
    
    # Remove <span> and </span> tags with content preservation
    text = re.sub(r'<span[^>]*?>(.*?)</span>', r'\1', text, flags=re.DOTALL)
    
    # Remove <a> and </a> tags with content preservation
    text = re.sub(r'<a[^>]*?>(.*?)</a>', r'\1', text, flags=re.DOTALL)
    
    # Remove [sound:...] audio tags
    text = re.sub(r'\[sound:[^\]]*?\]', '', text)
    
    # Remove any remaining HTML tags
    text = re.sub(r'<[^>]*?>', '', text)
    
    # Decode HTML entities
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&amp;', '&')
    text = text.replace('&quot;', '"')
    text = text.replace('&apos;', "'")
    
    # Remove Armenian diacritical marks (stress accent)
    text = re.sub(r'[Õ€Ô±Õ›Õœ]', '', text)  # Remove emphasis marks
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def clean_anki_export():
    """Clean the Anki export JSON."""
    
    ANKI_EXPORT = Path(__file__).parent.parent / "08-data" / "anki_export.json"
    BACKUP = ANKI_EXPORT.with_suffix('.json.bak')
    OUTPUT = ANKI_EXPORT.with_stem('anki_export_cleaned')
    
    print("="*70)
    print("ANKI EXPORT HTML CLEANUP")
    print("="*70)
    
    # Load original
    print(f"\nLoading: {ANKI_EXPORT}")
    with open(ANKI_EXPORT, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Create backup
    print(f"Creating backup: {BACKUP}")
    with open(BACKUP, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # Clean data
    print("\nCleaning Armenian fields...")
    
    stats = {
        'total_notes': 0,
        'cleaned': 0,
        'no_change': 0,
        'samples_before': [],
        'samples_after': []
    }
    
    for group_name, notes in data.items():
        for note in notes:
            stats['total_notes'] += 1
            
            armenian_raw = note['fields'].get('Armenian', '')
            
            if armenian_raw:
                armenian_clean = clean_html(armenian_raw)
                
                if armenian_clean != armenian_raw:
                    stats['cleaned'] += 1
                    
                    # Store samples
                    if len(stats['samples_before']) < 5:
                        stats['samples_before'].append({
                            'before': armenian_raw[:100],
                            'after': armenian_clean[:100],
                            'group': group_name
                        })
                    
                    note['fields']['Armenian'] = armenian_clean
                else:
                    stats['no_change'] += 1
    
    # Save cleaned version
    print(f"Saving cleaned version: {OUTPUT}")
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # Report
    print("\n" + "="*70)
    print("CLEANUP RESULTS")
    print("="*70)
    
    print(f"\nTotal notes processed: {stats['total_notes']}")
    print(f"Notes cleaned: {stats['cleaned']}")
    print(f"Notes with no changes: {stats['no_change']}")
    pct_cleaned = stats['cleaned'] / stats['total_notes'] * 100 if stats['total_notes'] else 0
    print(f"Percentage cleaned: {pct_cleaned:.1f}%")
    
    print(f"\nSample transformations (first 5):")
    for i, sample in enumerate(stats['samples_before'], 1):
        print(f"\n  Sample {i} ({sample['group']}):")
        print(f"    Before: {sample['before']!r}...")
        print(f"    After:  {sample['after']!r}...")
    
    # Show instructions for adoption
    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    print(f"""
1. REVIEW cleaned version:
   {OUTPUT}

2. VERIFY the cleaning looks good (check sample transformations above)

3. ADOPT cleaned version:
   - Backup original: {BACKUP} âœ“ (already created)
   - Replace original with cleaned:
     cp {OUTPUT} {ANKI_EXPORT}

4. COMMIT to git:
   git add {ANKI_EXPORT}
   git commit -m "Clean HTML markup from Anki export Armenian field"

5. FUTURE EXPORTS:
   When exporting from Anki, ensure "Armenian" field contains ONLY:
   - Pure Armenian words (no HTML, no examples)
   - Multiple variants separated by commas
   - No context labels, no example sentences
   
   Example good format:
     "Armenian": "Õ¢Õ¡Õ¶, Õ¢Õ¡Õ¼, Õ°Õ¡ÕµÕ¿Õ¡Ö€Õ¡Ö€"
   
   Example BAD format (with HTML):
     "Armenian": "<span style=\"color:red;\">Õ¢Õ¡Õ¶</span> (noun)"
    """)
    
    return data, stats, OUTPUT


if __name__ == "__main__":
    data, stats, output_file = clean_anki_export()
    
    print(f"\nâœ“ Cleaned export ready at: {output_file}")
    print(f"  Original backup: 08-data/anki_export.json.bak")

