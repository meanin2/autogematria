"""Tests for gematria precomputation — run after ag-index."""

import sqlite3
import pytest
from autogematria.config import DB_PATH


@pytest.fixture
def db():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")
    conn = sqlite3.connect(str(DB_PATH))
    # Check if gematria has been computed
    count = conn.execute("SELECT COUNT(*) FROM word_gematria").fetchone()[0]
    if count == 0:
        conn.close()
        pytest.skip("Gematria not yet computed — run ag-index first")
    yield conn
    conn.close()


def _get_gematria(db, word_raw: str, method: str) -> int | None:
    """Look up gematria value for a word form and method."""
    row = db.execute(
        "SELECT wg.value FROM word_gematria wg "
        "JOIN word_forms wf ON wg.form_id = wf.form_id "
        "JOIN gematria_methods gm ON wg.method_id = gm.method_id "
        "WHERE wf.form_raw = ? AND gm.method_name = ?",
        (word_raw, method),
    ).fetchone()
    return row[0] if row else None


def test_bereshit_standard(db):
    val = _get_gematria(db, "בראשית", "MISPAR_HECHRACHI")
    assert val == 913


def test_elohim_standard(db):
    val = _get_gematria(db, "אלהים", "MISPAR_HECHRACHI")
    assert val == 86


def test_moshe_standard(db):
    """משה = 40+300+5 = 345"""
    val = _get_gematria(db, "משה", "MISPAR_HECHRACHI")
    assert val == 345


def test_gematria_method_count(db):
    count = db.execute("SELECT COUNT(*) FROM gematria_methods").fetchone()[0]
    assert count >= 20  # at least 20 methods registered


def test_gematria_equivalences(db):
    """Find words with same gematria as אלהים (86) in MISPAR_HECHRACHI."""
    rows = db.execute(
        "SELECT DISTINCT wf.form_raw FROM word_gematria wg "
        "JOIN word_forms wf ON wg.form_id = wf.form_id "
        "JOIN gematria_methods gm ON wg.method_id = gm.method_id "
        "WHERE gm.method_name = 'MISPAR_HECHRACHI' AND wg.value = 86"
    ).fetchall()
    words = [r[0] for r in rows]
    assert "אלהים" in words
    assert len(words) >= 1  # at least אלהים itself
