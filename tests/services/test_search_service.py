"""Tests for backend.services.search_service."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx
from backend.services.search_service import search_brave, format_search_results, SearchResult


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {"web": {"results": []}}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


class TestSearchBrave:
    @pytest.mark.asyncio
    @patch("backend.services.search_service._get_http_client")
    async def test_success(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        client.get = AsyncMock(return_value=_mock_response(json_data={
            "web": {"results": [
                {"title": "Result 1", "url": "https://example.com/1", "description": "Desc 1"},
                {"title": "Result 2", "url": "https://example.com/2", "description": "Desc 2"},
            ]}
        }))
        results = await search_brave("test query")
        assert len(results) == 2
        assert results[0].title == "Result 1"
        assert results[0].url == "https://example.com/1"

    @pytest.mark.asyncio
    @patch("backend.services.search_service._get_http_client")
    async def test_429_rate_limit(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        resp = _mock_response(status_code=429)
        resp.raise_for_status = MagicMock()  # Don't raise for status
        client.get = AsyncMock(return_value=resp)
        with pytest.raises(RuntimeError, match="rate limit"):
            await search_brave("test")

    @pytest.mark.asyncio
    @patch("backend.services.search_service._get_http_client")
    async def test_403_invalid_key(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        resp = _mock_response(status_code=403)
        resp.raise_for_status = MagicMock()
        client.get = AsyncMock(return_value=resp)
        with pytest.raises(RuntimeError, match="invalid"):
            await search_brave("test")

    @pytest.mark.asyncio
    async def test_empty_query(self):
        results = await search_brave("")
        assert results == []

    @pytest.mark.asyncio
    async def test_no_api_key(self, monkeypatch):
        from backend.config import settings
        monkeypatch.setattr(settings, "BRAVE_API_KEY", "")
        with pytest.raises(ValueError, match="BRAVE_API_KEY"):
            await search_brave("test")

    @pytest.mark.asyncio
    @patch("backend.services.search_service._get_http_client")
    async def test_malformed_response(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        resp = _mock_response()
        resp.json.side_effect = Exception("Invalid JSON")
        client.get = AsyncMock(return_value=resp)
        results = await search_brave("test")
        assert results == []

    @pytest.mark.asyncio
    @patch("backend.services.search_service._get_http_client")
    async def test_invalid_urls_filtered(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        client.get = AsyncMock(return_value=_mock_response(json_data={
            "web": {"results": [
                {"title": "Good", "url": "https://example.com", "description": "ok"},
                {"title": "Bad", "url": "ftp://bad.com", "description": "bad"},
                {"title": "Empty", "url": "", "description": "empty"},
            ]}
        }))
        results = await search_brave("test")
        assert len(results) == 1
        assert results[0].url == "https://example.com"

    @pytest.mark.asyncio
    @patch("backend.services.search_service._get_http_client")
    async def test_num_results(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client
        items = [{"title": f"R{i}", "url": f"https://example.com/{i}", "description": f"d{i}"} for i in range(10)]
        client.get = AsyncMock(return_value=_mock_response(json_data={"web": {"results": items}}))
        results = await search_brave("test", num_results=3)
        assert len(results) == 3


class TestFormatSearchResults:
    def test_empty(self):
        assert format_search_results([]) == "No search results found."

    def test_multiple_results(self):
        results = [
            SearchResult("Title A", "https://a.com", "Snip A"),
            SearchResult("Title B", "https://b.com", "Snip B"),
        ]
        text = format_search_results(results)
        assert "Source 1:" in text
        assert "Source 2:" in text
        assert "Title A" in text
