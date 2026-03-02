"""
Local SQLite database for Armenian Anki card data storage.

Schema overview:
  cards        — generated card data (word, morphology, progression metadata)
  sentences    — example sentences linked to cards
  users        — user records, including A/B test group assignment
  card_reviews — per-user review events for spaced repetition and A/B analytics

This module is designed to be the local persistence layer that eventually
backs a stand-alone hosted app.  The ``card_reviews`` table captures every
review event with timing and algorithm-version tags so that different
ordering / scheduling strategies can be compared (A/B testing).
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .fsrs import FSRSScheduler, CardState

logger = logging.getLogger(__name__)

# Default path — lives alongside the package so it is easy to find but can
# be overridden by callers who want a custom location.
DEFAULT_DB_PATH = Path(__file__).parent.parent / "armenian_cards.db"


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ─── DDL ──────────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Core card record (one row per generated word / note)
CREATE TABLE IF NOT EXISTS cards (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    word             TEXT    NOT NULL,
    translation      TEXT    NOT NULL DEFAULT '',
    pos              TEXT    NOT NULL DEFAULT '',   -- noun | verb | adjective …
    declension_class TEXT    NOT NULL DEFAULT '',
    verb_class       TEXT    NOT NULL DEFAULT '',
    frequency_rank   INTEGER NOT NULL DEFAULT 9999,
    syllable_count   INTEGER NOT NULL DEFAULT 0,
    level            INTEGER NOT NULL DEFAULT 1,    -- progression level
    batch_index      INTEGER NOT NULL DEFAULT 0,    -- 0-based batch number
    card_type        TEXT    NOT NULL DEFAULT '',   -- noun_declension | verb_conjugation | sentence
    morphology_json  TEXT    NOT NULL DEFAULT '{}', -- full declension / conjugation blob
    anki_note_id     INTEGER,                       -- Anki note ID if pushed via AnkiConnect
    created_at       TEXT    NOT NULL,
    UNIQUE (word, card_type)
);

-- Example sentences attached to a card
CREATE TABLE IF NOT EXISTS sentences (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id          INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    form_label       TEXT    NOT NULL DEFAULT '',
    armenian_text    TEXT    NOT NULL DEFAULT '',
    english_text     TEXT    NOT NULL DEFAULT '',
    grammar_type     TEXT    NOT NULL DEFAULT '',
    created_at       TEXT    NOT NULL
);

-- Users (minimal; extended attributes can live in user_meta)
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL DEFAULT 'default',
    ab_group   TEXT    NOT NULL DEFAULT 'control', -- 'control' | 'treatment_v1' | …
    created_at TEXT    NOT NULL
);

-- Per-user review events — the main source of signal for A/B testing and
-- for training / evaluating the spaced-repetition scheduling algorithm.
CREATE TABLE IF NOT EXISTS card_reviews (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    card_id           INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    reviewed_at       TEXT    NOT NULL,
    rating            INTEGER NOT NULL DEFAULT 0, -- 1 (again) … 4 (easy)
    response_time_ms  INTEGER NOT NULL DEFAULT 0,
    algorithm_version TEXT    NOT NULL DEFAULT 'v1', -- tag for A/B variant
    ease_factor       REAL    NOT NULL DEFAULT 2.5,
    interval_days     REAL    NOT NULL DEFAULT 1.0,
    next_due_at       TEXT    NOT NULL DEFAULT ''
);

-- Vocabulary cache synced from Anki — enables offline vocabulary access
-- and eliminates dependency on AnkiConnect for reading sourced words.
CREATE TABLE IF NOT EXISTS vocabulary (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    lemma            TEXT    NOT NULL UNIQUE,  -- Armenian word/infinitive form
    translation      TEXT    NOT NULL DEFAULT '',
    pos              TEXT    NOT NULL DEFAULT '',  -- noun | verb | adjective …
    pronunciation    TEXT    NOT NULL DEFAULT '',  -- transliteration/romanization
    declension_class TEXT    NOT NULL DEFAULT '',  -- i_class, u_class, etc.
    verb_class       TEXT    NOT NULL DEFAULT '',  -- e_class, i_class, etc.
    syllable_count   INTEGER NOT NULL DEFAULT 0,
    anki_note_id     INTEGER,                   -- Original Anki note ID
    source_deck      TEXT    NOT NULL DEFAULT '',  -- Which deck it came from
    synced_at        TEXT    NOT NULL,          -- Last sync timestamp
    UNIQUE (lemma, source_deck)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_cards_word        ON cards(word);
CREATE INDEX IF NOT EXISTS idx_sentences_card    ON sentences(card_id);
CREATE INDEX IF NOT EXISTS idx_reviews_user_card ON card_reviews(user_id, card_id);
CREATE INDEX IF NOT EXISTS idx_reviews_due       ON card_reviews(user_id, next_due_at);
CREATE INDEX IF NOT EXISTS idx_vocabulary_lemma  ON vocabulary(lemma);
CREATE INDEX IF NOT EXISTS idx_vocabulary_pos    ON vocabulary(pos);
CREATE INDEX IF NOT EXISTS idx_vocabulary_deck   ON vocabulary(source_deck);
"""


