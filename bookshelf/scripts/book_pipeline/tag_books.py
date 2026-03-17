#!/usr/bin/env python3
"""
Generate AI tags for books in book_details.json using the Anthropic API.

Usage:
    python scripts/tag_books.py                       # tag all untagged books
    python scripts/tag_books.py --isbn 9781234567890  # tag/retag one book
    python scripts/tag_books.py --clean               # retag all books

Two-pass approach:

    Pass 1 — per-book tagging (concurrent, max 5 workers):
        For each book without ai_tags (or all books with --clean, or the
        specified book with --isbn), call the Anthropic API with the book's
        title and description and store the returned tags as ai_tags.

    Pass 2 — vocabulary derivation + assignment:
        Send all candidate tags (keyed by ISBN) to the API. The model
        derives a controlled vocabulary of 10-20 broad tags and assigns
        1-3 final tags per book. Existing tags from unchanged books are
        passed as context so new assignments stay consistent.
        Existing ai_tags are never renamed — only Pass 1 books are updated.

    ┌─────────────────────┐
    │  book_details.json  │
    └────────┬────────────┘
             │ load
             ▼
    ┌─────────────────────────────────────────────────┐
    │  Pass 1: tag each book (ThreadPoolExecutor x5)  │
    │  skip if ai_tags present (unless --isbn/--clean)│
    │  generates 3-8 raw candidate tags per book      │
    └────────┬────────────────────────────────────────┘
             │ intermediate save
             ▼
    ┌──────────────────────────────────────────────────────────┐
    │  Pass 2: vocabulary derivation + assignment              │
    │  candidates by ISBN → Anthropic → vocabulary (10-20)    │
    │  + assignments (1-3 tags per book)                       │
    │  existing ai_tags passed as context; never renamed       │
    └────────┬─────────────────────────────────────────────────┘
             │ final save + tag summary
             ▼
    ┌─────────────────────┐
    │  book_details.json  │
    └─────────────────────┘

Requires:
    pip install anthropic
    ANTHROPIC_API_KEY set in .env.local
"""

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic

from .utils import BOOK_DETAILS_PATH, load_env_local, load_json, save_json

MODEL = "claude-haiku-4-5-20251001"


def _strip_fences(text: str) -> str:
    """Strip markdown code fences from a response string."""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*\n?', '', text)
    text = re.sub(r'\n?```\s*$', '', text)
    return text.strip()


def parse_tag_response(text: str) -> list[str]:
    """
    Parse a JSON list of tags from an API response.
    Handles markdown fences and preamble text gracefully.
    Returns [] on any parse failure — never raises.
    """
    stripped = _strip_fences(text)
    match = re.search(r'\[.*\]', stripped, re.DOTALL)
    if match:
        stripped = match.group()
    try:
        result = json.loads(stripped)
        if isinstance(result, list) and all(isinstance(t, str) for t in result):
            return [t.strip() for t in result if t.strip()]
        print(f"  [warn] unexpected tag response shape: {type(result)}")
        return []
    except json.JSONDecodeError:
        print(f"  [warn] could not parse tag response: {text[:100]!r}")
        return []


def parse_normalization_response(text: str) -> dict:
    """
    Parse the normalization response.
    Expected shape: {"vocabulary": [str, ...], "assignments": {isbn: [str, ...]}}
    Handles markdown fences and preamble text gracefully.
    Returns {} on any parse failure — never raises.
    """
    stripped = _strip_fences(text)
    match = re.search(r'\{.*\}', stripped, re.DOTALL)
    if match:
        stripped = match.group()
    try:
        result = json.loads(stripped)
        if (
            isinstance(result, dict)
            and isinstance(result.get("vocabulary"), list)
            and isinstance(result.get("assignments"), dict)
        ):
            return result
        print(f"  [warn] unexpected normalization response shape: {type(result)}")
        return {}
    except json.JSONDecodeError:
        print(f"  [warn] could not parse normalization response: {text[:100]!r}")
        return {}


