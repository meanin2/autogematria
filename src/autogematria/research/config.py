"""Configuration defaults for bounded research runs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchConfig:
    """Controls breadth and budgets for a research run."""

    max_variants: int = 16
    max_full_name_variants: int = 8
    max_token_variants_per_token: int = 4
    max_tasks: int = 80
    text_methods: tuple[str, ...] = ("substring", "roshei_tevot", "sofei_tevot", "els")
    gematria_methods: tuple[str, ...] = (
        "MISPAR_HECHRACHI",
        "MISPAR_GADOL",
        "MISPAR_KATAN",
        "ATBASH",
    )
    corpus_scopes: tuple[str, ...] = ("torah", "tanakh")
    max_text_results_per_task: int = 12
    max_gematria_results_per_task: int = 12
    els_max_skip: int = 120
    els_max_skip_tanakh: int = 200
    max_gematria_span_words: int = 4
    stop_on_exact_full_name: bool = False

    @property
    def corpus_scope(self) -> str:
        return self.corpus_scopes[0]

    @property
    def include_tanakh_expansion(self) -> bool:
        return "tanakh" in self.corpus_scopes and self.corpus_scope != "tanakh"