# ─── Database class ───────────────────────────────────────────────────────────

class CardDatabase:
    """
    Manages the local SQLite database for Armenian card data.

    Basic usage::

        db = CardDatabase()                   # uses DEFAULT_DB_PATH
        db = CardDatabase("/path/to/my.db")   # custom path

        card_id = db.upsert_card(
            word="գdelayed",
            translation="book",
            pos="noun",
            card_type="noun_declension",
            morphology={"nom_sg": "...", ...},
        )
        db.add_sentence(card_id, "Nominative Sg", "Ես ...", "I ...")

        user_id = db.get_or_create_user("Alice")
        db.record_review(user_id, card_id, rating=3, response_time_ms=1200)
    """

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        """Create tables and indexes if they do not exist."""
        with self._connect() as conn:
            conn.executescript(_SCHEMA_SQL)
        logger.debug("Database initialised at %s", self.db_path)

    @contextmanager
    def _connect(self):
        """Yield a sqlite3 connection with row_factory set."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Cards ─────────────────────────────────────────────────────────────────

    def upsert_card(
        self,
        word: str,
        translation: str = "",
        pos: str = "",
        card_type: str = "",
        declension_class: str = "",
        verb_class: str = "",
        frequency_rank: int = 9999,
        syllable_count: int = 0,
        level: int = 1,
        batch_index: int = 0,
        morphology: dict | None = None,
        anki_note_id: int | None = None,
    ) -> int:
        """Insert or update a card record; return its ``id``.

        The (word, card_type) pair is the natural key: if a row already exists
        it is updated in place so that re-running the pipeline is idempotent.
        """
        morphology_json = json.dumps(morphology or {}, ensure_ascii=False)
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cards
                    (word, translation, pos, declension_class, verb_class,
                     frequency_rank, syllable_count, level, batch_index,
                     card_type, morphology_json, anki_note_id, created_at)
                VALUES
                    (:word, :translation, :pos, :declension_class, :verb_class,
                     :frequency_rank, :syllable_count, :level, :batch_index,
                     :card_type, :morphology_json, :anki_note_id, :created_at)
                ON CONFLICT(word, card_type) DO UPDATE SET
                    translation      = excluded.translation,
                    pos              = excluded.pos,
                    declension_class = excluded.declension_class,
                    verb_class       = excluded.verb_class,
                    frequency_rank   = excluded.frequency_rank,
                    syllable_count   = excluded.syllable_count,
                    level            = excluded.level,
                    batch_index      = excluded.batch_index,
                    morphology_json  = excluded.morphology_json,
                    anki_note_id     = COALESCE(excluded.anki_note_id, cards.anki_note_id)
                """,
                {
                    "word": word,
                    "translation": translation,
                    "pos": pos,
                    "declension_class": declension_class,
                    "verb_class": verb_class,
                    "frequency_rank": frequency_rank,
                    "syllable_count": syllable_count,
                    "level": level,
                    "batch_index": batch_index,
                    "card_type": card_type,
                    "morphology_json": morphology_json,
                    "anki_note_id": anki_note_id,
                    "created_at": now,
                },
            )
            row = conn.execute(
                "SELECT id FROM cards WHERE word = ? AND card_type = ?",
                (word, card_type),
            ).fetchone()
        card_id: int = row["id"]
        logger.debug("Upserted card id=%d word=%r type=%r", card_id, word, card_type)
        return card_id

    def get_card(self, card_id: int) -> Optional[dict]:
        """Return a card row as a dict, or None if not found."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM cards WHERE id = ?", (card_id,)
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["morphology"] = json.loads(result.pop("morphology_json", "{}"))
        return result

    def get_card_by_word(self, word: str, card_type: str = "") -> Optional[dict]:
        """Return a card row by word (and optionally card_type)."""
        with self._connect() as conn:
            if card_type:
                row = conn.execute(
                    "SELECT * FROM cards WHERE word = ? AND card_type = ?",
                    (word, card_type),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM cards WHERE word = ? LIMIT 1", (word,)
                ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["morphology"] = json.loads(result.pop("morphology_json", "{}"))
        return result

    def list_cards(
        self,
        pos: str = "",
        card_type: str = "",
        level: int | None = None,
    ) -> list[dict]:
        """Return cards, optionally filtered by pos, card_type, or level."""
        clauses: list[str] = []
        params: list = []
        if pos:
            clauses.append("pos = ?")
            params.append(pos)
        if card_type:
            clauses.append("card_type = ?")
            params.append(card_type)
        if level is not None:
            clauses.append("level = ?")
            params.append(level)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM cards {where} ORDER BY level, batch_index, frequency_rank",
                params,
            ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d["morphology"] = json.loads(d.pop("morphology_json", "{}"))
            results.append(d)
        return results

    # ── Sentences ─────────────────────────────────────────────────────────────

    def add_sentence(
        self,
        card_id: int,
        form_label: str,
        armenian_text: str,
        english_text: str,
        grammar_type: str = "",
    ) -> int:
        """Insert a sentence row and return its ``id``."""
        now = _now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO sentences
                    (card_id, form_label, armenian_text, english_text, grammar_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (card_id, form_label, armenian_text, english_text, grammar_type, now),
            )
        return cur.lastrowid

    def get_sentences(self, card_id: int) -> list[dict]:
        """Return all sentences for a card."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sentences WHERE card_id = ? ORDER BY id",
                (card_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    # ── Users ─────────────────────────────────────────────────────────────────

    def get_or_create_user(self, name: str = "default", ab_group: str = "control") -> int:
        """Return the id of the named user, creating them if necessary."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE name = ?", (name,)
            ).fetchone()
            if row:
                return row["id"]
            cur = conn.execute(
                "INSERT INTO users (name, ab_group, created_at) VALUES (?, ?, ?)",
                (name, ab_group, _now_iso()),
            )
        logger.debug("Created user id=%d name=%r ab_group=%r", cur.lastrowid, name, ab_group)
        return cur.lastrowid

    def list_users(self) -> list[dict]:
        """Return all user rows."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    # ── Card Reviews ──────────────────────────────────────────────────────────

    def record_review(
        self,
        user_id: int,
        card_id: int,
        rating: int,
        response_time_ms: int = 0,
        algorithm_version: str = "v1",
        ease_factor: float = 2.5,
        interval_days: float = 1.0,
        next_due_at: str = "",
    ) -> int:
        """Insert a review event and return its ``id``.

        Args:
            user_id:           ID of the reviewing user.
            card_id:           ID of the card being reviewed.
            rating:            1 (Again) · 2 (Hard) · 3 (Good) · 4 (Easy).
            response_time_ms:  Milliseconds taken to answer.
            algorithm_version: Scheduling algorithm tag (e.g. ``'v1'``, ``'fsrs_v4'``).
                               Use different values to A/B test algorithms.
            ease_factor:       Current ease factor for the card.
            interval_days:     Computed next interval in days.
            next_due_at:       ISO-8601 datetime when the card is next due.
        """
        if not next_due_at:
            next_due_at = _now_iso()
        now = _now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO card_reviews
                    (user_id, card_id, reviewed_at, rating, response_time_ms,
                     algorithm_version, ease_factor, interval_days, next_due_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id, card_id, now, rating, response_time_ms,
                    algorithm_version, ease_factor, interval_days, next_due_at,
                ),
            )
        logger.debug(
            "Recorded review id=%d user=%d card=%d rating=%d",
            cur.lastrowid, user_id, card_id, rating,
        )
        return cur.lastrowid

    def record_review_fsrs(
        self,
        user_id: int,
        card_id: int,
        rating: int,
        response_time_ms: int = 0,
        scheduler: FSRSScheduler | None = None,
    ) -> tuple[int, CardState]:
        """Record a review using the FSRS v4 algorithm to compute scheduling.

        Looks up the card's previous FSRS state from the most recent
        ``fsrs_v4`` review.  If no prior review exists the card is treated
        as new.

        Returns:
            (review_id, new_card_state)
        """
        scheduler = scheduler or FSRSScheduler()
        now = datetime.now(timezone.utc)

        # Fetch the latest fsrs_v4 review for this user+card
        prev = self._latest_review(user_id, card_id, algorithm_version="fsrs_v4")

        if prev is None:
            # First review — brand new card
            state = scheduler.first_review(rating, now=now)
        else:
            # Reconstruct prior state
            prev_reviewed = datetime.fromisoformat(prev["reviewed_at"])
            elapsed_days = max((now - prev_reviewed).total_seconds() / 86400, 0.0)
            prev_state = CardState(
                stability=prev["ease_factor"],  # we store stability in ease_factor column
                difficulty=5.0,                 # difficulty not stored; scheduler recomputes
                reps=0,
            )
            state = scheduler.review(prev_state, rating, elapsed_days, now=now)

        review_id = self.record_review(
            user_id=user_id,
            card_id=card_id,
            rating=rating,
            response_time_ms=response_time_ms,
            algorithm_version="fsrs_v4",
            ease_factor=state.stability,
            interval_days=float(state.interval),
            next_due_at=state.next_due or "",
        )
        return review_id, state

    def _latest_review(
        self,
        user_id: int,
        card_id: int,
        algorithm_version: str = "",
    ) -> Optional[dict]:
        """Return the most recent review for a user+card (optionally by algorithm)."""
        clauses = ["user_id = ?", "card_id = ?"]
        params: list = [user_id, card_id]
        if algorithm_version:
            clauses.append("algorithm_version = ?")
            params.append(algorithm_version)
        where = " AND ".join(clauses)
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT * FROM card_reviews WHERE {where} ORDER BY reviewed_at DESC LIMIT 1",
                params,
            ).fetchone()
        return dict(row) if row else None

    def get_reviews(
        self,
        user_id: int | None = None,
        card_id: int | None = None,
        algorithm_version: str = "",
    ) -> list[dict]:
        """Return review rows, optionally filtered."""
        clauses: list[str] = []
        params: list = []
        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)
        if card_id is not None:
            clauses.append("card_id = ?")
            params.append(card_id)
        if algorithm_version:
            clauses.append("algorithm_version = ?")
            params.append(algorithm_version)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM card_reviews {where} ORDER BY reviewed_at",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def due_cards(self, user_id: int, as_of: str = "") -> list[dict]:
        """Return card rows that are due for review by ``user_id``.

        ``as_of`` defaults to now (UTC).  Returns each due card at most once
        (the row with the most recent review for that card is used to
        determine due date).
        """
        as_of = as_of or _now_iso()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.*
                FROM cards c
                JOIN (
                    SELECT card_id, MAX(reviewed_at) AS last_reviewed, next_due_at
                    FROM card_reviews
                    WHERE user_id = ?
                    GROUP BY card_id
                ) r ON r.card_id = c.id
                WHERE r.next_due_at <= ?
                ORDER BY r.next_due_at
                """,
                (user_id, as_of),
            ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d["morphology"] = json.loads(d.pop("morphology_json", "{}"))
            results.append(d)
        return results

    # ── Reporting ─────────────────────────────────────────────────────────────

    def review_stats(self, user_id: int | None = None) -> dict:
        """Return aggregate review statistics for A/B reporting.

        If ``user_id`` is None, aggregates across all users.
        Groups metrics by ``algorithm_version`` to support A/B comparison.
        """
        params: list = []
        user_filter = ""
        if user_id is not None:
            user_filter = "WHERE user_id = ?"
            params.append(user_id)

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    algorithm_version,
                    COUNT(*)                           AS total_reviews,
                    ROUND(AVG(rating), 3)              AS avg_rating,
                    ROUND(AVG(response_time_ms), 1)    AS avg_response_ms,
                    SUM(CASE WHEN rating >= 3 THEN 1 ELSE 0 END) AS correct_count,
                    COUNT(DISTINCT user_id)            AS unique_users,
                    COUNT(DISTINCT card_id)            AS unique_cards
                FROM card_reviews
                {user_filter}
                GROUP BY algorithm_version
                ORDER BY algorithm_version
                """,
                params,
            ).fetchall()
        stats: list[dict] = []
        for row in rows:
            d = dict(row)
            total = d["total_reviews"] or 1
            d["accuracy_pct"] = round(100 * d["correct_count"] / total, 1)
            stats.append(d)
        return {"by_algorithm": stats}

    # ── Vocabulary Cache (Synced from Anki) ────────────────────────────────────

    def sync_vocabulary_from_anki(
        self,
        anki_connect_client,
        deck: str,
        field_overrides: dict | None = None,
        default_pos: str = "noun",
    ) -> dict:
        """Sync vocabulary from an Anki deck into the local SQLite cache.

        Extracts all notes from the Anki deck using the same field mapping
        logic as CardGenerator.get_source_words(), then inserts/updates 
        vocabulary cache entries.

        Args:
            anki_connect_client: An AnkiConnect instance
            deck: Name of the source Anki deck
            field_overrides: Optional field name overrides
            default_pos: POS to assume when pos field is missing

        Returns:
            A dict with keys: added, updated, skipped, total_processed
        """
        # Import CardGenerator to reuse its field extraction logic
        from .card_generator import CardGenerator
        
        gen = CardGenerator(anki=anki_connect_client, db=self)
        vocab_entries = gen.get_source_words(deck, field_overrides, default_pos, use_cache=False)
        
        now = _now_iso()
        stats = {"added": 0, "updated": 0, "skipped": 0, "total_processed": len(vocab_entries)}
        
        with self._connect() as conn:
            for entry in vocab_entries:
                lemma = entry.get("word", "")
                if not lemma:
                    stats["skipped"] += 1
                    continue
                
                existing = conn.execute(
                    "SELECT id FROM vocabulary WHERE lemma = ? AND source_deck = ?",
                    (lemma, deck),
                ).fetchone()

                conn.execute(
                    """
                    INSERT INTO vocabulary
                        (lemma, translation, pos, pronunciation, 
                         declension_class, verb_class, syllable_count, 
                         source_deck, synced_at)
                    VALUES
                        (:lemma, :translation, :pos, :pronunciation,
                         :declension_class, :verb_class, :syllable_count,
                         :source_deck, :synced_at)
                    ON CONFLICT(lemma, source_deck) DO UPDATE SET
                        translation      = excluded.translation,
                        pos              = excluded.pos,
                        pronunciation    = excluded.pronunciation,
                        declension_class = excluded.declension_class,
                        verb_class       = excluded.verb_class,
                        syllable_count   = excluded.syllable_count,
                        synced_at        = excluded.synced_at
                    """,
                    {
                        "lemma": lemma,
                        "translation": entry.get("translation", ""),
                        "pos": entry.get("pos", ""),
                        "pronunciation": entry.get("pronunciation", ""),
                        "declension_class": entry.get("declension_class", ""),
                        "verb_class": entry.get("verb_class", ""),
                        "syllable_count": entry.get("syllable_count", 0),
                        "source_deck": deck,
                        "synced_at": now,
                    },
                )
                if existing:
                    stats["updated"] += 1
                else:
                    stats["added"] += 1
        
        logger.info(
            f"Synced vocabulary from '{deck}': "
            f"({stats['added']} new, {stats['updated']} updated, {stats['skipped']} skipped)"
        )
        return stats

    def get_vocabulary_from_cache(self, source_deck: str | None = None) -> list[dict]:
        """Retrieve vocabulary entries from the local cache.

        Args:
            source_deck: If provided, filter to only this deck. If None, return all.

        Returns:
            List of vocabulary dicts with keys: lemma, translation, pos, etc.
        """
        with self._connect() as conn:
            if source_deck:
                rows = conn.execute(
                    """
                    SELECT lemma, translation, pos, pronunciation, 
                           declension_class, verb_class, syllable_count, 
                           source_deck, synced_at
                    FROM vocabulary
                    WHERE source_deck = ?
                    ORDER BY lemma
                    """,
                    (source_deck,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT lemma, translation, pos, pronunciation, 
                           declension_class, verb_class, syllable_count, 
                           source_deck, synced_at
                    FROM vocabulary
                    ORDER BY source_deck, lemma
                    """,
                ).fetchall()
        return [dict(row) for row in rows]

    def has_vocabulary_cache(self, source_deck: str | None = None) -> bool:
        """Check if vocabulary cache is populated.

        Args:
            source_deck: Check for a specific deck. If None, check for any vocabulary.

        Returns:
            True if cache has entries, False otherwise.
        """
        with self._connect() as conn:
            if source_deck:
                count = conn.execute(
                    "SELECT COUNT(*) as cnt FROM vocabulary WHERE source_deck = ?",
                    (source_deck,),
                ).fetchone()
            else:
                count = conn.execute(
                    "SELECT COUNT(*) as cnt FROM vocabulary"
                ).fetchone()
        return count and count["cnt"] > 0
