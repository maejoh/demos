"""Tests for scripts/book_pipeline/google_books.py."""

from unittest.mock import MagicMock, patch

from scripts.book_pipeline.google_books import (
    _author_looks_mangled,
    _google_request,
    _parse_volume,
)


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


class TestGoogleRequest:
    def test_returns_json_on_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}

        with patch("scripts.book_pipeline.google_books.requests.get", return_value=mock_response):
            result = _google_request({"q": "test"})

        assert result == {"items": []}

    def test_retries_on_429_and_succeeds(self):
        rate_limited = MagicMock(status_code=429)
        success = MagicMock(status_code=200)
        success.json.return_value = {"items": []}

        with patch("scripts.book_pipeline.google_books.requests.get", side_effect=[rate_limited, success]):
            with patch("scripts.book_pipeline.google_books.time.sleep"):  # don't actually wait
                result = _google_request({"q": "test"})

        assert result == {"items": []}

    def test_returns_none_after_three_429s(self):
        rate_limited = MagicMock(status_code=429)

        with patch("scripts.book_pipeline.google_books.requests.get", return_value=rate_limited):
            with patch("scripts.book_pipeline.google_books.time.sleep"):
                result = _google_request({"q": "test"})

        assert result is None
