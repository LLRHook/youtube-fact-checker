"""Tests for backend.services.fact_checker."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from backend.services.fact_checker import fact_check_claim, fact_check_all_claims
from backend.services.search_service import SearchResult


def _mock_search_results():
    return [
        SearchResult("Source 1", "https://example.com/1", "snippet 1"),
        SearchResult("Source 2", "https://example.com/2", "snippet 2"),
    ]


def _make_async_llm_response(text: str):
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


class TestFactCheckClaim:
    @pytest.mark.asyncio
    @patch("backend.services.fact_checker._get_anthropic_client")
    @patch("backend.services.fact_checker.search_brave", new_callable=AsyncMock)
    async def test_success(self, mock_search, mock_get_client):
        mock_search.return_value = _mock_search_results()
        client = MagicMock()
        mock_get_client.return_value = client
        client.messages.create = AsyncMock(return_value=_make_async_llm_response(
            '{"truth_percentage": 85, "confidence": 0.9, "reasoning": "Well supported.", "category": "fact"}'
        ))
        result = await fact_check_claim("The Earth is round")
        assert result["truth_percentage"] == 85
        assert result["confidence"] == 0.9
        assert len(result["sources"]) == 2
        assert result["category"] == "fact"

    @pytest.mark.asyncio
    @patch("backend.services.fact_checker._get_anthropic_client")
    @patch("backend.services.fact_checker.search_brave", new_callable=AsyncMock)
    async def test_search_failure_fallback(self, mock_search, mock_get_client):
        mock_search.side_effect = RuntimeError("Search failed")
        result = await fact_check_claim("Some claim")
        assert result["truth_percentage"] == 50
        assert result["confidence"] == 0.2
        assert result["category"] == "unclear"

    @pytest.mark.asyncio
    @patch("backend.services.fact_checker._get_anthropic_client")
    @patch("backend.services.fact_checker.search_brave", new_callable=AsyncMock)
    async def test_llm_failure_fallback(self, mock_search, mock_get_client):
        mock_search.return_value = _mock_search_results()
        client = MagicMock()
        mock_get_client.return_value = client
        client.messages.create = AsyncMock(side_effect=Exception("LLM error"))
        result = await fact_check_claim("Some claim")
        assert result["truth_percentage"] == 50
        assert result["confidence"] == 0.2

    @pytest.mark.asyncio
    async def test_empty_claim(self):
        result = await fact_check_claim("")
        assert result["truth_percentage"] == 50
        assert result["confidence"] == 0.1
        assert result["category"] == "unclear"

    @pytest.mark.asyncio
    @patch("backend.services.fact_checker._get_anthropic_client")
    @patch("backend.services.fact_checker.search_brave", new_callable=AsyncMock)
    async def test_invalid_category(self, mock_search, mock_get_client):
        mock_search.return_value = _mock_search_results()
        client = MagicMock()
        mock_get_client.return_value = client
        client.messages.create = AsyncMock(return_value=_make_async_llm_response(
            '{"truth_percentage": 50, "confidence": 0.5, "reasoning": "test", "category": "invalid"}'
        ))
        result = await fact_check_claim("test")
        assert result["category"] == "fact"

    @pytest.mark.asyncio
    @patch("backend.services.fact_checker._get_anthropic_client")
    @patch("backend.services.fact_checker.search_brave", new_callable=AsyncMock)
    async def test_truth_clamped(self, mock_search, mock_get_client):
        mock_search.return_value = _mock_search_results()
        client = MagicMock()
        mock_get_client.return_value = client
        client.messages.create = AsyncMock(return_value=_make_async_llm_response(
            '{"truth_percentage": 150, "confidence": 2.0, "reasoning": "test", "category": "fact"}'
        ))
        result = await fact_check_claim("test")
        assert 0 <= result["truth_percentage"] <= 100
        assert 0.0 <= result["confidence"] <= 1.0

    @pytest.mark.asyncio
    @patch("backend.services.fact_checker._get_anthropic_client")
    @patch("backend.services.fact_checker.search_brave", new_callable=AsyncMock)
    async def test_source_dedup(self, mock_search, mock_get_client):
        mock_search.return_value = [
            SearchResult("S1", "https://example.com/same", "a"),
            SearchResult("S2", "https://example.com/same", "b"),
        ]
        client = MagicMock()
        mock_get_client.return_value = client
        client.messages.create = AsyncMock(return_value=_make_async_llm_response(
            '{"truth_percentage": 80, "confidence": 0.8, "reasoning": "ok", "category": "fact"}'
        ))
        result = await fact_check_claim("test")
        assert len(result["sources"]) == 1

    @pytest.mark.asyncio
    @patch("backend.services.fact_checker._get_anthropic_client")
    @patch("backend.services.fact_checker.search_brave", new_callable=AsyncMock)
    async def test_unsafe_url_filtered(self, mock_search, mock_get_client):
        mock_search.return_value = [
            SearchResult("Good", "https://example.com", "ok"),
            SearchResult("Bad", "javascript:alert(1)", "xss"),
        ]
        client = MagicMock()
        mock_get_client.return_value = client
        client.messages.create = AsyncMock(return_value=_make_async_llm_response(
            '{"truth_percentage": 80, "confidence": 0.8, "reasoning": "ok", "category": "fact"}'
        ))
        result = await fact_check_claim("test")
        assert len(result["sources"]) == 1
        assert result["sources"][0]["url"] == "https://example.com"


class TestFactCheckAllClaims:
    @pytest.mark.asyncio
    @patch("backend.services.fact_checker.fact_check_claim", new_callable=AsyncMock)
    async def test_all_succeed(self, mock_fc):
        mock_fc.return_value = {
            "truth_percentage": 80, "confidence": 0.8, "reasoning": "ok",
            "sources": [], "category": "fact",
        }
        claims = [{"text": "claim1"}, {"text": "claim2"}]
        results = await fact_check_all_claims(claims)
        assert len(results) == 2
        assert results[0]["text"] == "claim1"
        assert results[1]["text"] == "claim2"

    @pytest.mark.asyncio
    @patch("backend.services.fact_checker.fact_check_claim", new_callable=AsyncMock)
    async def test_progress_callback(self, mock_fc):
        mock_fc.return_value = {
            "truth_percentage": 80, "confidence": 0.8, "reasoning": "ok",
            "sources": [], "category": "fact",
        }
        progress_calls = []
        claims = [{"text": "c1"}, {"text": "c2"}]
        await fact_check_all_claims(claims, on_progress=lambda c, t: progress_calls.append((c, t)))
        assert len(progress_calls) == 2
        assert progress_calls[-1] == (2, 2)

    @pytest.mark.asyncio
    @patch("backend.services.fact_checker.fact_check_claim", new_callable=AsyncMock)
    async def test_one_exception(self, mock_fc):
        async def side_effect(text):
            if text == "bad":
                raise RuntimeError("boom")
            return {
                "truth_percentage": 80, "confidence": 0.8, "reasoning": "ok",
                "sources": [], "category": "fact",
            }
        mock_fc.side_effect = side_effect
        claims = [{"text": "good"}, {"text": "bad"}]
        results = await fact_check_all_claims(claims)
        assert len(results) == 2
        # The failed one gets fallback
        assert results[1]["category"] == "unclear"
        assert results[1]["confidence"] == 0.1

    @pytest.mark.asyncio
    @patch("backend.services.fact_checker.fact_check_claim", new_callable=AsyncMock)
    async def test_order_preserved(self, mock_fc):
        async def side_effect(text):
            return {
                "truth_percentage": int(text[-1]) * 10,
                "confidence": 0.5, "reasoning": text,
                "sources": [], "category": "fact",
            }
        mock_fc.side_effect = side_effect
        claims = [{"text": "c1"}, {"text": "c2"}, {"text": "c3"}]
        results = await fact_check_all_claims(claims)
        assert [r["truth_percentage"] for r in results] == [10, 20, 30]
