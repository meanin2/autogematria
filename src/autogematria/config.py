"""Constants, paths, and Tanakh book registry."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
CORPUS_DIR = DATA_DIR / "corpus"
DB_PATH = DATA_DIR / "autogematria.db"

SEFARIA_BASE = "https://www.sefaria.org/api/texts"
# Request consonantal Hebrew only, no English
VERSION_PARAM = "ven=none&vhe=Tanach+with+Text+Only"

# (api_name, hebrew_name, category, num_chapters)
TANAKH_BOOKS: list[tuple[str, str, str, int]] = [
    # Torah
    ("Genesis", "בראשית", "Torah", 50),
    ("Exodus", "שמות", "Torah", 40),
    ("Leviticus", "ויקרא", "Torah", 27),
    ("Numbers", "במדבר", "Torah", 36),
    ("Deuteronomy", "דברים", "Torah", 34),
    # Nevi'im Rishonim
    ("Joshua", "יהושע", "Prophets", 24),
    ("Judges", "שופטים", "Prophets", 21),
    ("I Samuel", "שמואל א", "Prophets", 31),
    ("II Samuel", "שמואל ב", "Prophets", 24),
    ("I Kings", "מלכים א", "Prophets", 22),
    ("II Kings", "מלכים ב", "Prophets", 25),
    # Nevi'im Acharonim
    ("Isaiah", "ישעיהו", "Prophets", 66),
    ("Jeremiah", "ירמיהו", "Prophets", 52),
    ("Ezekiel", "יחזקאל", "Prophets", 48),
    ("Hosea", "הושע", "Prophets", 14),
    ("Joel", "יואל", "Prophets", 4),
    ("Amos", "עמוס", "Prophets", 9),
    ("Obadiah", "עובדיה", "Prophets", 1),
    ("Jonah", "יונה", "Prophets", 4),
    ("Micah", "מיכה", "Prophets", 7),
    ("Nahum", "נחום", "Prophets", 3),
    ("Habakkuk", "חבקוק", "Prophets", 3),
    ("Zephaniah", "צפניה", "Prophets", 3),
    ("Haggai", "חגי", "Prophets", 2),
    ("Zechariah", "זכריה", "Prophets", 14),
    ("Malachi", "מלאכי", "Prophets", 3),
    # Ketuvim
    ("Psalms", "תהלים", "Writings", 150),
    ("Proverbs", "משלי", "Writings", 31),
    ("Job", "איוב", "Writings", 42),
    ("Song of Songs", "שיר השירים", "Writings", 8),
    ("Ruth", "רות", "Writings", 4),
    ("Lamentations", "איכה", "Writings", 5),
    ("Ecclesiastes", "קהלת", "Writings", 12),
    ("Esther", "אסתר", "Writings", 10),
    ("Daniel", "דניאל", "Writings", 12),
    ("Ezra", "עזרא", "Writings", 10),
    ("Nehemiah", "נחמיה", "Writings", 13),
    ("I Chronicles", "דברי הימים א", "Writings", 29),
    ("II Chronicles", "דברי הימים ב", "Writings", 36),
]

TOTAL_BOOKS = len(TANAKH_BOOKS)  # 39
TOTAL_CHAPTERS = sum(ch for _, _, _, ch in TANAKH_BOOKS)  # 929

TORAH_BOOKS = tuple(name for name, _, category, _ in TANAKH_BOOKS if category == "Torah")
BOOK_CATEGORY_BY_NAME = {name: category for name, _, category, _ in TANAKH_BOOKS}
VALID_CORPUS_SCOPES = {"torah", "tanakh"}


def normalize_corpus_scope(corpus_scope: str | None) -> str:
    """Return a normalized corpus scope string."""
    if corpus_scope is None:
        return "torah"
    scope = corpus_scope.strip().lower()
    if scope not in VALID_CORPUS_SCOPES:
        raise ValueError(f"corpus_scope must be one of {sorted(VALID_CORPUS_SCOPES)}")
    return scope
