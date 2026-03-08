"""Integration tests for /api/channels endpoints."""

import pytest
from backend import database as db


@pytest.mark.asyncio
class TestChannelsEndpoint:
    async def test_list_channels(self, client, seed_video):
        resp = await client.get("/api/channels")
        assert resp.status_code == 200
        data = resp.json()
        channels = [c["channel"] for c in data]
        assert "TestChannel" in channels

    async def test_excludes_unknown(self, client, init_test_db):
        await db.create_video("unk1234567a", "https://youtube.com/watch?v=unk1234567a")
        await db.update_video_results(
            "unk1234567a", title="V", channel="Unknown",
            duration_seconds=60, transcript_text="t",
            overall_truth_percentage=50, summary="s", processing_time_seconds=1,
        )
        resp = await client.get("/api/channels")
        data = resp.json()
        channels = [c["channel"] for c in data]
        assert "Unknown" not in channels

    async def test_channel_detail(self, client, seed_video):
        resp = await client.get("/api/channels/TestChannel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["channel"] == "TestChannel"
        assert data["video_count"] == 1

    async def test_channel_not_found(self, client, init_test_db):
        resp = await client.get("/api/channels/NonexistentChannel")
        assert resp.status_code == 404

    async def test_invalid_channel_name_too_long(self, client, init_test_db):
        resp = await client.get(f"/api/channels/{'x' * 201}")
        assert resp.status_code == 400

    async def test_path_traversal_blocked(self, client, init_test_db):
        # URL-encoded slashes may be decoded differently by routers,
        # but either 400 (validation) or 404 (no videos) is acceptable
        resp = await client.get("/api/channels/..%2F..%2Fetc%2Fpasswd")
        assert resp.status_code in (400, 404)
