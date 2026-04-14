"""Tests for the gematria reverse lookup module."""

import pytest

from autogematria.search.gematria_reverse import (
    REPORT_METHODS,
    REPORT_METHOD_DISPLAY,
    build_name_gematria_graph,
    reverse_lookup,
    reverse_lookup_all_methods,
    word_gematria_profile,
)


class TestReverseLookup:
    def test_finds_moshe(self):
        results = reverse_lookup(345, method="MISPAR_HECHRACHI", max_results=10)
        words = [r["word"] for r in results]
        assert "משה" in words

    def test_returns_frequency(self):
        results = reverse_lookup(345, method="MISPAR_HECHRACHI", max_results=5)
        assert all(r["frequency"] > 0 for r in results)

    def test_respects_max_results(self):
        results = reverse_lookup(345, method="MISPAR_HECHRACHI", max_results=3)
        assert len(results) <= 3

    def test_different_methods(self):
        for method in REPORT_METHODS:
            results = reverse_lookup(10, method=method, max_results=5)
            assert isinstance(results, list)
            for r in results:
                assert r["method"] == method

    def test_returns_empty_for_huge_value(self):
        results = reverse_lookup(999999999, method="MISPAR_HECHRACHI")
        assert results == []


class TestReverseLookupAllMethods:
    def test_returns_all_report_methods(self):
        results = reverse_lookup_all_methods(345)
        assert set(results.keys()) == set(REPORT_METHODS)

    def test_custom_method_list(self):
        results = reverse_lookup_all_methods(
            345, methods=["MISPAR_HECHRACHI", "ATBASH"]
        )
        assert set(results.keys()) == {"MISPAR_HECHRACHI", "ATBASH"}


class TestWordGematriaProfile:
    def test_moshe_profile(self):
        prof = word_gematria_profile("משה")
        assert prof["word"] == "משה"
        assert prof["values"]["MISPAR_HECHRACHI"] == 345

    def test_all_report_methods_present(self):
        prof = word_gematria_profile("אברהם")
        for method in REPORT_METHODS:
            assert method in prof["values"]

    def test_empty_input(self):
        prof = word_gematria_profile("")
        assert prof["values"] == {}


class TestBuildNameGraph:
    def test_basic_graph_structure(self):
        graph = build_name_gematria_graph([
            ("משה", "first_name"),
            ("גינדי", "surname"),
        ])
        assert "nodes" in graph
        assert "edges" in graph
        assert "summary" in graph
        assert graph["summary"]["name_components"] == 2

    def test_single_component(self):
        graph = build_name_gematria_graph([("משה", "first_name")])
        assert graph["summary"]["name_components"] == 1

    def test_torah_words_found(self):
        graph = build_name_gematria_graph([("משה", "first_name")])
        assert graph["summary"]["torah_words"] > 0

    def test_node_types(self):
        graph = build_name_gematria_graph([
            ("דוד", "first_name"),
            ("אברהם", "father_name"),
        ])
        types = {n["type"] for n in graph["nodes"]}
        assert "name_component" in types

    def test_edges_have_required_fields(self):
        graph = build_name_gematria_graph([
            ("משה", "first_name"),
            ("אהרן", "father_name"),
        ])
        for edge in graph["edges"]:
            assert "source" in edge
            assert "target" in edge
            assert "type" in edge


class TestConstants:
    def test_report_methods_count(self):
        assert len(REPORT_METHODS) == 6

    def test_display_names(self):
        assert len(REPORT_METHOD_DISPLAY) == 6
        for method in REPORT_METHODS:
            assert method in REPORT_METHOD_DISPLAY
