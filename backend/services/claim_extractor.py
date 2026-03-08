"""LLM-based claim extraction from transcript text."""

import logging
import anthropic
from backend.config import settings
from backend.utils.json_parser import parse_llm_json

logger = logging.getLogger(__name__)

_anthropic_client: anthropic.Anthropic | None = None


def _get_anthropic_client() -> anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _anthropic_client


def close_anthropic_client():
    """Close the shared sync Anthropic client. Call on app shutdown."""
    global _anthropic_client
    if _anthropic_client is not None:
        _anthropic_client.close()
        _anthropic_client = None


CLAIM_EXTRACTION_SYSTEM = """You are a fact-checking assistant analyzing a YouTube video transcript.

Your task: Extract ONLY explicit factual claims the content creator makes.

EXCLUDE:
- Greetings, salutations, pleasantries ("hey guys", "welcome back")
- Pure opinions or subjective statements ("I think", "In my opinion", "I love")
- Questions the creator asks
- Music or background audio markers ([Music], [Applause])
- Quotes explicitly attributed to others (unless the creator endorses the claim)
- Vague statements without specific, verifiable assertions
- Self-referential statements ("I uploaded a video last week")
- Calls to action ("subscribe", "like this video")

INCLUDE:
- Specific factual assertions (dates, numbers, statistics, scientific claims)
- Verifiable statements about events, people, places, history
- Claims about how things work (science, technology, health, etc.)
- Attributions of actions or statements to public figures or organizations

For each claim, provide:
1. "text" - The exact factual claim (clean it up for clarity but preserve meaning)
2. "timestamp_seconds" - The timestamp in seconds where the claim STARTS. Use the exact [MM:SS] timestamp shown before the line containing the claim. Convert MM:SS to seconds (e.g., [02:15] = 135). Do NOT estimate or approximate — use the timestamp from the transcript.
3. "category" - One of: "fact", "opinion", or "unclear"

Return ONLY a JSON array. If no factual claims found, return an empty array [].
Example: [{"text": "The Great Wall of China is visible from space", "timestamp_seconds": 45, "category": "fact"}]"""


def extract_claims(transcript_text: str, segments: list = None) -> list[dict]:
    """
    Use Claude to extract factual claims from a transcript.

    Args:
        transcript_text: Full transcript text
        segments: Optional list of TranscriptSegment objects for timestamp context

    Returns:
        List of claim dicts with text, timestamp_seconds, category
    """
    if not settings.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set. Add it to your .env file.")

    client = _get_anthropic_client()

    # Build transcript with timestamps if segments available
    if segments:
        timestamped = []
        for seg in segments:
            start = seg.start
            if not isinstance(start, (int, float)) or start < 0:
                start = 0.0
            start = min(start, 86400.0)
            mins = int(start // 60)
            secs = int(start % 60)
            timestamped.append(f"[{mins:02d}:{secs:02d}] {seg.text}")
        transcript_for_llm = "\n".join(timestamped)
    else:
        transcript_for_llm = transcript_text

    user_prompt = f"""Analyze this YouTube video transcript and extract all factual claims.

TRANSCRIPT:
{transcript_for_llm}

Return ONLY a JSON array of claims. No other text."""

    response = client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=4096,
        system=CLAIM_EXTRACTION_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )

    response_text = response.content[0].text.strip()
    claims = parse_llm_json(response_text)
    if not isinstance(claims, list):
        return []

    # Validate and normalize
    valid_categories = {"fact", "opinion", "unclear"}
    valid_claims = []
    for claim in claims:
        if isinstance(claim, dict) and "text" in claim:
            category = claim.get("category", "fact")
            if category not in valid_categories:
                category = "fact"
            try:
                ts = max(0.0, float(claim.get("timestamp_seconds", 0)))
            except (TypeError, ValueError):
                logger.warning("Invalid timestamp for claim: %.50s", claim.get("text", ""))
                ts = 0.0
            text = claim["text"].strip()
            if len(text) > 500:
                truncated = text[:500]
                last_space = truncated.rfind(' ')
                if last_space > 400:
                    text = truncated[:last_space] + "…"
                else:
                    text = truncated + "…"
                logger.info("Truncated claim from %d to %d chars", len(claim["text"]), len(text))
            if not text:
                continue
            valid_claims.append({
                "text": text,
                "timestamp_seconds": ts,
                "category": category,
            })

    # Cap at max claims
    return valid_claims[: settings.MAX_CLAIMS_PER_VIDEO]
