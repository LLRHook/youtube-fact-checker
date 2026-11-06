"""Exercise Rust through provider service interfaces with synthetic peers."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.config import settings
from backend.services import claim_extractor, transcript_service

CASES = json.loads((Path(__file__).parents[1] / "fixtures/processor.json").read_text())
CLAIM_CASES = [case for case in CASES if case["request"]["op"] == "normalize_claims"]


@pytest.mark.parametrize("case", CLAIM_CASES, ids=lambda case: case["name"])
def test_model_output_normalized_in_service(case, monkeypatch):
    client = MagicMock()
    request = case["request"]
    client.messages.create.return_value = SimpleNamespace(content=[SimpleNamespace(text=request["text"])])
    monkeypatch.setattr(claim_extractor, "_get_anthropic_client", lambda: client)
    monkeypatch.setattr(settings, "MAX_CLAIMS_PER_VIDEO", request["max_claims"])
    assert claim_extractor.extract_claims("synthetic transcript", max_duration_seconds=request["max_duration"]) == case["expected"]


@pytest.mark.parametrize("content", [[], [SimpleNamespace()], [SimpleNamespace(text=None)], [SimpleNamespace(text=7)]])
def test_empty_or_wrong_model_content(content, monkeypatch):
    client = MagicMock()
    client.messages.create.return_value = SimpleNamespace(content=content)
    monkeypatch.setattr(claim_extractor, "_get_anthropic_client", lambda: client)
    assert claim_extractor.extract_claims("synthetic") == []


def test_caption_service_filters_invalid_rows_and_preserves_repetition(monkeypatch):
    rows = [SimpleNamespace(text=" hello 界 ", start="1.25", duration="2.5"),
            SimpleNamespace(text="[Music]", start=4, duration=1),
            SimpleNamespace(text=None, start=4, duration=1),
            SimpleNamespace(text="invalid", start=float("nan"), duration=1),
            SimpleNamespace(text="invalid", start=4, duration=float("inf")),
            SimpleNamespace(text="hello 界", start=-1, duration=-2), SimpleNamespace()]
    monkeypatch.setattr(transcript_service, "get_video_info", lambda _: dict(duration=120, title="Synthetic", channel="Test"))
    monkeypatch.setattr(transcript_service, "YouTubeTranscriptApi", lambda: SimpleNamespace(fetch=lambda _: rows))
    result = transcript_service.extract_transcript("https://youtu.be/a-b_c-D_E-f")
    assert result.full_text == "hello 界 hello 界"
    assert [(s.start, s.duration) for s in result.segments] == [(1.25, 2.5), (0, 0)]


@pytest.mark.parametrize("duration", [float("nan"), float("inf"), -1, None, {}, "oops"])
def test_invalid_duration_is_transcript_error_before_caption_fetch(duration, monkeypatch):
    monkeypatch.setattr(transcript_service, "get_video_info", lambda _: dict(duration=duration))
    fetch = MagicMock()
    monkeypatch.setattr(transcript_service, "YouTubeTranscriptApi", fetch)
    with pytest.raises(transcript_service.TranscriptError, match="Could not determine video duration"):
        transcript_service.extract_transcript("a-b_c-D_E-f")
    fetch.assert_not_called()
