"""Bounded multi-method research runner."""

from __future__ import annotations

from typing import Any

from autogematria.research.config import ResearchConfig
from autogematria.research.gematria_search import search_gematria_signatures
from autogematria.research.journal import start_journal
from autogematria.research.schema import ResearchFinding, ResearchRun
from autogematria.research.tasks import build_research_tasks


def _finding_from_row(task, query: str, row: dict[str, Any]) -> ResearchFinding:
    return ResearchFinding(
        task_id=task.task_id,
        query=query,
        variant=task.variant,
        family=task.family,
        method=str(row.get("method")),
        analysis_method=task.analysis_method or task.method,
        corpus_scope=task.corpus_scope,
        book=row.get("location", {}).get("book"),
        rank=int(row.get("rank") or 1),
        total_results=int(row.get("total_results") or 0),
        location=dict(row.get("location") or {}),
        location_end=dict(row["location_end"]) if row.get("location_end") else None,
        found_text=str(row.get("found_text") or ""),
        params=dict(row.get("params") or {}),
        verification=dict(row.get("verification") or {}),
        confidence=dict(row.get("confidence") or {}),
        task_params=dict(task.params),
    )


def run_research(query: str, config: ResearchConfig | None = None) -> ResearchRun:
    """Run bounded text and gematria research tasks for a query."""
    from autogematria.tools.tool_functions import find_name_in_torah

    cfg = config or ResearchConfig()
    variants, tasks = build_research_tasks(query, cfg)
    journal = start_journal(query)
    findings: list[ResearchFinding] = []
    stop_reason = "completed_task_queue"

    for task in tasks:
        if task.family == "text":
            payload = find_name_in_torah(
                task.variant.text,
                methods=[task.method],
                max_results=int(task.params.get("max_results") or cfg.max_text_results_per_task),
                els_max_skip=int(task.params.get("els_max_skip") or cfg.els_max_skip),
                include_verification=True,
                diversify_methods=False,
                corpus_scope=task.corpus_scope,
            )
            rows = payload.get("results", [])
            total_results = payload.get("total_results", len(rows))
            for rank, row in enumerate(rows, 1):
                enriched = dict(row)
                enriched["rank"] = rank
                enriched["total_results"] = total_results
                findings.append(_finding_from_row(task, query, enriched))
        else:
            rows = search_gematria_signatures(
                task.variant.text,
                methods=[task.analysis_method or "MISPAR_HECHRACHI"],
                corpus_scope=task.corpus_scope,
                max_results=int(task.params.get("max_results") or cfg.max_gematria_results_per_task),
                max_sequence_span=int(task.params.get("max_sequence_span") or cfg.max_gematria_span_words),
                variant=task.variant,
                task_id=task.task_id,
            )
            findings.extend(rows)

        journal.add(
            "task_completed",
            task_id=task.task_id,
            family=task.family,
            method=task.method,
            variant=task.variant.text,
            corpus_scope=task.corpus_scope,
            findings_added=len(findings),
        )

        if cfg.stop_on_exact_full_name and any(
            finding.family == "text"
            and finding.variant.kind == "full_name"
            and finding.method == "SUBSTRING"
            and finding.verification.get("verified")
            and ((finding.confidence.get("features") or {}).get("match_type") == "exact_phrase")
            for finding in findings
        ):
            stop_reason = "exact_full_name_match"
            break

    journal.add("run_completed", stop_reason=stop_reason, finding_count=len(findings))
    return ResearchRun(
        query=query,
        config={
            "max_variants": cfg.max_variants,
            "max_tasks": cfg.max_tasks,
            "text_methods": list(cfg.text_methods),
            "gematria_methods": list(cfg.gematria_methods),
            "corpus_scopes": list(cfg.corpus_scopes),
            "max_text_results_per_task": cfg.max_text_results_per_task,
            "max_gematria_results_per_task": cfg.max_gematria_results_per_task,
            "els_max_skip": cfg.els_max_skip,
            "els_max_skip_tanakh": cfg.els_max_skip_tanakh,
            "max_gematria_span_words": cfg.max_gematria_span_words,
        },
        variants=variants,
        tasks=tasks,
        findings=findings,
        journal=journal,
        stop_reason=stop_reason,
    )


def run_name_research(
    query: str,
    *,
    config: ResearchConfig | None = None,
    search_func=None,
    gematria_search_func=None,
) -> dict[str, Any]:
    """Compatibility wrapper returning a JSON-serializable research ledger."""
    del search_func, gematria_search_func
    return run_research(query, config=config).to_dict()
