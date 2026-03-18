"""Tests for scripts/book_pipeline/utils.py."""
import json
from pathlib import Path

import pytest

from scripts.book_pipeline.utils import load_env_local, load_json, sanitize_title, save_json, to_title_case


class TestSanitizeTitle:
    def test_strips_second_edition_suffix(self):
        assert sanitize_title("Learning Python, Second Edition") == "Learning Python"

    def test_strips_numeric_edition_suffix(self):
        assert sanitize_title("Clean Architecture, 3rd Edition") == "Clean Architecture"

    def test_leaves_plain_title_unchanged(self):
        assert sanitize_title("The Pragmatic Programmer") == "The Pragmatic Programmer"

    def test_case_insensitive(self):
        assert sanitize_title("Pro Git, SECOND EDITION") == "Pro Git"


class TestToTitleCase:
    def test_capitalizes_each_word(self):
        assert to_title_case("humble bundle software collection") == "Humble Bundle Software Collection"

    def test_leaves_already_cased_string_unchanged(self):
        assert to_title_case("No Starch Press Bundle") == "No Starch Press Bundle"

    def test_handles_single_word(self):
        assert to_title_case("python") == "Python"

    def test_handles_empty_string(self):
        assert to_title_case("") == ""


class TestLoadEnvLocal:
    def test_returns_empty_dict_when_file_missing(self, tmp_path, monkeypatch):
        import scripts.book_pipeline.utils as utils_mod
        monkeypatch.setattr(utils_mod, "SCRIPTS_DIR", tmp_path / "scripts")
        assert load_env_local() == {}

    def test_parses_key_value_pairs(self, tmp_path, monkeypatch):
        import scripts.book_pipeline.utils as utils_mod
        monkeypatch.setattr(utils_mod, "SCRIPTS_DIR", tmp_path / "scripts")
        (tmp_path / ".env.local").write_text("FOO=bar\nBAZ=qux\n", encoding="utf-8")
        assert load_env_local() == {"FOO": "bar", "BAZ": "qux"}

    def test_strips_double_quotes(self, tmp_path, monkeypatch):
        import scripts.book_pipeline.utils as utils_mod
        monkeypatch.setattr(utils_mod, "SCRIPTS_DIR", tmp_path / "scripts")
        (tmp_path / ".env.local").write_text('KEY="quoted value"\n', encoding="utf-8")
        assert load_env_local()["KEY"] == "quoted value"

    def test_strips_single_quotes(self, tmp_path, monkeypatch):
        import scripts.book_pipeline.utils as utils_mod
        monkeypatch.setattr(utils_mod, "SCRIPTS_DIR", tmp_path / "scripts")
        (tmp_path / ".env.local").write_text("KEY='single quoted'\n", encoding="utf-8")
        assert load_env_local()["KEY"] == "single quoted"

    def test_ignores_comment_lines(self, tmp_path, monkeypatch):
        import scripts.book_pipeline.utils as utils_mod
        monkeypatch.setattr(utils_mod, "SCRIPTS_DIR", tmp_path / "scripts")
        (tmp_path / ".env.local").write_text("# comment\nKEY=value\n", encoding="utf-8")
        assert load_env_local() == {"KEY": "value"}

    def test_ignores_empty_lines(self, tmp_path, monkeypatch):
        import scripts.book_pipeline.utils as utils_mod
        monkeypatch.setattr(utils_mod, "SCRIPTS_DIR", tmp_path / "scripts")
        (tmp_path / ".env.local").write_text("\n\nKEY=value\n\n", encoding="utf-8")
        assert load_env_local() == {"KEY": "value"}


class TestLoadJson:
    def test_loads_existing_dict(self, tmp_path):
        path = tmp_path / "data.json"
        path.write_text('{"key": "value"}', encoding="utf-8")
        assert load_json(path, {}) == {"key": "value"}

    def test_loads_existing_list(self, tmp_path):
        path = tmp_path / "data.json"
        path.write_text('[1, 2, 3]', encoding="utf-8")
        assert load_json(path, []) == [1, 2, 3]

    def test_returns_default_dict_when_file_missing(self, tmp_path):
        assert load_json(tmp_path / "missing.json", {}) == {}

    def test_returns_default_list_when_file_missing(self, tmp_path):
        assert load_json(tmp_path / "missing.json", []) == []


class TestSaveJson:
    def test_writes_json_to_file(self, tmp_path):
        path = tmp_path / "out.json"
        save_json(path, {"key": "value"})
        assert json.loads(path.read_text(encoding="utf-8")) == {"key": "value"}

    def test_creates_parent_directories(self, tmp_path):
        path = tmp_path / "nested" / "dir" / "out.json"
        save_json(path, [])
        assert path.exists()

    def test_writes_with_indentation(self, tmp_path):
        path = tmp_path / "out.json"
        save_json(path, {"a": 1})
        assert "\n" in path.read_text(encoding="utf-8")

    def test_preserves_unicode(self, tmp_path):
        path = tmp_path / "out.json"
        save_json(path, {"title": "Ñoño"})
        assert "Ñoño" in path.read_text(encoding="utf-8")
