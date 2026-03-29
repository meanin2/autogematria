"""Corpus-wide gematria search for exact-word and bounded-span matches."""

from __future__ import annotations

from dataclasses import dataclass

from hebrew import Hebrew
from hebrew.gematria import GematriaTypes

from autogematria.config import normalize_corpus_scope
from autogematria.normalize import FinalsPolicy, normalize_hebrew
from autogematria.search.base import SearchMethod, SearchResult


@dataclass(frozen=True)
class _QueryValue:
    method_name: str
    value: int
    normalized_query: str


def _resolve_method_names(methods: list[str] | None) -> list[str]:
    if not methods:
        return ["MISPAR_HECHRACHI"]
    names: list[str] = []
    for method in methods:
        gtype = getattr(GematriaTypes, method, None)
        if gtype is not None and gtype.name not in names:
            names.append(gtype.name)
    return names or ["MISPAR_HECHRACHI"]


def _query_values(query: str, methods: list[str] | None) -> list[_QueryValue]:
    clean = normalize_hebrew(query, FinalsPolicy.PRESERVE).replace(" ", "")
    if not clean:
        return []
    h = Hebrew(clean)
    values: list[_QueryValue] = []
    for method_name in _resolve_method_names(methods):
        gtype = getattr(GematriaTypes, method_name)
        values.append(
            _QueryValue(
                method_name=method_name,
                value=int(h.gematria(gtype)),
                normalized_query=clean,
            )
        )
    return values


class GematriaSearch(SearchMethod):
    """Find gematria-equivalent words and bounded contiguous spans."""

    name = "GEMATRIA"

    def search(
        self,
        query: str,
        *,
        methods: list[str] | None = None,
        book: str | None = None,
        max_results: int = 100,
        max_span_words: int = 4,
        corpus_scope: str = "tanakh",
        include_exact_words: bool = True,
        include_spans: bool = True,
    ) -> list[SearchResult]:
        values = _query_values(query, methods)
        if not values:
            return []
        scope = normalize_corpus_scope(corpus_scope)
        conn = self._connect()
        try:
            results: list[SearchResult] = []
            for query_value in values:
                if include_exact_words and len(results) < max_results:
                    results.extend(
                        self._search_exact_words(
                            conn,
                            query=query,
                            query_value=query_value,
                            book=book,
                            max_results=max_results - len(results),
                            corpus_scope=scope,
                        )
                    )
                if include_spans and len(results) < max_results:
                    results.extend(
                        self._search_spans(
                            conn,
                            query=query,
                            query_value=query_value,
                            book=book,
                            max_results=max_results - len(results),
                            max_span_words=max_span_words,
                            corpus_scope=scope,
                        )
                    )
            results.sort(
                key=lambda row: (
                    float(row.raw_score),
                    row.location_start.book,
                    row.location_start.chapter,
                    row.location_start.verse,
                )
            )
            return results[:max_results]
        finally:
            conn.close()

    def _search_exact_words(
        self,
        conn,
        *,
        query: str,
        query_value: _QueryValue,
        book: str | None,
        max_results: int,
        corpus_scope: str,
    ) -> list[SearchResult]:
        where_parts = ["gm.method_name = ?", "wg.value = ?"]
        params: list[object] = [query_value.method_name, query_value.value]
        if corpus_scope == "torah":
            where_parts.append("b.category = 'Torah'")
        if book:
            where_parts.append("b.api_name = ?")
            params.append(book)
        where_sql = " AND ".join(where_parts)

        rows = conn.execute(
            "SELECT w.word_raw, w.word_normalized, w.absolute_word_index, "
            "b.api_name, c.chapter_num, v.verse_num, v.text_raw "
            "FROM word_gematria wg "
            "JOIN gematria_methods gm ON wg.method_id = gm.method_id "
            "JOIN word_forms wf ON wg.form_id = wf.form_id "
            "JOIN words w ON w.word_normalized = wf.form_text "
            "JOIN verses v ON w.verse_id = v.verse_id "
            "JOIN chapters c ON v.chapter_id = c.chapter_id "
            "JOIN books b ON c.book_id = b.book_id "
            f"WHERE {where_sql} "
            "ORDER BY w.absolute_word_index "
            "LIMIT ?",
            params + [max_results],
        ).fetchall()

        results: list[SearchResult] = []
        for row in rows:
            loc = self._location_for_word(conn, int(row["absolute_word_index"]))
            results.append(
                SearchResult(
                    method=self.name,
                    query=query,
                    found_text=str(row["word_raw"]),
                    location_start=loc,
                    raw_score=0.22,
                    params={
                        "mode": "exact_word",
                        "gematria_method": query_value.method_name,
                        "query_value": query_value.value,
                        "matched_value": query_value.value,
                        "start_word_index": int(row["absolute_word_index"]),
                        "end_word_index": int(row["absolute_word_index"]),
                        "word_span": 1,
                    },
                    context=str(row["text_raw"]),
                )
            )
        return results

    def _search_spans(
        self,
        conn,
        *,
        query: str,
        query_value: _QueryValue,
        book: str | None,
        max_results: int,
        max_span_words: int,
        corpus_scope: str,
    ) -> list[SearchResult]:
        where_parts: list[str] = []
        params: list[object] = []
        if corpus_scope == "torah":
            where_parts.append("b.category = 'Torah'")
        if book:
            where_parts.append("b.api_name = ?")
            params.append(book)
        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

        verse_rows = conn.execute(
            "SELECT v.verse_id, v.text_raw, b.api_name, c.chapter_num, v.verse_num "
            "FROM verses v "
            "JOIN chapters c ON v.chapter_id = c.chapter_id "
            "JOIN books b ON c.book_id = b.book_id "
            f"{where_sql} "
            "ORDER BY v.verse_id",
            params,
        ).fetchall()

        results: list[SearchResult] = []
        gtype = getattr(GematriaTypes, query_value.method_name)
        for verse in verse_rows:
            if len(results) >= max_results:
                break
            words = conn.execute(
                "SELECT word_raw, absolute_word_index "
                "FROM words WHERE verse_id = ? ORDER BY word_index_in_verse",
                (int(verse["verse_id"]),),
            ).fetchall()
            if len(words) < 2:
                continue
            word_values: list[int] = []
            for word in words:
                value = int(Hebrew(str(word["word_raw"])).gematria(gtype))
                word_values.append(value)

            for start in range(len(words)):
                running = 0
                for end in range(start, min(len(words), start + max_span_words)):
                    running += word_values[end]
                    span_len = end - start + 1
                    if span_len == 1:
                        continue
                    if running != query_value.value:
                        continue
                    start_idx = int(words[start]["absolute_word_index"])
                    end_idx = int(words[end]["absolute_word_index"])
                    loc_start = self._location_for_word(conn, start_idx)
                    loc_end = self._location_for_word(conn, end_idx)
                    matched_words = [str(word["word_raw"]) for word in words[start : end + 1]]
                    results.append(
                        SearchResult(
                            method=self.name,
                            query=query,
                            found_text=" ".join(matched_words),
                            location_start=loc_start,
                            location_end=loc_end,
                            raw_score=0.4 + min(0.2, (span_len - 2) * 0.05),
                            params={
                                "mode": "contiguous_span",
                                "gematria_method": query_value.method_name,
                                "query_value": query_value.value,
                                "matched_value": running,
                                "start_word_index": start_idx,
                                "end_word_index": end_idx,
                                "word_span": span_len,
                                "matched_words": matched_words,
                            },
                            context=str(verse["text_raw"]),
                        )
                    )
                    if len(results) >= max_results:
                        break
                if len(results) >= max_results:
                    break
        return results
