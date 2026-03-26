"""Reproducible hard-negative generation for evaluation datasets."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


COMMON_FIRST_NAMES = [
    "אברהם",
    "אהרן",
    "אליהו",
    "בנימין",
    "דוד",
    "יוסף",
    "יהושע",
    "יעקב",
    "יצחק",
    "מאיר",
    "משה",
]

FAKE_FIRST_NAMES = [
    "זדקיה",
    "מלורם",
    "רפדון",
    "סתרון",
    "טלפיר",
    "כרמול",
    "גלעוז",
]

SURNAME_STEMS = [
    "ארג",
    "בלומ",
    "גרינ",
    "הרמ",
    "לנד",
    "מנד",
    "פיש",
    "קליינ",
    "רוזנ",
    "שוורצ",
]

SURNAME_SUFFIXES = ["ברג", "בלום", "היים", "וביץ", "זון", "לר", "מן", "סקי", "שטיין"]

HEBREW_CORE = "אבגדהוזחטיכלמנסעפצקרשת"
TRANSLIT_VARIANTS = [
    "זינדל",
    "גרצמן",
    "הרזוג",
    "פלומד",
    "דריגון",
    "זורביל",
]


def _make_hebrew_like_word(rng: random.Random, min_len: int = 8, max_len: int = 10) -> str:
    length = rng.randint(min_len, max_len)
    chars = []
    for i in range(length):
        ch = rng.choice(HEBREW_CORE)
        if i > 0 and chars[-1] == ch:
            ch = rng.choice(HEBREW_CORE)
        chars.append(ch)
    return "".join(chars)


def _pick_split(index: int) -> str:
    cycle = ["train", "train", "dev", "dev", "holdout"]
    return cycle[index % len(cycle)]


def generate_hard_negative_entries(
    *,
    existing_names: set[str],
    count: int = 36,
    seed: int = 613,
) -> list[dict]:
    """Generate hard-negative entries across multiple decoy categories."""
    rng = random.Random(seed)
    generated: list[dict] = []
    seen = set(existing_names)

    categories = [
        "hebrew_looking_fake",
        "surname_like_endings",
        "transliteration_variants",
        "length_matched_decoys",
        "same_first_fake_surname",
        "same_surname_fake_first",
    ]

    i = 0
    while len(generated) < count:
        cat = categories[i % len(categories)]
        i += 1

        if cat == "hebrew_looking_fake":
            name = _make_hebrew_like_word(rng, min_len=8, max_len=10)
            method = "els"
            params = {"skip_range": [1, 160]}
            task = "els"
        elif cat == "surname_like_endings":
            stem = rng.choice(SURNAME_STEMS)
            suffix = rng.choice(SURNAME_SUFFIXES)
            name = f"{stem}{suffix}"
            if len(name) < 8:
                name = f"{name}{rng.choice('אלמן')}"
            method = "els"
            params = {"skip_range": [1, 160]}
            task = "els"
        elif cat == "transliteration_variants":
            first = rng.choice(TRANSLIT_VARIANTS)
            second = rng.choice(TRANSLIT_VARIANTS)
            name = f"{first}{second[:3]}"
            method = "els"
            params = {"skip_range": [1, 180]}
            task = "els"
        elif cat == "length_matched_decoys":
            first = _make_hebrew_like_word(rng, min_len=4, max_len=5)
            second = _make_hebrew_like_word(rng, min_len=5, max_len=6)
            name = f"{first} {second}"
            method = "substring"
            params = {"mode": "phrase"}
            task = "multi_word_full_name"
        elif cat == "same_first_fake_surname":
            first = rng.choice(COMMON_FIRST_NAMES)
            fake_last = f"{_make_hebrew_like_word(rng, min_len=5, max_len=7)}{rng.choice('מן')}"
            name = f"{first} {fake_last}"
            method = "substring"
            params = {"mode": "phrase"}
            task = "multi_word_full_name"
        else:
            fake_first = rng.choice(FAKE_FIRST_NAMES)
            last = f"{rng.choice(SURNAME_STEMS)}{rng.choice(SURNAME_SUFFIXES)}"
            name = f"{fake_first} {last}"
            method = "substring"
            params = {"mode": "phrase"}
            task = "multi_word_full_name"

        if name in seen:
            continue
        seen.add(name)
        idx = len(generated)
        generated.append(
            {
                "entry_id": f"hardneg_{idx:04d}",
                "name": name,
                "english": f"Hard negative {idx + 1}",
                "method": method,
                "book": None,
                "chapter": None,
                "verse": None,
                "params": params,
                "source": "hard_negative_generator",
                "difficulty": "hard",
                "split": _pick_split(idx),
                "track": "hard_negative",
                "task": task,
                "corpus_scope": "torah",
                "is_negative": True,
                "notes": f"Generated hard negative ({cat})",
            }
        )

    return generated


def append_hard_negatives(
    dataset_path: Path,
    *,
    count: int = 36,
    seed: int = 613,
) -> int:
    """Append generated hard negatives to an existing JSONL dataset."""
    rows = []
    if dataset_path.exists():
        rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    existing_names = {str(row.get("name")) for row in rows}

    generated = generate_hard_negative_entries(
        existing_names=existing_names,
        count=count,
        seed=seed,
    )
    rows.extend(generated)
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    return len(generated)


def main() -> None:
    parser = argparse.ArgumentParser(description="Append hard negatives to a ground-truth JSONL file.")
    parser.add_argument("dataset_path", type=Path, help="Path to dataset JSONL")
    parser.add_argument("--count", type=int, default=36)
    parser.add_argument("--seed", type=int, default=613)
    args = parser.parse_args()

    added = append_hard_negatives(args.dataset_path, count=args.count, seed=args.seed)
    print(f"Appended {added} hard negatives to {args.dataset_path}")


if __name__ == "__main__":
    main()
