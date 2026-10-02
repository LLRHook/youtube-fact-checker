"""SQLite database layer for persistent video/claim storage."""

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from backend.config import settings
from backend.models import legacy_verdict

logger = logging.getLogger(__name__)

_DB_PATH = settings.DATABASE_PATH


@asynccontextmanager
async def _db():
    """Async context manager for DB connections with WAL and FK enabled."""
    try:
        db = await aiosqlite.connect(_DB_PATH, timeout=10.0)
    except Exception:
        logger.exception("Failed to connect to database at %s", _DB_PATH)
        raise
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
    finally:
        await db.close()


async def _add_column_if_missing(db, table, column, decl):
    async with db.execute(f"PRAGMA table_info({table})") as cursor:
        names = {row[1] for row in await cursor.fetchall()}
    if column not in names:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


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
            CREATE INDEX IF NOT EXISTS idx_claims_video_index ON claims(video_id, claim_index);
            CREATE INDEX IF NOT EXISTS idx_claim_sources_claim_id ON claim_sources(claim_id);
        """)

        await _add_column_if_missing(db, "videos", "ip_address", "TEXT DEFAULT ''")
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_videos_ip_status_created ON videos(ip_address, status, created_at)"
        )
        async with db.execute("PRAGMA user_version") as cursor:
            version = (await cursor.fetchone())[0]
        if version < 2:
            columns = {
                "videos": {
                    "channel_id": "TEXT DEFAULT ''",
                    "published_at": "TEXT DEFAULT ''",
                    "key_issues": "TEXT DEFAULT '[]'",
                    "pipeline_version": "INTEGER DEFAULT 1",
                    "model": "TEXT DEFAULT ''",
                    "cost_usd": "REAL DEFAULT 0",
                    "input_tokens": "INTEGER DEFAULT 0",
                    "output_tokens": "INTEGER DEFAULT 0",
                    "search_requests": "INTEGER DEFAULT 0",
                },
                "claims": {
                    "verdict": "TEXT",
                    "quote": "TEXT DEFAULT ''",
                    "speaker": "TEXT DEFAULT ''",
                    "topic": "TEXT DEFAULT ''",
                    "checkworthiness": "INTEGER DEFAULT 0",
                    "confidence_label": "TEXT DEFAULT ''",
                    "corrected_claim": "TEXT DEFAULT ''",
                    "relies_on_general_knowledge": "INTEGER DEFAULT 0",
                },
                "claim_sources": {
                    "domain": "TEXT DEFAULT ''",
                    "reliability": "TEXT DEFAULT ''",
                    "stance": "TEXT DEFAULT ''",
                    "quote": "TEXT DEFAULT ''",
                    "kind": "TEXT DEFAULT 'web'",
                    "rating": "TEXT DEFAULT ''",
                    "position": "INTEGER DEFAULT 0",
                },
            }
            for table, additions in columns.items():
                for column, decl in additions.items():
                    await _add_column_if_missing(db, table, column, decl)
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS search_cache (
                    cache_key TEXT PRIMARY KEY, provider TEXT NOT NULL, query TEXT NOT NULL,
                    results_json TEXT NOT NULL, created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS claim_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, video_id TEXT NOT NULL, claim_index INTEGER NOT NULL,
                    helpful INTEGER NOT NULL, ip_address TEXT DEFAULT '', created_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(video_id, claim_index, ip_address)
                );
                CREATE INDEX IF NOT EXISTS idx_videos_updated_at ON videos(updated_at);
                PRAGMA user_version = 2;
            """)
        await db.commit()


# --- Videos ---


