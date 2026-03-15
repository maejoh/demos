"""
Tests for extract_books.py.

Pure functions (sanitize_title, _author_looks_mangled, _parse_volume) are tested
directly. _google_request is tested with mocked HTTP to verify retry behaviour.
extract_epub_metadata is tested with a minimal epub built in-memory.
"""

import io
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from scripts.extract_books import (
    _author_looks_mangled,
    _google_request,
    _parse_volume,
    extract_epub_metadata,
    sanitize_title,
)


# ---------------------------------------------------------------------------
# sanitize_title
# ---------------------------------------------------------------------------

class TestSanitizeTitle:
    def test_strips_second_edition_suffix(self):
        assert sanitize_title("Learning Python, Second Edition") == "Learning Python"

    def test_strips_numeric_edition_suffix(self):
        assert sanitize_title("Clean Architecture, 3rd Edition") == "Clean Architecture"

    def test_leaves_plain_title_unchanged(self):
        assert sanitize_title("The Pragmatic Programmer") == "The Pragmatic Programmer"

    def test_case_insensitive(self):
        assert sanitize_title("Pro Git, SECOND EDITION") == "Pro Git"


# ---------------------------------------------------------------------------
# _author_looks_mangled
# ---------------------------------------------------------------------------

class TestAuthorLooksMangled:
    def test_normal_name_is_not_mangled(self):
        assert _author_looks_mangled("Martin Kleppmann") is False

    def test_all_caps_name_is_mangled(self):
        assert _author_looks_mangled("MARTIN KLEPPMANN") is True

    def test_majority_caps_name_is_mangled(self):
        # requires strictly more than half — "KYLE JAMES Simpson" is 2/3
        assert _author_looks_mangled("KYLE JAMES Simpson") is True

    def test_ampersand_joined_normal_names_are_not_mangled(self):
        assert _author_looks_mangled("David Thomas & Andrew Hunt") is False


# ---------------------------------------------------------------------------
# _parse_volume
# ---------------------------------------------------------------------------

class TestParseVolume:
    def test_prefers_isbn13_over_isbn10(self):
        volume_info = {
            "industryIdentifiers": [
                {"type": "ISBN_10", "identifier": "0135957052"},
                {"type": "ISBN_13", "identifier": "9780135957059"},
            ]
        }
        result = _parse_volume(volume_info)
        assert result["isbn"] == "9780135957059"

    def test_falls_back_to_isbn10_when_no_isbn13(self):
        volume_info = {
            "industryIdentifiers": [
                {"type": "ISBN_10", "identifier": "0135957052"},
            ]
        }
        result = _parse_volume(volume_info)
        assert result["isbn"] == "0135957052"

    def test_joins_multiple_authors_with_ampersand(self):
        volume_info = {"authors": ["David Thomas", "Andrew Hunt"]}
        result = _parse_volume(volume_info)
        assert result["author"] == "David Thomas & Andrew Hunt"

    def test_falls_back_to_epub_year_when_api_has_no_date(self):
        result = _parse_volume({}, epub_year=2019)
        assert result["year"] == 2019

    def test_parses_year_from_published_date(self):
        result = _parse_volume({"publishedDate": "2020-06-15"})
        assert result["year"] == 2020


# ---------------------------------------------------------------------------
# _google_request — mocked HTTP
# ---------------------------------------------------------------------------

class TestGoogleRequest:
    def test_returns_json_on_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}

        with patch("scripts.extract_books.requests.get", return_value=mock_response):
            result = _google_request({"q": "test"})

        assert result == {"items": []}

    def test_retries_on_429_and_succeeds(self):
        rate_limited = MagicMock(status_code=429)
        success = MagicMock(status_code=200)
        success.json.return_value = {"items": []}

        with patch("scripts.extract_books.requests.get", side_effect=[rate_limited, success]):
            with patch("scripts.extract_books.time.sleep"):  # don't actually wait
                result = _google_request({"q": "test"})

        assert result == {"items": []}

    def test_returns_none_after_three_429s(self):
        rate_limited = MagicMock(status_code=429)

        with patch("scripts.extract_books.requests.get", return_value=rate_limited):
            with patch("scripts.extract_books.time.sleep"):
                result = _google_request({"q": "test"})

        assert result is None


# ---------------------------------------------------------------------------
# extract_epub_metadata — minimal in-memory epub fixture
# ---------------------------------------------------------------------------

CONTAINER_XML = b"""\
<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="content.opf"
              media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

def make_epub(title="Test Book", author="Test Author", isbn="9781234567890", date="2020-01-01") -> io.BytesIO:
    """Build a minimal valid epub (zip) in memory."""
    opf = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
    <dc:identifier opf:scheme="ISBN">{isbn}</dc:identifier>
    <dc:date>{date}</dc:date>
  </metadata>
</package>
""".encode()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("META-INF/container.xml", CONTAINER_XML)
        zf.writestr("content.opf", opf)
    buf.seek(0)
    return buf


class TestExtractEpubMetadata:
    def test_extracts_title_author_isbn_and_year(self, tmp_path):
        epub_path = tmp_path / "test.epub"
        epub_path.write_bytes(make_epub().read())

        result = extract_epub_metadata(epub_path)

        assert result is not None
        assert result["title"] == "Test Book"
        assert result["author"] == "Test Author"
        assert result["isbn"] == "9781234567890"
        assert result["year"] == 2020

    def test_returns_none_for_epub_with_no_title(self, tmp_path):
        epub_path = tmp_path / "notitle.epub"
        epub_path.write_bytes(make_epub(title="").read())

        result = extract_epub_metadata(epub_path)

        assert result is None

    def test_returns_none_for_corrupt_epub(self, tmp_path):
        epub_path = tmp_path / "corrupt.epub"
        epub_path.write_bytes(b"not a zip file")

        result = extract_epub_metadata(epub_path)

        assert result is None
