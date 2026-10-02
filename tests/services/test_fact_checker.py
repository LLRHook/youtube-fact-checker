import asyncio
from unittest.mock import AsyncMock

import pytest

from backend.services import fact_checker as fc
from backend.services.llm import LLMResult, Usage
from backend.services.search_service import SearchResult
from backend.services.transcript_service import TranscriptResult, TranscriptSegment


@pytest.fixture
def transcript():
    return TranscriptResult(
        "dQw4w9WgXcQ", "Title", "Channel", 120, [TranscriptSegment("Words", 2, 5)], "Words", published_at="2021-01-01"
    )


def verdict(**kwargs):
    data = dict(
        verdict="mostly_false",
        confidence="high",
        explanation="  The core claim is wrong.  ",
        correction="  The accurate version.  ",
        relies_on_general_knowledge=False,
        citations=[dict(source=2, stance="refutes", quote="Contradicting passage")],
    )
    data.update(kwargs)
    return LLMResult(data, Usage(input_tokens=10, cost_usd=0.02), "end_turn")


async def test_verify_claim_grounded_and_sources_reordered(monkeypatch, transcript):
    evidence = [
        SearchResult("Context", "https://example.org", "Context passage", ["extra words"], "example.org", "medium"),
        SearchResult("Primary", "https://cdc.gov", "Contradicting passage", [], "cdc.gov", "high"),
    ]
    monkeypatch.setattr(fc, "gather_evidence", AsyncMock(return_value=(evidence, 3)))
    mock = AsyncMock(return_value=verdict())
    monkeypatch.setattr(fc, "structured_call", mock)
    context = fc.build_video_context_block(transcript)
    result, usage, count = await fc.verify_claim(
        dict(text="Claim", quote="Speaker words", timestamp_seconds=62, speaker="guest"), context
    )
    assert result["verdict"] == "mostly_false" and result["truth_percentage"] == 25
    assert result["confidence"] == 0.9 and result["category"] == "fact"
    assert result["corrected_claim"] == "The accurate version."
    assert result["reasoning"] == "The core claim is wrong."
    assert [s["title"] for s in result["sources"]] == ["Primary", "Context"]
    assert result["sources"][0]["stance"] == "refutes" and result["sources"][0]["quote"] == "Contradicting passage"
    assert (
        result["sources"][1]["stance"] == "" and result["sources"][1]["snippet"] == "Context passage \u2026 extra words"
    )
    assert count == 3 and usage.cost_usd == 0.02
    kwargs = mock.call_args.kwargs
    assert kwargs["system"] == [{"type": "text", "text": fc.VERDICT_SYSTEM}, context]
    assert context["cache_control"] == {"type": "ephemeral"}
    assert "[00:02] Words" in context["text"]
    assert "at 01:02, speaker: guest" in kwargs["messages"][0]["content"]
    assert kwargs["max_tokens"] == 8000


@pytest.mark.parametrize(
    "error,message",
    [
        ("refusal", "Our automated review could not assess this claim."),
        ("invalid_json", "We could not complete the assessment for this claim."),
    ],
)
async def test_llm_failure_keeps_uncited_evidence(monkeypatch, error, message):
    monkeypatch.setattr(
        fc, "gather_evidence", AsyncMock(return_value=([SearchResult("S", "https://example.org", "Passage")], 2))
    )
    monkeypatch.setattr(fc, "structured_call", AsyncMock(return_value=LLMResult(None, Usage(cost_usd=0.01), "", error)))
    result, usage, count = await fc.verify_claim({"text": "Claim"}, {})
    assert result["verdict"] == "unverifiable" and result["reasoning"] == message
    assert result["sources"][0]["stance"] == "" and usage.cost_usd == 0.01 and count == 2


async def test_retrieval_failure(monkeypatch):
    monkeypatch.setattr(fc, "gather_evidence", AsyncMock(side_effect=RuntimeError("search failed")))
    mock = AsyncMock()
    monkeypatch.setattr(fc, "structured_call", mock)
    result, usage, count = await fc.verify_claim({"text": "Claim"}, {})
    assert result["verdict"] == "unverifiable" and result["confidence_label"] == "low"
    assert result["reasoning"] == "We could not retrieve evidence for this claim right now."
    assert result["sources"] == [] and usage == Usage() and count == 0
    mock.assert_not_awaited()


