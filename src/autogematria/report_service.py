"""Canonical full-report composition shared by CLI and HTTP surfaces."""

from __future__ import annotations

from typing import Any

from autogematria.normalize import FinalsPolicy, normalize_hebrew
from autogematria.research.html_export import prepare_showcase_payload
from autogematria.research.name_report import build_name_report
from autogematria.run_logger import RunTimer
from autogematria.search.gematria_reverse import build_name_gematria_graph
from autogematria.tools.tool_functions import showcase_name


def build_full_report_payload(query: str) -> dict[str, Any]:
    """Build the stable JSON report contract used by both primary frontends."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    query = query.strip()
    clean = normalize_hebrew(query, FinalsPolicy.PRESERVE).replace(" ", "")
    timer = RunTimer(
        operation="full_report",
        input_text=query,
        letter_count=len(clean),
        word_count=len(query.split()),
    )

    with timer:
        report = build_name_report(query)
        components = [(c["text"], c["role"]) for c in report.get("hebrew_components", [])]
        timer.component_count = len(components)

        showcase_raw = showcase_name(report["full_hebrew_name"])
        prepared = prepare_showcase_payload(showcase_raw)
        showcase = prepared.get("showcase", {})
        graph = build_name_gematria_graph(components) if components else {}
        timer.set_result_metadata(
            verdict=showcase.get("verdict_label", ""),
            cross_matches=(
                report.get("cross_comparison", {})
                .get("summary", {})
                .get("total_cross_matches", 0)
            ),
        )

    return {
        "report": report,
        "showcase": showcase,
        "graph": graph,
        "timing": {"elapsed_seconds": round(timer.elapsed_seconds, 2)},
    }
