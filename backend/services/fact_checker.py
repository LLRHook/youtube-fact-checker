"""Fact-checking service: combines web search + LLM truth scoring."""

import json
import asyncio
import anthropic
from backend.config import settings
from backend.services.search_service import search_brave, format_search_results


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
    search_query = claim_text
    # Trim very long claims for better search
    if len(search_query) > 200:
        search_query = search_query[:200]

    try:
        search_results = await search_brave(search_query, num_results=settings.SEARCH_RESULTS_PER_CLAIM)
    except Exception as e:
        # If search fails, return uncertain result
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
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
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

        response_text = response.content[0].text.strip()
        # Parse JSON
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

        result = json.loads(response_text)

    except Exception as e:
        return {
            "truth_percentage": 50,
            "confidence": 0.2,
            "reasoning": f"Could not evaluate: LLM error ({str(e)[:100]})",
            "sources": [],
            "category": "unclear",
        }

    # Combine with sources
    sources = [
        {"title": r.title, "url": r.url, "snippet": r.snippet}
        for r in search_results
    ]

    return {
        "truth_percentage": max(0, min(100, result.get("truth_percentage", 50))),
        "confidence": max(0.0, min(1.0, result.get("confidence", 0.5))),
        "reasoning": result.get("reasoning", "No reasoning provided."),
        "sources": sources,
        "category": result.get("category", "fact"),
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
    semaphore = asyncio.Semaphore(3)
    completed_count = 0
    lock = asyncio.Lock()

    async def check_one(index, claim):
        nonlocal completed_count
        async with semaphore:
            result = await fact_check_claim(claim["text"])
            results[index] = {**claim, **result}
            async with lock:
                completed_count += 1
                if on_progress:
                    on_progress(completed_count, total)

    await asyncio.gather(*(check_one(i, c) for i, c in enumerate(claims)))
    return results
