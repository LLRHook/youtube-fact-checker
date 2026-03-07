"""YouTube Fact Checker — FastAPI application."""

import os
import time
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.config import settings, validate_settings
from backend.models import (
    CheckRequest,
    TaskResponse,
    TaskStatus,
    CheckResult,
    Claim,
    Source,
    ClaimCategory,
    PublicVideoSummary,
    PublicClaimDetail,
    PublicVideoDetail,
    ChannelSummary,
    ChannelDetail,
)
from backend.utils.validators import extract_video_id, is_valid_youtube_url
from backend.services.transcript_service import (
    extract_transcript,
    TranscriptError,
    VideoTooLongError,
)
from backend.services.claim_extractor import extract_claims, close_anthropic_client as close_sync_anthropic
from backend.services.fact_checker import fact_check_all_claims, close_anthropic_client as close_async_anthropic
from backend.services.search_service import close_http_client
from backend import database as db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# In-memory task store (for in-flight progress tracking only)
tasks: dict[str, TaskResponse] = {}

# Serve frontend static files
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# Queue processor task handle
_queue_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _queue_task
    validate_settings()
    await db.init_db()
    _queue_task = asyncio.create_task(queue_processor())
    yield
    _queue_task.cancel()
    try:
        await _queue_task
    except asyncio.CancelledError:
        pass
    await close_http_client()
    await close_async_anthropic()
    close_sync_anthropic()


app = FastAPI(title="YouTube Fact Checker", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
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
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' https://img.youtube.com https://i.ytimg.com data:; "
            "frame-src https://www.youtube-nocookie.com; "
            "connect-src 'self'; "
            "font-src 'self'"
        )
        path = request.url.path
        if path.endswith(_STATIC_EXTENSIONS):
            response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=86400"
        return response


app.add_middleware(SecurityHeadersMiddleware)


async def process_video(task_id: str, video_id: str, youtube_url: str):
    """Background task: extract transcript → claims → fact-check, then persist."""
    start_time = time.time()

    try:
        # Step 1: Extract transcript
        tasks[task_id].progress = "Extracting transcript..."
        transcript = await asyncio.to_thread(extract_transcript, youtube_url, settings.MAX_VIDEO_DURATION_SECONDS)

        # Step 2: Extract claims
        tasks[task_id].progress = f"Analyzing transcript ({len(transcript.full_text)} chars)..."
        raw_claims = await asyncio.to_thread(
            extract_claims,
            transcript.full_text,
            segments=transcript.segments,
        )

        if not raw_claims:
            elapsed = time.time() - start_time
            result = CheckResult(
                video_title=transcript.title,
                video_id=video_id,
                video_duration_seconds=transcript.duration_seconds,
                transcript_text=transcript.full_text[:2000],
                claims=[],
                overall_truth_percentage=0,
                summary="No verifiable factual claims found in this video.",
                processing_time_seconds=round(elapsed, 1),
            )
            tasks[task_id].status = TaskStatus.COMPLETED
            tasks[task_id].data = result

            await db.update_video_results(
                video_id,
                title=transcript.title,
                channel=transcript.channel,
                duration_seconds=transcript.duration_seconds,
                transcript_text=transcript.full_text,
                overall_truth_percentage=0,
                summary=result.summary,
                processing_time_seconds=result.processing_time_seconds,
            )
            _cleanup_task(task_id)
            return

        # Step 3: Fact-check each claim
        def on_progress(completed, total):
            tasks[task_id].progress = f"Fact-checking claim {completed}/{total}..."

        tasks[task_id].progress = f"Fact-checking {len(raw_claims)} claims..."
        checked_claims = await fact_check_all_claims(raw_claims, on_progress=on_progress)

        # Step 4: Build results
        claims = [
            Claim(
                id=f"claim-{i+1}",
                text=c["text"],
                timestamp_seconds=c.get("timestamp_seconds", 0),
                truth_percentage=c.get("truth_percentage", 50),
                confidence=c.get("confidence", 0.5),
                reasoning=c.get("reasoning", ""),
                sources=[Source(**s) for s in c.get("sources", [])],
                category=ClaimCategory(c.get("category", "fact")),
            )
            for i, c in enumerate(checked_claims)
        ]

        total_weight = 0
        weighted_sum = 0
        fact_count = 0
        opinion_count = 0
        for c in claims:
            if c.category == ClaimCategory.FACT:
                fact_count += 1
                total_weight += c.confidence
                weighted_sum += c.truth_percentage * c.confidence
            elif c.category == ClaimCategory.OPINION:
                opinion_count += 1
        overall = round(weighted_sum / total_weight) if total_weight > 0 else (50 if claims else 0)

        summary_parts = [f"Analyzed {len(claims)} statements."]
        if fact_count:
            summary_parts.append(f"{fact_count} factual claims with {overall}% average accuracy.")
        if opinion_count:
            summary_parts.append(f"{opinion_count} opinions identified.")

        elapsed = time.time() - start_time
        summary = " ".join(summary_parts)
        processing_time = round(elapsed, 1)

        tasks[task_id].status = TaskStatus.COMPLETED
        tasks[task_id].progress = "Done!"
        tasks[task_id].data = CheckResult(
            video_title=transcript.title,
            video_id=video_id,
            video_duration_seconds=transcript.duration_seconds,
            transcript_text=transcript.full_text[:2000],
            claims=claims,
            overall_truth_percentage=overall,
            summary=summary,
            processing_time_seconds=processing_time,
        )

        # Write claims before marking video as completed to avoid a window
        # where the video appears completed with zero claims.
        await db.delete_claims_for_video(video_id)
        await db.create_claims(video_id, checked_claims)
        await db.update_video_results(
            video_id,
            title=transcript.title,
            channel=transcript.channel,
            duration_seconds=transcript.duration_seconds,
            transcript_text=transcript.full_text,
            overall_truth_percentage=overall,
            summary=summary,
            processing_time_seconds=processing_time,
        )
        _cleanup_task(task_id)

    except VideoTooLongError as e:
        logger.warning("Video %s too long: %s", video_id, e)
        await _fail_task(task_id, video_id, str(e))
    except TranscriptError as e:
        logger.warning("Transcript error for video %s: %s", video_id, e)
        await _fail_task(task_id, video_id, str(e))
    except Exception as e:
        logger.exception("Unexpected error processing video %s", video_id)
        await _fail_task(task_id, video_id, f"Unexpected error: {str(e)[:200]}")