def build_tag_prompt(title: str, description: str) -> str:
    """Build the tagging prompt for a single book."""
    desc_section = f"\nDescription: {description}" if description else ""
    return (
        "You are tagging books for a personal technical library browsed by people in the tech industry — "
        "software engineers, architects, and hiring managers.\n\n"
        "Generate as few tags as accurately describe this book's main topics. "
        "Most books need 2-4. Never exceed 6. "
        "Tags should be short (1-4 words), lowercase, and reflect the main subjects covered. "
        "Be specific — these candidates will be normalized into broader categories later.\n\n"
        f"Title: {title}{desc_section}\n\n"
        'Respond with ONLY a JSON array of strings. Example: ["machine learning", "python", "neural networks", "data pipelines"]'
    )


def build_normalization_prompt(
    candidate_tags_by_isbn: dict[str, list[str]],
    existing_vocabulary: list[str],
) -> str:
    """Build the vocabulary derivation and assignment prompt for Pass 2."""
    candidates_str = json.dumps(candidate_tags_by_isbn, indent=2)
    vocab_section = (
        f"\nExisting tags already in use in this library (reuse these where appropriate):\n{json.dumps(existing_vocabulary)}\n"
        if existing_vocabulary else ""
    )
    return (
        "You are building a tag vocabulary for a personal technical library displayed as filter buttons in a UI. "
        "The audience is people in the tech industry — software engineers, architects, and hiring managers.\n\n"
        f"Here are candidate tags generated for books that need final tag assignment (keyed by ISBN):\n{candidates_str}\n"
        f"{vocab_section}\n"
        "Your job:\n"
        "1. Derive a controlled vocabulary of 10-20 tags that cover these books well. "
        "Tags should be broad enough that multiple books share them — if fewer than 3 books would share a tag, "
        "it is probably too specific. Use standard acronyms where widely recognised (RAG, LLM, SQL, REST, AI). "
        "Incorporate existing tags where appropriate.\n"
        "2. Assign each book 1-3 tags from your vocabulary.\n\n"
        "Respond with ONLY a JSON object in this exact format:\n"
        '{\n  "vocabulary": ["tag1", "tag2", ...],\n'
        '  "assignments": {"isbn": ["tag1"], "isbn2": ["tag1", "tag2"], ...}\n}'
    )


