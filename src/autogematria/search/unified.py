"""Unified search: fan-out across all methods, merge, and rank."""

from __future__ import annotations

from dataclasses import dataclass

from autogematria.config import DB_PATH, normalize_corpus_scope
from autogematria.search.base import SearchResult
from autogematria.search.els import ELSSearch
from autogematria.search.roshei_tevot import RosheiTevotSearch, SofeiTevotSearch
from autogematria.search.substring import SubstringSearch


@dataclass
class UnifiedSearchConfig:
    """Controls which methods are enabled and their bounds."""
    enable_substring: bool = True
    enable_roshei: bool = True
    enable_sofei: bool = True
    enable_els: bool = True
    els_min_skip: int = 1
    els_max_skip: int = 1000
    els_direction: str = "both"
    els_use_fast: bool = True
    max_results_per_method: int = 50
    book: str | None = None
    corpus_scope: str = "torah"  # "torah" (default) or "tanakh"


class UnifiedSearch:
    """Run all enabled search methods and merge results."""

    def __init__(self, config: UnifiedSearchConfig | None = None, db_path=DB_PATH):
        self.config = config or UnifiedSearchConfig()
        self.db_path = db_path

    def search(self, query: str, substring_cross_word: bool = True) -> list[SearchResult]:
        """Run all enabled methods, return merged results sorted by relevance."""
        results: list[SearchResult] = []
        cfg = self.config
        max_per = cfg.max_results_per_method
        scope = normalize_corpus_scope(cfg.corpus_scope)

        if cfg.enable_substring:
            sub = SubstringSearch(self.db_path)
            results.extend(
                sub.search(
                    query,
                    max_results=max_per,
                    book=cfg.book,
                    cross_word=substring_cross_word,
                    corpus_scope=scope,
                )
            )

        if cfg.enable_roshei:
            rt = RosheiTevotSearch(self.db_path)
            results.extend(rt.search(query, max_results=max_per, book=cfg.book, corpus_scope=scope))

        if cfg.enable_sofei:
            st = SofeiTevotSearch(self.db_path)
            results.extend(st.search(query, max_results=max_per, book=cfg.book, corpus_scope=scope))

        if cfg.enable_els:
            els = ELSSearch(self.db_path)
            if cfg.els_use_fast:
                results.extend(els.search_fast(
                    query, min_skip=cfg.els_min_skip, max_skip=cfg.els_max_skip,
                    book=cfg.book, max_results=max_per,
                    direction=cfg.els_direction,
                    corpus_scope=scope,
                ))
            else:
                results.extend(els.search(
                    query, min_skip=cfg.els_min_skip, max_skip=cfg.els_max_skip,
                    book=cfg.book, max_results=max_per,
                    direction=cfg.els_direction,
                    corpus_scope=scope,
                ))

        # Sort: substring first (score 0), then roshei/sofei, then ELS by skip distance
        results.sort(key=_sort_key)
        return results


def _sort_key(r: SearchResult) -> tuple[int, float]:
    """Sort order: method priority, then raw_score."""
    priority = {"SUBSTRING": 0, "ROSHEI_TEVOT": 1, "SOFEI_TEVOT": 2, "ELS": 3}
    return (priority.get(r.method, 99), r.raw_score)


def main():
    """CLI entry point for quick searches."""
    import argparse

    parser = argparse.ArgumentParser(prog="ag-search")
    parser.add_argument("query", help="Hebrew query text")
    parser.add_argument("book", nargs="?", default=None, help="Optional specific book filter")
    parser.add_argument(
        "--corpus-scope",
        choices=("torah", "tanakh"),
        default="torah",
        help="Search scope: Torah-only (default) or full Tanakh",
    )
    args = parser.parse_args()

    cfg = UnifiedSearchConfig(
        book=args.book,
        els_max_skip=500,
        corpus_scope=args.corpus_scope,
    )
    searcher = UnifiedSearch(cfg)
    results = searcher.search(args.query)

    print(f"\nFound {len(results)} results for '{args.query}' in scope '{args.corpus_scope}':\n")
    for i, r in enumerate(results[:30], 1):
        print(f"  {i:3}. [{r.method}] {r.found_text}")
        print(f"       {r.location_start.book} {r.location_start.chapter}:{r.location_start.verse}")
        if r.params:
            print(f"       params: {r.params}")
        if r.context:
            ctx = r.context[:80] + "..." if len(r.context) > 80 else r.context
            print(f"       context: {ctx}")
        print()
