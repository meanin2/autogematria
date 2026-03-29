"""Tests for research variant generation."""

from autogematria.research.variants import generate_name_variants


def test_generate_name_variants_for_latin_input_is_bounded_and_deterministic():
    variant_set = generate_name_variants("moshe gindi", max_variants=6)
    texts = [variant.text for variant in variant_set.variants]

    assert texts[0] == "משה גינדי"
    assert len(texts) <= 6
    assert len(texts) == len(set(texts))
    assert "משה גנדי" in texts


def test_generate_name_variants_includes_token_forms_for_hebrew_input():
    variant_set = generate_name_variants("משה גינדי", max_variants=6)
    texts = [variant.text for variant in variant_set.variants]

    assert texts[0] == "משה גינדי"
    assert "משה" in texts
    assert "גינדי" in texts
