"""SQLite schema definitions and creation."""

import sqlite3
from pathlib import Path

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS books (
    book_id      INTEGER PRIMARY KEY,
    api_name     TEXT NOT NULL UNIQUE,
    hebrew_name  TEXT NOT NULL,
    category     TEXT NOT NULL CHECK(category IN ('Torah','Prophets','Writings')),
    num_chapters INTEGER NOT NULL,
    sort_order   INTEGER NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS chapters (
    chapter_id  INTEGER PRIMARY KEY,
    book_id     INTEGER NOT NULL REFERENCES books(book_id),
    chapter_num INTEGER NOT NULL,
    num_verses  INTEGER NOT NULL,
    UNIQUE(book_id, chapter_num)
);

CREATE TABLE IF NOT EXISTS verses (
    verse_id        INTEGER PRIMARY KEY,
    chapter_id      INTEGER NOT NULL REFERENCES chapters(chapter_id),
    verse_num       INTEGER NOT NULL,
    text_raw        TEXT NOT NULL,
    text_normalized TEXT NOT NULL,
    UNIQUE(chapter_id, verse_num)
);

CREATE TABLE IF NOT EXISTS words (
    word_id             INTEGER PRIMARY KEY,
    verse_id            INTEGER NOT NULL REFERENCES verses(verse_id),
    word_index_in_verse INTEGER NOT NULL,
    absolute_word_index INTEGER NOT NULL UNIQUE,
    word_raw            TEXT NOT NULL,
    word_normalized     TEXT NOT NULL,
    UNIQUE(verse_id, word_index_in_verse)
);

CREATE TABLE IF NOT EXISTS letters (
    letter_id            INTEGER PRIMARY KEY,
    word_id              INTEGER NOT NULL REFERENCES words(word_id),
    letter_index_in_word INTEGER NOT NULL,
    absolute_letter_index INTEGER NOT NULL UNIQUE,
    letter_raw           TEXT NOT NULL,
    letter_normalized    TEXT NOT NULL,
    verse_id             INTEGER NOT NULL REFERENCES verses(verse_id),
    chapter_id           INTEGER NOT NULL REFERENCES chapters(chapter_id),
    book_id              INTEGER NOT NULL REFERENCES books(book_id),
    UNIQUE(word_id, letter_index_in_word)
);

CREATE TABLE IF NOT EXISTS word_forms (
    form_id   INTEGER PRIMARY KEY,
    form_text TEXT NOT NULL UNIQUE,
    form_raw  TEXT NOT NULL,
    frequency INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS gematria_methods (
    method_id   INTEGER PRIMARY KEY,
    method_name TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS word_gematria (
    form_id   INTEGER NOT NULL REFERENCES word_forms(form_id),
    method_id INTEGER NOT NULL REFERENCES gematria_methods(method_id),
    value     INTEGER NOT NULL,
    PRIMARY KEY(form_id, method_id)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_gematria_value ON word_gematria(method_id, value);
CREATE INDEX IF NOT EXISTS idx_letters_absolute ON letters(absolute_letter_index);
CREATE INDEX IF NOT EXISTS idx_letters_normalized ON letters(letter_normalized);
CREATE INDEX IF NOT EXISTS idx_words_normalized ON words(word_normalized);
CREATE INDEX IF NOT EXISTS idx_words_absolute ON words(absolute_word_index);
CREATE INDEX IF NOT EXISTS idx_verses_chapter ON verses(chapter_id, verse_num);
CREATE INDEX IF NOT EXISTS idx_word_forms_text ON word_forms(form_text);
"""


def create_schema(db_path: Path) -> sqlite3.Connection:
    """Create database and all tables. Returns open connection."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_DDL)
    return conn
