"""Integration tests for /api/check endpoints."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend import database as db
from backend import main
from backend.models import TaskStatus
from backend.services import pipeline


@pytest.mark.asyncio
class TestCheckEndpoint:
    async def test_invalid_url_400(self, client):
        resp = await client.post("/api/check", json={"youtube_url": "not-a-url"})
        assert resp.status_code == 400

    @patch("backend.services.pipeline.extract_transcript")
    async def test_valid_url_starts_processing(self, mock_transcript, client):
        """A valid URL should return processing status (background task started)."""
        # The background task will fail since extract_transcript is mocked but that's ok
        # We're testing the endpoint returns the right initial response
        mock_transcript.side_effect = Exception("test")
        resp = await client.post("/api/check", json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("processing", "completed", "queued")

    async def test_cached_completed_returns_immediately(self, client, seed_video):
        resp = await client.post("/api/check", json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["data"]["video_title"] == "Test Video"

    async def test_rate_limit_429(self, client, init_test_db, monkeypatch):
        from backend.config import settings

        monkeypatch.setattr(settings, "IP_DAILY_LIMIT", 0)
        resp = await client.post("/api/check", json={"youtube_url": "https://www.youtube.com/watch?v=xxxxxxxxxxx"})
        assert resp.status_code == 429

    async def test_daily_limit_queues(self, client, init_test_db, monkeypatch):
        from backend.config import settings

        monkeypatch.setattr(settings, "DAILY_VIDEO_LIMIT", 0)
        monkeypatch.setattr(settings, "IP_DAILY_LIMIT", 100)
        resp = await client.post("/api/check", json={"youtube_url": "https://www.youtube.com/watch?v=xxxxxxxxxxx"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "queued"


@pytest.mark.asyncio
class TestGetTaskStatus:
    async def test_task_not_found_404(self, client, init_test_db):
        resp = await client.get("/api/check/nonexistent1")
        assert resp.status_code == 404

    async def test_task_completed_from_db(self, client, seed_video):
        resp = await client.get(f"/api/check/{seed_video}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"

    async def test_task_failed_from_db(self, client, init_test_db):
        await db.create_video("fail1234567", "https://youtube.com/watch?v=fail1234567")
        await db.update_video_status("fail1234567", "failed", "Something broke")
        resp = await client.get("/api/check/fail1234567")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert data["error"] == "Something broke"


async def test_task_state_progress(client, monkeypatch):
    from backend.models import TaskStatus, claim_row_to_public
    from backend.services.pipeline import TaskState, tasks

    state = TaskState(
        "inflight123",
        TaskStatus.PROCESSING,
        stage="verifying",
        message="Checking claim 1 of 2...",
        completed=1,
        total=2,
        video={"id": "inflight123", "title": "Title"},
        claims=[claim_row_to_public(dict(index=1, text="Claim", verdict="true")).model_dump()],
    )
    monkeypatch.setitem(tasks, state.task_id, state)
    response = await client.get(f"/api/check/{state.task_id}")
    data = response.json()
    assert data["stage"] == "verifying" and data["completed"] == 1 and data["total"] == 2
    assert data["progress"] == state.message and data["video"]["title"] == "Title"
    assert data["claims"][0]["index"] == 1 and data["claims"][0]["verdict"] == "true"


async def test_budget_gate_queues(client, monkeypatch):
    from unittest.mock import AsyncMock

    from backend.config import settings

    monkeypatch.setattr(db, "spend_today_usd", AsyncMock(return_value=settings.DAILY_BUDGET_USD))
    response = await client.post("/api/check", json={"youtube_url": "https://youtube.com/watch?v=budget12345"})
    assert response.status_code == 200 and response.json()["status"] == "queued"
    assert response.json()["stage"] == "queued"
    assert (await db.get_video("budget12345"))["status"] == "queued"
    polled = await client.get("/api/check/budget12345")
    assert polled.json()["stage"] == "queued"


async def test_completed_task_has_public_claims(client, seed_v2_video):
    response = await client.get(f"/api/check/{seed_v2_video}")
    data = response.json()
    assert data["stage"] == "completed" and len(data["claims"]) == 2
    assert data["claims"][0]["verdict"] == "true"
    assert data["data"]["claims"][1]["verdict"] == "false"


async def test_concurrent_admission_respects_limit(client, monkeypatch):
    monkeypatch.setattr(main, "_admission_lock", asyncio.Lock())
    monkeypatch.setattr(main.settings, "DAILY_VIDEO_LIMIT", 1)
    monkeypatch.setattr(main.settings, "IP_DAILY_LIMIT", 100)
    monkeypatch.setattr(main.settings, "DAILY_BUDGET_USD", 100)
    monkeypatch.setattr(pipeline, "process_video", AsyncMock())
    monkeypatch.setattr(pipeline, "tasks", {})
    monkeypatch.setattr(main, "tasks", pipeline.tasks)
    responses = await asyncio.gather(*[
        client.post("/api/check", json={"youtube_url": f"https://youtube.com/watch?v={video_id}"})
        for video_id in ["concurrent1", "concurrent2"]
    ])
    assert all(response.status_code == 200 for response in responses)
    assert sorted(response.json()["status"] for response in responses) == ["processing", "queued"]
    assert await db.count_videos_today() == 1
    assert len([state for state in pipeline.tasks.values() if state.status == TaskStatus.PROCESSING]) == 1
