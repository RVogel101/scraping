"""
Live smoke tests for AnkiConnect integration.

These tests require:
  - Anki desktop running
  - AnkiConnect plugin installed (code: 2055492159)

Skipped automatically when Anki is not reachable.
"""

import unittest

from armenian_anki.anki_connect import AnkiConnect, AnkiConnectError

TEST_DECK = "___TestSmokeDeck___"
TEST_MODEL = "Basic"


def _anki_is_running() -> bool:
    try:
        return AnkiConnect().ping()
    except Exception:
        return False


@unittest.skipUnless(_anki_is_running(), "Anki is not running or AnkiConnect is unreachable")
class TestAnkiLiveSmoke(unittest.TestCase):
    """Round-trip smoke test: create deck, add note, query, clean up."""

    def setUp(self):
        self.client = AnkiConnect()
        self._created_note_ids: list[int] = []

    def tearDown(self):
        # Clean up: delete notes, then deck
        if self._created_note_ids:
            try:
                self.client._request("deleteNotes", notes=self._created_note_ids)
            except AnkiConnectError:
                pass
        try:
            self.client._request("deleteDecks", decks=[TEST_DECK], cardsToo=True)
        except AnkiConnectError:
            pass

    def test_round_trip(self):
        """Create deck → add note → query → verify fields → clean up."""
        # 1. Create deck
        deck_id = self.client.create_deck(TEST_DECK)
        self.assertIsNotNone(deck_id)

        # 2. Add a note using the built-in "Basic" model
        fields = {"Front": "smoke test front", "Back": "smoke test back"}
        note_id = self.client.add_note(
            deck=TEST_DECK,
            model=TEST_MODEL,
            fields=fields,
            tags=["test_smoke"],
        )
        self.assertIsNotNone(note_id)
        assert note_id is not None  # for type narrowing
        self._created_note_ids.append(note_id)

        # 3. Query the note back
        found = self.client.find_notes(f'"deck:{TEST_DECK}"')
        self.assertIn(note_id, found)

        # 4. Verify fields
        info = self.client.notes_info([note_id])
        self.assertEqual(len(info), 1)
        self.assertEqual(info[0]["fields"]["Front"]["value"], "smoke test front")
        self.assertEqual(info[0]["fields"]["Back"]["value"], "smoke test back")

    def test_ping(self):
        """Verify ping returns True."""
        self.assertTrue(self.client.ping())


if __name__ == "__main__":
    unittest.main()
