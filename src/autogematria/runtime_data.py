"""Validation and read-only access for the generated corpus database."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from autogematria.config import (
    DB_PATH,
    SCHEMA_VERSION,
    TANAKH_BOOKS,
    TOTAL_BOOKS,
    TOTAL_CHAPTERS,
    VAR_DIR,
)
from autogematria.gematria_index import ALL_METHODS

REQUIRED_TABLES = {
    "books",
    "chapters",
    "verses",
    "words",
    "letters",
    "word_forms",
    "gematria_methods",
    "word_gematria",
}
REQUIRED_INDEXES = {"idx_gematria_value_method"}
EXPECTED_GEMATRIA_METHODS = {method.name for method in ALL_METHODS}


class DataValidationError(RuntimeError):
    """Raised when generated runtime data is missing, corrupt, or incompatible."""


def _database_uri(path: Path, *, immutable: bool) -> str:
    suffix = "?mode=ro"
    if immutable:
        suffix += "&immutable=1"
    return f"{path.resolve().as_uri()}{suffix}"


def connect_corpus(
    db_path: str | Path | None = None,
    *,
    row_factory: bool = True,
    immutable: bool = True,
) -> sqlite3.Connection:
    """Open the corpus database read-only without creating journal sidecars."""
    path = Path(db_path or DB_PATH)
    if not path.is_file():
        raise DataValidationError(
            f"Corpus database not found at {path}. Run 'ag-prepare-data' first or set "
            "AUTOGEMATRIA_DATA_DIR to a prepared data directory."
        )
    try:
        conn = sqlite3.connect(_database_uri(path, immutable=immutable), uri=True)
    except sqlite3.Error as exc:
        raise DataValidationError(f"Unable to open corpus database at {path}: {exc}") from exc
    if row_factory:
        conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def validate_corpus_database(
    db_path: str | Path | None = None,
    *,
    strict_version: bool = False,
) -> dict[str, Any]:
    """Validate schema, integrity, and required corpus/index contents."""
    path = Path(db_path or DB_PATH)
    conn = connect_corpus(path)
    try:
        integrity = str(conn.execute("PRAGMA quick_check").fetchone()[0])
        if integrity != "ok":
            raise DataValidationError(f"Corpus database integrity check failed: {integrity}")

        tables = {
            str(row["name"])
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        missing_tables = sorted(REQUIRED_TABLES - tables)
        if missing_tables:
            raise DataValidationError(
                "Corpus database is incomplete; missing tables: " + ", ".join(missing_tables)
            )

        indexes = {
            str(row["name"])
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        }
        missing_indexes = sorted(REQUIRED_INDEXES - indexes)
        if missing_indexes:
            raise DataValidationError(
                "Corpus database is not finalized; missing indexes: " + ", ".join(missing_indexes)
            )

        counts = {
            table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in (
                "books",
                "chapters",
                "verses",
                "words",
                "letters",
                "word_forms",
                "word_gematria",
            )
        }
        empty_tables = [table for table, count in counts.items() if count <= 0]
        if empty_tables:
            raise DataValidationError(
                "Corpus database contains empty tables: " + ", ".join(empty_tables)
            )

        if counts["books"] != TOTAL_BOOKS or counts["chapters"] != TOTAL_CHAPTERS:
            raise DataValidationError(
                "Corpus database is incomplete; expected "
                f"{TOTAL_BOOKS} books/{TOTAL_CHAPTERS} chapters, found "
                f"{counts['books']} books/{counts['chapters']} chapters"
            )
        expected_books = {
            api_name: (hebrew_name, category, num_chapters)
            for api_name, hebrew_name, category, num_chapters in TANAKH_BOOKS
        }
        actual_books = {
            str(row["api_name"]): (
                str(row["hebrew_name"]),
                str(row["category"]),
                int(row["num_chapters"]),
                int(row["actual_chapters"]),
                int(row["first_chapter"] or 0),
                int(row["last_chapter"] or 0),
            )
            for row in conn.execute(
                "SELECT b.api_name, b.hebrew_name, b.category, b.num_chapters, "
                "COUNT(c.chapter_id) AS actual_chapters, "
                "MIN(c.chapter_num) AS first_chapter, MAX(c.chapter_num) AS last_chapter "
                "FROM books b LEFT JOIN chapters c ON b.book_id = c.book_id "
                "GROUP BY b.book_id"
            )
        }
        registry_matches = actual_books.keys() == expected_books.keys()
        if registry_matches:
            for api_name, expected in expected_books.items():
                actual = actual_books[api_name]
                expected_chapters = expected[2]
                if actual[:3] != expected or actual[3:] != (
                    expected_chapters,
                    1,
                    expected_chapters,
                ):
                    registry_matches = False
                    break
        if not registry_matches:
            raise DataValidationError("Corpus database has an incompatible book registry")

        for table, column in (
            ("words", "absolute_word_index"),
            ("letters", "absolute_letter_index"),
        ):
            row = conn.execute(
                f"SELECT MIN({column}), MAX({column}), COUNT(DISTINCT {column}) FROM {table}"
            ).fetchone()
            if int(row[0]) != 0 or int(row[1]) != counts[table] - 1 or int(row[2]) != counts[table]:
                raise DataValidationError(
                    f"Corpus database has a non-gapless {column} sequence"
                )

        method_names = {
            str(row["method_name"])
            for row in conn.execute("SELECT method_name FROM gematria_methods")
        }
        method_count = len(method_names)
        if method_names != EXPECTED_GEMATRIA_METHODS:
            raise DataValidationError(
                "Corpus gematria method registry is incompatible; expected "
                f"{len(EXPECTED_GEMATRIA_METHODS)} known methods, found {method_count}"
            )
        expected_values = counts["word_forms"] * method_count
        if counts["word_gematria"] != expected_values:
            raise DataValidationError(
                "Corpus gematria index is incomplete; expected "
                f"{expected_values} values, found {counts['word_gematria']}"
            )

        schema_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if strict_version and schema_version != SCHEMA_VERSION:
            raise DataValidationError(
                f"Corpus schema version {schema_version} is outdated; expected {SCHEMA_VERSION}. "
                "Run 'ag-prepare-data' to rebuild it."
            )
        if schema_version not in (0, SCHEMA_VERSION):
            raise DataValidationError(
                f"Corpus schema version {schema_version} is incompatible with version {SCHEMA_VERSION}"
            )

        return {
            "ready": True,
            "database": str(path.resolve()),
            "database_bytes": path.stat().st_size,
            "schema_version": schema_version,
            "current_schema_version": SCHEMA_VERSION,
            "legacy_schema": schema_version == 0,
            "integrity": integrity,
            "gematria_methods": method_count,
            "counts": counts,
        }
    except sqlite3.Error as exc:
        raise DataValidationError(f"Corpus database validation failed: {exc}") from exc
    finally:
        conn.close()


def ensure_runtime_state(var_dir: str | Path | None = None) -> Path:
    """Create and verify the writable directory used for jobs and timing logs."""
    path = Path(var_dir or VAR_DIR)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DataValidationError(f"Unable to create runtime state directory {path}: {exc}") from exc
    if not os.access(path, os.W_OK | os.X_OK):
        raise DataValidationError(f"Runtime state directory is not writable: {path}")
    return path


def readiness_payload() -> tuple[dict[str, Any], bool]:
    """Return a JSON-ready readiness report and success flag."""
    try:
        database = validate_corpus_database()
        state_dir = ensure_runtime_state()
        return {
            "status": "ready",
            "database": database,
            "state_dir": str(state_dir.resolve()),
        }, True
    except DataValidationError as exc:
        return {"status": "not_ready", "error": str(exc)}, False
