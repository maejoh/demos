#!/usr/bin/env python3
"""
Extract book metadata from epub files, enrich via Open Library, and fetch cover URLs from Google Books.

Usage:
    python scripts/extract_books.py /path/to/epub/folder
    python scripts/extract_books.py --bundle "Bundle Name"   # uses BOOKS_DIR from .env.local
    python scripts/extract_books.py --bundle "Bundle Name" --overwrite
    python scripts/extract_books.py --bundle "Bundle Name" --force   # re-fetch all, even known books

Outputs:
    scripts/book_list.json    — array of {isbn, title} from epub metadata. isbn may be empty.
                                Appended by default; use --overwrite to replace.
    scripts/book_details.json — dict keyed by ISBN with full book data incl. coverUrl.
                                Merged by default; use --overwrite to replace.

Requirements:
    pip install requests
"""

import argparse
import json
import re
import time
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


def load_env_local() -> dict[str, str]:
    """Load key=value pairs from .env.local in the project root."""
    env_path = SCRIPTS_DIR.parent / ".env.local"
    result = {}
    if not env_path.exists():
        return result
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r'^([^=]+)=(.*)$', line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip().strip('"').strip("'")
            result[key] = value
    return result


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

            date_text = getattr(metadata.find("dc:date", NS), "text", None) or ""
            year_match = re.search(r'\d{4}', date_text)
            year = int(year_match.group()) if year_match else None

            if not title:
                print(f"  [skip] No title found in {epub_path.name}")
                return None

            return {
                "title": title.strip(),
                "author": author.strip() if author else "Unknown",
                "isbn": isbn,
                "year": year,
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
        publish_date = details.get("publish_date", "")
        year_match = re.search(r'\d{4}', publish_date)
        year = int(year_match.group()) if year_match else None
        results[isbn] = {"description": desc, "year": year}

    return results


def fetch_cover_url(isbn: str, api_key: str | None = None) -> tuple[str | None, str]:
    """Fetch book cover thumbnail URL from Google Books API. Returns (url, reason)."""
    params: dict = {"q": f"isbn:{isbn}", "fields": "items/volumeInfo/imageLinks"}
    if api_key:
        params["key"] = api_key

    for attempt in range(3):
        try:
            response = requests.get(
                "https://www.googleapis.com/books/v1/volumes",
                params=params,
                timeout=10,
            )
            if response.status_code == 429:
                wait = 2 ** attempt
                print(f"  [429] rate limited, retrying in {wait}s...")
                time.sleep(wait)
                continue
            response.raise_for_status()
            data = response.json()
            items = data.get("items", [])
            if not items:
                return None, f"no items in response (keys: {list(data.keys())})"
            links = items[0].get("volumeInfo", {}).get("imageLinks", {})
            if not links:
                return None, "items found but no imageLinks"
            url = links.get("thumbnail") or links.get("smallThumbnail")
            if not url:
                return None, f"imageLinks present but no thumbnail/smallThumbnail (keys: {list(links.keys())})"
            return url.replace("http://", "https://"), "ok"
        except Exception as e:
            return None, f"exception: {e}"

    return None, "failed after 3 retries (429)"


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

    base = {"limit": 1, "fields": "isbn,first_sentence,first_publish_year"}
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
                year = doc.get("first_publish_year") or None
                return {"isbn": isbn, "description": description, "year": year}
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
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("folder", nargs="?", help="Path to folder containing epub files")
    group.add_argument("--bundle", metavar="NAME", help="Bundle subfolder name — combined with BOOKS_DIR from .env.local")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite output files instead of appending/merging")
    parser.add_argument("--force", action="store_true", help="Re-fetch API data for all books, even ones already in book_list.json")
    args = parser.parse_args()

    env = load_env_local()
    google_api_key = env.get("GOOGLE_BOOKS_API_KEY") or None

    if args.bundle:
        books_dir = env.get("BOOKS_DIR") or ""
        if not books_dir:
            print("Error: BOOKS_DIR not set in .env.local")
            return
        folder = Path(books_dir) / args.bundle
    else:
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

    # Determine which books need API enrichment (skip already-known ones unless --force)
    if args.force or args.overwrite:
        to_enrich = extracted
    else:
        existing_list = load_json(BOOK_LIST_PATH, [])
        known_isbns = {e["isbn"] for e in existing_list if e.get("isbn")}
        known_title_raws = {e.get("title_raw", e["title"]) for e in existing_list}
        to_enrich = [
            m for m in extracted
            if (m.get("isbn") and m["isbn"] not in known_isbns)
            or (not m.get("isbn") and m["title"] not in known_title_raws)
        ]
        skipped = len(extracted) - len(to_enrich)
        if skipped:
            print(f"Skipping {skipped} already-known book(s) — use --force to re-fetch.\n")

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

    # Step 3: enrich and write book_details.json — keyed by ISBN
    book_details = {} if args.overwrite else load_json(BOOK_DETAILS_PATH, {})

    has_isbn = [m for m in to_enrich if m.get("isbn")]
    needs_search = [m for m in to_enrich if not m.get("isbn")]

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
                "year": enriched.get("year") or meta.get("year") or book_details.get(isbn, {}).get("year"),
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
                    "year": result.get("year") or meta.get("year") or existing.get("year"),
                    "tags": existing.get("tags") or [],
                    "description": result.get("description") or existing.get("description") or "",
                }

        # Network requests are I/O-bound, so we parallelize with a small pool
        # rather than waiting on each one sequentially.
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(search_and_update, meta): meta for meta in needs_search}
            for f in as_completed(futures):
                f.result()

    # Step 4: fetch cover URLs from Google Books
    isbns_needing_covers = [isbn for isbn in book_details if not book_details[isbn].get("coverUrl")]
    if isbns_needing_covers:
        print(f"\nFetching cover URLs from Google Books for {len(isbns_needing_covers)} books...")
        cover_urls: dict[str, str] = {}

        def fetch_one_cover(isbn):
            url, reason = fetch_cover_url(isbn, google_api_key)
            title = book_details.get(isbn, {}).get("title", isbn)
            if url:
                cover_urls[isbn] = url
                print(f"  [ok]   {title} ({isbn})")
            else:
                print(f"  [miss] {title} ({isbn}): {reason}")

        with ThreadPoolExecutor(max_workers=1) as executor:
            futures = [executor.submit(fetch_one_cover, isbn) for isbn in isbns_needing_covers]
            for f in as_completed(futures):
                f.result()

        for isbn, url in cover_urls.items():
            book_details[isbn]["coverUrl"] = url
        print(f"  -> found covers for {len(cover_urls)} of {len(isbns_needing_covers)}")

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
