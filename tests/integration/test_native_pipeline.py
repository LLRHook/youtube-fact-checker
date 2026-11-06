"""HTTP -> real Rust processor -> mocked providers -> temporary SQLite persistence."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock

import pytest

from backend import database as db
from backend.services import claim_extractor, transcript_service, fact_checker


@pytest.mark.asyncio
@pytest.mark.parametrize("timestamp,expected_timestamp", [
    (999, 120), ("١٢.٥", 12.5), ("１２.５", 12.5), ("1_2.5", 12.5),
])
async def test_request_pipeline_and_cached_replay(client, monkeypatch, timestamp, expected_timestamp):
    from backend.main import tasks
    video_id = "a-b_c-D_E-f"
    tasks.pop(video_id, None)
    monkeypatch.setattr(transcript_service, "get_video_info", lambda _: dict(title="Synthetic", channel="Test", duration=120))
    rows = [SimpleNamespace(text="Synthetic caption 界", start=65, duration=2),
            SimpleNamespace(text="[Music]", start=0, duration=1)]
    captions = MagicMock(return_value=SimpleNamespace(fetch=lambda _: rows))
    monkeypatch.setattr(transcript_service, "YouTubeTranscriptApi", captions)
    model = MagicMock()
    model.messages.create.return_value = SimpleNamespace(content=[SimpleNamespace(text='```json\n' + json.dumps({"claims": [
        {"text": None}, {"text": "  Synthetic claim 界  ", "timestamp_seconds": timestamp, "category": []},
    ]}) + '\n```')])
    monkeypatch.setattr(claim_extractor, "_get_anthropic_client", lambda: model)
    monkeypatch.setattr(fact_checker, "search_brave", AsyncMock(return_value=[]))
    scorer = MagicMock()
    scorer.messages.create = AsyncMock(return_value=SimpleNamespace(content=[SimpleNamespace(text='```json\n{"truth_percentage":80,"confidence":0.9,"reasoning":"Synthetic evidence","category":"fact"}\n```')]))
    monkeypatch.setattr(fact_checker, "_get_anthropic_client", lambda: scorer)

    response = await client.post("/api/check", json={"youtube_url": f"https://youtube.com/watch?feature=share&v={video_id}"})
    assert response.status_code == 200
    stored = await db.get_video(video_id)
    assert stored["status"] == "completed"
    assert stored["transcript_text"] == "Synthetic caption 界"
    claims = await db.get_claims_for_video(video_id)
    assert len(claims) == 1
    assert claims[0]["text"] == "Synthetic claim 界"
    assert claims[0]["timestamp_seconds"] == expected_timestamp
    assert claims[0]["category"] == "fact"
    assert claims[0]["truth_percentage"] == 80
    assert "[01:05] Synthetic caption 界" in model.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "[Music]" not in model.messages.create.call_args.kwargs["messages"][0]["content"]
    # Cached replay must preserve results and avoid processing/provider calls.
    response = await client.post("/api/check", json={"youtube_url": video_id})
    assert response.json()["status"] == "completed"
    assert response.json()["data"]["claims"][0]["timestamp_seconds"] == expected_timestamp
    model.messages.create.assert_called_once()
    captions.assert_called_once()
    scorer.messages.create.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["https://evilyoutube.com/watch?v=a-b_c-D_E-f",
    "https://example.com/youtube.com/watch?v=a-b_c-D_E-f", "https://youtu.be/a-b_c-D_E-fextra"])
async def test_invalid_host_or_id_fails_before_providers(url, client, monkeypatch):
    fetch = MagicMock()
    monkeypatch.setattr(transcript_service, "get_video_info", fetch)
    response = await client.post("/api/check", json={"youtube_url": url})
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid YouTube URL."
    fetch.assert_not_called()
