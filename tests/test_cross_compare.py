"""Tests for cross-comparison engine."""

import pytest

from autogematria.research.cross_compare import (
    build_cross_comparison_report,
    compute_gematria_table,
    find_cross_matches,
    find_torah_word_matches,
)


class TestGematriaTable:
    def test_single_component(self):
        table = compute_gematria_table([("משה", "first_name")])
        assert len(table["methods"]) >= 4
        assert len(table["components"]) == 1
        assert table["components"][0]["values"]["MISPAR_HECHRACHI"] == 345

    def test_multiple_components(self):
        comps = [("משה", "first_name"), ("גינדי", "surname")]
        table = compute_gematria_table(comps)
        assert len(table["components"]) >= 3  # 2 components + combined + maybe pairs

    def test_combined_row(self):
        comps = [("משה", "first_name"), ("אברהם", "father_name")]
        table = compute_gematria_table(comps)
        combined = [c for c in table["components"] if c["role"] == "combined_all"]
        assert len(combined) == 1
        assert combined[0]["values"]["MISPAR_HECHRACHI"] == 345 + 248

    def test_empty_text_skipped(self):
        table = compute_gematria_table([("", "first_name")])
        assert len(table["components"]) == 0


class TestCrossMatches:
    def test_no_matches_for_different_values(self):
        matches = find_cross_matches([("א", "first_name"), ("ב", "surname")])
        same_method = [m for m in matches if m["match_type"] == "same_method_different_name"
                       and m["component_a"]["method"] == m["component_b"]["method"] == "MISPAR_HECHRACHI"]
        assert not same_method  # א=1 != ב=2

    def test_matching_values_found(self):
        # אהבה=13 and אחד=13 under standard
        matches = find_cross_matches([("אהבה", "first_name"), ("אחד", "surname")])
        standard_matches = [
            m for m in matches
            if m["value"] == 13
            and m["component_a"]["method"] == "MISPAR_HECHRACHI"
            and m["component_b"]["method"] == "MISPAR_HECHRACHI"
        ]
        assert len(standard_matches) >= 1

    def test_cross_method_match(self):
        matches = find_cross_matches([("משה", "first_name"), ("אברהם", "father_name")])
        assert isinstance(matches, list)

    def test_interest_score_present(self):
        matches = find_cross_matches([("אהבה", "first_name"), ("אחד", "surname")])
        if matches:
            assert all("interest_score" in m for m in matches)


class TestTorahWordMatches:
    def test_finds_words_for_common_value(self):
        matches = find_torah_word_matches([("משה", "first_name")])
        key = "משה|first_name"
        assert key in matches
        words = matches[key]
        assert len(words) > 0
        assert all("word" in w and "frequency" in w for w in words)

    def test_does_not_include_self(self):
        matches = find_torah_word_matches([("משה", "first_name")])
        key = "משה|first_name"
        words = matches[key]
        from autogematria.normalize import FinalsPolicy, normalize_hebrew
        self_norm = normalize_hebrew("משה", FinalsPolicy.NORMALIZE)
        for w in words:
            assert normalize_hebrew(w["word"], FinalsPolicy.NORMALIZE) != self_norm


class TestFullReport:
    def test_report_structure(self):
        report = build_cross_comparison_report([
            ("משה", "first_name"),
            ("יצחק", "father_name"),
        ])
        assert "gematria_table" in report
        assert "cross_matches" in report
        assert "torah_word_matches" in report
        assert "summary" in report
        assert report["summary"]["components_analyzed"] == 2
