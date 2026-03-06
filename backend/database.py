"""SQLite database layer for persistent video/claim storage."""

import aiosqlite
from pathlib import Path
from backend.config import settings

_DB_PATH = settings.DATABASE_PATH


async def _get_db() -> aiosqlite.Connection:
    """Open a connection with row_factory enabled."""
    db = await aiosqlite.connect(_DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    """Create tables if they don't exist. Call once on startup."""
    Path(_DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(_DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS videos (
                id TEXT PRIMARY KEY,
                youtube_url TEXT NOT NULL,
                title TEXT DEFAULT '',
                channel TEXT DEFAULT '',
                duration_seconds REAL DEFAULT 0,
                transcript_text TEXT DEFAULT '',
                overall_truth_percentage INTEGER DEFAULT 0,
                summary TEXT DEFAULT '',
                processing_time_seconds REAL DEFAULT 0,
                status TEXT DEFAULT 'processing',
                error TEXT,
                approval_status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT REFERENCES videos(id),
                claim_index INTEGER,
                text TEXT,
                timestamp_seconds REAL DEFAULT 0,
                truth_percentage INTEGER DEFAULT 50,
                confidence REAL DEFAULT 0.5,
                reasoning TEXT DEFAULT '',
                category TEXT DEFAULT 'fact',
                attributed_to_creator INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS claim_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id INTEGER REFERENCES claims(id),
                title TEXT DEFAULT '',
                url TEXT DEFAULT '',
                snippet TEXT DEFAULT ''
            );
        """)


# --- Videos ---


async def get_video(video_id: str) -> dict | None:
    """Return a video row as dict, or None."""
    db = await _get_db()
    try:
        async with db.execute(
            "SELECT * FROM videos WHERE id = ?", (video_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await db.close()


async def create_video(video_id: str, youtube_url: str) -> dict:
    """Insert a new video row in 'processing' state."""
    db = await _get_db()
    try:
        await db.execute(
            "INSERT INTO videos (id, youtube_url) VALUES (?, ?)",
            (video_id, youtube_url),
        )
        await db.commit()
        return {"id": video_id, "youtube_url": youtube_url, "status": "processing"}
    finally:
        await db.close()


async def update_video_status(video_id: str, status: str, error: str | None = None):
    """Set video status (processing/completed/failed) and optional error."""
    db = await _get_db()
    try:
        await db.execute(
            "UPDATE videos SET status = ?, error = ?, updated_at = datetime('now') WHERE id = ?",
            (status, error, video_id),
        )
        await db.commit()
    finally:
        await db.close()


async def update_video_results(
    video_id: str,
    *,
    title: str,
    channel: str,
    duration_seconds: float,
    transcript_text: str,
    overall_truth_percentage: int,
    summary: str,
    processing_time_seconds: float,
):
    """Write final results to a completed video row."""
    db = await _get_db()
    try:
        await db.execute(
            """UPDATE videos SET
                title = ?, channel = ?, duration_seconds = ?,
                transcript_text = ?, overall_truth_percentage = ?,
                summary = ?, processing_time_seconds = ?,
                status = 'completed', updated_at = datetime('now')
            WHERE id = ?""",
            (
                title, channel, duration_seconds,
                transcript_text, overall_truth_percentage,
                summary, processing_time_seconds,
                video_id,
            ),
        )
        await db.commit()
    finally:
        await db.close()


async def set_video_approval(video_id: str, approval_status: str):
    """Set approval_status to pending/approved/rejected."""
    db = await _get_db()
    try:
        await db.execute(
            "UPDATE videos SET approval_status = ?, updated_at = datetime('now') WHERE id = ?",
            (approval_status, video_id),
        )
        await db.commit()
    finally:
        await db.close()


async def list_videos(
    status: str | None = None,
    approval_status: str | None = None,
) -> list[dict]:
    """List videos with optional filters, newest first."""
    query = "SELECT * FROM videos WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if approval_status:
        query += " AND approval_status = ?"
        params.append(approval_status)
    query += " ORDER BY created_at DESC"

    db = await _get_db()
    try:
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    finally:
        await db.close()


# --- Claims ---


async def create_claims(video_id: str, claims_list: list[dict]):
    """Bulk-insert claims and their sources for a video."""
    db = await _get_db()
    try:
        for i, c in enumerate(claims_list):
            cursor = await db.execute(
                """INSERT INTO claims
                    (video_id, claim_index, text, timestamp_seconds,
                     truth_percentage, confidence, reasoning, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    video_id,
                    i + 1,
                    c.get("text", ""),
                    c.get("timestamp_seconds", 0),
                    c.get("truth_percentage", 50),
                    c.get("confidence", 0.5),
                    c.get("reasoning", ""),
                    c.get("category", "fact"),
                ),
            )
            claim_id = cursor.lastrowid

            for src in c.get("sources", []):
                await db.execute(
                    "INSERT INTO claim_sources (claim_id, title, url, snippet) VALUES (?, ?, ?, ?)",
                    (claim_id, src.get("title", ""), src.get("url", ""), src.get("snippet", "")),
                )

        await db.commit()
    finally:
        await db.close()


async def get_claims_for_video(video_id: str) -> list[dict]:
    """Return claims with nested sources for a video."""
    db = await _get_db()
    try:
        async with db.execute(
            "SELECT * FROM claims WHERE video_id = ? ORDER BY claim_index",
            (video_id,),
        ) as cursor:
            claim_rows = await cursor.fetchall()

        result = []
        for cr in claim_rows:
            claim = dict(cr)
            async with db.execute(
                "SELECT * FROM claim_sources WHERE claim_id = ?",
                (claim["id"],),
            ) as src_cursor:
                sources = [dict(s) for s in await src_cursor.fetchall()]
            claim["sources"] = sources
            result.append(claim)

        return result
    finally:
        await db.close()


async def update_claim_attribution(claim_id: int, attributed_to_creator: bool):
    """Toggle whether a claim is attributed to the content creator."""
    db = await _get_db()
    try:
        await db.execute(
            "UPDATE claims SET attributed_to_creator = ? WHERE id = ?",
            (1 if attributed_to_creator else 0, claim_id),
        )
        await db.commit()
    finally:
        await db.close()
