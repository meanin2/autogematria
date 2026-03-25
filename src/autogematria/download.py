"""Download the entire Tanakh from Sefaria API as local JSON files."""

import json
import time

import httpx
from tqdm import tqdm

from autogematria.config import TANAKH_BOOKS, SEFARIA_BASE, VERSION_PARAM, CORPUS_DIR


def download_chapter(client: httpx.Client, book: str, chapter: int) -> list[str]:
    """Download a single chapter, return list of verse strings."""
    url = f"{SEFARIA_BASE}/{book}.{chapter}?{VERSION_PARAM}"
    resp = client.get(url)
    resp.raise_for_status()
    data = resp.json()
    # v2 API returns Hebrew text in "he" key
    return data["he"]


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


def download_all() -> None:
    """Download entire Tanakh. One JSON file per book. Resumes if files exist."""
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    total_chapters = sum(ch for _, _, _, ch in TANAKH_BOOKS)

    with httpx.Client(timeout=30.0) as client:
        with tqdm(total=total_chapters, desc="Downloading Tanakh") as pbar:
            for api_name, he_name, category, num_ch in TANAKH_BOOKS:
                out_path = CORPUS_DIR / f"{api_name.replace(' ', '_')}.json"
                if out_path.exists():
                    pbar.update(num_ch)
                    continue

                book_data = download_book(client, api_name, num_ch)
                book_data["hebrew_name"] = he_name
                book_data["category"] = category
                out_path.write_text(
                    json.dumps(book_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                pbar.update(num_ch)

    print(f"Download complete. {len(TANAKH_BOOKS)} books saved to {CORPUS_DIR}")


def main():
    download_all()


if __name__ == "__main__":
    main()
