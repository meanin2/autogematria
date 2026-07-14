"""Tests for the research runner and journal plumbing."""

from __future__ import annotations

import pytest

from autogematria.config import DB_PATH
from autogematria.research.config import ResearchConfig
from autogematria.research.runner import run_research


@pytest.fixture(autouse=True)
def skip_no_db():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")


def test_run_research_smoke_uses_existing_search_primitives():
    cfg = ResearchConfig(
        max_variants=2,
        max_tasks=4,
        text_methods=("substring",),
        gematria_methods=("MISPAR_HECHRACHI",),
        corpus_scopes=("torah",),
        max_text_results_per_task=3,
        max_gematria_results_per_task=3,
    )

    run = run_research("משה", cfg)

    assert run.variants
    assert run.tasks
    assert run.findings
    assert run.journal.entries[0].event == "run_started"
    assert run.journal.entries[-1].event == "run_completed"
    assert any(f.family == "text" for f in run.findings)
    assert any(f.family == "gematria" for f in run.findings)
    assert run.findings[0].to_dict()["variant"]["text"]


def test_runner_does_not_expand_full_name_tasks_into_token_fallbacks(monkeypatch):
    calls = []

    def fake_find_name_in_torah(name, **kwargs):
        calls.append((name, kwargs))
        return {"results": [], "total_results": 0}

    monkeypatch.setattr(
        "autogematria.tools.tool_functions.find_name_in_torah",
        fake_find_name_in_torah,
    )
    cfg = ResearchConfig(
        max_variants=1,
        max_tasks=1,
        text_methods=("substring",),
        gematria_methods=(),
        corpus_scopes=("torah",),
    )

    run_research("דבורה יעקב", cfg)

    assert calls
    assert calls[0][1]["expand_tokens"] is False
