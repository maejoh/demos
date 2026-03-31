"""
Extract table of contents from epub files by ISBN.

Usage:
    python -m scripts.book_pipeline.extract_toc ISBN1 [ISBN2 ...]

Reads epub_path from book_details.json (set by extract_books.py).
Stored paths are relative to BOOKS_DIR in .env.local; absolute paths work too.
Each run completely overwrites the output file(s) for the given ISBNs.

Output: scripts/output/toc/{isbn}.json
"""
import argparse
import sys
from pathlib import Path

from .epub import extract_epub_toc
from .utils import BOOK_DETAILS_PATH, OUTPUT_DIR, load_env_local, load_json, save_json

TOC_DIR = OUTPUT_DIR / "toc"


def main():
    parser = argparse.ArgumentParser(description="Extract table of contents from epub files by ISBN.")
    parser.add_argument("isbns", nargs="+", help="One or more ISBNs to extract TOC for")
    args = parser.parse_args()

    env = load_env_local()
    books_dir_str = env.get("BOOKS_DIR")
    books_dir = Path(books_dir_str) if books_dir_str else None

    book_details = load_json(BOOK_DETAILS_PATH, {})
    if not book_details:
        print(f"Error: {BOOK_DETAILS_PATH} not found or empty — run extract_books.py first.")
        sys.exit(1)

    TOC_DIR.mkdir(parents=True, exist_ok=True)

    for isbn in args.isbns:
        entry = book_details.get(isbn)
        if not entry:
            print(f"[skip] {isbn}: not found in book_details.json")
            continue

        title = entry.get("title", "?")
        epub_path_str = entry.get("epub_path")
        if not epub_path_str:
            print(f"[skip] {isbn} ({title}): no epub_path stored — re-run extract_books.py with --mode overwrite to backfill")
            continue

        epub_path = _resolve_epub_path(epub_path_str, books_dir)
        if epub_path is None:
            location = f"{books_dir}/{epub_path_str}" if books_dir else epub_path_str
            print(f"[error] {isbn} ({title}): epub not found at {location}")
            continue

        toc = extract_epub_toc(epub_path)
        if toc is None:
            print(f"[error] {isbn} ({title}): TOC extraction failed")
            continue

        out_path = TOC_DIR / f"{isbn}.json"
        save_json(out_path, {"isbn": isbn, "title": title, "toc": toc})
        print(f"[ok]   {isbn} ({title}): {_count_entries(toc)} entries → {out_path.name}")


def _resolve_epub_path(epub_path_str: str, books_dir: Path | None) -> Path | None:
    p = Path(epub_path_str)
    if p.is_absolute():
        return p if p.exists() else None
    if books_dir is not None:
        resolved = books_dir / p
        return resolved if resolved.exists() else None
    return None


def _count_entries(toc: list) -> int:
    count = 0
    for entry in toc:
        count += 1
        count += _count_entries(entry.get("children", []))
    return count


if __name__ == "__main__":
    main()
