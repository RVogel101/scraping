"""Test vocabulary tracking in sentence generation."""
import sys
import json
sys.path.insert(0, '02-src')

from lousardzag.database import CardDatabase
from lousardzag.card_generator import CardGenerator

# Create a test card with sentences
db = CardDatabase()
gen = CardGenerator(anki=None, db=db)

# Generate a simple test (local only, no Anki)
print('Generating test card with sentence...')
sent_ids = gen.generate_sentence_cards(
    word='գիրք',
    translation='book',
    pos='noun',
    declension_class='i_class',
    push_to_anki=False
)
print(f'Created {len(sent_ids)} sentence cards')

# Check the stored vocabulary
if sent_ids:
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    conn.row_factory = sqlite3.Row
    result = conn.execute('SELECT * FROM sentences WHERE id = ?', (sent_ids[0],)).fetchone()
    if result:
        vocab_json = result['vocabulary_used']
        vocab = json.loads(vocab_json)
        print(f'\nFirst sentence:')
        print(f'  Armenian: {result["armenian_text"]}')
        print(f'  English: {result["english_text"]}')
        print(f'  Vocabulary used: {vocab}')
        print(f'  Word count: {len(vocab)}')
    conn.close()

