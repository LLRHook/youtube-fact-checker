"""Tests for backend.utils.json_parser."""

import pytest
from backend.utils.json_parser import parse_llm_json


class TestParseLlmJson:
    def test_clean_object(self):
        result = parse_llm_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_clean_array(self):
        result = parse_llm_json('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_markdown_fenced_json(self):
        result = parse_llm_json('```json\n{"key": "val"}\n```')
        assert result == {"key": "val"}

    def test_fenced_no_lang(self):
        result = parse_llm_json('```\n{"key": "val"}\n```')
        assert result == {"key": "val"}

    def test_text_before_json(self):
        result = parse_llm_json('Here is the result: {"key": "val"}')
        assert result == {"key": "val"}

    def test_text_after_json(self):
        result = parse_llm_json('{"key": "val"}\nThat is the answer.')
        assert result == {"key": "val"}

    def test_malformed_returns_none(self):
        result = parse_llm_json('not json at all')
        assert result is None

    def test_empty_string(self):
        result = parse_llm_json('')
        assert result is None

    def test_nested_object(self):
        result = parse_llm_json('{"a": {"b": [1, 2]}}')
        assert result == {"a": {"b": [1, 2]}}

    def test_array_of_objects(self):
        text = '[{"text": "claim1"}, {"text": "claim2"}]'
        result = parse_llm_json(text)
        assert len(result) == 2
        assert result[0]["text"] == "claim1"

    def test_embedded_in_prose(self):
        text = 'The claims are:\n[{"text": "claim"}]\nEnd of response.'
        result = parse_llm_json(text)
        assert result == [{"text": "claim"}]

    def test_array_preferred_when_first(self):
        text = '[1] then {"a": 1}'
        result = parse_llm_json(text)
        assert result == [1]
