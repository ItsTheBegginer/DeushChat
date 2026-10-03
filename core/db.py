import sqlite3
import json
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path.home() / ".deutschfreund" / "deutschfreund.db"


def _ensure_dir() -> None:
    """Create the parent directory for the DB file if it doesn't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_or_create_db() -> None:
    """Create the DB file and all tables if they don't already exist."""
    _ensure_dir()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profile (
                id          INTEGER PRIMARY KEY,
                name        TEXT    NOT NULL,
                level       TEXT    NOT NULL,
                city        TEXT,
                goal        TEXT    NOT NULL,
                created_at  TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id              INTEGER PRIMARY KEY,
                session_id      TEXT    NOT NULL,
                scenario_id     TEXT    NOT NULL,
                role            TEXT    NOT NULL,
                content         TEXT    NOT NULL,
                correction_json TEXT,
                timestamp       TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id              INTEGER PRIMARY KEY,
                front           TEXT    NOT NULL,
                back            TEXT    NOT NULL,
                error_type      TEXT    NOT NULL,
                source_scenario TEXT,
                ease            REAL    NOT NULL DEFAULT 2.5,
                interval_days   INTEGER NOT NULL DEFAULT 1,
                next_review     TEXT    NOT NULL,
                created_at      TEXT    NOT NULL
            )
        """)
        conn.commit()


def save_profile(name: str, level: str, city: str, goal: str) -> None:
    """Save or replace the user's profile (only one profile row is used)."""
    _ensure_dir()
    now = date.today().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        # Remove any existing profile so there is always only one row
        conn.execute("DELETE FROM profile")
        conn.execute(
            "INSERT INTO profile (name, level, city, goal, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, level, city, goal, now),
        )
        conn.commit()


def get_profile() -> dict | None:
    """Return the user profile as a dict, or None if none exists."""
    _ensure_dir()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM profile LIMIT 1")
        row = cur.fetchone()
        if row is None:
            return None
        return dict(row)


def save_message(
    session_id: str,
    scenario_id: str,
    role: str,
    content: str,
    correction_json: str | None = None,
) -> None:
    """Persist a single chat message to the messages table."""
    _ensure_dir()
    now = date.today().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO messages (session_id, scenario_id, role, content, correction_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, scenario_id, role, content, correction_json, now),
        )
        conn.commit()


def get_messages_for_session(session_id: str) -> list[dict]:
    """Return all messages for a given session, ordered by insertion time."""
    _ensure_dir()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def save_card(
    front: str,
    back: str,
    error_type: str,
    source_scenario: str | None = None,
) -> None:
    """Save a new flashcard with SM-2 initial values."""
    _ensure_dir()
    today = date.today().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO cards (front, back, error_type, source_scenario, ease, interval_days, next_review, created_at)
            VALUES (?, ?, ?, ?, 2.5, 1, ?, ?)
            """,
            (front, back, error_type, source_scenario, today, today),
        )
        conn.commit()


def get_due_cards() -> list[dict]:
    """Return all cards whose next_review date is today or earlier."""
    _ensure_dir()
    today = date.today().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM cards WHERE next_review <= ? ORDER BY next_review ASC",
            (today,),
        )
        return [dict(row) for row in cur.fetchall()]


def update_card_review(card_id: int, got_it: bool) -> None:
    """Update a card using the SM-2 lite algorithm after a review attempt."""
    _ensure_dir()
    quality = 4 if got_it else 1

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT ease, interval_days FROM cards WHERE id = ?",
            (card_id,),
        )
        row = cur.fetchone()
        if row is None:
            return

        ease: float = row["ease"]
        interval_days: int = row["interval_days"]

        if quality >= 3:
            if interval_days == 1:
                new_interval = 1
            elif interval_days <= 2:
                new_interval = 6
            else:
                new_interval = round(interval_days * ease)
            new_ease = ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
        else:
            new_interval = 1
            new_ease = ease - 0.20

        new_ease = max(1.3, new_ease)
        next_review = (date.today() + timedelta(days=new_interval)).isoformat()

        conn.execute(
            "UPDATE cards SET ease = ?, interval_days = ?, next_review = ? WHERE id = ?",
            (new_ease, new_interval, next_review, card_id),
        )
        conn.commit()


def get_error_stats() -> list[dict]:
    """Return error type counts, sorted by frequency descending."""
    _ensure_dir()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT error_type, COUNT(*) AS count
            FROM cards
            GROUP BY error_type
            ORDER BY count DESC
            """,
        )
        return [dict(row) for row in cur.fetchall()]


def save_word(
    word: str,
    meaning: str,
    gender: str,
    example_de: str,
    example_en: str,
) -> None:
    """Save a word from the Words from Life feature as a vocabulary flashcard."""
    back = f"{meaning}"
    if gender:
        back = f"({gender}) {meaning}"
    if example_de:
        back += f'\n\nExample: "{example_de}"'
    if example_en:
        back += f' → "{example_en}"'
    save_card(front=word, back=back, error_type="vocabulary")


def get_all_words() -> list[dict]:
    """Return all vocabulary cards ordered by creation date descending."""
    _ensure_dir()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM cards WHERE error_type = 'vocabulary' ORDER BY created_at DESC",
        )
        return [dict(row) for row in cur.fetchall()]
