#!/usr/bin/env python3
"""
Extract book metadata from epub files and enrich via Google Books API.

Usage:
    python scripts/extract_books_v2.py /path/to/epub/folder
    python scripts/extract_books_v2.py --bundle "Bundle Name"   # uses BOOKS_DIR from .env.local
    python scripts/extract_books_v2.py --bundle "Bundle Name" --overwrite
    python scripts/extract_books_v2.py --bundle "Bundle Name" --force

Outputs:
    scripts/book_list.json    — array of {isbn, title, title_raw} from epub metadata.
                                Appended by default; use --overwrite to replace.
    scripts/book_details.json — dict keyed by ISBN with full book data incl. coverUrl.
                                Merged by default; use --overwrite to replace.

Requirements:
    pip install requests
    GOOGLE_BOOKS_API_KEY set in .env.local
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

GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"
GOOGLE_FIELDS = "items(volumeInfo(title,authors,publishedDate,description,imageLinks,industryIdentifiers))"


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


def sanitize_title(title: str) -> str:
    """Strip edition suffixes and separators from a title."""
    return re.sub(r'[,\s–_-]+\s*(second|third|fourth|fifth|sixth|\d+(st|nd|rd|th))\s+edition.*', '', title, flags=re.IGNORECASE).strip()


def _google_request(params: dict) -> dict | None:
    """Make a Google Books API request with retry on 429."""
    for attempt in range(3):
        try:
            response = requests.get(GOOGLE_BOOKS_URL, params=params, timeout=10)
            if response.status_code == 429:
                wait = 2 ** attempt
                print(f"  [429] rate limited, retrying in {wait}s...")
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"  [warn] request failed: {e}")
            return None
    return None


def _author_looks_mangled(author: str) -> bool:
    """Return True if Google Books returned an ALL-CAPS or otherwise garbled author string."""
    alpha_words = [w for w in author.split() if w.isalpha()]
    return len(alpha_words) > 0 and sum(1 for w in alpha_words if w.isupper()) > len(alpha_words) / 2


def _parse_volume(volume_info: dict, epub_year: int | None = None) -> dict:
    """Extract normalized fields from a Google Books volumeInfo dict."""
    identifiers = volume_info.get("industryIdentifiers", [])
    isbn = next(
        (i["identifier"] for i in identifiers if i.get("type") == "ISBN_13"),
        next((i["identifier"] for i in identifiers if i.get("type") == "ISBN_10"), None),
    )

    authors = volume_info.get("authors", [])
    author = " & ".join(authors) if authors else None

    date_str = volume_info.get("publishedDate", "")
    year_match = re.search(r'\d{4}', date_str)
    year = int(year_match.group()) if year_match else epub_year

    image_links = volume_info.get("imageLinks", {})
    cover_url = image_links.get("thumbnail") or image_links.get("smallThumbnail")
    if cover_url:
        cover_url = cover_url.replace("http://", "https://")

    return {
        "isbn": isbn,
        "title": volume_info.get("title"),
        "author": author,
        "year": year,
        "description": volume_info.get("description", ""),
        "coverUrl": cover_url,
    }


def fetch_google_book(
    isbn: str | None,
    title: str,
    author: str,
    epub_year: int | None,
    api_key: str | None,
) -> dict | None:
    """
    Fetch full book data from Google Books API.
    Queries by ISBN first if available, then falls through title/author variants.
    Returns a normalized dict or None if nothing found.
    """
    base: dict = {"fields": GOOGLE_FIELDS, "maxResults": 1}
    if api_key:
        base["key"] = api_key

    queries: list[str] = []
    if isbn:
        queries.append(f"isbn:{isbn}")

    first_author = author.split(",")[0].strip()
    clean_title = sanitize_title(title)
    queries.append(f'intitle:"{title}" inauthor:"{author}"')
    if first_author != author:
        queries.append(f'intitle:"{title}" inauthor:"{first_author}"')
    queries.append(f'intitle:"{title}"')
    if clean_title != title:
        queries.append(f'intitle:"{clean_title}"')

    for q in queries:
        data = _google_request({**base, "q": q})
        if data:
            items = data.get("items", [])
            if items:
                return _parse_volume(items[0].get("volumeInfo", {}), epub_year)

    return None


def load_json(path: Path, default):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Extract and enrich book metadata via Google Books API.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("folder", nargs="?", help="Path to folder containing epub files")
    group.add_argument("--bundle", metavar="NAME", help="Bundle subfolder name — combined with BOOKS_DIR from .env.local")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite output files instead of appending/merging")
    parser.add_argument("--force", action="store_true", help="Re-fetch API data for all books, even ones already in book_list.json")
    args = parser.parse_args()

    env = load_env_local()
    api_key = env.get("GOOGLE_BOOKS_API_KEY") or None
    if not api_key:
        print("Warning: GOOGLE_BOOKS_API_KEY not set in .env.local — requests will be unauthenticated and heavily rate-limited\n")

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

    # Determine which books need API enrichment
    if args.force or args.overwrite:
        to_enrich = extracted
    else:
        existing_list = load_json(BOOK_LIST_PATH, [])
        known_isbns = {e["isbn"] for e in existing_list if e.get("isbn")}
        known_title_raws = {e.get("title_raw", e["title"]) for e in existing_list if e.get("isbn")}
        to_enrich = [
            m for m in extracted
            if (m.get("isbn") and m["isbn"] not in known_isbns)
            or (not m.get("isbn") and m["title"] not in known_title_raws)
        ]
        skipped = len(extracted) - len(to_enrich)
        if skipped:
            print(f"\nSkipping {skipped} already-known book(s) — use --force to re-fetch.")

    # Step 2: write book_list.json
    new_entries = [
        {"isbn": m.get("isbn") or "", "title": sanitize_title(m["title"]), "title_raw": m["title"]}
        for m in extracted
    ]
    if args.overwrite:
        book_list = new_entries
    else:
        existing_list = load_json(BOOK_LIST_PATH, [])
        existing_titles = {e["title"] for e in existing_list}
        book_list = existing_list + [e for e in new_entries if e["title"] not in existing_titles]
    save_json(BOOK_LIST_PATH, book_list)
    print(f"\n{len(book_list)} total entries in {BOOK_LIST_PATH.name}")

    if not to_enrich:
        print("Nothing new to enrich.")
        return

    # Step 3: enrich all books via Google Books in one parallel pass
    book_details = {} if args.overwrite else load_json(BOOK_DETAILS_PATH, {})
    print(f"\nEnriching {len(to_enrich)} book(s) via Google Books...")

    def enrich_one(meta: dict):
        epub_title = sanitize_title(meta["title"])
        epub_isbn = meta.get("isbn")

        result = fetch_google_book(
            isbn=epub_isbn,
            title=meta["title"],
            author=meta.get("author", ""),
            epub_year=meta.get("year"),
            api_key=api_key,
        )

        if result is None:
            print(f"  [miss] {epub_title}: no result from Google Books")
            if epub_isbn:
                existing = book_details.get(epub_isbn, {})
                book_details[epub_isbn] = {
                    "id": existing.get("id") or str(uuid.uuid4()),
                    "title": epub_title,
                    "author": meta.get("author", "Unknown"),
                    "isbn": epub_isbn,
                    "year": meta.get("year") or existing.get("year"),
                    "tags": existing.get("tags") or [],
                    "description": existing.get("description") or "",
                    "coverUrl": existing.get("coverUrl"),
                }
            return

        isbn = result.get("isbn") or epub_isbn
        if not isbn:
            print(f"  [miss] {epub_title}: Google Books returned no ISBN")
            return

        existing = book_details.get(isbn, {})
        flags = ", ".join(f for f, v in [("cover", result.get("coverUrl")), ("desc", result.get("description"))] if v)
        print(f"  [ok]   {epub_title} ({isbn}){': ' + flags if flags else ''}")

        book_details[isbn] = {
            "id": existing.get("id") or str(uuid.uuid4()),
            "title": result.get("title") or epub_title,
            "author": (result["author"] if result.get("author") and not _author_looks_mangled(result["author"]) else None) or meta.get("author", "Unknown"),
            "isbn": isbn,
            "year": result.get("year") or existing.get("year"),
            "tags": existing.get("tags") or [],
            "description": result.get("description") or existing.get("description") or "",
            "coverUrl": result.get("coverUrl") or existing.get("coverUrl"),
        }

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(enrich_one, meta) for meta in to_enrich]
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

    covered = sum(1 for v in book_details.values() if v.get("coverUrl"))
    no_isbn = [e["title"] for e in book_list if not e["isbn"]]
    print(f"\nDone. {len(book_details)} entries in {BOOK_DETAILS_PATH.name}")
    print(f"  {covered}/{len(book_details)} have cover URLs")
    if no_isbn:
        print(f"  {len(no_isbn)} book(s) with no ISBN:")
        for title in no_isbn:
            print(f"    - {title}")
    print("Next step: open book_details.json, fill in the 'tags' arrays, then run the seed script.")


if __name__ == "__main__":
    main()
