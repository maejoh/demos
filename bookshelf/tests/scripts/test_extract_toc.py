"""Tests for scripts/book_pipeline/extract_toc.py."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.book_pipeline.extract_toc import main

PATCH = "scripts.book_pipeline.extract_toc"

SAMPLE_TOC = [
    {"title": "Chapter 1", "children": []},
    {"title": "Chapter 2", "children": [{"title": "Section 2.1", "children": []}]},
]


def _entry(isbn="9781234567890", title="Test Book", epub_path: str | None = None) -> dict:
    e = {"isbn": isbn, "title": title, "author": "Author"}
    if epub_path is not None:
        e["epub_path"] = epub_path
    return e


@pytest.fixture
def paths(tmp_path, monkeypatch):
    import scripts.book_pipeline.extract_toc as toc_mod

    book_details = tmp_path / "book_details.json"
    toc_dir = tmp_path / "toc"

    monkeypatch.setattr(toc_mod, "BOOK_DETAILS_PATH", book_details)
    monkeypatch.setattr(toc_mod, "TOC_DIR", toc_dir)

    return {"book_details": book_details, "toc_dir": toc_dir}


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------

class TestMain:
    def test_writes_toc_for_single_isbn(self, monkeypatch, tmp_path, paths):
        isbn = "9781234567890"
        epub = tmp_path / "test.epub"
        epub.write_bytes(b"")

        paths["book_details"].write_text(json.dumps({isbn: _entry(epub_path=str(epub))}))
        monkeypatch.setattr(sys, "argv", ["prog", isbn])

        with patch(f"{PATCH}.extract_epub_toc", return_value=SAMPLE_TOC):
            with patch(f"{PATCH}.load_env_local", return_value={}):
                main()

        out = paths["toc_dir"] / f"{isbn}.json"
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["isbn"] == isbn
        assert data["title"] == "Test Book"
        assert data["toc"] == SAMPLE_TOC

    def test_writes_toc_for_multiple_isbns(self, monkeypatch, tmp_path, paths):
        isbn1, isbn2 = "9781234567890", "9780987654321"
        epub1, epub2 = tmp_path / "a.epub", tmp_path / "b.epub"
        epub1.write_bytes(b"")
        epub2.write_bytes(b"")

        paths["book_details"].write_text(json.dumps({
            isbn1: _entry(isbn=isbn1, epub_path=str(epub1)),
            isbn2: _entry(isbn=isbn2, title="Other Book", epub_path=str(epub2)),
        }))
        monkeypatch.setattr(sys, "argv", ["prog", isbn1, isbn2])

        with patch(f"{PATCH}.extract_epub_toc", return_value=SAMPLE_TOC):
            with patch(f"{PATCH}.load_env_local", return_value={}):
                main()

        assert (paths["toc_dir"] / f"{isbn1}.json").exists()
        assert (paths["toc_dir"] / f"{isbn2}.json").exists()

    def test_overwrites_existing_output_file(self, monkeypatch, tmp_path, paths):
        isbn = "9781234567890"
        epub = tmp_path / "test.epub"
        epub.write_bytes(b"")

        paths["book_details"].write_text(json.dumps({isbn: _entry(epub_path=str(epub))}))
        paths["toc_dir"].mkdir(parents=True)
        (paths["toc_dir"] / f"{isbn}.json").write_text(json.dumps({"stale": True}))

        monkeypatch.setattr(sys, "argv", ["prog", isbn])

        with patch(f"{PATCH}.extract_epub_toc", return_value=SAMPLE_TOC):
            with patch(f"{PATCH}.load_env_local", return_value={}):
                main()

        data = json.loads((paths["toc_dir"] / f"{isbn}.json").read_text())
        assert "stale" not in data
        assert data["toc"] == SAMPLE_TOC

    def test_resolves_relative_path_against_books_dir(self, monkeypatch, tmp_path, paths):
        isbn = "9781234567890"
        bundle = tmp_path / "My Bundle"
        bundle.mkdir()
        epub = bundle / "test.epub"
        epub.write_bytes(b"")

        paths["book_details"].write_text(json.dumps({
            isbn: _entry(epub_path="My Bundle/test.epub")
        }))
        monkeypatch.setattr(sys, "argv", ["prog", isbn])

        with patch(f"{PATCH}.extract_epub_toc", return_value=SAMPLE_TOC) as mock_toc:
            with patch(f"{PATCH}.load_env_local", return_value={"BOOKS_DIR": str(tmp_path)}):
                main()

        mock_toc.assert_called_once_with(epub)

    def test_uses_absolute_epub_path_directly(self, monkeypatch, tmp_path, paths):
        isbn = "9781234567890"
        epub = tmp_path / "test.epub"
        epub.write_bytes(b"")

        paths["book_details"].write_text(json.dumps({isbn: _entry(epub_path=str(epub))}))
        monkeypatch.setattr(sys, "argv", ["prog", isbn])

        with patch(f"{PATCH}.extract_epub_toc", return_value=SAMPLE_TOC) as mock_toc:
            with patch(f"{PATCH}.load_env_local", return_value={"BOOKS_DIR": str(tmp_path / "other")}):
                main()

        mock_toc.assert_called_once_with(epub)


# ---------------------------------------------------------------------------
# Skip and error paths
# ---------------------------------------------------------------------------

class TestMainErrorPaths:
    def test_exits_when_book_details_missing(self, monkeypatch, paths):
        monkeypatch.setattr(sys, "argv", ["prog", "9781234567890"])

        with patch(f"{PATCH}.load_env_local", return_value={}):
            with pytest.raises(SystemExit):
                main()

    def test_skips_isbn_not_in_book_details(self, monkeypatch, paths, capsys):
        # book_details must be non-empty to pass the early-exit guard; the ISBN just won't be found
        paths["book_details"].write_text(json.dumps({"9781234567890": _entry()}))
        monkeypatch.setattr(sys, "argv", ["prog", "9999999999999"])

        with patch(f"{PATCH}.load_env_local", return_value={}):
            main()

        assert "[skip]" in capsys.readouterr().out
        assert not list(paths["toc_dir"].glob("*.json"))

    def test_skips_when_no_epub_path_stored(self, monkeypatch, paths, capsys):
        isbn = "9781234567890"
        paths["book_details"].write_text(json.dumps({isbn: _entry()}))
        monkeypatch.setattr(sys, "argv", ["prog", isbn])

        with patch(f"{PATCH}.load_env_local", return_value={}):
            main()

        out = capsys.readouterr().out
        assert "[skip]" in out
        assert "overwrite" in out

    def test_errors_when_epub_file_not_found_absolute(self, monkeypatch, tmp_path, paths, capsys):
        isbn = "9781234567890"
        paths["book_details"].write_text(json.dumps({
            isbn: _entry(epub_path=str(tmp_path / "missing.epub"))
        }))
        monkeypatch.setattr(sys, "argv", ["prog", isbn])

        with patch(f"{PATCH}.load_env_local", return_value={}):
            main()

        assert "[error]" in capsys.readouterr().out
        assert not (paths["toc_dir"] / f"{isbn}.json").exists()

    def test_errors_when_relative_path_and_no_books_dir(self, monkeypatch, paths, capsys):
        isbn = "9781234567890"
        paths["book_details"].write_text(json.dumps({
            isbn: _entry(epub_path="Bundle/test.epub")
        }))
        monkeypatch.setattr(sys, "argv", ["prog", isbn])

        with patch(f"{PATCH}.load_env_local", return_value={}):
            main()

        assert "[error]" in capsys.readouterr().out

    def test_errors_when_toc_extraction_returns_none(self, monkeypatch, tmp_path, paths, capsys):
        isbn = "9781234567890"
        epub = tmp_path / "test.epub"
        epub.write_bytes(b"")

        paths["book_details"].write_text(json.dumps({isbn: _entry(epub_path=str(epub))}))
        monkeypatch.setattr(sys, "argv", ["prog", isbn])

        with patch(f"{PATCH}.extract_epub_toc", return_value=None):
            with patch(f"{PATCH}.load_env_local", return_value={}):
                main()

        assert "[error]" in capsys.readouterr().out
        assert not (paths["toc_dir"] / f"{isbn}.json").exists()
