"""YouTube Fact Checker — FastAPI application."""

import asyncio
import json as json_module
import logging
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote as url_quote

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend import database as db
from backend.config import PIPELINE_VERSION, settings, validate_settings
from backend.models import (
    ChannelDetail,
    ChannelSummary,
    CheckRequest,
    CheckResult,
    Claim,
    ClaimCategory,
    PublicVideoDetail,
    PublicVideoSummary,
    TaskResponse,
    TaskStatus,
    claim_row_to_public,
)
from backend.seo import (
    _channel_fallback_meta,
    _channel_jsonld,
    _html_escape,
    _inject_meta,
    _video_fallback_meta,
    _video_jsonld,
    build_robots,
    build_sitemap,
)
from backend.services import llm, pipeline, search_service
from backend.services.fact_checker import overall_score
from backend.services.pipeline import TaskState, capacity_available, tasks
from backend.utils.validators import extract_video_id, is_valid_youtube_url

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Serve frontend static files
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# Template caching — read once at import time
_VIDEO_TEMPLATE = (FRONTEND_DIR / "video.html").read_text(encoding="utf-8")
_CHANNEL_TEMPLATE = (FRONTEND_DIR / "channel.html").read_text(encoding="utf-8")
_INDEX_TEMPLATE = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
_VIDEOS_TEMPLATE = (FRONTEND_DIR / "videos.html").read_text(encoding="utf-8")

# Queue processor task handle
_queue_task: asyncio.Task | None = None
_admission_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _queue_task
    validate_settings()
    await db.init_db()
    _queue_task = asyncio.create_task(pipeline.queue_processor())
    yield
    _queue_task.cancel()
    try:
        await _queue_task
    except asyncio.CancelledError:
        pass
    await llm.close_client()
    await search_service.close_http_client()


app = FastAPI(title="YouTube Fact Checker", version="2.0.0", lifespan=lifespan)

if settings.CORS_ORIGINS.strip():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[s.strip() for s in settings.CORS_ORIGINS.split(",") if s.strip()],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )


