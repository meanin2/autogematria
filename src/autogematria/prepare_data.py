"""Safe end-to-end preparation and validation of AutoGematria runtime data."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path

from autogematria.config import DATA_DIR, SCHEMA_VERSION
from autogematria.download import download_all, validate_corpus_files
from autogematria.gematria_index import compute_all_gematria
from autogematria.gematria_report_index import build_report_indexes
from autogematria.ingest import ingest_all
from autogematria.runtime_data import DataValidationError, validate_corpus_database


def _finalize_database(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.commit()
    finally:
        conn.close()


def _cleanup_build_artifacts(building_db: Path) -> None:
    for suffix in ("", "-wal", "-shm", "-journal"):
        candidate = building_db.with_name(f"{building_db.name}{suffix}")
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            pass


def prepare_data(
    data_dir: str | Path = DATA_DIR,
    *,
    download: bool = True,
) -> dict[str, object]:
    """Build a complete database in a temporary file and atomically activate it."""
    root = Path(data_dir)
    corpus_dir = root / "corpus"
    final_db = root / "autogematria.db"
    building_db = root / "autogematria.db.building"
    root.mkdir(parents=True, exist_ok=True)

    _cleanup_build_artifacts(building_db)
    try:
        if download:
            download_all(corpus_dir)
        corpus_summary = validate_corpus_files(corpus_dir)
        ingest_all(corpus_dir=corpus_dir, db_path=building_db)
        compute_all_gematria(db_path=building_db)
        build_report_indexes(db_path=building_db)
        _finalize_database(building_db)
        database_summary = validate_corpus_database(building_db, strict_version=True)
        for suffix in ("-wal", "-shm"):
            final_db.with_name(f"{final_db.name}{suffix}").unlink(missing_ok=True)
        os.replace(building_db, final_db)
    except Exception:
        _cleanup_build_artifacts(building_db)
        raise

    database_summary["database"] = str(final_db.resolve())
    return {"corpus": corpus_summary, "database": database_summary}


def prepare_main() -> None:
    parser = argparse.ArgumentParser(
        prog="ag-prepare-data",
        description="Download, validate, ingest, and index the AutoGematria corpus safely",
    )
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Use already-downloaded corpus JSON and do not access Sefaria",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = prepare_data(args.data_dir, download=not args.skip_download)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        db = result["database"]
        counts = db["counts"]
        print(f"Prepared corpus database: {db['database']}")
        print(
            f"  {counts['books']} books, {counts['verses']:,} verses, "
            f"{counts['words']:,} words, {counts['letters']:,} letters"
        )


def check_main() -> None:
    parser = argparse.ArgumentParser(
        prog="ag-data-check",
        description="Validate the configured AutoGematria corpus database",
    )
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    parser.add_argument("--allow-legacy", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    db_path = Path(args.data_dir) / "autogematria.db"
    try:
        result = validate_corpus_database(db_path, strict_version=not args.allow_legacy)
    except DataValidationError as exc:
        if args.json:
            print(json.dumps({"ready": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"Data check failed: {exc}")
        raise SystemExit(1) from exc
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Data ready: {result['database']}")
        print(
            f"  schema={result['schema_version']} integrity={result['integrity']} "
            f"methods={result['gematria_methods']}"
        )


if __name__ == "__main__":
    prepare_main()
