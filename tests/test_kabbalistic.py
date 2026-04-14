"""Tests for kabbalistic analysis module."""

from autogematria.research.kabbalistic import (
    ATBASH_MAP,
    LETTER_MEANINGS,
    MILUI_SPELLINGS,
    analyze_letter_meanings,
    compute_atbash,
    compute_milui,
    four_worlds_breakdown,
    full_kabbalistic_analysis,
    sefirah_for_value,
)


class TestLetterMeanings:
    def test_all_22_letters_covered(self):
        assert len(LETTER_MEANINGS) == 22

    def test_each_letter_has_required_fields(self):
        for letter, info in LETTER_MEANINGS.items():
            assert "name" in info
            assert "value" in info
            assert "meaning" in info
            assert "sefirah" in info

    def test_analyze_moshe(self):
        result = analyze_letter_meanings("משה")
        assert len(result) == 3
        assert result[0]["letter"] == "מ"
        assert result[1]["letter"] == "ש"
        assert result[2]["letter"] == "ה"


class TestMilui:
    def test_all_22_letters_have_milui(self):
        assert len(MILUI_SPELLINGS) == 22

    def test_milui_aleph(self):
        result = compute_milui("א")
        assert result["full_milui_text"] == "אלף"
        assert result["hidden_text"] == "לף"

    def test_milui_moshe(self):
        result = compute_milui("משה")
        assert result["letters"] == ["מ", "ש", "ה"]
        assert len(result["spelled_out"]) == 3
        assert result["milui_value"] > 0
        assert result["hidden_value"] > 0

    def test_milui_breakdown(self):
        result = compute_milui("אב")
        bd = result["breakdown"]
        assert len(bd) == 2
        assert bd[0]["letter"] == "א"
        assert bd[0]["milui"] == "אלף"


class TestAtBash:
    def test_atbash_map_is_involution(self):
        for letter, mapped in ATBASH_MAP.items():
            assert ATBASH_MAP[mapped] == letter, f"AtBash({letter})={mapped} but AtBash({mapped})={ATBASH_MAP[mapped]}"

    def test_atbash_aleph_is_tav(self):
        assert ATBASH_MAP["א"] == "ת"
        assert ATBASH_MAP["ת"] == "א"

    def test_atbash_bet_is_shin(self):
        assert ATBASH_MAP["ב"] == "ש"
        assert ATBASH_MAP["ש"] == "ב"

    def test_atbash_computation(self):
        result = compute_atbash("משה")
        assert result["atbash_text"] != "משה"
        assert result["original_value"] == 345
        assert result["atbash_value"] > 0
        assert result["sum_with_original"] == result["original_value"] + result["atbash_value"]

    def test_atbash_sheshach_is_bavel(self):
        """The classical AtBash example from Jeremiah 25:26."""
        result = compute_atbash("ששך")
        assert result["atbash_text"] == "בבל"


class TestSefirah:
    def test_value_1_is_keter(self):
        assert sefirah_for_value(1)["sefirah"] == "Keter"

    def test_value_10_is_malchut(self):
        assert sefirah_for_value(10)["sefirah"] == "Malchut"

    def test_reduction(self):
        result = sefirah_for_value(345)
        assert result["reduced_to"] == 3
        assert result["sefirah"] == "Binah"


class TestFourWorlds:
    def test_basic_breakdown(self):
        result = four_worlds_breakdown("אברהם")
        assert result["total_letters"] == 5
        worlds = result["worlds"]
        assert len(worlds) == 4
        assert worlds[0]["world"] == "Atzilut"
        all_letters = []
        for w in worlds:
            all_letters.extend(w["letters"])
        assert len(all_letters) == 5

    def test_short_name(self):
        result = four_worlds_breakdown("נח")
        assert result["total_letters"] == 2

    def test_no_hebrew(self):
        result = four_worlds_breakdown("abc")
        assert "error" in result


class TestFullAnalysis:
    def test_full_analysis_moshe(self):
        result = full_kabbalistic_analysis("משה")
        assert result["standard_gematria"] == 345
        assert result["letter_count"] == 3
        assert "letter_meanings" in result
        assert "milui" in result
        assert "atbash" in result
        assert "sefirah" in result
        assert "four_worlds" in result

    def test_full_analysis_avraham(self):
        result = full_kabbalistic_analysis("אברהם")
        assert result["standard_gematria"] == 248
        assert result["letter_count"] == 5

    def test_full_analysis_empty(self):
        result = full_kabbalistic_analysis("abc")
        assert "error" in result