_STATIC_EXTENSIONS = (".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".woff", ".woff2")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' https://img.youtube.com https://i.ytimg.com data:; "
            "frame-src https://www.youtube-nocookie.com https://www.youtube.com; "
            "connect-src 'self'; "
            "font-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        if settings.BASE_URL.startswith("https://"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        path = request.url.path
        if path.endswith(_STATIC_EXTENSIONS):
            response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=86400"
        elif response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Cache-Control"] = "no-cache"
        elif path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Robots-Tag"] = "noindex"
        return response


app.add_middleware(SecurityHeadersMiddleware)


def _safe_category(value: str) -> ClaimCategory:
    """Convert a string to ClaimCategory with fallback to FACT."""
    try:
        return ClaimCategory(value)
    except ValueError:
        logger.warning("Unknown claim category %r, defaulting to 'fact'", value)
        return ClaimCategory.FACT


def _build_claims_from_rows(claims_rows: list[dict]) -> list[Claim]:
    return [Claim(id=f"claim-{row['claim_index']}", **claim_row_to_public(row).model_dump()) for row in claims_rows]


def _build_completed_result(video: dict, claims: list[Claim]) -> CheckResult:
    """Build a CheckResult from a completed video row and its claims."""
    return CheckResult(
        video_title=video["title"],
        video_id=video["id"],
        video_duration_seconds=video["duration_seconds"],
        transcript_text=video.get("transcript_text", "")[:2000],
        claims=claims,
        overall_truth_percentage=video["overall_truth_percentage"],
        summary=video["summary"],
        processing_time_seconds=video["processing_time_seconds"],
    )


def _build_video_summary(video: dict, claims: list[dict], verdict_counts=None) -> PublicVideoSummary:
    return PublicVideoSummary(
        id=video["id"],
        title=video["title"],
        channel=video["channel"],
        public_score=_calculate_public_score(claims)
        if video.get("pipeline_version", 1) == 1
        else (overall_score(claims) or 50),
        claim_count=len(claims),
        created_at=video["created_at"] or "",
        verdict_counts=verdict_counts or {},
        published_at=video.get("published_at", ""),
        thumbnail_url=f"https://i.ytimg.com/vi/{video['id']}/hqdefault.jpg",
    )


def _get_client_ip(request: Request) -> str:
    parts = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    hops = settings.TRUSTED_PROXY_HOPS
    ip = (
        (request.client.host if request.client else "")
        if hops == 0 or not parts
        else parts[-hops]
        if len(parts) >= hops
        else parts[0]
    )
    return ip[:45]


def _task_response(state):
    return TaskResponse(
        task_id=state.task_id,
        status=state.status,
        progress=state.message,
        stage=state.stage,
        completed=state.completed,
        total=state.total,
        video=state.video,
        claims=state.claims,
        error=state.error,
    )


def _is_valid_channel_name(name: str) -> bool:
    """Return True if the channel name passes basic sanity checks."""
    return bool(name and len(name) <= 200 and not any(c in name for c in "\x00/\\\n\r") and ".." not in name)


# --- API Routes ---


@app.post("/api/check")
async def check_video(req: CheckRequest, background_tasks: BackgroundTasks, request: Request):
    """Submit a YouTube video for fact-checking."""
    if not is_valid_youtube_url(req.youtube_url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL.")

    video_id = extract_video_id(req.youtube_url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Could not extract video ID from URL.")
    client_ip = _get_client_ip(request)

    async with _admission_lock:
        # Dedup: if video already completed in DB, return it
        existing = await db.get_video(video_id)
        if existing and existing["status"] == "completed":
            claims = _build_claims_from_rows(await db.get_claims_for_video(video_id))
            result = _build_completed_result(existing, claims)
            return TaskResponse(
                task_id=video_id,
                status=TaskStatus.COMPLETED,
                progress="Done!",
                data=result,
                stage="completed",
                claims=[claim_row_to_public(row) for row in await db.get_claims_for_video(video_id)],
            ).model_dump()

        # If already queued, return queued status
        if existing and existing["status"] == "queued":
            return TaskResponse(
                task_id=video_id,
                status=TaskStatus.QUEUED,
                progress="Queued — will be processed soon.",
                stage="queued",
            ).model_dump()

        # Check if already processing in-memory
        existing_task = tasks.get(video_id)
        if existing_task and existing_task.status == TaskStatus.PROCESSING:
            return TaskResponse(
                task_id=video_id,
                status=TaskStatus.PROCESSING,
                progress=existing_task.message,
                stage=existing_task.stage,
                completed=existing_task.completed,
                total=existing_task.total,
                video=existing_task.video,
                claims=existing_task.claims,
            ).model_dump()

        # Per-IP rate limit (skip for unresolvable IPs to avoid false positives)
        ip_count = await db.count_videos_today_by_ip(client_ip) if client_ip else 0
        if ip_count >= settings.IP_DAILY_LIMIT:
            raise HTTPException(
                status_code=429,
                detail=f"You've reached the limit of {settings.IP_DAILY_LIMIT} videos per day. Please try again tomorrow.",
            )

        # Site-wide daily limit — queue if exceeded
        if not await capacity_available():
            if not existing:
                await db.create_video(video_id, req.youtube_url, ip_address=client_ip, status="queued")
            else:
                await db.update_video_status(video_id, "queued")
            return TaskResponse(
                task_id=video_id,
                status=TaskStatus.QUEUED,
                progress="Queued — will be processed soon.",
                stage="queued",
            ).model_dump()

        # Under limits — process immediately
        task_id = video_id

        # Re-check after awaits: another coroutine may have reserved this task
        # while we were awaiting rate-limit DB queries above.
        existing_task = tasks.get(task_id)
        if existing_task and existing_task.status == TaskStatus.PROCESSING:
            return TaskResponse(
                task_id=task_id,
                status=TaskStatus.PROCESSING,
                progress=existing_task.message,
                stage=existing_task.stage,
                completed=existing_task.completed,
                total=existing_task.total,
                video=existing_task.video,
                claims=existing_task.claims,
            ).model_dump()

        tasks[task_id] = TaskState(
            task_id=task_id,
            status=TaskStatus.PROCESSING,
            message="Starting...",
        )

        try:
            if not existing:
                await db.create_video(video_id, req.youtube_url, ip_address=client_ip)
            elif existing["status"] in ("failed", "processing"):
                await db.update_video_status(video_id, "processing")
        except Exception:
            tasks.pop(task_id, None)
            raise

        background_tasks.add_task(pipeline.process_video, task_id, video_id, req.youtube_url)

        return TaskResponse(
            task_id=task_id,
            status=TaskStatus.PROCESSING,
            progress="Starting...",
        ).model_dump()


@app.get("/api/check/{task_id}")
async def get_task_status(task_id: str):
    """Poll the status of a fact-check task."""
    # Check in-memory first (in-flight tasks)
    if task_id in tasks:
        task = tasks[task_id]
        return _task_response(task).model_dump()

    # Fall back to DB
    video = await db.get_video(task_id)
    if not video:
        raise HTTPException(status_code=404, detail="Task not found.")

    if video["status"] == "completed":
        claims = _build_claims_from_rows(await db.get_claims_for_video(task_id))
        result = _build_completed_result(video, claims)
        return TaskResponse(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            progress="Done!",
            data=result,
            stage="completed",
            claims=[claim_row_to_public(row) for row in await db.get_claims_for_video(task_id)],
        ).model_dump()

    if video["status"] == "failed":
        return TaskResponse(
            task_id=task_id,
            status=TaskStatus.FAILED,
            error=video.get("error"),
            stage="failed",
        ).model_dump()

    if video["status"] == "queued":
        return TaskResponse(
            task_id=task_id,
            status=TaskStatus.QUEUED,
            progress="Queued — will be processed soon.",
            stage="queued",
        ).model_dump()

    # Still processing but not in memory
    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PROCESSING,
        progress="Processing...",
    ).model_dump()


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "pipeline_version": PIPELINE_VERSION}


_stats_cache: dict | None = None
_stats_cache_time: float = 0
_STATS_TTL = 60  # seconds


@app.get("/api/stats")
async def public_stats():
    """Aggregate site statistics (cached for 60s)."""
    global _stats_cache, _stats_cache_time
    now = time.time()
    if _stats_cache is not None and now - _stats_cache_time < _STATS_TTL:
        return _stats_cache
    _stats_cache = await db.get_stats()
    _stats_cache_time = now
    return _stats_cache


# --- Public API ---


def _calculate_public_score(claims: list[dict]) -> int:
    """Calculate score from fact claims."""
    total_weight = 0
    weighted_sum = 0
    for c in claims:
        if c.get("category") != "fact":
            continue
        conf = c.get("confidence", 0.5)
        total_weight += conf
        weighted_sum += c.get("truth_percentage", 50) * conf
    if total_weight > 0:
        return max(0, min(100, round(weighted_sum / total_weight)))
    return 50  # No factual claims to score — return neutral


@app.get("/api/videos")
async def public_list_videos(page: int = 1, limit: int = 50, sort: str = "newest", q: str = ""):
    """List completed videos with pagination."""
    sort = sort if sort in {"newest", "highest", "lowest"} else "newest"
    q = q[:100]
    limit = max(1, min(limit, 100))
    page = max(1, page)

    total = await db.count_videos(status="completed", q=q)
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    if page > total_pages:
        page = total_pages
    offset = (page - 1) * limit

    videos = await db.list_videos(status="completed", limit=limit, offset=offset, sort=sort, q=q)
    video_ids = [v["id"] for v in videos]
    all_claims = await db.get_claims_for_videos(video_ids)
    counts = await db.get_verdict_counts(video_ids)
    items = [_build_video_summary(v, all_claims.get(v["id"], []), counts.get(v["id"])).model_dump() for v in videos]
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": total_pages,
    }


