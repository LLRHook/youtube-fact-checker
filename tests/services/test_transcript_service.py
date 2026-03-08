"""Tests for backend.services.transcript_service."""

import pytest
from unittest.mock import patch, MagicMock
from backend.services.transcript_service import (
    extract_transcript,
    TranscriptError,
    VideoTooLongError,
    TranscriptSegment,
)


def _mock_video_info(duration=120, title="Test Video", channel="TestCh"):
    return {"title": title, "duration": duration, "channel": channel}


def _mock_transcript_entries(texts=None):
    """Create mock transcript entries matching youtube-transcript-api output."""
    if texts is None:
        texts = [("Hello world", 0.0, 5.0), ("Second line", 5.0, 3.0)]
    entries = []
    for text, start, dur in texts:
        e = MagicMock()
        e.text = text
        e.start = start
        e.duration = dur
        entries.append(e)
    return entries


class TestExtractTranscript:
    @patch("backend.services.transcript_service.YouTubeTranscriptApi")
    @patch("backend.services.transcript_service.get_video_info")
    def test_success(self, mock_info, mock_ytt_cls):
        mock_info.return_value = _mock_video_info()
        api_instance = MagicMock()
        mock_ytt_cls.return_value = api_instance
        api_instance.fetch.return_value = _mock_transcript_entries()

        result = extract_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result.video_id == "dQw4w9WgXcQ"
        assert result.title == "Test Video"
        assert result.channel == "TestCh"
        assert "Hello world" in result.full_text
        assert len(result.segments) == 2

    @patch("backend.services.transcript_service.get_video_info")
    def test_video_too_long(self, mock_info):
        mock_info.return_value = _mock_video_info(duration=9999)
        with pytest.raises(VideoTooLongError):
            extract_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ", max_duration_seconds=600)

    @patch("backend.services.transcript_service.YouTubeTranscriptApi")
    @patch("backend.services.transcript_service.get_video_info")
    def test_no_transcript(self, mock_info, mock_ytt_cls):
        from youtube_transcript_api._errors import NoTranscriptFound
        mock_info.return_value = _mock_video_info()
        api_instance = MagicMock()
        mock_ytt_cls.return_value = api_instance
        api_instance.fetch.side_effect = NoTranscriptFound("vid", [], None)

        with pytest.raises(TranscriptError, match="No transcript found"):
            extract_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    @patch("backend.services.transcript_service.YouTubeTranscriptApi")
    @patch("backend.services.transcript_service.get_video_info")
    def test_transcripts_disabled(self, mock_info, mock_ytt_cls):
        from youtube_transcript_api._errors import TranscriptsDisabled
        mock_info.return_value = _mock_video_info()
        api_instance = MagicMock()
        mock_ytt_cls.return_value = api_instance
        api_instance.fetch.side_effect = TranscriptsDisabled("vid")

        with pytest.raises(TranscriptError, match="disabled"):
            extract_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    @patch("backend.services.transcript_service.YouTubeTranscriptApi")
    @patch("backend.services.transcript_service.get_video_info")
    def test_video_unavailable(self, mock_info, mock_ytt_cls):
        from youtube_transcript_api._errors import VideoUnavailable
        mock_info.return_value = _mock_video_info()
        api_instance = MagicMock()
        mock_ytt_cls.return_value = api_instance
        api_instance.fetch.side_effect = VideoUnavailable("vid")

        with pytest.raises(TranscriptError, match="unavailable"):
            extract_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_invalid_url(self):
        with pytest.raises(TranscriptError, match="Invalid YouTube URL"):
            extract_transcript("not-a-url")

    @patch("backend.services.transcript_service.YouTubeTranscriptApi")
    @patch("backend.services.transcript_service.get_video_info")
    def test_empty_after_filtering(self, mock_info, mock_ytt_cls):
        mock_info.return_value = _mock_video_info()
        # All entries are bracketed (music markers) — should be filtered out
        entries = _mock_transcript_entries([("[Music]", 0.0, 5.0), ("[Applause]", 5.0, 3.0)])
        api_instance = MagicMock()
        mock_ytt_cls.return_value = api_instance
        api_instance.fetch.return_value = entries

        with pytest.raises(TranscriptError, match="empty"):
            extract_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    @patch("backend.services.transcript_service.get_video_info")
    def test_zero_duration(self, mock_info):
        mock_info.return_value = _mock_video_info(duration=0)
        with pytest.raises(TranscriptError, match="duration"):
            extract_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
