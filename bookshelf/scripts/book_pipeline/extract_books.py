import argparse
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .epub import extract_epub_cover, extract_epub_metadata
from .google_books import _author_looks_mangled, fetch_google_book
from .utils import (
    BOOK_DETAILS_NO_ISBN_PATH,
    BOOK_DETAILS_PATH,
    BOOK_LIST_MANUAL_ISBN_PATH,
    BOOK_LIST_PATH,
    load_env_local,
    load_json,
    sanitize_title,
    save_json,
)


def main():
    parser = argparse.ArgumentParser(description="Extract and enrich book metadata, with covers from epub files.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("folder", nargs="?", help="Path to folder containing epub files")
    group.add_argument("--bundle", metavar="NAME", help="Bundle subfolder name — combined with BOOKS_DIR from .env.local")
    parser.add_argument("--mode", choices=["fast", "overwrite", "clean"], default="fast",
                        help="fast (default): skip already-processed books. overwrite: re-process all, update entries, keep old data. clean: delete all output files first, then run fresh.")
    parser.add_argument("--list-only", action="store_true", help="Extract epub metadata and update book_list.json only — skip enrichment and API calls")
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

    if args.mode == "clean":
        for path in [BOOK_LIST_PATH, BOOK_DETAILS_PATH, BOOK_DETAILS_NO_ISBN_PATH]:
            if path.exists():
                path.unlink()
                print(f"Deleted {path.name}")

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

    # Step 2: write book_list.json (ISBN books) and book_list_manual_isbn.json (no-ISBN books)
    existing_list = load_json(BOOK_LIST_PATH, [])
    existing_list_missing = load_json(BOOK_LIST_MANUAL_ISBN_PATH, [])

    # Recover any ISBNs manually filled into book_list_manual_isbn.json
    manually_filled = {
        e.get("title_raw", e["title"]): e["isbn"]
        for e in existing_list_missing
        if e.get("isbn") and e["isbn"].strip()
    }
    if manually_filled:
        extracted = [
            {**m, "isbn": manually_filled[m["title"]]}
            if not (m.get("isbn") and m["isbn"].strip()) and m["title"] in manually_filled
            else m
            for m in extracted
        ]
        print(f"Recovered {len(manually_filled)} manually-filled ISBN(s) from {BOOK_LIST_MANUAL_ISBN_PATH.name}")
    # Promoted entries stay in book_list_manual_isbn.json for reuse on future clean runs

    new_with_isbn = [
        {"isbn": m["isbn"], "title": sanitize_title(m["title"]), "title_raw": m["title"]}
        for m in extracted if (m.get("isbn") and m["isbn"].strip() != "")
    ]
    new_without_isbn = [
        {"isbn": "", "title": sanitize_title(m["title"]), "title_raw": m["title"]}
        for m in extracted if not (m.get("isbn") and m["isbn"].strip() != "")
    ]

    if args.mode == "fast":
        existing_titled_with_isbn = {e["title"] for e in existing_list if e.get("isbn")}
        book_list = existing_list + [e for e in new_with_isbn if e["title"] not in existing_titled_with_isbn]

        existing_missing_titles = {e["title"] for e in existing_list_missing}
        book_list_missing = existing_list_missing + [e for e in new_without_isbn if e["title"] not in existing_missing_titles]
    else:  # overwrite or clean (clean already deleted the files, so existing lists are empty)
        by_title = {e["title"]: e for e in existing_list}
        for e in new_with_isbn:
            by_title[e["title"]] = e
        book_list = list(by_title.values())

        missing_by_title = {e["title"]: e for e in existing_list_missing}
        for e in new_without_isbn:
            missing_by_title[e["title"]] = e
        book_list_missing = list(missing_by_title.values())

    save_json(BOOK_LIST_PATH, book_list)
    print(f"\n{len(book_list)} total entries in {BOOK_LIST_PATH.name}")
    if book_list_missing:
        save_json(BOOK_LIST_MANUAL_ISBN_PATH, book_list_missing)
        print(f"{len(book_list_missing)} entries in {BOOK_LIST_MANUAL_ISBN_PATH.name} (no ISBN)")

    if args.list_only:
        return

    # Step 3: enrich — Google Books for metadata, epub file for cover image
    book_details = load_json(BOOK_DETAILS_PATH, {})

    # Step 3a: enrich entries from book_list_manual_isbn.json that aren't yet in book_list.json
    if book_list_missing:
        book_list_isbns = {e["isbn"] for e in book_list if e.get("isbn")}
        manual_added = 0
        manual_isbn_updated = 0
        print(f"\nChecking {len(book_list_missing)} manual ISBN entry(s)...")

        for entry in book_list_missing:
            title = entry.get("title", "")
            raw_isbn = entry.get("isbn", "").replace("-", "").strip()

            if raw_isbn and raw_isbn in book_list_isbns:
                continue  # already tracked in book_list.json

            result = fetch_google_book(
                isbn=raw_isbn or None,
                title=entry.get("title_raw", title),
                author="",
                epub_year=None,
                api_key=api_key,
            )

            if result is None:
                print(f"  [miss] {title}: no result from Google Books")
                continue

            found_isbn = result.get("isbn") or raw_isbn or None
            if not found_isbn:
                print(f"  [miss] {title}: no ISBN returned")
                continue

            print(f"  [ok]   {title} ({found_isbn})")
            existing = book_details.get(found_isbn, {})
            book_details[found_isbn] = {
                "id": existing.get("id") or str(uuid.uuid4()),
                "title": result.get("title") or title,
                "author": (result["author"] if result.get("author") and not _author_looks_mangled(result["author"]) else None) or "Unknown",
                "isbn": found_isbn,
                "year": result.get("year") or existing.get("year"),
                "tags": existing.get("tags") or [],
                "ai_tags": existing.get("ai_tags") or [],
                "description": result.get("description") or existing.get("description") or "",
                "coverUrl": existing.get("coverUrl"),
            }

            # Update isbn in the manual list entry if it was empty or different
            if entry.get("isbn", "").replace("-", "").strip() != found_isbn:
                entry["isbn"] = found_isbn
                manual_isbn_updated += 1

            # Add to book_list if not already tracked
            if found_isbn not in book_list_isbns:
                book_list.append({"isbn": found_isbn, "title": title, "title_raw": entry.get("title_raw", title)})
                book_list_isbns.add(found_isbn)
                manual_added += 1

        if manual_added or manual_isbn_updated:
            save_json(BOOK_LIST_PATH, book_list)
            save_json(BOOK_LIST_MANUAL_ISBN_PATH, book_list_missing)
            parts = []
            if manual_added:
                parts.append(f"{manual_added} added to {BOOK_LIST_PATH.name}")
            if manual_isbn_updated:
                parts.append(f"{manual_isbn_updated} ISBN(s) updated in {BOOK_LIST_MANUAL_ISBN_PATH.name}")
            print(f"  {', '.join(parts)}")

    # Determine which books need enrichment
    if args.mode != "fast":
        to_enrich = extracted
    else:
        enriched_isbns = set(book_details.keys())
        # Pick up ISBNs manually added to book_list for previously no-ISBN epubs
        list_isbn_by_title_raw = {
            e.get("title_raw", e["title"]): e["isbn"]
            for e in book_list
            if e.get("isbn")
        }
        to_enrich = []
        skipped = 0
        for m in extracted:
            effective_isbn = m.get("isbn") or list_isbn_by_title_raw.get(m["title"])
            if effective_isbn and effective_isbn in enriched_isbns:
                skipped += 1
                continue
            epub_title = sanitize_title(m["title"])
            if effective_isbn:
                print(f"  [debug] {epub_title}: isbn={effective_isbn}, in enriched_isbns={effective_isbn in enriched_isbns}")
            else:
                in_list = m["title"] in list_isbn_by_title_raw
                print(f"  [debug] {epub_title}: no isbn in epub, title_raw lookup={'found' if in_list else 'miss'}")
            to_enrich.append({**m, "isbn": effective_isbn} if effective_isbn else m)
        if skipped:
            print(f"Skipping {skipped} already-enriched book(s) — use --mode overwrite to re-fetch.")
    book_details_no_isbn: list = []
    isbn_discovered: dict[str, str] = {}  # epub_title → isbn for books with no epub isbn
    print(f"\nEnriching {len(to_enrich)} book(s)...")

    def enrich_one(meta: dict):
        epub_title = sanitize_title(meta["title"])
        epub_isbn = meta.get("isbn")
        epub_path = meta["epub_path"]

        result = fetch_google_book(
            isbn=epub_isbn,
            title=meta["title"],
            author=meta.get("author", ""),
            epub_year=meta.get("year"),
            api_key=api_key,
        )

        isbn = epub_isbn or (result.get("isbn") if result else None)
        # Use ISBN as cover filename if available, otherwise a sanitized title slug
        cover_key = isbn or re.sub(r'[^\w]', '_', epub_title)[:60]
        cover_url = extract_epub_cover(epub_path, cover_key)

        flags = ", ".join(f for f, v in [("cover", cover_url), ("desc", result and result.get("description"))] if v)

        if result is None:
            print(f"  [miss] {epub_title}: no result from Google Books{': ' + flags if flags else ''}")
            if isbn:
                existing = book_details.get(isbn, {})
                book_details[isbn] = {
                    "id": existing.get("id") or str(uuid.uuid4()),
                    "title": epub_title,
                    "author": meta.get("author", "Unknown"),
                    "isbn": isbn,
                    "year": meta.get("year") or existing.get("year"),
                    "tags": existing.get("tags") or [],
                    "ai_tags": existing.get("ai_tags") or [],
                    "description": existing.get("description") or "",
                    "coverUrl": cover_url or existing.get("coverUrl"),
                }
            else:
                book_details_no_isbn.append({"isbn": "", "title": epub_title, "title_raw": meta["title"]})
            return

        if not isbn:
            print(f"  [miss] {epub_title}: Google Books returned no ISBN")
            book_details_no_isbn.append({"isbn": "", "title": epub_title, "title_raw": meta["title"]})
            return

        print(f"  [ok]   {epub_title} ({isbn}){': ' + flags if flags else ''}")
        existing = book_details.get(isbn, {})
        book_details[isbn] = {
            "id": existing.get("id") or str(uuid.uuid4()),
            "title": result.get("title") or epub_title,
            "author": (result["author"] if result.get("author") and not _author_looks_mangled(result["author"]) else None) or meta.get("author", "Unknown"),
            "isbn": isbn,
            "year": result.get("year") or existing.get("year"),
            "tags": existing.get("tags") or [],
            "ai_tags": existing.get("ai_tags") or [],
            "description": result.get("description") or existing.get("description") or "",
            "coverUrl": cover_url or existing.get("coverUrl"),
        }
        if not epub_isbn:
            isbn_discovered[epub_title] = isbn

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(enrich_one, meta) for meta in to_enrich]
        for f in as_completed(futures):
            f.result()

    save_json(BOOK_DETAILS_PATH, book_details)
    if book_details_no_isbn:
        save_json(BOOK_DETAILS_NO_ISBN_PATH, book_details_no_isbn)

    # Persist ISBNs discovered for no-epub-isbn books back to book_list and book_list_missing
    if isbn_discovered:
        updated = 0
        for entry in book_list:
            if not entry.get("isbn") and entry.get("title") in isbn_discovered:
                entry["isbn"] = isbn_discovered[entry["title"]]
                updated += 1
        for entry in book_list_missing:
            if not entry.get("isbn") and entry.get("title") in isbn_discovered:
                entry["isbn"] = isbn_discovered[entry["title"]]
                updated += 1
        if updated:
            save_json(BOOK_LIST_PATH, book_list)
            save_json(BOOK_LIST_MANUAL_ISBN_PATH, book_list_missing)
            print(f"\nUpdated {updated} ISBN(s) in book lists")

    covered = sum(1 for v in book_details.values() if v.get("coverUrl"))
    print(f"\nDone. {len(book_details)} entries in {BOOK_DETAILS_PATH.name}")
    print(f"  {covered}/{len(book_details)} have cover images")
    if book_details_no_isbn:
        print(f"\n{len(book_details_no_isbn)} book(s) written to {BOOK_DETAILS_NO_ISBN_PATH.name} (no ISBN found):")
        for entry in book_details_no_isbn:
            print(f"    - {entry['title']}")
        print("  Fill in the 'isbn' fields, add entries to book_list.json, then re-run to enrich.")
    print("\nNext step: run tag_books.py, then seed.ts.")


if __name__ == "__main__":
    main()
