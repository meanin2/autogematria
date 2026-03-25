"""Tests for corpus ingestion — run after download + ingest."""

import sqlite3
import pytest
from autogematria.config import DB_PATH


@pytest.fixture
def db():
    """Connect to the ingested database (must exist)."""
    if not DB_PATH.exists():
        pytest.skip("Database not yet created — run ag-ingest first")
    conn = sqlite3.connect(str(DB_PATH))
    yield conn
    conn.close()


def test_book_count(db):
    count = db.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    assert count == 39


def test_genesis_1_1_word_count(db):
    """Genesis 1:1 has 7 words."""
    row = db.execute(
        "SELECT COUNT(*) FROM words w "
        "JOIN verses v ON w.verse_id = v.verse_id "
        "JOIN chapters c ON v.chapter_id = c.chapter_id "
        "JOIN books b ON c.book_id = b.book_id "
        "WHERE b.api_name='Genesis' AND c.chapter_num=1 AND v.verse_num=1"
    ).fetchone()
    assert row[0] == 7


def test_genesis_1_1_letter_count(db):
    """Genesis 1:1 has 28 letters (no spaces)."""
    row = db.execute(
        "SELECT COUNT(*) FROM letters l "
        "JOIN verses v ON l.verse_id = v.verse_id "
        "JOIN chapters c ON v.chapter_id = c.chapter_id "
        "JOIN books b ON c.book_id = b.book_id "
        "WHERE b.api_name='Genesis' AND c.chapter_num=1 AND v.verse_num=1"
    ).fetchone()
    assert row[0] == 28


def test_absolute_letter_index_gapless(db):
    """Absolute letter index should be gapless: max = count - 1."""
    max_idx = db.execute("SELECT MAX(absolute_letter_index) FROM letters").fetchone()[0]
    count = db.execute("SELECT COUNT(*) FROM letters").fetchone()[0]
    assert max_idx == count - 1


def test_first_letters_are_bereshit(db):
    """First 6 letters by absolute index should spell בראשית."""
    rows = db.execute(
        "SELECT letter_raw FROM letters ORDER BY absolute_letter_index LIMIT 6"
    ).fetchall()
    first_word = "".join(r[0] for r in rows)
    assert first_word == "בראשית"  # first 6 letters = בראשית


def test_genesis_1_1_text(db):
    """Verify the raw text of Genesis 1:1."""
    row = db.execute(
        "SELECT v.text_raw FROM verses v "
        "JOIN chapters c ON v.chapter_id = c.chapter_id "
        "JOIN books b ON c.book_id = b.book_id "
        "WHERE b.api_name='Genesis' AND c.chapter_num=1 AND v.verse_num=1"
    ).fetchone()
    assert row[0] == "בראשית ברא אלהים את השמים ואת הארץ"