_VIDEO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{11}$")


@app.get("/api/videos/{video_id}")
async def public_get_video(video_id: str):
    """Public video detail."""
    if not _VIDEO_ID_PATTERN.match(video_id):
        raise HTTPException(status_code=404, detail="Video not found.")
    video = await db.get_video(video_id)
    if not video or video["status"] != "completed":
        raise HTTPException(status_code=404, detail="Video not found.")

    claims = await db.get_claims_for_video(video_id)
    public_score = _calculate_public_score(claims) if video.get("pipeline_version", 1) == 1 else overall_score(claims)
    feedback = await db.get_feedback_counts(video_id)
    public_claims = [claim_row_to_public(c, feedback.get(c["claim_index"])) for c in claims]
    counts = await db.get_verdict_counts([video_id])
    try:
        key_issues = json_module.loads(video.get("key_issues") or "[]")
        if not isinstance(key_issues, list):
            key_issues = []
    except (ValueError, TypeError):
        key_issues = []

    return PublicVideoDetail(
        id=video["id"],
        title=video["title"],
        channel=video["channel"],
        youtube_url=video["youtube_url"],
        duration_seconds=video["duration_seconds"],
        overall_truth_percentage=video["overall_truth_percentage"],
        public_score=public_score,
        summary=video["summary"],
        processing_time_seconds=video.get("processing_time_seconds", 0),
        created_at=video["created_at"] or "",
        claims=public_claims,
        channel_id=video.get("channel_id", ""),
        published_at=video.get("published_at", ""),
        key_issues=key_issues,
        verdict_counts=counts.get(video_id, {}),
        pipeline_version=video.get("pipeline_version", 1),
        model=video.get("model", ""),
        thumbnail_url=f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    ).model_dump()


