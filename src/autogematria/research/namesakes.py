"""Well-known biblical namesakes.

A raw direct-word occurrence of one of these names inside the Torah is
almost never a meaningful finding about a modern person -- it is simply
where the Torah talks about the biblical figure.  The report should not
present those as personal Torah findings when the user's query is a
full multi-token name (e.g. ``משה בן יצחק גינדי``).  Instead such hits
are demoted into a dedicated "Biblical Namesake" category, or dropped
entirely when stronger full-name findings are available.
"""

from __future__ import annotations

from autogematria.normalize import FinalsPolicy, normalize_hebrew


# Hebrew (unpointed consonantal) spellings of common biblical figures.
# Keep this list focused -- it should contain names whose raw occurrence
# in the Torah is clearly "about the biblical figure", not a personal
# Torah source for a modern namesake.
BIBLICAL_NAMESAKES_HEBREW: frozenset[str] = frozenset(
    {
        "משה",
        "אברהם",
        "אברם",
        "יצחק",
        "יעקב",
        "ישראל",
        "יוסף",
        "דוד",
        "שלמה",
        "אהרן",
        "אהרון",
        "שמואל",
        "נח",
        "אדם",
        "חוה",
        "שרה",
        "שרי",
        "רבקה",
        "רחל",
        "לאה",
        "מרים",
        "אסתר",
        "רות",
        "חנה",
        "דבורה",
        "יהושע",
        "אליהו",
        "אלישע",
        "בנימין",
        "ראובן",
        "שמעון",
        "לוי",
        "יהודה",
        "דן",
        "נפתלי",
        "גד",
        "אשר",
        "יששכר",
        "זבולון",
    }
)


def _normalize(text: str) -> str:
    return normalize_hebrew(str(text or ""), FinalsPolicy.NORMALIZE).replace(" ", "")


_NORMALIZED_NAMESAKES: frozenset[str] = frozenset(
    _normalize(name) for name in BIBLICAL_NAMESAKES_HEBREW
)


def is_biblical_namesake(text: str) -> bool:
    """Return True if ``text`` is a known biblical namesake (any spelling)."""
    if not text:
        return False
    norm = _normalize(text)
    if not norm:
        return False
    return norm in _NORMALIZED_NAMESAKES or text.strip() in BIBLICAL_NAMESAKES_HEBREW
