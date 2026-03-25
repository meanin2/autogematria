"""Ingest downloaded JSON corpus into SQLite database."""

import json
from pathlib import Path

from tqdm import tqdm

from autogematria.config import TANAKH_BOOKS, CORPUS_DIR, DB_PATH
from autogematria.normalize import normalize_hebrew, FinalsPolicy, FINALS_MAP
from autogematria.schema import create_schema


def ingest_all(corpus_dir: Path = CORPUS_DIR, db_path: Path = DB_PATH) -> None:
    """Read all 39 JSON files and populate every table."""
    conn = create_schema(db_path)
    absolute_word_idx = 0
    absolute_letter_idx = 0
    word_form_cache: dict[str, int] = {}  # normalized_form -> form_id

    for sort_order, (api_name, he_name, category, num_ch) in enumerate(
        tqdm(TANAKH_BOOKS, desc="Ingesting books")
    ):
        # Insert book
        conn.execute(
            "INSERT INTO books VALUES (NULL,?,?,?,?,?)",
            (api_name, he_name, category, num_ch, sort_order),
        )
        book_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Load JSON
        json_path = corpus_dir / f"{api_name.replace(' ', '_')}.json"
        book_data = json.loads(json_path.read_text(encoding="utf-8"))

        for ch_num in range(1, num_ch + 1):
            verses_raw = book_data["chapters"][str(ch_num)]
            conn.execute(
                "INSERT INTO chapters VALUES (NULL,?,?,?)",
                (book_id, ch_num, len(verses_raw)),
            )
            chapter_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            for v_num, verse_text in enumerate(verses_raw, start=1):
                # Normalize: strip diacritics, maqaf→space, collapse whitespace
                # Use PRESERVE for raw storage normalization (keep finals in raw)
                text_norm = normalize_hebrew(verse_text, FinalsPolicy.NORMALIZE)
                # Also clean raw of any HTML/diacritics but keep finals
                text_raw = normalize_hebrew(verse_text, FinalsPolicy.PRESERVE)

                conn.execute(
                    "INSERT INTO verses VALUES (NULL,?,?,?,?)",
                    (chapter_id, v_num, text_raw, text_norm),
                )
                verse_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

                # Tokenize on whitespace from the raw (preserve-finals) text
                raw_words = text_raw.split()
                if not raw_words:
                    continue

                for w_idx, raw_word in enumerate(raw_words):
                    norm_word = normalize_hebrew(raw_word, FinalsPolicy.NORMALIZE)

                    conn.execute(
                        "INSERT INTO words VALUES (NULL,?,?,?,?,?)",
                        (verse_id, w_idx, absolute_word_idx, raw_word, norm_word),
                    )
                    word_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    absolute_word_idx += 1

                    # Track unique word forms
                    if norm_word not in word_form_cache:
                        conn.execute(
                            "INSERT INTO word_forms(form_text, form_raw, frequency) "
                            "VALUES (?,?,1)",
                            (norm_word, raw_word),
                        )
                        form_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                        word_form_cache[norm_word] = form_id
                    else:
                        conn.execute(
                            "UPDATE word_forms SET frequency=frequency+1 WHERE form_id=?",
                            (word_form_cache[norm_word],),
                        )

                    # Insert letters — each character of the raw word
                    for l_idx, letter_raw in enumerate(raw_word):
                        letter_norm = letter_raw.translate(FINALS_MAP)
                        conn.execute(
                            "INSERT INTO letters VALUES (NULL,?,?,?,?,?,?,?,?)",
                            (
                                word_id, l_idx, absolute_letter_idx,
                                letter_raw, letter_norm,
                                verse_id, chapter_id, book_id,
                            ),
                        )
                        absolute_letter_idx += 1

        conn.commit()  # commit per book for safety

    conn.close()
    print(
        f"Ingested: {absolute_word_idx:,} words, "
        f"{absolute_letter_idx:,} letters, "
        f"{len(word_form_cache):,} unique word forms"
    )


def main():
    ingest_all()


if __name__ == "__main__":
    main()
