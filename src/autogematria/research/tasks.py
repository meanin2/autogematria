"""Task queue generation for bounded research runs."""

from __future__ import annotations

from autogematria.research.config import ResearchConfig
from autogematria.research.schema import ResearchTask, ResearchVariant
from autogematria.research.variants import generate_name_variants


def build_research_tasks(query: str, config: ResearchConfig) -> tuple[list[ResearchVariant], list[ResearchTask]]:
    """Build deterministic text and gematria research tasks for a query."""
    variants = generate_name_variants(query, max_variants=config.max_variants).variants[: config.max_variants]
    tasks: list[ResearchTask] = []
    task_num = 1
    for variant in variants:
        for scope in config.corpus_scopes:
            for method in config.text_methods:
                params: dict[str, object] = {
                    "max_results": config.max_text_results_per_task,
                }
                if method == "els":
                    params["els_max_skip"] = (
                        config.els_max_skip if scope == config.corpus_scope else config.els_max_skip_tanakh
                    )
                tasks.append(
                    ResearchTask(
                        task_id=f"{task_num:04d}:text:{method}:{scope}:{variant.text}",
                        family="text",
                        method=method,
                        variant=variant,
                        corpus_scope=scope,
                        params=params,
                    )
                )
                task_num += 1
                if len(tasks) >= config.max_tasks:
                    return variants, tasks

            for gematria_method in config.gematria_methods:
                tasks.append(
                    ResearchTask(
                        task_id=f"{task_num:04d}:gematria:signature:{scope}:{variant.text}",
                        family="gematria",
                        method="GEMATRIA",
                        variant=variant,
                        corpus_scope=scope,
                        params={
                            "gematria_method": gematria_method,
                            "max_results": config.max_gematria_results_per_task,
                            "max_sequence_span": config.max_gematria_span_words,
                        },
                        analysis_method=gematria_method,
                    )
                )
                task_num += 1
                if len(tasks) >= config.max_tasks:
                    return variants, tasks
    return variants, tasks
