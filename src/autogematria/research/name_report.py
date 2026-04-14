"""Unified name report builder that integrates all analysis modules.

This is the top-level orchestrator: given a raw name input (Hebrew or English),
it parses it, generates variants, runs text search, gematria search, kabbalistic
analysis, and cross-comparisons, then packages everything for the HTML renderer.
"""

from __future__ import annotations

from typing import Any

from hebrew import Hebrew
from hebrew.gematria import GematriaTypes

from autogematria.normalize import FinalsPolicy, normalize_hebrew
from autogematria.research.cross_compare import build_cross_comparison_report
from autogematria.research.kabbalistic import full_kabbalistic_analysis
from autogematria.tools.name_parser import ParsedName, parse_name
from autogematria.tools.name_variants import contains_hebrew, generate_hebrew_variants


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
    kabbalistic_full = full_kabbalistic_analysis(full_name_heb)

    cross_comparison = build_cross_comparison_report(hebrew_components)

    report: dict[str, Any] = {
        "raw_input": raw_input,
        "parsed_name": parsed.to_dict(),
        "hebrew_components": [
            {"text": h, "role": r, "gematria": _gematria_value(h)}
            for h, r in hebrew_components
        ],
        "full_hebrew_name": full_name_heb,
        "full_name_gematria": _gematria_value(full_name_heb),
        "kabbalistic_per_component": kabbalistic_per_component,
        "kabbalistic_full_name": kabbalistic_full,
        "cross_comparison": cross_comparison,
    }

    return report
