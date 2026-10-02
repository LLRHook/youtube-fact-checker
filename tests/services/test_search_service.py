import hashlib
import json
from dataclasses import asdict
from unittest.mock import AsyncMock

import httpx
import pytest

from backend.services import search_service as search
from backend.services.search_service import SearchResult


@pytest.fixture(autouse=True)
def cache_and_transport(monkeypatch):
    monkeypatch.setattr(search, "_context_unavailable", False)
    monkeypatch.setattr(search.settings, "SEARCH_MODE", "llm_context")
    monkeypatch.setattr(search.settings, "GOOGLE_FACTCHECK_API_KEY", "")
    monkeypatch.setattr(search.db, "get_search_cache", AsyncMock(return_value=None))
    monkeypatch.setattr(search.db, "put_search_cache", AsyncMock())


def mock_http(monkeypatch, *payloads):
    responses = [
        httpx.Response(status, json=data, request=httpx.Request("GET", "https://api.test")) for status, data in payloads
    ]
    get = AsyncMock(side_effect=responses)
    monkeypatch.setattr(search, "_get_http_client", lambda: type("Client", (), {"get": get})())
    return get


async def test_context_passages_html_age_and_exclusions(monkeypatch):
    get = mock_http(
        monkeypatch,
        (
            200,
            {
                "grounding": {
                    "generic": [
                        {
                            "url": "https://www.cdc.gov/facts",
                            "title": "<b>Health &amp; facts</b>",
                            "snippets": [
                                "<p>Primary &quot;evidence&quot;</p>",
                                "<em>Extra</em>",
                                "x" * 900,
                                "Fourth",
                                "Fifth",
                            ],
                        },
                        {"url": "https://youtube.com/watch?v=1", "snippets": ["video"]},
                        {"url": "javascript:alert(1)"},
                        {"url": "https://example.com/\x01unsafe"},
                    ]
                },
                "sources": {"https://www.cdc.gov/facts": {"hostname": "www.cdc.gov", "age": ["2 days", "2026-09-30"]}},
            },
        ),
    )
    results = await search.search_brave("health evidence", 5)
    assert len(results) == 1
    result = results[0]
    assert result.title == "Health & facts" and result.snippet == 'Primary "evidence"'
    assert result.extra_snippets == ["Extra", "x" * 700, "Fourth"]
    assert result.domain == "cdc.gov" and result.reliability == "high" and result.age == "2026-09-30"
    kwargs = get.call_args.kwargs
    assert get.call_args.args[0].endswith("/llm/context")
    assert kwargs["params"]["maximum_number_of_tokens"] == 2048
    assert kwargs["params"]["maximum_number_of_tokens_per_url"] == 600
    assert kwargs["params"]["context_threshold_mode"] == "balanced"
    search.db.put_search_cache.assert_awaited_once()


async def test_web_parsing(monkeypatch):
    monkeypatch.setattr(search.settings, "SEARCH_MODE", "web")
    get = mock_http(
        monkeypatch,
        (
            200,
            {
                "web": {
                    "results": [
                        {
                            "url": "https://en.wikipedia.org/a",
                            "title": "<b>Wiki</b>",
                            "description": "A &amp; B",
                            "extra_snippets": ["<b>C</b>"],
                            "page_age": "2026-01-01",
                        },
                        {"url": "https://youtu.be/abc", "title": "Excluded"},
                    ]
                }
            },
        ),
    )
    results = await search.search_brave("query", 5)
    assert results[0].snippet == "A & B" and results[0].extra_snippets == ["C"]
    assert results[0].reliability == "medium" and len(results) == 1
    params = get.call_args.kwargs["params"]
    assert params["extra_snippets"] == "true" and params["safesearch"] == "moderate"


@pytest.mark.parametrize("status", [400, 404, 422])
async def test_context_fallback_persists_and_warns_once(monkeypatch, caplog, status):
    get = mock_http(monkeypatch, (status, {}), (200, {"web": {"results": []}}), (200, {"web": {"results": []}}))
    await search.search_brave("first", 5)
    await search.search_brave("second", 5)
    assert [c.args[0].rsplit("/", 1)[-1] for c in get.call_args_list] == ["context", "search", "search"]
    assert len([r for r in caplog.records if "falling back" in r.message]) == 1


