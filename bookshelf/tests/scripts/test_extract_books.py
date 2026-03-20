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

    def test_no_isbn_book_written_to_manual_list_in_clean_mode(self, monkeypatch, epub_dir, paths):
        """In clean mode, a book with no ISBN should land in book_list_manual_isbn."""
        bundle, epub = epub_dir
        monkeypatch.setattr(sys, "argv", ["prog", str(bundle), "--mode", "clean"])

        with patch(f"{PATCH}.extract_epub_metadata", side_effect=lambda p: _meta(p, isbn=None)):
            with patch(f"{PATCH}.fetch_google_book", return_value=None):
                with patch(f"{PATCH}.extract_epub_cover", return_value=None):
                    with patch(f"{PATCH}.load_env_local", return_value={}):
                        main()

        assert paths["manual"].exists()
        manual = json.loads(paths["manual"].read_text())
        assert any(e["title"] == "Test Book" for e in manual)


# ---------------------------------------------------------------------------
# isbn_discovered — backfill to book lists
# ---------------------------------------------------------------------------

class TestIsbnDiscoveredBackfill:
    def test_isbn_discovered_backfills_both_book_list_and_book_list_missing(self, monkeypatch, epub_dir, paths):
        """Backfill updates both lists when step 3a misses but enrich_one discovers an isbn.

        step 3a returns None → entries keep empty isbn.
        enrich_one discovers isbn → isbn_discovered fires and fills both lists.
        """
        bundle, epub = epub_dir

        # book_list has an empty-isbn entry for this title
        paths["book_list"].write_text(json.dumps([
            {"isbn": "", "title": "Test Book", "title_raw": "Test Book"}
        ]))
        monkeypatch.setattr(sys, "argv", ["prog", str(bundle), "--mode", "overwrite"])

        # step 3a calls google first (miss), then enrich_one calls google (finds isbn)
        with patch(f"{PATCH}.extract_epub_metadata", side_effect=lambda p: _meta(p, isbn=None)):
            with patch(f"{PATCH}.fetch_google_book", side_effect=[None, _google_result(isbn="9780987654321")]):
                with patch(f"{PATCH}.extract_epub_cover", return_value=None):
                    with patch(f"{PATCH}.load_env_local", return_value={}):
                        main()

        book_list = json.loads(paths["book_list"].read_text())
        manual = json.loads(paths["manual"].read_text())
        assert "9780987654321" in [e.get("isbn") for e in book_list]
        assert "9780987654321" in [e.get("isbn") for e in manual]

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

# ---------------------------------------------------------------------------
# enrich_one — miss and discovery paths
# ---------------------------------------------------------------------------

class TestEnrichOne:
    def test_writes_partial_entry_when_google_misses_but_epub_has_isbn(self, monkeypatch, epub_dir, paths):
        """result is None + epub has isbn → partial entry written from epub metadata."""
        bundle, epub = epub_dir
        monkeypatch.setattr(sys, "argv", ["prog", str(bundle)])

        with patch(f"{PATCH}.extract_epub_metadata", side_effect=lambda p: _meta(p)):
            with patch(f"{PATCH}.fetch_google_book", return_value=None):
                with patch(f"{PATCH}.extract_epub_cover", return_value=None):
                    with patch(f"{PATCH}.load_env_local", return_value={}):
                        main()

        saved = json.loads(paths["book_details"].read_text())
        assert "9781234567890" in saved
        assert saved["9781234567890"]["title"] == "Test Book"
        assert saved["9781234567890"]["author"] == "Test Author"

    def test_skips_book_when_google_returns_result_with_no_isbn_and_epub_has_no_isbn(self, monkeypatch, epub_dir, paths):
        """result returned but isbn absent from both epub and Google response → nothing written."""
        bundle, epub = epub_dir
        monkeypatch.setattr(sys, "argv", ["prog", str(bundle)])

        with patch(f"{PATCH}.extract_epub_metadata", side_effect=lambda p: _meta(p, isbn=None)):
            with patch(f"{PATCH}.fetch_google_book", return_value=_google_result(isbn=None)):
                with patch(f"{PATCH}.extract_epub_cover", return_value=None):
                    with patch(f"{PATCH}.load_env_local", return_value={}):
                        main()

        assert json.loads(paths["book_details"].read_text()) == {}

    def test_isbn_discovered_by_google_backfilled_into_book_list_missing(self, monkeypatch, epub_dir, paths):
        """epub has no isbn but Google finds one → isbn_discovered backfills book_list_missing.

        Uses --mode overwrite so enrich_one always runs even after step 3a has already
        processed the same book via the manual-isbn-recovery path.
        """
        bundle, epub = epub_dir
        monkeypatch.setattr(sys, "argv", ["prog", str(bundle), "--mode", "overwrite"])

        with patch(f"{PATCH}.extract_epub_metadata", side_effect=lambda p: _meta(p, isbn=None)):
            with patch(f"{PATCH}.fetch_google_book", return_value=_google_result(isbn="9780987654321")):
                with patch(f"{PATCH}.extract_epub_cover", return_value=None):
                    with patch(f"{PATCH}.load_env_local", return_value={}):
                        main()

        manual = json.loads(paths["manual"].read_text())
        isbns = [e.get("isbn") for e in manual]
        assert "9780987654321" in isbns


