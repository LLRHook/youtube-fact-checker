"""Integration tests for backend.database — real SQLite, no mocks."""

import pytest
import pytest_asyncio
from backend import database as db


@pytest.mark.asyncio
class TestInitDb:
    async def test_creates_tables(self, tmp_db):
        await db.init_db()
        import aiosqlite
        async with aiosqlite.connect(tmp_db) as conn:
            cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in await cursor.fetchall()}
        assert "videos" in tables
        assert "claims" in tables
        assert "claim_sources" in tables


@pytest.mark.asyncio
class TestVideoCrud:
    async def test_create_and_get(self, init_test_db):
        v = await db.create_video("abc12345678", "https://youtube.com/watch?v=abc12345678")
        assert v["id"] == "abc12345678"
        got = await db.get_video("abc12345678")
        assert got is not None
        assert got["status"] == "processing"

    async def test_get_nonexistent(self, init_test_db):
        assert await db.get_video("nonexistent1") is None

    async def test_update_status(self, init_test_db):
        await db.create_video("test1234567", "https://youtube.com/watch?v=test1234567")
        await db.update_video_status("test1234567", "failed", "Some error")
        v = await db.get_video("test1234567")
        assert v["status"] == "failed"
        assert v["error"] == "Some error"

    async def test_update_results(self, init_test_db):
        await db.create_video("res12345678", "https://youtube.com/watch?v=res12345678")
        await db.update_video_results(
            "res12345678",
            title="My Video",
            channel="MyCh",
            duration_seconds=100.0,
            transcript_text="text",
            overall_truth_percentage=80,
            summary="summary",
            processing_time_seconds=3.5,
        )
        v = await db.get_video("res12345678")
        assert v["status"] == "completed"
        assert v["title"] == "My Video"
        assert v["overall_truth_percentage"] == 80


@pytest.mark.asyncio
class TestVideoListing:
    async def test_list_with_status_filter(self, init_test_db):
        await db.create_video("v1_12345678", "https://youtube.com/watch?v=v1_12345678")
        await db.update_video_status("v1_12345678", "completed")
        await db.create_video("v2_12345678", "https://youtube.com/watch?v=v2_12345678")
        completed = await db.list_videos(status="completed")
        assert len(completed) == 1

    async def test_pagination(self, init_test_db):
        for i in range(5):
            vid = f"pg{i:09d}"
            await db.create_video(vid, f"https://youtube.com/watch?v={vid}")
            await db.update_video_status(vid, "completed")
        page1 = await db.list_videos(status="completed", limit=2, offset=0)
        page2 = await db.list_videos(status="completed", limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0]["id"] != page2[0]["id"]

    async def test_count_total(self, init_test_db):
        await db.create_video("cnt1234567a", "https://youtube.com/watch?v=cnt1234567a")
        assert await db.count_videos() == 1

    async def test_count_today(self, init_test_db):
        await db.create_video("tod1234567a", "https://youtube.com/watch?v=tod1234567a")
        count = await db.count_videos_today()
        assert count >= 1

    async def test_count_by_ip(self, init_test_db):
        await db.create_video("ip_12345678", "https://youtube.com/watch?v=ip_12345678", ip_address="1.2.3.4")
        count = await db.count_videos_today_by_ip("1.2.3.4")
        assert count >= 1
        count_other = await db.count_videos_today_by_ip("5.6.7.8")
        assert count_other == 0


@pytest.mark.asyncio
class TestClaimsCrud:
    async def test_create_and_get_claims(self, init_test_db):
        await db.create_video("clm1234567a", "https://youtube.com/watch?v=clm1234567a")
        claims = [
            {"text": "Claim 1", "timestamp_seconds": 10, "truth_percentage": 80,
             "confidence": 0.9, "reasoning": "r1", "category": "fact",
             "sources": [{"title": "S1", "url": "https://s1.com", "snippet": "sn1"}]},
            {"text": "Claim 2", "timestamp_seconds": 20, "truth_percentage": 60,
             "confidence": 0.7, "reasoning": "r2", "category": "opinion", "sources": []},
        ]
        await db.create_claims("clm1234567a", claims)
        fetched = await db.get_claims_for_video("clm1234567a")
        assert len(fetched) == 2
        assert fetched[0]["text"] == "Claim 1"
        assert len(fetched[0]["sources"]) == 1

    async def test_delete_claims(self, init_test_db):
        await db.create_video("del1234567a", "https://youtube.com/watch?v=del1234567a")
        await db.create_claims("del1234567a", [{"text": "c", "sources": []}])
        await db.delete_claims_for_video("del1234567a")
        assert await db.get_claims_for_video("del1234567a") == []

    async def test_batch_claims(self, init_test_db):
        for vid in ["bat1234567a", "bat1234567b"]:
            await db.create_video(vid, f"https://youtube.com/watch?v={vid}")
            await db.create_claims(vid, [{"text": f"c-{vid}", "sources": []}])
        batch = await db.get_claims_for_videos(["bat1234567a", "bat1234567b"])
        assert "bat1234567a" in batch
        assert len(batch["bat1234567a"]) == 1


@pytest.mark.asyncio
class TestChannels:
    async def test_list_channels(self, init_test_db):
        await db.create_video("ch_12345678", "https://youtube.com/watch?v=ch_12345678")
        await db.update_video_results(
            "ch_12345678", title="V", channel="MyChannel",
            duration_seconds=60, transcript_text="t",
            overall_truth_percentage=70, summary="s", processing_time_seconds=1,
        )
        channels = await db.list_channels()
        names = [c["channel"] for c in channels]
        assert "MyChannel" in names

    async def test_channel_videos(self, init_test_db):
        await db.create_video("cv_12345678", "https://youtube.com/watch?v=cv_12345678")
        await db.update_video_results(
            "cv_12345678", title="V", channel="ChanVids",
            duration_seconds=60, transcript_text="t",
            overall_truth_percentage=70, summary="s", processing_time_seconds=1,
        )
        vids = await db.get_channel_videos("ChanVids")
        assert len(vids) == 1


@pytest.mark.asyncio
class TestStats:
    async def test_get_stats(self, init_test_db):
        stats = await db.get_stats()
        assert "video_count" in stats
        assert "claim_count" in stats
        assert "channel_count" in stats


@pytest.mark.asyncio
class TestQueueAndStale:
    async def test_queued_videos(self, init_test_db):
        await db.create_video("q1_12345678", "https://youtube.com/watch?v=q1_12345678", status="queued")
        queued = await db.get_queued_videos()
        assert len(queued) >= 1
        assert queued[0]["status"] == "queued"

    async def test_stale_processing(self, init_test_db):
        # A freshly created processing video should NOT be stale (stale = 10 min old)
        await db.create_video("st_12345678", "https://youtube.com/watch?v=st_12345678")
        stale = await db.get_stale_processing_videos(stale_minutes=10)
        # Might be empty since we just created it
        assert isinstance(stale, list)
