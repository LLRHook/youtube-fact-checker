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
                vid,
                title=f"V{i}",
                channel="Ch",
                duration_seconds=60,
                transcript_text="t",
                overall_truth_percentage=50,
                summary="s",
                processing_time_seconds=1,
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


async def test_v2_detail_fields(client, seed_v2_video):
    data = (await client.get(f"/api/videos/{seed_v2_video}")).json()
    assert data["pipeline_version"] == 2 and data["model"] == "claude-sonnet-5-5"
    assert data["channel_id"] == "UCscience" and data["published_at"] == "2024-01-02"
    assert data["key_issues"] == ["The second claim is false."]
    assert data["verdict_counts"] == {"true": 1, "false": 1} and data["public_score"] == 50
    assert data["thumbnail_url"] == f"https://i.ytimg.com/vi/{seed_v2_video}/hqdefault.jpg"
    claim = data["claims"][0]
    assert claim["index"] == 1 and claim["quote"] == "Earth orbits the Sun."
    assert claim["checkworthiness"] == 5
    assert claim["verdict"] == "true" and claim["confidence_label"] == "high"
    assert claim["sources"][0]["stance"] == "supports" and claim["sources"][0]["domain"] == "nasa.gov"
    assert claim["feedback"] == {"helpful": 0, "not_helpful": 0}


async def test_legacy_detail_mapping(client, seed_video):
    data = (await client.get(f"/api/videos/{seed_video}")).json()
    assert data["pipeline_version"] == 1 and data["model"] == "" and data["key_issues"] == []
    assert data["verdict_counts"] == {"true": 2} and data["public_score"] == 93
    assert [c["verdict"] for c in data["claims"]] == ["true", "true"]
    assert data["claims"][0]["confidence_label"] == "high"
    assert data["claims"][0]["checkworthiness"] == 0


async def test_v2_no_checkable_score_and_bad_key_issues(client, seed_v2_video):
    await db.delete_claims_for_video(seed_v2_video)
    await db.create_claims(seed_v2_video, [dict(text="Unknown", verdict="unverifiable", category="unclear")])
    async with db._db() as connection:
        await connection.execute("UPDATE videos SET key_issues='invalid' WHERE id=?", (seed_v2_video,))
        await connection.commit()
    data = (await client.get(f"/api/videos/{seed_v2_video}")).json()
    assert data["public_score"] is None and data["key_issues"] == []


async def test_sort_search_and_summary_fields(client, seed_video, seed_v2_video):
    highest = (await client.get("/api/videos?sort=highest")).json()
    assert [v["id"] for v in highest["items"]] == [seed_video, seed_v2_video]
    lowest = (await client.get("/api/videos?sort=lowest")).json()
    assert [v["id"] for v in lowest["items"]] == [seed_v2_video, seed_video]
    for sort in ["newest", "invalid"]:
        data = (await client.get(f"/api/videos?sort={sort}")).json()
        assert [v["id"] for v in data["items"]] == sorted([seed_video, seed_v2_video], reverse=True)
    for query in ["science report", "SCIENCECHANNEL"]:
        data = (await client.get("/api/videos", params={"q": query, "limit": 1})).json()
        assert data["total"] == 1 and data["items"][0]["id"] == seed_v2_video
        item = data["items"][0]
        assert item["verdict_counts"] == {"true": 1, "false": 1}
        assert item["published_at"] == "2024-01-02" and item["thumbnail_url"].endswith("/hqdefault.jpg")
    assert (await client.get("/api/videos?q=missing")).json()["total"] == 0


async def test_feedback_upsert(client, seed_v2_video):
    path = f"/api/videos/{seed_v2_video}/claims/1/feedback"
    for helpful in [True, True, False]:
        response = await client.post(path, json={"helpful": helpful}, headers={"X-Forwarded-For": "1.2.3.4"})
        assert response.status_code == 204 and response.content == b""
    response = await client.post(path, json={"helpful": True}, headers={"X-Forwarded-For": "2.3.4.5"})
    assert response.status_code == 204
    assert await db.get_feedback_counts(seed_v2_video) == {1: {"helpful": 1, "not_helpful": 1}}
    data = (await client.get(f"/api/videos/{seed_v2_video}")).json()
    assert data["claims"][0]["feedback"] == {"helpful": 1, "not_helpful": 1}


async def test_feedback_404_and_bad_body(client, seed_v2_video):
    await db.create_video("pending1234", "https://youtube.com/watch?v=pending1234")
    for video_id, index in [("missing1234", 1), ("pending1234", 1), (seed_v2_video, 99), (seed_v2_video, 0)]:
        response = await client.post(f"/api/videos/{video_id}/claims/{index}/feedback", json={"helpful": True})
        assert response.status_code == 404
    response = await client.post(f"/api/videos/{seed_v2_video}/claims/1/feedback", json={})
    assert response.status_code == 422
