"""Tests for backend.utils.validators."""

import pytest
from backend.utils.validators import extract_video_id, is_valid_youtube_url


class TestExtractVideoId:
    def test_standard_watch_url(self):
        assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_short_url(self):
        assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_embed_url(self):
        assert extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_shorts_url(self):
        assert extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_v_url(self):
        assert extract_video_id("https://www.youtube.com/v/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_bare_id(self):
        assert extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_extra_params(self):
        assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s") == "dQw4w9WgXcQ"

    def test_invalid_domain(self):
        assert extract_video_id("https://vimeo.com/123456") is None

    def test_empty_string(self):
        assert extract_video_id("") is None

    def test_short_id(self):
        assert extract_video_id("abc") is None

    def test_long_id(self):
        assert extract_video_id("dQw4w9WgXcQextra") is None

    def test_hyphens_underscores(self):
        assert extract_video_id("a-b_c-D_E-f") == "a-b_c-D_E-f"


class TestIsValidYoutubeUrl:
    def test_valid(self):
        assert is_valid_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is True

    def test_invalid(self):
        assert is_valid_youtube_url("https://example.com") is False

    def test_empty(self):
        assert is_valid_youtube_url("") is False
