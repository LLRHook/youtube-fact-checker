"""YouTube URL validation through the in-process Rust processor."""

from backend.utils.native_core import NativeInputError, process


def extract_video_id(url: str) -> str | None:
    """Extract an exact video ID from a supported YouTube host/path or bare ID."""
    try:
        return process("extract_video_id", url=url if isinstance(url, str) else None)
    except NativeInputError:
        return None


def is_valid_youtube_url(url: str) -> bool:
    return extract_video_id(url) is not None
