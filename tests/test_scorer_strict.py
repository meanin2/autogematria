"""Unit tests for strict scorer behavior."""

from autogematria.autoresearch.ground_truth import GroundTruthEntry
from autogematria.autoresearch.scorer import evaluate_entry, score
from autogematria.search.base import Location, SearchResult


def _entry(
    method: str,
    *,
    book: str | None = None,
    chapter: int | None = None,
    verse: int | None = None,
    params: dict | None = None,
    is_negative: bool = False,
) -> GroundTruthEntry:
    return GroundTruthEntry(
        name="משה",
        english="Moses",
        method=method,
        book=book,
        chapter=chapter,
        verse=verse,
        params=params or {},
        source="test",
        difficulty="easy",
        split="train",
        is_negative=is_negative,
    )


def _result(method: str, *, book: str = "Genesis", chapter: int = 1, verse: int = 1, params=None):
    return SearchResult(
        method=method,
        query="משה",
        found_text="משה",
        location_start=Location(book, chapter, verse),
        params=params or {},
    )


def test_evaluate_entry_does_not_accept_wrong_method():
    entry = _entry("substring", book="Genesis", chapter=1, verse=1)
    results = [_result("ELS", book="Genesis", chapter=1, verse=1, params={"skip": 5})]
    verdict = evaluate_entry(entry, results)
    assert verdict["found"] is False


def test_evaluate_entry_checks_chapter_and_verse():
    entry = _entry("substring", book="Genesis", chapter=2, verse=3)
    results = [_result("SUBSTRING", book="Genesis", chapter=2, verse=4)]
    verdict = evaluate_entry(entry, results)
    assert verdict["found"] is False


def test_evaluate_entry_els_skip_range_accepts_backward_skip():
    entry = _entry(
        "els",
        book="Genesis",
        chapter=1,
        verse=1,
        params={"skip_range": [40, 60], "direction": "forward_reversed"},
    )
    results = [_result("ELS", params={"skip": -50, "start_index": 5})]
    verdict = evaluate_entry(entry, results)
    assert verdict["found"] is True


def test_score_validates_gematria_entries_with_lookup():
    entry = GroundTruthEntry(
        name="משה",
        english="Moses",
        method="gematria",
        book=None,
        chapter=None,
        verse=None,
        params={"value": 345, "method": "MISPAR_HECHRACHI", "equivalents": ["השם"]},
        source="test",
        difficulty="easy",
        split="train",
    )

    def fake_search(_name: str, **_kwargs):
        return []

    def fake_gematria(_name: str, method: str, max_equivalents: int):
        assert method == "MISPAR_HECHRACHI"
        assert max_equivalents >= 100
        return {
            "value": 345,
            "equivalents": [{"word": "השם"}, {"word": "שמה"}],
        }

    sc = score([entry], fake_search, gematria_func=fake_gematria)
    assert sc.found_positives == 1
    assert sc.recall == 1.0
    assert sc.mean_reciprocal_rank == 1.0


def test_negative_entries_are_evaluated_by_their_method():
    negative = _entry("els", is_negative=True, params={"skip_range": [1, 100]})

    def search_returns_only_substring(_name: str, **_kwargs):
        return [_result("SUBSTRING")]

    sc = score([negative], search_returns_only_substring)
    assert sc.total_negatives == 1
    assert sc.found_negatives == 0
    assert sc.false_positive_rate == 0.0


def test_score_passes_method_specific_kwargs():
    entry = _entry(
        "els",
        book="Genesis",
        chapter=1,
        verse=1,
        params={"skip_range": [40, 60], "direction": "forward_reversed"},
    )
    seen_kwargs = {}

    def fake_search(_name: str, **kwargs):
        seen_kwargs.update(kwargs)
        return [_result("ELS", params={"skip": -50, "start_index": 5})]

    sc = score([entry], fake_search, top_k=20)
    assert sc.found_positives == 1
    assert seen_kwargs["only_method"] == "els"
    assert seen_kwargs["book"] == "Genesis"
    assert seen_kwargs["els_min_skip"] == 40
    assert seen_kwargs["els_max_skip"] == 60
    assert seen_kwargs["els_direction"] == "backward"
