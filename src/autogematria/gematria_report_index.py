"""Build optimized reverse-lookup indexes for the 6 report gematria methods.

Run after ag-index to add covering indexes that make reverse lookups
(value -> words) fast across the methods used in name reports.

This is idempotent and safe to run repeatedly.
"""

import sqlite3

from autogematria.config import DB_PATH
from autogematria.search.gematria_reverse import REPORT_METHODS, ensure_report_indexes


def build_report_indexes(db_path=DB_PATH) -> dict[str, int]:
    """Verify all report methods are indexed and add optimized indexes.

    Returns a summary of how many values exist per method.
    """
    ensure_report_indexes(db_path)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    summary: dict[str, int] = {}

    for method in REPORT_METHODS:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM word_gematria wg "
            "JOIN gematria_methods gm ON wg.method_id = gm.method_id "
            "WHERE gm.method_name = ?",
            (method,),
        ).fetchone()
        summary[method] = row["cnt"] if row else 0

    distinct = conn.execute(
        "SELECT COUNT(DISTINCT wg.value) as cnt FROM word_gematria wg "
        "JOIN gematria_methods gm ON wg.method_id = gm.method_id "
        "WHERE gm.method_name = 'MISPAR_HECHRACHI'",
    ).fetchone()

    conn.close()

    summary["distinct_standard_values"] = distinct["cnt"] if distinct else 0
    return summary


def main():
    print("Building report-optimized gematria indexes...")
    summary = build_report_indexes()
    print("Methods indexed:")
    for method, count in summary.items():
        if method == "distinct_standard_values":
            continue
        print(f"  {method}: {count:,} word-form values")
    print(f"  Distinct standard values: {summary.get('distinct_standard_values', 0):,}")
    print("Done.")


if __name__ == "__main__":
    main()