def tag_book(book: dict, client: anthropic.Anthropic, retries: int = 2, retry_delay: float = 5.0) -> list[str]:
    """Call the Anthropic API to generate tags for a single book."""
    prompt = build_tag_prompt(book.get("title", ""), book.get("description", ""))
    title = book.get("title", "unknown")
    for attempt in range(retries + 1):
        try:
            message = client.messages.create(
                model=MODEL,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            return parse_tag_response(message.content[0].text)
        except Exception as e:
            if attempt < retries:
                print(f"  [retry {attempt + 1}/{retries}] {title}: {e} — waiting {retry_delay}s")
                time.sleep(retry_delay)
            else:
                print(f"  [warn] API call failed for {title}: {e}")
                return []
    return []


def apply_tag_assignments(
    book_details: dict,
    assignments: dict[str, list[str]],
    isbn_filter: set[str],
) -> int:
    """
    Apply final tag assignments directly to books.
    Only books whose ISBNs are in isbn_filter are touched.
    Returns the number of books updated.
    """
    updated = 0
    for isbn in isbn_filter:
        if isbn not in assignments:
            print(f"  [warn] no assignment returned for ISBN {isbn}")
            continue
        tags = assignments[isbn]
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            print(f"  [warn] invalid assignment for ISBN {isbn}: {tags}")
            continue
        book_details[isbn]["ai_tags"] = tags
        updated += 1
    return updated


def print_tag_summary(book_details: dict) -> None:
    """Print each tag in the library and how many books carry it, sorted by count."""
    from collections import Counter
    tag_counts: Counter = Counter()
    for book in book_details.values():
        for tag in book.get("ai_tags", []):
            tag_counts[tag] += 1
    if not tag_counts:
        return
    print("\nTag summary:")
    for tag, count in sorted(tag_counts.items(), key=lambda x: (-x[1], x[0])):
        print(f"  {tag:<35} {count} book(s)")


def main():
    parser = argparse.ArgumentParser(
        description="Generate AI tags for books using the Anthropic API."
    )
    parser.add_argument(
        "--isbn",
        metavar="ISBN",
        help="Tag (or retag) a single book by ISBN, overwriting any existing ai_tags",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Retag all books, overwriting existing ai_tags",
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="Skip Pass 1 and run normalization on all currently tagged books",
    )
    args = parser.parse_args()

    env = load_env_local()
    api_key = env.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set in .env.local")
        sys.exit(1)

    if not BOOK_DETAILS_PATH.exists():
        print(f"Error: {BOOK_DETAILS_PATH} not found. Run extract_books.py first.")
        sys.exit(1)

    book_details = load_json(BOOK_DETAILS_PATH, {})
    if not book_details:
        print("No books found in book_details.json.")
        return

    client = anthropic.Anthropic(api_key=api_key)

    # Determine which books to tag in Pass 1
    if args.isbn:
        if args.isbn not in book_details:
            print(f"Error: ISBN {args.isbn} not found in book_details.json")
            sys.exit(1)
        to_tag = {args.isbn: book_details[args.isbn]}
    elif args.clean:
        to_tag = dict(book_details)
    else:
        to_tag = {
            isbn: book
            for isbn, book in book_details.items()
            if not book.get("ai_tags")
        }

    skipped = len(book_details) - len(to_tag)
    if skipped and not args.clean and not args.isbn:
        print(f"Skipping {skipped} already-tagged book(s). Use --clean to retag all.")

    if args.normalize:
        # Skip Pass 1 — build new_tags_by_isbn from all currently tagged books
        new_tags_by_isbn = {
            isbn: book["ai_tags"]
            for isbn, book in book_details.items()
            if book.get("ai_tags")
        }
        if not new_tags_by_isbn:
            print("No books have ai_tags yet. Run without --normalize first.")
            return
        existing_vocabulary = set()
        print(f"\nForcing normalization on {len(new_tags_by_isbn)} tagged book(s)...")
    else:
        if not to_tag:
            print("Nothing to tag.")
            return

        # Collect existing vocabulary from books NOT being retagged
        existing_vocabulary = set()
        for isbn, book in book_details.items():
            if isbn not in to_tag and book.get("ai_tags"):
                existing_vocabulary.update(book["ai_tags"])

        print(f"\nTagging {len(to_tag)} book(s)...")

    if not args.normalize:
        # Pass 1: tag each book concurrently
        def tag_one(isbn: str, book: dict) -> tuple[str, list[str]]:
            tags = tag_book(book, client)
            if tags:
                print(f"  [ok]   {book.get('title', isbn)}: {tags}")
            else:
                print(f"  [miss] {book.get('title', isbn)}: no tags generated")
            return isbn, tags

        new_tags_by_isbn = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(tag_one, isbn, book): isbn
                for isbn, book in to_tag.items()
            }
            for f in as_completed(futures):
                isbn, tags = f.result()
                if tags:
                    book_details[isbn]["ai_tags"] = tags
                    new_tags_by_isbn[isbn] = tags

        # Intermediate save — preserve Pass 1 results before Pass 2
        save_json(BOOK_DETAILS_PATH, book_details)
        print(f"\nPass 1 complete. Tagged {len(new_tags_by_isbn)}/{len(to_tag)} book(s).")

        if not new_tags_by_isbn:
            print("No tags generated — skipping normalization.")
            return

    # Pass 2: derive vocabulary and assign 1-3 final tags per book
    print(
        f"\nDeriving vocabulary and assigning final tags for "
        f"{len(new_tags_by_isbn)} book(s) "
        f"({len(existing_vocabulary)} existing tag(s) as context)..."
    )

    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=8192,
            messages=[{
                "role": "user",
                "content": build_normalization_prompt(
                    new_tags_by_isbn, sorted(existing_vocabulary)
                ),
            }],
        )
        result = parse_normalization_response(message.content[0].text)
    except Exception as e:
        print(f"  [warn] normalization API call failed: {e}")
        result = {}

    if not result:
        print("  [warn] No normalization result returned — skipping.")
        return

    vocabulary = result.get("vocabulary", [])
    assignments = result.get("assignments", {})
    print(f"Vocabulary ({len(vocabulary)} tags): {vocabulary}")

    updated = apply_tag_assignments(
        book_details, assignments, set(new_tags_by_isbn.keys())
    )

    save_json(BOOK_DETAILS_PATH, book_details)
    print(f"\nDone. {updated} book(s) assigned final tags.")
    print_tag_summary(book_details)


if __name__ == "__main__":
    main()
