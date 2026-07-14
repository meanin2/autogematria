"""Known-answer calculations used by the manual name smoke matrix."""

import pytest

from autogematria.research.cross_compare import compute_gematria_table


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("משה", 345),
        ("דוד", 14),
        ("אברהם", 248),
        ("שרה", 505),
        ("רחל", 238),
        ("יצחק", 208),
        ("יעקב", 182),
        ("מרים", 290),
        ("שלמה", 375),
        ("אסתר", 661),
        ("מלך", 90),
        ("נח", 58),
    ],
)
def test_known_standard_values(name: str, expected: int) -> None:
    row = compute_gematria_table([(name, "manual")])["components"][0]
    assert row["values"]["MISPAR_HECHRACHI"] == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (
            "משה",
            {
                "MISPAR_HECHRACHI": 345,
                "MISPAR_GADOL": 345,
                "MISPAR_KATAN": 12,
                "MISPAR_SIDURI": 39,
                "ATBASH": 102,
                "MISPAR_KOLEL": 346,
            },
        ),
        (
            "אברהם",
            {
                "MISPAR_HECHRACHI": 248,
                "MISPAR_GADOL": 808,
                "MISPAR_KATAN": 14,
                "MISPAR_SIDURI": 52,
                "ATBASH": 803,
                "MISPAR_KOLEL": 249,
            },
        ),
        (
            "מלך",
            {
                "MISPAR_HECHRACHI": 90,
                "MISPAR_GADOL": 570,
                "MISPAR_KATAN": 9,
                "MISPAR_SIDURI": 48,
                "ATBASH": 60,
                "MISPAR_KOLEL": 91,
            },
        ),
    ],
)
def test_known_six_method_profiles(name: str, expected: dict[str, int]) -> None:
    row = compute_gematria_table([(name, "manual")])["components"][0]
    assert row["values"] == expected
