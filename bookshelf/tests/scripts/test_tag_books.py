"""
Tests for tag_books.py.

Pure functions (_strip_fences, parse_json_list, parse_assignments,
build_vocabulary_prompt, build_assignment_prompt, apply_tag_assignments)
are tested directly. tag_single_book is tested with a mocked Anthropic client.
"""

from unittest.mock import MagicMock, patch

from scripts.book_pipeline.tag_books import (
    _strip_fences,
    apply_tag_assignments,
    build_assignment_prompt,
    build_vocabulary_prompt,
    parse_assignments,
    parse_json_list,
    tag_single_book,
)


# ---------------------------------------------------------------------------
# _strip_fences
# ---------------------------------------------------------------------------

class TestStripFences:
    def test_strips_json_fence(self):
        assert _strip_fences("```json\n[\"a\"]\n```") == '["a"]'

    def test_strips_plain_fence(self):
        assert _strip_fences("```\n[\"a\"]\n```") == '["a"]'

    def test_leaves_plain_text_unchanged(self):
        assert _strip_fences('["a", "b"]') == '["a", "b"]'

    def test_strips_surrounding_whitespace(self):
        assert _strip_fences('  ["a"]  ') == '["a"]'


# ---------------------------------------------------------------------------
# parse_json_list
# ---------------------------------------------------------------------------

class TestParseJsonList:
    def test_parses_clean_json_list(self):
        assert parse_json_list('["Python", "Machine Learning"]') == ["Python", "Machine Learning"]

    def test_strips_markdown_fence(self):
        assert parse_json_list('```json\n["Python", "ML"]\n```') == ["Python", "ML"]

    def test_extracts_list_from_preamble(self):
        result = parse_json_list('Here are the tags: ["Python", "ML"]')
        assert result == ["Python", "ML"]

    def test_strips_whitespace_from_items(self):
        assert parse_json_list('[" Python ", "ML"]') == ["Python", "ML"]

    def test_filters_empty_strings(self):
        assert parse_json_list('["Python", "", "ML"]') == ["Python", "ML"]

    def test_empty_string_returns_empty_list(self):
        assert parse_json_list("") == []

    def test_wrong_shape_object_returns_empty_list(self):
        assert parse_json_list('{"tag": "python"}') == []

    def test_invalid_json_returns_empty_list(self):
        assert parse_json_list("not json at all") == []

    def test_list_with_non_string_elements_returns_empty_list(self):
        assert parse_json_list('[1, 2, 3]') == []


# ---------------------------------------------------------------------------
# parse_assignments
# ---------------------------------------------------------------------------

class TestParseAssignments:
    def test_parses_valid_assignments(self):
        result = parse_assignments('{"isbn1": ["AI", "Python"], "isbn2": ["Databases"]}')
        assert result == {"isbn1": ["AI", "Python"], "isbn2": ["Databases"]}

    def test_strips_markdown_fence(self):
        result = parse_assignments('```json\n{"isbn1": ["AI"]}\n```')
        assert result == {"isbn1": ["AI"]}

    def test_extracts_object_from_preamble(self):
        result = parse_assignments('Here you go: {"isbn1": ["AI"]}')
        assert result == {"isbn1": ["AI"]}

    def test_empty_string_returns_empty_dict(self):
        assert parse_assignments("") == {}

    def test_invalid_json_returns_empty_dict(self):
        assert parse_assignments("not json") == {}

    def test_wrong_shape_list_returns_empty_dict(self):
        assert parse_assignments('["AI", "Python"]') == {}


# ---------------------------------------------------------------------------
# build_vocabulary_prompt
# ---------------------------------------------------------------------------

class TestBuildVocabularyPrompt:
    def test_contains_all_titles(self):
        prompt = build_vocabulary_prompt(["Learning Python", "Designing Data-Intensive Applications"])
        assert "Learning Python" in prompt
        assert "Designing Data-Intensive Applications" in prompt

    def test_requests_specific_tools(self):
        prompt = build_vocabulary_prompt(["Learning Python"])
        assert "language" in prompt.lower() or "tool" in prompt.lower()

    def test_requests_broad_categories(self):
        prompt = build_vocabulary_prompt(["Learning Python"])
        assert "categor" in prompt.lower()

    def test_titles_wrapped_in_xml(self):
        prompt = build_vocabulary_prompt(["Learning Python"])
        assert "<title>Learning Python</title>" in prompt

    def test_returns_nonempty_string(self):
        assert len(build_vocabulary_prompt(["Title"])) > 0


# ---------------------------------------------------------------------------
# build_assignment_prompt
# ---------------------------------------------------------------------------

