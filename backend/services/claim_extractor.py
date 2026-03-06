"""LLM-based claim extraction from transcript text."""

import json
import anthropic
from backend.config import settings

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

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    # Build transcript with timestamps if segments available
    if segments:
        timestamped = []
        for seg in segments:
            mins = int(seg.start // 60)
            secs = int(seg.start % 60)
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

    # Parse JSON from response (handle markdown code blocks)
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

    try:
        claims = json.loads(response_text)
    except json.JSONDecodeError:
        # Try to find JSON array in the response
        start = response_text.find("[")
        end = response_text.rfind("]") + 1
        if start != -1 and end > start:
            try:
                claims = json.loads(response_text[start:end])
            except json.JSONDecodeError:
                return []
        else:
            return []

    # Validate and normalize
    valid_claims = []
    for i, claim in enumerate(claims):
        if isinstance(claim, dict) and "text" in claim:
            valid_claims.append({
                "text": claim["text"],
                "timestamp_seconds": claim.get("timestamp_seconds", 0),
                "category": claim.get("category", "fact"),
            })

    # Cap at max claims
    return valid_claims[: settings.MAX_CLAIMS_PER_VIDEO]
