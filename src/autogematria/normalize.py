"""Hebrew text normalization for search and gematria computation."""

import re
from enum import Enum


class FinalsPolicy(Enum):
    NORMALIZE = "normalize"  # ך→כ etc. (for search/ELS)
    PRESERVE = "preserve"    # keep as-is (for gematria)


FINALS_MAP = str.maketrans("ךםןףץ", "כמנפצ")

# Nikkud (vowel points): U+05B0..U+05BD, U+05BF, U+05C1, U+05C2, U+05C4, U+05C5, U+05C7
# Taamim (cantillation): U+0591..U+05AF
# Punctuation: maqaf U+05BE, sof pasuq U+05C3, paseq U+05C0, geresh U+05F3, gershayim U+05F4
_DIACRITICS_RE = re.compile(
    "[\u0591-\u05af"   # taamim
    "\u05b0-\u05bd"    # nikkud range 1
    "\u05bf"           # nikkud: rafe
    "\u05c1\u05c2"     # nikkud: shin/sin dot
    "\u05c4\u05c5"     # nikkud: upper/lower dot
    "\u05c7"           # nikkud: qamats qatan
    "]"
)

_PUNCTUATION_RE = re.compile(
    "[\u05c0"   # paseq
    "\u05c3"    # sof pasuq
    "\u05f3"    # geresh
    "\u05f4"    # gershayim
    "]"
)

# Hebrew letter range: א (U+05D0) through ת (U+05EA)
_VALID_CHAR_RE = re.compile(r"^[\u05d0-\u05ea ]*$")


def normalize_hebrew(
    text: str,
    finals: FinalsPolicy = FinalsPolicy.NORMALIZE,
) -> str:
    """Normalize Hebrew text to canonical consonantal form.

    Steps in order:
    1. Strip nikkud (vowel points)
    2. Strip cantillation marks (taamim)
    3. Replace maqaf with space, strip other punctuation
    4. Optionally normalize final letters to medial forms
    5. Collapse whitespace
    """
    # 1+2: Strip diacritics (nikkud + taamim)
    text = _DIACRITICS_RE.sub("", text)

    # 3: Maqaf → space, strip other punctuation
    text = text.replace("\u05be", " ")  # maqaf
    text = _PUNCTUATION_RE.sub("", text)

    # 4: Final-letter normalization
    if finals is FinalsPolicy.NORMALIZE:
        text = text.translate(FINALS_MAP)

    # 5: Whitespace collapse
    text = " ".join(text.split())

    return text


def extract_letters(text: str, finals: FinalsPolicy = FinalsPolicy.NORMALIZE) -> str:
    """Return only consonantal letters (no spaces) — for ELS index."""
    normalized = normalize_hebrew(text, finals)
    return normalized.replace(" ", "")


def validate_normalized(text: str) -> bool:
    """Return True if text contains only Hebrew letters (א-ת) and spaces."""
    return bool(_VALID_CHAR_RE.match(text))
