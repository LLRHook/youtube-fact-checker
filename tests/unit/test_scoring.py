"""Tests for scoring functions in backend.main."""

import pytest
from backend.main import _calculate_public_score, _safe_category
from backend.models import ClaimCategory


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
