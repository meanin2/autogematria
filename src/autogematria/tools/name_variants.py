"""Generate Hebrew query variants for Latin-script names."""

from __future__ import annotations

import itertools
import re

_HEBREW_RE = re.compile(r"[\u05d0-\u05ea]")
_LATIN_RE = re.compile(r"[a-zA-Z]+")
_ENGLISH_STOPWORDS = {
    "maiden", "name", "wife", "my", "mr", "mrs", "ms", "dr", "the", "and",
    "ben", "bat", "bas", "bar", "ibn", "v", "ve",
}

_COMMON_VARIANTS: dict[str, list[str]] = {
    # Male biblical / traditional names
    "aaron": ["אהרן", "אהרון"],
    "abraham": ["אברהם"],
    "avraham": ["אברהם"],
    "adam": ["אדם"],
    "akiva": ["עקיבא", "עקיבה"],
    "amos": ["עמוס"],
    "ari": ["ארי", "אריה"],
    "aryeh": ["אריה"],
    "asher": ["אשר"],
    "azriel": ["עזריאל"],
    "baruch": ["ברוך"],
    "binyamin": ["בנימין"],
    "benjamin": ["בנימין"],
    "boaz": ["בועז"],
    "caleb": ["כלב"],
    "chaim": ["חיים"],
    "haim": ["חיים"],
    "dan": ["דן"],
    "daniel": ["דניאל"],
    "david": ["דוד"],
    "dovid": ["דוד"],
    "efraim": ["אפרים"],
    "ephraim": ["אפרים"],
    "elazar": ["אלעזר"],
    "eli": ["עלי", "אלי"],
    "eliezer": ["אליעזר"],
    "eliyahu": ["אליהו"],
    "elijah": ["אליהו"],
    "elimelech": ["אלימלך"],
    "enoch": ["חנוך"],
    "chanoch": ["חנוך"],
    "ezra": ["עזרא"],
    "gad": ["גד"],
    "gavriel": ["גבריאל"],
    "gabriel": ["גבריאל"],
    "gershon": ["גרשון", "גרשם"],
    "gershom": ["גרשם", "גרשון"],
    "hillel": ["הלל"],
    "isaac": ["יצחק"],
    "yitzchak": ["יצחק"],
    "yitzhak": ["יצחק"],
    "isaiah": ["ישעיהו", "ישעיה"],
    "yeshayahu": ["ישעיהו"],
    "israel": ["ישראל"],
    "yisrael": ["ישראל"],
    "issachar": ["יששכר"],
    "jacob": ["יעקב"],
    "yaakov": ["יעקב"],
    "jeremiah": ["ירמיהו", "ירמיה"],
    "joel": ["יואל"],
    "jonah": ["יונה"],
    "jonathan": ["יונתן", "יהונתן"],
    "yonatan": ["יונתן"],
    "joseph": ["יוסף"],
    "yosef": ["יוסף"],
    "joshua": ["יהושע"],
    "yehoshua": ["יהושע"],
    "judah": ["יהודה"],
    "yehuda": ["יהודה"],
    "kalman": ["קלמן", "קלונימוס"],
    "levi": ["לוי"],
    "menachem": ["מנחם"],
    "menashe": ["מנשה"],
    "mendel": ["מנדל"],
    "meir": ["מאיר"],
    "michael": ["מיכאל"],
    "mordechai": ["מרדכי"],
    "moshe": ["משה"],
    "moses": ["משה"],
    "nachman": ["נחמן"],
    "nachum": ["נחום"],
    "naftali": ["נפתלי"],
    "nathan": ["נתן"],
    "natan": ["נתן"],
    "netanel": ["נתנאל"],
    "noach": ["נח"],
    "noah": ["נח"],
    "ovadia": ["עובדיה"],
    "obadiah": ["עובדיה"],
    "pinchas": ["פנחס"],
    "rafael": ["רפאל"],
    "raphael": ["רפאל"],
    "refael": ["רפאל"],
    "reuven": ["ראובן"],
    "reuben": ["ראובן"],
    "samuel": ["שמואל"],
    "shmuel": ["שמואל"],
    "saul": ["שאול"],
    "shaul": ["שאול"],
    "shimon": ["שמעון"],
    "simon": ["שמעון"],
    "shalom": ["שלום"],
    "shlomo": ["שלמה"],
    "solomon": ["שלמה"],
    "tzvi": ["צבי"],
    "zvi": ["צבי"],
    "yechezkel": ["יחזקאל"],
    "ezekiel": ["יחזקאל"],
    "yirmiyahu": ["ירמיהו"],
    "yishai": ["ישי"],
    "jesse": ["ישי"],
    "yissachar": ["יששכר"],
    "yonah": ["יונה"],
    "yoel": ["יואל"],
    "zev": ["זאב"],
    "zevulun": ["זבולון"],
    "zechariah": ["זכריה"],
    "zecharia": ["זכריה"],
    "zussman": ["זוסמן"],
    # Female biblical / traditional names
    "chana": ["חנה"],
    "hannah": ["חנה"],
    "chava": ["חוה"],
    "eve": ["חוה"],
    "devorah": ["דבורה"],
    "deborah": ["דבורה"],
    "dvorah": ["דבורה"],
    "dvora": ["דבורה"],
    "dinah": ["דינה"],
    "dina": ["דינה"],
    "esther": ["אסתר"],
    "hadassah": ["הדסה"],
    "leah": ["לאה"],
    "lea": ["לאה"],
    "michal": ["מיכל"],
    "miriam": ["מרים"],
    "naomi": ["נעמי"],
    "rachel": ["רחל"],
    "rivka": ["רבקה"],
    "rebecca": ["רבקה"],
    "ruth": ["רות"],
    "sarah": ["שרה"],
    "sara": ["שרה"],
    "tamar": ["תמר"],
    "tzipora": ["צפורה"],
    "yael": ["יעל"],
    "yehudit": ["יהודית"],
    "judith": ["יהודית"],
    # Modern / Yiddish / common names
    "aliza": ["עליזה"],
    "alisa": ["אליסה", "אליזה", "עליזה"],
    "alyssa": ["אליסה", "אליזה"],
    "avigail": ["אביגיל"],
    "batsheva": ["בתשבע"],
    "bila": ["בילה"],
    "bracha": ["ברכה"],
    "dorit": ["דורית"],
    "elisa": ["אליסה", "אליזה", "עליזה", "ליסה"],
    "feiga": ["פייגא"],
    "frida": ["פרידה"],
    "golda": ["גולדה"],
    "malka": ["מלכה"],
    "nitzevet": ["נצבת"],
    "noa": ["נעה", "נועה"],
    "ora": ["אורה"],
    "penina": ["פנינה"],
    "shira": ["שירה"],
    "shoshana": ["שושנה"],
    "shulamit": ["שולמית"],
    "tehila": ["תהילה"],
    "tova": ["טובה"],
    "yocheved": ["יוכבד"],
    "zelda": ["זלדה"],
    # Surnames
    "cohen": ["כהן", "כהאן"],
    "katz": ["כץ"],
    "levy": ["לוי"],
    "mizrahi": ["מזרחי"],
    "peretz": ["פרץ"],
    "shapiro": ["שפירא", "שפירו"],
    "schwartz": ["שוורץ", "שווארץ"],
    "goldstein": ["גולדשטיין"],
    "friedman": ["פרידמן"],
    "gindi": ["גינדי", "גנדי"],
    "gandi": ["גנדי", "גינדי", "גאנדי"],
    "gandy": ["גנדי", "גינדי", "גאנדי"],
    "ergas": ["ארגס", "ארגאס"],
    "swed": ["שווד", "שוויד", "סוויד", "סויד"],
    "abadi": ["עבאדי"],
    "abulafia": ["אבולעפיה"],
    "harari": ["הררי"],
    # Common Hebrew titles used in structured names
    "hamelech": ["המלך"],
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
        options = list(_COMMON_VARIANTS.get(key, ()))
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
