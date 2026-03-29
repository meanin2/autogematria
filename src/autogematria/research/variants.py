"""Bounded name variant generation for research runs."""

from __future__ import annotations

from typing import Any

from autogematria.normalize import FinalsPolicy, normalize_hebrew
from autogematria.research.config import ResearchConfig
from autogematria.research.schema import ResearchVariant, ResearchVariantSet
from autogematria.tools.name_variants import contains_hebrew, generate_hebrew_variants


def _dedupe_variants(items: list[ResearchVariant]) -> list[ResearchVariant]:
    seen: set[tuple[str, str, str, int | None]] = set()
    out: list[ResearchVariant] = []
    for item in items:
        key = (item.text, item.kind, item.source, item.token_index)
        if item.text and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def generate_name_variants(query: str, max_variants: int = 16) -> ResearchVariantSet:
    """Generate a bounded, deterministic variant list for a query."""
    cfg = ResearchConfig(max_variants=max_variants, max_full_name_variants=max_variants)
    payload = build_variants(query, cfg)
    return ResearchVariantSet(
        query=query,
        variants=[
            ResearchVariant(
                text=row["text"],
                source=row["source"],
                kind=row["kind"],
                token_count=int(row.get("token_count") or len(str(row["text"]).split()) or 1),
                token_index=row.get("token_index"),
            )
            for row in payload["all_variants"]
        ],
    )


def build_variants(query: str, config: ResearchConfig) -> dict[str, Any]:
    """Generate bounded full-name and token variants with provenance."""
    normalized = normalize_hebrew(query, FinalsPolicy.PRESERVE)
    normalized_letters = normalize_hebrew(query, FinalsPolicy.NORMALIZE)
    is_hebrew = contains_hebrew(query)

    full_name_variants: list[ResearchVariant] = []
    if is_hebrew:
        full_name_variants.append(
            ResearchVariant(
                text=normalized,
                kind="full_name",
                source="exact_input",
                token_count=max(1, len(normalized.split())),
            )
        )
    if is_hebrew and normalized_letters != normalized:
        full_name_variants.append(
            ResearchVariant(
                text=normalized_letters,
                kind="full_name",
                source="finals_normalized",
                token_count=max(1, len(normalized_letters.split())),
            )
        )

    if not is_hebrew:
        for text in generate_hebrew_variants(query, max_variants=config.max_full_name_variants):
            full_name_variants.append(
                ResearchVariant(
                    text=text,
                    kind="full_name",
                    source="transliteration",
                    token_count=max(1, len(text.split())),
                )
            )

    full_name_variants = _dedupe_variants(full_name_variants)[: config.max_full_name_variants]
    if not full_name_variants:
        full_name_variants.append(
            ResearchVariant(
                text=normalized,
                kind="full_name",
                source="exact_input",
                token_count=max(1, len(normalized.split())),
            )
        )

    token_variants: list[ResearchVariant] = []
    tokens = [token for token in normalized.split() if token]
    for idx, token in enumerate(tokens):
        per_token = [
            ResearchVariant(
                text=token,
                kind="token",
                source="token_exact",
                token_count=1,
                token_index=idx,
            )
        ]
        token_normalized = normalize_hebrew(token, FinalsPolicy.NORMALIZE)
        if token_normalized != token:
            per_token.append(
                ResearchVariant(
                    text=token_normalized,
                    kind="token",
                    source="token_finals_normalized",
                    token_count=1,
                    token_index=idx,
                )
            )
        token_variants.extend(_dedupe_variants(per_token)[: config.max_token_variants_per_token])

    all_variants = _dedupe_variants(full_name_variants + token_variants)[: config.max_variants]
    return {
        "query": query,
        "normalized": normalized,
        "normalized_letters": normalized_letters,
        "full_name_variants": [item.to_dict() for item in full_name_variants],
        "token_variants": [item.to_dict() for item in token_variants],
        "all_variants": [item.to_dict() for item in all_variants],
        "tokens": tokens,
    }