# ---------------------------------------------------------------------------
# Epub scan — extraction failures
# ---------------------------------------------------------------------------

class TestEpubScan:
    def test_skips_epub_when_metadata_extraction_returns_none(self, monkeypatch, epub_dir, paths):
        """An epub that yields no metadata should be silently skipped."""
        bundle, epub = epub_dir
        monkeypatch.setattr(sys, "argv", ["prog", str(bundle), "--list-only"])

        with patch(f"{PATCH}.extract_epub_metadata", return_value=None):
            with patch(f"{PATCH}.load_env_local", return_value={}):
                main()

        # Nothing extracted — book_list should be empty
        book_list = json.loads(paths["book_list"].read_text())
        assert book_list == []


# ---------------------------------------------------------------------------
# CLI arg handling — --bundle, --all, folder validation
# ---------------------------------------------------------------------------

class TestCLIArgs:
    def test_bundle_flag_missing_books_dir_returns_early(self, monkeypatch, paths):
        """--bundle with no BOOKS_DIR in env should print an error and return."""
        monkeypatch.setattr(sys, "argv", ["prog", "--bundle", "My Bundle"])

        with patch(f"{PATCH}.load_env_local", return_value={}):
            main()

        assert not paths["book_details"].exists()

    def test_all_flag_missing_book_bundles_returns_early(self, monkeypatch, tmp_path, paths):
        """--all with BOOKS_DIR set but no BOOK_BUNDLES should print an error and return."""
        monkeypatch.setattr(sys, "argv", ["prog", "--all"])

        with patch(f"{PATCH}.load_env_local", return_value={"BOOKS_DIR": str(tmp_path)}):
            main()

        assert not paths["book_details"].exists()

    def test_bundle_flag_resolves_folder_from_books_dir(self, monkeypatch, tmp_path, paths):
        """--bundle NAME resolves to BOOKS_DIR/NAME and processes epubs there."""
        bundle = tmp_path / "My Bundle"
        bundle.mkdir()
        (bundle / "book.epub").write_bytes(b"")

        monkeypatch.setattr(sys, "argv", ["prog", "--bundle", "My Bundle"])

        with patch(f"{PATCH}.extract_epub_metadata", side_effect=lambda p: _meta(p)):
            with patch(f"{PATCH}.fetch_google_book", return_value=_google_result()):
                with patch(f"{PATCH}.extract_epub_cover", return_value=None):
                    with patch(f"{PATCH}.load_env_local", return_value={"BOOKS_DIR": str(tmp_path)}):
                        main()

        assert paths["book_details"].exists()

    def test_all_flag_scans_each_bundle_listed_in_book_bundles(self, monkeypatch, tmp_path, paths):
        """--all iterates all bundle names in BOOK_BUNDLES and processes epubs in each."""
        for name in ("Bundle A", "Bundle B"):
            d = tmp_path / name
            d.mkdir()
            (d / "book.epub").write_bytes(b"")

        monkeypatch.setattr(sys, "argv", ["prog", "--all"])

        with patch(f"{PATCH}.extract_epub_metadata", side_effect=lambda p: _meta(p)):
            with patch(f"{PATCH}.fetch_google_book", return_value=_google_result()):
                with patch(f"{PATCH}.extract_epub_cover", return_value=None):
                    with patch(f"{PATCH}.load_env_local", return_value={
                        "BOOKS_DIR": str(tmp_path),
                        "BOOK_BUNDLES": "Bundle A, Bundle B",
                    }):
                        main()

        assert paths["book_details"].exists()

    def test_nonexistent_folder_returns_early(self, monkeypatch, tmp_path, paths):
        """A folder path that doesn't exist should print an error and return."""
        missing = tmp_path / "does_not_exist"
        monkeypatch.setattr(sys, "argv", ["prog", str(missing)])

        with patch(f"{PATCH}.load_env_local", return_value={}):
            main()

        assert not paths["book_details"].exists()


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
