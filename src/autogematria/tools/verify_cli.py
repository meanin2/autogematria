"""CLI for deterministic verification of search results."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from autogematria.tools.glm_client import GLMClientError, chat_completion
from autogematria.tools.name_variants import contains_hebrew, generate_hebrew_variants
from autogematria.tools.tool_functions import find_name_in_torah


def _build_summary(data: dict[str, Any]) -> dict[str, Any]:
    total = data.get("total_results", 0)
    results = data.get("results", [])
    verified = sum(1 for r in results if r.get("verification", {}).get("verified"))
    confidence_counts: dict[str, int] = {}

    by_method: dict[str, int] = {}
    for r in results:
        method = r.get("method", "?")
        by_method[method] = by_method.get(method, 0) + 1
        label = (r.get("confidence") or {}).get("label")
        if label:
            confidence_counts[str(label)] = confidence_counts.get(str(label), 0) + 1

    return {
        "query": data.get("query"),
        "query_normalized": data.get("query_normalized"),
        "book_filter": data.get("book_filter"),
        "corpus_scope": data.get("corpus_scope"),
        "total_results": total,
        "verified_results": verified,
        "unverified_results": total - verified,
        "verified_ratio": (verified / total) if total else 0.0,
        "by_method": by_method,
        "confidence_labels": confidence_counts,
        "final_verdict": (data.get("final_verdict") or {}).get("verdict"),
        "final_confidence": (data.get("final_verdict") or {}).get("confidence_score"),
    }


def _confidence_rank(label: str) -> int:
    order = {"invalid": 0, "very_low": 1, "low": 2, "medium": 3, "high": 4}
    return order.get(label, 0)


def _summarize_word_breakdown(
    query: str,
    *,
    max_results: int,
    els_max_skip: int,
    book: str | None,
    corpus_scope: str,
) -> dict[str, Any]:
    words = query.split()
    if len(words) <= 1:
        return {"enabled": False}

    per_word = {}
    for word in words:
        data = find_name_in_torah(
            word,
            book=book,
            max_results=max_results,
            els_max_skip=els_max_skip,
            include_verification=True,
            corpus_scope=corpus_scope,
        )
        best_label = "invalid"
        best_score = 0.0
        best_is_direct_exact = False
        for row in data.get("results", []):
            conf = row.get("confidence") or {}
            label = str(conf.get("label", "invalid"))
            score = float(conf.get("score", 0.0) or 0.0)
            features = conf.get("features") or {}
            is_direct_exact = (
                row.get("method") == "SUBSTRING"
                and features.get("match_type") == "exact_word"
            )
            if _confidence_rank(label) > _confidence_rank(best_label):
                best_label = label
                best_score = score
                best_is_direct_exact = is_direct_exact
            elif label == best_label and score > best_score:
                best_score = score
                best_is_direct_exact = is_direct_exact

        per_word[word] = {
            "total_results": data.get("total_results", 0),
            "best_label": best_label,
            "best_score": round(best_score, 4),
            "best_is_direct_exact": best_is_direct_exact,
            "top_result": data.get("results", [None])[0],
        }

    has_direct_strong = any(
        v["best_label"] in ("high", "medium") and v["best_is_direct_exact"]
        for v in per_word.values()
    )
    all_direct_strong = all(
        v["best_label"] in ("high", "medium") and v["best_is_direct_exact"]
        for v in per_word.values()
    )
    any_hits = any(v["total_results"] > 0 for v in per_word.values())

    if all_direct_strong:
        overall = "strong_word_evidence"
    elif has_direct_strong:
        overall = "partial_word_evidence"
    elif any_hits:
        overall = "weak_word_evidence"
    else:
        overall = "no_word_evidence"

    return {
        "enabled": True,
        "overall": overall,
        "words": per_word,
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
                "confidence": item.get("confidence"),
                "verification": item.get("verification"),
            }
        )
    return rows


def _resolve_query_with_variants(
    query: str,
    *,
    auto_hebrew: bool,
    book: str | None,
    max_results: int,
    els_max_skip: int,
    corpus_scope: str,
) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    if not auto_hebrew or contains_hebrew(query):
        data = find_name_in_torah(
            query,
            book=book,
            max_results=max_results,
            els_max_skip=els_max_skip,
            include_verification=True,
            corpus_scope=corpus_scope,
        )
        return query, data, []

    variants = generate_hebrew_variants(query, max_variants=12)
    if not variants:
        variants = [query]

    best_variant = variants[0]
    best_data = None
    best_key = (-1, -1, -1, 0)  # (high+medium, verified, total, -index)
    variant_rows = []
    first_data = None
    first_key = None

    for idx, variant in enumerate(variants):
        data = find_name_in_torah(
            variant,
            book=book,
            max_results=max_results,
            els_max_skip=els_max_skip,
            include_verification=True,
            corpus_scope=corpus_scope,
        )
        if idx == 0:
            first_data = data
        summary = _build_summary(data)
        labels = summary.get("confidence_labels", {})
        high_medium = int(labels.get("high", 0)) + int(labels.get("medium", 0))
        verified = int(summary.get("verified_results", 0))
        total = int(summary.get("total_results", 0))
        row = {
            "index": idx,
            "variant": variant,
            "high_medium": high_medium,
            "verified": verified,
            "total": total,
        }
        variant_rows.append(row)

        key = (high_medium, verified, total, -idx)
        if idx == 0:
            first_key = key
        if key > best_key:
            best_key = key
            best_variant = variant
            best_data = data

    # If no variant has any medium/high evidence, keep curated-first transliteration.
    if best_key[0] <= 0:
        best_variant = variants[0]
        best_data = first_data
    # Avoid overfitting to weak alternate transliterations.
    elif best_key[3] != 0 and best_key[0] < 2:
        best_variant = variants[0]
        best_data = first_data
    elif first_key is not None and first_key[0] > 0:
        best_variant = variants[0]
        best_data = first_data

    if best_data is None:
        best_data = find_name_in_torah(
            best_variant,
            book=book,
            max_results=max_results,
            els_max_skip=els_max_skip,
            include_verification=True,
            corpus_scope=corpus_scope,
        )
    return best_variant, best_data, variant_rows


def _ask_glm_for_audit(
    data: dict[str, Any],
    glm_model: str,
    glm_api_key: str | None,
    glm_base_url: str | None,
    glm_allow_fallback: bool = True,
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
        allow_model_fallback=glm_allow_fallback,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return {
        "model_requested": response.get("model_requested", glm_model),
        "model": response["model"],
        "base_url": response.get("base_url"),
        "content": response["content"],
    }


def _print_human(data: dict[str, Any], summary: dict[str, Any], max_rows: int) -> None:
    print(f"\nQuery: {summary['query']}")
    print(f"Normalized: {summary['query_normalized']}")
    print(f"Corpus scope: {summary.get('corpus_scope', 'torah')}")
    if summary["book_filter"]:
        print(f"Book filter: {summary['book_filter']}")
    print(f"Results: {summary['total_results']}")
    print(
        "Verified: "
        f"{summary['verified_results']}/{summary['total_results']} "
        f"({summary['verified_ratio']:.1%})"
    )
    print(f"By method: {summary['by_method']}")
    if summary["confidence_labels"]:
        print(f"Confidence labels: {summary['confidence_labels']}")
    if summary.get("final_verdict"):
        print(
            f"Final verdict: {summary['final_verdict']} "
            f"(confidence={summary.get('final_confidence')})"
        )
    strongest = (data.get("final_verdict") or {}).get("strongest_evidence")
    if strongest:
        print(
            "Strongest evidence: "
            f"{strongest.get('method')} {strongest.get('ref')} "
            f"score={strongest.get('score')}"
        )
    discounted = (data.get("final_verdict") or {}).get("discounted_findings") or []
    if discounted:
        print("Discounted as weak/random-like:")
        for item in discounted[:4]:
            print(f"  - {item}")

    print("\nTop findings:")
    for i, item in enumerate(data.get("results", [])[:max_rows], 1):
        loc = item.get("location", {})
        ref = f"{loc.get('book')} {loc.get('chapter')}:{loc.get('verse')}"
        ver = item.get("verification", {})
        conf = item.get("confidence", {})
        status = "PASS" if ver.get("verified") else "FAIL"
        label = conf.get("label", "?")
        score = conf.get("score")
        print(
            f"  {i:2}. [{item.get('method')}] {ref}  "
            f"verification={status} confidence={label}({score})"
        )
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
    parser.add_argument(
        "--glm-strict-model",
        action="store_true",
        help="Do not fallback from requested GLM model to glm-4.7",
    )
    parser.add_argument(
        "--word-breakdown",
        action="store_true",
        help="For multi-word names, run per-word verification summary",
    )
    parser.add_argument(
        "--auto-hebrew",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Auto-generate Hebrew variants for Latin-script names",
    )
    parser.add_argument(
        "--corpus-scope",
        choices=("torah", "tanakh"),
        default="torah",
        help="Search scope: Torah/Chumash only (default) or full Tanakh",
    )
    args = parser.parse_args()

    resolved_query, data, query_variants = _resolve_query_with_variants(
        args.name,
        auto_hebrew=args.auto_hebrew,
        book=args.book,
        max_results=args.max_results,
        els_max_skip=args.els_max_skip,
        corpus_scope=args.corpus_scope,
    )
    summary = _build_summary(data)
    word_breakdown = _summarize_word_breakdown(
        query=resolved_query,
        max_results=min(args.max_results, 10),
        els_max_skip=args.els_max_skip,
        book=args.book,
        corpus_scope=args.corpus_scope,
    ) if args.word_breakdown else {"enabled": False}

    glm_audit = None
    if args.glm_audit:
        try:
            glm_audit = _ask_glm_for_audit(
                data=data,
                glm_model=args.glm_model,
                glm_api_key=args.glm_api_key,
                glm_base_url=args.glm_base_url,
                glm_allow_fallback=not args.glm_strict_model,
            )
        except GLMClientError as exc:
            glm_audit = {"error": str(exc)}

    if args.json:
        payload = {
            "query_input": args.name,
            "query_resolved": resolved_query,
            "query_variants": query_variants,
            "summary": summary,
            "results": data.get("results", []),
            "word_breakdown": word_breakdown,
            "glm_audit": glm_audit,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if resolved_query != args.name:
        print(f"Input query: {args.name}")
        print(f"Resolved query: {resolved_query}")
        if query_variants:
            print("Variant candidates:")
            for row in query_variants[:8]:
                print(
                    "  - "
                    f"{row['variant']}  "
                    f"(high+medium={row['high_medium']}, verified={row['verified']}, total={row['total']})"
                )

    _print_human(data, summary, args.display_results)
    if word_breakdown.get("enabled"):
        print("\nWord breakdown:")
        print(f"  overall: {word_breakdown['overall']}")
        for word, details in word_breakdown["words"].items():
            print(
                f"  - {word}: best={details['best_label']}({details['best_score']}) "
                f"hits={details['total_results']}"
            )
            top = details.get("top_result")
            if top:
                loc = top.get("location", {})
                print(
                    "      top="
                    f"{top.get('method')} {loc.get('book')} "
                    f"{loc.get('chapter')}:{loc.get('verse')}"
                )
    if glm_audit:
        print("\nGLM audit:")
        if "error" in glm_audit:
            print(f"  ERROR: {glm_audit['error']}")
        else:
            print(
                f"  model: {glm_audit['model']} "
                f"(requested {glm_audit.get('model_requested')})"
            )
            if glm_audit.get("base_url"):
                print(f"  endpoint: {glm_audit['base_url']}")
            print(glm_audit["content"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