class TestBuildAssignmentPrompt:
    def test_contains_isbn_and_title(self):
        books = {"9781234567890": {"title": "Learning Python", "description": ""}}
        prompt = build_assignment_prompt(books, ["Python", "Web Development"])
        assert "9781234567890" in prompt
        assert "Learning Python" in prompt

    def test_contains_vocabulary(self):
        books = {"9781234567890": {"title": "Learning Python", "description": ""}}
        prompt = build_assignment_prompt(books, ["Python", "Machine Learning"])
        assert "Python" in prompt
        assert "Machine Learning" in prompt

    def test_includes_description_when_present(self):
        books = {"9781234567890": {"title": "Learning Python", "description": "A book about Python."}}
        prompt = build_assignment_prompt(books, ["Python"])
        assert "A book about Python." in prompt

    def test_omits_description_tag_when_empty(self):
        books = {"9781234567890": {"title": "Learning Python", "description": ""}}
        prompt = build_assignment_prompt(books, ["Python"])
        assert "<description>" not in prompt

    def test_books_wrapped_in_xml(self):
        books = {"9781234567890": {"title": "Learning Python", "description": ""}}
        prompt = build_assignment_prompt(books, ["Python"])
        assert '<book isbn="9781234567890">' in prompt

    def test_returns_nonempty_string(self):
        assert len(build_assignment_prompt({}, [])) > 0


# ---------------------------------------------------------------------------
# apply_tag_assignments
# ---------------------------------------------------------------------------

class TestApplyTagAssignments:
    def test_assigns_tags_to_books(self):
        book_details = {"isbn1": {"title": "A Book"}}
        apply_tag_assignments(book_details, {"isbn1": ["AI", "Python"]}, {"isbn1"})
        assert book_details["isbn1"]["ai_tags"] == ["AI", "Python"]

    def test_only_touches_books_in_isbn_filter(self):
        book_details = {
            "isbn1": {"title": "Book 1"},
            "isbn2": {"title": "Book 2"},
        }
        apply_tag_assignments(
            book_details,
            {"isbn1": ["AI"], "isbn2": ["Web Development"]},
            {"isbn1"},
        )
        assert book_details["isbn1"]["ai_tags"] == ["AI"]
        assert "ai_tags" not in book_details["isbn2"]

    def test_skips_isbn_with_no_assignment(self):
        book_details = {"isbn1": {"title": "A Book"}}
        updated = apply_tag_assignments(book_details, {}, {"isbn1"})
        assert updated == 0
        assert "ai_tags" not in book_details["isbn1"]

    def test_skips_isbn_with_invalid_assignment(self):
        book_details = {"isbn1": {"title": "A Book"}}
        updated = apply_tag_assignments(book_details, {"isbn1": "not a list"}, {"isbn1"})
        assert updated == 0

    def test_returns_count_of_updated_books(self):
        book_details = {
            "isbn1": {"title": "Book 1"},
            "isbn2": {"title": "Book 2"},
        }
        updated = apply_tag_assignments(
            book_details,
            {"isbn1": ["AI"], "isbn2": ["Web Development"]},
            {"isbn1", "isbn2"},
        )
        assert updated == 2


# ---------------------------------------------------------------------------
# tag_single_book — mocked Anthropic client
# ---------------------------------------------------------------------------

class TestTagSingleBook:
    def _make_client(self, response_text: str) -> MagicMock:
        client = MagicMock()
        client.messages.create.return_value.content = [MagicMock(text=response_text)]
        return client

    def test_returns_assigned_tags(self):
        client = self._make_client('{"9781234567890": ["Python", "Machine Learning"]}')
        result = tag_single_book({"title": "Learning Python"}, "9781234567890", ["Python", "Machine Learning"], client)
        assert result == ["Python", "Machine Learning"]

    def test_calls_api_with_isbn_and_title_in_prompt(self):
        client = self._make_client('{"9781234567890": ["Python"]}')
        tag_single_book({"title": "Learning Python"}, "9781234567890", ["Python"], client)
        prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "9781234567890" in prompt
        assert "Learning Python" in prompt

    def test_returns_empty_list_on_api_exception(self):
        client = MagicMock()
        client.messages.create.side_effect = Exception("API error")
        result = tag_single_book({"title": "A Book"}, "9781234567890", ["Python"], client, retries=0)
        assert result == []

    def test_returns_empty_list_when_isbn_not_in_response(self):
        client = self._make_client('{"other_isbn": ["Python"]}')
        result = tag_single_book({"title": "A Book"}, "9781234567890", ["Python"], client)
        assert result == []

    def test_retries_on_exception_and_succeeds(self):
        client = MagicMock()
        ok_response = MagicMock(text='{"9781234567890": ["Python"]}')
        client.messages.create.side_effect = [Exception("rate limit"), MagicMock(content=[ok_response])]
        with patch("scripts.book_pipeline.tag_books.time.sleep"):
            result = tag_single_book({"title": "A Book"}, "9781234567890", ["Python"], client, retries=1, retry_delay=0)
        assert result == ["Python"]
        assert client.messages.create.call_count == 2

    def test_exhausts_retries_and_returns_empty_list(self):
        client = MagicMock()
        client.messages.create.side_effect = Exception("rate limit")
        with patch("scripts.book_pipeline.tag_books.time.sleep"):
            result = tag_single_book({"title": "A Book"}, "9781234567890", ["Python"], client, retries=2, retry_delay=0)
        assert result == []
        assert client.messages.create.call_count == 3
