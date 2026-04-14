"""Kabbalistic name analysis rooted in traditional Orthodox sources.

Covers:
  - Letter-level meanings (per Sefer Yetzirah, Tanya, Arizal)
  - Milui (letter-filling / spelled-out letters)
  - AtBash pair analysis
  - Sefirot associations for gematria values
  - Four-worlds (ABYA) breakdown
  - Mispar Neelam (hidden value)
"""

from __future__ import annotations

from typing import Any

from hebrew import Hebrew
from hebrew.gematria import GematriaTypes

from autogematria.normalize import FinalsPolicy, normalize_hebrew


LETTER_MEANINGS: dict[str, dict[str, Any]] = {
    "א": {
        "name": "Aleph",
        "value": 1,
        "meaning": "Oneness, mastery, breath of life",
        "sefirah": "Keter",
        "element": "Air",
        "note": "Silent letter representing the infinite Ein Sof beyond speech",
    },
    "ב": {
        "name": "Bet",
        "value": 2,
        "meaning": "House, dwelling, containment",
        "sefirah": "Chochmah",
        "element": None,
        "note": "The Torah begins with Bet, signifying the creation of a dwelling for Hashem",
    },
    "ג": {
        "name": "Gimel",
        "value": 3,
        "meaning": "Giving, beneficence, camel (carries across desert)",
        "sefirah": "Binah",
        "element": None,
        "note": "Gimel runs after Dalet to give — gemilut chasadim",
    },
    "ד": {
        "name": "Dalet",
        "value": 4,
        "meaning": "Door, humility, poverty of self",
        "sefirah": "Chesed",
        "element": None,
        "note": "The poor person (dal) stands at the door; also the 4 directions",
    },
    "ה": {
        "name": "Hei",
        "value": 5,
        "meaning": "Breath, revelation, divine speech",
        "sefirah": "Gevurah",
        "element": None,
        "note": "Two Heis in the divine Name — one for this world, one for the world to come",
    },
    "ו": {
        "name": "Vav",
        "value": 6,
        "meaning": "Connection, hook, pillar",
        "sefirah": "Tiferet",
        "element": None,
        "note": "The letter of connection — hooks the upper and lower together",
    },
    "ז": {
        "name": "Zayin",
        "value": 7,
        "meaning": "Weapon, sustenance, crowned",
        "sefirah": "Netzach",
        "element": None,
        "note": "Seven — Shabbat, completeness of time",
    },
    "ח": {
        "name": "Chet",
        "value": 8,
        "meaning": "Life, transcendence, enclosure",
        "sefirah": "Hod",
        "element": None,
        "note": "Chet=8, beyond the 7 of nature; also Chayim (life)",
    },
    "ט": {
        "name": "Tet",
        "value": 9,
        "meaning": "Goodness concealed, womb, hidden good",
        "sefirah": "Yesod",
        "element": None,
        "note": "First appears in Torah with 'tov' (good) — hidden goodness within",
    },
    "י": {
        "name": "Yud",
        "value": 10,
        "meaning": "Point of creation, divine spark, humility",
        "sefirah": "Malchut",
        "element": None,
        "note": "Smallest letter — the initial point from which all creation flows",
    },
    "כ": {
        "name": "Kaf",
        "value": 20,
        "meaning": "Palm, potential, crowning",
        "sefirah": "Keter",
        "element": None,
        "note": "Kaf = palm of the hand; Keter (crown) begins with Kaf",
    },
    "ל": {
        "name": "Lamed",
        "value": 30,
        "meaning": "Learning, teaching, aspiration",
        "sefirah": "Binah",
        "element": None,
        "note": "Tallest letter — the tower that rises above; lilmod u'lelamed",
    },
    "מ": {
        "name": "Mem",
        "value": 40,
        "meaning": "Water, womb, revelation",
        "sefirah": "Chesed",
        "element": "Water",
        "note": "Open Mem (מ) and closed Mem (ם) — revealed and concealed Torah",
    },
    "נ": {
        "name": "Nun",
        "value": 50,
        "meaning": "Soul, faithfulness, falling and rising",
        "sefirah": "Gevurah",
        "element": None,
        "note": "Bent Nun = humility; straight Nun sofit = standing tall in the end",
    },
    "ס": {
        "name": "Samech",
        "value": 60,
        "meaning": "Support, surrounding, cyclical",
        "sefirah": "Tiferet",
        "element": None,
        "note": "Circular form — Hashem surrounds and supports from all sides",
    },
    "ע": {
        "name": "Ayin",
        "value": 70,
        "meaning": "Eye, insight, wellspring",
        "sefirah": "Netzach",
        "element": None,
        "note": "70 facets of Torah; the eye of wisdom that perceives depth",
    },
    "פ": {
        "name": "Peh",
        "value": 80,
        "meaning": "Mouth, speech, expression",
        "sefirah": "Hod",
        "element": None,
        "note": "The mouth through which Torah and prayer emerge",
    },
    "צ": {
        "name": "Tzadi",
        "value": 90,
        "meaning": "Righteousness, tzaddik, humility before G-d",
        "sefirah": "Yesod",
        "element": None,
        "note": "The tzaddik — foundation of the world",
    },
    "ק": {
        "name": "Kuf",
        "value": 100,
        "meaning": "Holiness, monkey (imitation), encompassing",
        "sefirah": "Malchut",
        "element": None,
        "note": "Kedusha (holiness) begins with Kuf; descends below the line to elevate",
    },
    "ר": {
        "name": "Reish",
        "value": 200,
        "meaning": "Head, beginning, poverty/richness",
        "sefirah": "Chochmah",
        "element": None,
        "note": "Rosh = head, beginning; also rash = poor — the duality of perspective",
    },
    "ש": {
        "name": "Shin",
        "value": 300,
        "meaning": "Fire, divine presence, transformation",
        "sefirah": "Binah",
        "element": "Fire",
        "note": "Three heads of Shin — the three patriarchs; fire of the burning bush",
    },
    "ת": {
        "name": "Tav",
        "value": 400,
        "meaning": "Truth, seal, completion",
        "sefirah": "Malchut",
        "element": None,
        "note": "Last letter — the seal of truth (emet ends with Tav); completion of aleph-bet",
    },
}

