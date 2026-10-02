from unittest.mock import AsyncMock

import pytest

from backend.services import fact_checker as fc
from backend.services.llm import LLMResult, Usage
from backend.services.search_service import SearchResult


@pytest.fixture
def evidence():
    return [
        SearchResult(
            "NASA",
            "https://nasa.gov",
            "Earth orbits the Sun. The “blue planet” has liquid water.",
            ["alpha beta gamma delta epsilon zeta eta theta iota kappa"],
            reliability="high",
        )
    ]


@pytest.mark.parametrize(
    "quote",
    [
        "Earth orbits the Sun",
        '  "The "blue planet"   has\nliquid water." ',
        "The blue-planet has liquid, water!",
        "Earth orbits ... liquid water",
        "alpha beta … iota kappa",
    ],
)
def test_grounded_quotes(evidence, quote):
    citation = dict(source=1, stance="supports", quote=quote)
    assert fc.validate_citations([citation], evidence) == [citation]


@pytest.mark.parametrize(
    "citation",
    [
        dict(source=0, stance="supports", quote="Earth"),
        dict(source=2, stance="supports", quote="Earth"),
        dict(source=1, stance="supports", quote=""),
        dict(source=1, stance="supports", quote="Invented unsupported statement"),
        dict(source=1, stance="supports", quote="alpha beta gamma delta epsilon zeta eta theta absent missing"),
        dict(source=1, stance="supports", quote="kappa iota theta eta zeta epsilon delta gamma beta missing"),
        dict(source=1, stance="supports", quote="liquid water ... Earth orbits"),
        dict(source=1, stance="supports", quote="... …"),
    ],
)
def test_invalid_quotes_dropped(evidence, citation):
    assert fc.validate_citations([citation], evidence) == []


def test_duplicate_source_stance_first_wins(evidence):
    first = dict(source=1, stance="supports", quote="Earth orbits the Sun")
    duplicate = dict(source=1, stance="supports", quote="liquid water")
    context = dict(source=1, stance="context", quote="liquid water")
    assert fc.validate_citations([first, duplicate, context], evidence) == [first, context]


def test_negation_cannot_be_omitted():
    evidence = [SearchResult("Study", "https://example.org", "Vaccines do not cause autism", [])]
    citation = dict(source=1, stance="supports", quote="Vaccines cause autism")
    assert fc.validate_citations([citation], evidence) == []


@pytest.mark.parametrize(
    "general,tier,citations,verdict,confidence",
    [
        (False, "high", [], "unverifiable", "low"),
        (True, "high", [], "true", "medium"),
        (False, "low", [dict(source=1, stance="supports", quote="Earth orbits the Sun")], "true", "low"),
        (False, "high", [dict(source=1, stance="supports", quote="Earth orbits the Sun")], "true", "high"),
    ],
)
async def test_post_rules(monkeypatch, evidence, general, tier, citations, verdict, confidence):
    evidence[0].reliability = tier
    monkeypatch.setattr(fc, "gather_evidence", AsyncMock(return_value=(evidence, 2)))
    monkeypatch.setattr(
        fc,
        "structured_call",
        AsyncMock(
            return_value=LLMResult(
                dict(
                    verdict="true",
                    confidence="high",
                    explanation="Model explanation.",
                    correction="Discard this.",
                    relies_on_general_knowledge=general,
                    citations=citations,
                ),
                Usage(),
                "end_turn",
            )
        ),
    )
    result, _, count = await fc.verify_claim({"text": "Earth orbits the Sun"}, {})
    assert result["verdict"] == verdict and result["confidence_label"] == confidence
    assert result["reasoning"] == "Model explanation."
    assert result["corrected_claim"] == "" and count == 2
