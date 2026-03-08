"""Shared fixtures for the YouTube Fact Checker test suite."""

import os
import tempfile
import asyncio

import pytest
import pytest_asyncio

# Set dummy env vars before any backend imports so config.Settings reads them
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("BRAVE_API_KEY", "test-key")

from backend import database as db  # noqa: E402


@pytest.fixture()
def tmp_db(monkeypatch, tmp_path):
    """Create a temporary SQLite database and patch _DB_PATH."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "_DB_PATH", db_path)
    return db_path


@pytest_asyncio.fixture()
async def init_test_db(tmp_db):
    """Initialise the temporary database schema."""
    await db.init_db()
    return tmp_db


@pytest_asyncio.fixture()
async def client(init_test_db):
    """Async HTTP test client against the FastAPI app (no background tasks)."""
    import httpx
    from backend.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture()
async def seed_video(init_test_db):
    """Insert a completed video with claims and sources into the temp DB."""
    video_id = "dQw4w9WgXcQ"
    await db.create_video(video_id, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    await db.update_video_results(
        video_id,
        title="Test Video",
        channel="TestChannel",
        duration_seconds=120.0,
        transcript_text="This is a test transcript.",
        overall_truth_percentage=75,
        summary="Test summary with 2 claims.",
        processing_time_seconds=5.0,
    )
    claims = [
        {
            "text": "The Earth orbits the Sun.",
            "timestamp_seconds": 10,
            "truth_percentage": 95,
            "confidence": 0.9,
            "reasoning": "Well-established scientific fact.",
            "category": "fact",
            "sources": [
                {"title": "NASA", "url": "https://nasa.gov", "snippet": "Earth orbits Sun."},
            ],
        },
        {
            "text": "Water boils at 100C at sea level.",
            "timestamp_seconds": 30,
            "truth_percentage": 90,
            "confidence": 0.85,
            "reasoning": "Standard chemistry.",
            "category": "fact",
            "sources": [],
        },
    ]
    await db.create_claims(video_id, claims)
    return video_id