MILUI_SPELLINGS: dict[str, str] = {
    "א": "אלף",
    "ב": "בית",
    "ג": "גימל",
    "ד": "דלת",
    "ה": "הא",
    "ו": "ויו",
    "ז": "זין",
    "ח": "חית",
    "ט": "טית",
    "י": "יוד",
    "כ": "כף",
    "ל": "למד",
    "מ": "מם",
    "נ": "נון",
    "ס": "סמך",
    "ע": "עין",
    "פ": "פא",
    "צ": "צדי",
    "ק": "קוף",
    "ר": "ריש",
    "ש": "שין",
    "ת": "תיו",
}

ATBASH_MAP: dict[str, str] = {}
_ALEPH_BET = "אבגדהוזחטיכלמנסעפצקרשת"
for i, letter in enumerate(_ALEPH_BET):
    ATBASH_MAP[letter] = _ALEPH_BET[-(i + 1)]

SEFIROT_ORDER = [
    "Keter", "Chochmah", "Binah", "Chesed", "Gevurah",
    "Tiferet", "Netzach", "Hod", "Yesod", "Malchut",
]

SEFIROT_DESCRIPTIONS: dict[str, str] = {
    "Keter": "Crown — the will and source above understanding",
    "Chochmah": "Wisdom — the flash of insight, the seminal point",
    "Binah": "Understanding — the expansion and processing of wisdom",
    "Chesed": "Lovingkindness — unbounded giving and mercy",
    "Gevurah": "Strength — discipline, judgment, and boundaries",
    "Tiferet": "Beauty — the harmonious balance of chesed and gevurah",
    "Netzach": "Victory — endurance, eternity, overcoming",
    "Hod": "Splendor — gratitude, acknowledgment, humility",
    "Yesod": "Foundation — connection, channeling, the tzaddik",
    "Malchut": "Sovereignty — receiving, speech, the manifest world",
}

FOUR_WORLDS = {
    "Atzilut": {
        "description": "Emanation — the world of divine unity",
        "sefirah": "Chochmah",
        "letter_of_name": "י",
        "soul_level": "Chaya",
    },
    "Beriah": {
        "description": "Creation — the world of the throne and intellect",
        "sefirah": "Binah",
        "letter_of_name": "ה",
        "soul_level": "Neshama",
    },
    "Yetzirah": {
        "description": "Formation — the world of angels and emotion",
        "sefirah": "Tiferet (6 middot)",
        "letter_of_name": "ו",
        "soul_level": "Ruach",
    },
    "Asiyah": {
        "description": "Action — the world of deed and physical reality",
        "sefirah": "Malchut",
        "letter_of_name": "ה",
        "soul_level": "Nefesh",
    },
}


def _letters_of(text: str) -> list[str]:
    norm = normalize_hebrew(text, FinalsPolicy.NORMALIZE)
    return [ch for ch in norm if ch in LETTER_MEANINGS]


def analyze_letter_meanings(text: str) -> list[dict[str, Any]]:
    """Return letter-level breakdown with meanings and sefirot."""
    return [
        {
            "letter": ch,
            **LETTER_MEANINGS[ch],
        }
        for ch in _letters_of(text)
    ]


