"""Integration tests for /api/check endpoints."""

import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from backend import database as db


@pytest.mark.asyncio
class TestCheckEndpoint:
    async def test_invalid_url_400(self, client):
        resp = await client.post("/api/check", json={"youtube_url": "not-a-url"})
        assert resp.status_code == 400

    @patch("backend.main.extract_transcript")
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
