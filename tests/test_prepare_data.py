"""Tests for atomic corpus database activation."""

from __future__ import annotations

import sqlite3

import pytest

import autogematria.prepare_data as prepare_module
from autogematria.download import _book_payload_is_complete


def test_resume_only_accepts_well_formed_complete_book_payloads():
    assert _book_payload_is_complete(
        {"chapters": {"1": ["בראשית"], "2": ["ויכלו"]}},
        2,
    )
    assert not _book_payload_is_complete(
        {"chapters": {"1": ["בראשית"], "2": "not a verse list"}},
        2,
    )
    assert not _book_payload_is_complete({"chapters": {"1": ["בראשית"]}}, 2)


def _stub_common_pipeline(monkeypatch):
    monkeypatch.setattr(
        prepare_module,
        "validate_corpus_files",
        lambda _path: {"books": 39, "chapters": 929, "verses": 23_206},
    )
    monkeypatch.setattr(prepare_module, "compute_all_gematria", lambda **_kwargs: None)
    monkeypatch.setattr(prepare_module, "build_report_indexes", lambda **_kwargs: None)
    monkeypatch.setattr(
        prepare_module,
        "validate_corpus_database",
        lambda path, strict_version: {
            "ready": True,
            "database": str(path),
            "counts": {"books": 39, "verses": 23_206, "words": 1, "letters": 1},
        },
    )


def test_prepare_data_atomically_replaces_database(tmp_path, monkeypatch):
    _stub_common_pipeline(monkeypatch)
    final_db = tmp_path / "autogematria.db"
    final_db.write_bytes(b"old database")

    def fake_ingest(*, corpus_dir, db_path):
        assert corpus_dir == tmp_path / "corpus"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE marker(value TEXT)")
        conn.execute("INSERT INTO marker VALUES ('new')")
        conn.commit()
        conn.close()

    monkeypatch.setattr(prepare_module, "ingest_all", fake_ingest)
    result = prepare_module.prepare_data(tmp_path, download=False)

    conn = sqlite3.connect(final_db)
    assert conn.execute("SELECT value FROM marker").fetchone()[0] == "new"
    conn.close()
    assert result["database"]["database"] == str(final_db.resolve())
    assert not (tmp_path / "autogematria.db.building").exists()


def test_prepare_failure_preserves_previous_database(tmp_path, monkeypatch):
    _stub_common_pipeline(monkeypatch)
    final_db = tmp_path / "autogematria.db"
    final_db.write_bytes(b"known-good")

    def fake_ingest(*, corpus_dir, db_path):
        del corpus_dir
        db_path.write_bytes(b"incomplete")

    def fail_index(*, db_path):
        del db_path
        raise RuntimeError("index failed")

    monkeypatch.setattr(prepare_module, "ingest_all", fake_ingest)
    monkeypatch.setattr(prepare_module, "compute_all_gematria", fail_index)

    with pytest.raises(RuntimeError, match="index failed"):
        prepare_module.prepare_data(tmp_path, download=False)

    assert final_db.read_bytes() == b"known-good"
    assert not (tmp_path / "autogematria.db.building").exists()


def test_validation_failure_cleans_stale_build_artifacts(tmp_path, monkeypatch):
    final_db = tmp_path / "autogematria.db"
    building_db = tmp_path / "autogematria.db.building"
    final_db.write_bytes(b"known-good")
    building_db.write_bytes(b"stale")
    building_db.with_name(f"{building_db.name}-wal").write_bytes(b"stale wal")

    def fail_validation(_path):
        raise ValueError("invalid corpus")

    monkeypatch.setattr(prepare_module, "validate_corpus_files", fail_validation)

    with pytest.raises(ValueError, match="invalid corpus"):
        prepare_module.prepare_data(tmp_path, download=False)

    assert final_db.read_bytes() == b"known-good"
    assert not building_db.exists()
    assert not building_db.with_name(f"{building_db.name}-wal").exists()
