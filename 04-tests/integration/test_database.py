#!/usr/bin/env python3
"""
Tests for lousardzag.database — local SQLite card storage.

Run with:  python test_database.py
"""

import json
import os
import sys
import tempfile
import unittest

# Make sure the package is importable when running from the repo root.
sys.path.insert(0, os.path.dirname(__file__))

from lousardzag.database import CardDatabase


class TestCardDatabase(unittest.TestCase):
    """Unit tests for CardDatabase."""

    def setUp(self):
        # Use an in-memory-style temp file so each test starts fresh.
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.db = CardDatabase(self._tmp.name)

    def tearDown(self):
        os.unlink(self._tmp.name)

    # ── Schema / init ──────────────────────────────────────────────────

    def test_tables_created(self):
        """All expected tables must exist after init."""
        import sqlite3
        conn = sqlite3.connect(self._tmp.name)
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        for expected in ("anki_cards", "card_enrichment", "sentences", "users", "card_reviews"):
            self.assertIn(expected, tables)

    # ── Cards ──────────────────────────────────────────────────────────

    def test_upsert_card_insert(self):
        card_id = self.db.upsert_card(
            word="test_noun",
            translation="book",
            pos="noun",
            syllable_count=1,
            anki_note_id=1001,
        )
        self.assertIsInstance(card_id, int)
        self.assertGreater(card_id, 0)

    def test_upsert_card_update(self):
        """Second upsert with same anki_note_id updates without changing id."""
        id1 = self.db.upsert_card(word="test", translation="a", anki_note_id=2001)
        id2 = self.db.upsert_card(word="test", translation="b", anki_note_id=2001)
        self.assertEqual(id1, id2)
        card = self.db.get_card(id1)
        self.assertEqual(card["translation"], "b")

    def test_get_card_roundtrip(self):
        morphology = {"nom_sg": "test_nom", "acc_sg": "test_acc"}
        card_id = self.db.upsert_card(
            word="test_noun",
            translation="book",
            pos="noun",
            morphology=morphology,
            anki_note_id=3001,
        )
        card = self.db.get_card(card_id)
        self.assertIsNotNone(card)
        self.assertEqual(card["word"], "test_noun")
        self.assertEqual(card["morphology"], morphology)

    def test_template_version_and_metadata_roundtrip(self):
        metadata = {
            "loanword_origin": "french",
            "loanword_badge_class": "origin-french",
        }
        card_id = self.db.upsert_card(
            word="test_meta",
            translation="menu",
            template_version="v2",
            metadata=metadata,
            anki_note_id=4001,
        )
        card = self.db.get_card(card_id)
        self.assertEqual(card["template_version"], "v2")
        self.assertEqual(card["metadata"], metadata)

    def test_get_card_not_found(self):
        self.assertIsNone(self.db.get_card(99999))

    def test_get_card_by_word(self):
        self.db.upsert_card(word="test_noun", anki_note_id=5001)
        card = self.db.get_card_by_word("test_noun")
        self.assertIsNotNone(card)
        self.assertEqual(card["word"], "test_noun")

    def test_list_cards_filter_pos(self):
        self.db.upsert_card(word="w1", pos="noun", anki_note_id=6001)
        self.db.upsert_card(word="w2", pos="verb", anki_note_id=6002)
        nouns = self.db.list_cards(pos="noun")
        self.assertEqual(len(nouns), 1)
        self.assertEqual(nouns[0]["word"], "w1")

    def test_list_cards_filter_level(self):
        self.db.upsert_card(word="w1", pos="noun", level=1, anki_note_id=7001)
        self.db.upsert_card(word="w2", pos="noun", level=2, anki_note_id=7002)
        lvl1 = self.db.list_cards(level=1)
        self.assertEqual(len(lvl1), 1)

    # ── Sentences ──────────────────────────────────────────────────────

    def test_add_and_get_sentences(self):
        card_id = self.db.upsert_card(word="test_noun", anki_note_id=8001)
        sent_id = self.db.add_sentence(
            card_id=card_id,
            form_label="Nominative Sg",
            armenian_text="Ես test_noun oonem",
            english_text="I have a book",
            grammar_type="nominative_subject",
        )
        self.assertIsInstance(sent_id, int)
        sents = self.db.get_sentences(card_id)
        self.assertEqual(len(sents), 1)
        self.assertEqual(sents[0]["english_text"], "I have a book")
        self.assertEqual(sents[0]["grammar_type"], "nominative_subject")

    def test_get_sentences_empty(self):
        card_id = self.db.upsert_card(word="w1", anki_note_id=8002)
        self.assertEqual(self.db.get_sentences(card_id), [])

    # ── Users ──────────────────────────────────────────────────────────

    def test_get_or_create_user_creates(self):
        uid = self.db.get_or_create_user("Alice")
        self.assertIsInstance(uid, int)
        self.assertGreater(uid, 0)

    def test_get_or_create_user_idempotent(self):
        uid1 = self.db.get_or_create_user("Alice")
        uid2 = self.db.get_or_create_user("Alice")
        self.assertEqual(uid1, uid2)

    def test_get_or_create_user_ab_group(self):
        uid = self.db.get_or_create_user("Bob", ab_group="treatment_v1")
        users = self.db.list_users()
        user = next(u for u in users if u["id"] == uid)
        self.assertEqual(user["ab_group"], "treatment_v1")

    def test_list_users(self):
        self.db.get_or_create_user("Alice")
        self.db.get_or_create_user("Bob")
        users = self.db.list_users()
        self.assertEqual(len(users), 2)

    # ── Card Reviews ───────────────────────────────────────────────────

    def test_record_review_returns_id(self):
        uid = self.db.get_or_create_user("Alice")
        cid = self.db.upsert_card(word="test_noun", anki_note_id=9001)
        rid = self.db.record_review(uid, cid, rating=3, response_time_ms=800)
        self.assertIsInstance(rid, int)
        self.assertGreater(rid, 0)

    def test_get_reviews_by_user(self):
        uid = self.db.get_or_create_user("Alice")
        cid = self.db.upsert_card(word="test_noun", anki_note_id=9002)
        self.db.record_review(uid, cid, rating=2)
        self.db.record_review(uid, cid, rating=4)
        reviews = self.db.get_reviews(user_id=uid)
        self.assertEqual(len(reviews), 2)

    def test_get_reviews_by_algorithm_version(self):
        uid = self.db.get_or_create_user("Alice")
        cid = self.db.upsert_card(word="test_noun", anki_note_id=9003)
        self.db.record_review(uid, cid, rating=3, algorithm_version="v1")
        self.db.record_review(uid, cid, rating=4, algorithm_version="fsrs_v4")
        v1_reviews = self.db.get_reviews(algorithm_version="v1")
        self.assertEqual(len(v1_reviews), 1)
        self.assertEqual(v1_reviews[0]["algorithm_version"], "v1")

    # ── Due cards ──────────────────────────────────────────────────────

    def test_due_cards_returns_overdue(self):
        uid = self.db.get_or_create_user("Alice")
        cid = self.db.upsert_card(word="test_noun", anki_note_id=10001)
        # next_due in the past
        self.db.record_review(uid, cid, rating=1, next_due_at="2000-01-01T00:00:00+00:00")
        due = self.db.due_cards(uid)
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]["word"], "test_noun")

    def test_due_cards_excludes_future(self):
        uid = self.db.get_or_create_user("Alice")
        cid = self.db.upsert_card(word="test_noun", anki_note_id=10002)
        # next_due far in the future
        self.db.record_review(uid, cid, rating=4, next_due_at="2099-01-01T00:00:00+00:00")
        due = self.db.due_cards(uid)
        self.assertEqual(due, [])

    # ── Review stats ───────────────────────────────────────────────────

    def test_review_stats_aggregation(self):
        uid = self.db.get_or_create_user("Alice")
        cid = self.db.upsert_card(word="test_noun", anki_note_id=11001)
        self.db.record_review(uid, cid, rating=4, algorithm_version="v1")
        self.db.record_review(uid, cid, rating=2, algorithm_version="v1")
        stats = self.db.review_stats()
        self.assertIn("by_algorithm", stats)
        row = stats["by_algorithm"][0]
        self.assertEqual(row["algorithm_version"], "v1")
        self.assertEqual(row["total_reviews"], 2)
        self.assertAlmostEqual(row["avg_rating"], 3.0)
        self.assertEqual(row["accuracy_pct"], 50.0)  # only rating>=3 counts

    def test_review_stats_ab_comparison(self):
        """Stats must group independently by algorithm_version for A/B analysis."""
        uid = self.db.get_or_create_user("Alice")
        cid = self.db.upsert_card(word="test_noun", anki_note_id=11002)
        self.db.record_review(uid, cid, rating=4, algorithm_version="v1")
        self.db.record_review(uid, cid, rating=1, algorithm_version="fsrs_v4")
        stats = self.db.review_stats()
        versions = {r["algorithm_version"] for r in stats["by_algorithm"]}
        self.assertIn("v1", versions)
        self.assertIn("fsrs_v4", versions)


if __name__ == "__main__":
    unittest.main(verbosity=2)
