from unittest.mock import AsyncMock

import pytest

from backend.services import claim_extractor as ce
from backend.services.llm import LLMResult, Usage
from backend.services.transcript_service import TranscriptResult, TranscriptSegment


@pytest.fixture
def transcript():
    return TranscriptResult(
        "dQw4w9WgXcQ",
        "Example title",
        "Example channel",
        120,
        [TranscriptSegment("Exact words", 12, 5)],
        "Exact words",
        published_at="2020-02-03",
        language="de",
    )


def item(text="A specific claim", weight=5, timestamp=12, **kwargs):
    return dict(
        claim=text,
        quote="Exact words",
        timestamp_seconds=timestamp,
        speaker="creator",
        topic="science",
        checkworthiness=weight,
        search_queries=["neutral query", "primary source"],
        **kwargs,
    )


async def extract(monkeypatch, transcript, items):
    mock = AsyncMock(return_value=LLMResult({"claims": items}, Usage(input_tokens=30, cost_usd=0.01), "end_turn"))
    monkeypatch.setattr(ce, "structured_call", mock)
    result = await ce.extract_claims(transcript)
    return result, mock


async def test_filter_dedupe_and_order(monkeypatch, transcript):
    (claims, usage), mock = await extract(
        monkeypatch,
        transcript,
        [
            item("Lower priority", 3, 10),
            item("More important", 5, 30),
            item("MORE IMPORTANT", 5, 60),
            item("Trivial", 2, 0),
            item(" ", 5, 0),
            item("First", 4, 0),
        ],
    )
    assert [c["text"] for c in claims] == ["First", "Lower priority", "More important"]
    assert claims[-1]["timestamp_seconds"] == 30
    assert set(claims[0]) == {
        "text",
        "quote",
        "timestamp_seconds",
        "speaker",
        "topic",
        "checkworthiness",
        "search_queries",
    }
    assert usage.cost_usd == 0.01
    kwargs = mock.call_args.kwargs
    assert kwargs["max_tokens"] == 16000
    assert kwargs["schema"]["additionalProperties"] is False
    assert "Transcript language: de" in kwargs["messages"][0]["content"]
    assert "Uploaded: 2020-02-03" in kwargs["messages"][0]["content"]
    assert "[00:12] Exact words" in kwargs["messages"][0]["content"]


async def test_cap_prefers_weight_then_time(monkeypatch, transcript):
    monkeypatch.setattr(ce.settings, "MAX_CLAIMS_PER_VIDEO", 2)
    (claims, _), _ = await extract(
        monkeypatch, transcript, [item("Low", 3, 0), item("Late", 5, 50), item("Early", 5, 20), item("Later", 5, 80)]
    )
    assert [c["text"] for c in claims] == ["Early", "Late"]


async def test_truncation_and_timestamp_clamping(monkeypatch, transcript):
    data = item("word " * 130, timestamp=500)
    data.update(quote="q" * 400, topic="t" * 60, search_queries=[" ", " first ", "x" * 250, "third", "fourth"])
    (claims, _), _ = await extract(monkeypatch, transcript, [data, item("Negative", timestamp=-5)])
    assert claims[0]["timestamp_seconds"] == 0
    long = claims[1]
    assert long["timestamp_seconds"] == 120
    assert len(long["text"]) <= 500 and long["text"].endswith("\u2026")
    assert len(long["quote"]) == 300 and len(long["topic"]) == 40
    assert long["search_queries"] == ["first", "x" * 200, "third"]


async def test_empty_claims(monkeypatch, transcript):
    (claims, _), _ = await extract(monkeypatch, transcript, [])
    assert claims == []


@pytest.mark.parametrize("error", ["refusal", "max_tokens", "invalid_json", "api_error: APIError"])
async def test_failed_call_raises(monkeypatch, transcript, error):
    usage = Usage(100, 20, cost_usd=0.01)
    monkeypatch.setattr(ce, "structured_call", AsyncMock(return_value=LLMResult(None, usage, "", error)))
    with pytest.raises(ce.ClaimExtractionError, match="Could not analyze this transcript. Please try again later.") as exc:
        await ce.extract_claims(transcript)
    assert exc.value.usage is usage
