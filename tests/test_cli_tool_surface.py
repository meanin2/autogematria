"""Tests for CLI parity with the former tool surface."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from autogematria.config import DB_PATH, PROJECT_ROOT
from autogematria.tools import cli_entrypoints


EXPECTED_SCRIPTS = {
    "ag-search-name",
    "ag-lookup-gematria",
    "ag-search-gematria-patterns",
    "ag-explore-gematria-connections",
    "ag-read-verse",
    "ag-inspect-els",
    "ag-corpus-stats",
    "ag-show-name",
    "ag-research-name",
}


def test_pyproject_exposes_cli_tool_surface():
    payload = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = set((payload.get("project") or {}).get("scripts") or {})
    assert EXPECTED_SCRIPTS.issubset(scripts)


@pytest.fixture(autouse=True)
def skip_no_db():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")


def test_search_name_cli_emits_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["ag-search-name", "משה", "--max-results", "2", "--json"])
    cli_entrypoints.search_name_main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["query"] == "משה"
    assert payload["total_results"] >= 1


def test_corpus_stats_cli_emits_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["ag-corpus-stats", "--json"])
    cli_entrypoints.corpus_stats_main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["total_books"] == 39
