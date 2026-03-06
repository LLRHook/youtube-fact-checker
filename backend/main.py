"""YouTube Fact Checker — FastAPI application."""

import uuid
import time
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.models import (
    CheckRequest,
    TaskResponse,
    TaskStatus,
    CheckResult,
    Claim,
    Source,
    ClaimCategory,
    ApprovalStatus,
    VideoSummary,
    ClaimDetail,
    VideoDetail,
    ClaimAttributionUpdate,
    VideoApprovalUpdate,
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

# In-memory task store (for in-flight progress tracking only)
tasks: dict[str, TaskResponse] = {}

# Serve frontend static files
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    yield


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

            # Persist to DB
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

        # Calculate overall score (weighted by confidence)
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

        # Persist to DB
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
        # Persist claims
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


# --- API Routes ---


@app.post("/api/check")
async def check_video(req: CheckRequest, background_tasks: BackgroundTasks):
    """Submit a YouTube video for fact-checking."""
    if not is_valid_youtube_url(req.youtube_url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL.")

    video_id = extract_video_id(req.youtube_url)

    # Dedup: if video already completed in DB, return it
    existing = await db.get_video(video_id)
    if existing and existing["status"] == "completed":
        # Build response from DB
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
        # Return as already-completed task
        task_id = video_id
        return {
            "task_id": task_id,
            "status": "completed",
            "data": result.model_dump(),
        }

    # Check if already processing in-memory
    for tid, t in tasks.items():
        if tid == video_id or (t.data and t.data.video_id == video_id):
            if t.status == TaskStatus.PROCESSING:
                return {"task_id": tid, "status": "processing"}

    # New video — create DB row and start processing
    task_id = video_id
    if not existing:
        await db.create_video(video_id, req.youtube_url)

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

    # Fall back to DB (completed/failed, survives restarts)
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

    # Still processing but not in memory (shouldn't normally happen)
    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PROCESSING,
        progress="Processing...",
    ).model_dump()


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# --- Admin API ---


@app.get("/api/admin/videos")
async def admin_list_videos(
    status: str | None = Query(None),
    approval: str | None = Query(None),
):
    """List all videos with optional status/approval filters."""
    videos = await db.list_videos(status=status, approval_status=approval)
    result = []
    for v in videos:
        claims = await db.get_claims_for_video(v["id"])
        result.append(
            VideoSummary(
                id=v["id"],
                title=v["title"],
                channel=v["channel"],
                overall_truth_percentage=v["overall_truth_percentage"],
                claim_count=len(claims),
                status=v["status"],
                approval_status=v["approval_status"],
                created_at=v["created_at"] or "",
            ).model_dump()
        )
    return result


@app.get("/api/admin/videos/{video_id}")
async def admin_get_video(video_id: str):
    """Full video detail with all claims and sources."""
    video = await db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found.")

    claims_rows = await db.get_claims_for_video(video_id)
    claims = []
    for cr in claims_rows:
        claims.append(
            ClaimDetail(
                id=cr["id"],
                claim_index=cr["claim_index"],
                text=cr["text"],
                timestamp_seconds=cr["timestamp_seconds"],
                truth_percentage=cr["truth_percentage"],
                confidence=cr["confidence"],
                reasoning=cr["reasoning"],
                category=cr["category"],
                attributed_to_creator=bool(cr["attributed_to_creator"]),
                sources=[
                    Source(title=s["title"], url=s["url"], snippet=s["snippet"])
                    for s in cr["sources"]
                ],
            ).model_dump()
        )

    return VideoDetail(
        id=video["id"],
        youtube_url=video["youtube_url"],
        title=video["title"],
        channel=video["channel"],
        duration_seconds=video["duration_seconds"],
        overall_truth_percentage=video["overall_truth_percentage"],
        summary=video["summary"],
        processing_time_seconds=video["processing_time_seconds"],
        status=video["status"],
        approval_status=video["approval_status"],
        created_at=video["created_at"] or "",
        claims=claims,
    ).model_dump()


@app.patch("/api/admin/claims/{claim_id}/attribution")
async def admin_update_attribution(claim_id: int, body: ClaimAttributionUpdate):
    """Toggle whether a claim is attributed to the content creator."""
    await db.update_claim_attribution(claim_id, body.attributed_to_creator)
    return {"ok": True, "claim_id": claim_id, "attributed_to_creator": body.attributed_to_creator}


@app.patch("/api/admin/videos/{video_id}/approval")
async def admin_update_approval(video_id: str, body: VideoApprovalUpdate):
    """Set video approval status (pending/approved/rejected)."""
    video = await db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found.")
    await db.set_video_approval(video_id, body.approval_status.value)
    return {"ok": True, "video_id": video_id, "approval_status": body.approval_status.value}


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


@app.get("/admin")
async def serve_admin():
    return FileResponse(FRONTEND_DIR / "admin.html")


@app.get("/admin.js")
async def serve_admin_js():
    return FileResponse(FRONTEND_DIR / "admin.js", media_type="application/javascript")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