# --- Queue processor ---


async def queue_processor():
    """Background loop that processes queued videos."""
    while True:
        try:
            await asyncio.sleep(settings.QUEUE_INTERVAL_MINUTES * 60)
            queued = await db.get_queued_videos(limit=5)
            for video in queued:
                video_id = video["id"]
                youtube_url = video["youtube_url"]
                task_id = video_id

                tasks[task_id] = TaskResponse(
                    task_id=task_id,
                    status=TaskStatus.PROCESSING,
                    progress="Starting (from queue)...",
                )
                await db.update_video_status(video_id, "processing")
                await process_video(task_id, video_id, youtube_url)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Queue processor error")


def _cleanup_task(task_id: str):
    """Remove a completed/failed task from memory after persisting to DB."""
    tasks.pop(task_id, None)


async def _fail_task(task_id: str, video_id: str, error_msg: str):
    """Mark a task as failed in memory and DB, then clean up."""
    task = tasks.get(task_id)
    if task:
        task.status = TaskStatus.FAILED
        task.error = error_msg
    await db.update_video_status(video_id, "failed", error_msg)
    _cleanup_task(task_id)


def _build_claims_from_rows(claims_rows: list[dict]) -> list[Claim]:
    """Convert DB claim rows (with nested sources) to Claim model instances."""
    return [
        Claim(
            id=f"claim-{cr['claim_index']}",
            text=cr["text"],
            timestamp_seconds=cr["timestamp_seconds"],
            truth_percentage=cr["truth_percentage"],
            confidence=cr["confidence"],
            reasoning=cr["reasoning"],
            sources=[Source(title=s["title"], url=s["url"], snippet=s["snippet"]) for s in cr["sources"]],
            category=ClaimCategory(cr["category"]),
        )
        for cr in claims_rows
    ]


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


def _build_video_summary(video: dict, claims: list[dict]) -> PublicVideoSummary:
    """Build a PublicVideoSummary from a video row and its claims."""
    return PublicVideoSummary(
        id=video["id"],
        title=video["title"],
        channel=video["channel"],
        public_score=_calculate_public_score(claims),
        claim_count=len(claims),
        created_at=video["created_at"] or "",
    )


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


# --- API Routes ---


@app.post("/api/check")
async def check_video(req: CheckRequest, background_tasks: BackgroundTasks, request: Request):
    """Submit a YouTube video for fact-checking."""
    if not is_valid_youtube_url(req.youtube_url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL.")

    video_id = extract_video_id(req.youtube_url)
    client_ip = _get_client_ip(request)

    # Dedup: if video already completed in DB, return it
    existing = await db.get_video(video_id)
    if existing and existing["status"] == "completed":
        claims = _build_claims_from_rows(await db.get_claims_for_video(video_id))
        result = _build_completed_result(existing, claims)
        return {
            "task_id": video_id,
            "status": "completed",
            "data": result.model_dump(),
        }

    # If already queued, return queued status
    if existing and existing["status"] == "queued":
        return {"task_id": video_id, "status": "queued"}

    # Check if already processing in-memory
    existing_task = tasks.get(video_id)
    if existing_task and existing_task.status == TaskStatus.PROCESSING:
        return {"task_id": video_id, "status": "processing"}

    # Per-IP rate limit
    ip_count = await db.count_videos_today_by_ip(client_ip)
    if ip_count >= settings.IP_DAILY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"You've reached the limit of {settings.IP_DAILY_LIMIT} videos per day. Please try again tomorrow.",
        )

    # Site-wide daily limit — queue if exceeded
    daily_count = await db.count_videos_today()
    if daily_count >= settings.DAILY_VIDEO_LIMIT:
        if not existing:
            await db.create_video(video_id, req.youtube_url, ip_address=client_ip, status="queued")
        else:
            await db.update_video_status(video_id, "queued")
        return {"task_id": video_id, "status": "queued"}

    # Under limits — process immediately
    task_id = video_id
    if not existing:
        await db.create_video(video_id, req.youtube_url, ip_address=client_ip)
    elif existing["status"] == "failed":
        await db.update_video_status(video_id, "processing")

    tasks[task_id] = TaskResponse(
        task_id=task_id,
        status=TaskStatus.PROCESSING,
        progress="Starting...",
    )

    background_tasks.add_task(process_video, task_id, video_id, req.youtube_url)

    return {"task_id": task_id, "status": "processing"}