@pytest.mark.parametrize("status,message", [(429, "rate limit"), (403, "invalid or quota")])
async def test_brave_errors(monkeypatch, status, message):
    mock_http(monkeypatch, (status, {}))
    with pytest.raises(RuntimeError, match=message):
        await search.search_brave("query", 5)
    search.db.put_search_cache.assert_not_awaited()


async def test_query_trimming(monkeypatch):
    get = mock_http(monkeypatch, (200, {}))
    await search.search_brave("verylongword " * 100, 5)
    query = get.call_args.kwargs["params"]["q"]
    assert len(query) <= 600 and len(query.split()) <= 75
    assert query.split()[-1] == "verylongword"


async def test_factcheck_mapping(monkeypatch):
    monkeypatch.setattr(search.settings, "GOOGLE_FACTCHECK_API_KEY", "test")
    get = mock_http(
        monkeypatch,
        (
            200,
            {
                "claims": [
                    dict(
                        text="Claim &amp; words",
                        claimant="Speaker",
                        claimReview=[
                            dict(
                                publisher={"name": "AFP"},
                                title="<b>Review</b>",
                                url="https://factcheck.afp.com/a",
                                textualRating="False",
                                reviewDate="2026-09-20T10:00:00Z",
                            ),
                            dict(publisher={"name": "Other"}, url="https://snopes.com/a", textualRating="Mixed"),
                        ],
                    )
                ]
            },
        ),
    )
    results = await search.search_factchecks("word " * 100)
    assert len(results) == 2
    assert results[0].kind == "factcheck" and results[0].reliability == "factchecker"
    assert results[0].title == "AFP: Review" and results[1].title == "Other: Claim & words"
    assert (
        results[0].snippet
        == 'Claim reviewed: "Claim & words" (claimant: Speaker). Rating: "False". Reviewed 2026-09-20.'
    )
    assert results[0].rating == "False"
    assert len(get.call_args.kwargs["params"]["query"]) <= 200


async def test_factcheck_error_and_optional_key(monkeypatch):
    get = mock_http(monkeypatch, (500, {}))
    assert await search.search_factchecks("query") == []
    get.assert_not_awaited()
    monkeypatch.setattr(search.settings, "GOOGLE_FACTCHECK_API_KEY", "test")
    assert await search.search_factchecks("query") == []
    search.db.put_search_cache.assert_not_awaited()


async def test_cache_hit_avoids_http(monkeypatch):
    result = SearchResult("Cached", "https://example.org", "evidence")
    monkeypatch.setattr(search.db, "get_search_cache", AsyncMock(return_value=json.dumps([asdict(result)])))
    get = mock_http(monkeypatch)
    assert await search.search_brave("  HEALTH   Query ", 5) == [result]
    key = hashlib.sha256(b"brave_context|health query|5").hexdigest()
    search.db.get_search_cache.assert_awaited_once_with(key, search.settings.SEARCH_CACHE_DAYS)
    get.assert_not_awaited()
    search.db.put_search_cache.assert_not_awaited()


async def test_empty_not_cached(monkeypatch):
    mock_http(monkeypatch, (200, {}))
    assert await search.search_brave("query", 5) == []
    search.db.put_search_cache.assert_not_awaited()


@pytest.mark.parametrize(
    "url,expected",
    [
        ("HTTPS://EXAMPLE.COM/path/?utm_source=a&fbclid=b&gclid=c&id=1#frag", "https://example.com/path?id=1"),
        ("https://example.com/", "https://example.com"),
    ],
)
def test_url_normalization(url, expected):
    assert search.normalize_url(url) == expected


