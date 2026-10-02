"""Tests for scoring functions in backend.main."""

import pytest

from backend.main import _calculate_public_score, _safe_category
from backend.models import Claim, ClaimCategory, claim_row_to_public, legacy_verdict
from backend.services.fact_checker import VERDICT_SCORE, legacy_category, overall_score


class TestCalculatePublicScore:
    def test_no_claims(self):
        assert _calculate_public_score([]) == 50

    def test_no_fact_claims(self):
        claims = [{"category": "opinion", "confidence": 0.8, "truth_percentage": 90}]
        assert _calculate_public_score(claims) == 50

    def test_single_fact(self):
        claims = [{"category": "fact", "confidence": 1.0, "truth_percentage": 80}]
        assert _calculate_public_score(claims) == 80

    def test_weighted_average(self):
        claims = [
            {"category": "fact", "confidence": 1.0, "truth_percentage": 100},
            {"category": "fact", "confidence": 1.0, "truth_percentage": 0},
        ]
        assert _calculate_public_score(claims) == 50

    def test_all_true(self):
        claims = [
            {"category": "fact", "confidence": 0.9, "truth_percentage": 100},
            {"category": "fact", "confidence": 0.8, "truth_percentage": 100},
        ]
        assert _calculate_public_score(claims) == 100

    def test_all_false(self):
        claims = [
            {"category": "fact", "confidence": 0.9, "truth_percentage": 0},
            {"category": "fact", "confidence": 0.8, "truth_percentage": 0},
        ]
        assert _calculate_public_score(claims) == 0

    def test_mixed_categories(self):
        claims = [
            {"category": "fact", "confidence": 1.0, "truth_percentage": 70},
            {"category": "opinion", "confidence": 1.0, "truth_percentage": 20},
            {"category": "fact", "confidence": 1.0, "truth_percentage": 90},
        ]
        # Only facts: (70+90)/2 = 80
        assert _calculate_public_score(claims) == 80

    def test_zero_confidence(self):
        claims = [{"category": "fact", "confidence": 0, "truth_percentage": 100}]
        # total_weight = 0, so returns 50
        assert _calculate_public_score(claims) == 50

    def test_clamped_to_0_100(self):
        claims = [{"category": "fact", "confidence": 1.0, "truth_percentage": 150}]
        result = _calculate_public_score(claims)
        assert 0 <= result <= 100


class TestSafeCategory:
    def test_fact(self):
        assert _safe_category("fact") == ClaimCategory.FACT

    def test_opinion(self):
        assert _safe_category("opinion") == ClaimCategory.OPINION

    def test_unclear(self):
        assert _safe_category("unclear") == ClaimCategory.UNCLEAR

    def test_invalid_defaults_to_fact(self):
        assert _safe_category("bogus") == ClaimCategory.FACT

    def test_empty_defaults_to_fact(self):
        assert _safe_category("") == ClaimCategory.FACT

    def test_uppercase_defaults_to_fact(self):
        # ClaimCategory uses lowercase values, so "FACT" is invalid
        assert _safe_category("FACT") == ClaimCategory.FACT


@pytest.mark.parametrize(
    "verdict,score",
    [
        ("true", 95),
        ("mostly_true", 75),
        ("mixed", 50),
        ("mostly_false", 25),
        ("false", 5),
        ("unverifiable", 50),
        ("opinion", 50),
    ],
)
def test_verdict_score(verdict, score):
    assert VERDICT_SCORE[verdict] == score


def test_overall_weighting():
    assert (
        overall_score(
            [
                dict(verdict="true", truth_percentage=95, confidence=0.9),
                dict(verdict="false", truth_percentage=5, confidence=0.35),
                dict(verdict="unverifiable", truth_percentage=50, confidence=0.9),
            ]
        )
        == 70
    )


@pytest.mark.parametrize("claims", [[], [dict(verdict="opinion")], [dict(verdict="unverifiable")]])
def test_no_checkable_claims(claims):
    assert overall_score(claims) is None


def test_legacy_scoring():
    assert (
        overall_score(
            [
                dict(category="fact", truth_percentage=90, confidence=0.8),
                dict(category="opinion", truth_percentage=0, confidence=1),
            ]
        )
        == 90
    )


@pytest.mark.parametrize(
    "category,score,expected",
    [
        ("opinion", 99, "opinion"),
        ("unclear", 99, "unverifiable"),
        ("fact", 85, "true"),
        ("fact", 84, "mostly_true"),
        ("fact", 65, "mostly_true"),
        ("fact", 64, "mixed"),
        ("fact", 40, "mixed"),
        ("fact", 39, "mostly_false"),
        ("fact", 20, "mostly_false"),
        ("fact", 19, "false"),
    ],
)
def test_legacy_verdict(category, score, expected):
    assert legacy_verdict(category, score) == expected
    assert Claim(id="legacy", text="claim", category=category, truth_percentage=score).verdict == expected
    assert claim_row_to_public(dict(category=category, truth_percentage=score, verdict=None)).verdict == expected


@pytest.mark.parametrize("confidence,label", [(0.8, "high"), (0.5, "medium"), (0.49, "low")])
def test_legacy_confidence_label(confidence, label):
    assert claim_row_to_public(dict(confidence=confidence, verdict=None)).confidence_label == label


def test_legacy_categories():
    assert legacy_category("opinion") == "opinion"
    assert legacy_category("unverifiable") == "unclear"
    assert legacy_category("false") == "fact"