async def test_explanation_and_correction_limits(monkeypatch):
    evidence = [SearchResult("Source", "https://cdc.gov", "Contradicting passage", reliability="high")]
    monkeypatch.setattr(fc, "gather_evidence", AsyncMock(return_value=(evidence, 1)))
    monkeypatch.setattr(
        fc,
        "structured_call",
        AsyncMock(
            return_value=verdict(
                explanation="x" * 1300,
                correction="y" * 500,
                citations=[dict(source=1, stance="refutes", quote="Contradicting passage")],
            )
        ),
    )
    result, _, _ = await fc.verify_claim({"text": "Claim"}, {})
    assert len(result["reasoning"]) == 1200 and len(result["corrected_claim"]) == 400


async def test_verify_all_warms_cache_preserves_order_and_concurrency(monkeypatch, transcript):
    events = []
    active = 0
    max_active = 0
    context_ids = []

    async def verify(claim, context):
        nonlocal active, max_active
        index = int(claim["text"])
        if index:
            assert "end0" in events
        events.append(f"start{index}")
        context_ids.append(id(context))
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01 * (4 - index))
        active -= 1
        events.append(f"end{index}")
        return fc._result("true", "high", "Evidence"), Usage(10, 5, cost_usd=0.01), 2

    monkeypatch.setattr(fc, "verify_claim", verify)
    monkeypatch.setattr(fc.settings, "FACT_CHECK_CONCURRENCY", 2)
    done = []
    results, usage, count = await fc.verify_all(
        [{"text": str(i)} for i in range(4)], transcript, lambda index, merged: done.append((index, merged))
    )
    assert events[:2] == ["start0", "end0"]
    assert [r["text"] for r in results] == ["0", "1", "2", "3"]
    assert len(set(context_ids)) == 1 and max_active == 2
    assert {index for index, _ in done} == {0, 1, 2, 3}
    assert (
        usage.input_tokens == 40 and usage.output_tokens == 20 and usage.cost_usd == pytest.approx(0.04) and count == 8
    )


async def test_verify_all_exception_padding_and_empty(monkeypatch, transcript):
    monkeypatch.setattr(
        fc,
        "verify_claim",
        AsyncMock(side_effect=[RuntimeError("failure"), (fc._result("true", "medium", "ok"), Usage(), 1)]),
    )
    results, _, count = await fc.verify_all([dict(text="first"), dict(text="second")], transcript)
    assert [r["text"] for r in results] == ["first", "second"]
    assert results[0]["verdict"] == "unverifiable" and results[1]["verdict"] == "true" and count == 1
    assert await fc.verify_all([], transcript) == ([], Usage(), 0)


async def test_summarize_fallback(monkeypatch, transcript):
    monkeypatch.setattr(fc, "structured_call", AsyncMock(return_value=LLMResult(None, Usage(), "", "refusal")))
    claims = [
        {"text": v, **fc._result(v, "medium", "Explanation")}
        for v in ["true", "mostly_true", "false", "mixed", "unverifiable"]
    ]
    summary, _ = await fc.summarize(transcript, claims)
    assert summary == dict(
        summary="Checked 5 claims: 2 accurate or mostly accurate, 1 false or mostly false, 1 mixed, 1 unverified.",
        key_issues=[],
    )
    summary, _ = await fc.summarize(transcript, claims[:2])
    assert summary["summary"] == "Checked 2 claims: 2 accurate or mostly accurate."


async def test_summary_success_limits(monkeypatch, transcript):
    mock = AsyncMock(
        return_value=LLMResult(dict(summary="x" * 900, key_issues=["y" * 250] * 4), Usage(cost_usd=0.03), "end_turn")
    )
    monkeypatch.setattr(fc, "structured_call", mock)
    report, usage = await fc.summarize(
        transcript, [{"text": "Claim", **fc._result("mixed", "low", "Explanation", "Correction")}]
    )
    assert len(report["summary"]) == 800 and [len(s) for s in report["key_issues"]] == [200] * 3
    assert usage.cost_usd == 0.03 and mock.call_args.kwargs["max_tokens"] == 4000
    assert "(Correction)" in mock.call_args.kwargs["messages"][0]["content"]
