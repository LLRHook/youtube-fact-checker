"""Web search service using Brave Search API."""

import httpx
from backend.config import settings

_http_client: httpx.AsyncClient | None = None
_http_shutdown = False


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_shutdown:
        raise RuntimeError("HTTP client is shut down")
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=15.0)
    return _http_client


async def close_http_client():
    """Close the shared HTTP client. Call on app shutdown."""
    global _http_client, _http_shutdown
    _http_shutdown = True
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


class SearchResult:
    def __init__(self, title: str, url: str, snippet: str):
        self.title = title
        self.url = url
        self.snippet = snippet


async def search_brave(query: str, num_results: int = 5) -> list[SearchResult]:
    """
    Search using Brave Search API.

    Args:
        query: Search query string
        num_results: Number of results to return

    Returns:
        List of SearchResult objects
    """
    if not settings.BRAVE_API_KEY:
        raise ValueError("BRAVE_API_KEY not set. Add it to your .env file.")

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": settings.BRAVE_API_KEY,
    }

    params = {
        "q": query,
        "count": num_results,
        "text_decorations": "false",
        "search_lang": "en",
    }

    client = _get_http_client()
    response = await client.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers=headers,
        params=params,
    )
    if response.status_code == 429:
        raise RuntimeError("Brave Search rate limit exceeded — please try again shortly")
    if response.status_code == 403:
        raise RuntimeError("Brave Search API key is invalid or quota exhausted")
    response.raise_for_status()
    data = response.json()

    results = []
    web_results = data.get("web", {}).get("results", [])
    for item in web_results[:num_results]:
        url = item.get("url", "").strip()
        if not url or not url.startswith(("https://", "http://")) or "\n" in url:
            continue
        results.append(
            SearchResult(
                title=item.get("title", "").strip(),
                url=url,
                snippet=item.get("description", "").strip(),
            )
        )

    return results


def format_search_results(results: list[SearchResult]) -> str:
    """Format search results as text for LLM consumption."""
    if not results:
        return "No search results found."

    parts = []
    for i, r in enumerate(results, 1):
        parts.append(f"Source {i}: {r.title}\nURL: {r.url}\nSnippet: {r.snippet}\n")
    return "\n".join(parts)
