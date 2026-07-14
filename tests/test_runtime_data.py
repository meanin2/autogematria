"""Runtime corpus validation and read-only connection tests."""

from __future__ import annotations

import sqlite3

import pytest

from autogematria.config import SCHEMA_VERSION, TANAKH_BOOKS
from autogematria.gematria_index import ALL_METHODS
from autogematria.runtime_data import (
    DataValidationError,
    connect_corpus,
    readiness_payload,
    validate_corpus_database,
)
from autogematria.schema import SCHEMA_DDL


def _build_minimal_valid_database(path, *, schema_version: int = SCHEMA_VERSION) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_DDL)
    chapter_id = 1
    genesis_chapter_id = None
    for book_id, (api_name, hebrew_name, category, chapter_count) in enumerate(
        TANAKH_BOOKS, start=1
    ):
        conn.execute(
            "INSERT INTO books VALUES (?, ?, ?, ?, ?, ?)",
            (book_id, api_name, hebrew_name, category, chapter_count, book_id - 1),
        )
        for chapter_num in range(1, chapter_count + 1):
            conn.execute(
                "INSERT INTO chapters VALUES (?, ?, ?, ?)",
                (chapter_id, book_id, chapter_num, 1 if chapter_id == 1 else 0),
            )
            if api_name == "Genesis" and chapter_num == 1:
                genesis_chapter_id = chapter_id
            chapter_id += 1
    assert genesis_chapter_id == 1
    conn.execute("INSERT INTO verses VALUES (1, 1, 1, 'אבג', 'אבג')")
    conn.execute("INSERT INTO words VALUES (1, 1, 0, 0, 'אבג', 'אבג')")
    conn.execute("INSERT INTO letters VALUES (1, 1, 0, 0, 'א', 'א', 1, 1, 1)")
    conn.execute("INSERT INTO word_forms VALUES (1, 'אבג', 'אבג', 1)")
    for method_id, method in enumerate(ALL_METHODS, start=1):
        conn.execute(
            "INSERT INTO gematria_methods(method_id, method_name) VALUES (?, ?)",
            (method_id, method.name),
        )
        conn.execute(
            "INSERT INTO word_gematria(form_id, method_id, value) VALUES (1, ?, ?)",
            (method_id, method_id),
        )
    conn.execute(
        "CREATE INDEX idx_gematria_value_method ON word_gematria(value, method_id)"
    )
    conn.execute(f"PRAGMA user_version={schema_version}")
    conn.commit()
    conn.close()


def test_validate_and_open_corpus_read_only(tmp_path):
    db_path = tmp_path / "autogematria.db"
    _build_minimal_valid_database(db_path)

    summary = validate_corpus_database(db_path, strict_version=True)
    assert summary["ready"] is True
    assert summary["schema_version"] == SCHEMA_VERSION
    assert summary["gematria_methods"] == 22

    conn = connect_corpus(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 39
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("CREATE TABLE forbidden(value INTEGER)")
    finally:
        conn.close()
    assert not db_path.with_name("autogematria.db-wal").exists()
    assert not db_path.with_name("autogematria.db-shm").exists()


def test_missing_corpus_has_actionable_error(tmp_path):
    with pytest.raises(DataValidationError, match="ag-prepare-data"):
        connect_corpus(tmp_path / "missing.db")


def test_legacy_database_is_runtime_compatible_but_not_release_ready(tmp_path):
    db_path = tmp_path / "legacy.db"
    _build_minimal_valid_database(db_path, schema_version=0)
    assert validate_corpus_database(db_path)["legacy_schema"] is True
    with pytest.raises(DataValidationError, match="outdated"):
        validate_corpus_database(db_path, strict_version=True)


def test_method_registry_must_contain_the_supported_methods(tmp_path):
    db_path = tmp_path / "wrong-methods.db"
    _build_minimal_valid_database(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE gematria_methods SET method_name = 'MADE_UP' WHERE method_id = 1")
    conn.commit()
    conn.close()

    with pytest.raises(DataValidationError, match="method registry"):
        validate_corpus_database(db_path)


def test_readiness_reports_invalid_data_without_raising(tmp_path, monkeypatch):
    import autogematria.runtime_data as runtime_data

    monkeypatch.setattr(runtime_data, "DB_PATH", tmp_path / "missing.db")
    monkeypatch.setattr(runtime_data, "VAR_DIR", tmp_path / "var")
    payload, ready = readiness_payload()
    assert ready is False
    assert payload["status"] == "not_ready"
    assert "ag-prepare-data" in payload["error"]
