"""YouTube Fact Checker — FastAPI application."""

import time
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse

from backend.config import settings
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
from backend.services.claim_extractor import extract_claims
from backend.services.fact_checker import fact_check_all_claims
from backend import database as db

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
    await db.init_db()
    _queue_task = asyncio.create_task(queue_processor())
    yield
    _queue_task.cancel()
    try:
        await _queue_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="YouTube Fact Checker", version="1.0.0", lifespan=lifespan)


async def process_video(task_id: str, video_id: str, youtube_url: str):
    """Background task: extract transcript → claims → fact-check, then persist."""
    start_time = time.time()

    try:
        # Step 1: Extract transcript
        tasks[task_id].progress = "Extracting transcript..."
        transcript = await asyncio.to_thread(extract_transcript, youtube_url)

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
                channel=getattr(transcript, "channel", ""),
                duration_seconds=transcript.duration_seconds,
                transcript_text=transcript.full_text,
                overall_truth_percentage=0,
                summary=result.summary,
                processing_time_seconds=result.processing_time_seconds,
            )
            return

        # Step 3: Fact-check each claim
        total_claims = len(raw_claims)

        def on_progress(completed, total):
            tasks[task_id].progress = f"Fact-checking claim {completed}/{total}..."

        tasks[task_id].progress = f"Fact-checking {total_claims} claims..."
        checked_claims = await fact_check_all_claims(raw_claims, on_progress=on_progress)

        # Step 4: Build results
        claims = []
        for i, c in enumerate(checked_claims):
            claims.append(
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
            )

        if claims:
            total_weight = sum(c.confidence for c in claims if c.category == ClaimCategory.FACT)
            if total_weight > 0:
                weighted_sum = sum(
                    c.truth_percentage * c.confidence
                    for c in claims
                    if c.category == ClaimCategory.FACT
                )
                overall = round(weighted_sum / total_weight)
            else:
                overall = 50
        else:
            overall = 0

        fact_count = sum(1 for c in claims if c.category == ClaimCategory.FACT)
        opinion_count = sum(1 for c in claims if c.category == ClaimCategory.OPINION)

        summary_parts = [f"Analyzed {len(claims)} statements."]
        if fact_count:
            summary_parts.append(f"{fact_count} factual claims with {overall}% average accuracy.")
        if opinion_count:
            summary_parts.append(f"{opinion_count} opinions identified.")

        elapsed = time.time() - start_time
        tasks[task_id].status = TaskStatus.COMPLETED
        tasks[task_id].progress = "Done!"
        tasks[task_id].data = CheckResult(
            video_title=transcript.title,
            video_id=video_id,
            video_duration_seconds=transcript.duration_seconds,
            transcript_text=transcript.full_text[:2000],
            claims=claims,
            overall_truth_percentage=overall,
            summary=" ".join(summary_parts),
            processing_time_seconds=round(elapsed, 1),
        )

        await db.update_video_results(
            video_id,
            title=transcript.title,
            channel=getattr(transcript, "channel", ""),
            duration_seconds=transcript.duration_seconds,
            transcript_text=transcript.full_text,
            overall_truth_percentage=overall,
            summary=" ".join(summary_parts),
            processing_time_seconds=round(elapsed, 1),
        )
        claims_for_db = []
        for c in checked_claims:
            claims_for_db.append({
                "text": c["text"],
                "timestamp_seconds": c.get("timestamp_seconds", 0),
                "truth_percentage": c.get("truth_percentage", 50),
                "confidence": c.get("confidence", 0.5),
                "reasoning": c.get("reasoning", ""),
                "category": c.get("category", "fact"),
                "sources": c.get("sources", []),
            })
        await db.create_claims(video_id, claims_for_db)

    except VideoTooLongError as e:
        tasks[task_id].status = TaskStatus.FAILED
        tasks[task_id].error = str(e)
        await db.update_video_status(video_id, "failed", str(e))
    except TranscriptError as e:
        tasks[task_id].status = TaskStatus.FAILED
        tasks[task_id].error = str(e)
        await db.update_video_status(video_id, "failed", str(e))
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)[:200]}"
        tasks[task_id].status = TaskStatus.FAILED
        tasks[task_id].error = error_msg
        await db.update_video_status(video_id, "failed", error_msg)


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
        claims_rows = await db.get_claims_for_video(video_id)
        claims = []
        for cr in claims_rows:
            claims.append(
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
            )
        result = CheckResult(
            video_title=existing["title"],
            video_id=video_id,
            video_duration_seconds=existing["duration_seconds"],
            transcript_text=existing.get("transcript_text", "")[:2000],
            claims=claims,
            overall_truth_percentage=existing["overall_truth_percentage"],
            summary=existing["summary"],
            processing_time_seconds=existing["processing_time_seconds"],
        )
        return {
            "task_id": video_id,
            "status": "completed",
            "data": result.model_dump(),
        }

    # If already queued, return queued status
    if existing and existing["status"] == "queued":
        return {"task_id": video_id, "status": "queued"}

    # Check if already processing in-memory
    for tid, t in tasks.items():
        if tid == video_id or (t.data and t.data.video_id == video_id):
            if t.status == TaskStatus.PROCESSING:
                return {"task_id": tid, "status": "processing"}

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
        claims_rows = await db.get_claims_for_video(task_id)
        claims = []
        for cr in claims_rows:
            claims.append(
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
            )
        result = CheckResult(
            video_title=video["title"],
            video_id=task_id,
            video_duration_seconds=video["duration_seconds"],
            transcript_text=video.get("transcript_text", "")[:2000],
            claims=claims,
            overall_truth_percentage=video["overall_truth_percentage"],
            summary=video["summary"],
            processing_time_seconds=video["processing_time_seconds"],
        )
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


