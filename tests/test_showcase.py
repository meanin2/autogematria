"""Tests for the curated showcase layer."""

import json

import pytest

from autogematria.config import DB_PATH
from autogematria.tools import cli_entrypoints
from autogematria.tools.tool_functions import showcase_name


@pytest.fixture(autouse=True)
def skip_no_db():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")


def test_showcase_name_promotes_direct_hits():
    payload = showcase_name("משה")
    showcase = payload["showcase"]
    assert showcase["verdict"] == "presentable_direct_hit"
    assert showcase["verdict_label"] == "Direct textual hit"
    assert showcase["summary_line"]
    assert showcase["headline"] is not None
    assert showcase["headline"]["method"] == "SUBSTRING"


def test_show_name_cli_emits_curated_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["ag-show-name", "משה", "--json"])
    cli_entrypoints.show_name_main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["query"] == "משה"
    assert payload["showcase"]["headline"] is not None


def test_show_name_cli_human_output_is_consumer_facing(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["ag-show-name", "משה"])
    cli_entrypoints.show_name_main()
    out = capsys.readouterr().out
    assert "Verdict: Direct textual hit" in out
    assert "Headline:" in out
    assert "For the full ledger" in out
