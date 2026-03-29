"""Tests for the bounded multi-method research workflow."""

import pytest

from autogematria.config import DB_PATH
from autogematria.research.config import ResearchConfig
from autogematria.research.tasks import build_research_tasks
from autogematria.research.variants import build_variants
from autogematria.tools.tool_functions import run_name_research


@pytest.fixture(autouse=True)
def skip_no_db():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")


def test_build_variants_preserves_hebrew_and_transliteration():
    cfg = ResearchConfig(max_variants=8, max_full_name_variants=4)
    data = build_variants("moshe gindi", cfg)
    assert data["full_name_variants"]
    texts = [row["text"] for row in data["full_name_variants"]]
    assert "משה גינדי" in texts or "משה גנדי" in texts
    assert data["token_variants"]


def test_task_queue_includes_gematria_tasks():
    cfg = ResearchConfig(text_methods=("substring",), gematria_methods=("MISPAR_HECHRACHI",), max_tasks=20)
    _variants, tasks = build_research_tasks("משה", cfg)
    assert any(task.family == "gematria" for task in tasks)


def test_run_name_research_returns_structured_ledger():
    data = run_name_research(
        "משה",
        methods=["substring", "gematria"],
        max_variants=4,
        max_tasks=12,
        max_results_per_task=5,
        max_gematria_span_words=3,
    )
    assert data["tasks_run"] > 0
    assert data["journal"]
    assert "substring" in data["findings_by_method"]
    assert "gematria" in data["findings_by_method"]
    assert data["best_overall"] is not None