def compute_milui(text: str) -> dict[str, Any]:
    """Compute the milui (spelled-out form) of each letter and its gematria.

    Milui reveals the 'hidden' content within each letter. For example,
    מ (Mem) spells out to מם, revealing an additional מ.
    """
    letters = _letters_of(text)
    spelled_out = [MILUI_SPELLINGS.get(ch, ch) for ch in letters]
    full_milui = "".join(spelled_out)
    milui_value = int(Hebrew(full_milui).gematria(GematriaTypes.MISPAR_HECHRACHI))

    hidden_letters = []
    for ch, spelled in zip(letters, spelled_out):
        if len(spelled) > 1:
            hidden_letters.extend(list(spelled[1:]))

    hidden_text = "".join(hidden_letters)
    hidden_value = 0
    if hidden_text:
        hidden_value = int(Hebrew(hidden_text).gematria(GematriaTypes.MISPAR_HECHRACHI))

    return {
        "original": text,
        "letters": letters,
        "spelled_out": spelled_out,
        "full_milui_text": full_milui,
        "milui_value": milui_value,
        "hidden_letters": hidden_letters,
        "hidden_text": hidden_text,
        "hidden_value": hidden_value,
        "breakdown": [
            {
                "letter": ch,
                "milui": spelled,
                "hidden": spelled[1:] if len(spelled) > 1 else "",
            }
            for ch, spelled in zip(letters, spelled_out)
        ],
    }


def compute_atbash(text: str) -> dict[str, Any]:
    """Transform text through AtBash cipher and compute its gematria.

    AtBash maps א↔ת, ב↔ש, ג↔ר, etc. It reveals the 'hidden opposite'
    of a word. Traditional source: mentioned in Jeremiah (ששך = בבל via AtBash).
    """
    letters = _letters_of(text)
    transformed = [ATBASH_MAP.get(ch, ch) for ch in letters]
    transformed_text = "".join(transformed)
    original_value = int(Hebrew("".join(letters)).gematria(GematriaTypes.MISPAR_HECHRACHI))
    atbash_value = int(Hebrew(transformed_text).gematria(GematriaTypes.MISPAR_HECHRACHI))

    return {
        "original": text,
        "original_value": original_value,
        "atbash_text": transformed_text,
        "atbash_value": atbash_value,
        "sum_with_original": original_value + atbash_value,
        "pairs": [
            {"original": ch, "atbash": ATBASH_MAP.get(ch, ch)}
            for ch in letters
        ],
    }


def sefirah_for_value(value: int) -> dict[str, Any]:
    """Map a gematria value to its sefirah association.

    Based on the traditional mapping where values 1-10 correspond to the
    ten sefirot in order.
    """
    reduced = value
    while reduced > 10 and reduced != 0:
        reduced = sum(int(d) for d in str(reduced))

    if reduced == 0:
        idx = 0
    elif reduced <= 10:
        idx = reduced - 1
    else:
        idx = (reduced - 1) % 10

    sefirah = SEFIROT_ORDER[idx]
    return {
        "value": value,
        "reduced_to": reduced,
        "sefirah": sefirah,
        "description": SEFIROT_DESCRIPTIONS[sefirah],
    }


def four_worlds_breakdown(text: str) -> dict[str, Any]:
    """Analyze a name through the four worlds (ABYA).

    Divides the letters roughly across the four worlds:
    Atzilut-Beriah-Yetzirah-Asiyah, and computes the gematria of each segment.
    """
    letters = _letters_of(text)
    if not letters:
        return {"error": "no Hebrew letters found"}

    n = len(letters)
    world_names = ["Atzilut", "Beriah", "Yetzirah", "Asiyah"]
    base_size = n // 4
    remainder = n % 4

    segments: list[list[str]] = []
    idx = 0
    for i in range(4):
        size = base_size + (1 if i < remainder else 0)
        if size > 0:
            segments.append(letters[idx:idx + size])
        else:
            segments.append([])
        idx += size

    worlds = []
    for i, world_name in enumerate(world_names):
        seg = segments[i] if i < len(segments) else []
        seg_text = "".join(seg)
        seg_value = int(Hebrew(seg_text).gematria(GematriaTypes.MISPAR_HECHRACHI)) if seg_text else 0
        info = FOUR_WORLDS[world_name]
        worlds.append({
            "world": world_name,
            "description": info["description"],
            "soul_level": info["soul_level"],
            "letters": seg,
            "text": seg_text,
            "value": seg_value,
            "sefirah": info["sefirah"],
        })

    total_value = sum(w["value"] for w in worlds)
    return {
        "original": text,
        "total_letters": n,
        "total_value": total_value,
        "worlds": worlds,
    }


def full_kabbalistic_analysis(text: str) -> dict[str, Any]:
    """Run all kabbalistic analyses on a name/word."""
    letters = _letters_of(text)
    if not letters:
        return {"error": "no Hebrew letters found", "original": text}

    plain_text = "".join(letters)
    standard_value = int(Hebrew(plain_text).gematria(GematriaTypes.MISPAR_HECHRACHI))

    return {
        "original": text,
        "hebrew_letters": letters,
        "letter_count": len(letters),
        "standard_gematria": standard_value,
        "letter_meanings": analyze_letter_meanings(text),
        "milui": compute_milui(text),
        "atbash": compute_atbash(text),
        "sefirah": sefirah_for_value(standard_value),
        "four_worlds": four_worlds_breakdown(text),
    }
