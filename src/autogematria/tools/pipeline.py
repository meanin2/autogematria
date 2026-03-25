"""End-to-end 'find name in Torah' pipeline."""

from __future__ import annotations

from autogematria.tools.tool_functions import (
    find_name_in_torah,
    gematria_lookup,
)
from autogematria.normalize import normalize_hebrew, FinalsPolicy

# The main gematria methods to check
REPORT_GEMATRIA_METHODS = [
    "MISPAR_HECHRACHI",
    "MISPAR_GADOL",
    "MISPAR_KATAN",
    "ATBASH",
]


def find_name_full_report(
    name: str,
    book: str | None = None,
    els_max_skip: int = 500,
    max_results: int = 20,
) -> dict:
    """Complete 'find name in Torah' pipeline.

    1. Normalize the input name
    2. Run unified search across all methods
    3. Compute gematria for the name across multiple methods
    4. Find equivalent words in Tanakh for each method
    5. Return structured report

    Args:
        name: Hebrew name to find (e.g. "משה גינדי")
        book: Optional book filter
        els_max_skip: Max ELS skip distance
        max_results: Max search results per method
    """
    name_preserved = normalize_hebrew(name, FinalsPolicy.PRESERVE)
    name_normalized = normalize_hebrew(name, FinalsPolicy.NORMALIZE)

    # Run search across all methods
    search_results = find_name_in_torah(
        name, book=book, max_results=max_results, els_max_skip=els_max_skip,
    )

    # Also search each word of the name separately if multi-word
    words = name_preserved.split()
    word_results = {}
    if len(words) > 1:
        for w in words:
            wr = find_name_in_torah(w, book=book, max_results=10, els_max_skip=els_max_skip)
            word_results[w] = wr

    # Compute gematria across multiple methods
    gematria_info = {}
    for method in REPORT_GEMATRIA_METHODS:
        try:
            g = gematria_lookup(name_preserved, method=method, max_equivalents=10)
            gematria_info[method] = {
                "value": g["value"],
                "equivalents": [e["word"] for e in g["equivalents"][:5]],
            }
        except Exception:
            pass

    # Per-word gematria if multi-word name
    word_gematria = {}
    if len(words) > 1:
        for w in words:
            try:
                g = gematria_lookup(w, method="MISPAR_HECHRACHI", max_equivalents=5)
                word_gematria[w] = {
                    "value": g["value"],
                    "equivalents": [e["word"] for e in g["equivalents"][:5]],
                }
            except Exception:
                pass

    # Build summary
    method_counts = {}
    for r in search_results.get("results", []):
        m = r["method"]
        method_counts[m] = method_counts.get(m, 0) + 1

    return {
        "name": name,
        "name_preserved": name_preserved,
        "name_normalized": name_normalized,
        "book_filter": book,
        "search_results": search_results,
        "word_results": word_results if word_results else None,
        "gematria": gematria_info,
        "word_gematria": word_gematria if word_gematria else None,
        "summary": {
            "total_findings": search_results["total_results"],
            "methods_with_hits": method_counts,
            "standard_gematria": gematria_info.get("MISPAR_HECHRACHI", {}).get("value"),
        },
    }


def main():
    """CLI for quick full reports."""
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m autogematria.tools.pipeline <hebrew_name> [book]")
        sys.exit(1)

    name = sys.argv[1]
    book = sys.argv[2] if len(sys.argv) > 2 else None

    report = find_name_full_report(name, book=book)

    # Print summary
    print(f"\n{'='*60}")
    print(f"  FULL REPORT: {report['name']}")
    print(f"{'='*60}")
    print(f"  Normalized: {report['name_normalized']}")
    print(f"  Standard gematria: {report['summary']['standard_gematria']}")
    print(f"  Total findings: {report['summary']['total_findings']}")
    print(f"  Methods: {report['summary']['methods_with_hits']}")

    if report["gematria"]:
        print(f"\n  Gematria:")
        for method, info in report["gematria"].items():
            equivs = ", ".join(info["equivalents"][:3])
            print(f"    {method}: {info['value']} (also: {equivs})")

    if report["search_results"]["results"]:
        print(f"\n  Top findings:")
        for i, r in enumerate(report["search_results"]["results"][:10], 1):
            loc = r["location"]
            print(f"    {i}. [{r['method']}] {loc['book']} {loc['chapter']}:{loc['verse']}")
            if r.get("context"):
                ctx = r["context"][:60] + "..." if len(r["context"]) > 60 else r["context"]
                print(f"       {ctx}")

    print()


if __name__ == "__main__":
    main()
