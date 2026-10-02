import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from backend import database as db
from backend.models import TaskStatus
from backend.services import claim_extractor as ce
from backend.services import pipeline
from backend.services.claim_extractor import ClaimExtractionError
from backend.services.fact_checker import _result
from backend.services.llm import LLMResult, Usage
from backend.services.transcript_service import TranscriptError, TranscriptResult, TranscriptSegment, VideoTooLongError


@pytest.fixture
def transcript():
    return TranscriptResult(
        "pipeline123",
        "Title",
        "Channel",
        120,
        [TranscriptSegment("Words", 12, 3)],
        "Words",
        channel_id="UC123",
        published_at="2020-01-01",
        language="en",
    )


async def test_process_persists_cost_metadata_and_progress(monkeypatch, init_test_db, transcript):
    video_id = transcript.video_id
    await db.create_video(video_id, "https://youtube.com/watch?v=pipeline123")
    state = pipeline.TaskState(video_id, TaskStatus.PROCESSING)
    monkeypatch.setitem(pipeline.tasks, video_id, state)

    def extract(*args):
        assert state.stage == "transcript" and state.message == "Fetching transcript…"
        return transcript

    async def claims(_):
        assert state.stage == "claims" and state.video["published_at"] == "2020-01-01"
        return [dict(text="Claim 1"), dict(text="Claim 2")], Usage(100, 10, cost_usd=0.01)

    async def verify(claims, _, callback):
        assert state.stage == "verifying" and state.total == 2
        merged = [{**c, **_result("true", "high", "Evidence")} for c in claims]
        for index in [1, 0]:
            callback(index, merged[index])
        assert [c["index"] for c in state.claims] == [2, 1] and state.completed == 2
        assert state.message == "Checking claim 2 of 2…"
        return merged, Usage(200, 20, cost_usd=0.02), 4

    async def summarize(*args):
        assert state.stage == "summary" and state.message == "Writing the summary…"
        return dict(summary="Report", key_issues=["Issue"]), Usage(300, 30, cost_usd=0.03)

    monkeypatch.setattr(pipeline, "extract_transcript", extract)
    monkeypatch.setattr(pipeline, "extract_claims", claims)
    monkeypatch.setattr(pipeline, "verify_all", verify)
    monkeypatch.setattr(pipeline, "summarize", summarize)
    await pipeline.process_video(video_id, video_id, "https://youtube.com/watch?v=pipeline123")
    assert video_id not in pipeline.tasks and state.stage == "completed"
    video = await db.get_video(video_id)
    assert video["status"] == "completed" and video["pipeline_version"] == 2
    assert video["cost_usd"] == pytest.approx(0.06) and video["search_requests"] == 4
    assert video["input_tokens"] == 600 and video["output_tokens"] == 60
    assert video["channel_id"] == "UC123" and video["published_at"] == "2020-01-01"
    assert video["overall_truth_percentage"] == 95 and video["summary"] == "Report"
    assert [c["text"] for c in await db.get_claims_for_video(video_id)] == ["Claim 1", "Claim 2"]


async def test_no_claims_completes_without_verdict_calls(monkeypatch, init_test_db, transcript):
    await db.create_video(transcript.video_id, "url")
    monkeypatch.setattr(pipeline, "extract_transcript", Mock(return_value=transcript))
    monkeypatch.setattr(pipeline, "extract_claims", AsyncMock(return_value=([], Usage(cost_usd=0.01))))
    verify = AsyncMock()
    summary = AsyncMock()
    monkeypatch.setattr(pipeline, "verify_all", verify)
    monkeypatch.setattr(pipeline, "summarize", summary)
    await pipeline.process_video(transcript.video_id, transcript.video_id, "url")
    video = await db.get_video(transcript.video_id)
    assert video["summary"] == "We didn't find any check-worthy factual claims in this video."
    assert video["overall_truth_percentage"] == 50 and video["key_issues"] == "[]" and video["pipeline_version"] == 2
    verify.assert_not_awaited()
    summary.assert_not_awaited()


@pytest.mark.parametrize(
    "error,expected",
    [
        (VideoTooLongError("Too long"), "Too long"),
        (TranscriptError("Transcript unavailable"), "Transcript unavailable"),
        (ClaimExtractionError("Analysis unavailable"), "Analysis unavailable"),
        (RuntimeError("internal details"), "An unexpected error occurred. Please try again later."),
    ],
)
async def test_process_failure_cleanup(monkeypatch, init_test_db, transcript, error, expected):
    await db.create_video(transcript.video_id, "url")
    state = pipeline.TaskState(transcript.video_id, TaskStatus.PROCESSING)
    monkeypatch.setitem(pipeline.tasks, transcript.video_id, state)
    monkeypatch.setattr(pipeline, "extract_transcript", Mock(side_effect=error))
    await pipeline.process_video(transcript.video_id, transcript.video_id, "url")
    assert transcript.video_id not in pipeline.tasks and state.stage == "failed"
    video = await db.get_video(transcript.video_id)
    assert video["status"] == "failed" and video["error"] == expected


@pytest.mark.parametrize("videos,spend,expected", [(0, 0, True), (30, 0, False), (0, 10.0, False), (29, 9.99, True)])
async def test_capacity(monkeypatch, videos, spend, expected):
    monkeypatch.setattr(pipeline, "tasks", {})
    monkeypatch.setattr(pipeline.settings, "DAILY_VIDEO_LIMIT", 30)
    monkeypatch.setattr(pipeline.settings, "DAILY_BUDGET_USD", 10.0)
    monkeypatch.setattr(db, "count_videos_today", AsyncMock(return_value=videos))
    monkeypatch.setattr(db, "spend_today_usd", AsyncMock(return_value=spend))
    assert await pipeline.capacity_available() is expected


