"""
Shape contract tests: ensure book_details.json entries match the Book type in lib/books.ts.

TypeScript Book type (for reference):
  id: string           — required
  title: string        — required
  author: string       — required
  isbn: string         — required
  year: number | null  — required, nullable
  tags: string[]       — required
  ai_tags?: string[]   — optional (pipeline always writes it for consistency)
  description: string  — required
  coverUrl?: string    — optional
  votes: number        — added at seed time, not present in book_details.json

Any change to the entry structure written by extract_books.py should be reflected here.
"""

import pytest


REQUIRED_STR_FIELDS = ["id", "title", "author", "isbn", "description"]
REQUIRED_LIST_FIELDS = ["tags", "ai_tags"]
OPTIONAL_STR_FIELDS = ["coverUrl"]


def assert_book_shape(entry: dict) -> None:
    for field in REQUIRED_STR_FIELDS:
        assert field in entry, f"Missing required field: '{field}'"
        assert isinstance(entry[field], str), f"'{field}' must be str, got {type(entry[field]).__name__}"

    assert "year" in entry, "Missing required field: 'year'"
    assert entry["year"] is None or isinstance(entry["year"], int), \
        f"'year' must be int or None, got {type(entry['year']).__name__}"

    for field in REQUIRED_LIST_FIELDS:
        assert field in entry, f"Missing required field: '{field}'"
        assert isinstance(entry[field], list), f"'{field}' must be list, got {type(entry[field]).__name__}"

    for field in OPTIONAL_STR_FIELDS:
        if entry.get(field) is not None:
            assert isinstance(entry[field], str), f"'{field}' must be str or None, got {type(entry[field]).__name__}"


class TestBookEntryShape:
    def test_ok_path_entry(self):
        """Entry written by enrich_one when Google Books returns a result."""
        entry = {
            "id": "abc-123",
            "title": "Designing Data-Intensive Applications",
            "author": "Martin Kleppmann",
            "isbn": "9781449373320",
            "year": 2017,
            "tags": [],
            "ai_tags": [],
            "description": "A book about data systems.",
            "coverUrl": "/covers/9781449373320.jpg",
        }
        assert_book_shape(entry)

    def test_miss_path_entry(self):
        """Entry written by enrich_one when Google Books returns no result but epub has an ISBN."""
        entry = {
            "id": "def-456",
            "title": "Some Obscure Book",
            "author": "Unknown",
            "isbn": "9781234567890",
            "year": None,
            "tags": [],
            "ai_tags": [],
            "description": "",
            "coverUrl": None,
        }
        assert_book_shape(entry)

    def test_step3a_entry(self):
        """Entry written by Step 3a (manual ISBN enrichment path)."""
        entry = {
            "id": "ghi-789",
            "title": "Building Agentic AI Systems",
            "author": "Some Author",
            "isbn": "9781803238753",
            "year": 2024,
            "tags": [],
            "ai_tags": [],
            "description": "A book about agentic AI.",
            "coverUrl": None,
        }
        assert_book_shape(entry)

    def test_missing_required_string_field_fails(self):
        entry = {
            "id": "abc-123",
            "title": "Test Book",
            # missing author, isbn, description
            "year": 2020,
            "tags": [],
            "ai_tags": [],
        }
        with pytest.raises(AssertionError):
            assert_book_shape(entry)

    def test_missing_ai_tags_fails(self):
        """ai_tags must always be present — the pipeline always writes it."""
        entry = {
            "id": "abc-123",
            "title": "Test Book",
            "author": "Test Author",
            "isbn": "9781234567890",
            "year": 2020,
            "tags": [],
            "description": "",
        }
        with pytest.raises(AssertionError):
            assert_book_shape(entry)

    def test_year_none_is_valid(self):
        entry = {
            "id": "abc-123",
            "title": "Test Book",
            "author": "Test Author",
            "isbn": "9781234567890",
            "year": None,
            "tags": [],
            "ai_tags": [],
            "description": "",
        }
        assert_book_shape(entry)

    def test_year_wrong_type_fails(self):
        entry = {
            "id": "abc-123",
            "title": "Test Book",
            "author": "Test Author",
            "isbn": "9781234567890",
            "year": "2020",  # string, not int
            "tags": [],
            "ai_tags": [],
            "description": "",
        }
        with pytest.raises(AssertionError):
            assert_book_shape(entry)
