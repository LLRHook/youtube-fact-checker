"""Video processing, progress and capacity-limited queue recovery."""

import asyncio
import logging
import time
from dataclasses import dataclass, field

from backend import database as db
from backend.config import PIPELINE_VERSION, settings
from backend.models import TaskStatus, claim_row_to_public
from backend.services.claim_extractor import ClaimExtractionError, extract_claims
from backend.services.fact_checker import overall_score, summarize, verify_all
from backend.services.llm import Usage
from backend.services.transcript_service import TranscriptError, VideoTooLongError, extract_transcript

logger = logging.getLogger(__name__)


@dataclass
class TaskState:
    task_id: str
    status: TaskStatus
    stage: str = "queued"
    message: str = ""
    completed: int = 0
    total: int = 0
    video: dict | None = None
    claims: list[dict] = field(default_factory=list)
    error: str | None = None


tasks: dict[str, TaskState] = {}
IN_FLIGHT_ESTIMATE_USD = 0.60


async def capacity_available() -> bool:
    return (
        await db.count_videos_today() < settings.DAILY_VIDEO_LIMIT
        and await db.spend_today_usd()
        + IN_FLIGHT_ESTIMATE_USD * len([t for t in tasks.values() if t.status == TaskStatus.PROCESSING])
        < settings.DAILY_BUDGET_USD
    )


async def process_video(task_id, video_id, youtube_url):
    started = time.monotonic()
    state = tasks.setdefault(task_id, TaskState(task_id, TaskStatus.PROCESSING))
    usage = Usage()
    requests = 0
    try:
        state.stage, state.message = "transcript", "Fetching transcript…"
        transcript = await asyncio.to_thread(extract_transcript, youtube_url, settings.MAX_VIDEO_DURATION_SECONDS)
        state.video = dict(
            id=video_id,
            title=transcript.title,
            channel=transcript.channel,
            duration_seconds=transcript.duration_seconds,
            published_at=transcript.published_at,
        )
        state.stage, state.message = "claims", "Finding check-worthy claims…"
        claims, extraction_usage = await extract_claims(transcript)
        usage.add(extraction_usage)
        if claims:
            state.stage = "verifying"
            state.total = len(claims)
            state.message = f"Checking claim {state.completed} of {state.total}…"

            def on_claim_done(index, merged_claim):
                state.claims.append(claim_row_to_public({**merged_claim, "index": index + 1}).model_dump())
                state.completed += 1
                state.message = f"Checking claim {state.completed} of {state.total}…"

            claims, verdict_usage, verdict_requests = await verify_all(claims, transcript, on_claim_done)
            usage.add(verdict_usage)
            requests += verdict_requests
            state.stage, state.message = "summary", "Writing the summary…"
            summary, summary_usage = await summarize(transcript, claims)
            usage.add(summary_usage)
        else:
            summary = dict(summary="We didn't find any check-worthy factual claims in this video.", key_issues=[])
        await db.delete_claims_for_video(video_id)
        await db.create_claims(video_id, claims)
        score = overall_score(claims)
        await db.update_video_results(
            video_id,
            title=transcript.title,
            channel=transcript.channel,
            duration_seconds=transcript.duration_seconds,
            transcript_text=transcript.full_text,
            overall_truth_percentage=50 if score is None else score,
            summary=summary["summary"],
            key_issues=summary["key_issues"],
            channel_id=transcript.channel_id,
            published_at=transcript.published_at,
            pipeline_version=PIPELINE_VERSION,
            model=settings.VERDICT_MODEL,
            cost_usd=usage.cost_usd,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            search_requests=requests,
            processing_time_seconds=round(time.monotonic() - started, 1),
        )
        state.status, state.stage, state.message = TaskStatus.COMPLETED, "completed", "Done!"
        logger.info(
            "Video %s completed: claims=%d cost_usd=%.6f search_requests=%d",
            video_id,
            len(claims),
            usage.cost_usd,
            requests,
        )
    except (VideoTooLongError, TranscriptError, ClaimExtractionError) as exc:
        if isinstance(exc, ClaimExtractionError):
            usage.add(exc.usage)
        await _fail_task(state, video_id, str(exc), usage, requests)
    except Exception:
        logger.exception("Unexpected error processing video %s", video_id)
        await _fail_task(state, video_id, "An unexpected error occurred. Please try again later.", usage, requests)
    finally:
        tasks.pop(task_id, None)


async def _fail_task(state, video_id, message, usage, requests):
    state.status, state.stage, state.error = TaskStatus.FAILED, "failed", message
    try:
        await db.add_video_cost(video_id, usage.cost_usd, usage.input_tokens, usage.output_tokens, requests)
        await db.update_video_status(video_id, "failed", message)
    except Exception:
        logger.exception("Failed to persist failure for video %s", video_id)


async def queue_processor():
    first_run = True
    consecutive_errors = 0
    while True:
        try:
            if first_run:
                first_run = False
                await asyncio.sleep(5)
            else:
                await asyncio.sleep(min(settings.QUEUE_INTERVAL_MINUTES * 60 * (2**consecutive_errors), 3600))
            await db.prune_search_cache(settings.SEARCH_CACHE_DAYS)
            for video in await db.get_stale_processing_videos(stale_minutes=10, limit=3):
                if video["id"] not in tasks:
                    await db.update_video_status(video["id"], "queued")
            for video in await db.get_queued_videos(limit=5):
                if not await capacity_available():
                    break
                video_id = video["id"]
                if video_id in tasks:
                    continue
                tasks[video_id] = TaskState(video_id, TaskStatus.PROCESSING, message="Starting (from queue)...")
                try:
                    await db.update_video_status(video_id, "processing")
                except Exception:
                    tasks.pop(video_id, None)
                    raise
                await process_video(video_id, video_id, video["youtube_url"])
            consecutive_errors = 0
        except asyncio.CancelledError:
            break
        except Exception:
            consecutive_errors += 1
            logger.exception("Queue processor error (consecutive: %d)", consecutive_errors)
