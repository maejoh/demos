"""
Tests for scripts/book_pipeline/extract_books.py.

All external calls (extract_epub_metadata, fetch_google_book, extract_epub_cover,
load_env_local) are mocked. Output path constants are monkeypatched to temp
directories so real file I/O can be inspected without touching the project.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.book_pipeline.extract_books import main

PATCH = "scripts.book_pipeline.extract_books"


def _meta(epub_path: Path, title="Test Book", author="Test Author", isbn="9781234567890", year=2020) -> dict:
    """Minimal metadata dict as returned by extract_epub_metadata."""
    return {"title": title, "author": author, "isbn": isbn, "year": year, "epub_path": epub_path}


def _google_result(isbn="9781234567890", title="Test Book", author="Test Author", year=2020, desc="") -> dict:
    return {"isbn": isbn, "title": title, "author": author, "year": year, "description": desc}


@pytest.fixture
def epub_dir(tmp_path) -> tuple[Path, Path]:
    """A temp bundle folder with one empty .epub file."""
    bundle = tmp_path / "My Bundle"
    bundle.mkdir()
    epub = bundle / "test_book.epub"
    epub.write_bytes(b"")
    return bundle, epub


@pytest.fixture
def paths(tmp_path, monkeypatch) -> dict[str, Path]:
    """Patch all output path constants to temp paths and return them."""
    import scripts.book_pipeline.extract_books as eb_mod

    book_list = tmp_path / "book_list.json"
    book_details = tmp_path / "book_details.json"
    manual = tmp_path / "book_list_manual_isbn.json"

    monkeypatch.setattr(eb_mod, "BOOK_LIST_PATH", book_list)
    monkeypatch.setattr(eb_mod, "BOOK_DETAILS_PATH", book_details)
    monkeypatch.setattr(eb_mod, "BOOK_LIST_MANUAL_ISBN_PATH", manual)

    return {"book_list": book_list, "book_details": book_details, "manual": manual}


# ---------------------------------------------------------------------------
# Fast mode — skip logic
# ---------------------------------------------------------------------------

class TestFastModeSkipLogic:
    def test_skips_book_whose_isbn_is_already_in_book_details(self, monkeypatch, epub_dir, paths):
        bundle, epub = epub_dir

        paths["book_details"].write_text(json.dumps({
            "9781234567890": {"id": "1", "title": "Test Book", "author": "Author",
                              "isbn": "9781234567890", "year": 2020, "tags": [],
                              "ai_tags": [], "description": "", "coverUrl": None, "humbleBundle": "My Bundle"}
        }))
        monkeypatch.setattr(sys, "argv", ["prog", str(bundle)])

        with patch(f"{PATCH}.extract_epub_metadata", side_effect=lambda p: _meta(p)):
            with patch(f"{PATCH}.fetch_google_book") as mock_fetch:
                with patch(f"{PATCH}.extract_epub_cover", return_value=None):
                    with patch(f"{PATCH}.load_env_local", return_value={}):
                        main()

        mock_fetch.assert_not_called()

    def test_skips_book_via_title_raw_lookup_in_book_list(self, monkeypatch, epub_dir, paths):
        """
        Regression: a book with no epub ISBN that was previously enriched via
        book_list (title_raw → isbn mapping) should not be re-enriched.

        This simulates the steady state after a first run where isbn_discovered
        backfilled the isbn into both book_list and book_list_manual_isbn.
        """
        bundle, epub = epub_dir

        # Both lists have the isbn filled in, reflecting the post-backfill state
        paths["book_list"].write_text(json.dumps([
            {"isbn": "9780000000001", "title": "Test Book", "title_raw": "Test Book"}
        ]))
        paths["manual"].write_text(json.dumps([
            {"isbn": "9780000000001", "title": "Test Book", "title_raw": "Test Book"}
        ]))
        paths["book_details"].write_text(json.dumps({
            "9780000000001": {"id": "1", "title": "Test Book", "author": "Author",
                              "isbn": "9780000000001", "year": 2020, "tags": [],
                              "ai_tags": [], "description": "", "coverUrl": None, "humbleBundle": "My Bundle"}
        }))
        monkeypatch.setattr(sys, "argv", ["prog", str(bundle)])

        # Epub has no ISBN
        with patch(f"{PATCH}.extract_epub_metadata", side_effect=lambda p: _meta(p, isbn=None)):
            with patch(f"{PATCH}.fetch_google_book") as mock_fetch:
                with patch(f"{PATCH}.extract_epub_cover", return_value=None):
                    with patch(f"{PATCH}.load_env_local", return_value={}):
                        main()

        mock_fetch.assert_not_called()

    def test_enriches_new_book_not_yet_in_book_details(self, monkeypatch, epub_dir, paths):
        bundle, epub = epub_dir
        monkeypatch.setattr(sys, "argv", ["prog", str(bundle)])

        with patch(f"{PATCH}.extract_epub_metadata", side_effect=lambda p: _meta(p)):
            with patch(f"{PATCH}.fetch_google_book", return_value=_google_result()):
                with patch(f"{PATCH}.extract_epub_cover", return_value="/covers/9781234567890.jpg"):
                    with patch(f"{PATCH}.load_env_local", return_value={}):
                        main()

        saved = json.loads(paths["book_details"].read_text())
        assert "9781234567890" in saved
        assert saved["9781234567890"]["coverUrl"] == "/covers/9781234567890.jpg"


# ---------------------------------------------------------------------------
# --list-only flag
# ---------------------------------------------------------------------------

class TestListOnlyMode:
    def test_writes_book_list_but_skips_enrichment(self, monkeypatch, epub_dir, paths):
        bundle, epub = epub_dir
        monkeypatch.setattr(sys, "argv", ["prog", str(bundle), "--list-only"])

        with patch(f"{PATCH}.extract_epub_metadata", side_effect=lambda p: _meta(p)):
            with patch(f"{PATCH}.fetch_google_book") as mock_fetch:
                with patch(f"{PATCH}.load_env_local", return_value={}):
                    main()

        mock_fetch.assert_not_called()
        assert paths["book_list"].exists()
        assert not paths["book_details"].exists()

    def test_book_list_contains_extracted_isbn_and_title(self, monkeypatch, epub_dir, paths):
        bundle, epub = epub_dir
        monkeypatch.setattr(sys, "argv", ["prog", str(bundle), "--list-only"])

        with patch(f"{PATCH}.extract_epub_metadata", side_effect=lambda p: _meta(p)):
            with patch(f"{PATCH}.load_env_local", return_value={}):
                main()

        book_list = json.loads(paths["book_list"].read_text())
        assert len(book_list) == 1
        assert book_list[0]["isbn"] == "9781234567890"
        assert book_list[0]["title"] == "Test Book"


# ---------------------------------------------------------------------------
# --mode clean
# ---------------------------------------------------------------------------

class TestCleanMode:
    def test_deletes_existing_book_list_and_book_details_before_run(self, monkeypatch, epub_dir, paths):
        bundle, epub = epub_dir

        # Pre-create output files with stale data
        paths["book_list"].write_text(json.dumps([{"isbn": "0000000000", "title": "Old Book", "title_raw": "Old Book"}]))
        paths["book_details"].write_text(json.dumps({"0000000000": {"title": "Old Book"}}))

        monkeypatch.setattr(sys, "argv", ["prog", str(bundle), "--mode", "clean"])

        with patch(f"{PATCH}.extract_epub_metadata", side_effect=lambda p: _meta(p)):
            with patch(f"{PATCH}.fetch_google_book", return_value=_google_result()):
                with patch(f"{PATCH}.extract_epub_cover", return_value=None):
                    with patch(f"{PATCH}.load_env_local", return_value={}):
                        main()

        # book_list should only have the freshly scanned book, not the old stale entry
        book_list = json.loads(paths["book_list"].read_text())
        isbns = [e["isbn"] for e in book_list]
        assert "9781234567890" in isbns
        assert "0000000000" not in isbns

    def test_does_not_delete_book_list_manual_isbn(self, monkeypatch, epub_dir, paths):
        """--mode clean should preserve the manual ISBN cache."""
        bundle, epub = epub_dir

        manual_entry = [{"isbn": "9781111111111", "title": "Manual Book", "title_raw": "Manual Book"}]
        paths["manual"].write_text(json.dumps(manual_entry))

        monkeypatch.setattr(sys, "argv", ["prog", str(bundle), "--mode", "clean"])

        with patch(f"{PATCH}.extract_epub_metadata", side_effect=lambda p: _meta(p)):
            with patch(f"{PATCH}.fetch_google_book", return_value=_google_result()):
                with patch(f"{PATCH}.extract_epub_cover", return_value=None):
                    with patch(f"{PATCH}.load_env_local", return_value={}):
                        main()

        assert paths["manual"].exists()
        saved_manual = json.loads(paths["manual"].read_text())
        assert any(e["title"] == "Manual Book" for e in saved_manual)


# ---------------------------------------------------------------------------
# isbn_discovered — backfill to book lists
# ---------------------------------------------------------------------------

class TestIsbnDiscoveredBackfill:
    def test_updates_book_list_when_google_finds_isbn_for_no_isbn_epub(self, monkeypatch, epub_dir, paths):
        bundle, epub = epub_dir

        # book_list has this title but no isbn yet
        paths["book_list"].write_text(json.dumps([
            {"isbn": "", "title": "Test Book", "title_raw": "Test Book"}
        ]))
        monkeypatch.setattr(sys, "argv", ["prog", str(bundle)])

        # Epub has no ISBN; Google discovers one
        with patch(f"{PATCH}.extract_epub_metadata", side_effect=lambda p: _meta(p, isbn=None)):
            with patch(f"{PATCH}.fetch_google_book", return_value=_google_result(isbn="9780987654321")):
                with patch(f"{PATCH}.extract_epub_cover", return_value=None):
                    with patch(f"{PATCH}.load_env_local", return_value={}):
                        main()

        book_list = json.loads(paths["book_list"].read_text())
        isbns = [e.get("isbn") for e in book_list]
        assert "9780987654321" in isbns


# ---------------------------------------------------------------------------
# Manual ISBN recovery (book_list_manual_isbn.json → book_details)
# ---------------------------------------------------------------------------

class TestManualIsbnRecovery:
    def test_enriches_book_using_isbn_filled_into_manual_list(self, monkeypatch, epub_dir, paths):
        bundle, epub = epub_dir

        # Manual list has an isbn filled in for this title
        paths["manual"].write_text(json.dumps([
            {"isbn": "9781111111111", "title": "No ISBN Book", "title_raw": "No ISBN Book"}
        ]))
        monkeypatch.setattr(sys, "argv", ["prog", str(bundle)])

        # Epub has no ISBN, but manual list has it
        with patch(f"{PATCH}.extract_epub_metadata", side_effect=lambda p: _meta(p, title="No ISBN Book", isbn=None)):
            with patch(f"{PATCH}.fetch_google_book", return_value=_google_result(isbn="9781111111111", title="No ISBN Book")):
                with patch(f"{PATCH}.extract_epub_cover", return_value=None):
                    with patch(f"{PATCH}.load_env_local", return_value={}):
                        main()

        saved = json.loads(paths["book_details"].read_text())
        assert "9781111111111" in saved
        assert saved["9781111111111"]["title"] == "No ISBN Book"


# ---------------------------------------------------------------------------
# humbleBundle field
# ---------------------------------------------------------------------------

class TestHumbleBundleField:
    def test_humble_bundle_is_set_from_epub_parent_folder_name(self, monkeypatch, tmp_path, paths):
        bundle = tmp_path / "Humble Dev Bundle"
        bundle.mkdir()
        epub = bundle / "book.epub"
        epub.write_bytes(b"")

        monkeypatch.setattr(sys, "argv", ["prog", str(bundle)])

        with patch(f"{PATCH}.extract_epub_metadata", side_effect=lambda p: _meta(p)):
            with patch(f"{PATCH}.fetch_google_book", return_value=_google_result()):
                with patch(f"{PATCH}.extract_epub_cover", return_value=None):
                    with patch(f"{PATCH}.load_env_local", return_value={}):
                        main()

        saved = json.loads(paths["book_details"].read_text())
        assert saved["9781234567890"]["humbleBundle"] == "Humble Dev Bundle"
