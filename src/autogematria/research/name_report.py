"""Unified name report builder that integrates all analysis modules.

This is the top-level orchestrator: given a raw name input (Hebrew or English),
it parses it, generates variants, runs text search, gematria search, kabbalistic
analysis, and cross-comparisons, then packages everything for the HTML renderer.
"""

from __future__ import annotations

from typing import Any

from hebrew import Hebrew
from hebrew.gematria import GematriaTypes

from autogematria.normalize import FinalsPolicy, extract_letters, normalize_hebrew
from autogematria.research.cross_compare import build_cross_comparison_report
from autogematria.research.kabbalistic import full_kabbalistic_analysis
from autogematria.search.base import SearchResult
from autogematria.search.corpus_index import MIDDLE_LETTER_POLICY
from autogematria.search.unified import UnifiedSearch, UnifiedSearchConfig
from autogematria.tools.name_parser import ParsedName, parse_name
from autogematria.tools.name_variants import contains_hebrew, generate_hebrew_variants


_TEXT_SEARCH_METHODS = {
    "ROSHEI_TEVOT": "roshei_tevot",
    "SOFEI_TEVOT": "sofei_tevot",
    "EMTZAEI_TEVOT": "emtzaei_tevot",
}


def _result_to_dict(r: SearchResult) -> dict[str, Any]:
    return {
        "found_text": r.found_text,
        "book": r.location_start.book,
        "chapter": r.location_start.chapter,
        "verse": r.location_start.verse,
        "context": r.context or "",
        "word_span": int(r.params.get("word_span") or 0),
        "start_word_index": int(r.params.get("start_word_index") or 0),
        "experimental": bool(r.params.get("experimental")),
        "middle_policy": r.params.get("middle_policy"),
    }


def _run_acrostic_search(
    searcher: UnifiedSearch, query: str
) -> dict[str, list[dict[str, Any]]]:
    empty = {"roshei_tevot": [], "sofei_tevot": [], "emtzaei_tevot": []}
    query_norm = extract_letters(query, FinalsPolicy.NORMALIZE)
    if len(query_norm) < 2:
        return empty
    buckets: dict[str, list[dict[str, Any]]] = {
        "roshei_tevot": [],
        "sofei_tevot": [],
        "emtzaei_tevot": [],
    }
    for r in searcher.search(query):
        key = _TEXT_SEARCH_METHODS.get(r.method)
        if key is None:
            continue
        if len(buckets[key]) >= 10:
            continue
        buckets[key].append(_result_to_dict(r))
    return buckets


def _to_hebrew(text: str) -> str:
    """Ensure text is Hebrew; transliterate if needed."""
    if contains_hebrew(text):
        return normalize_hebrew(text, FinalsPolicy.PRESERVE)
    variants = generate_hebrew_variants(text, max_variants=1)
    return variants[0] if variants else text


def _gematria_value(text: str) -> int:
    clean = normalize_hebrew(text, FinalsPolicy.PRESERVE).replace(" ", "")
    if not clean:
        return 0
    return int(Hebrew(clean).gematria(GematriaTypes.MISPAR_HECHRACHI))


def _build_search_hebrew_name(
    parsed: ParsedName,
    hebrew_components: list[tuple[str, str]],
) -> str:
    """Restore relationship words for textual search, but not arithmetic.

    Gematria totals intentionally combine only meaningful name components.
    Text search needs the patronymic syntax, however: ``דוד בן ישי`` is a
    plausible corpus phrase while the arithmetic form ``דוד ישי`` is not the
    phrase a reader supplied.
    """
    parts: list[str] = []
    for text, role in hebrew_components:
        if role == "father_name" and parsed.patronymic_type:
            connector = "בת" if parsed.patronymic_type in {"bat", "בת"} else "בן"
            parts.append(connector)
        if role == "mother_name":
            parts.append(f"ו{text}")
        else:
            parts.append(text)
    return " ".join(parts)


def build_name_report(raw_input: str) -> dict[str, Any]:
    """Build a comprehensive name report from any input format.

    Orchestrates:
      1. Name parsing (first/father/mother/surname)
      2. Hebrew variant generation
      3. Per-component kabbalistic analysis
      4. Cross-comparison gematria table
      5. Torah text search (delegated to existing pipeline)
      6. Package for HTML rendering
    """
    parsed = parse_name(raw_input)
    components = parsed.searchable_components

    hebrew_components: list[tuple[str, str]] = []
    for text, role in components:
        heb = _to_hebrew(text)
        hebrew_components.append((heb, role))

    kabbalistic_per_component: dict[str, dict[str, Any]] = {}
    for heb_text, role in hebrew_components:
        key = f"{heb_text}|{role}"
        kabbalistic_per_component[key] = full_kabbalistic_analysis(heb_text)

    full_name_heb = " ".join(h for h, _ in hebrew_components)
    search_name_heb = _build_search_hebrew_name(parsed, hebrew_components)
    kabbalistic_full = full_kabbalistic_analysis(full_name_heb)

    cross_comparison = build_cross_comparison_report(hebrew_components)

    search_cfg = UnifiedSearchConfig(
        enable_substring=False,
        enable_roshei=True,
        enable_sofei=True,
        enable_emtzaei=True,
        enable_els=False,
        max_results_per_method=10,
        corpus_scope="tanakh",
    )
    searcher = UnifiedSearch(search_cfg)

    by_component: dict[str, dict[str, list[dict[str, Any]]]] = {}
    totals = {"roshei_tevot": 0, "sofei_tevot": 0, "emtzaei_tevot": 0}
    for heb_text, role in hebrew_components:
        key = f"{heb_text}|{role}"
        comp_results = _run_acrostic_search(searcher, heb_text)
        by_component[key] = comp_results
        for k in totals:
            totals[k] += len(comp_results[k])

    full_name_query = full_name_heb.replace(" ", "")
    full_name_results = _run_acrostic_search(searcher, full_name_query)
    for k in totals:
        totals[k] += len(full_name_results[k])

    text_search_matches = {
        "by_component": by_component,
        "full_name": full_name_results,
        "totals": totals,
        "experimental_methods": {
            "emtzaei_tevot": {
                "experimental": True,
                "eligible_for_verdict": False,
                "middle_policy": MIDDLE_LETTER_POLICY,
            }
        },
    }

    report: dict[str, Any] = {
        "raw_input": raw_input,
        "parsed_name": parsed.to_dict(),
        "hebrew_components": [
            {"text": h, "role": r, "gematria": _gematria_value(h)}
            for h, r in hebrew_components
        ],
        "full_hebrew_name": full_name_heb,
        "search_hebrew_name": search_name_heb,
        "full_name_gematria": _gematria_value(full_name_heb),
        "kabbalistic_per_component": kabbalistic_per_component,
        "kabbalistic_full_name": kabbalistic_full,
        "cross_comparison": cross_comparison,
        "text_search_matches": text_search_matches,
    }

    return report
