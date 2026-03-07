"""SQLite database layer for persistent video/claim storage."""

import aiosqlite
from contextlib import asynccontextmanager
from pathlib import Path
from backend.config import settings

_DB_PATH = settings.DATABASE_PATH


@asynccontextmanager
async def _db():
    """Async context manager for DB connections with WAL and FK enabled."""
    db = await aiosqlite.connect(_DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
    finally:
        await db.close()


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

            CREATE INDEX IF NOT EXISTS idx_videos_channel ON videos(channel);
            CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
            CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at);
            CREATE INDEX IF NOT EXISTS idx_videos_status_created ON videos(status, created_at);
            CREATE INDEX IF NOT EXISTS idx_videos_channel_status_created ON videos(channel, status, created_at);
            CREATE INDEX IF NOT EXISTS idx_claims_video_id ON claims(video_id);
            CREATE INDEX IF NOT EXISTS idx_claim_sources_claim_id ON claim_sources(claim_id);
        """)

        # Migration: add ip_address column
        try:
            await db.execute("ALTER TABLE videos ADD COLUMN ip_address TEXT DEFAULT ''")
        except Exception:
            pass  # column already exists


# --- Videos ---


async def get_video(video_id: str) -> dict | None:
    """Return a video row as dict, or None."""
    async with _db() as db:
        async with db.execute(
            "SELECT * FROM videos WHERE id = ?", (video_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def create_video(video_id: str, youtube_url: str, *, ip_address: str = "", status: str = "processing") -> dict:
    """Insert a new video row."""
    async with _db() as db:
        await db.execute(
            "INSERT INTO videos (id, youtube_url, ip_address, status) VALUES (?, ?, ?, ?)",
            (video_id, youtube_url, ip_address, status),
        )
        await db.commit()
        return {"id": video_id, "youtube_url": youtube_url, "status": status}


async def update_video_status(video_id: str, status: str, error: str | None = None):
    """Set video status (processing/completed/failed) and optional error."""
    async with _db() as db:
        await db.execute(
            "UPDATE videos SET status = ?, error = ?, updated_at = datetime('now') WHERE id = ?",
            (status, error, video_id),
        )
        await db.commit()


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
    async with _db() as db:
        await db.execute(
            """UPDATE videos SET
                title = ?, channel = ?, duration_seconds = ?,
                transcript_text = ?, overall_truth_percentage = ?,
                summary = ?, processing_time_seconds = ?,
                status = 'completed', error = NULL, updated_at = datetime('now')
            WHERE id = ?""",
            (
                title, channel, duration_seconds,
                transcript_text, overall_truth_percentage,
                summary, processing_time_seconds,
                video_id,
            ),
        )
        await db.commit()


_LIST_COLUMNS = "id, title, channel, youtube_url, duration_seconds, overall_truth_percentage, summary, status, created_at"


async def list_videos(status: str | None = None, *, limit: int = 0, offset: int = 0) -> list[dict]:
    """List videos with optional status filter, newest first. Supports pagination.

    Excludes large columns (transcript_text) for efficiency.
    """
    query = f"SELECT {_LIST_COLUMNS} FROM videos WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"
    if limit > 0:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    async with _db() as db:
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def count_videos(status: str | None = None) -> int:
    """Count videos with optional status filter."""
    query = "SELECT COUNT(*) FROM videos WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)

    async with _db() as db:
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def count_videos_today() -> int:
    """Count processing or completed videos created today (excludes queued and failed)."""
    async with _db() as db:
        async with db.execute(
            "SELECT COUNT(*) FROM videos WHERE status IN ('processing', 'completed') AND created_at >= date('now')"
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def count_videos_today_by_ip(ip: str) -> int:
    """Count non-failed videos submitted by a specific IP today."""
    async with _db() as db:
        async with db.execute(
            "SELECT COUNT(*) FROM videos WHERE ip_address = ? AND status != 'failed' AND created_at >= date('now')",
            (ip,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_queued_videos(limit: int = 5) -> list[dict]:
    """Return oldest queued videos."""
    async with _db() as db:
        async with db.execute(
            "SELECT * FROM videos WHERE status = 'queued' ORDER BY created_at ASC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


# --- Claims ---


async def delete_claims_for_video(video_id: str):
    """Delete all claims and their sources for a video (used before re-inserting on retry)."""
    async with _db() as db:
        await db.execute(
            "DELETE FROM claim_sources WHERE claim_id IN (SELECT id FROM claims WHERE video_id = ?)",
            (video_id,),
        )
        await db.execute("DELETE FROM claims WHERE video_id = ?", (video_id,))
        await db.commit()


async def create_claims(video_id: str, claims_list: list[dict]):
    """Bulk-insert claims and their sources for a video."""
    async with _db() as db:
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


async def get_claims_for_video(video_id: str) -> list[dict]:
    """Return claims with nested sources for a video."""
    async with _db() as db:
        async with db.execute(
            "SELECT * FROM claims WHERE video_id = ? ORDER BY claim_index",
            (video_id,),
        ) as cursor:
            claim_rows = await cursor.fetchall()

        if not claim_rows:
            return []

        claims_by_id = {}
        result = []
        for cr in claim_rows:
            claim = dict(cr)
            claim["sources"] = []
            claims_by_id[claim["id"]] = claim
            result.append(claim)

        claim_ids = list(claims_by_id.keys())
        placeholders = ",".join("?" for _ in claim_ids)
        async with db.execute(
            f"SELECT * FROM claim_sources WHERE claim_id IN ({placeholders})",
            claim_ids,
        ) as src_cursor:
            for src_row in await src_cursor.fetchall():
                src = dict(src_row)
                cid = src["claim_id"]
                if cid in claims_by_id:
                    claims_by_id[cid]["sources"].append(src)

        return result


async def get_claims_for_videos(video_ids: list[str]) -> dict[str, list[dict]]:
    """Return claims with nested sources for multiple videos in batch.

    Returns a dict mapping video_id -> list of claim dicts.
    """
    if not video_ids:
        return {}

    async with _db() as db:
        placeholders = ",".join("?" for _ in video_ids)

        # Fetch all claims for the given videos
        async with db.execute(
            f"SELECT * FROM claims WHERE video_id IN ({placeholders}) ORDER BY video_id, claim_index",
            video_ids,
        ) as cursor:
            claim_rows = await cursor.fetchall()

        if not claim_rows:
            return {vid: [] for vid in video_ids}

        # Collect claim IDs for source lookup
        claims_by_id = {}
        result: dict[str, list[dict]] = {vid: [] for vid in video_ids}
        for cr in claim_rows:
            claim = dict(cr)
            claim["sources"] = []
            claims_by_id[claim["id"]] = claim
            result[claim["video_id"]].append(claim)

        # Fetch all sources for these claims in one query
        claim_ids = list(claims_by_id.keys())
        src_placeholders = ",".join("?" for _ in claim_ids)
        async with db.execute(
            f"SELECT * FROM claim_sources WHERE claim_id IN ({src_placeholders})",
            claim_ids,
        ) as src_cursor:
            for src_row in await src_cursor.fetchall():
                src = dict(src_row)
                cid = src["claim_id"]
                if cid in claims_by_id:
                    claims_by_id[cid]["sources"].append(src)

        return result


# --- Public queries ---


async def list_channels() -> list[dict]:
    """List channels with aggregate stats from completed videos."""
    async with _db() as db:
        async with db.execute(
            """SELECT channel, COUNT(*) as video_count,
                      AVG(overall_truth_percentage) as avg_score
               FROM videos
               WHERE status = 'completed' AND channel != ''
               GROUP BY channel
               ORDER BY video_count DESC"""
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_channel_videos(channel: str) -> list[dict]:
    """List completed videos for a specific channel."""
    async with _db() as db:
        async with db.execute(
            f"""SELECT {_LIST_COLUMNS} FROM videos
               WHERE channel = ? AND status = 'completed'
               ORDER BY created_at DESC""",
            (channel,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_stats() -> dict:
    """Get aggregate site statistics."""
    async with _db() as db:
        async with db.execute("""
            SELECT
                (SELECT COUNT(*) FROM videos WHERE status = 'completed'),
                (SELECT COUNT(*) FROM claims WHERE video_id IN
                    (SELECT id FROM videos WHERE status = 'completed')),
                (SELECT COUNT(DISTINCT channel) FROM videos
                    WHERE status = 'completed' AND channel != '')
        """) as c:
            row = await c.fetchone()
            return {
                "video_count": row[0],
                "claim_count": row[1],
                "channel_count": row[2],
            }