@app.get("/api/check/{task_id}")
async def get_task_status(task_id: str):
    """Poll the status of a fact-check task."""
    # Check in-memory first (in-flight tasks)
    if task_id in tasks:
        task = tasks[task_id]
        return task.model_dump()

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
        ).model_dump()

    if video["status"] == "failed":
        return TaskResponse(
            task_id=task_id,
            status=TaskStatus.FAILED,
            error=video.get("error"),
        ).model_dump()

    if video["status"] == "queued":
        return TaskResponse(
            task_id=task_id,
            status=TaskStatus.QUEUED,
            progress="Queued — will be processed soon.",
        ).model_dump()

    # Still processing but not in memory
    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PROCESSING,
        progress="Processing...",
    ).model_dump()


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/stats")
async def public_stats():
    """Aggregate site statistics."""
    return await db.get_stats()


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
        return round(weighted_sum / total_weight)
    return 50 if claims else 0


@app.get("/api/videos")
async def public_list_videos(page: int = 1, limit: int = 50):
    """List completed videos with pagination."""
    limit = max(1, min(limit, 100))
    page = max(1, page)

    total = await db.count_videos(status="completed")
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    if page > total_pages:
        page = total_pages
    offset = (page - 1) * limit

    videos = await db.list_videos(status="completed", limit=limit, offset=offset)
    video_ids = [v["id"] for v in videos]
    all_claims = await db.get_claims_for_videos(video_ids)
    items = [_build_video_summary(v, all_claims.get(v["id"], [])).model_dump() for v in videos]
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": total_pages,
    }


@app.get("/api/videos/{video_id}")
async def public_get_video(video_id: str):
    """Public video detail."""
    video = await db.get_video(video_id)
    if not video or video["status"] != "completed":
        raise HTTPException(status_code=404, detail="Video not found.")

    claims = await db.get_claims_for_video(video_id)
    public_score = _calculate_public_score(claims)

    public_claims = [
        PublicClaimDetail(
            text=c["text"],
            timestamp_seconds=c["timestamp_seconds"],
            truth_percentage=c["truth_percentage"],
            confidence=c["confidence"],
            reasoning=c["reasoning"],
            category=c["category"],
            sources=[
                Source(title=s["title"], url=s["url"], snippet=s["snippet"])
                for s in c.get("sources", [])
            ],
        ).model_dump()
        for c in claims
    ]

    return PublicVideoDetail(
        id=video["id"],
        title=video["title"],
        channel=video["channel"],
        youtube_url=video["youtube_url"],
        duration_seconds=video["duration_seconds"],
        overall_truth_percentage=video["overall_truth_percentage"],
        public_score=public_score,
        summary=video["summary"],
        created_at=video["created_at"] or "",
        claims=public_claims,
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
    videos = await db.get_channel_videos(channel_name)
    if not videos:
        raise HTTPException(status_code=404, detail="Channel not found.")

    video_ids = [v["id"] for v in videos]
    all_claims = await db.get_claims_for_videos(video_ids)

    video_summaries = [_build_video_summary(v, all_claims.get(v["id"], [])) for v in videos]

    all_scores = [vs.public_score for vs in video_summaries if vs.public_score > 0]
    avg_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0

    return ChannelDetail(
        channel=channel_name,
        video_count=len(video_summaries),
        avg_score=avg_score,
        videos=video_summaries,
    ).model_dump()


# --- Frontend ---


@app.get("/")
async def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/videos")
async def serve_videos_page():
    return FileResponse(FRONTEND_DIR / "videos.html")


@app.get("/video/{video_id}")
async def serve_video_page(video_id: str):
    return FileResponse(FRONTEND_DIR / "video.html")


@app.get("/channel/{channel_name}")
async def serve_channel_page(channel_name: str):
    return FileResponse(FRONTEND_DIR / "channel.html")


app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