async def get_video(video_id: str) -> dict | None:
    """Return a video row as dict, or None."""
    async with _db() as db:
        async with db.execute("SELECT * FROM videos WHERE id = ?", (video_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def create_video(video_id: str, youtube_url: str, *, ip_address: str = "", status: str = "processing") -> dict:
    """Insert a new video row."""
    async with _db() as db:
        try:
            await db.execute(
                "INSERT INTO videos (id, youtube_url, ip_address, status) VALUES (?, ?, ?, ?)",
                (video_id, youtube_url, ip_address, status),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        return {"id": video_id, "youtube_url": youtube_url, "status": status}


async def update_video_status(video_id: str, status: str, error: str | None = None):
    """Set video status (processing/completed/failed) and optional error."""
    async with _db() as db:
        try:
            await db.execute(
                "UPDATE videos SET status = ?, error = ?, updated_at = datetime('now') WHERE id = ?",
                (status, error, video_id),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise


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
    key_issues: list[str] | None = None,
    channel_id="",
    published_at="",
    pipeline_version=1,
    model="",
    cost_usd=0.0,
    input_tokens=0,
    output_tokens=0,
    search_requests=0,
):
    async with _db() as db:
        await db.execute(
            """UPDATE videos SET title=?, channel=?, duration_seconds=?, transcript_text=?, overall_truth_percentage=?,
            summary=?, processing_time_seconds=?, key_issues=?, channel_id=?, published_at=?, pipeline_version=?,
            model=?, cost_usd=?, input_tokens=?, output_tokens=?, search_requests=?,
            status='completed', error=NULL, updated_at=datetime('now') WHERE id=?""",
            (
                title,
                channel,
                duration_seconds,
                transcript_text,
                overall_truth_percentage,
                summary,
                processing_time_seconds,
                json.dumps(key_issues or []),
                channel_id,
                published_at,
                pipeline_version,
                model,
                cost_usd,
                input_tokens,
                output_tokens,
                search_requests,
                video_id,
            ),
        )
        await db.commit()


_LIST_COLUMNS = "id, title, channel, youtube_url, duration_seconds, overall_truth_percentage, summary, status, created_at, published_at, pipeline_version"


async def list_videos(
    status: str | None = None, *, limit: int = 0, offset: int = 0, sort: str = "newest", q: str = ""
) -> list[dict]:
    """List videos with optional status filter, newest first. Supports pagination.

    Excludes large columns (transcript_text) for efficiency.
    """
    query = f"SELECT {_LIST_COLUMNS} FROM videos WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if q:
        query += " AND (title LIKE ? OR channel LIKE ?)"
        params.extend([f"%{q[:100]}%", f"%{q[:100]}%"])
    order = {"highest": "overall_truth_percentage DESC", "lowest": "overall_truth_percentage ASC"}.get(sort)
    query += " ORDER BY " + (order + ", " if order else "") + "created_at DESC, id DESC"
    if limit > 0:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    async with _db() as db:
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def count_videos(status: str | None = None, *, q: str = "") -> int:
    """Count videos with optional status filter."""
    query = "SELECT COUNT(*) FROM videos WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)

    if q:
        query += " AND (title LIKE ? OR channel LIKE ?)"
        params.extend([f"%{q[:100]}%", f"%{q[:100]}%"])

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


async def get_stale_processing_videos(stale_minutes: int = 10, limit: int = 5) -> list[dict]:
    """Return videos stuck in 'processing' for longer than stale_minutes."""
    async with _db() as db:
        async with db.execute(
            "SELECT * FROM videos WHERE status = 'processing' AND updated_at <= datetime('now', ? || ' minutes') ORDER BY updated_at ASC LIMIT ?",
            (f"-{stale_minutes}", limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


# --- Claims ---


async def delete_claims_for_video(video_id: str):
    """Delete all claims and their sources for a video (used before re-inserting on retry)."""
    async with _db() as db:
        try:
            await db.execute(
                "DELETE FROM claim_sources WHERE claim_id IN (SELECT id FROM claims WHERE video_id = ?)",
                (video_id,),
            )
            await db.execute("DELETE FROM claims WHERE video_id = ?", (video_id,))
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def create_claims(video_id: str, claims_list: list[dict]):
    claim_defaults = {
        "text": "",
        "timestamp_seconds": 0,
        "truth_percentage": 50,
        "confidence": 0.5,
        "reasoning": "",
        "category": "fact",
        "verdict": None,
        "quote": "",
        "speaker": "",
        "topic": "",
        "checkworthiness": 0,
        "confidence_label": "",
        "corrected_claim": "",
        "relies_on_general_knowledge": 0,
    }
    source_defaults = {
        "title": "",
        "url": "",
        "snippet": "",
        "domain": "",
        "reliability": "",
        "stance": "",
        "quote": "",
        "kind": "web",
        "rating": "",
    }
    async with _db() as db:
        try:
            for i, claim in enumerate(claims_list, 1):
                columns = ["video_id", "claim_index", *claim_defaults]
                values = [video_id, i, *(claim.get(k, v) for k, v in claim_defaults.items())]
                cursor = await db.execute(
                    f"INSERT INTO claims ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                    values,
                )
                for position, source in enumerate(claim.get("sources", [])):
                    columns = ["claim_id", *source_defaults, "position"]
                    values = [cursor.lastrowid, *(source.get(k, v) for k, v in source_defaults.items()), position]
                    await db.execute(
                        f"INSERT INTO claim_sources ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                        values,
                    )
            await db.commit()
        except Exception:
            await db.rollback()
            raise


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
            f"SELECT * FROM claim_sources WHERE claim_id IN ({placeholders}) ORDER BY position, id",
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
            f"SELECT * FROM claim_sources WHERE claim_id IN ({src_placeholders}) ORDER BY position, id",
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
               WHERE status = 'completed' AND channel != '' AND channel != 'Unknown'
               GROUP BY channel
               ORDER BY video_count DESC, channel ASC
               LIMIT 500"""
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_channel_videos(channel: str) -> list[dict]:
    """List completed videos for a specific channel."""
    async with _db() as db:
        async with db.execute(
            f"""SELECT {_LIST_COLUMNS} FROM videos
               WHERE channel = ? AND status = 'completed'
               ORDER BY created_at DESC, id DESC""",
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
                    WHERE status = 'completed' AND channel != '' AND channel != 'Unknown')
        """) as c:
            row = await c.fetchone()
            return {
                "video_count": row[0],
                "claim_count": row[1],
                "channel_count": row[2],
            }


async def add_video_cost(video_id, cost_usd, input_tokens, output_tokens, search_requests):
    async with _db() as db:
        await db.execute(
            """UPDATE videos SET cost_usd=COALESCE(cost_usd,0)+?,
            input_tokens=COALESCE(input_tokens,0)+?, output_tokens=COALESCE(output_tokens,0)+?,
            search_requests=COALESCE(search_requests,0)+?, updated_at=datetime('now') WHERE id=?""",
            (cost_usd, input_tokens, output_tokens, search_requests, video_id),
        )
        await db.commit()


async def spend_today_usd() -> float:
    async with _db() as db:
        async with db.execute("SELECT COALESCE(SUM(cost_usd),0) FROM videos WHERE updated_at >= date('now')") as cursor:
            return float((await cursor.fetchone())[0])


async def get_search_cache(key, max_age_days) -> str | None:
    async with _db() as db:
        async with db.execute(
            "SELECT results_json FROM search_cache WHERE cache_key=? AND created_at >= datetime('now', ?)",
            (key, f"-{max_age_days} days"),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def put_search_cache(key, provider, query, results_json):
    async with _db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO search_cache (cache_key, provider, query, results_json) VALUES (?,?,?,?)",
            (key, provider, query, results_json),
        )
        await db.commit()


async def prune_search_cache(max_age_days):
    async with _db() as db:
        await db.execute("DELETE FROM search_cache WHERE created_at < datetime('now', ?)", (f"-{max_age_days} days",))
        await db.commit()


async def upsert_claim_feedback(video_id, claim_index, helpful: bool, ip):
    async with _db() as db:
        await db.execute(
            """INSERT INTO claim_feedback (video_id, claim_index, helpful, ip_address) VALUES (?,?,?,?)
            ON CONFLICT(video_id, claim_index, ip_address) DO UPDATE SET helpful=excluded.helpful, created_at=datetime('now')""",
            (video_id, claim_index, int(helpful), ip),
        )
        await db.commit()


async def get_feedback_counts(video_id) -> dict:
    async with _db() as db:
        async with db.execute(
            "SELECT claim_index, SUM(helpful), SUM(1-helpful) FROM claim_feedback WHERE video_id=? GROUP BY claim_index",
            (video_id,),
        ) as cursor:
            return {r[0]: {"helpful": r[1], "not_helpful": r[2]} for r in await cursor.fetchall()}


async def get_verdict_counts(video_ids) -> dict:
    if not video_ids:
        return {}
    result = {vid: {} for vid in video_ids}
    async with _db() as db:
        async with db.execute(
            f"""SELECT video_id, verdict, category, truth_percentage, COUNT(*) FROM claims
            WHERE video_id IN ({",".join("?" for _ in video_ids)}) GROUP BY video_id, verdict, category, truth_percentage""",
            video_ids,
        ) as cursor:
            for vid, verdict, category, score, count in await cursor.fetchall():
                verdict = verdict or legacy_verdict(category, score)
                result[vid][verdict] = result[vid].get(verdict, 0) + count
    return result
