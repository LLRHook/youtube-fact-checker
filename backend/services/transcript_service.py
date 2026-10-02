"""YouTube transcript extraction service."""

import logging
from datetime import datetime
from types import SimpleNamespace

import httpx
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    IpBlocked,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
)
from youtube_transcript_api.proxies import GenericProxyConfig

from backend.config import settings
from backend.utils.validators import extract_video_id

logger = logging.getLogger(__name__)


class TranscriptError(Exception):
    pass


class VideoTooLongError(TranscriptError):
    pass


class TranscriptSegment:
    def __init__(self, text: str, start: float, duration: float):
        self.text = text
        self.start = start
        self.duration = duration


class TranscriptResult:
    def __init__(
        self,
        video_id: str,
        title: str,
        channel: str,
        duration_seconds: float,
        segments: list[TranscriptSegment],
        full_text: str,
        channel_id: str = "",
        published_at: str = "",
        language: str = "",
        is_generated: bool = False,
    ):
        self.video_id = video_id
        self.title = title
        self.channel = channel
        self.duration_seconds = duration_seconds
        self.segments = segments
        self.full_text = full_text
        self.channel_id = channel_id
        self.published_at = published_at
        self.language = language
        self.is_generated = is_generated


def get_video_info(video_id: str) -> dict:
    """Get video metadata using yt-dlp (no download)."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "socket_timeout": 15,
    }
    if settings.TRANSCRIPT_PROXY_URL:
        ydl_opts["proxy"] = settings.TRANSCRIPT_PROXY_URL
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        uploaded = info.get("upload_date") or ""
        try:
            uploaded = datetime.strptime(uploaded, "%Y%m%d").date().isoformat()
        except ValueError:
            uploaded = ""
        return {
            "channel_id": info.get("channel_id") or "",
            "upload_date": uploaded,
            "subtitles": info.get("subtitles") or {},
            "automatic_captions": info.get("automatic_captions") or {},
            "title": (info.get("title") or "Unknown").strip(),
            "duration": info.get("duration", 0),
            "channel": (info.get("channel") or "").strip(),
        }


def extract_transcript(youtube_url: str, max_duration_seconds: int | None = None) -> TranscriptResult:
    """
    Extract transcript from a YouTube video.

    Args:
        youtube_url: YouTube video URL
        max_duration_seconds: Maximum allowed video duration (defaults to settings.MAX_VIDEO_DURATION_SECONDS)

    Returns:
        TranscriptResult with segments and full text

    Raises:
        TranscriptError: If transcript cannot be extracted
        VideoTooLongError: If video exceeds max duration
    """
    if max_duration_seconds is None:
        max_duration_seconds = settings.MAX_VIDEO_DURATION_SECONDS
    video_id = extract_video_id(youtube_url)
    if not video_id:
        raise TranscriptError(f"Invalid YouTube URL: {youtube_url}")

    # Get video info for title and duration check
    try:
        info = get_video_info(video_id)
    except Exception as e:
        raise TranscriptError(f"Could not fetch video info: {str(e)[:200]}") from e

    duration = float(info.get("duration") or 0)
    if not duration:
        raise TranscriptError("Could not determine video duration.")
    if duration > max_duration_seconds:
        raise VideoTooLongError(
            f"Video is {duration}s ({duration / 60:.1f} min). "
            f"Maximum allowed is {max_duration_seconds}s ({max_duration_seconds / 60:.0f} min)."
        )

    language = ""
    is_generated = False
    try:
        proxy = settings.TRANSCRIPT_PROXY_URL
        api = (
            YouTubeTranscriptApi(proxy_config=GenericProxyConfig(http_url=proxy, https_url=proxy))
            if proxy
            else YouTubeTranscriptApi()
        )
        available = list(api.list(video_id))

        def preference(item):
            english = item.language_code in {"en", "en-US", "en-GB"}
            return 0 if english and not item.is_generated else 1 if english else 2 if not item.is_generated else 3

        chosen = min(available, key=preference) if available else None
        if chosen is None:
            raise TranscriptError("No transcript found for this video.")
        language, is_generated = chosen.language_code, chosen.is_generated
        transcript_list = chosen.fetch()
    except (TranscriptsDisabled, VideoUnavailable) as exc:
        message = (
            "Transcripts are disabled for this video."
            if isinstance(exc, TranscriptsDisabled)
            else "Video is unavailable."
        )
        raise TranscriptError(message) from exc
    except Exception as exc:
        if isinstance(exc, (RequestBlocked, IpBlocked)):
            message = "YouTube temporarily blocked transcript access from our server. Please try again later."
        elif isinstance(exc, NoTranscriptFound):
            message = "No transcript found for this video."
        elif isinstance(exc, TranscriptError):
            message = str(exc)
        else:
            message = f"Could not extract transcript: {str(exc)[:200]}"
        try:
            transcript_list, language, is_generated = _captions_fallback(info)
        except Exception:
            raise TranscriptError(message) from exc

    # Build segments and full text
    segments = []
    text_parts = []
    for entry in transcript_list:
        try:
            text = " ".join(str(entry.text).split())
            start = float(entry.start)
            dur = float(entry.duration)
        except (TypeError, ValueError, AttributeError) as e:
            logger.warning("Skipping malformed transcript segment: %s", e)
            continue
        # Skip empty or music/sound effect markers
        if not text or (text.startswith("[") and text.endswith("]")):
            continue
        segments.append(
            TranscriptSegment(
                text=text,
                start=start,
                duration=dur,
            )
        )
        text_parts.append(text)

    full_text = " ".join(text_parts)

    if not full_text.strip():
        raise TranscriptError("Transcript is empty after filtering.")

    return TranscriptResult(
        video_id=video_id,
        title=info["title"],
        channel=info["channel"],
        duration_seconds=duration,
        segments=segments,
        full_text=full_text,
        channel_id=info.get("channel_id", ""),
        published_at=info.get("upload_date", ""),
        language=language,
        is_generated=is_generated,
    )


def _captions_fallback(info):
    for key in ("subtitles", "automatic_captions"):
        captions = info.get(key) or {}
        for language in sorted(captions, key=lambda code: not code.startswith("en")):
            for caption in captions[language]:
                if caption.get("ext") != "json3":
                    continue
                try:
                    with httpx.Client(timeout=20, proxy=settings.TRANSCRIPT_PROXY_URL or None) as client:
                        response = client.get(caption["url"])
                        response.raise_for_status()
                        events = response.json().get("events", [])
                    entries = []
                    for event in events:
                        text = "".join(seg.get("utf8", "") for seg in event.get("segs", [])).strip()
                        if text:
                            entries.append(
                                SimpleNamespace(
                                    text=text,
                                    start=event.get("tStartMs", 0) / 1000,
                                    duration=event.get("dDurationMs", 0) / 1000,
                                )
                            )
                    if entries:
                        return entries, language, key == "automatic_captions"
                except Exception as exc:
                    logger.warning("Caption fallback failed: %s", exc)
    raise TranscriptError("No captions found for this video.")


def format_timestamp(seconds) -> str:
    seconds = max(0, int(seconds))
    minutes, second = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    return f"{hours}:{minute:02d}:{second:02d}" if hours else f"{minute:02d}:{second:02d}"


def build_timestamped_transcript(segments) -> str:
    lines = []
    text = ""
    start = 0
    for segment in segments:
        segment_text = " ".join(segment.text.split())
        if text and len(text) + len(segment_text) + 1 > 200:
            lines.append(f"[{format_timestamp(start)}] {text}")
            text = ""
        if not text:
            start = segment.start
        text = (text + " " + segment_text).strip()
    if text:
        lines.append(f"[{format_timestamp(start)}] {text}")
    return "\n".join(lines)
