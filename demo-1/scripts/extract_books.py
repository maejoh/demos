#!/usr/bin/env python3
"""
Extract book metadata from epub files and enrich via Open Library.

Usage:
    python scripts/extract_books.py /path/to/epub/folder
    python scripts/extract_books.py /path/to/epub/folder --enrich
    python scripts/extract_books.py /path/to/epub/folder --enrich --overwrite

Outputs:
    scripts/book_list.json   — array of {isbn, title} from epub metadata. isbn may be empty.
                               Appended by default; use --overwrite to replace.
    scripts/book_details.json — dict keyed by ISBN with full book data.
                               Only written when --enrich is passed.
                               Merged by default; use --overwrite to replace.

Requirements:
    pip install requests
"""

import argparse
import json
import re
import uuid
import zipfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

NS = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
}

SCRIPTS_DIR = Path(__file__).parent
BOOK_LIST_PATH = SCRIPTS_DIR / "book_list.json"
BOOK_DETAILS_PATH = SCRIPTS_DIR / "book_details.json"


def extract_epub_metadata(epub_path: Path) -> dict | None:
    """Extract title, author, and ISBN from an epub file."""
    try:
        with zipfile.ZipFile(epub_path, "r") as zf:
            container = ET.fromstring(zf.read("META-INF/container.xml"))
            opf_path = container.find(".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile").get("full-path")

            opf = ET.fromstring(zf.read(opf_path))
            metadata = opf.find("opf:metadata", NS)

            title = getattr(metadata.find("dc:title", NS), "text", None)
            author = getattr(metadata.find("dc:creator", NS), "text", None)

            isbn = None
            for identifier in metadata.findall("dc:identifier", NS):
                scheme = identifier.get("{http://www.idpf.org/2007/opf}scheme", "").upper()
                text = identifier.text or ""
                if "ISBN" in scheme or text.startswith("978") or text.startswith("979"):
                    isbn = text.replace("-", "").strip()
                    break

            if not title:
                print(f"  [skip] No title found in {epub_path.name}")
                return None

            return {
                "title": title.strip(),
                "author": author.strip() if author else "Unknown",
                "isbn": isbn,
            }

    except Exception as e:
        print(f"  [error] {epub_path.name}: {e}")
        return None


def fetch_by_isbns(isbns: list[str]) -> dict[str, dict]:
    """Batch fetch book details from Open Library by ISBN."""
    bibkeys = ",".join(f"ISBN:{isbn}" for isbn in isbns)
    try:
        response = requests.get(
            "https://openlibrary.org/api/books",
            params={"bibkeys": bibkeys, "format": "json", "jscmd": "details"},
            timeout=15,
        )
        response.raise_for_status()
        raw = response.json()
    except Exception as e:
        print(f"  [warn] Batch ISBN lookup failed: {e}")
        return {}

    results = {}
    for key, entry in raw.items():
        isbn = key.replace("ISBN:", "")
        details = entry.get("details", {})
        desc = details.get("description", "")
        if isinstance(desc, dict):
            desc = desc.get("value", "")
        results[isbn] = {"description": desc}

    return results


def sanitize_title(title: str) -> str:
    """Strip edition suffixes and separators from a title."""
    return re.sub(r'[,\s–_-]+\s*(second|third|fourth|fifth|sixth|\d+(st|nd|rd|th))\s+edition.*', '', title, flags=re.IGNORECASE).strip()


def search_open_library(title: str, author: str) -> dict:
    """
    Search Open Library by title/author. Used for books with no ISBN in epub metadata.
    Falls back to first author only (handles 'Author A, Author B' strings), then title-only,
    then title with edition suffix stripped.
    """
    def _query(params):
        r = requests.get("https://openlibrary.org/search.json", params=params, timeout=10)
        r.raise_for_status()
        return r.json().get("docs", [])

    base = {"limit": 1, "fields": "isbn,first_sentence"}
    first_author = author.split(",")[0].strip()
    clean_title = sanitize_title(title)

    attempts = [
        {"title": title, "author": author, **base},
        {"title": title, "author": first_author, **base},
        {"title": title, **base},
        {"title": clean_title, **base},
    ]
    # Deduplicate (e.g. if title had no edition suffix, or author had no comma)
    seen = []
    for a in attempts:
        if a not in seen:
            seen.append(a)

    for params in seen:
        try:
            docs = _query(params)
            if docs:
                doc = docs[0]
                isbn_list = doc.get("isbn", [])
                isbn = next((i for i in isbn_list if len(i) == 13), isbn_list[0] if isbn_list else None)
                first_sentence = doc.get("first_sentence", {})
                description = first_sentence.get("value", "") if isinstance(first_sentence, dict) else ""
                return {"isbn": isbn, "description": description}
        except Exception:
            continue

    print(f"  [warn] All search attempts failed for '{title}'")
    return {}


