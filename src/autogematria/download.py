"""Download the entire Tanakh from Sefaria API as local JSON files."""

import json
import time
from pathlib import Path

import httpx
from tqdm import tqdm

from autogematria.config import TANAKH_BOOKS, SEFARIA_BASE, VERSION_PARAM, CORPUS_DIR


def _book_payload_is_complete(payload: object, num_chapters: int) -> bool:
    if not isinstance(payload, dict):
        return False
    chapters = payload.get("chapters")
    if not isinstance(chapters, dict):
        return False
    return all(
        isinstance(chapters.get(str(chapter)), list)
        and all(isinstance(verse, str) for verse in chapters[str(chapter)])
        for chapter in range(1, num_chapters + 1)
    )


def download_chapter(
    client: httpx.Client,
    book: str,
    chapter: int,
    *,
    attempts: int = 3,
) -> list[str]:
    """Download a single chapter, return list of verse strings."""
    url = f"{SEFARIA_BASE}/{book}.{chapter}?{VERSION_PARAM}"
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
            verses = data["he"]
            if not isinstance(verses, list) or not all(isinstance(v, str) for v in verses):
                raise ValueError(f"Unexpected Sefaria response for {book} {chapter}")
            return verses
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    raise RuntimeError(f"Unable to download {book} {chapter}: {last_error}") from last_error


def download_book(client: httpx.Client, book: str, num_chapters: int) -> dict:
    """Download all chapters of a book."""
    chapters = {}
    for ch in range(1, num_chapters + 1):
        verses = download_chapter(client, book, ch)
        chapters[str(ch)] = verses
        time.sleep(0.3)  # rate limit courtesy
    return {
        "book": book,
        "num_chapters": num_chapters,
        "chapters": chapters,
    }


def validate_corpus_files(corpus_dir: Path = CORPUS_DIR) -> dict[str, int]:
    """Validate that every configured book and chapter is present and well-formed."""
    books = 0
    chapters = 0
    verses = 0
    for api_name, _he_name, _category, num_chapters in TANAKH_BOOKS:
        path = corpus_dir / f"{api_name.replace(' ', '_')}.json"
        if not path.is_file():
            raise ValueError(f"Missing corpus file: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid corpus file {path}: {exc}") from exc
        chapter_map = payload.get("chapters")
        if not isinstance(chapter_map, dict):
            raise ValueError(f"Corpus file has no chapter map: {path}")
        for chapter in range(1, num_chapters + 1):
            chapter_verses = chapter_map.get(str(chapter))
            if not isinstance(chapter_verses, list) or not all(
                isinstance(verse, str) for verse in chapter_verses
            ):
                raise ValueError(f"Invalid or missing {api_name} chapter {chapter}")
            chapters += 1
            verses += len(chapter_verses)
        books += 1
    return {"books": books, "chapters": chapters, "verses": verses}


def download_all(corpus_dir: Path = CORPUS_DIR) -> None:
    """Download entire Tanakh. One JSON file per book. Resumes if files exist."""
    corpus_dir.mkdir(parents=True, exist_ok=True)
    total_chapters = sum(ch for _, _, _, ch in TANAKH_BOOKS)

    with httpx.Client(timeout=30.0) as client:
        with tqdm(total=total_chapters, desc="Downloading Tanakh") as pbar:
            for api_name, he_name, category, num_ch in TANAKH_BOOKS:
                out_path = corpus_dir / f"{api_name.replace(' ', '_')}.json"
                if out_path.exists():
                    try:
                        existing = json.loads(out_path.read_text(encoding="utf-8"))
                        if _book_payload_is_complete(existing, num_ch):
                            pbar.update(num_ch)
                            continue
                    except (OSError, json.JSONDecodeError):
                        pass

                book_data = download_book(client, api_name, num_ch)
                book_data["hebrew_name"] = he_name
                book_data["category"] = category
                out_path.write_text(
                    json.dumps(book_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                pbar.update(num_ch)

    summary = validate_corpus_files(corpus_dir)
    print(
        f"Download complete. {summary['books']} books, {summary['chapters']} chapters, "
        f"{summary['verses']} verses saved to {corpus_dir}"
    )


def main():
    download_all()


if __name__ == "__main__":
    main()