@app.get("/api/channels")
async def public_list_channels():
    """List channels with aggregate stats."""
    channels = await db.list_channels()
    return [
        ChannelSummary(
            channel=ch["channel"],
            video_count=ch["video_count"],
            avg_score=round(ch["avg_score"] or 0, 1),
        ).model_dump()
        for ch in channels
    ]


@app.get("/api/channels/{channel_name}")
async def public_get_channel(channel_name: str):
    """Channel detail with its videos."""
    if not _is_valid_channel_name(channel_name):
        raise HTTPException(status_code=400, detail="Invalid channel name.")
    videos = await db.get_channel_videos(channel_name)
    if not videos:
        raise HTTPException(status_code=404, detail="Channel not found.")

    video_ids = [v["id"] for v in videos]
    all_claims = await db.get_claims_for_videos(video_ids)

    counts = await db.get_verdict_counts(video_ids)
    video_summaries = [_build_video_summary(v, all_claims.get(v["id"], []), counts.get(v["id"])) for v in videos]

    all_scores = [vs.public_score for vs in video_summaries]
    avg_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0

    return ChannelDetail(
        channel=channel_name,
        video_count=len(video_summaries),
        avg_score=avg_score,
        videos=video_summaries,
    ).model_dump()


# --- Frontend (server-side meta injection) ---


@app.get("/robots.txt")
async def robots_txt():
    return Response(content=build_robots(), media_type="text/plain")


_sitemap_cache: str | None = None
_sitemap_cache_time: float = 0
_SITEMAP_TTL = 300  # seconds


@app.get("/sitemap.xml")
async def sitemap():
    global _sitemap_cache, _sitemap_cache_time
    now = time.time()
    if _sitemap_cache is not None and now - _sitemap_cache_time < _SITEMAP_TTL:
        return Response(content=_sitemap_cache, media_type="application/xml")

    videos, channels = await asyncio.gather(db.list_videos(status="completed", limit=1000), db.list_channels())
    xml = build_sitemap(videos, channels)
    _sitemap_cache = xml
    _sitemap_cache_time = now
    return Response(content=xml, media_type="application/xml")


@app.get("/")
async def serve_index():
    base = settings.BASE_URL
    html = _INDEX_TEMPLATE.replace("__CANONICAL_URL__", base)
    return HTMLResponse(html)


@app.get("/videos")
async def serve_videos_page():
    base = settings.BASE_URL
    html = _VIDEOS_TEMPLATE.replace("__CANONICAL_URL__", f"{base}/videos")
    return HTMLResponse(html)


