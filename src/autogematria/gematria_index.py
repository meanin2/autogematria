"""Precompute gematria values for every unique word form in the corpus."""

import sqlite3

from hebrew import Hebrew
from hebrew.gematria import GematriaTypes
from tqdm import tqdm

from autogematria.config import DB_PATH

# All methods from the hebrew package (22 distinct methods)
ALL_METHODS = [
    GematriaTypes.MISPAR_HECHRACHI,
    GematriaTypes.MISPAR_GADOL,
    GematriaTypes.MISPAR_SIDURI,
    GematriaTypes.MISPAR_KATAN,
    GematriaTypes.MISPAR_PERATI,
    GematriaTypes.ATBASH,
    GematriaTypes.ALBAM,
    GematriaTypes.MISPAR_MESHULASH,
    GematriaTypes.MISPAR_KIDMI,
    GematriaTypes.MISPAR_MISPARI,
    GematriaTypes.AYAK_BACHAR,
    GematriaTypes.OFANIM,
    GematriaTypes.ACHAS_BETA,
    GematriaTypes.AVGAD,
    GematriaTypes.REVERSE_AVGAD,
    GematriaTypes.MISPAR_MUSAFI,
    GematriaTypes.MISPAR_BONEEH,
    GematriaTypes.MISPAR_HAMERUBAH_HAKLALI,
    GematriaTypes.MISPAR_HAACHOR,
    GematriaTypes.MISPAR_KATAN_MISPARI,
    GematriaTypes.MISPAR_KOLEL,
    GematriaTypes.MISPAR_SHEMI_MILUI,
]


def register_methods(conn: sqlite3.Connection) -> dict[str, int]:
    """Insert all gematria methods, return name->id mapping."""
    method_ids = {}
    for m in ALL_METHODS:
        conn.execute(
            "INSERT OR IGNORE INTO gematria_methods(method_name) VALUES (?)",
            (m.name,),
        )
        row = conn.execute(
            "SELECT method_id FROM gematria_methods WHERE method_name=?",
            (m.name,),
        ).fetchone()
        method_ids[m.name] = row[0]
    return method_ids


def compute_all_gematria(db_path=DB_PATH) -> None:
    """Compute gematria for every unique word form x every method."""
    conn = sqlite3.connect(str(db_path))
    method_ids = register_methods(conn)

    forms = conn.execute("SELECT form_id, form_raw FROM word_forms").fetchall()
    batch = []
    errors = 0

    for form_id, form_raw in tqdm(forms, desc="Computing gematria"):
        h = Hebrew(form_raw)
        for m in ALL_METHODS:
            try:
                val = h.gematria(m)
                if val is not None:
                    batch.append((form_id, method_ids[m.name], val))
            except Exception:
                errors += 1

        if len(batch) >= 10_000:
            conn.executemany(
                "INSERT OR IGNORE INTO word_gematria VALUES (?,?,?)", batch
            )
            conn.commit()
            batch.clear()

    if batch:
        conn.executemany(
            "INSERT OR IGNORE INTO word_gematria VALUES (?,?,?)", batch
        )
        conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM word_gematria").fetchone()[0]
    conn.close()
    print(f"Computed {total:,} gematria values ({errors} errors skipped)")


def main():
    compute_all_gematria()


if __name__ == "__main__":
    main()
