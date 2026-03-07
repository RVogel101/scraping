"""Tests for preview rendering payload and minimal API surface."""

from __future__ import annotations

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from lousardzag.api import PreviewRequest, app, cards_preview
from lousardzag.database import CardDatabase
from lousardzag.preview import build_preview_payload


class TestPreviewPayload(unittest.TestCase):
    """Validate preview payload structure from local DB-backed data."""

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.db = CardDatabase(self._tmp.name)

        # Seed fallback cards so preview can run without Anki cache.
        self.db.upsert_card(
            word="մայր",
            translation="mother",
            pos="noun",
            template_version="v2",
            anki_note_id=50001,
        )
        self.db.upsert_card(
            word="գրdelays",
            translation="to write",
            pos="verb",
            template_version="v2",
            anki_note_id=50002,
        )

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_build_preview_payload_shape(self):
        payload = build_preview_payload(self.db)

        self.assertEqual(payload["template_version"], "v2")
        self.assertIn("cards", payload)
        self.assertIn("noun", payload["cards"])
        self.assertIn("verb", payload["cards"])
        self.assertIn("sentence", payload["cards"])

        for card_key in ("noun", "verb", "sentence"):
            rendered = payload["cards"][card_key]["rendered"]
            self.assertIsInstance(rendered["front"], str)
            self.assertIsInstance(rendered["back"], str)
            self.assertGreater(len(rendered["front"].strip()), 0)
            self.assertGreater(len(rendered["back"].strip()), 0)

    def test_build_preview_payload_includes_loanword_keys(self):
        payload = build_preview_payload(self.db)
        noun_fields = payload["cards"]["noun"]["fields"]

        self.assertIn("LoanwordOrigin", noun_fields)
        self.assertIn("LoanwordOriginLabel", noun_fields)
        self.assertIn("LoanwordBadgeClass", noun_fields)


class TestPreviewApi(unittest.TestCase):
    """Validate minimal POST /cards/preview behavior via handler call."""

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.db = CardDatabase(self._tmp.name)
        self.db.upsert_card(
            word="մայր",
            translation="mother",
            pos="noun",
            template_version="v2",
            anki_note_id=51001,
        )
        self.db.upsert_card(
            word="գրել",
            translation="to write",
            pos="verb",
            template_version="v2",
            anki_note_id=51002,
        )

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_cards_preview_handler(self):
        req = PreviewRequest(db_path=self._tmp.name)
        payload = cards_preview(req)

        self.assertIn("cards", payload)

    def test_cards_preview_endpoint(self):
        client = TestClient(app)
        response = client.post("/cards/preview", json={"db_path": self._tmp.name})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("cards", payload)
        self.assertEqual(payload["cards"]["sentence"]["card_type"], "vocab_sentences")


if __name__ == "__main__":
    unittest.main()
