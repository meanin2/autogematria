"""Compare query behavior between Torah-only and full Tanakh scopes.

This probe is intentionally deterministic and conservative:
- fixed query set (targets + multi-word hard negatives),
- fixed search parameters,
- strict delta reporting for verdict/confidence/total_results.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass

from autogematria.autoresearch.ground_truth import load_ground_truth
from autogematria.tools.tool_functions import find_name_in_torah


TARGET_QUERIES = [
    "משה גנדי",
    "דורית אליסה גינדי",
]


@dataclass(frozen=True)
class ScopeSnapshot:
    verdict: str
    confidence: float
    total_results: int
    strongest_method: str | None
    strongest_ref: str | None


def _query_set() -> list[str]:
    hard_multi = sorted(
        {
            entry.name
            for entry in load_ground_truth()
            if entry.track == "hard_negative" and " " in entry.name
        }
    )
    queries = list(TARGET_QUERIES)
    queries.extend(q for q in hard_multi if q not in queries)
    return queries


def _snapshot(query: str, scope: str) -> ScopeSnapshot:
    payload = find_name_in_torah(
        query,
        max_results=20,
        diversify_methods=False,
        corpus_scope=scope,
    )
    final = payload.get("final_verdict") or {}
    strongest = final.get("strongest_evidence") or {}
    return ScopeSnapshot(
        verdict=str(final.get("verdict") or ""),
        confidence=float(final.get("confidence_score") or 0.0),
        total_results=int(payload.get("total_results") or 0),
        strongest_method=strongest.get("method"),
        strongest_ref=strongest.get("ref"),
    )


def run_probe(*, offset: int = 0, limit: int | None = None) -> dict:
    all_queries = _query_set()
    sliced = all_queries[offset : offset + limit] if limit is not None else all_queries[offset:]

    rows = []
    changed = []
    hard_negative_regressions = []
    for query in sliced:
        torah = _snapshot(query, "torah")
        tanakh = _snapshot(query, "tanakh")
        row = {
            "query": query,
            "torah": asdict(torah),
            "tanakh": asdict(tanakh),
            "changed": (
                torah.verdict != tanakh.verdict
                or round(torah.confidence, 4) != round(tanakh.confidence, 4)
                or torah.total_results != tanakh.total_results
            ),
        }
        rows.append(row)
        if row["changed"]:
            changed.append(row)
        if query not in TARGET_QUERIES and tanakh.verdict != "no_convincing_evidence":
            hard_negative_regressions.append(row)

    return {
        "total_queries": len(sliced),
        "offset": offset,
        "limit": limit,
        "changed_count": len(changed),
        "negative_regressions": len(hard_negative_regressions),
        "changed_queries": changed,
        "negative_regression_queries": hard_negative_regressions,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe Torah vs Tanakh scope differences.")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    payload = run_probe(offset=args.offset, limit=args.limit)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
