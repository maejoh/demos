#!/usr/bin/env python3
"""
Generate AI tags for books in book_details.json using the Anthropic API.

Usage:
    python -m scripts.book_pipeline.tag_books          # build vocabulary + tag untagged books
    python -m scripts.book_pipeline.tag_books --clean  # rebuild vocabulary + retag all books
    python -m scripts.book_pipeline.tag_books --normalize  # skip Pass 1, reassign from existing vocabulary
    python -m scripts.book_pipeline.tag_books --isbn 9781234567890  # retag one book

Two-pass approach:

    Pass 1 — vocabulary discovery (one API call, all titles):
        Send all book titles to the model. It extracts every specific
        language/tool/library/framework mentioned by name, plus 5-10
        broader topic categories (e.g. "Web Development", "Databases").
        Returns a canonical tag list for the whole library.

    Pass 2 — bulk assignment (one API call, all books):
        Send all books (title + description) alongside the canonical
        vocabulary. The model assigns 1-3 tags per book from the list.

    ┌─────────────────────┐
    │  book_details.json  │
    └────────┬────────────┘
             │ load
             ▼
    ┌─────────────────────────────────────────────────┐
    │  Pass 1: vocabulary discovery (single API call) │
    │  all titles → canonical tag list                │
    └────────┬────────────────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────────────────────────┐
    │  Pass 2: bulk assignment (single API call)               │
    │  all books + canonical vocabulary → assignments by ISBN  │
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

import anthropic

from .utils import BOOK_DETAILS_PATH, load_env_local, load_json, save_json

MODEL = "claude-haiku-4-5-20251001"


def _strip_fences(text: str) -> str:
    """Strip markdown code fences from a response string."""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*\n?', '', text)
    text = re.sub(r'\n?```\s*$', '', text)
    return text.strip()


def parse_json_list(text: str) -> list[str]:
    """
    Parse a JSON array of strings from response text.
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
        print(f"  [warn] unexpected response shape: {type(result)}")
        return []
    except json.JSONDecodeError:
        print(f"  [warn] could not parse response: {text[:100]!r}")
        return []


def parse_assignments(text: str) -> dict[str, list[str]]:
    """
    Parse a JSON object of {isbn: [tags]} from response text.
    Handles markdown fences and preamble text gracefully.
    Returns {} on any parse failure — never raises.
    """
    stripped = _strip_fences(text)
    match = re.search(r'\{.*\}', stripped, re.DOTALL)
    if match:
        stripped = match.group()
    try:
        result = json.loads(stripped)
        if isinstance(result, dict):
            return result
        print(f"  [warn] unexpected assignments shape: {type(result)}")
        return {}
    except json.JSONDecodeError:
        print(f"  [warn] could not parse assignments: {text[:100]!r}")
        return {}


def build_vocabulary_prompt(titles: list[str]) -> str:
    """Build the Pass 1 prompt: discover a canonical tag vocabulary from all book titles."""
    titles_xml = "\n".join(f"  <title>{t}</title>" for t in titles)
    return (
        "You are building a tag vocabulary for a personal technical library. "
        "The audience is software engineers, architects, and hiring managers.\n\n"
        "Here are all the book titles in the library:\n"
        f"<titles>\n{titles_xml}\n</titles>\n\n"
        "Your task:\n"
        "1. Extract every specific programming language, tool, library, or framework "
        "mentioned by name in these titles (e.g. Python, LangChain, Kubernetes, SQL).\n"
        "2. Identify 5-10 broader topic categories that meaningfully group the library "
        "(e.g. Web Development, Machine Learning, Databases, Software Architecture). "
        "Only include a category if at least 3 books would share it.\n\n"
        "Rules:\n"
        "- Use standard capitalisation and acronyms (Python, LLM, SQL, REST, RAG, AI)\n"
        "- Do not duplicate specific tools as broad categories "
        "(e.g. don't list both 'PyTorch' and 'Deep Learning Frameworks')\n"
        "- Total tag count should be 20-40\n\n"
        "Respond with ONLY a JSON array of strings.\n"
        'Example: ["Python", "LangChain", "Machine Learning", "Databases", "Web Development"]'
    )