# --- Public API ---


def _calculate_public_score(claims: list[dict]) -> int:
    """Calculate score from fact claims."""
    fact_claims = [c for c in claims if c.get("category") == "fact"]
    if not fact_claims:
        return 0
    total_weight = sum(c.get("confidence", 0.5) for c in fact_claims)
    if total_weight == 0:
        return 0
    weighted_sum = sum(
        c.get("truth_percentage", 50) * c.get("confidence", 0.5) for c in fact_claims
    )
    return round(weighted_sum / total_weight)


@app.get("/api/videos")
async def public_list_videos():
    """List completed videos."""
    videos = await db.list_videos(status="completed")
    result = []
    for v in videos:
        claims = await db.get_claims_for_video(v["id"])
        public_score = _calculate_public_score(claims)
        result.append(
            PublicVideoSummary(
                id=v["id"],
                title=v["title"],
                channel=v["channel"],
                public_score=public_score,
                claim_count=len(claims),
                created_at=v["created_at"] or "",
            ).model_dump()
        )
    return result


@app.get("/api/videos/{video_id}")
async def public_get_video(video_id: str):
    """Public video detail."""
    video = await db.get_video(video_id)
    if not video or video["status"] != "completed":
        raise HTTPException(status_code=404, detail="Video not found.")

    claims = await db.get_claims_for_video(video_id)
    public_score = _calculate_public_score(claims)

    public_claims = []
    for c in claims:
        public_claims.append(
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
        )

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

    video_summaries = []
    for v in videos:
        claims = await db.get_claims_for_video(v["id"])
        public_score = _calculate_public_score(claims)
        video_summaries.append(
            PublicVideoSummary(
                id=v["id"],
                title=v["title"],
                channel=v["channel"],
                public_score=public_score,
                claim_count=len(claims),
                created_at=v["created_at"] or "",
            ).model_dump()
        )

    all_scores = [vs["public_score"] for vs in video_summaries if vs["public_score"] > 0]
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


@app.get("/styles.css")
async def serve_css():
    return FileResponse(FRONTEND_DIR / "styles.css", media_type="text/css")


@app.get("/app.js")
async def serve_js():
    return FileResponse(FRONTEND_DIR / "app.js", media_type="application/javascript")


@app.get("/videos")
async def serve_videos_page():
    return FileResponse(FRONTEND_DIR / "videos.html")


@app.get("/videos.js")
async def serve_videos_js():
    return FileResponse(FRONTEND_DIR / "videos.js", media_type="application/javascript")


@app.get("/video/{video_id}")
async def serve_video_page(video_id: str):
    return FileResponse(FRONTEND_DIR / "video.html")


@app.get("/video.js")
async def serve_video_js():
    return FileResponse(FRONTEND_DIR / "video.js", media_type="application/javascript")


@app.get("/channel/{channel_name}")
async def serve_channel_page(channel_name: str):
    return FileResponse(FRONTEND_DIR / "channel.html")


@app.get("/channel.js")
async def serve_channel_js():
    return FileResponse(FRONTEND_DIR / "channel.js", media_type="application/javascript")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
