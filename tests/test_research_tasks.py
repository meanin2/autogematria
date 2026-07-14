"""Tests for research task generation."""

from autogematria.research.config import ResearchConfig
from autogematria.research.tasks import build_research_tasks


def test_build_research_tasks_is_deterministic_and_covers_configured_methods():
    cfg = ResearchConfig(
        max_variants=2,
        max_tasks=20,
        text_methods=("substring", "els"),
        gematria_methods=("MISPAR_HECHRACHI", "ATBASH"),
        corpus_scopes=("torah",),
        max_text_results_per_task=3,
        max_gematria_results_per_task=4,
    )

    variants, tasks = build_research_tasks("moshe gindi", cfg)

    assert len(variants) == 2
    assert len(tasks) == 8
    assert len({task.task_id for task in tasks}) == len(tasks)
    assert tasks[0].task_id.startswith("0001:text:substring:torah:")
    assert tasks[1].task_id.startswith("0002:text:els:torah:")
    assert tasks[-1].family == "gematria"
    assert tasks[-1].params["gematria_method"] == "ATBASH"


def test_full_name_initials_only_schedule_roshei_tevot():
    cfg = ResearchConfig(
        max_variants=8,
        max_tasks=100,
        corpus_scopes=("torah", "tanakh"),
    )

    variants, tasks = build_research_tasks("דבורה יעקב", cfg)

    initials = next(variant for variant in variants if variant.source == "full_name_initials")
    initials_tasks = [task for task in tasks if task.variant == initials]
    assert initials.kind == "initials"
    assert initials_tasks
    assert {task.method for task in initials_tasks} == {"roshei_tevot"}
    assert {task.family for task in initials_tasks} == {"text"}
