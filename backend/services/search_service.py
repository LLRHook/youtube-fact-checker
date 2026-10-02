"""Cached Brave passages and professional fact-check retrieval."""

import asyncio
import hashlib
import html
import json
import logging
import re
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from backend import database as db
from backend.config import settings
from backend.services.source_quality import TIER_RANK, domain_of, is_excluded, reliability

logger = logging.getLogger(__name__)
_http_client: httpx.AsyncClient | None = None
_context_unavailable = False
_request_counter: ContextVar[list[int] | None] = ContextVar("search_requests", default=None)


def _get_http_client():
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=15)
    return _http_client


async def close_http_client():
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    extra_snippets: list[str] = field(default_factory=list)
    domain: str = ""
    reliability: str = "unknown"
    kind: str = "web"
    rating: str = ""
    age: str = ""


def _trim(query, limit, words=None):
    query = " ".join(query.split()[:words]) if words else " ".join(query.split())
    if len(query) > limit:
        query = query[:limit].rsplit(" ", 1)[0] if " " in query[:limit] else query[:limit]
    return query


def _clean(text):
    return html.unescape(re.sub(r"<[^>]*>", "", str(text or ""))).strip()


def _safe_url(url):
    return bool(url and url.startswith(("http://", "https://")) and not any(ord(c) < 32 or ord(c) == 127 for c in url))


def normalize_url(url):
    parts = urlsplit(url)
    params = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}
    ]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(params), ""))


async def _cached(provider, query, count, fetch):
    normalized = " ".join(query.lower().split())
    key = hashlib.sha256(f"{provider}|{normalized}|{count}".encode()).hexdigest()
    cached = await db.get_search_cache(key, settings.SEARCH_CACHE_DAYS)
    if cached is not None:
        return [SearchResult(**item) for item in json.loads(cached)]
    results = await fetch()
    if results:
        await db.put_search_cache(key, provider, query, json.dumps([asdict(r) for r in results]))
    return results


async def _get(url, **kwargs):
    counter = _request_counter.get()
    if counter is not None:
        counter[0] += 1
    return await _get_http_client().get(url, **kwargs)


def _web_result(title, url, snippet, extras, age=""):
    url = (url or "").strip()
    if not _safe_url(url):
        return None
    domain = domain_of(url)
    if not domain or is_excluded(domain):
        return None
    return SearchResult(
        _clean(title),
        url,
        _clean(snippet)[:700],
        [_clean(s)[:700] for s in extras],
        domain,
        reliability(domain),
        age=_clean(age),
    )


async def search_brave(query, count) -> list[SearchResult]:
    if not settings.BRAVE_API_KEY:
        raise ValueError("BRAVE_API_KEY not set. Add it to your .env file.")
    query = _trim(query, 600, 75)
    if not query:
        return []

    async def fetch():
        global _context_unavailable
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": settings.BRAVE_API_KEY,
        }
        params = dict(q=query, count=count, search_lang="en", safesearch="moderate")
        context = settings.SEARCH_MODE == "llm_context" and not _context_unavailable
        if context:
            response = await _get(
                "https://api.search.brave.com/res/v1/llm/context",
                headers=headers,
                params={
                    **params,
                    "maximum_number_of_urls": count,
                    "maximum_number_of_tokens": 2048,
                    "maximum_number_of_tokens_per_url": 600,
                    "maximum_number_of_snippets_per_url": 4,
                    "context_threshold_mode": "balanced",
                },
            )
            if response.status_code in {400, 404, 422}:
                if not _context_unavailable:
                    logger.warning("Brave LLM Context unavailable; falling back to web search")
                _context_unavailable = True
                context = False
        if not context:
            response = await _get(
                "https://api.search.brave.com/res/v1/web/search",
                headers=headers,
                params={**params, "extra_snippets": "true", "text_decorations": "false"},
            )
        if response.status_code == 429:
            raise RuntimeError("Brave Search rate limit exceeded - please try again shortly")
        if response.status_code == 403:
            raise RuntimeError("Brave Search API key is invalid or quota exhausted")
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError as exc:
            logger.warning("Brave returned non-JSON response: %s", exc)
            return []
        results = []
        items = data.get("grounding", {}).get("generic", []) if context else data.get("web", {}).get("results", [])
        for item in items[:count]:
            if context:
                snippets = item.get("snippets") or []
                age = data.get("sources", {}).get(item.get("url"), {}).get("age") or []
                age = age[1] if isinstance(age, list) and len(age) > 1 else ""
                result = _web_result(
                    item.get("title"), item.get("url"), snippets[0] if snippets else "", snippets[1:4], age
                )
            else:
                result = _web_result(
                    item.get("title"),
                    item.get("url"),
                    item.get("description"),
                    item.get("extra_snippets") or [],
                    item.get("age") or item.get("page_age") or "",
                )
            if result:
                results.append(result)
        return results

    provider = "brave_context" if settings.SEARCH_MODE == "llm_context" and not _context_unavailable else "brave_web"
    return await _cached(provider, query, count, fetch)


