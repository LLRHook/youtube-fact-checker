"""Integration tests for /api/videos, /api/health, /api/stats endpoints."""

import pytest
from backend import database as db


@pytest.mark.asyncio
class TestVideosEndpoint:
    async def test_list_empty(self, client, init_test_db):
        resp = await client.get("/api/videos")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_with_data(self, client, seed_video):
        resp = await client.get("/api/videos")
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Test Video"

    async def test_pagination(self, client, init_test_db):
        for i in range(3):
            vid = f"pv{i:09d}"
            await db.create_video(vid, f"https://youtube.com/watch?v={vid}")
            await db.update_video_results(
                vid, title=f"V{i}", channel="Ch",
                duration_seconds=60, transcript_text="t",
                overall_truth_percentage=50, summary="s", processing_time_seconds=1,
            )
        resp = await client.get("/api/videos?page=1&limit=2")
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["pages"] == 2

    async def test_page_clamping(self, client, init_test_db):
        resp = await client.get("/api/videos?page=999")
        data = resp.json()
        assert data["page"] >= 1

    async def test_video_detail(self, client, seed_video):
        resp = await client.get(f"/api/videos/{seed_video}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Video"
        assert len(data["claims"]) == 2

    async def test_video_not_found(self, client, init_test_db):
        resp = await client.get("/api/videos/xxxxxxxxxxx")
        assert resp.status_code == 404

    async def test_processing_returns_404(self, client, init_test_db):
        await db.create_video("proc1234567", "https://youtube.com/watch?v=proc1234567")
        resp = await client.get("/api/videos/proc1234567")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestHealthAndStats:
    async def test_health(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_stats(self, client, init_test_db):
        resp = await client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "video_count" in data
