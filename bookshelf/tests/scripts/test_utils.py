"""Tests for scripts/book_pipeline/utils.py."""

from scripts.book_pipeline.utils import sanitize_title


class TestSanitizeTitle:
    def test_strips_second_edition_suffix(self):
        assert sanitize_title("Learning Python, Second Edition") == "Learning Python"

    def test_strips_numeric_edition_suffix(self):
        assert sanitize_title("Clean Architecture, 3rd Edition") == "Clean Architecture"

    def test_leaves_plain_title_unchanged(self):
        assert sanitize_title("The Pragmatic Programmer") == "The Pragmatic Programmer"

    def test_case_insensitive(self):
        assert sanitize_title("Pro Git, SECOND EDITION") == "Pro Git"
