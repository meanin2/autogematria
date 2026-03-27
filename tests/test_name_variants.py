"""Tests for Latin->Hebrew query variant generation."""

from autogematria.tools.name_variants import contains_hebrew, generate_hebrew_variants


def test_contains_hebrew():
    assert contains_hebrew("משה")
    assert not contains_hebrew("moshe")


def test_generate_known_name_variant_first():
    variants = generate_hebrew_variants("moshe gindi")
    assert variants
    assert variants[0] == "משה גינדי"
    assert "משה גינדי" in variants


def test_generate_elisa_variant_prefers_common_hebrew_forms():
    variants = generate_hebrew_variants("dorit elisa gindi")
    assert variants
    assert variants[0] == "דורית אליסה גינדי"
    assert "דורית אליזה גינדי" in variants


def test_generate_gandi_variant_prefers_known_surname_spelling():
    variants = generate_hebrew_variants("moshe gandi")
    assert variants
    assert variants[0] == "משה גנדי"
    assert "משה גינדי" in variants


def test_generate_gandy_variant_prefers_known_surname_spelling():
    variants = generate_hebrew_variants("moshe gandy")
    assert variants
    assert variants[0] == "משה גנדי"
    assert "משה גינדי" in variants


def test_generate_removes_stopwords():
    variants = generate_hebrew_variants("dorit alisa gindi maiden name ergas")
    assert variants
    assert variants[0] == "דורית אליסה גינדי ארגס"


def test_generate_max_variants_cap():
    variants = generate_hebrew_variants("a b c d e f g h i", max_variants=5)
    assert len(variants) <= 5
