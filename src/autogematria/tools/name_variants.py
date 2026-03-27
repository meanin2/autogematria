"""Generate Hebrew query variants for Latin-script names."""

from __future__ import annotations

import itertools
import re

_HEBREW_RE = re.compile(r"[\u05d0-\u05ea]")
_LATIN_RE = re.compile(r"[a-zA-Z]+")
_ENGLISH_STOPWORDS = {
    "maiden",
    "name",
    "wife",
    "my",
    "mr",
    "mrs",
    "ms",
    "dr",
    "the",
    "and",
}

_COMMON_VARIANTS: dict[str, list[str]] = {
    "moshe": ["משה"],
    "gindi": ["גינדי", "גנדי"],
    "gandi": ["גנדי", "גינדי", "גאנדי"],
    "gandy": ["גנדי", "גינדי", "גאנדי"],
    "dorit": ["דורית"],
    "elisa": ["אליסה", "אליזה", "עליזה", "ליסה"],
    "alisa": ["אליסה", "אליזה", "עליזה"],
    "alyssa": ["אליסה", "אליזה"],
    "ergas": ["ארגס", "ארגאס"],
    "meir": ["מאיר"],
    "swed": ["שווד", "שוויד", "סוויד", "סויד"],
}

_DIGRAPH_MAP = {
    "sh": "ש",
    "ch": "ח",
    "kh": "כ",
    "tz": "צ",
    "ts": "צ",
    "ph": "פ",
    "th": "ת",
}

_CHAR_MAP = {
    "a": "א",
    "b": "ב",
    "c": "ק",
    "d": "ד",
    "e": "",
    "f": "פ",
    "g": "ג",
    "h": "ה",
    "i": "י",
    "j": "ג",
    "k": "ק",
    "l": "ל",
    "m": "מ",
    "n": "נ",
    "o": "ו",
    "p": "פ",
    "q": "ק",
    "r": "ר",
    "s": "ס",
    "t": "ט",
    "u": "ו",
    "v": "ו",
    "w": "ו",
    "x": "קס",
    "y": "י",
    "z": "ז",
}


def contains_hebrew(text: str) -> bool:
    return bool(_HEBREW_RE.search(text))


def _latin_key(word: str) -> str:
    letters = _LATIN_RE.findall(word)
    return "".join(letters).lower()


def _rough_transliterate(word: str) -> str:
    key = _latin_key(word)
    if not key:
        return ""

    out = []
    i = 0
    while i < len(key):
        digraph = key[i : i + 2]
        if digraph in _DIGRAPH_MAP:
            out.append(_DIGRAPH_MAP[digraph])
            i += 2
            continue
        out.append(_CHAR_MAP.get(key[i], ""))
        i += 1

    translit = "".join(out)
    translit = translit.replace("יי", "י").replace("וו", "ו")
    return translit


def generate_hebrew_variants(query: str, max_variants: int = 24) -> list[str]:
    raw_words = query.split()
    words = []
    for word in raw_words:
        key = _latin_key(word)
        if key and key in _ENGLISH_STOPWORDS:
            continue
        words.append(word)
    if not words:
        return []

    word_options: list[list[str]] = []
    for word in words:
        if contains_hebrew(word):
            word_options.append([word])
            continue

        key = _latin_key(word)
        options = _COMMON_VARIANTS.get(key, [])
        rough = _rough_transliterate(word)
        if rough:
            options.append(rough)
        if not options:
            options = [word]

        deduped = []
        seen = set()
        for option in options:
            if option and option not in seen:
                seen.add(option)
                deduped.append(option)
        word_options.append(deduped[:4])  # limit combinatoric blow-up per token

    variants = []
    for combo in itertools.product(*word_options):
        variants.append(" ".join(combo))
        if len(variants) >= max_variants:
            break
    # Preserve order and dedupe.
    return list(dict.fromkeys(variants))
