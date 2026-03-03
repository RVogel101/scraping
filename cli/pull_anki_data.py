"""Read-only export of all Anki data to a local JSON file.
Does NOT modify anything in Anki — only reads.

Uses exportPackage (single API call per deck) to avoid connection drops,
then parses the .apkg files (zip of SQLite) locally.
Extracts media (audio/images) referenced in fields into anki_media/."""

import base64
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import zipfile
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from lousardzag.anki_connect import AnkiConnect, AnkiConnectError

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
OUT_PATH = DATA_DIR / "anki_export.json"
MEDIA_DIR = DATA_DIR / "anki_media"

# Patterns for media references in Anki field HTML
RE_SOUND = re.compile(r'\[sound:([^\]]+)\]')
RE_IMG = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)


def request_with_retry(ac, action, retries=3, **params):
    for attempt in range(retries):
        try:
            return ac._request(action, **params)
        except Exception as e:
            if attempt == retries - 1:
                raise
            wait = 2 ** (attempt + 1)
            print(f"    Retry {attempt+1} in {wait}s: {e}")
            time.sleep(wait)


def parse_apkg(apkg_path):
    """Extract notes and media from an .apkg file (zip containing SQLite db + media)."""
    notes = []
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(apkg_path, "r") as zf:
            zf.extractall(tmp)

        # Anki 2.1 uses collection.anki21 or collection.anki2
        db_path = None
        for name in ["collection.anki21", "collection.anki2"]:
            candidate = os.path.join(tmp, name)
            if os.path.exists(candidate):
                db_path = candidate
                break
        if not db_path:
            print(f"    WARNING: No SQLite db found in {apkg_path}")
            return notes

        # Extract media files: the 'media' JSON maps numeric names to real filenames
        media_map_path = os.path.join(tmp, "media")
        media_count = 0
        if os.path.exists(media_map_path):
            with open(media_map_path, "r", encoding="utf-8") as mf:
                media_map = json.load(mf)  # {"0": "audio.mp3", "1": "image.jpg", ...}
            MEDIA_DIR.mkdir(exist_ok=True)
            for numeric_name, real_name in media_map.items():
                src = os.path.join(tmp, numeric_name)
                dst = MEDIA_DIR / real_name
                if os.path.exists(src) and not dst.exists():
                    shutil.copy2(src, dst)
                    media_count += 1
        if media_count:
            print(f"    Extracted {media_count} media files")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Get model (note type) info
        col_row = cur.execute("SELECT models FROM col").fetchone()
        models = json.loads(col_row["models"])

        # Get all notes
        for row in cur.execute("SELECT id, mid, flds, tags FROM notes"):
            model_id = str(row["mid"])
            model = models.get(model_id, {})
            model_name = model.get("name", "Unknown")
            field_names = [f["name"] for f in model.get("flds", [])]
            field_values = row["flds"].split("\x1f")
            fields = {}
            for i, name in enumerate(field_names):
                fields[name] = field_values[i] if i < len(field_values) else ""
            tags = row["tags"].strip().split() if row["tags"].strip() else []
            notes.append({
                "noteId": row["id"],
                "modelName": model_name,
                "tags": tags,
                "fields": fields,
            })
        conn.close()
    return notes


def export_via_apkg(ac, deck_name):
    """Export a deck using exportPackage, parse it, delete the temp file."""
    # Write to system temp dir (not OneDrive) to avoid sync interference
    tmp_dir = tempfile.gettempdir()
    apkg_path = os.path.join(tmp_dir, "_anki_temp_export.apkg").replace("\\", "/")
    result = request_with_retry(
        ac, "exportPackage",
        deck=deck_name, path=apkg_path, includeSched=False,
    )
    if not result:
        print(f"    exportPackage returned false for {deck_name}")
        return []
    notes = parse_apkg(apkg_path)
    os.remove(apkg_path)
    return notes


def find_media_refs(fields):
    """Find all media filenames referenced in note fields."""
    refs = set()
    for value in fields.values():
        refs.update(RE_SOUND.findall(value))
        refs.update(RE_IMG.findall(value))
    return refs


def fetch_media_via_api(ac, media_filenames):
    """Download media files from Anki using retrieveMediaFile (for notesInfo fallback)."""
    MEDIA_DIR.mkdir(exist_ok=True)
    fetched = 0
    for fname in media_filenames:
        dst = MEDIA_DIR / fname
        if dst.exists():
            continue
        try:
            data = request_with_retry(ac, "retrieveMediaFile", filename=fname)
            if data:
                dst.write_bytes(base64.b64decode(data))
                fetched += 1
        except Exception:
            pass  # non-critical — note data is still exported
    return fetched


def export_via_notesinfo(ac, deck_name):
    """Fallback: use findNotes + multi(notesInfo) batching."""
    note_ids = request_with_retry(ac, "findNotes", query=f'deck:"{deck_name}"')
    if not note_ids:
        return []

    BATCH = 25
    actions = []
    for i in range(0, len(note_ids), BATCH):
        chunk = note_ids[i:i + BATCH]
        actions.append({"action": "notesInfo", "params": {"notes": chunk}})

    # Use multi to send all batches in ONE http request
    results = request_with_retry(ac, "multi", actions=actions)

    notes = []
    all_media = set()
    for batch_result in results:
        if isinstance(batch_result, dict) and batch_result.get("error"):
            print(f"    Batch error: {batch_result['error']}")
            continue
        batch_notes = batch_result if isinstance(batch_result, list) else batch_result.get("result", [])
        for n in batch_notes:
            fields = {k: v["value"] for k, v in n["fields"].items()}
            all_media.update(find_media_refs(fields))
            notes.append({
                "noteId": n["noteId"],
                "modelName": n["modelName"],
                "tags": n["tags"],
                "fields": fields,
            })

    if all_media:
        fetched = fetch_media_via_api(ac, all_media)
        if fetched:
            print(f"    Fetched {fetched} media files via API")

    return notes


ac = AnkiConnect()
assert ac.ping(), "AnkiConnect not reachable — is Anki running?"

decks = ac.deck_names()
print(f"Found {len(decks)} decks")

# Only export leaf decks (avoid re-fetching parent deck notes)
leaf_decks = []
for d in sorted(decks):
    # A deck is a leaf if no other deck starts with "d::"
    if not any(other.startswith(d + "::") for other in decks):
        leaf_decks.append(d)
    else:
        print(f"  Skipping parent deck: {d}")

# Try exportPackage first (single API call + native Anki export)
export = {}
for deck in leaf_decks:
    try:
        notes = export_via_apkg(ac, deck)
        print(f"  {deck}: {len(notes)} notes (via exportPackage)")
    except Exception as e:
        print(f"  {deck}: exportPackage failed ({e}), trying notesInfo fallback...")
        try:
            notes = export_via_notesinfo(ac, deck)
            print(f"  {deck}: {len(notes)} notes (via multi+notesInfo)")
        except Exception as e2:
            print(f"  {deck}: FAILED — {e2}")
            notes = []
    export[deck] = notes
    time.sleep(0.5)

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(export, f, ensure_ascii=False, indent=2)

total = sum(len(v) for v in export.values())
media_count = len(list(MEDIA_DIR.glob("*"))) if MEDIA_DIR.exists() else 0
print(f"\nExported {total} notes across {len(export)} decks -> {OUT_PATH}")
print(f"Media files: {media_count} in {MEDIA_DIR.name}/")
