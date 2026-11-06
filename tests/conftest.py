"""Shared fixtures for the YouTube Fact Checker test suite."""

import os
import tempfile
import asyncio
import socket
from unittest.mock import patch

import pytest
import pytest_asyncio

# Set dummy env vars before any backend imports so config.Settings reads them
os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["BRAVE_API_KEY"] = "test-key"
os.environ["DATABASE_URL"] = ""

# Do not load developer secrets just to run synthetic tests. Config is imported
# inside this patch before services/application modules are collected.
with patch("dotenv.load_dotenv", return_value=False):
    from backend import database as db  # noqa: E402


@pytest.fixture(autouse=True)
def offline_providers(monkeypatch, request):
    """Fail immediately if a backend test accidentally reaches a real provider."""
    if request.node.get_closest_marker("e2e"):
        return

    def blocked(*args, **kwargs):
        raise AssertionError("External networking is disabled in backend tests")

    # Postgres is the one opt-in network fixture; still block Python HTTP/SDK
    # sockets. psycopg's libpq connection does not use Python socket.connect.
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


@pytest.fixture()
def tmp_db(monkeypatch, tmp_path):
    """Use SQLite by default; run the same contracts on an isolated PG schema."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "_DB_PATH", db_path)
    url = os.getenv("TEST_DATABASE_URL", "")
    if not url:
        monkeypatch.setattr(db, "_DATABASE_URL", "")
        yield db_path
        return
    import uuid
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    schema = "test_" + uuid.uuid4().hex
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        monkeypatch.setattr(db, "_DATABASE_URL", make_conninfo(
            url, options="-csearch_path=" + schema,
        ))
        try:
            yield db_path
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


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