async def search_factchecks(query) -> list[SearchResult]:
    if not settings.GOOGLE_FACTCHECK_API_KEY:
        return []
    query = _trim(query, 200)

    async def fetch():
        response = await _get(
            "https://factchecktools.googleapis.com/v1alpha1/claims:search",
            params=dict(query=query, languageCode="en", pageSize=5, key=settings.GOOGLE_FACTCHECK_API_KEY),
        )
        response.raise_for_status()
        results = []
        for claim in response.json().get("claims", []):
            for review in claim.get("claimReview", []):
                url = (review.get("url") or "").strip()
                if not _safe_url(url) or is_excluded(domain_of(url)):
                    continue
                text = _clean(claim.get("text"))
                rating = _clean(review.get("textualRating"))
                snippet = f'Claim reviewed: "{text}"'
                if claim.get("claimant"):
                    snippet += f" (claimant: {_clean(claim['claimant'])})"
                snippet += f'. Rating: "{rating}".'
                if review.get("reviewDate"):
                    snippet += f" Reviewed {review['reviewDate'][:10]}."
                title = f"{_clean(review.get('publisher', {}).get('name'))}: {_clean(review.get('title') or text)}"
                results.append(
                    SearchResult(
                        title,
                        url,
                        snippet[:700],
                        domain=domain_of(url),
                        reliability="factchecker",
                        kind="factcheck",
                        rating=rating,
                    )
                )
        return results

    try:
        return await _cached("google_factchecks", query, 5, fetch)
    except Exception as exc:
        logger.warning("Fact-check search failed: %s", exc)
        return []


async def gather_evidence(claim_text, queries) -> tuple[list[SearchResult], int]:
    queries = queries[: settings.SEARCH_QUERIES_PER_CLAIM] or [claim_text[:200]]
    counter = [0]
    token = _request_counter.set(counter)
    try:
        responses = await asyncio.gather(
            *(search_brave(q, settings.SEARCH_RESULTS_PER_QUERY) for q in queries),
            search_factchecks(claim_text),
            return_exceptions=True,
        )
    finally:
        _request_counter.reset(token)
    errors = [r for r in responses[:-1] if isinstance(r, Exception)]
    for error in [r for r in responses if isinstance(r, Exception)]:
        logger.warning("Evidence retrieval failed: %s", error)
    if len(errors) == len(queries):
        raise errors[0]
    brave = [r if isinstance(r, list) else [] for r in responses[:-1]]
    merged = list(responses[-1]) if isinstance(responses[-1], list) else []
    for position in range(max((len(r) for r in brave), default=0)):
        merged.extend(r[position] for r in brave if position < len(r))
    seen = set()
    unique = []
    for result in merged:
        key = normalize_url(result.url)
        if key not in seen:
            seen.add(key)
            unique.append(result)
    unique.sort(key=lambda r: TIER_RANK[r.reliability])
    return unique[: settings.EVIDENCE_MAX_SOURCES], counter[0]


def format_evidence(results) -> str:
    if not results:
        return "<evidence>\nNo search results found.\n</evidence>"
    parts = []
    for i, result in enumerate(results, 1):
        metadata = f"Source: {result.domain} | reliability: {result.reliability}"
        if result.age:
            metadata += " | " + result.age
        if result.kind == "factcheck":
            metadata += " | FACT-CHECK rating: " + result.rating
        body = result.snippet + "\n" + "\n".join("- " + s for s in result.extra_snippets)
        parts.append(f"[{i}] {result.title}\n{metadata}\n{body[:1500]}")
    return "<evidence>\n" + "\n\n".join(parts) + "\n</evidence>"