async def test_round_robin_dedupe_tiers_and_cap(monkeypatch):
    q1 = [
        SearchResult("Low", "https://reddit.com/a", "x", reliability="low"),
        SearchResult("High 1", "https://cdc.gov/a?utm_source=x#f", "x", reliability="high"),
        SearchResult("Unknown", "https://example.org/a", "x"),
    ]
    q2 = [
        SearchResult("High 2", "https://nasa.gov/a", "x", reliability="high"),
        SearchResult("Duplicate", "https://cdc.gov/a", "x", reliability="high"),
        SearchResult("Medium", "https://wikipedia.org/a", "x", reliability="medium"),
    ]
    fact = SearchResult("Factcheck", "https://snopes.com/a", "x", reliability="factchecker")
    monkeypatch.setattr(search, "search_brave", AsyncMock(side_effect=[q1, q2]))
    monkeypatch.setattr(search, "search_factchecks", AsyncMock(return_value=[fact]))
    monkeypatch.setattr(search.settings, "EVIDENCE_MAX_SOURCES", 4)
    results, count = await search.gather_evidence("claim", ["one", "two", "ignored"])
    assert [r.title for r in results] == ["Factcheck", "High 2", "High 1", "Medium"]
    assert count == 0
    assert search.search_brave.await_count == 2


async def test_request_count_includes_fallback_and_google(monkeypatch):
    monkeypatch.setattr(search.settings, "GOOGLE_FACTCHECK_API_KEY", "test")

    async def get(url, **kwargs):
        if url.endswith("context"):
            status, data = 404, {}
        else:
            status, data = 200, {}
        return httpx.Response(status, json=data, request=httpx.Request("GET", url))

    monkeypatch.setattr(search, "_get_http_client", lambda: type("Client", (), {"get": staticmethod(get)})())
    _, count = await search.gather_evidence("claim", ["query"])
    assert count == 3


async def test_cached_gather_makes_zero_requests(monkeypatch):
    monkeypatch.setattr(
        search.db,
        "get_search_cache",
        AsyncMock(return_value=json.dumps([asdict(SearchResult("Cached", "https://example.org", "text"))])),
    )
    get = mock_http(monkeypatch)
    results, count = await search.gather_evidence("claim", [])
    assert len(results) == 1 and count == 0
    get.assert_not_awaited()


async def test_all_brave_fail_raises(monkeypatch):
    first = RuntimeError("first")
    monkeypatch.setattr(search, "search_brave", AsyncMock(side_effect=[first, RuntimeError("second")]))
    monkeypatch.setattr(search, "search_factchecks", AsyncMock(return_value=[]))
    with pytest.raises(RuntimeError, match="first"):
        await search.gather_evidence("claim", ["q1", "q2"])


async def test_partial_brave_failure_and_empty_query_fallback(monkeypatch):
    monkeypatch.setattr(search, "search_brave", AsyncMock(side_effect=[RuntimeError("failure"), []]))
    monkeypatch.setattr(search, "search_factchecks", AsyncMock(return_value=[]))
    assert await search.gather_evidence("claim", ["q1", "q2"]) == ([], 0)
    search.search_brave.reset_mock(side_effect=True)
    search.search_brave.return_value = []
    await search.gather_evidence("x" * 250, [])
    search.search_brave.assert_awaited_once_with("x" * 200, search.settings.SEARCH_RESULTS_PER_QUERY)


def test_evidence_format():
    result = SearchResult(
        "Review",
        "https://snopes.com",
        "Body",
        ["Extra"],
        "snopes.com",
        "factchecker",
        "factcheck",
        "False",
        "2026-01-01",
    )
    formatted = search.format_evidence([result])
    assert formatted.startswith("<evidence>\n[1] Review") and formatted.endswith("</evidence>")
    assert "Source: snopes.com | reliability: factchecker | 2026-01-01 | FACT-CHECK rating: False" in formatted
    assert "Body\n- Extra" in formatted
    assert search.format_evidence([]) == "<evidence>\nNo search results found.\n</evidence>"
    assert len(search.format_evidence([SearchResult("T", "https://example.org", "x" * 2000)])) < 1600