def load_json(path: Path, default):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Extract book metadata from epub files.")
    parser.add_argument("folder", help="Path to folder containing epub files")
    parser.add_argument("--enrich", action="store_true", help="Enrich metadata via Open Library API")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite output files instead of appending/merging")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"Error: {folder} is not a directory")
        return

    epub_files = list(folder.rglob("*.epub"))
    print(f"Found {len(epub_files)} epub files in {folder}\n")

    # Step 1: extract metadata from all epubs locally
    extracted = []
    for epub_path in epub_files:
        print(f"Processing: {epub_path.name}")
        meta = extract_epub_metadata(epub_path)
        if not meta:
            continue
        extracted.append(meta)
        status = f"isbn: {meta['isbn']}" if meta.get("isbn") else "no isbn in epub"
        print(f"  -> {meta['title']} ({status})")

    # Step 2: write book_list.json — {isbn, title (sanitized), title_raw} per book
    new_entries = [{"isbn": m.get("isbn") or "", "title": sanitize_title(m["title"]), "title_raw": m["title"]} for m in extracted]

    if args.overwrite:
        book_list = new_entries
    else:
        existing_list = load_json(BOOK_LIST_PATH, [])
        existing_titles = {e["title"] for e in existing_list}
        book_list = existing_list + [e for e in new_entries if e["title"] not in existing_titles]

    save_json(BOOK_LIST_PATH, book_list)
    print(f"\n{len(book_list)} total entries in {BOOK_LIST_PATH.name}")

    if not args.enrich:
        isbn_count = sum(1 for e in new_entries if e["isbn"])
        print(f"{isbn_count}/{len(new_entries)} new books had an ISBN in their epub metadata.")
        print("Run with --enrich to populate book_details.json.")
        return

    # Step 3: enrich and write book_details.json — keyed by ISBN
    book_details = {} if args.overwrite else load_json(BOOK_DETAILS_PATH, {})

    has_isbn = [m for m in extracted if m.get("isbn")]
    needs_search = [m for m in extracted if not m.get("isbn")]

    print(f"\n{len(has_isbn)} books have ISBNs — fetching in one batch call...")
    if has_isbn:
        batch_results = fetch_by_isbns([m["isbn"] for m in has_isbn])
        for meta in has_isbn:
            isbn = meta["isbn"]
            enriched = batch_results.get(isbn, {})
            book_details[isbn] = {
                "id": book_details.get(isbn, {}).get("id") or str(uuid.uuid4()),
                "title": sanitize_title(meta["title"]),
                "author": meta["author"],
                "isbn": isbn,
                "tags": book_details.get(isbn, {}).get("tags") or [],
                "description": enriched.get("description") or book_details.get(isbn, {}).get("description") or "",
            }
        print(f"  -> got descriptions for {sum(1 for m in has_isbn if book_details[m['isbn']]['description'])} of {len(has_isbn)}")

    print(f"\n{len(needs_search)} books need a search (no ISBN in epub)...")
    if needs_search:
        def search_and_update(meta):
            result = search_open_library(meta["title"], meta["author"])
            isbn = result.get("isbn")
            found = "isbn + description" if isbn and result.get("description") else "isbn" if isbn else "nothing"
            print(f"  -> {meta['title']}: found {found}")
            if isbn:
                existing = book_details.get(isbn, {})
                book_details[isbn] = {
                    "id": existing.get("id") or str(uuid.uuid4()),
                    "title": sanitize_title(meta["title"]),
                    "author": meta["author"],
                    "isbn": isbn,
                    "tags": existing.get("tags") or [],
                    "description": result.get("description") or existing.get("description") or "",
                }

        # Network requests are I/O-bound, so we parallelize with a small pool
        # rather than waiting on each one sequentially.
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(search_and_update, meta): meta for meta in needs_search}
            for f in as_completed(futures):
                f.result()

    save_json(BOOK_DETAILS_PATH, book_details)

    # Update book_list.json with any ISBNs found during enrichment
    title_to_isbn = {details["title"]: isbn for isbn, details in book_details.items()}
    updated = 0
    for entry in book_list:
        if not entry["isbn"] and entry["title"] in title_to_isbn:
            entry["isbn"] = title_to_isbn[entry["title"]]
            updated += 1
    if updated:
        save_json(BOOK_LIST_PATH, book_list)
        print(f"\nUpdated {updated} ISBN(s) in {BOOK_LIST_PATH.name}")

    no_isbn = [e["title"] for e in book_list if not e["isbn"]]
    print(f"\nDone. {len(book_details)} entries in {BOOK_DETAILS_PATH.name}")
    if no_isbn:
        print(f"  {len(no_isbn)} book(s) with no ISBN after enrichment:")
        for title in no_isbn:
            print(f"    - {title}")
    print("Next step: open book_details.json, fill in the 'tags' arrays, then run the seed script.")


if __name__ == "__main__":
    main()
