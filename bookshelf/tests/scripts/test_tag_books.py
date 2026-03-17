"""
Tests for tag_books.py.

Pure functions (_strip_fences, parse_tag_response, parse_normalization_response,
build_tag_prompt, build_normalization_prompt, apply_tag_assignments) are
tested directly. tag_book is tested with a mocked Anthropic client.
"""

from unittest.mock import MagicMock, patch

from scripts.book_pipeline.tag_books import (
    _strip_fences,
    apply_tag_assignments,
    build_normalization_prompt,
    build_tag_prompt,
    parse_normalization_response,
    parse_tag_response,
    tag_book,
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
# parse_tag_response
# ---------------------------------------------------------------------------

class TestParseTagResponse:
    def test_parses_clean_json_list(self):
        assert parse_tag_response('["python", "machine learning"]') == ["python", "machine learning"]

    def test_strips_markdown_fence(self):
        assert parse_tag_response('```json\n["python", "ml"]\n```') == ["python", "ml"]

    def test_extracts_list_from_preamble(self):
        result = parse_tag_response('Here are the tags: ["python", "ml"]')
        assert result == ["python", "ml"]

    def test_strips_whitespace_from_tags(self):
        assert parse_tag_response('[" python ", "ml"]') == ["python", "ml"]

    def test_filters_empty_strings(self):
        assert parse_tag_response('["python", "", "ml"]') == ["python", "ml"]

    def test_empty_string_returns_empty_list(self):
        assert parse_tag_response("") == []

    def test_wrong_shape_object_returns_empty_list(self):
        assert parse_tag_response('{"tag": "python"}') == []

    def test_invalid_json_returns_empty_list(self):
        assert parse_tag_response("not json at all") == []

    def test_list_with_non_string_elements_returns_empty_list(self):
        assert parse_tag_response('[1, 2, 3]') == []


# ---------------------------------------------------------------------------
# parse_normalization_response
# ---------------------------------------------------------------------------

VALID_NORM_RESPONSE = '{"vocabulary": ["AI", "web development"], "assignments": {"isbn1": ["AI"]}}'

class TestParseNormalizationResponse:
    def test_parses_valid_response(self):
        result = parse_normalization_response(VALID_NORM_RESPONSE)
        assert result["vocabulary"] == ["AI", "web development"]
        assert result["assignments"] == {"isbn1": ["AI"]}

    def test_strips_markdown_fence(self):
        result = parse_normalization_response(f"```json\n{VALID_NORM_RESPONSE}\n```")
        assert result["vocabulary"] == ["AI", "web development"]

    def test_extracts_object_from_preamble(self):
        result = parse_normalization_response(f"Here you go: {VALID_NORM_RESPONSE}")
        assert result["vocabulary"] == ["AI", "web development"]

    def test_empty_string_returns_empty_dict(self):
        assert parse_normalization_response("") == {}

    def test_missing_vocabulary_key_returns_empty_dict(self):
        assert parse_normalization_response('{"assignments": {"isbn1": ["AI"]}}') == {}

    def test_missing_assignments_key_returns_empty_dict(self):
        assert parse_normalization_response('{"vocabulary": ["AI"]}') == {}

    def test_wrong_shape_list_returns_empty_dict(self):
        assert parse_normalization_response('["AI", "web development"]') == {}

    def test_invalid_json_returns_empty_dict(self):
        assert parse_normalization_response("not json") == {}


# ---------------------------------------------------------------------------
# build_tag_prompt
# ---------------------------------------------------------------------------

class TestBuildTagPrompt:
    def test_contains_title(self):
        prompt = build_tag_prompt("Learning Python", "A great book.")
        assert "Learning Python" in prompt

    def test_contains_description_when_provided(self):
        prompt = build_tag_prompt("Learning Python", "A great book about Python.")
        assert "A great book about Python." in prompt

    def test_omits_description_section_when_empty(self):
        prompt = build_tag_prompt("Learning Python", "")
        assert "Description:" not in prompt

    def test_mentions_tech_audience(self):
        prompt = build_tag_prompt("Learning Python", "")
        assert "tech industry" in prompt

    def test_instructs_to_minimize_tags(self):
        prompt = build_tag_prompt("Learning Python", "")
        assert "as few" in prompt

    def test_returns_nonempty_string(self):
        assert len(build_tag_prompt("Title", "")) > 0


# ---------------------------------------------------------------------------
# build_normalization_prompt
# ---------------------------------------------------------------------------

class TestBuildNormalizationPrompt:
    def test_contains_candidate_tags(self):
        prompt = build_normalization_prompt({"isbn1": ["ML", "python"]}, [])
        assert "ML" in prompt
        assert "python" in prompt

    def test_contains_existing_vocabulary_when_provided(self):
        prompt = build_normalization_prompt({"isbn1": ["ML"]}, ["machine learning", "web development"])
        assert "machine learning" in prompt
        assert "web development" in prompt

    def test_omits_existing_vocabulary_section_when_empty(self):
        prompt = build_normalization_prompt({"isbn1": ["ML"]}, [])
        assert "Existing tags" not in prompt

    def test_returns_nonempty_string(self):
        assert len(build_normalization_prompt({}, [])) > 0


# ---------------------------------------------------------------------------
# apply_tag_assignments
# ---------------------------------------------------------------------------

class TestApplyTagAssignments:
    def test_assigns_tags_to_books(self):
        book_details = {"isbn1": {"title": "A Book"}}
        apply_tag_assignments(book_details, {"isbn1": ["AI", "python"]}, {"isbn1"})
        assert book_details["isbn1"]["ai_tags"] == ["AI", "python"]

    def test_only_touches_books_in_isbn_filter(self):
        book_details = {
            "isbn1": {"title": "Book 1"},
            "isbn2": {"title": "Book 2"},
        }
        apply_tag_assignments(
            book_details,
            {"isbn1": ["AI"], "isbn2": ["web development"]},
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
            {"isbn1": ["AI"], "isbn2": ["web development"]},
            {"isbn1", "isbn2"},
        )
        assert updated == 2


# ---------------------------------------------------------------------------
# tag_book — mocked Anthropic client
# ---------------------------------------------------------------------------

class TestTagBook:
    def _make_client(self, response_text: str) -> MagicMock:
        client = MagicMock()
        client.messages.create.return_value.content = [MagicMock(text=response_text)]
        return client

    def test_returns_parsed_tags(self):
        client = self._make_client('["python", "machine learning"]')
        result = tag_book({"title": "Learning Python", "description": "A book."}, client)
        assert result == ["python", "machine learning"]

    def test_calls_api_with_title_in_prompt(self):
        client = self._make_client('["python"]')
        tag_book({"title": "Learning Python", "description": ""}, client)
        call_args = client.messages.create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        assert "Learning Python" in prompt

    def test_returns_empty_list_on_api_exception(self):
        client = MagicMock()
        client.messages.create.side_effect = Exception("API error")
        result = tag_book({"title": "A Book", "description": ""}, client, retries=0)
        assert result == []

    def test_returns_empty_list_on_unparseable_response(self):
        client = self._make_client("Sorry, I cannot tag this book.")
        result = tag_book({"title": "A Book", "description": ""}, client)
        assert result == []

    def test_handles_missing_description_gracefully(self):
        client = self._make_client('["python"]')
        result = tag_book({"title": "A Book"}, client)  # no description key
        assert result == ["python"]

    def test_retries_on_exception_and_succeeds(self):
        client = MagicMock()
        ok_response = MagicMock(text='["python"]')
        client.messages.create.side_effect = [Exception("rate limit"), MagicMock(content=[ok_response])]
        with patch("scripts.book_pipeline.tag_books.time.sleep"):
            result = tag_book({"title": "A Book", "description": ""}, client, retries=1, retry_delay=0)
        assert result == ["python"]
        assert client.messages.create.call_count == 2

    def test_exhausts_retries_and_returns_empty_list(self):
        client = MagicMock()
        client.messages.create.side_effect = Exception("rate limit")
        with patch("scripts.book_pipeline.tag_books.time.sleep"):
            result = tag_book({"title": "A Book", "description": ""}, client, retries=2, retry_delay=0)
        assert result == []
        assert client.messages.create.call_count == 3
