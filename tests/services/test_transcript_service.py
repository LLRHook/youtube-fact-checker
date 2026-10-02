"""Tests for backend.services.transcript_service."""

from unittest.mock import MagicMock, patch

import pytest

from backend.services.transcript_service import (
    TranscriptError,
    VideoTooLongError,
    extract_transcript,
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
        track = MagicMock(language_code="en", is_generated=False)
        track.fetch.return_value = _mock_transcript_entries([
            ("  Hello\n\tworld  ", 0.0, 5.0), (" Second\r\n  line ", 5.0, 3.0)
        ])
        api_instance.list.return_value = [track]

        result = extract_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result.video_id == "dQw4w9WgXcQ"
        assert result.title == "Test Video"
        assert result.channel == "TestCh"
        assert result.full_text == "Hello world Second line"
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
        api_instance.list.side_effect = NoTranscriptFound("vid", [], None)

        with pytest.raises(TranscriptError, match="No transcript found"):
            extract_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    @patch("backend.services.transcript_service.YouTubeTranscriptApi")
    @patch("backend.services.transcript_service.get_video_info")
    def test_transcripts_disabled(self, mock_info, mock_ytt_cls):
        from youtube_transcript_api._errors import TranscriptsDisabled

        mock_info.return_value = _mock_video_info()
        api_instance = MagicMock()
        mock_ytt_cls.return_value = api_instance
        api_instance.list.side_effect = TranscriptsDisabled("vid")

        with pytest.raises(TranscriptError, match="disabled"):
            extract_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    @patch("backend.services.transcript_service.YouTubeTranscriptApi")
    @patch("backend.services.transcript_service.get_video_info")
    def test_video_unavailable(self, mock_info, mock_ytt_cls):
        from youtube_transcript_api._errors import VideoUnavailable

        mock_info.return_value = _mock_video_info()
        api_instance = MagicMock()
        mock_ytt_cls.return_value = api_instance
        api_instance.list.side_effect = VideoUnavailable("vid")

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
        track = MagicMock(language_code="en", is_generated=False)
        track.fetch.return_value = entries
        api_instance.list.return_value = [track]

        with pytest.raises(TranscriptError, match="empty"):
            extract_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    @patch("backend.services.transcript_service.get_video_info")
    def test_zero_duration(self, mock_info):
        mock_info.return_value = _mock_video_info(duration=0)
        with pytest.raises(TranscriptError, match="duration"):
            extract_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")


@pytest.mark.parametrize(
    "tracks,expected",
    [
        ([("de", False), ("en", True), ("en-GB", False)], ("en-GB", False)),
        ([("de", False), ("en-US", True)], ("en-US", True)),
        ([("de", True), ("fr", False)], ("fr", False)),
        ([("de", True), ("fr", True)], ("de", True)),
    ],
)
def test_language_preference(tracks, expected):
    available = []
    for language, generated in tracks:
        track = MagicMock(language_code=language, is_generated=generated)
        track.fetch.return_value = _mock_transcript_entries()
        available.append(track)
    with (
        patch("backend.services.transcript_service.get_video_info", return_value=_mock_video_info()),
        patch("backend.services.transcript_service.YouTubeTranscriptApi") as api,
    ):
        api.return_value.list.return_value = available
        result = extract_transcript("https://youtube.com/watch?v=dQw4w9WgXcQ")
    assert (result.language, result.is_generated) == expected


@pytest.mark.parametrize("error_name", ["RequestBlocked", "IpBlocked"])
def test_blocked_message(error_name):
    from youtube_transcript_api import _errors

    with (
        patch("backend.services.transcript_service.get_video_info", return_value=_mock_video_info()),
        patch("backend.services.transcript_service.YouTubeTranscriptApi") as api,
    ):
        api.return_value.list.side_effect = getattr(_errors, error_name)("video")
        with pytest.raises(
            TranscriptError,
            match="YouTube temporarily blocked transcript access from our server. Please try again later.",
        ):
            extract_transcript("https://youtube.com/watch?v=dQw4w9WgXcQ")


@pytest.mark.parametrize("caption_type,generated", [("subtitles", False), ("automatic_captions", True)])
def test_json3_fallback(caption_type, generated):
    info = {
        **_mock_video_info(),
        caption_type: {
            "fr": [{"ext": "json3", "url": "https://captions.test/fr"}],
            "en": [
                {"ext": "vtt", "url": "https://captions.test/vtt"},
                {"ext": "json3", "url": "https://captions.test/en"},
            ],
        },
    }
    with (
        patch("backend.services.transcript_service.get_video_info", return_value=info),
        patch("backend.services.transcript_service.YouTubeTranscriptApi") as api,
        patch("backend.services.transcript_service.httpx.Client") as client,
    ):
        api.return_value.list.side_effect = RuntimeError("primary failed")
        response = client.return_value.__enter__.return_value.get.return_value
        response.json.return_value = {
            "events": [
                {"tStartMs": 1500, "dDurationMs": 2500, "segs": [{"utf8": "Hello "}, {"utf8": "world"}]},
                {"segs": [{"utf8": "\n"}]},
                {"segs": [{"utf8": "[Music]"}]},
                {},
            ]
        }
        result = extract_transcript("https://youtube.com/watch?v=dQw4w9WgXcQ")
        client.return_value.__enter__.return_value.get.assert_called_once_with("https://captions.test/en")
    assert result.language == "en" and result.is_generated == generated
    assert result.full_text == "Hello world" and len(result.segments) == 1
    assert result.segments[0].start == 1.5 and result.segments[0].duration == 2.5


def test_first_error_preserved_when_fallback_fails():
    info = {**_mock_video_info(), "subtitles": {"en": [{"ext": "json3", "url": "https://captions.test/en"}]}}
    with (
        patch("backend.services.transcript_service.get_video_info", return_value=info),
        patch("backend.services.transcript_service.YouTubeTranscriptApi") as api,
        patch("backend.services.transcript_service.httpx.Client") as client,
    ):
        api.return_value.list.side_effect = RuntimeError("first failure")
        client.return_value.__enter__.return_value.get.side_effect = RuntimeError("second failure")
        with pytest.raises(TranscriptError, match="first failure"):
            extract_transcript("https://youtube.com/watch?v=dQw4w9WgXcQ")


def test_metadata_and_proxy(monkeypatch):
    from backend.services import transcript_service as ts

    monkeypatch.setattr(ts.settings, "TRANSCRIPT_PROXY_URL", "http://proxy.test:8080")
    with patch.object(ts.yt_dlp, "YoutubeDL") as ydl:
        ydl.return_value.__enter__.return_value.extract_info.return_value = dict(
            title=" Title ", channel=" Channel ", duration=120, channel_id="UC123", upload_date="20200921"
        )
        info = ts.get_video_info("dQw4w9WgXcQ")
        assert ydl.call_args.args[0]["proxy"] == "http://proxy.test:8080"
        assert ydl.call_args.args[0]["socket_timeout"] == 15
    assert info["upload_date"] == "2020-09-21" and info["channel_id"] == "UC123"
    with patch.object(ts, "get_video_info", return_value=info), patch.object(ts, "YouTubeTranscriptApi") as api:
        track = MagicMock(language_code="en", is_generated=False)
        track.fetch.return_value = _mock_transcript_entries()
        api.return_value.list.return_value = [track]
        result = extract_transcript("https://youtube.com/watch?v=dQw4w9WgXcQ")
        proxy = api.call_args.kwargs["proxy_config"]
        assert proxy.to_requests_dict() == {"http": "http://proxy.test:8080", "https": "http://proxy.test:8080"}
    assert result.published_at == "2020-09-21" and result.channel_id == "UC123"


@pytest.mark.parametrize(
    "seconds,formatted", [(0, "00:00"), (65, "01:05"), (3599, "59:59"), (3601, "1:00:01"), (-1, "00:00")]
)
def test_timestamp(seconds, formatted):
    from backend.services.transcript_service import format_timestamp

    assert format_timestamp(seconds) == formatted


def test_merge_transcript_lines():
    from backend.services.transcript_service import TranscriptSegment, build_timestamped_transcript

    segments = [
        TranscriptSegment(" First\n\tpart ", 65, 2),
        TranscriptSegment("second\r\n  part", 70, 2),
        TranscriptSegment("word " * 40, 75, 2),
        TranscriptSegment("last", 3601, 2),
    ]
    lines = build_timestamped_transcript(segments).splitlines()
    assert lines[0] == "[01:05] First part second part"
    assert lines[1].startswith("[01:15] word") and lines[-1] == "[1:00:01] last"
    assert build_timestamped_transcript([]) == ""