async def test_inflight_estimate_blocks_capacity(monkeypatch):
    monkeypatch.setattr(pipeline.settings, "DAILY_VIDEO_LIMIT", 30)
    monkeypatch.setattr(pipeline.settings, "DAILY_BUDGET_USD", 1.0)
    monkeypatch.setattr(db, "count_videos_today", AsyncMock(return_value=0))
    monkeypatch.setattr(db, "spend_today_usd", AsyncMock(return_value=0.4))
    monkeypatch.setattr(pipeline, "tasks", {"active": pipeline.TaskState("active", TaskStatus.PROCESSING)})
    assert not await pipeline.capacity_available()
    pipeline.tasks["active"].status = TaskStatus.COMPLETED
    assert await pipeline.capacity_available()


async def test_extraction_refusal_persists_spend(monkeypatch, init_test_db, transcript):
    await db.create_video(transcript.video_id, "url")
    monkeypatch.setattr(pipeline, "extract_transcript", Mock(return_value=transcript))
    monkeypatch.setattr(ce, "structured_call", AsyncMock(return_value=LLMResult(
        None, Usage(100, 20, cost_usd=0.01), "refusal", "refusal"
    )))
    await pipeline.process_video(transcript.video_id, transcript.video_id, "url")
    video = await db.get_video(transcript.video_id)
    assert video["status"] == "failed"
    assert video["cost_usd"] == pytest.approx(0.01)
    assert (video["input_tokens"], video["output_tokens"], video["search_requests"]) == (100, 20, 0)
    assert await db.spend_today_usd() == pytest.approx(0.01)


async def test_summary_failure_persists_accumulated_cost(monkeypatch, init_test_db, transcript):
    await db.create_video(transcript.video_id, "url")
    await db.add_video_cost(transcript.video_id, 0.01, 10, 1, 1)
    monkeypatch.setattr(pipeline, "extract_transcript", Mock(return_value=transcript))
    monkeypatch.setattr(pipeline, "extract_claims", AsyncMock(return_value=([dict(text="Claim")], Usage(100, 10, cost_usd=0.02))))
    monkeypatch.setattr(pipeline, "verify_all", AsyncMock(return_value=([dict(text="Claim")], Usage(200, 20, cost_usd=0.03), 4)))
    monkeypatch.setattr(pipeline, "summarize", AsyncMock(side_effect=RuntimeError("Summary failed")))
    await pipeline.process_video(transcript.video_id, transcript.video_id, "url")
    video = await db.get_video(transcript.video_id)
    assert video["status"] == "failed" and video["cost_usd"] == pytest.approx(0.06)
    assert (video["input_tokens"], video["output_tokens"], video["search_requests"]) == (310, 31, 5)


async def test_queue_status_failure_releases_reservation(monkeypatch):
    sleeps = []

    async def sleep(delay):
        sleeps.append(delay)
        if len(sleeps) > 1:
            raise asyncio.CancelledError

    monkeypatch.setattr(pipeline.asyncio, "sleep", sleep)
    monkeypatch.setattr(pipeline, "tasks", {})
    monkeypatch.setattr(db, "prune_search_cache", AsyncMock())
    monkeypatch.setattr(db, "get_stale_processing_videos", AsyncMock(return_value=[]))
    monkeypatch.setattr(db, "get_queued_videos", AsyncMock(return_value=[dict(id="queued", youtube_url="url")]))
    monkeypatch.setattr(db, "update_video_status", AsyncMock(side_effect=RuntimeError("Database failed")))
    monkeypatch.setattr(pipeline, "capacity_available", AsyncMock(return_value=True))
    process = AsyncMock()
    monkeypatch.setattr(pipeline, "process_video", process)
    await pipeline.queue_processor()
    assert pipeline.tasks == {}
    process.assert_not_awaited()
    assert sleeps == [5, min(pipeline.settings.QUEUE_INTERVAL_MINUTES * 60 * 2, 3600)]


async def test_queue_prunes_recovers_stale_and_stops_at_capacity(monkeypatch):
    sleeps = []

    async def sleep(delay):
        sleeps.append(delay)
        if len(sleeps) > 1:
            raise asyncio.CancelledError

    prune = AsyncMock()
    status = AsyncMock()
    process = AsyncMock()
    monkeypatch.setattr(pipeline.asyncio, "sleep", sleep)
    monkeypatch.setattr(db, "prune_search_cache", prune)
    monkeypatch.setattr(db, "get_stale_processing_videos", AsyncMock(return_value=[dict(id="stale")]))
    monkeypatch.setattr(db, "update_video_status", status)
    monkeypatch.setattr(
        db,
        "get_queued_videos",
        AsyncMock(return_value=[dict(id="first", youtube_url="url1"), dict(id="second", youtube_url="url2")]),
    )
    monkeypatch.setattr(pipeline, "capacity_available", AsyncMock(side_effect=[True, False]))
    monkeypatch.setattr(pipeline, "process_video", process)
    monkeypatch.setattr(pipeline, "tasks", {})
    await pipeline.queue_processor()
    assert sleeps[0] == 5
    prune.assert_awaited_once_with(pipeline.settings.SEARCH_CACHE_DAYS)
    assert [c.args for c in status.await_args_list] == [("stale", "queued"), ("first", "processing")]
    process.assert_awaited_once_with("first", "first", "url1")
