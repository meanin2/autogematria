"""Tests for the structured name parser."""

from autogematria.tools.name_parser import ParsedName, parse_name


class TestBasicParsing:
    def test_single_hebrew_name(self):
        p = parse_name("משה")
        assert p.first_name == "משה"
        assert p.surname is None
        assert p.father_name is None

    def test_single_english_name(self):
        p = parse_name("avraham")
        assert p.first_name == "avraham"

    def test_first_and_surname_hebrew(self):
        p = parse_name("משה גינדי")
        assert p.first_name == "משה"
        assert p.surname == "גינדי"
        assert p.father_name is None

    def test_first_and_surname_english(self):
        p = parse_name("David Cohen")
        assert p.first_name == "David"
        assert p.surname == "Cohen"

    def test_empty_input(self):
        p = parse_name("")
        assert p.first_name == ""


class TestPatronymicParsing:
    def test_ben_english(self):
        p = parse_name("moshe ben yitzchak")
        assert p.first_name == "moshe"
        assert p.patronymic_type == "ben"
        assert p.father_name == "yitzchak"
        assert p.surname is None

    def test_bat_english(self):
        p = parse_name("sarah bat avraham")
        assert p.first_name == "sarah"
        assert p.patronymic_type == "bat"
        assert p.father_name == "avraham"

    def test_ben_hebrew(self):
        p = parse_name("יהודה בן שמעון")
        assert p.first_name == "יהודה"
        assert p.patronymic_type == "בן"
        assert p.father_name == "שמעון"

    def test_bat_hebrew(self):
        p = parse_name("שרה בת אברהם")
        assert p.first_name == "שרה"
        assert p.patronymic_type == "בת"
        assert p.father_name == "אברהם"

    def test_ben_with_surname_english(self):
        p = parse_name("moshe ben yitzchak gindi")
        assert p.first_name == "moshe"
        assert p.patronymic_type == "ben"
        assert p.father_name == "yitzchak"
        assert p.surname == "gindi"


class TestFatherMotherParsing:
    def test_father_and_mother_english(self):
        p = parse_name("moshe ben yitzchak v miriam gindi")
        assert p.first_name == "moshe"
        assert p.father_name == "yitzchak"
        assert p.mother_name == "miriam"
        assert p.surname == "gindi"

    def test_father_and_mother_hebrew(self):
        p = parse_name("שרה בת אברהם ורבקה")
        assert p.first_name == "שרה"
        assert p.father_name == "אברהם"
        assert p.mother_name == "רבקה"


class TestSearchableComponents:
    def test_components_simple(self):
        p = parse_name("משה גינדי")
        comps = p.searchable_components
        assert ("משה", "first_name") in comps
        assert ("גינדי", "surname") in comps

    def test_components_full(self):
        p = parse_name("moshe ben yitzchak v miriam gindi")
        comps = p.searchable_components
        roles = {role for _, role in comps}
        assert "first_name" in roles
        assert "father_name" in roles
        assert "mother_name" in roles
        assert "surname" in roles

    def test_all_name_tokens(self):
        p = parse_name("moshe ben yitzchak gindi")
        tokens = p.all_name_tokens
        assert "moshe" in tokens
        assert "yitzchak" in tokens
        assert "gindi" in tokens
        assert "ben" not in tokens

    def test_display_name(self):
        p = parse_name("moshe ben yitzchak gindi")
        assert "moshe" in p.display_name
        assert "yitzchak" in p.display_name
        assert "gindi" in p.display_name


class TestGenderAwareParsing:
    def test_hebrew_mother_first(self):
        """User's exact case: משה בן מרים ויצחק גינדי"""
        p = parse_name("משה בן מרים ויצחק גינדי")
        assert p.father_name == "יצחק"
        assert p.mother_name == "מרים"
        assert p.surname == "גינדי"

    def test_hebrew_father_first(self):
        p = parse_name("משה בן יצחק ומרים גינדי")
        assert p.father_name == "יצחק"
        assert p.mother_name == "מרים"

    def test_english_mother_first(self):
        p = parse_name("moshe ben miriam v yitzchak gindi")
        assert p.father_name == "yitzchak"
        assert p.mother_name == "miriam"
        assert p.surname == "gindi"

    def test_english_father_first(self):
        p = parse_name("moshe ben yitzchak v miriam gindi")
        assert p.father_name == "yitzchak"
        assert p.mother_name == "miriam"

    def test_bat_with_parents(self):
        p = parse_name("שרה בת רבקה ואברהם")
        assert p.father_name == "אברהם"
        assert p.mother_name == "רבקה"

    def test_unknown_names_keep_order(self):
        p = parse_name("moshe ben shmendrik v ploni")
        assert p.father_name == "shmendrik"
        assert p.mother_name == "ploni"


class TestEdgeCases:
    def test_bar_patronymic(self):
        p = parse_name("shimon bar yochai")
        assert p.patronymic_type == "ben"
        assert p.father_name == "yochai"

    def test_ve_connector(self):
        p = parse_name("moshe ben yitzchak ve sarah")
        assert p.father_name == "yitzchak"
        assert p.mother_name == "sarah"

    def test_to_dict(self):
        p = parse_name("moshe ben yitzchak gindi")
        d = p.to_dict()
        assert d["first_name"] == "moshe"
        assert d["father_name"] == "yitzchak"
        assert d["surname"] == "gindi"
        assert "searchable_components" in d
