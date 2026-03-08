"""Tests for backend.services.claim_extractor."""

import pytest
from unittest.mock import patch, MagicMock
from backend.services.claim_extractor import extract_claims


def _make_llm_response(text: str):
    """Build a mock Anthropic response with the given text."""
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


class TestExtractClaims:
    @patch("backend.services.claim_extractor._get_anthropic_client")
    def test_valid_extraction(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        client.messages.create.return_value = _make_llm_response(
            '[{"text": "The sky is blue", "timestamp_seconds": 10, "category": "fact"}]'
        )
        result = extract_claims("Some transcript text")
        assert len(result) == 1
        assert result[0]["text"] == "The sky is blue"
        assert result[0]["timestamp_seconds"] == 10
        assert result[0]["category"] == "fact"

    @patch("backend.services.claim_extractor._get_anthropic_client")
    def test_empty_array(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        client.messages.create.return_value = _make_llm_response("[]")
        result = extract_claims("Some transcript text")
        assert result == []

    @patch("backend.services.claim_extractor._get_anthropic_client")
    def test_malformed_json(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        client.messages.create.return_value = _make_llm_response("not json")
        result = extract_claims("text")
        assert result == []

    @patch("backend.services.claim_extractor._get_anthropic_client")
    def test_markdown_fenced(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        client.messages.create.return_value = _make_llm_response(
            '```json\n[{"text": "claim", "timestamp_seconds": 0, "category": "fact"}]\n```'
        )
        result = extract_claims("text")
        assert len(result) == 1

    @patch("backend.services.claim_extractor._get_anthropic_client")
    def test_timestamp_clamping(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        client.messages.create.return_value = _make_llm_response(
            '[{"text": "claim", "timestamp_seconds": 999, "category": "fact"}]'
        )
        result = extract_claims("text", max_duration_seconds=300)
        assert result[0]["timestamp_seconds"] == 300

    @patch("backend.services.claim_extractor._get_anthropic_client")
    def test_invalid_timestamp(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        client.messages.create.return_value = _make_llm_response(
            '[{"text": "claim", "timestamp_seconds": "not_a_number", "category": "fact"}]'
        )
        result = extract_claims("text")
        assert result[0]["timestamp_seconds"] == 0.0

    @patch("backend.services.claim_extractor._get_anthropic_client")
    def test_cap_at_max_claims(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        # Generate 40 claims (max is 30)
        claims = [{"text": f"Claim {i}", "timestamp_seconds": i, "category": "fact"} for i in range(40)]
        import json
        client.messages.create.return_value = _make_llm_response(json.dumps(claims))
        result = extract_claims("text")
        assert len(result) == 30

    @patch("backend.services.claim_extractor._get_anthropic_client")
    def test_missing_text_dropped(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        client.messages.create.return_value = _make_llm_response(
            '[{"timestamp_seconds": 10, "category": "fact"}, {"text": "valid", "category": "fact"}]'
        )
        result = extract_claims("text")
        assert len(result) == 1
        assert result[0]["text"] == "valid"

    @patch("backend.services.claim_extractor._get_anthropic_client")
    def test_invalid_category_defaults_to_fact(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        client.messages.create.return_value = _make_llm_response(
            '[{"text": "claim", "timestamp_seconds": 0, "category": "bogus"}]'
        )
        result = extract_claims("text")
        assert result[0]["category"] == "fact"

    @patch("backend.services.claim_extractor._get_anthropic_client")
    def test_dict_unwrap(self, mock_get_client):
        """When LLM returns {"claims": [...]} instead of bare array."""
        client = MagicMock()
        mock_get_client.return_value = client
        client.messages.create.return_value = _make_llm_response(
            '{"claims": [{"text": "claim", "timestamp_seconds": 0, "category": "fact"}]}'
        )
        result = extract_claims("text")
        assert len(result) == 1

    def test_no_api_key(self, monkeypatch):
        from backend.config import settings
        monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            extract_claims("text")

    @patch("backend.services.claim_extractor._get_anthropic_client")
    def test_segments_formatting(self, mock_get_client):
        """Verify that segments produce timestamped transcript for LLM."""
        client = MagicMock()
        mock_get_client.return_value = client
        client.messages.create.return_value = _make_llm_response("[]")

        seg = MagicMock()
        seg.text = "Hello"
        seg.start = 65.0  # 1:05
        extract_claims("text", segments=[seg])

        call_args = client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "[01:05]" in user_msg
