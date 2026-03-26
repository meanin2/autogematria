"""CLI for deterministic verification of search results."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from autogematria.tools.glm_client import GLMClientError, chat_completion
from autogematria.tools.tool_functions import find_name_in_torah


def _build_summary(data: dict[str, Any]) -> dict[str, Any]:
    total = data.get("total_results", 0)
    results = data.get("results", [])
    verified = sum(1 for r in results if r.get("verification", {}).get("verified"))

    by_method: dict[str, int] = {}
    for r in results:
        method = r.get("method", "?")
        by_method[method] = by_method.get(method, 0) + 1

    return {
        "query": data.get("query"),
        "query_normalized": data.get("query_normalized"),
        "book_filter": data.get("book_filter"),
        "total_results": total,
        "verified_results": verified,
        "unverified_results": total - verified,
        "verified_ratio": (verified / total) if total else 0.0,
        "by_method": by_method,
    }


def _trim_for_llm(data: dict[str, Any], top_n: int = 10) -> list[dict[str, Any]]:
    rows = []
    for item in data.get("results", [])[:top_n]:
        loc = item.get("location") or {}
        rows.append(
            {
                "method": item.get("method"),
                "ref": f"{loc.get('book')} {loc.get('chapter')}:{loc.get('verse')}",
                "params": item.get("params"),
                "verified": item.get("verification", {}).get("verified"),
                "verification": item.get("verification"),
            }
        )
    return rows


def _ask_glm_for_audit(
    data: dict[str, Any],
    glm_model: str,
    glm_api_key: str | None,
    glm_base_url: str | None,
) -> dict[str, Any]:
    summary = _build_summary(data)
    compact = _trim_for_llm(data, top_n=10)

    system = (
        "You are auditing Torah-search findings. Be strict and skeptical. "
        "Use only the provided deterministic verification payloads."
    )
    user = (
        "Audit this search output.\n"
        "1) State whether the deterministic evidence supports each finding.\n"
        "2) Flag any methodological risks.\n"
        "3) Give a final confidence score 0-100.\n\n"
        f"Summary:\n{json.dumps(summary, ensure_ascii=False)}\n\n"
        f"Top Results:\n{json.dumps(compact, ensure_ascii=False)}"
    )

    response = chat_completion(
        model=glm_model,
        api_key=glm_api_key,
        base_url=glm_base_url,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return {
        "model": response["model"],
        "content": response["content"],
    }


def _print_human(data: dict[str, Any], summary: dict[str, Any], max_rows: int) -> None:
    print(f"\nQuery: {summary['query']}")
    print(f"Normalized: {summary['query_normalized']}")
    if summary["book_filter"]:
        print(f"Book filter: {summary['book_filter']}")
    print(f"Results: {summary['total_results']}")
    print(
        "Verified: "
        f"{summary['verified_results']}/{summary['total_results']} "
        f"({summary['verified_ratio']:.1%})"
    )
    print(f"By method: {summary['by_method']}")

    print("\nTop findings:")
    for i, item in enumerate(data.get("results", [])[:max_rows], 1):
        loc = item.get("location", {})
        ref = f"{loc.get('book')} {loc.get('chapter')}:{loc.get('verse')}"
        ver = item.get("verification", {})
        status = "PASS" if ver.get("verified") else "FAIL"
        print(f"  {i:2}. [{item.get('method')}] {ref}  verification={status}")
        params = item.get("params") or {}
        if params:
            print(f"      params={params}")
        if item.get("context"):
            print(f"      context={item['context'][:90]}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ag-verify",
        description="Run search + deterministic verification payload checks.",
    )
    parser.add_argument("name", help="Hebrew name or phrase to search")
    parser.add_argument("--book", default=None, help="Optional Tanakh book filter")
    parser.add_argument("--max-results", type=int, default=20)
    parser.add_argument("--els-max-skip", type=int, default=500)
    parser.add_argument(
        "--display-results",
        type=int,
        default=10,
        help="How many findings to print in text mode",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument(
        "--glm-audit",
        action="store_true",
        help="Ask GLM to independently audit the deterministic verification payload",
    )
    parser.add_argument("--glm-model", default="glm-5")
    parser.add_argument("--glm-api-key", default=None)
    parser.add_argument("--glm-base-url", default=None)
    args = parser.parse_args()

    data = find_name_in_torah(
        args.name,
        book=args.book,
        max_results=args.max_results,
        els_max_skip=args.els_max_skip,
        include_verification=True,
    )
    summary = _build_summary(data)

    glm_audit = None
    if args.glm_audit:
        try:
            glm_audit = _ask_glm_for_audit(
                data=data,
                glm_model=args.glm_model,
                glm_api_key=args.glm_api_key,
                glm_base_url=args.glm_base_url,
            )
        except GLMClientError as exc:
            glm_audit = {"error": str(exc)}

    if args.json:
        payload = {
            "summary": summary,
            "results": data.get("results", []),
            "glm_audit": glm_audit,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    _print_human(data, summary, args.display_results)
    if glm_audit:
        print("\nGLM audit:")
        if "error" in glm_audit:
            print(f"  ERROR: {glm_audit['error']}")
        else:
            print(f"  model: {glm_audit['model']}")
            print(glm_audit["content"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
