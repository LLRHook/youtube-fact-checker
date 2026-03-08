"""Fact-checking service: combines web search + LLM truth scoring."""

import asyncio
import logging
import anthropic
from backend.config import settings
from backend.services.search_service import search_brave, format_search_results
from backend.utils.json_parser import parse_llm_json

logger = logging.getLogger(__name__)

_anthropic_client: anthropic.AsyncAnthropic | None = None


def _get_anthropic_client() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _anthropic_client


async def close_anthropic_client():
    """Close the shared async Anthropic client. Call on app shutdown."""
    global _anthropic_client
    if _anthropic_client is not None:
        await _anthropic_client.close()
        _anthropic_client = None


TRUTH_SCORING_SYSTEM = """You are a fact-checker. Evaluate the claim below against the provided search results.

Scoring guide:
- 90-100: Strong corroboration from multiple reliable sources
- 70-89: Generally supported with minor caveats
- 50-69: Mixed or partial evidence
- 30-49: Contradicted by some reliable sources
- 10-29: Strongly contradicted or debunked
- 0-9: Completely false according to all sources

If the claim is an opinion rather than a verifiable fact, set category to "opinion" and truth_percentage to 50.
If there isn't enough evidence to evaluate, set confidence lower (0.3-0.5) and truth_percentage to 50.

Return ONLY a JSON object (no markdown, no extra text):
{
  "truth_percentage": <0-100>,
  "confidence": <0.0-1.0>,
  "reasoning": "<2-3 sentence explanation of your assessment>",
  "category": "fact" or "opinion" or "unclear"
}"""


async def fact_check_claim(claim_text: str) -> dict:
    """
    Fact-check a single claim using web search + LLM evaluation.

    Args:
        claim_text: The factual claim to verify

    Returns:
        Dict with truth_percentage, confidence, reasoning, sources, category
    """
    # Step 1: Search for evidence
    claim_text = (claim_text or "").strip()
    if not claim_text:
        return {
            "truth_percentage": 50,
            "confidence": 0.1,
            "reasoning": "Empty claim text — nothing to verify.",
            "sources": [],
            "category": "unclear",
        }

    search_query = claim_text
    # Trim very long claims for better search (at word boundary)
    if len(search_query) > 200:
        search_query = search_query[:200].rsplit(" ", 1)[0] or search_query[:200]

    try:
        search_results = await search_brave(search_query, num_results=settings.SEARCH_RESULTS_PER_CLAIM)
    except Exception as e:
        logger.warning("Search failed for claim '%.50s': %s", claim_text, e)
        return {
            "truth_percentage": 50,
            "confidence": 0.2,
            "reasoning": f"Could not verify: search failed ({str(e)[:100]})",
            "sources": [],
            "category": "unclear",
        }

    evidence_text = format_search_results(search_results)

    # Step 2: LLM evaluation
    try:
        client = _get_anthropic_client()
        response = await client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=1024,
            system=TRUTH_SCORING_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f'Claim: "{claim_text}"\n\nSearch Results:\n{evidence_text}\n\nEvaluate the truth of this claim.',
                }
            ],
        )

        if not response.content or not hasattr(response.content[0], 'text'):
            raise ValueError("LLM returned empty content for fact-check evaluation")
        response_text = response.content[0].text.strip()
        result = parse_llm_json(response_text)
        if result is None:
            raise ValueError("Failed to parse LLM JSON response")

    except Exception as e:
        logger.warning("LLM evaluation failed for claim '%.50s': %s", claim_text, e)
        return {
            "truth_percentage": 50,
            "confidence": 0.2,
            "reasoning": f"Could not evaluate: LLM error ({str(e)[:100]})",
            "sources": [],
            "category": "unclear",
        }

    # Combine with sources, deduplicating by URL and filtering unsafe schemes
    seen_urls = set()
    sources = []
    for r in search_results:
        if r.url not in seen_urls and r.url.startswith(("https://", "http://")):
            seen_urls.add(r.url)
            sources.append({"title": r.title, "url": r.url, "snippet": r.snippet})

    required_fields = ("truth_percentage", "confidence", "reasoning")
    missing = [f for f in required_fields if f not in result]
    if missing:
        logger.warning("LLM response missing fields %s for claim '%.50s'", missing, claim_text)

    category = result.get("category", "fact")
    if category not in ("fact", "opinion", "unclear"):
        category = "fact"

    try:
        truth_pct = round(float(result.get("truth_percentage", 50)))
    except (TypeError, ValueError):
        truth_pct = 50
    try:
        confidence = float(result.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5

    return {
        "truth_percentage": max(0, min(100, truth_pct)),
        "confidence": max(0.0, min(1.0, confidence)),
        "reasoning": str(result.get("reasoning", "No reasoning provided.")).strip() or "No reasoning provided.",
        "sources": sources,
        "category": category,
    }


async def fact_check_all_claims(claims: list[dict], on_progress=None) -> list[dict]:
    """
    Fact-check all claims with bounded concurrency.

    Args:
        claims: List of claim dicts from claim_extractor
        on_progress: Optional callback(completed, total) for progress updates

    Returns:
        List of enriched claim dicts with truth scores (order preserved)
    """
    total = len(claims)
    results = [None] * total
    semaphore = asyncio.Semaphore(settings.FACT_CHECK_CONCURRENCY)
    completed_count = 0
    lock = asyncio.Lock()

    async def check_one(index, claim):
        nonlocal completed_count
        async with semaphore:
            try:
                result = await fact_check_claim(claim["text"])
            except Exception as e:
                logger.warning("Unexpected error fact-checking claim %d: %s", index, e)
                result = {
                    "truth_percentage": 50,
                    "confidence": 0.1,
                    "reasoning": "Fact-check failed due to an unexpected error.",
                    "sources": [],
                    "category": "unclear",
                }
            async with lock:
                results[index] = {**claim, **result}
                completed_count += 1
                if on_progress:
                    on_progress(completed_count, total)

    await asyncio.gather(*(check_one(i, c) for i, c in enumerate(claims)))
    # Pad any missing results with neutral fallback instead of silently dropping
    for i, r in enumerate(results):
        if r is None:
            logger.warning("Fact-check result %d was None, padding with fallback", i)
            results[i] = {
                **claims[i],
                "truth_percentage": 50,
                "confidence": 0.0,
                "reasoning": "Fact-check could not be completed.",
                "sources": [],
                "category": "unclear",
            }
    return results
