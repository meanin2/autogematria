"""CLI entry points mirroring the former MCP tool surface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from autogematria.publish.herenow import publish_directory
from autogematria.research.html_export import write_showcase_html, write_showcase_site_bundle
from autogematria.tools.tool_functions import (
    corpus_stats,
    els_detail,
    find_name_in_torah,
    showcase_name,
    gematria_connections,
    gematria_lookup,
    gematria_pattern_search,
    get_verse,
)


PRESET_DEFAULTS = {
    "demo": {
        "max_variants": 8,
        "max_tasks": 40,
        "max_results_per_task": 6,
        "els_max_skip": 60,
        "max_gematria_span_words": 3,
        "include_tanakh_expansion": True,
    },
    "strict": {
        "max_variants": 6,
        "max_tasks": 28,
        "max_results_per_task": 5,
        "els_max_skip": 40,
        "max_gematria_span_words": 2,
        "include_tanakh_expansion": True,
    },
    "wide": {
        "max_variants": 12,
        "max_tasks": 60,
        "max_results_per_task": 8,
        "els_max_skip": 80,
        "max_gematria_span_words": 3,
        "include_tanakh_expansion": True,
    },
}


def _print_payload(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _finding_tag(row: dict) -> str:
    method = str(row.get("method") or "")
    mode = (row.get("params") or {}).get("mode") or (row.get("params") or {}).get("search_kind")
    return f"{method}/{mode}" if mode else method


def search_name_main() -> None:
    parser = argparse.ArgumentParser(prog="ag-search-name")
    parser.add_argument("name")
    parser.add_argument("--methods", nargs="*", default=None)
    parser.add_argument("--book", default=None)
    parser.add_argument("--max-results", type=int, default=20)
    parser.add_argument("--els-max-skip", type=int, default=500)
    parser.add_argument("--no-verification", action="store_true")
    parser.add_argument("--corpus-scope", choices=("torah", "tanakh"), default="torah")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    _print_payload(
        find_name_in_torah(
            name=args.name,
            methods=args.methods,
            book=args.book,
            max_results=args.max_results,
            els_max_skip=args.els_max_skip,
            include_verification=not args.no_verification,
            corpus_scope=args.corpus_scope,
        ),
        args.json,
    )


def lookup_gematria_main() -> None:
    parser = argparse.ArgumentParser(prog="ag-lookup-gematria")
    parser.add_argument("word")
    parser.add_argument("--method", default="MISPAR_HECHRACHI")
    parser.add_argument("--max-equivalents", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    _print_payload(
        gematria_lookup(args.word, method=args.method, max_equivalents=args.max_equivalents),
        args.json,
    )


def search_gematria_patterns_main() -> None:
    parser = argparse.ArgumentParser(prog="ag-search-gematria-patterns")
    parser.add_argument("query")
    parser.add_argument("--methods", nargs="*", default=None)
    parser.add_argument("--book", default=None)
    parser.add_argument("--max-results", type=int, default=20)
    parser.add_argument("--max-span-words", type=int, default=4)
    parser.add_argument("--corpus-scope", choices=("torah", "tanakh"), default="torah")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    _print_payload(
        gematria_pattern_search(
            query=args.query,
            methods=args.methods,
            book=args.book,
            max_results=args.max_results,
            max_span_words=args.max_span_words,
            corpus_scope=args.corpus_scope,
        ),
        args.json,
    )


def explore_gematria_connections_main() -> None:
    parser = argparse.ArgumentParser(prog="ag-explore-gematria-connections")
    parser.add_argument("word")
    parser.add_argument("--method", default="MISPAR_HECHRACHI")
    parser.add_argument("--max-related", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    _print_payload(
        gematria_connections(args.word, method=args.method, max_related=args.max_related),
        args.json,
    )


def read_verse_main() -> None:
    parser = argparse.ArgumentParser(prog="ag-read-verse")
    parser.add_argument("book")
    parser.add_argument("chapter", type=int)
    parser.add_argument("verse", type=int)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    _print_payload(get_verse(args.book, args.chapter, args.verse), args.json)


def inspect_els_main() -> None:
    parser = argparse.ArgumentParser(prog="ag-inspect-els")
    parser.add_argument("query")
    parser.add_argument("skip", type=int)
    parser.add_argument("start_index", type=int)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    _print_payload(els_detail(args.query, args.skip, args.start_index), args.json)


def corpus_stats_main() -> None:
    parser = argparse.ArgumentParser(prog="ag-corpus-stats")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    _print_payload(corpus_stats(), args.json)


def show_name_main() -> None:
    parser = argparse.ArgumentParser(prog="ag-show-name")
    parser.add_argument("query")
    parser.add_argument("--corpus-scope", choices=("torah", "tanakh"), default="torah")
    parser.add_argument("--preset", choices=("demo", "strict", "wide"), default="demo")
    parser.add_argument("--no-tanakh-expansion", action="store_true")
    parser.add_argument("--methods", nargs="*", default=None)
    parser.add_argument("--max-variants", type=int, default=None)
    parser.add_argument("--max-tasks", type=int, default=None)
    parser.add_argument("--max-results-per-task", type=int, default=None)
    parser.add_argument("--els-max-skip", type=int, default=None)
    parser.add_argument("--max-gematria-span-words", type=int, default=None)
    parser.add_argument("--gematria-methods", nargs="*", default=None)
    parser.add_argument("--html-out", default=None)
    parser.add_argument("--site-dir", default=None)
    parser.add_argument("--publish-here-now", action="store_true")
    parser.add_argument("--here-now-api-key", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    preset = PRESET_DEFAULTS[args.preset]
    max_variants = args.max_variants if args.max_variants is not None else preset["max_variants"]
    max_tasks = args.max_tasks if args.max_tasks is not None else preset["max_tasks"]
    max_results_per_task = (
        args.max_results_per_task
        if args.max_results_per_task is not None
        else preset["max_results_per_task"]
    )
    els_max_skip = args.els_max_skip if args.els_max_skip is not None else preset["els_max_skip"]
    max_gematria_span_words = (
        args.max_gematria_span_words
        if args.max_gematria_span_words is not None
        else preset["max_gematria_span_words"]
    )
    include_tanakh_expansion = (
        False if args.no_tanakh_expansion else bool(preset["include_tanakh_expansion"])
    )

    payload = showcase_name(
        args.query,
        corpus_scope=args.corpus_scope,
        include_tanakh_expansion=include_tanakh_expansion,
        methods=args.methods,
        max_variants=max_variants,
        max_tasks=max_tasks,
        max_results_per_task=max_results_per_task,
        els_max_skip=els_max_skip,
        gematria_methods=args.gematria_methods,
        max_gematria_span_words=max_gematria_span_words,
    )
    html_output: Path | None = None
    site_bundle: dict[str, Path] | None = None
    site_bundle_dir: Path | None = None
    here_now: dict | None = None
    if args.html_out:
        html_output = write_showcase_html(payload, args.html_out)
    if args.site_dir:
        site_bundle = write_showcase_site_bundle(payload, args.site_dir)
        site_bundle_dir = site_bundle["directory"]
    if args.publish_here_now:
        if site_bundle_dir is None:
            site_bundle_dir = Path(tempfile.mkdtemp(prefix="autogematria-showcase-"))
            site_bundle = write_showcase_site_bundle(payload, site_bundle_dir)
        here_now = publish_directory(
            site_bundle_dir,
            api_key=args.here_now_api_key,
            viewer_title=f"AutoGematria Showcase · {args.query}",
            viewer_description=payload["showcase"]["summary_line"],
        )
    if args.json:
        json_payload = dict(payload)
        if html_output is not None:
            json_payload["html_output"] = str(html_output)
        if site_bundle is not None:
            json_payload["site_bundle"] = {key: str(value) for key, value in site_bundle.items()}
        if here_now is not None:
            json_payload["here_now"] = here_now
        _print_payload(json_payload, True)
        return

    showcase = payload["showcase"]
    print(f"\nQuery: {payload['query']}")
    print(f"Preset: {args.preset}")
    print(f"Verdict: {showcase['verdict_label']}")
    print(showcase["summary_line"])
    headline = showcase.get("headline")
    if headline:
        loc = headline.get("location") or {}
        conf = (headline.get("confidence") or {}).get("score")
        print(
            "Headline: "
            f"{headline.get('found_text')} at {loc.get('book')} {loc.get('chapter')}:{loc.get('verse')} "
            f"via {headline.get('method')} (score={conf})"
        )

    if showcase.get("headline_findings"):
        print("\nHeadline findings:")
        for row in showcase["headline_findings"]:
            loc = row.get("location") or {}
            print(
                f"  {row.get('found_text')} "
                f"[{row.get('method')}] {loc.get('book')} {loc.get('chapter')}:{loc.get('verse')}"
            )

    if showcase.get("supporting_findings"):
        print("\nSupporting findings:")
        for row in showcase["supporting_findings"]:
            loc = row.get("location") or {}
            print(
                f"  {row.get('found_text')} "
                f"[{_finding_tag(row)}] {loc.get('book')} {loc.get('chapter')}:{loc.get('verse')}"
            )

    if showcase.get("interesting_findings"):
        print("\nInteresting findings:")
        for row in showcase["interesting_findings"]:
            loc = row.get("location") or {}
            print(
                f"  {row.get('found_text')} "
                f"[{_finding_tag(row)}] {loc.get('book')} {loc.get('chapter')}:{loc.get('verse')}"
            )
    if showcase.get("hidden_findings"):
        print(f"\nAdditional findings hidden: {showcase['hidden_findings']}")
    if html_output is not None:
        print(f"\nSaved branded showcase HTML to: {html_output}")
    if site_bundle is not None:
        print(f"\nSaved static site bundle to: {site_bundle['directory']}")
        print(f"  HTML: {site_bundle['index_html']}")
        print(f"  JSON: {site_bundle['result_json']}")
    if here_now is not None:
        print(f"\nPublished to here.now: {here_now['site_url']}")
        if here_now.get("claimUrl"):
            print(f"Claim URL: {here_now['claimUrl']}")
        if here_now.get("expiresAt"):
            print(f"Expires at: {here_now['expiresAt']}")
    print("\nFor the full ledger, run: ag-research-name \"<name>\" --json")