def build_assignment_prompt(books: dict, vocabulary: list[str]) -> str:
    """Build the Pass 2 prompt: assign tags from the canonical vocabulary to each book."""
    books_xml = "\n".join(
        f'  <book isbn="{isbn}">\n'
        f"    <title>{book.get('title', '')}</title>\n"
        + (f"    <description>{book.get('description', '')[:300]}</description>\n" if book.get('description') else "")
        + "  </book>"
        for isbn, book in books.items()
    )
    vocab_json = json.dumps(vocabulary)
    return (
        "You are assigning tags to books in a personal technical library. "
        "The audience is software engineers, architects, and hiring managers.\n\n"
        "Here are the books to tag:\n"
        f"<library>\n{books_xml}\n</library>\n\n"
        f"Canonical tag vocabulary (assign ONLY tags from this list):\n{vocab_json}\n\n"
        "Rules:\n"
        "- Assign 1-3 tags per book\n"
        "- Only use tags from the vocabulary above — never invent new ones\n"
        "- Prefer specific tags (e.g. 'Python') over broad ones (e.g. 'Programming') "
        "when the title makes it explicit\n"
        "- A book may get one specific and one broad tag "
        "(e.g. ['Machine Learning', 'PyTorch'])\n\n"
        "Example output:\n"
        '{"9780000000001": ["Python", "Web Development"], "9780000000002": ["Machine Learning"]}\n\n'
        "Respond with ONLY a JSON object mapping each ISBN to its list of tags."
    )


def tag_single_book(
    book: dict,
    isbn: str,
    vocabulary: list[str],
    client: anthropic.Anthropic,
    retries: int = 2,
    retry_delay: float = 5.0,
) -> list[str]:
    """Assign tags to a single book from a known vocabulary."""
    prompt = build_assignment_prompt({isbn: book}, vocabulary)
    title = book.get("title", isbn)
    for attempt in range(retries + 1):
        try:
            message = client.messages.create(
                model=MODEL,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            assignments = parse_assignments(message.content[0].text)
            return assignments.get(isbn, [])
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
    Apply final tag assignments to books.
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
        help="Tag (or retag) a single book by ISBN using existing vocabulary",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Rebuild vocabulary and retag all books",
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="Skip Pass 1 and reassign tags using vocabulary derived from already-tagged books",
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

    # --- Pass 1: vocabulary discovery ---
    if args.isbn or args.normalize:
        # Use vocabulary derived from already-tagged books
        vocabulary = sorted({
            tag
            for book in book_details.values()
            for tag in book.get("ai_tags", [])
        })
        if not vocabulary:
            print("No existing vocabulary found. Run without --isbn/--normalize first.")
            sys.exit(1)
        print(f"Using existing vocabulary ({len(vocabulary)} tags): {vocabulary}")
    else:
        titles = [book.get("title", "") for book in book_details.values() if book.get("title")]
        print(f"\nPass 1: discovering vocabulary from {len(titles)} book titles...")
        try:
            message = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": build_vocabulary_prompt(titles)}],
            )
            vocabulary = parse_json_list(message.content[0].text)
        except Exception as e:
            print(f"  [error] vocabulary API call failed: {e}")
            sys.exit(1)
        if not vocabulary:
            print("  [error] No vocabulary returned — aborting.")
            sys.exit(1)
        print(f"Vocabulary ({len(vocabulary)} tags): {vocabulary}")

    # --- Pass 2: assignment ---
    if args.isbn:
        if args.isbn not in book_details:
            print(f"Error: ISBN {args.isbn} not found in book_details.json")
            sys.exit(1)
        book = book_details[args.isbn]
        print(f"\nTagging {book.get('title', args.isbn)}...")
        tags = tag_single_book(book, args.isbn, vocabulary, client)
        if tags:
            book_details[args.isbn]["ai_tags"] = tags
            print(f"  [ok]   {book.get('title', args.isbn)}: {tags}")
        else:
            print(f"  [miss] {book.get('title', args.isbn)}: no tags assigned")
        save_json(BOOK_DETAILS_PATH, book_details)
        return

    to_tag = dict(book_details) if (args.clean or args.normalize) else {
        isbn: book for isbn, book in book_details.items() if not book.get("ai_tags")
    }

    if not to_tag:
        print("\nAll books already tagged. Use --clean to retag all.")
        print_tag_summary(book_details)
        return

    skipped = len(book_details) - len(to_tag)
    if skipped:
        print(f"Skipping {skipped} already-tagged book(s). Use --clean to retag all.")

    print(f"\nPass 2: assigning tags to {len(to_tag)} book(s)...")
    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=8192,
            messages=[{"role": "user", "content": build_assignment_prompt(to_tag, vocabulary)}],
        )
        assignments = parse_assignments(message.content[0].text)
    except Exception as e:
        print(f"  [error] assignment API call failed: {e}")
        sys.exit(1)

    updated = apply_tag_assignments(book_details, assignments, set(to_tag.keys()))
    save_json(BOOK_DETAILS_PATH, book_details)
    print(f"\nDone. {updated} book(s) assigned final tags.")
    print_tag_summary(book_details)


if __name__ == "__main__":
    main()
