"""YouTube transcript extraction service."""

import logging
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)
import yt_dlp

from backend.utils.validators import extract_video_id
from backend.utils.native_core import NativeInputError, process, segment_entries, wire_value

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
    ):
        self.video_id = video_id
        self.title = title
        self.channel = channel
        self.duration_seconds = duration_seconds
        self.segments = segments
        self.full_text = full_text


def get_video_info(video_id: str) -> dict:
    """Get video metadata using yt-dlp (no download)."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "socket_timeout": 15,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            "title": (info.get("title") or "Unknown").strip(),
            "duration": info.get("duration", 0),
            "channel": (info.get("channel") or "").strip(),
        }


def extract_transcript(youtube_url: str, max_duration_seconds: int = 600) -> TranscriptResult:
    """
    Extract transcript from a YouTube video.

    Args:
        youtube_url: YouTube video URL
        max_duration_seconds: Maximum allowed video duration (default 10 min)

    Returns:
        TranscriptResult with segments and full text

    Raises:
        TranscriptError: If transcript cannot be extracted
        VideoTooLongError: If video exceeds max duration
    """
    video_id = extract_video_id(youtube_url)
    if not video_id:
        raise TranscriptError(f"Invalid YouTube URL: {youtube_url}")

    # Get video info for title and duration check
    try:
        info = get_video_info(video_id)
    except Exception as e:
        raise TranscriptError(f"Could not fetch video info: {str(e)[:200]}") from e

    try:
        validated = process("validate_duration", duration=wire_value(info.get("duration")),
                            max_duration=max_duration_seconds)
    except NativeInputError as e:
        raise TranscriptError("Could not determine video duration.") from e
    duration = validated["duration"]
    if validated["too_long"]:
        raise VideoTooLongError(
            f"Video is {duration}s ({duration/60:.1f} min). "
            f"Maximum allowed is {max_duration_seconds}s ({max_duration_seconds/60:.0f} min)."
        )

    # Extract transcript
    try:
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.fetch(video_id)
    except TranscriptsDisabled:
        raise TranscriptError("Transcripts are disabled for this video.") from None
    except NoTranscriptFound:
        raise TranscriptError("No transcript found for this video.") from None
    except VideoUnavailable:
        raise TranscriptError("Video is unavailable.") from None
    except Exception as e:
        raise TranscriptError(f"Could not extract transcript: {str(e)[:200]}") from e

    # Validate/filter the entire caption batch in one in-process Rust call.
    try:
        normalized = process("normalize_transcript", entries=segment_entries(transcript_list))
    except NativeInputError as e:
        raise TranscriptError("Could not extract transcript: invalid transcript data.") from e
    segments = [TranscriptSegment(**entry) for entry in normalized["segments"]]
    full_text = normalized["full_text"]

    if not full_text.strip():
        raise TranscriptError("Transcript is empty after filtering.")

    return TranscriptResult(
        video_id=video_id,
        title=info["title"],
        channel=info["channel"],
        duration_seconds=duration,
        segments=segments,
        full_text=full_text,
    )
