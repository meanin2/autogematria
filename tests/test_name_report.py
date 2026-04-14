"""Tests for the unified name report builder."""

from autogematria.research.name_report import build_name_report


class TestNameReport:
    def test_hebrew_name(self):
        report = build_name_report("משה גינדי")
        assert report["raw_input"] == "משה גינדי"
        assert report["full_hebrew_name"] == "משה גינדי"
        assert report["full_name_gematria"] > 0
        assert len(report["hebrew_components"]) == 2

    def test_english_name_transliterated(self):
        report = build_name_report("moshe gindi")
        assert "משה" in report["full_hebrew_name"]
        assert len(report["hebrew_components"]) == 2

    def test_patronymic_name(self):
        report = build_name_report("moshe ben yitzchak gindi")
        comps = report["hebrew_components"]
        roles = {c["role"] for c in comps}
        assert "first_name" in roles
        assert "father_name" in roles
        assert "surname" in roles

    def test_kabbalistic_present(self):
        report = build_name_report("אברהם")
        kab = report["kabbalistic_full_name"]
        assert kab["standard_gematria"] == 248
        assert "letter_meanings" in kab
        assert "milui" in kab
        assert "atbash" in kab

    def test_cross_comparison_present(self):
        report = build_name_report("דוד כהן")
        cc = report["cross_comparison"]
        assert "gematria_table" in cc
        assert "cross_matches" in cc
        assert "torah_word_matches" in cc

    def test_father_mother_name(self):
        report = build_name_report("שרה בת אברהם ורבקה")
        parsed = report["parsed_name"]
        assert parsed["first_name"] == "שרה"
        assert parsed["father_name"] == "אברהם"
        assert parsed["mother_name"] == "רבקה"

    def test_realistic_names(self):
        names = [
            "Yehuda ben Shimon",
            "Rivka bat Yitzchak",
            "אליהו הנביא",
            "Daniel Friedman",
        ]
        for name in names:
            report = build_name_report(name)
            assert report["full_name_gematria"] >= 0
            assert len(report["hebrew_components"]) >= 1
