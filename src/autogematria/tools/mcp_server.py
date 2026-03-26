"""MCP server exposing AutoGematria tools for LLM agents."""

from __future__ import annotations

from fastmcp import FastMCP

from autogematria.tools.tool_functions import (
    find_name_in_torah,
    gematria_lookup,
    gematria_connections,
    get_verse,
    els_detail,
    corpus_stats,
)

mcp = FastMCP(
    "AutoGematria",
    description="Torah name-finding and gematria research tools. "
    "Search for Hebrew names in the Tanakh using ELS, roshei/sofei tevot, "
    "substring matching, and gematria equivalences.",
)


@mcp.tool()
def search_name(
    name: str,
    methods: list[str] | None = None,
    book: str | None = None,
    max_results: int = 20,
    els_max_skip: int = 500,
    include_verification: bool = True,
    corpus_scope: str = "torah",
) -> dict:
    """Search for a Hebrew name across the Tanakh using all available methods.

    Methods: substring (direct text match), roshei_tevot (first letters of consecutive
    words), sofei_tevot (last letters), els (equidistant letter sequences).

    Args:
        name: Hebrew name to search for (e.g. "משה", "אברהם")
        methods: Optional subset of ["substring", "roshei_tevot", "sofei_tevot", "els"]
        book: Optional book filter (e.g. "Genesis", "Exodus", "Psalms")
        max_results: Maximum results to return (default 20)
        els_max_skip: Maximum ELS skip distance (default 500)
        include_verification: Include deterministic proof payload per result
        corpus_scope: "torah" (default) or "tanakh"
    """
    return find_name_in_torah(
        name=name,
        methods=methods,
        book=book,
        max_results=max_results,
        els_max_skip=els_max_skip,
        include_verification=include_verification,
        corpus_scope=corpus_scope,
    )


@mcp.tool()
def lookup_gematria(
    word: str,
    method: str = "MISPAR_HECHRACHI",
    max_equivalents: int = 20,
) -> dict:
    """Compute gematria value of a Hebrew word and find all Tanakh words with the same value.

    Available methods: MISPAR_HECHRACHI (standard), MISPAR_GADOL, MISPAR_KATAN,
    MISPAR_SIDURI, ATBASH, ALBAM, MISPAR_PERATI, MISPAR_MESHULASH, and 14 more.

    Args:
        word: Hebrew word (e.g. "משה", "אלהים")
        method: Gematria calculation method (default: MISPAR_HECHRACHI/standard)
        max_equivalents: Max equivalent words to return
    """
    return gematria_lookup(word, method, max_equivalents)


@mcp.tool()
def explore_gematria_connections(
    word: str,
    method: str = "MISPAR_HECHRACHI",
    max_related: int = 20,
) -> dict:
    """Get graph-ranked, source-backed gematria connections for a word/value cluster."""
    return gematria_connections(word, method, max_related)


@mcp.tool()
def read_verse(
    book: str,
    chapter: int,
    verse: int,
) -> dict:
    """Retrieve a specific Tanakh verse with words, gematria values, and letter indices.

    Args:
        book: Book name (e.g. "Genesis", "Exodus", "Isaiah", "Psalms")
        chapter: Chapter number
        verse: Verse number
    """
    return get_verse(book, chapter, verse)


@mcp.tool()
def inspect_els(
    query: str,
    skip: int,
    start_index: int,
) -> dict:
    """Get detailed letter-by-letter breakdown of a specific ELS occurrence.

    Use this after search_name returns an ELS result to see exactly which
    letters form the sequence and which verses they span.

    Args:
        query: The Hebrew text found (e.g. "תורה")
        skip: The skip distance between letters
        start_index: Absolute letter index where the ELS starts
    """
    return els_detail(query, skip, start_index)


@mcp.tool()
def get_corpus_stats() -> dict:
    """Get summary statistics about the Tanakh corpus.

    Returns total counts (books, chapters, verses, words, letters),
    unique word forms, gematria method count, and per-book breakdown.
    """
    return corpus_stats()


def main():
    """Run the MCP server."""
    mcp.run(transport="sse", host="127.0.0.1", port=8087)


if __name__ == "__main__":
    main()
