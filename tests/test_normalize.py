"""Tests for Hebrew normalization."""

from autogematria.normalize import (
    normalize_hebrew,
    extract_letters,
    validate_normalized,
    FinalsPolicy,
)


def test_strip_nikkud():
    # bereshit with full nikkud
    assert normalize_hebrew("בְּרֵאשִׁית") == "בראשית"


def test_strip_taamim():
    # etnachta (U+0591) and other cantillation marks
    assert normalize_hebrew("בְּרֵאשִׁ֖ית") == "בראשית"


def test_maqaf_to_space():
    assert normalize_hebrew("ויהי־אור") == "ויהי אור"


def test_finals_normalize():
    # ם at end should become מ with NORMALIZE policy
    result = normalize_hebrew("אברהם", FinalsPolicy.NORMALIZE)
    assert result == "אברהמ"


def test_finals_preserve():
    result = normalize_hebrew("אברהם", FinalsPolicy.PRESERVE)
    assert result == "אברהם"  # keeps ם


def test_already_clean():
    text = "בראשית ברא אלהים את השמים ואת הארץ"
    result = normalize_hebrew(text, FinalsPolicy.PRESERVE)
    assert result == text


def test_whitespace_collapse():
    assert normalize_hebrew("  אב   גד  ") == "אב גד"


def test_extract_letters():
    assert extract_letters("בראשית ברא") == "בראשיתברא"


def test_validate_normalized_good():
    assert validate_normalized("בראשית ברא אלהים")


def test_validate_normalized_bad():
    assert not validate_normalized("hello בראשית")


def test_all_finals():
    result = normalize_hebrew("ךםןףץ", FinalsPolicy.NORMALIZE)
    assert result == "כמנפצ"
    result = normalize_hebrew("ךםןףץ", FinalsPolicy.PRESERVE)
    assert result == "ךםןףץ"


def test_sof_pasuq_removed():
    assert normalize_hebrew("הארץ׃") == "הארצ"


def test_geresh_removed():
    assert normalize_hebrew("ה׳") == "ה"