@app.get("/video/{video_id}")
async def serve_video_page(video_id: str):
    if not _VIDEO_ID_PATTERN.match(video_id):
        return HTMLResponse(_inject_meta(_VIDEO_TEMPLATE, _video_fallback_meta(video_id)))

    video = await db.get_video(video_id)
    if not video or video["status"] != "completed":
        return HTMLResponse(_inject_meta(_VIDEO_TEMPLATE, _video_fallback_meta(video_id)))

    base = settings.BASE_URL
    canonical = f"{base}/video/{url_quote(video_id)}"
    thumbnail = f"https://img.youtube.com/vi/{url_quote(video_id)}/hqdefault.jpg"
    title = _html_escape(video.get("title") or "Video")
    score = video.get("overall_truth_percentage", 50)
    summary = _html_escape(video.get("summary") or "")

    meta_title = f"{title} — {score}% Accuracy — YouTube Fact Checker"
    meta_desc = summary or "AI-powered fact-check with accuracy scores and sourced evidence for every claim."
    og_desc = f"Accuracy: {score}%. {summary}" if summary else meta_desc

    jsonld = _video_jsonld(video, canonical, thumbnail, score)

    replacements = {
        "__META_TITLE__": meta_title,
        "__META_DESCRIPTION__": meta_desc,
        "__OG_TITLE__": meta_title,
        "__OG_DESCRIPTION__": og_desc,
        "__OG_IMAGE__": thumbnail,
        "__OG_URL__": canonical,
        "__CANONICAL_URL__": canonical,
        "__JSON_LD__": jsonld,
    }
    return HTMLResponse(_inject_meta(_VIDEO_TEMPLATE, replacements))


@app.get("/channel/{channel_name}")
async def serve_channel_page(channel_name: str):
    if not _is_valid_channel_name(channel_name):
        return HTMLResponse(_inject_meta(_CHANNEL_TEMPLATE, _channel_fallback_meta(channel_name or "Unknown")))

    videos = await db.get_channel_videos(channel_name)
    if not videos:
        return HTMLResponse(_inject_meta(_CHANNEL_TEMPLATE, _channel_fallback_meta(channel_name)))

    base = settings.BASE_URL
    canonical = f"{base}/channel/{url_quote(channel_name)}"
    safe_name = _html_escape(channel_name)
    count = len(videos)

    scores = [v.get("overall_truth_percentage", 50) for v in videos]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    # Use first video's thumbnail as the channel OG image
    first_vid = videos[0]["id"] if videos else ""
    thumbnail = f"https://img.youtube.com/vi/{url_quote(first_vid)}/hqdefault.jpg" if first_vid else ""

    meta_title = f"{safe_name} — {avg_score:.0f}% Avg Accuracy — YouTube Fact Checker"
    meta_desc = f"{count} fact-checked video{'s' if count != 1 else ''} with {avg_score:.0f}% average accuracy score."
    jsonld = _channel_jsonld(channel_name, count, avg_score, canonical)

    replacements = {
        "__META_TITLE__": meta_title,
        "__META_DESCRIPTION__": meta_desc,
        "__OG_TITLE__": meta_title,
        "__OG_DESCRIPTION__": meta_desc,
        "__OG_IMAGE__": thumbnail,
        "__OG_URL__": canonical,
        "__CANONICAL_URL__": canonical,
        "__JSON_LD__": jsonld,
    }
    return HTMLResponse(_inject_meta(_CHANNEL_TEMPLATE, replacements))


class FeedbackRequest(BaseModel):
    helpful: bool


@app.post("/api/videos/{video_id}/claims/{claim_index}/feedback", status_code=204)
async def claim_feedback(video_id: str, claim_index: int, body: FeedbackRequest, request: Request):
    video = await db.get_video(video_id)
    if not video or video["status"] != "completed":
        raise HTTPException(status_code=404, detail="Video not found.")
    claims = await db.get_claims_for_video(video_id)
    if not any(c["claim_index"] == claim_index for c in claims):
        raise HTTPException(status_code=404, detail="Claim not found.")
    await db.upsert_claim_feedback(video_id, claim_index, body.helpful, _get_client_ip(request))
    return Response(status_code=204)


_ABOUT_PATH = FRONTEND_DIR / "about.html"
_ABOUT_TEMPLATE: str | None = None


@app.get("/about")
async def serve_about():
    global _ABOUT_TEMPLATE
    if not _ABOUT_PATH.is_file():
        raise HTTPException(status_code=404, detail="Page not found.")
    if _ABOUT_TEMPLATE is None:
        _ABOUT_TEMPLATE = _ABOUT_PATH.read_text(encoding="utf-8")
    return HTMLResponse(_ABOUT_TEMPLATE.replace("__CANONICAL_URL__", f"{settings.BASE_URL}/about"))


app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
