"""CLI for bounded multi-method name research runs."""

from __future__ import annotations

import argparse
import json

from autogematria.tools.tool_functions import run_name_research


def main() -> None:
    parser = argparse.ArgumentParser(prog="ag-research-name")
    parser.add_argument("query", help="Name or phrase to research")
    parser.add_argument(
        "--corpus-scope",
        choices=("torah", "tanakh"),
        default="torah",
        help="Primary corpus scope for the run",
    )
    parser.add_argument("--no-tanakh-expansion", action="store_true")
    parser.add_argument(
        "--methods",
        nargs="*",
        default=None,
        help="Optional subset of methods: substring roshei_tevot sofei_tevot els gematria",
    )
    parser.add_argument("--max-variants", type=int, default=16)
    parser.add_argument("--max-tasks", type=int, default=80)
    parser.add_argument("--max-results-per-task", type=int, default=12)
    parser.add_argument("--els-max-skip", type=int, default=120)
    parser.add_argument("--max-gematria-span-words", type=int, default=4)
    parser.add_argument(
        "--gematria-methods",
        nargs="*",
        default=None,
        help="Gematria methods to enumerate during gematria search tasks",
    )
    parser.add_argument("--json", action="store_true", help="Emit the full research ledger as JSON")
    args = parser.parse_args()

    payload = run_name_research(
        args.query,
        corpus_scope=args.corpus_scope,
        include_tanakh_expansion=not args.no_tanakh_expansion,
        methods=args.methods,
        max_variants=args.max_variants,
        max_tasks=args.max_tasks,
        max_results_per_task=args.max_results_per_task,
        els_max_skip=args.els_max_skip,
        gematria_methods=args.gematria_methods,
        max_gematria_span_words=args.max_gematria_span_words,
    )

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"\nQuery: {payload['query']}")
    print(f"Tasks run: {payload['tasks_run']} ({payload['stop_reason']})")
    best = payload.get("best_overall")
    if best:
        loc = best.get("location") or {}
        print(
            "Best overall: "
            f"{best.get('method')} {loc.get('book')} {loc.get('chapter')}:{loc.get('verse')} "
            f"score={((best.get('confidence') or {}).get('score'))}"
        )

    print("\nBest by method:")
    for method, row in sorted((payload.get("best_by_method") or {}).items()):
        if not row:
            continue
        loc = row.get("location") or {}
        print(
            f"  {method}: {loc.get('book')} {loc.get('chapter')}:{loc.get('verse')} "
            f"score={((row.get('confidence') or {}).get('score'))}"
        )

    print("\nJournal:")
    for entry in payload.get("journal", [])[:12]:
        details = entry.get("payload") or {}
        print(
            f"  {entry.get('event')} {entry.get('task_id') or '-'} "
            f"{details.get('method') or ''} {details.get('variant') or ''}"
        )


if __name__ == "__main__":
    main()
