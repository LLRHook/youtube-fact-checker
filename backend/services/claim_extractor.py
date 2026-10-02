"""Extract check-worthy claims with a structured response."""

from datetime import date

from backend.config import settings
from backend.services.llm import Usage, structured_call
from backend.services.transcript_service import TranscriptResult, build_timestamped_transcript


class ClaimExtractionError(Exception):
    def __init__(self, message: str, usage: Usage | None = None):
        super().__init__(message)
        self.usage = usage if usage is not None else Usage()


EXTRACTION_SYSTEM = """You find the check-worthy factual claims in a YouTube video transcript for an independent fact-checking service.

A claim is check-worthy when it asserts something about the world that evidence could confirm or refute: statistics, quantities, dates, events, scientific, medical, economic or historical assertions, what a person or organization said or did, and specific causal claims.

Skip: opinions and value judgments, predictions, jokes and sarcasm, hypotheticals, rhetorical questions, personal anecdotes nobody else could verify, sponsor reads, calls to action, and statements about the video itself.

For each claim:
- claim: rewrite it so it stands alone. Resolve pronouns and references from the surrounding transcript and include the who, what, when and where needed to check it without watching the video. Keep the speaker's hedges ("about", "nearly", "up to"). Never add facts the speaker did not state or clearly imply. Write it in English even if the transcript is not.
- quote: the speaker's exact words from the transcript, at most 40 words.
- timestamp_seconds: the [MM:SS] or [H:MM:SS] marker of the line where the claim starts, converted to seconds.
- speaker: "creator" for the host or narrator, "guest" for another participant, "quoted" when the speaker attributes the statement to someone else without endorsing it, "unknown" if unclear.
- topic: one or two words (for example "health", "economy", "history", "science", "politics", "technology").
- checkworthiness: 5 = specific and consequential, misleading people if wrong (health, money, safety, public policy, science); 3 = specific but lower stakes; 1 = trivial or common knowledge.
- search_queries: one or two short web search queries (at most 12 words) likely to surface authoritative evidence for or against the claim. Include the key entities, numbers and time frame. Make the first neutral; make the second target the primary source or the strongest counter-evidence.

Split compound statements into separate claims when each part could be true or false on its own. Merge repeats of the same claim and keep the first occurrence. Return at most {max_claims} claims, preferring the most check-worthy. Return an empty list if there are none."""

_CLAIM_PROPERTIES = {
    "claim": {"type": "string"},
    "quote": {"type": "string"},
    "timestamp_seconds": {"type": "number"},
    "speaker": {"type": "string", "enum": ["creator", "guest", "quoted", "unknown"]},
    "topic": {"type": "string"},
    "checkworthiness": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
    "search_queries": {"type": "array", "items": {"type": "string"}},
}
_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": _CLAIM_PROPERTIES,
                "required": list(_CLAIM_PROPERTIES),
                "additionalProperties": False,
            },
        }
    },
    "required": ["claims"],
    "additionalProperties": False,
}


def _truncate(text, limit):
    text = text.strip()
    if len(text) <= limit:
        return text
    prefix = text[: limit - 1]
    if " " in prefix:
        prefix = prefix.rsplit(" ", 1)[0]
    return prefix + "\u2026"


async def extract_claims(transcript: TranscriptResult) -> tuple[list[dict], Usage]:
    content = (
        f"Video title: {transcript.title}\nChannel: {transcript.channel}\n"
        f"Uploaded: {transcript.published_at or 'unknown'}\nToday's date: {date.today().isoformat()}\n"
        f"Transcript language: {transcript.language}\n\n<transcript>\n"
        f"{build_timestamped_transcript(transcript.segments)}\n</transcript>"
    )
    response = await structured_call(
        model=settings.EXTRACTION_MODEL,
        effort=settings.EXTRACTION_EFFORT,
        system=[{"type": "text", "text": EXTRACTION_SYSTEM.format(max_claims=settings.MAX_CLAIMS_PER_VIDEO)}],
        messages=[{"role": "user", "content": content}],
        schema=_SCHEMA,
        max_tokens=16000,
    )
    if response.data is None:
        raise ClaimExtractionError("Could not analyze this transcript. Please try again later.", response.usage)
    claims = []
    seen = set()
    for item in response.data["claims"]:
        text = _truncate(item["claim"], 500)
        if not text or item["checkworthiness"] < settings.MIN_CHECKWORTHINESS or text.casefold() in seen:
            continue
        seen.add(text.casefold())
        queries = [q.strip()[:200] for q in item["search_queries"] if q.strip()][:3]
        claims.append(
            dict(
                text=text,
                quote=item["quote"].strip()[:300],
                timestamp_seconds=max(0, min(transcript.duration_seconds, item["timestamp_seconds"])),
                speaker=item["speaker"],
                topic=item["topic"].strip()[:40],
                checkworthiness=item["checkworthiness"],
                search_queries=queries,
            )
        )
    claims.sort(key=lambda c: (-c["checkworthiness"], c["timestamp_seconds"]))
    claims = claims[: settings.MAX_CLAIMS_PER_VIDEO]
    claims.sort(key=lambda c: c["timestamp_seconds"])
    return claims, response.usage
