"""Tests for scripts/book_pipeline/google_books.py."""

from unittest.mock import MagicMock, patch

from scripts.book_pipeline.google_books import (
    _author_looks_mangled,
    _google_request,
    _parse_volume,
    fetch_google_book,
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

    def test_returns_none_isbn_when_no_identifiers(self):
        result = _parse_volume({})
        assert result["isbn"] is None

    def test_returns_none_author_when_no_authors(self):
        result = _parse_volume({})
        assert result["author"] is None


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

    def test_returns_none_on_request_exception(self):
        with patch("scripts.book_pipeline.google_books.requests.get", side_effect=Exception("timeout")):
            result = _google_request({"q": "test"})
        assert result is None


class TestFetchGoogleBook:
    def _volume_response(self, isbn="9781234567890", title="Test Book"):
        return {
            "items": [{
                "volumeInfo": {
                    "title": title,
                    "authors": ["Test Author"],
                    "publishedDate": "2020",
                    "description": "A description.",
                    "industryIdentifiers": [
                        {"type": "ISBN_13", "identifier": isbn}
                    ],
                }
            }]
        }

    def test_returns_parsed_volume_on_isbn_query_hit(self):
        with patch("scripts.book_pipeline.google_books._google_request", return_value=self._volume_response()):
            result = fetch_google_book("9781234567890", "Test Book", "Author", None, None)

        assert result is not None
        assert result["isbn"] == "9781234567890"
        assert result["title"] == "Test Book"

    def test_queries_by_isbn_first(self):
        with patch("scripts.book_pipeline.google_books._google_request", return_value=self._volume_response()) as mock_req:
            fetch_google_book("9781234567890", "Test Book", "Author", None, "api_key")

        first_query = mock_req.call_args_list[0][0][0]["q"]
        assert first_query == "isbn:9781234567890"

    def test_skips_isbn_query_when_no_isbn_provided(self):
        with patch("scripts.book_pipeline.google_books._google_request", return_value={"items": []}) as mock_req:
            fetch_google_book(None, "Test Book", "Author", None, None)

        queries = [call[0][0]["q"] for call in mock_req.call_args_list]
        assert not any(q.startswith("isbn:") for q in queries)

    def test_falls_back_to_title_author_query_when_isbn_returns_nothing(self):
        no_results = {"items": []}
        with patch("scripts.book_pipeline.google_books._google_request", side_effect=[no_results, self._volume_response()]) as mock_req:
            result = fetch_google_book("9781234567890", "Test Book", "Author", None, None)

        assert mock_req.call_count == 2
        second_query = mock_req.call_args_list[1][0][0]["q"]
        assert "intitle:" in second_query

    def test_returns_none_when_all_queries_return_no_items(self):
        with patch("scripts.book_pipeline.google_books._google_request", return_value={"items": []}):
            result = fetch_google_book("9781234567890", "Test Book", "Author", None, None)
        assert result is None

    def test_returns_none_when_all_requests_fail(self):
        with patch("scripts.book_pipeline.google_books._google_request", return_value=None):
            result = fetch_google_book(None, "Test Book", "Author", None, None)
        assert result is None

    def test_includes_api_key_in_all_requests(self):
        with patch("scripts.book_pipeline.google_books._google_request", return_value={"items": []}) as mock_req:
            fetch_google_book(None, "Test Book", "Author", None, "my_api_key")

        for call in mock_req.call_args_list:
            assert call[0][0].get("key") == "my_api_key"

    def test_omits_key_when_no_api_key(self):
        with patch("scripts.book_pipeline.google_books._google_request", return_value={"items": []}) as mock_req:
            fetch_google_book(None, "Test Book", "Author", None, None)

        for call in mock_req.call_args_list:
            assert "key" not in call[0][0]

    def test_passes_epub_year_to_parse_volume(self):
        # volumeInfo with no publishedDate — should fall back to epub_year
        with patch("scripts.book_pipeline.google_books._google_request", return_value={"items": [{"volumeInfo": {}}]}):
            result = fetch_google_book(None, "Test Book", "Author", 2019, None)

        assert result["year"] == 2019

    def test_includes_first_author_only_query_when_author_has_comma(self):
        # author="Smith, Jones" → first_author="Smith" → an extra query with just "Smith"
        with patch("scripts.book_pipeline.google_books._google_request", return_value={"items": []}) as mock_req:
            fetch_google_book(None, "Test Book", "Smith, Jones", None, None)

        queries = [call[0][0]["q"] for call in mock_req.call_args_list]
        assert any('inauthor:"Smith"' in q and 'inauthor:"Smith, Jones"' not in q for q in queries)

    def test_includes_sanitized_title_query_when_title_has_edition_suffix(self):
        # "Test Book, 2nd Edition" sanitizes to "Test Book" → extra query with clean title
        with patch("scripts.book_pipeline.google_books._google_request", return_value={"items": []}) as mock_req:
            fetch_google_book(None, "Test Book, 2nd Edition", "Author", None, None)

        queries = [call[0][0]["q"] for call in mock_req.call_args_list]
        assert any('intitle:"Test Book"' in q and "Edition" not in q for q in queries)
