"""Tests for the curated showcase layer."""

import json

import pytest

from autogematria.config import DB_PATH
from autogematria.research.presentation import build_showcase
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


def test_component_hit_is_not_labeled_as_direct_full_name_hit():
    row = {
        "method": "SUBSTRING",
        "family": "text",
        "found_text": "כהן",
        "location": {"book": "Leviticus", "chapter": 1, "verse": 5},
        "variant": {
            "text": "כהן",
            "kind": "token",
            "source": "token_exact",
            "token_count": 1,
        },
        "verification": {"verified": True},
        "confidence": {
            "score": 0.9,
            "features": {"match_type": "exact_word"},
        },
        "params": {"mode": "within_word"},
    }

    showcase = build_showcase(
        {"query": "פלוני כהן", "findings_by_method": {"substring": [row]}}
    )

    assert showcase["verdict"] == "presentable_indirect_hit"
    assert showcase["headline"] is None
    assert showcase["supporting_findings"][0]["found_text"] == "כהן"
