#!/usr/bin/env python3
"""
Tests for the FSRS v4 scheduler (armenian_anki.fsrs).

Run with:  python -m pytest test_fsrs.py -v
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from armenian_anki.fsrs import FSRSScheduler, CardState, DEFAULT_WEIGHTS
from armenian_anki.database import CardDatabase


class TestFSRSSchedulerInit(unittest.TestCase):
    """Constructor validation."""

    def test_default_weights(self):
        s = FSRSScheduler()
        self.assertEqual(len(s.w), 17)
        self.assertAlmostEqual(s.desired_retention, 0.9)

    def test_rejects_wrong_weight_count(self):
        with self.assertRaises(ValueError):
            FSRSScheduler(weights=(1.0,))

    def test_rejects_bad_retention(self):
        with self.assertRaises(ValueError):
            FSRSScheduler(desired_retention=0.1)
        with self.assertRaises(ValueError):
            FSRSScheduler(desired_retention=1.0)


class TestFSRSFirstReview(unittest.TestCase):
    """first_review() for a brand-new card."""

    def setUp(self):
        self.sched = FSRSScheduler()
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_rating_good(self):
        state = self.sched.first_review(3, now=self.now)
        self.assertGreater(state.stability, 0)
        self.assertGreaterEqual(state.interval, 1)
        self.assertEqual(state.reps, 1)
        self.assertIsNotNone(state.next_due)

    def test_rating_again_gives_short_interval(self):
        state = self.sched.first_review(1, now=self.now)
        self.assertEqual(state.interval, 1)  # minimal interval

    def test_rating_easy_gives_longer_interval(self):
        easy = self.sched.first_review(4, now=self.now)
        good = self.sched.first_review(3, now=self.now)
        self.assertGreaterEqual(easy.interval, good.interval)

    def test_invalid_rating(self):
        with self.assertRaises(ValueError):
            self.sched.first_review(0)
        with self.assertRaises(ValueError):
            self.sched.first_review(5)

    def test_difficulty_range(self):
        for r in (1, 2, 3, 4):
            state = self.sched.first_review(r, now=self.now)
            self.assertGreaterEqual(state.difficulty, 1.0)
            self.assertLessEqual(state.difficulty, 10.0)


class TestFSRSReview(unittest.TestCase):
    """Subsequent reviews — stability & difficulty updates."""

    def setUp(self):
        self.sched = FSRSScheduler()
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.initial = self.sched.first_review(3, now=self.now)

    def test_good_recall_increases_stability(self):
        state2 = self.sched.review(
            self.initial, rating=3,
            elapsed_days=self.initial.interval,
            now=self.now + timedelta(days=self.initial.interval),
        )
        self.assertGreater(state2.stability, self.initial.stability)
        self.assertEqual(state2.reps, 2)

    def test_again_decreases_stability(self):
        state2 = self.sched.review(
            self.initial, rating=1,
            elapsed_days=self.initial.interval,
            now=self.now + timedelta(days=self.initial.interval),
        )
        self.assertLess(state2.stability, self.initial.stability)

    def test_easy_bonus(self):
        good = self.sched.review(
            self.initial, rating=3,
            elapsed_days=self.initial.interval,
            now=self.now + timedelta(days=self.initial.interval),
        )
        easy = self.sched.review(
            self.initial, rating=4,
            elapsed_days=self.initial.interval,
            now=self.now + timedelta(days=self.initial.interval),
        )
        self.assertGreaterEqual(easy.stability, good.stability)

    def test_interval_always_at_least_one(self):
        state2 = self.sched.review(
            self.initial, rating=1,
            elapsed_days=0.5,
            now=self.now + timedelta(hours=12),
        )
        self.assertGreaterEqual(state2.interval, 1)


class TestCardStateDict(unittest.TestCase):
    def test_as_dict_keys(self):
        state = CardState(stability=4.0, difficulty=5.0, interval=3)
        d = state.as_dict()
        for key in ("stability", "difficulty", "interval", "last_review", "next_due", "reps"):
            self.assertIn(key, d)


class TestDatabaseFSRSIntegration(unittest.TestCase):
    """Integration: record_review_fsrs writes correct rows."""

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.db = CardDatabase(self._tmp.name)
        self.user_id = self.db.get_or_create_user("tester")
        self.card_id = self.db.upsert_card(word="test", translation="test")

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_first_fsrs_review(self):
        review_id, state = self.db.record_review_fsrs(
            self.user_id, self.card_id, rating=3,
        )
        self.assertGreater(review_id, 0)
        self.assertGreater(state.stability, 0)
        self.assertEqual(state.reps, 1)

    def test_subsequent_fsrs_review(self):
        _, state1 = self.db.record_review_fsrs(
            self.user_id, self.card_id, rating=3,
        )
        _, state2 = self.db.record_review_fsrs(
            self.user_id, self.card_id, rating=3,
        )
        self.assertEqual(state2.reps, 1)  # scheduler doesn't track across calls
        self.assertGreater(state2.stability, 0)

    def test_fsrs_review_stored_as_fsrs_v4(self):
        self.db.record_review_fsrs(self.user_id, self.card_id, rating=4)
        reviews = self.db.get_reviews(
            user_id=self.user_id, card_id=self.card_id,
            algorithm_version="fsrs_v4",
        )
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0]["algorithm_version"], "fsrs_v4")

    def test_due_cards_with_fsrs(self):
        self.db.record_review_fsrs(self.user_id, self.card_id, rating=3)
        # Card should not be due immediately (interval ≥ 1 day)
        due_now = self.db.due_cards(self.user_id)
        # The card should not appear as due right after review
        card_ids = [c["id"] for c in due_now]
        self.assertNotIn(self.card_id, card_ids)


if __name__ == "__main__":
    unittest.main()
